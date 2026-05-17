"""
BOS Pipeline v9.0 — Digital Twin Router

API endpoints for digital twin management and simulation.
"""

import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role, set_tenant_context, get_pagination, PaginationParams
from app.models import User, DigitalTwin, DigitalTwinSnapshot
from app.schemas import (
    DigitalTwinCreate,
    DigitalTwinUpdate,
    DigitalTwinResponse,
    MessageResponse,
    PaginatedResponse,
)
from app.engine.digital_twin_engine import (
    TwinParameters,
    TwinState,
    predict_step,
    update_step,
    simulate_trajectory,
)
# Phase A V5 strict schemas live in schemas/twin.py alongside the V9
# CRUD DTOs. Imported here under alias names so they don't collide with
# the engine's dataclass TwinState above.
from app.schemas.twin import (
    InnovationStats as RunInnovationStats,
    TwinConfig as RunTwinConfig,
    TwinRunRequest,
    TwinRunResponse,
    TwinSnapshot as RunTwinSnapshot,
    TwinState as RunTwinState,
)

router = APIRouter()


# ════════════════════════════════════════════════════════════════════
# Phase A — POST /api/v1/twin/run (stateless V5 contract)
# ════════════════════════════════════════════════════════════════════
#
# This handler is intentionally added before the path-parameter routes
# (/{twin_id}/...) so the static segment "/run" matches first. FastAPI
# does match static literals before path params regardless of order,
# but lexical order also matches the V5 contract intent.


def _engine_state_to_v5(es: TwinState) -> RunTwinState:
    """digital_twin_engine.TwinState (dataclass) → V5 pydantic TwinState."""
    return RunTwinState(
        biomass_kg=round(float(es.biomass), 6),
        substrate_kg=round(float(es.substrate), 6),
        temperature_c=round(float(es.temperature), 4),
        moisture_pct=round(float(es.moisture), 4),
        # The engine carries nitrogen in grams; the V5 contract is kg.
        nitrogen_kg=round(float(es.nitrogen) / 1000.0, 6),
    )


def _v5_state_to_engine(v5: RunTwinState, t: float = 0.0) -> TwinState:
    return TwinState(
        biomass=float(v5.biomass_kg),
        substrate=float(v5.substrate_kg),
        temperature=float(v5.temperature_c),
        moisture=float(v5.moisture_pct),
        nitrogen=float(v5.nitrogen_kg) * 1000.0,  # back to engine units (g)
        timestamp_hours=t,
    )


@router.post(
    "/run",
    response_model=TwinRunResponse,
    summary="Phase A — stateless digital-twin run (V5)",
)
async def twin_run_endpoint(
    body: TwinRunRequest,
    current_user: User = Depends(require_minimum_role("operator")),
) -> TwinRunResponse:
    """Run the digital twin forward over an explicit input schedule.

    No DB persistence, no twin record required. If ``observations`` is
    provided and ``enable_ekf=True``, each predict step is followed by
    an EKF update. Innovation statistics are aggregated across the run.
    """
    cfg = body.config
    params = TwinParameters(
        mu_max=cfg.mu_max, K_s=cfg.K_s, Y=cfg.Y, k_death=cfg.k_death,
        k_n=cfg.k_n, tau_T=cfg.tau_T, tau_M=cfg.tau_M,
        T_env=cfg.T_env, M_env=cfg.M_env,
    )

    state = _v5_state_to_engine(body.initial_state, t=0.0)
    cumulative_t = 0.0

    snapshots: list[RunTwinSnapshot] = []
    estimated_states: list[RunTwinState] = []
    innovations: list[list[float]] = []
    n_updates = 0
    has_obs = body.observations is not None and body.enable_ekf

    for i, inp in enumerate(body.inputs):
        # ---- Predict step ----
        ctrl = {
            "feed_rate": float(inp.feed_rate_kg_h),
            "ventilation": float(inp.ventilation_m3_h),
            "heating": float(inp.heating_kw),
        }
        pred = predict_step(state, ctrl, params, float(inp.dt_hours))
        state = pred.state
        cumulative_t = float(state.timestamp_hours)

        v5_predicted = _engine_state_to_v5(state)
        snap = RunTwinSnapshot(
            step_index=i,
            cumulative_time_h=round(cumulative_t, 4),
            state=v5_predicted,
            growth_rate_kg_h=float(pred.growth_rate),
            ser_instantaneous=float(pred.ser_instantaneous),
        )
        snapshots.append(snap)

        # ---- Optional EKF update ----
        if has_obs:
            obs = body.observations[i]
            obs_dict: dict[str, float] = {}
            if obs.weight_kg is not None:
                obs_dict["weight"] = float(obs.weight_kg)
            if obs.temperature_c is not None:
                obs_dict["temperature"] = float(obs.temperature_c)
            if obs.moisture_pct is not None:
                obs_dict["moisture"] = float(obs.moisture_pct)
            if obs_dict:
                upd = update_step(state, obs_dict, params)
                state = upd.state
                n_updates += 1
                if upd.innovation is not None:
                    innovations.append(list(upd.innovation))

        # estimated_states tracks the post-update (corrected) view if EKF
        # ran this step, otherwise the predicted state.
        estimated_states.append(_engine_state_to_v5(state))

    # ---- Innovation aggregation ----
    if innovations:
        import numpy as _np
        arr = _np.asarray(innovations)
        channels = ["weight", "temperature", "moisture"]
        mean_abs = {ch: float(round(_np.mean(_np.abs(arr[:, k])), 6))
                    for k, ch in enumerate(channels[: arr.shape[1]])}
        rms = {ch: float(round(_np.sqrt(_np.mean(arr[:, k] ** 2)), 6))
               for k, ch in enumerate(channels[: arr.shape[1]])}
    else:
        mean_abs, rms = {}, {}

    innovation_stats = RunInnovationStats(
        n_updates=n_updates,
        mean_abs_innovation=mean_abs,
        rms_innovation=rms,
    )

    # ---- Evidence level ----
    # EKF-corrected runs with real observations earn "supported"; pure
    # forward predictions (no observations) are "planned" because there
    # is no measurement loop closing the uncertainty.
    evidence_level = "supported" if n_updates > 0 else "planned"

    return TwinRunResponse(
        trajectory=snapshots,
        estimated_states=estimated_states,
        final_state=estimated_states[-1],
        innovation_stats=innovation_stats,
        evidence_level=evidence_level,
        engine_version="9.0.0",
    )


async def _get_twin_or_404(db: AsyncSession, *, twin_id: int, tenant_id: int) -> DigitalTwin:
    result = await db.execute(
        select(DigitalTwin).where(
            DigitalTwin.id == twin_id,
            DigitalTwin.tenant_id == tenant_id,
        )
    )
    twin = result.scalar_one_or_none()

    if not twin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digital twin not found")

    return twin


def _ensure_twin_active_for_runtime(twin: DigitalTwin, action: str) -> None:
    if not twin.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Inactive digital twins must be re-activated before {action}.",
        )


@router.get("", response_model=PaginatedResponse[DigitalTwinResponse])
async def list_twins(
    pagination: PaginationParams = Depends(get_pagination),
    is_active: Optional[bool] = None,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """List digital twins for the current tenant."""
    query = select(DigitalTwin).where(DigitalTwin.tenant_id == current_user.tenant_id)

    if is_active is not None:
        query = query.where(DigitalTwin.is_active == is_active)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(DigitalTwin.updated_at.desc())
    query = query.offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    twins = result.scalars().all()

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    return PaginatedResponse(
        items=[DigitalTwinResponse.model_validate(t) for t in twins],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=DigitalTwinResponse, status_code=status.HTTP_201_CREATED)
async def create_twin(
    body: DigitalTwinCreate,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new digital twin."""
    twin = DigitalTwin(
        twin_id=body.twin_id,
        name=body.name,
        species=body.species,
        is_active=True,
        config=body.config,
        parameters=body.parameters,
        state={
            "biomass": 0.5,
            "substrate": 10.0,
            "temperature": 28.0,
            "moisture": 70.0,
            "nitrogen": 50.0,
        },
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(twin)
    await db.commit()
    await db.refresh(twin)

    return DigitalTwinResponse.model_validate(twin)


@router.get("/{twin_id}", response_model=DigitalTwinResponse)
async def get_twin(
    twin_id: int,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a digital twin by ID."""
    twin = await _get_twin_or_404(db, twin_id=twin_id, tenant_id=current_user.tenant_id)
    return DigitalTwinResponse.model_validate(twin)


@router.patch("/{twin_id}", response_model=DigitalTwinResponse)
async def update_twin(
    twin_id: int,
    body: DigitalTwinUpdate,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Update a digital twin."""
    twin = await _get_twin_or_404(db, twin_id=twin_id, tenant_id=current_user.tenant_id)
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(twin, key, value)

    twin.version += 1
    await db.commit()
    await db.refresh(twin)

    return DigitalTwinResponse.model_validate(twin)


@router.delete("/{twin_id}", response_model=MessageResponse)
async def delete_twin(
    twin_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a digital twin and its snapshots."""
    twin = await _get_twin_or_404(db, twin_id=twin_id, tenant_id=current_user.tenant_id)
    await db.delete(twin)
    await db.commit()
    return MessageResponse(message=f"Digital twin '{twin.twin_id}' deleted")


class TwinPredictRequest(BaseModel):
    """Twin predict step request."""

    inputs: Dict[str, float] = Field(default_factory=lambda: {"feed_rate": 0.15, "ventilation": 0.5, "heating": 0.3})
    dt: float = Field(default=1.0, gt=0, le=24, description="Time step in hours")


@router.post(
    "/{twin_id}/predict",
    deprecated=True,
    description=(
        "DEPRECATED (Phase A V5 D1 sunset): use POST /api/v1/twin/run for "
        "stateless predictions. Old stateful path stays callable until "
        "2027-05-17 (T0 + 12 months from Phase A start)."
    ),
)
async def predict_twin_step(
    twin_id: int,
    body: TwinPredictRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    """Advance the digital twin forward by one time step (prediction)."""
    twin = await _get_twin_or_404(db, twin_id=twin_id, tenant_id=current_user.tenant_id)
    _ensure_twin_active_for_runtime(twin, "prediction")

    # Reconstruct state
    state_dict = twin.state or {}
    state = TwinState(
        biomass=state_dict.get("biomass", 0.5),
        substrate=state_dict.get("substrate", 10.0),
        temperature=state_dict.get("temperature", 28.0),
        moisture=state_dict.get("moisture", 70.0),
        nitrogen=state_dict.get("nitrogen", 50.0),
        covariance=state_dict.get("covariance"),
        timestamp_hours=state_dict.get("timestamp_hours", 0),
    )

    params_dict = twin.parameters or {}
    params = TwinParameters(**{k: v for k, v in params_dict.items() if hasattr(TwinParameters, k)})

    # Predict
    step_result = predict_step(state, body.inputs, params, body.dt)

    # Update twin state in DB
    new_state = step_result.state
    twin.state = {
        "biomass": new_state.biomass,
        "substrate": new_state.substrate,
        "temperature": new_state.temperature,
        "moisture": new_state.moisture,
        "nitrogen": new_state.nitrogen,
        "covariance": new_state.covariance,
        "timestamp_hours": new_state.timestamp_hours,
    }
    twin.version += 1
    await db.commit()

    return {
        "state": twin.state,
        "growth_rate": step_result.growth_rate,
        "ser_instantaneous": step_result.ser_instantaneous,
        "timestamp_hours": new_state.timestamp_hours,
        "version": twin.version,
    }


class TwinUpdateObsRequest(BaseModel):
    """Twin observation update request."""

    observations: Dict[str, float] = Field(
        ...,
        description="Sensor observations: weight, temperature, moisture",
    )


@router.post(
    "/{twin_id}/update",
    deprecated=True,
    description=(
        "DEPRECATED (Phase A V5 D1 sunset): use POST /api/v1/twin/run with "
        "an observations array for stateless EKF correction. Old stateful "
        "path stays callable until 2027-05-17."
    ),
)
async def update_twin_observations(
    twin_id: int,
    body: TwinUpdateObsRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    """Correct the digital twin state with sensor observations (EKF update)."""
    twin = await _get_twin_or_404(db, twin_id=twin_id, tenant_id=current_user.tenant_id)
    _ensure_twin_active_for_runtime(twin, "observation updates")

    state_dict = twin.state or {}
    state = TwinState(
        biomass=state_dict.get("biomass", 0.5),
        substrate=state_dict.get("substrate", 10.0),
        temperature=state_dict.get("temperature", 28.0),
        moisture=state_dict.get("moisture", 70.0),
        nitrogen=state_dict.get("nitrogen", 50.0),
        covariance=state_dict.get("covariance"),
        timestamp_hours=state_dict.get("timestamp_hours", 0),
    )

    params_dict = twin.parameters or {}
    params = TwinParameters(**{k: v for k, v in params_dict.items() if hasattr(TwinParameters, k)})

    step_result = update_step(state, body.observations, params)

    new_state = step_result.state
    twin.state = {
        "biomass": new_state.biomass,
        "substrate": new_state.substrate,
        "temperature": new_state.temperature,
        "moisture": new_state.moisture,
        "nitrogen": new_state.nitrogen,
        "covariance": new_state.covariance,
        "timestamp_hours": new_state.timestamp_hours,
    }
    twin.version += 1

    # Save snapshot
    snapshot = DigitalTwinSnapshot(
        twin_id=twin.id,
        state=twin.state,
        parameters=twin.parameters,
        trigger="observation_update",
    )
    db.add(snapshot)
    await db.commit()

    return {
        "state": twin.state,
        "innovation": step_result.innovation,
        "version": twin.version,
    }


class TwinSimulateRequest(BaseModel):
    """Twin trajectory simulation request."""

    inputs_schedule: Optional[List[Dict[str, float]]] = Field(default=None, min_length=1, max_length=720)
    initial_biomass: float = Field(default=0.5, ge=0)
    initial_substrate: float = Field(default=10.0, ge=0)
    initial_temperature: float = Field(default=28.0, ge=0, le=60)
    initial_moisture: float = Field(default=70.0, ge=0, le=100)
    initial_nitrogen: float = Field(default=50.0, ge=0)
    n_steps: int = Field(default=100, ge=1, le=720)
    dt: float = Field(default=1.0, gt=0, le=24)


@router.post(
    "/{twin_id}/simulate",
    deprecated=True,
    description=(
        "DEPRECATED (Phase A V5 D1 sunset): use POST /api/v1/twin/run for "
        "stateless trajectory simulation. Old stateful path stays callable "
        "until 2027-05-17."
    ),
)
async def simulate_twin(
    twin_id: int,
    body: TwinSimulateRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Simulate a full trajectory without modifying the twin state."""
    twin = await _get_twin_or_404(db, twin_id=twin_id, tenant_id=current_user.tenant_id)
    _ensure_twin_active_for_runtime(twin, "simulation")

    state_dict = twin.state or {}
    initial_state = TwinState(
        biomass=body.initial_biomass if body.initial_biomass is not None else state_dict.get("biomass", 0.5),
        substrate=body.initial_substrate if body.initial_substrate is not None else state_dict.get("substrate", 10.0),
        temperature=body.initial_temperature if body.initial_temperature is not None else state_dict.get("temperature", 28.0),
        moisture=body.initial_moisture if body.initial_moisture is not None else state_dict.get("moisture", 70.0),
        nitrogen=body.initial_nitrogen if body.initial_nitrogen is not None else state_dict.get("nitrogen", 50.0),
        timestamp_hours=state_dict.get("timestamp_hours", 0),
    )

    params_dict = twin.parameters or {}
    params = TwinParameters(**{k: v for k, v in params_dict.items() if hasattr(TwinParameters, k)})

    inputs_schedule = body.inputs_schedule or [{"feed_rate": 0.0, "ventilation": 0.0, "heating": 0.0}]
    trajectory = simulate_trajectory(initial_state, inputs_schedule, params, body.dt, total_hours=body.n_steps)

    final_state = trajectory[-1].state if trajectory else initial_state

    return {
        "n_steps": len(trajectory),
        "trajectory": [
            {
                "t": step.state.timestamp_hours,
                "biomass": step.state.biomass,
                "substrate": step.state.substrate,
                "temperature": step.state.temperature,
                "moisture": step.state.moisture,
                "nitrogen": step.state.nitrogen,
                "growth_rate": step.growth_rate,
                "ser_instantaneous": step.ser_instantaneous,
            }
            for step in trajectory
        ],
        "final_state": {
            "biomass": final_state.biomass,
            "substrate": final_state.substrate,
            "temperature": final_state.temperature,
            "moisture": final_state.moisture,
            "nitrogen": final_state.nitrogen,
            "timestamp_hours": final_state.timestamp_hours,
        },
    }
