"""
BOS Pipeline v9.0 energy balance router.
"""

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.engine.energy_engine import EnergyInput, compute_energy_balance
from app.models import Batch, Calculation, User

router = APIRouter()


class EnergyRequest(BaseModel):
    """Energy balance computation request."""

    batch_id: int
    dm_in: float = Field(..., gt=0)
    dm_out_larvae: float = Field(..., ge=0)
    dm_out_frass: float = Field(default=0, ge=0)
    protein_content: float = Field(default=42.0, ge=0, le=100)
    fat_content: float = Field(default=35.0, ge=0, le=100)
    chitin_content: float = Field(default=8.0, ge=0, le=100)
    electricity_heating: float = Field(default=0, ge=0, description="kWh")
    electricity_ventilation: float = Field(default=0, ge=0)
    electricity_lighting: float = Field(default=0, ge=0)
    electricity_pumps: float = Field(default=0, ge=0)
    electricity_drying: float = Field(default=0, ge=0)
    electricity_other: float = Field(default=0, ge=0)
    natural_gas_m3: float = Field(default=0, ge=0)
    diesel_liters: float = Field(default=0, ge=0)
    batch_days: float = Field(default=14, gt=0)


@router.post("/compute")
async def compute_energy_endpoint(
    body: EnergyRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Compute energy balance for a batch."""
    start_time = time.perf_counter()

    result = await db.execute(
        select(Batch).where(Batch.id == body.batch_id, Batch.tenant_id == current_user.tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    energy_input = EnergyInput(
        dm_in=body.dm_in,
        dm_out_larvae=body.dm_out_larvae,
        dm_out_frass=body.dm_out_frass,
        protein_content=body.protein_content,
        fat_content=body.fat_content,
        chitin_content=body.chitin_content,
        electricity_heating=body.electricity_heating,
        electricity_ventilation=body.electricity_ventilation,
        electricity_lighting=body.electricity_lighting,
        electricity_pumps=body.electricity_pumps,
        electricity_drying=body.electricity_drying,
        electricity_other=body.electricity_other,
        natural_gas_m3=body.natural_gas_m3,
        diesel_liters=body.diesel_liters,
        batch_days=body.batch_days,
    )

    energy_result = compute_energy_balance(energy_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    calc = Calculation(
        batch_id=body.batch_id,
        calc_type="energy",
        status="completed",
        inputs=body.model_dump(),
        result={
            "total_energy_in_mj": energy_result.total_energy_in,
            "chemical_energy_out_mj": energy_result.total_chemical_energy_out,
            "eroi": energy_result.eroi,
            "energy_efficiency": energy_result.energy_efficiency,
            "specific_energy_kwh_per_kg": energy_result.specific_energy,
            "breakdown_in": energy_result.breakdown_in,
            "breakdown_out": energy_result.breakdown_out,
        },
        duration_ms=round(duration_ms, 2),
        engine_version=energy_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    await db.commit()

    return {
        "total_energy_in_mj": energy_result.total_energy_in,
        "total_energy_out_mj": energy_result.total_chemical_energy_out,
        "eroi": energy_result.eroi,
        "energy_efficiency": energy_result.energy_efficiency,
        "specific_energy": {
            "kwh_per_kg_larvae": energy_result.specific_energy,
            "kwh_per_kg_protein": energy_result.specific_energy_per_protein,
        },
        "breakdown_in": energy_result.breakdown_in,
        "breakdown_out": energy_result.breakdown_out,
        "electricity_breakdown_mj": energy_result.electricity_breakdown,
        "computation_time_ms": round(duration_ms, 2),
    }
