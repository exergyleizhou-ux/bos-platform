"""
BOS Pipeline v9.0 �� GHG Balance Router

API endpoints for greenhouse gas balance computation.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role, set_tenant_context
from app.models import User, Batch, Calculation
from app.engine.ghg_engine import GHGInput, compute_ghg

router = APIRouter()


class GHGRequest(BaseModel):
    """GHG balance computation request."""

    batch_id: int
    dm_in: float = Field(..., gt=0)
    dm_out_larvae: float = Field(..., ge=0)
    dm_out_frass: float = Field(default=0, ge=0)
    n_in: float = Field(default=0, ge=0, description="Nitrogen input (g)")
    protein_content: float = Field(default=42.0, ge=0, le=100)
    fat_content: float = Field(default=35.0, ge=0, le=100)
    electricity_kwh: float = Field(default=0, ge=0)
    natural_gas_m3: float = Field(default=0, ge=0)
    diesel_liters: float = Field(default=0, ge=0)
    transport_distance_km: float = Field(default=50, ge=0)
    grid_ef: Optional[float] = Field(None, ge=0, description="Grid emission factor (kg CO?e/kWh)")
    include_credits: bool = True
    include_avoided: bool = True


@router.post("/compute")
async def compute_ghg_endpoint(
    body: GHGRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Compute greenhouse gas balance for a batch."""
    start_time = time.perf_counter()

    # Verify batch
    result = await db.execute(
        select(Batch).where(Batch.id == body.batch_id, Batch.tenant_id == current_user.tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    ghg_input = GHGInput(
        dm_in=body.dm_in,
        dm_out_larvae=body.dm_out_larvae,
        dm_out_frass=body.dm_out_frass,
        n_in=body.n_in,
        protein_content=body.protein_content,
        fat_content=body.fat_content,
        electricity_kwh=body.electricity_kwh,
        natural_gas_m3=body.natural_gas_m3,
        diesel_liters=body.diesel_liters,
        transport_distance_km=body.transport_distance_km,
        grid_ef=body.grid_ef,
        include_credits=body.include_credits,
        include_avoided=body.include_avoided,
    )

    ghg_result = compute_ghg(ghg_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    # Persist
    calc = Calculation(
        batch_id=body.batch_id,
        calc_type="ghg",
        status="completed",
        inputs=body.model_dump(),
        result={
            "total_net": ghg_result.total_net,
            "total_direct": ghg_result.total_direct,
            "total_indirect": ghg_result.total_indirect,
            "total_credits": ghg_result.total_credits,
            "carbon_intensity_per_kg_larvae": ghg_result.carbon_intensity_per_kg_larvae,
            "carbon_intensity_per_kg_protein": ghg_result.carbon_intensity_per_kg_protein,
            "savings_vs_fishmeal": ghg_result.savings_vs_fishmeal,
            "savings_vs_soy": ghg_result.savings_vs_soy,
            "breakdown": ghg_result.breakdown,
        },
        duration_ms=round(duration_ms, 2),
        engine_version=ghg_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    await db.commit()

    return {
        "total_net_co2e": ghg_result.total_net,
        "direct_emissions": ghg_result.total_direct,
        "indirect_emissions": ghg_result.total_indirect,
        "credits": ghg_result.total_credits,
        "intensity": {
            "per_kg_larvae": ghg_result.carbon_intensity_per_kg_larvae,
            "per_kg_protein": ghg_result.carbon_intensity_per_kg_protein,
        },
        "comparison": {
            "vs_fishmeal": ghg_result.savings_vs_fishmeal,
            "vs_soy": ghg_result.savings_vs_soy,
        },
        "breakdown": ghg_result.breakdown,
        "computation_time_ms": round(duration_ms, 2),
    }
