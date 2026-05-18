"""Phase B — /api/v1/causal/estimate engine.

Wraps DoWhy's ``estimate_effect`` (for ``linear_regression`` and
``propensity_score`` method families) and EconML's ``LinearDML`` (for
the ``dml`` family). Phase B MVP (D9=α) ships these three only;
``causal_forest_dml`` / ``x_learner`` are reserved enum values that
this engine refuses with HTTP 422 ``code='method_family_reserved'``.

Reference: PHASE_B_PLAN.md §2.2 + §2.8.
"""

from __future__ import annotations

import time
import warnings
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from app.engine.extended.causal_identify_engine import (
    _classify_strategy,
    _strategy_to_evidence_level,
)
from app.engine.extended.causal_utils import (
    causal_data_to_dataframe,
    cheap_evalue,
    count_per_stratum,
    dag_to_gml,
    has_continuous_covariate,
    split_covariates,
)
from app.schemas.causal.estimate import (
    CausalEstimateRequest,
    CausalEstimateResponse,
    EstimateDiagnostics,
    MethodFamily,
)
from app.schemas.causal_common import (
    CAUSAL_ENGINE_VERSION,
    CausalWarning,
    EstimateHandle,
    EvidenceLevel,
    IdentifiedEstimandHandle,
)


# ════════════════════════════════════════════════════════════════════
# Custom exceptions surfaced as HTTP errors by the router
# ════════════════════════════════════════════════════════════════════


class CausalEstimateError(ValueError):
    """Raised when /estimate's pre-conditions or post-conditions fail.

    Router maps to HTTP 422 with a structured body that includes a
    machine-readable ``code``.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════════════════════════════════════════════════════
# Method dispatch
# ════════════════════════════════════════════════════════════════════


_RESERVED_FAMILIES = frozenset(("causal_forest_dml", "x_learner"))


def _check_method_family(family: MethodFamily) -> None:
    """Reject reserved method families before any work happens."""
    if family in _RESERVED_FAMILIES:
        raise CausalEstimateError(
            code="method_family_reserved",
            message=(
                f"method_family={family!r} is reserved for a future Phase-B-2 "
                f"release. Phase B MVP supports only 'linear_regression', "
                f"'propensity_score', and 'dml' (D9=α single LinearDML)."
            ),
        )


def _resolve_sklearn_model(name: str):
    """Map a DmlParams.model_y / model_t string to a sklearn estimator
    instance. Kept centralised so /refute can re-fit identically."""
    if name == "linear_regression":
        from sklearn.linear_model import LinearRegression
        return LinearRegression()
    if name == "lasso":
        from sklearn.linear_model import Lasso
        return Lasso(random_state=0)
    if name == "ridge":
        from sklearn.linear_model import Ridge
        return Ridge(random_state=0)
    if name == "logistic":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(max_iter=1000, random_state=0)
    raise CausalEstimateError(
        code="unknown_sklearn_model",
        message=f"Unsupported nuisance model name: {name!r}.",
    )


# ════════════════════════════════════════════════════════════════════
# DoWhy / EconML adapters
# ════════════════════════════════════════════════════════════════════


def _adjustment_set_for_estimate(
    request: CausalEstimateRequest,
    df: pd.DataFrame,
) -> List[str]:
    """Use the precomputed estimand when provided; otherwise re-identify
    via DoWhy and take its backdoor (or frontdoor) variables.

    Plan v2 Mod 4: never re-identify when the caller supplied a
    precomputed_estimand — that defeats the divergence-prevention
    purpose of the handle.
    """
    if request.precomputed_estimand is not None:
        return list(request.precomputed_estimand.adjustment_set)

    # Re-identify on the fly. Reuse identify_engine's classifier rather
    # than the full /identify endpoint (no need for the response shell).
    from dowhy import CausalModel
    gml = dag_to_gml(request.dag)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = CausalModel(
            data=df,
            treatment=request.treatment,
            outcome=request.outcome,
            graph=gml,
        )
        try:
            estimand = model.identify_effect(
                proceed_when_unidentifiable=True,
                method_name="default",
            )
        except Exception as exc:
            raise CausalEstimateError(
                code="identification_failed",
                message=f"identify_effect raised: {type(exc).__name__}",
            ) from exc
    strategy, adjustment_set, _expr = _classify_strategy(
        estimand, request.dag, request.treatment, request.outcome
    )
    if strategy == "unidentifiable":
        raise CausalEstimateError(
            code="unidentifiable_dag",
            message=(
                "DAG is unidentifiable under standard assumptions. "
                "Call /api/v1/causal/identify with "
                "proceed_when_unidentifiable=true to obtain a planned-"
                "level estimand handle, or revise the DAG."
            ),
        )
    return adjustment_set


def _confidence_z(level: float) -> float:
    """Two-sided z for a normal CI; e.g. level=0.95 → 1.959964."""
    # Use scipy when available (it is, per requirements.txt); fall back
    # to a closed-form approximation otherwise.
    try:
        from scipy.stats import norm
        return float(norm.ppf(0.5 + level / 2.0))
    except Exception:  # pragma: no cover
        # Beasley-Springer-Moro inverse normal CDF (sufficient for B2a).
        a = (1.0 - level) / 2.0
        # Acklam's approximation
        p = 1.0 - a
        t = (-2.0 * np.log(p)) ** 0.5
        c = [
            2.515517, 0.802853, 0.010328,
            1.432788, 0.189269, 0.001308,
        ]
        z = t - (
            (c[0] + c[1] * t + c[2] * t * t)
            / (1.0 + c[3] * t + c[4] * t * t + c[5] * t * t * t)
        )
        return float(z)


def _estimate_linear_regression(
    request: CausalEstimateRequest,
    df: pd.DataFrame,
    adjustment_set: List[str],
) -> Tuple[float, float, float, float, str]:
    """Linear regression of Y on T + adjustment set; returns
    (point_estimate, std_error, ci_lower, ci_upper, method_used).

    Uses statsmodels OLS so we get a t-distribution CI for free.
    """
    import statsmodels.api as sm

    y = df[request.outcome].to_numpy(dtype="float64")
    t = df[request.treatment].to_numpy(dtype="float64")
    X_cols = [request.treatment] + [
        c for c in adjustment_set if c in df.columns and c != request.treatment
    ]
    X = df[X_cols].to_numpy(dtype="float64")
    X = sm.add_constant(X, has_constant="add")
    model = sm.OLS(y, X).fit()
    # Coefficient on treatment is at column index 1 (after the constant).
    beta = float(model.params[1])
    se = float(model.bse[1])
    z = _confidence_z(request.confidence_level)
    return (
        beta,
        se,
        beta - z * se,
        beta + z * se,
        "linear_regression (statsmodels OLS)",
    )


def _estimate_propensity_score(
    request: CausalEstimateRequest,
    df: pd.DataFrame,
    adjustment_set: List[str],
    *,
    seed: int | None,
) -> Tuple[float, float, float, float, str]:
    """Propensity-score IPW estimate via DoWhy."""
    from dowhy import CausalModel
    gml = dag_to_gml(request.dag)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = CausalModel(
            data=df, treatment=request.treatment,
            outcome=request.outcome, graph=gml,
        )
        estimand = model.identify_effect(proceed_when_unidentifiable=True)
        est = model.estimate_effect(
            estimand,
            method_name="backdoor.propensity_score_weighting",
            confidence_intervals=True,
            target_units=request.target_units,
        )
    point = float(est.value)
    ci = getattr(est, "get_confidence_intervals", lambda: None)()
    if ci is not None:
        try:
            arr = np.asarray(ci, dtype="float64").reshape(-1)
            ci_low, ci_high = float(arr[0]), float(arr[1])
        except Exception:
            ci_low, ci_high = point, point
    else:
        ci_low, ci_high = point, point
    # Propensity-score doesn't yield an obvious SE; approximate from the
    # CI half-width and the same z used for the CI.
    z = _confidence_z(request.confidence_level)
    se = (ci_high - ci_low) / (2.0 * z) if z > 0 else 0.0
    return (
        point, max(se, 0.0), ci_low, ci_high,
        "propensity_score (DoWhy backdoor.propensity_score_weighting)",
    )


def _estimate_dml(
    request: CausalEstimateRequest,
    df: pd.DataFrame,
    adjustment_set: List[str],
    *,
    seed: int | None,
) -> Tuple[float, float, float, float, str, Dict[str, float]]:
    """EconML LinearDML estimate.

    Returns (point, se, ci_lower, ci_upper, method_used, heterogeneity_summary).
    """
    from econml.dml import LinearDML

    # D9=α MVP: enforce ≥1 continuous covariate.
    if not has_continuous_covariate(df, adjustment_set):
        raise CausalEstimateError(
            code="no_continuous_covariate",
            message=(
                "method_family='dml' requires at least one continuous "
                "covariate in the adjustment set. Adjustment set "
                f"{adjustment_set} has none. Either add a continuous "
                "control to the DAG or switch to "
                "method_family='linear_regression'."
            ),
        )

    cont, disc = split_covariates(df, adjustment_set)
    X = df[cont].to_numpy(dtype="float64") if cont else None
    W = df[disc].to_numpy(dtype="float64") if disc else None
    y = df[request.outcome].to_numpy(dtype="float64")
    t = df[request.treatment].to_numpy(dtype="float64")

    dml_params = request.method_params.dml
    if dml_params is None:
        # Apply Phase B defaults.
        model_y = _resolve_sklearn_model("linear_regression")
        model_t = _resolve_sklearn_model("linear_regression")
        discrete_treatment = False
        cv = 2
        random_state = seed
    else:
        model_y = _resolve_sklearn_model(dml_params.model_y)
        model_t = _resolve_sklearn_model(dml_params.model_t)
        discrete_treatment = dml_params.discrete_treatment
        cv = dml_params.cv
        random_state = (
            dml_params.random_state
            if dml_params.random_state is not None
            else seed
        )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        est = LinearDML(
            model_y=model_y,
            model_t=model_t,
            discrete_treatment=discrete_treatment,
            cv=cv,
            random_state=random_state,
        )
        est.fit(Y=y, T=t, X=X, W=W)
        # ATE on the marginal distribution.
        if X is not None:
            ate = float(np.asarray(est.ate(X)).reshape(-1)[0])
        else:
            ate = float(est.const_marginal_ate())
        # CI
        try:
            if X is not None:
                lb, ub = est.ate_interval(X, alpha=1 - request.confidence_level)
                ci_lower = float(np.asarray(lb).reshape(-1)[0])
                ci_upper = float(np.asarray(ub).reshape(-1)[0])
            else:
                lb, ub = est.const_marginal_ate_interval(
                    alpha=1 - request.confidence_level
                )
                ci_lower = float(np.asarray(lb).reshape(-1)[0])
                ci_upper = float(np.asarray(ub).reshape(-1)[0])
        except Exception:
            ci_lower, ci_upper = ate, ate
        # CATE summary on continuous covariates
        if X is not None:
            try:
                cate = np.asarray(est.effect(X)).reshape(-1)
                heterogeneity = {
                    "cate_mean": float(np.mean(cate)),
                    "cate_std": float(np.std(cate)),
                    "cate_min": float(np.min(cate)),
                    "cate_max": float(np.max(cate)),
                }
            except Exception:
                heterogeneity = {}
        else:
            heterogeneity = {}
    z = _confidence_z(request.confidence_level)
    se = (ci_upper - ci_lower) / (2.0 * z) if z > 0 else 0.0
    return (
        ate, max(se, 0.0), ci_lower, ci_upper,
        "dml (EconML LinearDML)", heterogeneity,
    )


# ════════════════════════════════════════════════════════════════════
# Public entrypoint
# ════════════════════════════════════════════════════════════════════


def run_estimate(
    request: CausalEstimateRequest,
) -> CausalEstimateResponse:
    """Execute the estimation phase. Sync mode only in Phase B MVP.

    Per Plan v2 §2.2: when ``n_used_per_stratum.min() <
    n_min_per_stratum``, ``evidence_level`` clamps to ``'planned'``
    and a ``'small_sample'`` warning is added — but **no error is
    raised**. The paper's n=4/arm experiment is itself a valid
    demonstrator.
    """
    _check_method_family(request.method_family)

    if request.mode != "sync":
        # B2a ships sync only; B2b wires up the async-job protocol.
        raise CausalEstimateError(
            code="async_not_implemented_yet",
            message=(
                "mode='async_job' is reserved for B2b. Phase B B2a "
                "MVP only supports sync."
            ),
        )

    # Realise the dataframe.
    df = causal_data_to_dataframe(request.data)
    # Validate columns: every node in the DAG must be a column (so
    # statsmodels / EconML can index it).
    missing = [
        n.name for n in request.dag.nodes if n.name not in df.columns
    ]
    if missing:
        raise CausalEstimateError(
            code="dag_columns_missing_in_data",
            message=(
                f"DAG nodes {missing} are not present as columns in "
                f"the inline data. Either add the columns or trim the "
                f"DAG to match the data."
            ),
        )

    adjustment_set = _adjustment_set_for_estimate(request, df)
    used_precomputed = request.precomputed_estimand is not None

    n_per_stratum = count_per_stratum(df, [])  # no auto-strat for B2a
    n_effective = len(df)

    warnings_list: List[CausalWarning] = []

    # ── Run estimator ──
    seed = request.seed
    t0 = time.perf_counter()
    if request.method_family == "linear_regression":
        point, se, ci_lower, ci_upper, method_used = _estimate_linear_regression(
            request, df, adjustment_set
        )
        heterogeneity = None
    elif request.method_family == "propensity_score":
        point, se, ci_lower, ci_upper, method_used = _estimate_propensity_score(
            request, df, adjustment_set, seed=seed,
        )
        heterogeneity = None
    elif request.method_family == "dml":
        (
            point, se, ci_lower, ci_upper, method_used, heterogeneity,
        ) = _estimate_dml(request, df, adjustment_set, seed=seed)
    else:  # pragma: no cover - already filtered by _check_method_family
        raise CausalEstimateError(
            code="method_family_internal",
            message=f"unexpected method_family={request.method_family!r}",
        )
    fit_time_ms = (time.perf_counter() - t0) * 1000.0

    # Response-time invariant: ci_lower <= point <= ci_upper (the schema
    # validator will refuse otherwise). If the estimator produced a
    # degenerate CI (e.g. when ATE landed outside the CI due to
    # numerical noise), widen the CI just enough to satisfy the
    # invariant and emit a 'ci_wider_than_estimate' warning.
    if not (ci_lower <= point <= ci_upper):
        eps = max(abs(point) * 1e-6, 1e-9)
        ci_lower = min(ci_lower, point - eps)
        ci_upper = max(ci_upper, point + eps)
        warnings_list.append(CausalWarning(
            code="ci_wider_than_estimate",
            severity="info",
            message=(
                "estimator returned a CI that did not bracket the point "
                "estimate; CI was widened by eps to satisfy response "
                "invariant."
            ),
        ))

    # ── Cheap E-value (continuous outcome) ──
    std_outcome = float(df[request.outcome].std(ddof=1))
    e_value = cheap_evalue(point, std_outcome)

    # ── evidence_level clamp ──
    # B2a only does the n_min clamp; the refute endpoint (B2b) will
    # tighten further. Default initial level when the estimand is
    # available is 'supported'; 'validated' is reserved for the
    # post-refute path.
    evidence_level: EvidenceLevel = "supported"

    min_stratum_size = min(n_per_stratum.values()) if n_per_stratum else 0
    if min_stratum_size < request.n_min_per_stratum:
        evidence_level = "planned"
        warnings_list.append(CausalWarning(
            code="small_sample",
            severity="warn",
            message=(
                f"effective per-stratum sample size {min_stratum_size} "
                f"< n_min_per_stratum {request.n_min_per_stratum}; "
                f"evidence_level clamped to 'planned'."
            ),
        ))

    if request.method_family == "dml":
        # DML auto-promotion is not granted here; refute does it. But we
        # surface the continuous-covariate count so the operator sees
        # the precondition was met.
        cont, _ = split_covariates(df, adjustment_set)
        n_cont = len(cont)
    else:
        cont, disc = split_covariates(df, adjustment_set)
        n_cont = len(cont)
    cont_all, disc_all = split_covariates(df, adjustment_set)

    diagnostics = EstimateDiagnostics(
        method=method_used,
        n_samples=n_effective,
        n_treated=int(np.sum(df[request.treatment] > 0)),
        n_control=int(np.sum(df[request.treatment] <= 0)),
        n_continuous_covariates=len(cont_all),
        n_discrete_covariates=len(disc_all),
        cv_folds=(
            request.method_params.dml.cv
            if request.method_params.dml is not None
            else None
        ),
        fit_time_ms=fit_time_ms,
        used_precomputed_estimand=used_precomputed,
    )

    handle = EstimateHandle(
        dag=request.dag,
        treatment=request.treatment,
        outcome=request.outcome,
        method_family=request.method_family,
        method_params=(
            request.method_params.model_dump(exclude_none=True)
            if request.method_params is not None
            else {}
        ),
        data=request.data,
        seed=seed,
        issued_at=datetime.now(timezone.utc),
    )

    return CausalEstimateResponse(
        point_estimate=point,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        std_error=se if se >= 0 else None,
        method_used=method_used,
        n_used_per_stratum=n_per_stratum,
        n_effective=n_effective,
        heterogeneity_summary=heterogeneity,
        e_value_cheap=e_value,
        estimate_handle=handle,
        diagnostics=diagnostics,
        evidence_level=evidence_level,
        warnings=warnings_list,
        engine_version=CAUSAL_ENGINE_VERSION,
    )
