"""Phase A — SFI (Signal/Flight Integrity) router.

POST /api/v1/sfi/check — strict, stateless. Backed by
``app.engine.core.sfi_engine``. The legacy alternative is
``/api/v1/flight-envelope/check`` which keeps its V9 schema and is
NOT removed (per PHASE_A_PLAN §4 D1 sunset rules).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import require_minimum_role
from app.engine.core.sfi_engine import check_sfi
from app.models import User
from app.schemas.sfi import (
    Action,
    AxisStatus,
    ForecastBreach,
    SfiCheckRequest,
    SfiCheckResponse,
)

router = APIRouter()


@router.post(
    "/check",
    response_model=SfiCheckResponse,
    summary="Phase A — paper-strict SFI envelope check (Eq.5-6)",
)
async def sfi_check_endpoint(
    body: SfiCheckRequest,
    current_user: User = Depends(require_minimum_role("operator")),
) -> SfiCheckResponse:
    """Run the V5 SFI check.

    Paper map: Eq.5 (per-axis envelope), Eq.6 (physical horizon
    tau_max = ln(s0/s_min)/k_decay).
    Honest k_decay treatment: provenance drives evidence_level.
    """
    measurements = body.measurements.model_dump()
    setpoint = body.setpoint_profile.model_dump() if body.setpoint_profile else None
    k_band = body.k_decay_band.model_dump() if body.k_decay_band else None

    try:
        raw = check_sfi(
            species_code=body.species_code,
            measurements=measurements,
            setpoint_profile=setpoint,
            horizon_hours=body.horizon_hours,
            k_decay_band=k_band,
            s0=body.s0,
            s_min=body.s_min,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Coerce nested dicts to Pydantic models so the response_model
    # validator catches any drift.
    per_axis_models = {
        name: AxisStatus(**spec) for name, spec in raw["per_axis"].items()
    }
    forecast_model = (
        ForecastBreach(**raw["forecast_breach"]) if raw.get("forecast_breach") else None
    )
    action_models = [Action(**a) for a in raw["recommended_actions"]]

    return SfiCheckResponse(
        sfi_pass=raw["sfi_pass"],
        zone=raw["zone"],
        composite_score=raw["composite_score"],
        per_axis=per_axis_models,
        forecast_breach=forecast_model,
        recommended_actions=action_models,
        evidence_level=raw["evidence_level"],
        k_decay_used=body.k_decay_band,
        engine_version=raw["engine_version"],
    )
