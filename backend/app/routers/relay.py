"""Phase A — Relay simulation router.

POST /api/v1/relay/simulate — three-stage M1 → M2 → M3 relay over the
digital twin. Composes existing engines:
    - app.engine.core.digital_twin_engine (state-space step)
    - app.engine.core.mass_balance         (boundary closure)
    - app.engine.core.ser_engine           (final SER aggregation)
Phase D will swap the placeholder MC band for a real
monte_carlo_engine propagation across the full trajectory.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import require_minimum_role
from app.engine.core.relay_engine import simulate_relay
from app.models import User
from app.schemas.relay import (
    BoundaryLedger,
    RelayHealth,
    RelaySimulateRequest,
    RelaySimulateResponse,
    TwinSnapshot,
    TwinState,
    Warning as RelayWarning,
)

router = APIRouter()


@router.post(
    "/simulate",
    response_model=RelaySimulateResponse,
    summary="Phase A — three-stage M1→M2→M3 relay simulation",
)
async def relay_simulate_endpoint(
    body: RelaySimulateRequest,
    current_user: User = Depends(require_minimum_role("operator")),
) -> RelaySimulateResponse:
    """Run the V5 relay simulation.

    Paper map: M1 (deconstruction) → M2 (assimilation, signal decay per
    Eq.6) → M3 (stabilization). Each stage emits a BoundaryLedger via
    mass_balance.reconcile, so closure_pct < 95% produces a warning.
    """
    initial = body.initial_state.model_dump()
    relay_cfg = body.relay_config.model_dump()
    mc_cfg = body.monte_carlo.model_dump() if body.monte_carlo else None
    ctrl = body.control_profile.model_dump() if body.control_profile else None

    try:
        raw = simulate_relay(
            initial_state=initial,
            relay_config=relay_cfg,
            horizon_steps=body.horizon_steps,
            dt_hours=body.dt_hours,
            species_code=body.species_code,
            monte_carlo=mc_cfg,
            control_profile=ctrl,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Coerce nested dicts into Pydantic models so response_model
    # validation catches any drift.
    trajectory = [
        TwinSnapshot(
            step_index=s["step_index"],
            stage=s["stage"],
            cumulative_time_h=s["cumulative_time_h"],
            state=TwinState(**s["state"]),
        )
        for s in raw["trajectory"]
    ]
    ledger = [BoundaryLedger(**lg) for lg in raw["boundary_ledger"]]
    health = RelayHealth(**raw["relay_health"])
    warnings = [RelayWarning(**w) for w in raw["warnings"]]

    return RelaySimulateResponse(
        trajectory=trajectory,
        boundary_ledger=ledger,
        relay_health=health,
        final_ser=raw["final_ser"],
        final_ser_ci=tuple(raw["final_ser_ci"]) if raw["final_ser_ci"] else None,
        warnings=warnings,
        engine_version=raw["engine_version"],
        evidence_level=raw["evidence_level"],
    )
