"""
BOS Pipeline v9.0 / Phase B — Causal Inference Router.

Phase B (B2a) contract:

    POST /api/v1/causal/identify   — DoWhy 4-step pipeline phase 1+2
                                     (model + identify). Returns the
                                     identifiable estimand or honest
                                     `unidentifiable` verdict.

    POST /api/v1/causal/estimate   — DoWhy 4-step pipeline phase 3.
                                     LinearDML (D9=α MVP) +
                                     linear_regression + propensity_score.
                                     Reserved enum values
                                     (causal_forest_dml, x_learner)
                                     422-rejected.

Phase B B2b.1 added /refute; B2b.2 added /mediation; B2b.3 adds
/sensitivity. Async-job mode reserved across all endpoints until a
later batch.

Reference: PHASE_B_PLAN.md §2.1, §2.2, §2.3, §2.4, §2.5, §2.7.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import require_minimum_role
from app.models import User
from app.schemas.causal.estimate import (
    CausalEstimateRequest,
    CausalEstimateResponse,
)
from app.schemas.causal.identify import (
    CausalIdentifyRequest,
    CausalIdentifyResponse,
)
from app.schemas.causal.refute import (
    CausalRefuteRequest,
    CausalRefuteResponse,
)
from app.schemas.causal.mediation import (
    CausalMediationRequest,
    CausalMediationResponse,
)
from app.schemas.causal.sensitivity import (
    CausalSensitivityRequest,
    CausalSensitivityResponse,
)
from app.engine.extended.causal_identify_engine import run_identify
from app.engine.extended.causal_estimate_engine import (
    CausalEstimateError,
    run_estimate,
)
from app.engine.extended.causal_refute_engine import (
    CausalRefuteError,
    run_refute,
)
from app.engine.extended.causal_mediation_engine import (
    CausalMediationError,
    run_mediation,
)
from app.engine.extended.causal_sensitivity_engine import (
    CausalSensitivityError,
    run_sensitivity,
)
from app.schemas.causal.bayesian import (
    BayesianEstimateRequest,
    BayesianEstimateResponse,
)
from app.engine.extended.causal_bayesian_engine import (
    CausalBayesianError,
    estimate_ate_bayesian,
)
from app.schemas.causal.conformal import (
    ConformalPredictRequest,
    ConformalPredictResponse,
)
from app.engine.extended.causal_conformal_engine import (
    CausalConformalError,
    predict_conformal,
)


router = APIRouter()


# ════════════════════════════════════════════════════════════════════
# /identify
# ════════════════════════════════════════════════════════════════════


@router.post(
    "/identify",
    response_model=CausalIdentifyResponse,
    summary="Phase B — causal identification (DoWhy CausalModel.identify_effect)",
)
async def identify_endpoint(
    body: CausalIdentifyRequest,
    current_user: User = Depends(require_minimum_role("operator")),
) -> CausalIdentifyResponse:
    """
    Resolve the identifiable estimand for a (treatment, outcome) pair
    under the supplied DAG.

    Paper map: paper §3.6.1 (*"Pearl / Rubin counterfactual mediation
    analysis on the Signal-API → κ → SER pathway"*).

    The endpoint never 500s on unidentifiable graphs — instead it
    returns ``identified=False, strategy="unidentifiable",
    evidence_level="planned"``. Schema-layer validators catch the
    structural errors (cycle, missing nodes, treatment with no
    outgoing edges) and 422 them.
    """
    try:
        return run_identify(body)
    except ValueError as exc:
        # Engine-layer pre-condition violation. Surface as 422 with the
        # exception's message; we don't expose stack traces.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "identify_failed", "message": str(exc)},
        ) from exc


# ════════════════════════════════════════════════════════════════════
# /estimate
# ════════════════════════════════════════════════════════════════════


@router.post(
    "/estimate",
    response_model=CausalEstimateResponse,
    summary="Phase B — causal effect estimation (LinearDML MVP)",
)
async def estimate_endpoint(
    body: CausalEstimateRequest,
    current_user: User = Depends(require_minimum_role("operator")),
) -> CausalEstimateResponse:
    """
    Compute an ATE / ATT / ATC for the (treatment, outcome) pair on
    the supplied data.

    Method families (B2a MVP):

    - ``linear_regression`` — statsmodels OLS.
    - ``propensity_score`` — DoWhy backdoor.propensity_score_weighting.
    - ``dml`` — EconML LinearDML (D9=α; requires ≥1 continuous covariate).

    Reserved values ``causal_forest_dml`` and ``x_learner`` are
    422-rejected with ``code='method_family_reserved'`` (D9=α MVP
    keeps the public OpenAPI surface forward-compatible).

    Sync-mode requests with inline row count > 10_000 are
    422-rejected at validator time; use ``mode='async_job'`` (B2b)
    for larger datasets.

    When the effective per-stratum sample size falls below
    ``n_min_per_stratum`` (default 30), the response is forced to
    ``evidence_level='planned'`` and a ``'small_sample'`` warning is
    added — but **no error is raised**. The paper's n=4/arm
    experiment is itself a valid demonstrator.
    """
    try:
        return run_estimate(body)
    except CausalEstimateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "estimate_failed", "message": str(exc)},
        ) from exc


# ════════════════════════════════════════════════════════════════════
# /refute (B2b.1)
# ════════════════════════════════════════════════════════════════════


@router.post(
    "/refute",
    response_model=CausalRefuteResponse,
    summary=(
        "Phase B — causal refutation (DoWhy refuters + evidence-level "
        "aggregation, Plan v2 §2.3 patched)"
    ),
)
async def refute_endpoint(
    body: CausalRefuteRequest,
    current_user: User = Depends(require_minimum_role("operator")),
) -> CausalRefuteResponse:
    """
    Runs DoWhy refuters against the estimate referenced by
    ``estimate_handle`` (echoed from a previous /estimate response).

    Refuters (B2b.1):

    - Mandatory (4): ``random_common_cause``,
      ``placebo_treatment_refuter``, ``data_subset_refuter``,
      ``add_unobserved_common_cause``.
    - Optional implemented: ``bootstrap_refuter``.
    - Optional reserved: ``non_parametric_sensitivity_analyzer``
      (422-rejected with ``code='refuter_reserved'``; mirrors B2a's
      reserved-method pattern).

    ``evidence_level`` is one of ``validated`` / ``supported`` /
    ``planned`` per Plan v2 §2.3 (patched — see
    ``_reports/PHASE_B_PLAN_V2_PATCH_S2_3.md``):

    - **validated**: all 4 mandatory refuters pass with p > 0.10
      AND identify.strategy == 'backdoor' AND e_value > 1.5.
    - **supported**: >= 2/4 mandatory pass with p > 0.05 AND
      identify.strategy in {'backdoor', 'frontdoor', 'mediation'}.
    - **planned**: otherwise.

    ``original_e_value`` is optional in the request. When provided,
    the engine uses it verbatim in the evidence-level rule (best for
    audit trail — pass through /estimate.response.e_value_cheap).
    When absent, the engine recomputes via a lightweight OLS pass on
    the same data + adjustment set (~20% engine cost) and adds a
    ``method_fallback`` warning to the response.

    Note: ``e_value_sensitivity_analyzer`` was moved out of /refute
    in the Plan v2 §2.3 patch — it is a sensitivity analysis, not a
    Monte-Carlo refuter, and will land in /api/v1/causal/sensitivity
    (B2b.3) instead.
    """
    try:
        return run_refute(body)
    except CausalRefuteError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "refute_failed", "message": str(exc)},
        ) from exc


# ════════════════════════════════════════════════════════════════════
# /mediation (B2b.2)
# ════════════════════════════════════════════════════════════════════


@router.post(
    "/mediation",
    response_model=CausalMediationResponse,
    summary=(
        "Phase B — causal mediation (Pearl/Rubin "
        "ACME/ADE decomposition with bootstrap CI, "
        "Plan v2 §2.4)"
    ),
)
async def mediation_endpoint(
    body: CausalMediationRequest,
    current_user: User = Depends(require_minimum_role("operator")),
) -> CausalMediationResponse:
    """
    Decomposes the treatment → outcome ATE into direct (ADE/NDE) and
    per-mediator indirect (ACME/NIE) effects via the Pearl/Rubin
    counterfactual framework (D14 = γ, NOT Baron-Kenny).

    Branches:

    - ``len(mediators) == 1``: DoWhy nonparametric NDE/NIE
      (``mediation.two_stage_regression``).
    - ``len(mediators) >= 2``: Farbmacher 2022 leave-one-out
      LinearDML fallback (DoWhy 0.14's ``get_mediator_variables()``
      only returns one mediator under multi-mediator DAGs, verified
      in ``scratch_mediation_api.py`` Gap 2 probe).

    Bootstrap CI: ``n_bootstrap`` defaults to 200 (Plan v2 §2.4's
    1000 overridden for MVP wall-clock budget; see
    ``PHASE_B2b2_DESIGN.md`` §8 R1). Iterations that fail are
    skipped with a ``method_fallback`` warning; <50% completion →
    422 ``code='bootstrap_diverged'``. The actual completed count is
    echoed in ``diagnostics.n_bootstrap_used``.

    Reserved decomposition modes (``controlled`` /
    ``interventional``) → 422 ``code='decomposition_reserved'``
    (D9-style reserved-enum pattern).

    Operator MUST acknowledge ≥1 Pearl assumption in
    ``assumptions_acknowledged`` (echoed verbatim in
    ``assumptions_echo`` for audit, Mod 8).

    When the effective per-stratum sample size falls below 30, the
    response is forced to ``evidence_level='planned'`` and a
    ``small_sample`` warning is added (mirrors B2a /estimate's Mod 5).

    Plan v2 §2.4 paper map: Signal-API → κ → SER pathway (V14 line
    11 + line 153, paper headline ~70% proportion mediated).
    """
    try:
        return run_mediation(body)
    except CausalMediationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "mediation_failed", "message": str(exc)},
        ) from exc


# ════════════════════════════════════════════════════════════════════
# /sensitivity (B2b.3)
# ════════════════════════════════════════════════════════════════════


@router.post(
    "/sensitivity",
    response_model=CausalSensitivityResponse,
    summary=(
        "Phase B — causal sensitivity (E-value + Cinelli-Hazlett "
        "robustness value, Plan v2 §2.5)"
    ),
)
async def sensitivity_endpoint(
    body: CausalSensitivityRequest,
    current_user: User = Depends(require_minimum_role("operator")),
) -> CausalSensitivityResponse:
    """
    Bounds the unmeasured-confounder bias on the upstream
    /estimate result without re-running the estimation.

    Methods (B2b.3 MVP):

    - ``evalue`` (default) — VanderWeele-Ding E-value. Primary path
      uses DoWhy's ``EValueSensitivityAnalyzer`` standalone class;
      automatic fallback to a self-implemented Chinn-VWD E-value
      when the DoWhy path raises (delta-style pattern mirroring
      B2b.1 refute's reliability fallbacks). Source is recorded in
      ``evalue_detail.source``.
    - ``linear`` — Cinelli-Hazlett 2020 robustness value + partial
      R² from a single ``statsmodels`` OLS fit. Closed form; no
      DoWhy / EconML dependency on this branch. When
      ``benchmark_covariate`` is supplied, the benchmark's partial
      R² on Y given T + the rest of the adjustment set is computed
      from its t-statistic in the same OLS.
    - ``partial_linear`` — Reserved; 422-rejected with
      ``code='method_reserved'`` (DoWhy's
      ``NonParametricSensitivityAnalyzer`` requires a ``theta_s``
      parameter that Plan v2 §2.5 does not expose).

    The ``overall_robust`` Response field operationalises Plan v2
    §2.5's "Γ-bound ≥ 1.5" gate (paper line 101): for ``evalue``,
    ``e_value_lower_ci > 1.5``; for ``linear``,
    ``robustness_value_alpha > 0.10`` (Cinelli-Hazlett 2020
    conventional threshold; the two numbers live on incompatible
    scales). ``evidence_level`` is ``validated`` when robust and
    ``supported`` otherwise.

    Plan v2 §2.5 paper map: the cheap E-value is already returned
    in-line by ``/estimate`` (Mod 9). This endpoint exists for the
    expensive class-based / partial-R² analysis the operator might
    want for a high-stakes claim.
    """
    try:
        return run_sensitivity(body)
    except CausalSensitivityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "sensitivity_failed", "message": str(exc)},
        ) from exc


# ════════════════════════════════════════════════════════════════════
# /bayesian_estimate (Phase C C1)
# ════════════════════════════════════════════════════════════════════


@router.post(
    "/bayesian_estimate",
    response_model=BayesianEstimateResponse,
    summary=(
        "Phase C C1 — Bayesian backdoor ATE estimation "
        "(PyMC posterior + 95% HDI)"
    ),
)
async def bayesian_estimate_endpoint(
    body: BayesianEstimateRequest,
    current_user: User = Depends(require_minimum_role("operator")),
) -> BayesianEstimateResponse:
    """
    Compute a Bayesian posterior over the ATE for the (treatment,
    outcome) pair on the supplied data via PyMC NUTS sampling.

    Complements Phase B B2a's frequentist LinearDML by providing
    full posterior characterisation (HDI + samples) instead of point
    + frequentist CI. The two approaches are reported side-by-side
    in Paper 3 (methodology paper) per the "dual Bayesian–frequentist
    reporting" framing.

    Method families (C1 MVP):

    - ``bayesian_backdoor`` (default) — Linear regression with
      weakly informative priors (Gelman et al. 2008 style) over the
      treatment coefficient. Returns posterior samples + 95% HDI.
    - ``bayesian_dml`` — Reserved for Phase C C2+; 422-rejected with
      ``code='method_reserved'`` (mirrors B2a's
      ``method_family_reserved`` pattern).

    Sync-mode requests with inline row count > 10,000 are
    422-rejected at validator time; use ``mode='async_job'`` for
    larger datasets.

    Evidence level rules:

    - ``validated`` — r_hat < 1.01 AND ESS > 400 AND n_divergent == 0
      AND HDI excludes zero AND backdoor adjustment set non-empty
    - ``supported`` — r_hat < 1.05 AND ESS > 100 AND HDI excludes zero
    - ``planned`` — otherwise (e.g. small_sample, no backdoor, or
      poor sampler diagnostics)

    Sampling timing: typically 10-30s with a C++ compiler available
    (pytensor compiled mode); 30-90s on pytensor's Python fallback
    when no compiler is present. The lazy PyMC import means
    importing this router does not pay the ~5-10s PyMC import cost.
    """
    try:
        response, _warnings = estimate_ate_bayesian(body)
        return response
    except CausalBayesianError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "bayesian_estimate_failed",
                "message": str(exc),
            },
        ) from exc


# ════════════════════════════════════════════════════════════════════
# /conformal_predict (Phase C C2)
# ════════════════════════════════════════════════════════════════════


@router.post(
    "/conformal_predict",
    response_model=ConformalPredictResponse,
    summary=(
        "Phase C C2 — distribution-free conformal prediction "
        "intervals (split + Mondrian variants)"
    ),
)
async def conformal_predict_endpoint(
    body: ConformalPredictRequest,
    current_user: User = Depends(require_minimum_role("operator")),
) -> ConformalPredictResponse:
    """
    Compute distribution-free prediction intervals at the requested
    (1-α) coverage level for new observations.

    Method families (C2 MVP):

    - ``split_conformal`` (default) — Lei & Wasserman 2014. Marginal
      coverage guarantee P(Y ∈ Ĉ(X)) ≥ 1-α. Requires no
      distributional assumption beyond exchangeability between
      training and calibration splits.
    - ``mondrian_conformal`` — Vovk et al. 2005. Stratified
      conformal: per-stratum quantile gives conditional coverage
      guarantee P(Y ∈ Ĉ(X) | stratum=s) ≥ 1-α within each stratum.
      Requires ``stratum_variable`` to be set (validator-enforced).
      Strata with fewer than ``n_min_per_stratum`` calibration
      samples fall back to the marginal quantile with a
      ``small_stratum`` warning.

    Implementation: custom split-conformal (~50 LOC numpy) with no
    ``mapie`` / ``crepes`` dependency. Internal OLS regressor fit on
    training split; residuals computed on calibration split; (1-α)
    quantile (``method='higher'`` for finite-sample correction).

    Evidence level rules (C2 Design §3.4):
    - ``validated`` — n_cal ≥ 30 AND marginal_quantile < 50% of
      outcome std AND (for Mondrian) all strata have n ≥
      n_min_per_stratum
    - ``supported`` — n_cal ≥ 10
    - ``planned`` — otherwise
    """
    try:
        response, _warnings = predict_conformal(body)
        return response
    except CausalConformalError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "conformal_predict_failed",
                "message": str(exc),
            },
        ) from exc
