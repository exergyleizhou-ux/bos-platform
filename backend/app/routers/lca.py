"""
BOS Pipeline v9.0 �� LCA (Life Cycle Assessment) Router

API endpoints for simplified cradle-to-gate LCA.
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
from app.engine.lca_engine import LCAInput, compute_lca

router = APIRouter()


class LCARequest(BaseModel):
    """LCA computation request."""

    batch_id: int
    dm_in: float = Field(..., gt=0)
    dm_out_larvae: float = Field(..., ge=0)
    dm_out_frass: float = Field(default=0, ge=0)
    electricity_kwh: float = Field(default=0, ge=0)
    natural_gas_m3: float = Field(default=0, ge=0)
    transport_tkm: float = Field(default=0, ge=0, description="Tonne-kilometers")
    protein_content: float = Field(default=42.0, ge=0, le=100)
    functional_unit: str = Field(default="kg_protein", pattern=r"^(kg_protein|kg_larvae|tonne_substrate)$")


@router.post("/compute")
async def compute_lca_endpoint(
    body: LCARequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Compute life cycle assessment for a batch."""
    start_time = time.perf_counter()

    # Verify batch
    result = await db.execute(
        select(Batch).where(Batch.id == body.batch_id, Batch.tenant_id == current_user.tenant_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    lca_input = LCAInput(
        dm_in=body.dm_in,
        dm_out_larvae=body.dm_out_larvae,
        dm_out_frass=body.dm_out_frass,
        electricity_kwh=body.electricity_kwh,
        natural_gas_m3=body.natural_gas_m3,
        transport_tkm=body.transport_tkm,
        protein_content=body.protein_content,
        functional_unit=body.functional_unit,
    )

    lca_result = compute_lca(lca_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    # Persist
    calc = Calculation(
        batch_id=body.batch_id,
        calc_type="lca",
        status="completed",
        inputs=body.model_dump(),
        result={
            "impacts": lca_result.impacts,
            "impacts_per_fu": lca_result.impacts_per_fu,
            "functional_unit": lca_result.functional_unit,
            "functional_unit_value": lca_result.functional_unit_value,
            "contributions": lca_result.contributions,
            "normalized": lca_result.normalized,
        },
        duration_ms=round(duration_ms, 2),
        engine_version=lca_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    await db.commit()

    return {
        "impacts_absolute": lca_result.impacts,
        "impacts_per_functional_unit": lca_result.impacts_per_fu,
        "functional_unit": lca_result.functional_unit,
        "functional_unit_value": lca_result.functional_unit_value,
        "contribution_analysis": lca_result.contributions,
        "normalized_milli_person_years": lca_result.normalized,
        "units": lca_result.units,
        "names": lca_result.names,
        "computation_time_ms": round(duration_ms, 2),
    }
