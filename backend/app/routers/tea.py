"""
BOS Pipeline v9.0 — TEA (Techno-Economic Analysis) Router

API endpoints for techno-economic analysis of bioconversion operations.
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
from app.engine.tea_engine import TEAInput, compute_tea
from app.schemas.sustainability_kernel import SustainabilityResultResponse, TEAEstimateRequest
from app.services.sustainability_kernel_service import estimate_tea

router = APIRouter()


class TEARequest(BaseModel):
    """TEA computation request."""

    batch_id: Optional[int] = None
    annual_substrate_tonnes: float = Field(default=1000.0, gt=0)
    ser: float = Field(default=0.22, gt=0, le=1.0)
    operating_days: int = Field(default=340, ge=1, le=365)
    batch_days: float = Field(default=14.0, gt=0)

    # Prices
    price_larvae: float = Field(default=2.50, ge=0)
    price_frass: float = Field(default=0.30, ge=0)
    price_chitin: float = Field(default=25.00, ge=0)
    price_oil: float = Field(default=1.20, ge=0)

    # Composition
    protein_content: float = Field(default=42.0, ge=0, le=100)
    fat_content: float = Field(default=35.0, ge=0, le=100)
    chitin_content: float = Field(default=8.0, ge=0, le=100)

    # CAPEX
    capex_facility: float = Field(default=500_000, ge=0)
    capex_equipment: float = Field(default=300_000, ge=0)
    capex_processing: float = Field(default=200_000, ge=0)
    capex_other: float = Field(default=50_000, ge=0)

    # OPEX
    opex_substrate: float = Field(default=50_000)
    opex_labor: float = Field(default=150_000, ge=0)
    opex_energy: float = Field(default=40_000, ge=0)
    opex_maintenance: float = Field(default=30_000, ge=0)
    opex_packaging: float = Field(default=20_000, ge=0)
    opex_transport: float = Field(default=25_000, ge=0)
    opex_regulatory: float = Field(default=15_000, ge=0)
    opex_other: float = Field(default=10_000, ge=0)

    # Financial
    project_lifetime_years: int = Field(default=15, ge=1, le=50)
    discount_rate: float = Field(default=0.10, ge=0, le=1)
    tax_rate: float = Field(default=0.25, ge=0, le=1)
    waste_gate_fee: float = Field(default=0, ge=0)


@router.post("/compute")
async def compute_tea_endpoint(
    body: TEARequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Compute techno-economic analysis."""
    start_time = time.perf_counter()

    # Verify batch if provided
    if body.batch_id:
        result = await db.execute(
            select(Batch).where(Batch.id == body.batch_id, Batch.tenant_id == current_user.tenant_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    tea_input = TEAInput(
        annual_substrate_tonnes=body.annual_substrate_tonnes,
        ser=body.ser,
        operating_days=body.operating_days,
        batch_days=body.batch_days,
        price_larvae=body.price_larvae,
        price_frass=body.price_frass,
        price_chitin=body.price_chitin,
        price_oil=body.price_oil,
        protein_content=body.protein_content,
        fat_content=body.fat_content,
        chitin_content=body.chitin_content,
        capex_facility=body.capex_facility,
        capex_equipment=body.capex_equipment,
        capex_processing=body.capex_processing,
        capex_other=body.capex_other,
        opex_substrate=body.opex_substrate,
        opex_labor=body.opex_labor,
        opex_energy=body.opex_energy,
        opex_maintenance=body.opex_maintenance,
        opex_packaging=body.opex_packaging,
        opex_transport=body.opex_transport,
        opex_regulatory=body.opex_regulatory,
        opex_other=body.opex_other,
        project_lifetime_years=body.project_lifetime_years,
        discount_rate=body.discount_rate,
        tax_rate=body.tax_rate,
        waste_gate_fee=body.waste_gate_fee,
    )

    tea_result = compute_tea(tea_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    # Persist if batch specified
    if body.batch_id:
        calc = Calculation(
            batch_id=body.batch_id,
            calc_type="tea",
            status="completed",
            inputs=body.model_dump(),
            result={
                "npv": tea_result.npv,
                "irr": tea_result.irr,
                "payback_years": tea_result.payback_years,
                "lcop": tea_result.lcop,
                "roi": tea_result.roi,
                "total_revenue": tea_result.total_revenue,
                "total_opex": tea_result.total_opex,
                "gross_margin": tea_result.gross_margin,
            },
            duration_ms=round(duration_ms, 2),
            engine_version=tea_result.engine_version,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
        db.add(calc)
        await db.commit()

    return {
        "production": {
            "annual_larvae_tonnes": tea_result.annual_larvae_tonnes,
            "annual_frass_tonnes": tea_result.annual_frass_tonnes,
            "batches_per_year": tea_result.batches_per_year,
        },
        "financials": {
            "total_revenue": tea_result.total_revenue,
            "total_capex": tea_result.total_capex,
            "total_opex": tea_result.total_opex,
            "gross_profit": tea_result.gross_profit,
            "net_profit": tea_result.net_profit,
            "gross_margin_pct": tea_result.gross_margin,
        },
        "investment_metrics": {
            "npv": tea_result.npv,
            "irr_pct": tea_result.irr,
            "payback_years": tea_result.payback_years,
            "discounted_payback_years": tea_result.discounted_payback,
            "lcop_per_kg": tea_result.lcop,
            "roi_pct": tea_result.roi,
        },
        "revenue_breakdown": tea_result.revenue_breakdown,
        "opex_breakdown": tea_result.opex_breakdown,
        "capex_breakdown": tea_result.capex_breakdown,
        "cash_flows": tea_result.cash_flows,
        "computation_time_ms": round(duration_ms, 2),
    }


@router.post("/estimate", response_model=SustainabilityResultResponse)
async def estimate_tea_kernel_endpoint(
    body: TEAEstimateRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    return await estimate_tea(db, tenant_id=current_user.tenant_id, user_id=current_user.id, payload=body)
