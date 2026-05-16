"""
BOS Pipeline v9.0 risk assessment router.

API endpoints for contaminant risk assessment.
"""

import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.engine.risk_engine import (
    HEAVY_METAL_LIMITS,
    MICROBIAL_LIMITS,
    MYCOTOXIN_LIMITS,
    PESTICIDE_LIMITS,
    SUBSTRATE_RISK_PROFILES,
    ContaminantReading,
    RiskInput,
    assess_risk,
)
from app.models import Batch, Calculation, User

router = APIRouter()


class ContaminantItem(BaseModel):
    """Single contaminant measurement."""

    name: str = Field(..., min_length=1, max_length=100)
    value: float = Field(..., ge=0)
    unit: str = Field(default="mg/kg")
    category: str = Field(default="heavy_metal", pattern=r"^(heavy_metal|pesticide|mycotoxin|microbial)$")


class RiskRequest(BaseModel):
    """Risk assessment request."""

    batch_id: int
    contaminants: List[ContaminantItem]
    species: str = Field(default="BSF", max_length=100)
    product_use: str = Field(default="feed", pattern=r"^(feed|food|fertilizer)$")
    substrate_type: str | None = Field(default=None, max_length=100)


@router.post("/assess")
async def assess_risk_endpoint(
    body: RiskRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Perform contaminant risk assessment for a batch."""
    start_time = time.perf_counter()

    result = await db.execute(
        select(Batch).where(Batch.id == body.batch_id, Batch.tenant_id == current_user.tenant_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    readings = [
        ContaminantReading(name=c.name, value=c.value, unit=c.unit, category=c.category)
        for c in body.contaminants
    ]

    risk_input = RiskInput(
        contaminants=readings,
        species=body.species,
        product_use=body.product_use,
        substrate_type=body.substrate_type or batch.substrate or "mixed_organic_waste",
    )

    risk_result = assess_risk(risk_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    calc = Calculation(
        batch_id=body.batch_id,
        calc_type="risk",
        status="completed",
        inputs=body.model_dump(),
        result={
            "overall_risk": risk_result.overall_risk,
            "overall_safe": risk_result.overall_safe,
            "critical_count": risk_result.critical_count,
            "high_count": risk_result.high_count,
            "medium_count": risk_result.medium_count,
            "checks": [
                {
                    "name": c.name,
                    "value": c.value,
                    "limit": c.limit,
                    "ratio": c.ratio,
                    "risk_level": c.risk_level,
                    "category": c.category,
                    "message": c.message,
                }
                for c in risk_result.checks
            ],
            "recommendations": risk_result.recommendations,
            "warnings": risk_result.warnings,
        },
        passed=risk_result.overall_safe,
        duration_ms=round(duration_ms, 2),
        engine_version=risk_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    await db.commit()

    return {
        "overall_risk": risk_result.overall_risk,
        "overall_safe": risk_result.overall_safe,
        "summary": {
            "critical": risk_result.critical_count,
            "high": risk_result.high_count,
            "medium": risk_result.medium_count,
        },
        "checks": [
            {
                "name": c.name,
                "value": c.value,
                "limit": c.limit,
                "unit": c.unit,
                "ratio": c.ratio,
                "risk_level": c.risk_level,
                "category": c.category,
                "message": c.message,
                "recommendation": c.recommendation,
            }
            for c in risk_result.checks
        ],
        "recommendations": risk_result.recommendations,
        "warnings": risk_result.warnings,
        "substrate_profile": risk_result.substrate_profile,
        "regulatory_framework": risk_result.regulatory_framework,
        "computation_time_ms": round(duration_ms, 2),
    }


@router.get("/limits")
async def get_regulatory_limits(
    current_user: User = Depends(require_minimum_role("viewer")),
):
    """Get all regulatory limits used in risk assessment."""
    del current_user
    return {
        "heavy_metals": HEAVY_METAL_LIMITS,
        "pesticides": PESTICIDE_LIMITS,
        "mycotoxins": MYCOTOXIN_LIMITS,
        "microbial": MICROBIAL_LIMITS,
        "substrate_profiles": SUBSTRATE_RISK_PROFILES,
    }
