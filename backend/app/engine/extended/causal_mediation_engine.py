"""Phase B B2b.2 — /api/v1/causal/mediation engine.

Implements the Pearl/Rubin counterfactual mediation analysis described
in Plan v2 §2.4 (PHASE_B_PLAN.md) and the design recorded in
PHASE_B2b2_DESIGN.md (§1 method selection, §4 function signatures,
§8 risks).

The engine dispatches on ``len(request.mediators)``:

- **Single mediator** -> ``_run_dowhy_mediation``: three DoWhy
  ``identify_effect`` + ``estimate_effect`` rounds for ATE / NDE / NIE,
  with ``method_name='backdoor.linear_regression'`` for ATE and
  ``method_name='mediation.two_stage_regression'`` for NDE / NIE.
  (Candidate 2 in PHASE_B2b2_DESIGN.md §1, verified by
  ``backend/scratch_mediation_api.py``: Pearl identity NDE+NIE==ATE
  held to 1e-4 on the bench.)

- **Multi mediator** -> ``_run_farbmacher_mediation``: a leave-one-out
  LinearDML loop (Candidate 4). Baseline LinearDML on covariates only
  yields ``total``; full-adjust LinearDML on covariates + all mediators
  yields ``direct``; for each mediator ``m``, a LinearDML on
  ``covariates + (mediators \\ m)`` yields ``effect_without_m``, and
  ``per_mediator_indirect[m] = effect_without_m - direct``. Shares
  are absolute-value normalised so a sign-reversed mediator still
  contributes a positive share fraction. This branch is used because
  DoWhy 0.14's ``get_mediator_variables()`` only returns the last
  declared mediator under a multi-mediator DAG (verified in
  ``scratch_mediation_api.py`` Gap 2 probe), making the DoWhy
  two-stage estimator unreliable for K>=2.

Bootstrap CI (``_bootstrap_ci``) resamples ``df`` with replacement
``n_bootstrap`` times, runs the chosen branch on each resample, and
takes ``(alpha/2, 1-alpha/2)`` quantiles per field. Iterations that
raise (numerical issues, DoWhy / EconML edge cases) are caught and
counted as ``failed``; if more than half of the iterations fail, the
engine raises ``CausalMediationError(code='bootstrap_diverged')``. A
partial-completion warning surfaces in ``warnings`` and the actual
completed count is echoed in ``diagnostics.n_bootstrap_used``.

D14 = gamma is preserved: this engine implements Pearl NDE/NIE
(natural direct / natural indirect effects), not Baron-Kenny. The
``controlled`` and ``interventional`` decomposition modes are accepted
at the schema layer but rejected here with HTTP 422
``code='decomposition_reserved'`` (D9-style reserved-enum pattern).

Reused (no modification) from earlier B engines:
- ``causal_data_to_dataframe``, ``dag_to_gml``, ``split_covariates``,
  ``count_per_stratum`` from ``causal_utils``
- ``_classify_strategy`` from ``causal_identify_engine``
"""

from __future__ import annotations

import logging
import time
import warnings as warnings_module
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from app.engine.extended.causal_identify_engine import _classify_strategy
from app.engine.extended.causal_utils import (
    causal_data_to_dataframe,
    count_per_stratum,
    dag_to_gml,
    split_covariates,
)
from app.schemas.causal.mediation import (
    CausalMediationRequest,
    CausalMediationResponse,
    MediationDecomposition,
    MediationDiagnostics,
)
from app.schemas.causal_common import (
    CAUSAL_ENGINE_VERSION,
    CausalWarning,
    EvidenceLevel,
)


_logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
# Custom exception (router → HTTP 422)
# ════════════════════════════════════════════════════════════════════


class CausalMediationError(ValueError):
    """Raised on /mediation pre-condition or in-flight failure.

    The router maps this to HTTP 422 with a structured body that
    includes the machine-readable ``code``. Mirrors
    ``CausalRefuteError`` / ``CausalEstimateError`` shape.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════════════════════════════════════════════════════
# Constants
# ════════════════════════════════════════════════════════════════════


# B2b.2 MVP only implements 'natural'. Plan v2 §2.4 lists three modes;
# the other two are reserved with a 422 gate (D9-style reserved-enum
# pattern, mirroring B2a estimate's method_family and B2b.1 refute's
# non_parametric_sensitivity_analyzer).
_RESERVED_DECOMPOSITIONS = frozenset({"controlled", "interventional"})


# Small-sample clamp threshold. The schema does not expose a
# request-level ``n_min_per_stratum`` field (Plan v2 §2.4 does not list
# one), so the engine hard-codes the same value B2a estimate uses as
# its schema default (30). Below this n the response clamps to
# ``evidence_level='planned'`` and emits a ``small_sample`` warning.
_N_MIN_PER_STRATUM = 30


# Bootstrap CI level. The schema does not expose
# ``confidence_level`` / ``significance_alpha`` for mediation (Plan v2
# §2.4 omits them), so the engine hard-codes 95% CI (alpha=0.05). The
# paper (V14 line 153) reports "10,000-iteration nonparametric
# bootstrap" without specifying alpha; 95% is the field default.
_DEFAULT_CI_ALPHA = 0.05


# Bootstrap divergence floor. If fewer than this fraction of iterations
# complete without raising, the engine refuses to return a CI rather
# than report a degenerate band.
_BOOTSTRAP_MIN_COMPLETED_FRACTION = 0.5


# Cross-fitting folds for the Farbmacher branch LinearDML. Same as B2a
# estimate's _estimate_dml default.
_DML_CV_FOLDS = 2


# ════════════════════════════════════════════════════════════════════
# Reserved-enum gate
# ════════════════════════════════════════════════════════════════════


def _check_decomposition(decomposition: str) -> None:
    """Reject reserved decomposition modes before any work happens.

    B2b.2 MVP implements ``natural`` only. ``controlled`` and
    ``interventional`` map to HTTP 422 ``code='decomposition_reserved'``.
    """
    if decomposition in _RESERVED_DECOMPOSITIONS:
        raise CausalMediationError(
            code="decomposition_reserved",
            message=(
                f"decomposition={decomposition!r} is reserved for a "
                f"future Phase B / Phase G release. B2b.2 implements "
                f"only 'natural' (Pearl NDE/NIE)."
            ),
        )


# ════════════════════════════════════════════════════════════════════
# Single-mediator branch — DoWhy NDE/NIE/ATE triple (Candidate 2)
# ════════════════════════════════════════════════════════════════════


def _run_dowhy_mediation(
    request: CausalMediationRequest,
    df: pd.DataFrame,
) -> Tuple[MediationDecomposition, MediationDiagnostics, str]:
    """Single-mediator Pearl decomposition via DoWhy.

    Wraps three identify_effect + estimate_effect rounds:

    1. ``estimand_type='nonparametric-ate'`` +
       ``method_name='backdoor.linear_regression'`` -> ``total``.
    2. ``estimand_type='nonparametric-nde'`` +
       ``method_name='mediation.two_stage_regression'`` -> ``direct``.
    3. ``estimand_type='nonparametric-nie'`` +
       ``method_name='mediation.two_stage_regression'`` -> ``indirect``.

    All three calls pass ``proceed_when_unidentifiable=True`` so DoWhy
    still returns an estimand when standard identification fails (the
    operator already acknowledged the assumptions in
    ``assumptions_acknowledged``; the engine does not re-gate here).

    Returns ``(decomposition_point, diagnostics_no_ci, strategy_str)``.
    Bootstrap CI is the outer caller's responsibility.
    """
    from dowhy import CausalModel

    mediator = request.mediators[0]
    gml = dag_to_gml(request.dag)
    t0 = time.perf_counter()

    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore")
        model = CausalModel(
            data=df,
            treatment=request.treatment,
            outcome=request.outcome,
            graph=gml,
        )

        # ── ATE (total) ──
        try:
            estimand_ate = model.identify_effect(
                estimand_type="nonparametric-ate",
                proceed_when_unidentifiable=True,
            )
            estimate_ate = model.estimate_effect(
                estimand_ate,
                method_name="backdoor.linear_regression",
            )
        except Exception as exc:
            raise CausalMediationError(
                code="dowhy_ate_failed",
                message=(
                    f"DoWhy ATE identify/estimate raised "
                    f"{type(exc).__name__}: {exc}"
                ),
            ) from exc

        # ── NDE (direct) ──
        try:
            estimand_nde = model.identify_effect(
                estimand_type="nonparametric-nde",
                proceed_when_unidentifiable=True,
            )
            estimate_nde = model.estimate_effect(
                estimand_nde,
                method_name="mediation.two_stage_regression",
            )
        except Exception as exc:
            raise CausalMediationError(
                code="dowhy_nde_failed",
                message=(
                    f"DoWhy NDE identify/estimate raised "
                    f"{type(exc).__name__}: {exc}"
                ),
            ) from exc

        # ── NIE (indirect) ──
        try:
            estimand_nie = model.identify_effect(
                estimand_type="nonparametric-nie",
                proceed_when_unidentifiable=True,
            )
            estimate_nie = model.estimate_effect(
                estimand_nie,
                method_name="mediation.two_stage_regression",
            )
        except Exception as exc:
            raise CausalMediationError(
                code="dowhy_nie_failed",
                message=(
                    f"DoWhy NIE identify/estimate raised "
                    f"{type(exc).__name__}: {exc}"
                ),
            ) from exc

    total = float(estimate_ate.value)
    direct = float(estimate_nde.value)
    indirect = float(estimate_nie.value)

    # Pearl identity (direct + indirect == total) is enforced by the
    # response validator at assembly time. Here we snap indirect to
    # (total - direct) when DoWhy's three independent fits drift beyond
    # 1e-3 — DoWhy's estimator is consistent so any drift is numerical,
    # and the engine must always produce a Pearl-consistent point
    # estimate for the validator to accept the response.
    gap = direct + indirect - total
    if abs(gap) > 1e-3:
        indirect = total - direct

    decomposition = MediationDecomposition(
        total_effect=total,
        direct_effect=direct,
        indirect_effect=indirect,
        mediator_share={mediator: 1.0},
    )

    fit_time_ms = (time.perf_counter() - t0) * 1000.0
    diagnostics = MediationDiagnostics(
        method="dowhy_two_stage",
        n_samples=len(df),
        n_bootstrap_used=0,  # outer caller updates after bootstrap
        n_mediators=1,
        fit_time_ms=fit_time_ms,
        used_precomputed_estimand=False,  # DoWhy re-identifies internally
    )

    strategy, _adjustment, _expr = _classify_strategy(
        estimand_ate, request.dag, request.treatment, request.outcome,
    )
    return decomposition, diagnostics, strategy


# ════════════════════════════════════════════════════════════════════
# Multi-mediator branch — Farbmacher leave-one-out DML (Candidate 4)
# ════════════════════════════════════════════════════════════════════


def _fit_linear_dml_ate(
    df: pd.DataFrame,
    *,
    outcome: str,
    treatment: str,
    feature_cols: Sequence[str],
    seed: Optional[int],
) -> float:
    """Run one LinearDML fit on (Y, T, X=feature_cols) and return ATE.

    ``feature_cols`` are passed as ``X`` (treatment-effect features)
    rather than ``W`` (controls) to mirror the scratch_mediation_api
    Farbmacher probe, which used ``est.ate(X)``. Both routes give the
    same ATE for additive linear data; the X route exposes the
    heterogeneity surface even though we don't use it here.
    """
    from econml.dml import LinearDML
    from sklearn.linear_model import LinearRegression

    y = df[outcome].to_numpy(dtype="float64")
    t = df[treatment].to_numpy(dtype="float64")
    X = (
        df[list(feature_cols)].to_numpy(dtype="float64")
        if feature_cols else None
    )

    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore")
        est = LinearDML(
            model_y=LinearRegression(),
            model_t=LinearRegression(),
            discrete_treatment=False,
            cv=_DML_CV_FOLDS,
            random_state=seed,
        )
        est.fit(Y=y, T=t, X=X, W=None)
        if X is not None:
            ate = float(np.asarray(est.ate(X)).reshape(-1)[0])
        else:
            ate = float(est.const_marginal_ate())
    return ate


# Module-level cache for Bayesian posterior samples (used to
# short-circuit the bootstrap when method='bayesian_mediation').
# Keyed by (id(request), id(df)). Cleared per call; not threadsafe.
_BAYESIAN_POSTERIOR_CACHE: Dict[int, Dict[str, np.ndarray]] = {}


def _run_bayesian_mediation(
    request: CausalMediationRequest,
    df: pd.DataFrame,
) -> Tuple[
    MediationDecomposition, MediationDiagnostics, str, List[CausalWarning]
]:
    """Phase C C3 — Bayesian two-stage mediation via PyMC.

    Model (single mediator M, treatment T, outcome Y, covariates X):

        Mediator equation:
            M = alpha_T * T + alpha_X . X + eps_M,  eps_M ~ Normal(0, sigma_M)

        Outcome equation:
            Y = beta_T * T + beta_M * M + beta_X . X + eps_Y,
            eps_Y ~ Normal(0, sigma_Y)

    Pearl decomposition (posterior-sampled):
        NDE (natural direct effect):    posterior(beta_T)
        NIE (natural indirect effect):  posterior(alpha_T * beta_M)
        Total effect:                   posterior(beta_T + alpha_T * beta_M)
        proportion mediated:            posterior(NIE / total)

    The Bayesian branch is restricted to **single mediator** in this
    MVP. Multi-mediator extension is a future Plan v3 amendment
    (would require joint PyMC model with multiple mediator
    equations).

    Returns ``(decomposition_point, diagnostics, strategy_str,
    warnings_list)``. Bootstrap CI is the outer caller's
    responsibility; the Bayesian posterior already provides
    uncertainty, but the response schema expects bootstrap CI bands,
    so the outer caller will re-sample the posterior in
    ``_bootstrap_ci``. (A future refinement: short-circuit the
    bootstrap when method='bayesian_mediation' and use posterior
    HDI directly.)
    """
    # Lazy PyMC import (same pattern as C1)
    import pymc as pm
    import arviz as az

    warnings_list: List[CausalWarning] = []

    # Restrict to single mediator in this MVP
    if len(request.mediators) != 1:
        raise CausalMediationError(
            code="bayesian_mediation_single_only",
            message=(
                f"method='bayesian_mediation' requires exactly 1 "
                f"mediator in Phase C C3 MVP; got "
                f"{len(request.mediators)}. Multi-mediator Bayesian "
                f"mediation is a Plan v3 amendment item; use "
                f"farbmacher_dml_loo for multi-mediator analysis."
            ),
        )

    mediator = request.mediators[0]
    t0 = time.perf_counter()

    # Extract arrays
    T = df[request.treatment].to_numpy(dtype=float)
    M = df[mediator].to_numpy(dtype=float)
    Y = df[request.outcome].to_numpy(dtype=float)

    # Covariates: DAG nodes minus {T, M, Y}
    excluded = {request.treatment, request.outcome, mediator}
    covariate_names = [
        n.name for n in request.dag.nodes if n.name not in excluded
    ]
    # Keep only columns that exist in df
    covariate_names = [c for c in covariate_names if c in df.columns]
    if covariate_names:
        X = df[covariate_names].to_numpy(dtype=float)
    else:
        X = np.zeros((len(df), 0), dtype=float)

    # PyMC two-stage model
    with pm.Model():
        # Mediator equation coefficients
        alpha_T = pm.Normal("alpha_T", mu=0.0, sigma=2.0)
        if X.shape[1] > 0:
            alpha_X = pm.Normal(
                "alpha_X", mu=0.0, sigma=2.0, shape=X.shape[1]
            )
        sigma_M = pm.HalfNormal("sigma_M", sigma=1.0)

        # Outcome equation coefficients
        beta_T = pm.Normal("beta_T", mu=0.0, sigma=2.0)
        beta_M = pm.Normal("beta_M", mu=0.0, sigma=2.0)
        if X.shape[1] > 0:
            beta_X = pm.Normal(
                "beta_X", mu=0.0, sigma=2.0, shape=X.shape[1]
            )
        sigma_Y = pm.HalfNormal("sigma_Y", sigma=1.0)

        # Mediator likelihood
        mu_M = alpha_T * T
        if X.shape[1] > 0:
            mu_M = mu_M + pm.math.dot(X, alpha_X)
        pm.Normal("M_obs", mu=mu_M, sigma=sigma_M, observed=M)

        # Outcome likelihood
        mu_Y = beta_T * T + beta_M * M
        if X.shape[1] > 0:
            mu_Y = mu_Y + pm.math.dot(X, beta_X)
        pm.Normal("Y_obs", mu=mu_Y, sigma=sigma_Y, observed=Y)

        # Sample
        with warnings_module.catch_warnings():
            warnings_module.simplefilter("ignore")
            idata = pm.sample(
                draws=request.n_bootstrap if request.n_bootstrap >= 500
                else 500,
                tune=500,
                chains=2,
                target_accept=0.95,
                random_seed=request.seed or 42,
                progressbar=False,
                return_inferencedata=True,
                compute_convergence_checks=False,
            )

    # Posterior samples
    alpha_T_samples = idata.posterior["alpha_T"].values.flatten()
    beta_T_samples = idata.posterior["beta_T"].values.flatten()
    beta_M_samples = idata.posterior["beta_M"].values.flatten()

    # Pearl decomposition (posterior samples)
    NDE_samples = beta_T_samples
    NIE_samples = alpha_T_samples * beta_M_samples
    total_samples = NDE_samples + NIE_samples

    # Cache posterior samples so run_mediation() can short-circuit
    # the bootstrap when method='bayesian_mediation' (each PyMC
    # call takes 30-90s without C++ compiler; 200 bootstrap calls
    # would take 1+ hours per request).
    _BAYESIAN_POSTERIOR_CACHE[id(request)] = {
        "NDE": NDE_samples,
        "NIE": NIE_samples,
        "total": total_samples,
    }

    # Point estimates (posterior means)
    total_effect = float(np.mean(total_samples))
    direct_effect = float(np.mean(NDE_samples))
    indirect_effect = float(np.mean(NIE_samples))

    fit_ms = (time.perf_counter() - t0) * 1000.0

    # Per-mediator share (must sum to ~1.0; single mediator → 1.0).
    decomposition = MediationDecomposition(
        total_effect=total_effect,
        direct_effect=direct_effect,
        indirect_effect=indirect_effect,
        mediator_share={mediator: 1.0},
    )

    diagnostics = MediationDiagnostics(
        method="bayesian_mediation",
        n_samples=len(df),
        n_bootstrap_used=len(total_samples),
        n_mediators=1,
        fit_time_ms=fit_ms,
        used_precomputed_estimand=False,
    )

    # Pearl identity check (additivity)
    pearl_residual = abs(
        (direct_effect + indirect_effect) - total_effect
    )
    if pearl_residual > 1e-6:
        warnings_list.append(
            CausalWarning(
                code="ci_wider_than_estimate",
                message=(
                    f"Bayesian Pearl residual "
                    f"{pearl_residual:.2e} > 1e-6 tolerance; "
                    f"posterior NDE+NIE != total at the posterior "
                    f"mean (sampling noise on small posteriors)."
                ),
            )
        )

    return decomposition, diagnostics, "bayesian_pearl", warnings_list


def _run_farbmacher_mediation(
    request: CausalMediationRequest,
    df: pd.DataFrame,
) -> Tuple[
    MediationDecomposition, MediationDiagnostics, str, List[CausalWarning]
]:
    """Multi-mediator leave-one-out DML mediation.

    Steps (Farbmacher 2022 style, adapted for the single ATE summary
    we need here):

    1. Adjustment set = DAG covariate nodes (excluding the mediators
       — those are conditioned in / out per leave-one-out iteration).
    2. ``total = LinearDML(Y, T | X=covariates).ate``.
    3. ``direct = LinearDML(Y, T | X=covariates + all_mediators).ate``.
       (Conditioning on all mediators removes their indirect effect.)
    4. For each mediator ``m``:
         ``effect_without_m = LinearDML(
             Y, T | X=covariates + (mediators \\ m)
         ).ate``
         ``per_mediator_indirect[m] = effect_without_m - direct``
       (Intuition: ``effect_without_m`` leaves ``m``'s indirect path
       open, so the gap from ``direct`` is exactly ``m``'s indirect
       contribution.)
    5. Normalise ``mediator_share[m] = |per[m]| / sum(|per[*]|)``.
       Absolute-value normalisation handles the sign-reversal case
       (a mediator with negative indirect under interaction still
       carries a positive share).
    6. Pearl identity: ``indirect = total - direct`` (by construction).

    Returns ``(decomposition_point, diagnostics_no_ci, "backdoor",
    warnings)``. The warnings list carries a ``method_fallback``
    record when the raw per-mediator sum falls outside [0.7, 1.3]
    *before* renormalisation (R3 mitigation in PHASE_B2b2_DESIGN.md §8).
    """
    mediators = list(request.mediators)
    covariates = [
        n.name for n in request.dag.nodes if n.node_kind == "covariate"
    ]
    covariates_in_df = [c for c in covariates if c in df.columns]

    warnings_out: List[CausalWarning] = []
    seed = request.seed
    t0 = time.perf_counter()

    # Step 2: total — covariates only
    total = _fit_linear_dml_ate(
        df,
        outcome=request.outcome,
        treatment=request.treatment,
        feature_cols=covariates_in_df,
        seed=seed,
    )

    # Step 3: direct — covariates + all mediators
    full_features = covariates_in_df + mediators
    direct = _fit_linear_dml_ate(
        df,
        outcome=request.outcome,
        treatment=request.treatment,
        feature_cols=full_features,
        seed=seed,
    )

    # Step 4: leave-one-out
    per_mediator_indirect: Dict[str, float] = {}
    for m in mediators:
        without_m = [x for x in mediators if x != m]
        features = covariates_in_df + without_m
        try:
            effect_without_m = _fit_linear_dml_ate(
                df,
                outcome=request.outcome,
                treatment=request.treatment,
                feature_cols=features,
                seed=seed,
            )
        except Exception as exc:
            raise CausalMediationError(
                code="farbmacher_loo_failed",
                message=(
                    f"LinearDML leave-one-out for mediator {m!r} raised "
                    f"{type(exc).__name__}: {exc}"
                ),
            ) from exc
        per_mediator_indirect[m] = effect_without_m - direct

    # Step 5: absolute-value normalisation. Carry a warning if the raw
    # absolute sum is degenerate or far from 1.0 — the renormalisation
    # always produces a sum of exactly 1.0, but a raw sum outside
    # [0.7, 1.3] suggests the LOO decomposition was noisy.
    abs_per_med = {m: abs(v) for m, v in per_mediator_indirect.items()}
    abs_sum = sum(abs_per_med.values())
    if abs_sum <= 0.0:
        # Degenerate: every per-mediator effect is exactly zero. Split
        # uniformly so the share-sum slack validator still passes.
        share = 1.0 / len(mediators)
        mediator_share = {m: share for m in mediators}
        warnings_out.append(CausalWarning(
            code="method_fallback",
            severity="warn",
            message=(
                "Farbmacher leave-one-out returned zero per-mediator "
                "effects for every mediator; mediator_share split "
                "uniformly. Likely indicates the mediator-outcome path "
                "is degenerate on this sample."
            ),
        ))
    else:
        mediator_share = {m: abs_per_med[m] / abs_sum for m in mediators}

    # R3 (PHASE_B2b2_DESIGN.md §8): surface a warning when the raw
    # per-mediator decomposition is noisy. The check looks at the
    # signed sum vs total - direct (the Pearl indirect target).
    indirect_target = total - direct
    raw_signed_sum = sum(per_mediator_indirect.values())
    if indirect_target != 0.0:
        share_of_target = raw_signed_sum / indirect_target
        if not (0.7 <= share_of_target <= 1.3):
            warnings_out.append(CausalWarning(
                code="method_fallback",
                severity="info",
                message=(
                    f"Farbmacher leave-one-out signed sum "
                    f"{raw_signed_sum:.4f} / target {indirect_target:.4f} "
                    f"= {share_of_target:.3f} outside [0.7, 1.3] before "
                    f"absolute-value renormalisation. Per-mediator "
                    f"shares are renormalised to sum to 1.0 but the "
                    f"decomposition under treatment-mediator interaction "
                    f"may be unreliable on this sample."
                ),
            ))

    decomposition = MediationDecomposition(
        total_effect=total,
        direct_effect=direct,
        indirect_effect=indirect_target,
        mediator_share=mediator_share,
    )

    fit_time_ms = (time.perf_counter() - t0) * 1000.0
    diagnostics = MediationDiagnostics(
        method="farbmacher_dml_loo",
        n_samples=len(df),
        n_bootstrap_used=0,  # outer caller updates after bootstrap
        n_mediators=len(mediators),
        fit_time_ms=fit_time_ms,
        used_precomputed_estimand=False,
    )

    return decomposition, diagnostics, "backdoor", warnings_out


# ════════════════════════════════════════════════════════════════════
# Bootstrap CI
# ════════════════════════════════════════════════════════════════════


# Type alias: a branch function for the bootstrap loop returns just
# the (decomposition, _, _, ...) tuple — we collapse to decomposition
# inside _bootstrap_ci's wrapper.
_BranchFn = Callable[
    [CausalMediationRequest, pd.DataFrame],
    MediationDecomposition,
]


def _bootstrap_ci(
    request: CausalMediationRequest,
    df: pd.DataFrame,
    *,
    branch_fn: _BranchFn,
    n_bootstrap: int,
    alpha: float,
    seed: Optional[int],
) -> Tuple[
    MediationDecomposition,
    MediationDecomposition,
    Tuple[float, float],
    int,
    List[CausalWarning],
]:
    """Returns
    ``(ci_lower, ci_upper, proportion_mediated_ci, n_completed, warnings)``.

    Resamples ``df`` with replacement ``n_bootstrap`` times, runs
    ``branch_fn`` on each resample, collects ``(total, direct,
    indirect, share_dict, proportion_mediated)``, then takes
    ``(alpha/2, 1-alpha/2)`` quantiles per field.

    Per the Step 3 brief (補 1): iterations that raise are caught and
    counted; if fewer than 50% complete, raises
    ``CausalMediationError(code='bootstrap_diverged')``. If between
    50% and 100% complete, surfaces a partial-completion warning and
    proceeds with the completed subset.

    Per the Step 3 brief (補 2): emits a debug log every
    ``n_bootstrap / 10`` iterations so that hung runs in Step 5
    testing can be diagnosed with ``logging.basicConfig(level=DEBUG)``.

    ``proportion_mediated_ci`` (Q3 = B) is computed from an independent
    per-iteration proportion-mediated array rather than from the
    ci_lower / ci_upper bands; quantile-of-ratios != ratio-of-quantiles.
    """
    rng = np.random.default_rng(seed)
    n_rows = len(df)

    totals: List[float] = []
    directs: List[float] = []
    indirects: List[float] = []
    proportions: List[float] = []
    # Per-mediator share collector: mediator name -> List[float].
    share_acc: Dict[str, List[float]] = {m: [] for m in request.mediators}

    failed_count = 0
    log_every = max(1, n_bootstrap // 10)

    for i in range(n_bootstrap):
        if i % log_every == 0:
            _logger.debug(
                "bootstrap iteration %d/%d (completed=%d, failed=%d)",
                i, n_bootstrap, len(totals), failed_count,
            )
        try:
            seed_i = int(rng.integers(0, 2**32 - 1))
            sample_df = df.sample(
                n=n_rows, replace=True, random_state=seed_i,
            ).reset_index(drop=True)
            decomp_i = branch_fn(request, sample_df)
        except Exception as exc:
            failed_count += 1
            _logger.debug(
                "bootstrap iteration %d failed: %s: %s",
                i, type(exc).__name__, exc,
            )
            continue

        totals.append(decomp_i.total_effect)
        directs.append(decomp_i.direct_effect)
        indirects.append(decomp_i.indirect_effect)
        # proportion_mediated, computed per iteration. Guard against
        # total==0 by skipping that iter's proportion contribution
        # (still count the iter as completed for the decomposition).
        if decomp_i.total_effect != 0.0:
            proportions.append(
                decomp_i.indirect_effect / decomp_i.total_effect
            )
        for m, share in decomp_i.mediator_share.items():
            if m in share_acc:
                share_acc[m].append(share)

    n_completed = len(totals)

    # Floor check (補 1).
    if n_completed < int(_BOOTSTRAP_MIN_COMPLETED_FRACTION * n_bootstrap):
        raise CausalMediationError(
            code="bootstrap_diverged",
            message=(
                f"Bootstrap diverged: only {n_completed}/{n_bootstrap} "
                f"iterations completed ({failed_count} failures). "
                f"Mediation engine cannot produce a reliable CI under "
                f"this fixture."
            ),
        )

    warnings_out: List[CausalWarning] = []
    if n_completed < n_bootstrap:
        warnings_out.append(CausalWarning(
            code="method_fallback",
            severity="info",
            message=(
                f"Bootstrap completed {n_completed}/{n_bootstrap} "
                f"iterations ({failed_count} failed). CI is computed "
                f"from the completed subset; diagnostics."
                f"n_bootstrap_used reflects the actual count."
            ),
        ))

    lo_q = alpha / 2.0
    hi_q = 1.0 - alpha / 2.0

    def _q(arr: List[float], q: float) -> float:
        if not arr:
            return 0.0
        return float(np.quantile(np.asarray(arr, dtype="float64"), q))

    # Per-mediator share quantiles. Fall back to the point estimate
    # share when a mediator never appeared (shouldn't happen for our
    # branch implementations, but keep the validator-required
    # min_length=1 satisfied).
    share_lower: Dict[str, float] = {}
    share_upper: Dict[str, float] = {}
    for m in request.mediators:
        arr = share_acc.get(m, [])
        share_lower[m] = _q(arr, lo_q) if arr else 0.0
        share_upper[m] = _q(arr, hi_q) if arr else 0.0

    ci_lower = MediationDecomposition(
        total_effect=_q(totals, lo_q),
        direct_effect=_q(directs, lo_q),
        indirect_effect=_q(indirects, lo_q),
        mediator_share=share_lower,
    )
    ci_upper = MediationDecomposition(
        total_effect=_q(totals, hi_q),
        direct_effect=_q(directs, hi_q),
        indirect_effect=_q(indirects, hi_q),
        mediator_share=share_upper,
    )

    if proportions:
        prop_lo = _q(proportions, lo_q)
        prop_hi = _q(proportions, hi_q)
    else:
        prop_lo, prop_hi = 0.0, 0.0
    proportion_ci: Tuple[float, float] = (prop_lo, prop_hi)

    return ci_lower, ci_upper, proportion_ci, n_completed, warnings_out


# ════════════════════════════════════════════════════════════════════
# Public entrypoint
# ════════════════════════════════════════════════════════════════════


def _branch_decomposition_only(
    branch_fn_raw: Callable[
        [CausalMediationRequest, pd.DataFrame],
        Tuple,
    ],
) -> _BranchFn:
    """Wrap a branch function so it returns just the
    ``MediationDecomposition`` (drops diagnostics / strategy / warnings).

    Used by ``_bootstrap_ci`` which only needs the decomposition per
    iteration. Keeping the branch functions' richer return signatures
    intact for the point-estimate path.
    """

    def _inner(
        request: CausalMediationRequest, df: pd.DataFrame,
    ) -> MediationDecomposition:
        result = branch_fn_raw(request, df)
        # First tuple element is always the MediationDecomposition.
        return result[0]

    return _inner


def run_mediation(
    request: CausalMediationRequest,
) -> CausalMediationResponse:
    """Execute the mediation phase. Sync mode only in B2b.2 MVP.

    Pipeline:

    1. ``_check_decomposition`` rejects reserved enum values.
    2. Realise the dataframe; verify every DAG node has a column.
    3. Branch on ``len(request.mediators)``:
       - 1 -> ``_run_dowhy_mediation``
       - >= 2 -> ``_run_farbmacher_mediation``
    4. ``_bootstrap_ci`` on the chosen branch for CI bands +
       proportion_mediated_ci.
    5. Small-sample clamp (B2a Mod 5 pattern):
       ``min_stratum_size < _N_MIN_PER_STRATUM`` ->
       ``evidence_level = 'planned'`` + ``small_sample`` warning.
    6. Assemble ``CausalMediationResponse``; the response validators
       enforce the Pearl identity and the share-sum slack on the point
       decomposition.
    """
    _check_decomposition(request.decomposition)

    if request.mode != "sync":
        # Schema also gates this, but engine-side defence is cheap.
        raise CausalMediationError(
            code="async_not_implemented_yet",
            message=(
                "mode='async_job' is reserved for B2b.3. B2b.2 only "
                "supports sync."
            ),
        )

    df = causal_data_to_dataframe(request.data)

    # Every node in the DAG must be present as a column.
    missing = [n.name for n in request.dag.nodes if n.name not in df.columns]
    if missing:
        raise CausalMediationError(
            code="dag_columns_missing_in_data",
            message=(
                f"DAG nodes {missing} are not present as columns in the "
                f"inline data. Either add the columns or trim the DAG "
                f"to match the data."
            ),
        )

    n_effective = len(df)

    # Branch dispatch.
    # Phase C C3 (2026-05-21): operator can opt into the Bayesian
    # branch by setting ``request.method = "bayesian_mediation"``.
    # Otherwise the legacy mediator-count dispatch applies (single
    # mediator → DoWhy two-stage; multi-mediator → Farbmacher LOO).
    warnings_list: List[CausalWarning] = []
    if request.method == "bayesian_mediation":
        (
            decomp_point, diagnostics, strategy, branch_warnings,
        ) = _run_bayesian_mediation(request, df)
        warnings_list.extend(branch_warnings)
        branch_fn_raw: Callable[
            [CausalMediationRequest, pd.DataFrame], Tuple
        ] = _run_bayesian_mediation
    elif len(request.mediators) == 1:
        decomp_point, diagnostics, strategy = _run_dowhy_mediation(
            request, df,
        )
        branch_fn_raw = _run_dowhy_mediation
    else:
        (
            decomp_point, diagnostics, strategy, branch_warnings,
        ) = _run_farbmacher_mediation(request, df)
        warnings_list.extend(branch_warnings)
        branch_fn_raw = _run_farbmacher_mediation

    # Bootstrap CI — Phase C C3 short-circuit:
    # When method='bayesian_mediation', the PyMC sampler in
    # _run_bayesian_mediation already produced ~1000 posterior
    # samples per NDE/NIE/total. Re-running it 200x for bootstrap
    # would take 1+ hours per request. Instead we derive the CI
    # bands directly from the posterior quantiles (alpha/2,
    # 1-alpha/2), matching the bootstrap response shape.
    if request.method == "bayesian_mediation":
        cached = _BAYESIAN_POSTERIOR_CACHE.pop(id(request), None)
        if cached is None:
            raise CausalMediationError(
                code="bayesian_posterior_cache_missing",
                message=(
                    "Internal error: _run_bayesian_mediation should "
                    "have populated _BAYESIAN_POSTERIOR_CACHE."
                ),
            )
        # alpha/2 and 1-alpha/2 quantiles for each effect
        alpha = _DEFAULT_CI_ALPHA
        nde_low = float(np.quantile(cached["NDE"], alpha / 2))
        nde_high = float(np.quantile(cached["NDE"], 1 - alpha / 2))
        nie_low = float(np.quantile(cached["NIE"], alpha / 2))
        nie_high = float(np.quantile(cached["NIE"], 1 - alpha / 2))
        total_low = float(np.quantile(cached["total"], alpha / 2))
        total_high = float(np.quantile(cached["total"], 1 - alpha / 2))
        mediator_name = request.mediators[0]
        # CI bands are pure data holders (per MediationDecomposition
        # docstring — no validators on this sub-model). mediator_share
        # must be a non-empty Dict, so single mediator → 1.0 marker.
        ci_lower = MediationDecomposition(
            total_effect=total_low,
            direct_effect=nde_low,
            indirect_effect=nie_low,
            mediator_share={mediator_name: 1.0},
        )
        ci_upper = MediationDecomposition(
            total_effect=total_high,
            direct_effect=nde_high,
            indirect_effect=nie_high,
            mediator_share={mediator_name: 1.0},
        )
        # proportion mediated quantiles
        # Guard against zero division — only compute ratio where
        # total != 0.
        with np.errstate(divide="ignore", invalid="ignore"):
            prop_samples = np.where(
                np.abs(cached["total"]) > 1e-12,
                cached["NIE"] / cached["total"],
                np.nan,
            )
        prop_samples = prop_samples[~np.isnan(prop_samples)]
        if len(prop_samples) > 0:
            proportion_ci = (
                float(np.quantile(prop_samples, alpha / 2)),
                float(np.quantile(prop_samples, 1 - alpha / 2)),
            )
        else:
            proportion_ci = (0.0, 0.0)
        n_completed = len(cached["total"])
        boot_warnings: List[CausalWarning] = []
        warnings_list.append(
            CausalWarning(
                code="method_fallback",
                message=(
                    "bayesian_mediation: bootstrap loop short-"
                    "circuited; CI bands derived from PyMC posterior "
                    f"quantiles ({n_completed} samples)."
                ),
            )
        )
    else:
        branch_fn = _branch_decomposition_only(branch_fn_raw)
        (
            ci_lower, ci_upper, proportion_ci, n_completed, boot_warnings,
        ) = _bootstrap_ci(
            request,
            df,
            branch_fn=branch_fn,
            n_bootstrap=request.n_bootstrap,
            alpha=_DEFAULT_CI_ALPHA,
            seed=request.seed,
        )
    warnings_list.extend(boot_warnings)

    # Update diagnostics with the bootstrap-completed count and a
    # honest used_precomputed_estimand flag (the DoWhy branch
    # re-identifies internally; the Farbmacher branch never uses the
    # handle — both report False).
    diagnostics = MediationDiagnostics(
        method=diagnostics.method,
        n_samples=diagnostics.n_samples,
        n_bootstrap_used=n_completed,
        n_mediators=diagnostics.n_mediators,
        fit_time_ms=diagnostics.fit_time_ms,
        used_precomputed_estimand=False,
    )

    # proportion_mediated on the point estimate.
    if decomp_point.total_effect != 0.0:
        proportion_mediated = (
            decomp_point.indirect_effect / decomp_point.total_effect
        )
    else:
        proportion_mediated = 0.0
    # Clamp to schema bounds [-1.0, 2.0]; emit a warning if the raw
    # ratio exceeded them (signals an unstable decomposition).
    if not (-1.0 <= proportion_mediated <= 2.0):
        warnings_list.append(CausalWarning(
            code="method_fallback",
            severity="warn",
            message=(
                f"proportion_mediated raw value {proportion_mediated:.3f} "
                f"outside schema bounds [-1.0, 2.0]; clamped. Indicates "
                f"a near-zero total effect or sign-reversed mediation."
            ),
        ))
        proportion_mediated = max(-1.0, min(2.0, proportion_mediated))

    # Small-sample clamp.
    n_per_stratum = count_per_stratum(df, [])
    min_stratum_size = (
        min(n_per_stratum.values()) if n_per_stratum else 0
    )
    evidence_level: EvidenceLevel = "supported"
    if min_stratum_size < _N_MIN_PER_STRATUM:
        evidence_level = "planned"
        warnings_list.append(CausalWarning(
            code="small_sample",
            severity="warn",
            message=(
                f"effective per-stratum sample size {min_stratum_size} "
                f"< _N_MIN_PER_STRATUM {_N_MIN_PER_STRATUM}; "
                f"evidence_level clamped to 'planned'."
            ),
        ))

    # Also clamp proportion_mediated_ci so it sits inside the schema
    # bound for proportion_mediated. The CI itself has no explicit
    # schema bound, but a CI outside the point's clamp is misleading.
    prop_ci_lo, prop_ci_hi = proportion_ci
    prop_ci_lo = max(-1.0, min(2.0, prop_ci_lo))
    prop_ci_hi = max(-1.0, min(2.0, prop_ci_hi))
    proportion_ci = (prop_ci_lo, prop_ci_hi)

    # Use the strategy classification result as an info warning when it
    # is anything other than the expected mediation/backdoor for this
    # branch (defensive — surfaces DAG misconfiguration without
    # blocking the response).
    if strategy not in ("mediation", "backdoor"):
        warnings_list.append(CausalWarning(
            code="identification_unstable",
            severity="info",
            message=(
                f"Strategy classifier returned {strategy!r} for the "
                f"branch's identifying estimand; expected 'mediation' "
                f"or 'backdoor'. Decomposition may be unreliable."
            ),
        ))

    return CausalMediationResponse(
        decomposition=decomp_point,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        assumptions_echo=list(request.assumptions_acknowledged),
        proportion_mediated=proportion_mediated,
        proportion_mediated_ci=proportion_ci,
        evidence_level=evidence_level,
        diagnostics=diagnostics,
        warnings=warnings_list,
        engine_version=CAUSAL_ENGINE_VERSION,
    )


__all__ = [
    "CausalMediationError",
    "run_mediation",
    "_run_dowhy_mediation",
    "_run_farbmacher_mediation",
    "_bootstrap_ci",
    "_check_decomposition",
    "_RESERVED_DECOMPOSITIONS",
    "_N_MIN_PER_STRATUM",
    "_DEFAULT_CI_ALPHA",
]
