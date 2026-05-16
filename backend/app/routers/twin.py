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

router = APIRouter()


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


@router.post("/{twin_id}/predict")
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


@router.post("/{twin_id}/update")
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


@router.post("/{twin_id}/simulate")
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
