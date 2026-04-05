"""
BOS Pipeline v9.0 �� Mass Balance Router

API endpoints for mass balance reconciliation.
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
from app.engine.mass_balance import MassBalanceInput, reconcile_mass_balance

router = APIRouter()


class MassBalanceRequest(BaseModel):
    """Mass balance reconciliation request."""

    batch_id: Optional[int] = None
    dm_in: float = Field(..., gt=0)
    dm_larvae: float = Field(..., ge=0)
    dm_frass: float = Field(..., ge=0)
    dm_gas_loss: Optional[float] = Field(None, ge=0)
    sigma_dm_in: float = Field(default=0.3, ge=0)
    sigma_dm_larvae: float = Field(default=0.15, ge=0)
    sigma_dm_frass: float = Field(default=0.3, ge=0)
    sigma_dm_gas: float = Field(default=0.5, ge=0)
    dm_wastewater: float = Field(default=0, ge=0)
    sigma_dm_wastewater: float = Field(default=0.1, ge=0)
    max_adjustment_pct: float = Field(default=20.0, ge=1, le=50)


@router.post("/reconcile")
async def reconcile_endpoint(
    body: MassBalanceRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Reconcile mass balance using weighted least squares."""
    start_time = time.perf_counter()

    # Verify batch if provided
    if body.batch_id:
        result = await db.execute(
            select(Batch).where(Batch.id == body.batch_id, Batch.tenant_id == current_user.tenant_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    mb_input = MassBalanceInput(
        dm_in=body.dm_in,
        dm_larvae=body.dm_larvae,
        dm_frass=body.dm_frass,
        dm_gas_loss=body.dm_gas_loss,
        sigma_dm_in=body.sigma_dm_in,
        sigma_dm_larvae=body.sigma_dm_larvae,
        sigma_dm_frass=body.sigma_dm_frass,
        sigma_dm_gas=body.sigma_dm_gas,
        dm_wastewater=body.dm_wastewater,
        sigma_dm_wastewater=body.sigma_dm_wastewater,
        max_adjustment_pct=body.max_adjustment_pct,
    )

    mb_result = reconcile_mass_balance(mb_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    # Persist
    if body.batch_id:
        calc = Calculation(
            batch_id=body.batch_id,
            calc_type="mass_balance",
            status="completed",
            inputs=body.model_dump(),
            result={
                "original": mb_result.original,
                "reconciled": mb_result.reconciled,
                "adjustments": mb_result.adjustments,
                "closure_pct": mb_result.closure_pct,
                "chi_squared": mb_result.chi_squared,
                "chi_squared_acceptable": mb_result.chi_squared_acceptable,
            },
            duration_ms=round(duration_ms, 2),
            engine_version=mb_result.engine_version,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
        db.add(calc)
        await db.commit()

    return {
        "original": mb_result.original,
        "reconciled": mb_result.reconciled,
        "adjustments": mb_result.adjustments,
        "adjustment_pct": mb_result.adjustment_pct,
        "balance": {
            "raw_error": mb_result.raw_balance_error,
            "reconciled_error": mb_result.reconciled_balance_error,
            "closure_pct": mb_result.closure_pct,
        },
        "estimated_gas_loss": mb_result.estimated_gas_loss,
        "chi_squared": {
            "value": mb_result.chi_squared,
            "df": mb_result.degrees_of_freedom,
            "acceptable": mb_result.chi_squared_acceptable,
        },
        "warnings": mb_result.warnings,
        "computation_time_ms": round(duration_ms, 2),
    }
