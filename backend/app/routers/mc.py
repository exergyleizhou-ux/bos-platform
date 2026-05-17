"""Phase A — Monte Carlo propagation router.

POST /api/v1/mc/propagate — generic Eq.7 propagation. Thin wrapper
over ``monte_carlo_engine.propagate``. Each Phase A target_func
("ser", "sfi_score", "relay_final_state", "custom") routes through
the same interface; non-SER targets currently use a placeholder
evaluator and downgrade evidence_level to "planned" (Phase D will
swap in real downstream evaluators).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import require_minimum_role
from app.engine.core.monte_carlo_engine import propagate as engine_propagate
from app.models import User
from app.schemas.mc import (
    McDiagnostics,
    McPropagateRequest,
    McPropagateResponse,
    SobolIndices,
)

router = APIRouter()


@router.post(
    "/propagate",
    response_model=McPropagateResponse,
    summary="Phase A — generic Monte Carlo uncertainty propagation (Eq.7)",
)
async def mc_propagate_endpoint(
    body: McPropagateRequest,
    current_user: User = Depends(require_minimum_role("operator")),
) -> McPropagateResponse:
    """Run the V5 MC propagation.

    Paper map: Eq.7 (sample-and-evaluate Monte Carlo). For
    ``target_func="ser"`` the SER engine is the per-sample evaluator
    (evidence_level=supported). For other targets the engine returns
    a deterministic placeholder so the full request/response contract
    can be exercised (evidence_level=planned).
    """
    inputs_dict = {name: spec.model_dump() for name, spec in body.inputs.items()}

    try:
        raw = engine_propagate(
            target_func=body.target_func,
            target_func_config=body.target_func_config,
            inputs=inputs_dict,
            n_samples=body.n_samples,
            seed=body.seed,
            return_samples=body.return_samples,
            compute_sobol=body.compute_sobol,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    diagnostics = McDiagnostics(**raw["diagnostics"])
    sobol_model = SobolIndices(**raw["sobol_indices"]) if raw["sobol_indices"] else None

    return McPropagateResponse(
        target_mean=raw["target_mean"],
        target_std=raw["target_std"],
        ci_lower=raw["ci_lower"],
        ci_upper=raw["ci_upper"],
        samples=raw["samples"],
        sobol_indices=sobol_model,
        diagnostics=diagnostics,
        evidence_level=raw["evidence_level"],
        engine_version=raw["engine_version"],
    )
