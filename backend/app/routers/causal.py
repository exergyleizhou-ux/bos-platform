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

Phase B B2b will add /refute, /mediation, /sensitivity (+ async jobs).

Reference: PHASE_B_PLAN.md §2.1, §2.2, §2.7.
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
from app.engine.extended.causal_identify_engine import run_identify
from app.engine.extended.causal_estimate_engine import (
    CausalEstimateError,
    run_estimate,
)
from app.engine.extended.causal_refute_engine import (
    CausalRefuteError,
    run_refute,
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
