"""
BOS Pipeline v9.0 -Water Footprint Router

API endpoints for water footprint computation.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.models import User, Batch, Calculation
from app.engine.water_engine import WaterInput, compute_water_footprint

router = APIRouter()


class WaterRequest(BaseModel):
    """Water footprint computation request."""

    batch_id: int
    dm_in: float = Field(..., gt=0)
    dm_out_larvae: float = Field(..., ge=0)
    dm_out_frass: float = Field(default=0, ge=0)
    process_water: Optional[float] = Field(None, ge=0, description="Measured process water (L)")
    cleaning_water: Optional[float] = Field(None, ge=0)
    cooling_energy_kwh: float = Field(default=0, ge=0)
    protein_content: float = Field(default=42.0, ge=0, le=100)
    wastewater_volume: float = Field(default=0, ge=0)
    wastewater_nitrogen: float = Field(default=0, ge=0, description="g N in wastewater")


@router.post("/compute")
async def compute_water_endpoint(
    body: WaterRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Compute water footprint for a batch."""
    start_time = time.perf_counter()

    # Verify batch
    result = await db.execute(select(Batch).where(Batch.id == body.batch_id, Batch.tenant_id == current_user.tenant_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    water_input = WaterInput(
        dm_in=body.dm_in,
        dm_out_larvae=body.dm_out_larvae,
        dm_out_frass=body.dm_out_frass,
        process_water=body.process_water,
        cleaning_water=body.cleaning_water,
        cooling_energy_kwh=body.cooling_energy_kwh,
        protein_content=body.protein_content,
        wastewater_volume=body.wastewater_volume,
        wastewater_nitrogen=body.wastewater_nitrogen,
    )

    water_result = compute_water_footprint(water_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    # Persist
    calc = Calculation(
        batch_id=body.batch_id,
        calc_type="water",
        status="completed",
        inputs=body.model_dump(),
        result={
            "total_water": water_result.total_water,
            "blue_water": water_result.blue_water,
            "green_water": water_result.green_water,
            "grey_water": water_result.grey_water,
            "wf_per_kg_larvae": water_result.wf_per_kg_larvae,
            "wf_per_kg_protein": water_result.wf_per_kg_protein,
            "water_productivity": water_result.water_productivity,
            "comparison": water_result.comparison,
            "breakdown": water_result.breakdown,
        },
        duration_ms=round(duration_ms, 2),
        engine_version=water_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    await db.commit()

    return {
        "total_water_liters": water_result.total_water,
        "components": {
            "blue": water_result.blue_water,
            "green": water_result.green_water,
            "grey": water_result.grey_water,
        },
        "intensity": {
            "per_kg_larvae": water_result.wf_per_kg_larvae,
            "per_kg_protein": water_result.wf_per_kg_protein,
        },
        "water_productivity_kg_per_m3": water_result.water_productivity,
        "comparison": water_result.comparison,
        "breakdown": water_result.breakdown,
        "computation_time_ms": round(duration_ms, 2),
    }
