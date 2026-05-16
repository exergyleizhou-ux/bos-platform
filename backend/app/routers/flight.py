"""
BOS Pipeline v9.0 — Flight Envelope Router

API endpoints for operating envelope checks.
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
from app.engine.flight_envelope import FlightEnvelopeInput, check_flight_envelope

router = APIRouter()


class FlightEnvelopeRequest(BaseModel):
    """Flight envelope check request."""

    batch_id: Optional[int] = None
    species: str = Field(default="BSF", max_length=100)
    temperature: Optional[float] = Field(None, ge=-50, le=100)
    moisture: Optional[float] = Field(None, ge=0, le=100)
    feed_rate: Optional[float] = Field(None, ge=0)
    density: Optional[float] = Field(None, ge=0)
    ph: Optional[float] = Field(None, ge=0, le=14)
    o2_level: Optional[float] = Field(None, ge=0, le=100)
    co2_level: Optional[float] = Field(None, ge=0, le=100)


@router.post("/check")
async def check_envelope(
    body: FlightEnvelopeRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    """Check if operating parameters are within the flight envelope."""
    start_time = time.perf_counter()

    # Verify batch if provided
    if body.batch_id:
        result = await db.execute(
            select(Batch).where(Batch.id == body.batch_id, Batch.tenant_id == current_user.tenant_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    envelope_input = FlightEnvelopeInput(
        species=body.species,
        temperature=body.temperature,
        moisture=body.moisture,
        feed_rate=body.feed_rate,
        density=body.density,
        ph=body.ph,
        o2_level=body.o2_level,
        co2_level=body.co2_level,
    )

    envelope_result = check_flight_envelope(envelope_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    # Persist if batch specified
    if body.batch_id:
        calc = Calculation(
            batch_id=body.batch_id,
            calc_type="flight_envelope",
            status="completed",
            inputs=body.model_dump(),
            result={
                "overall_zone": envelope_result.overall_zone,
                "in_envelope": envelope_result.in_envelope,
                "checks": [
                    {
                        "parameter": c.parameter,
                        "value": c.value,
                        "zone": c.zone,
                        "deviation_pct": c.deviation_pct,
                        "message": c.message,
                    }
                    for c in envelope_result.checks
                ],
            },
            passed=envelope_result.in_envelope,
            duration_ms=round(duration_ms, 2),
            engine_version=envelope_result.engine_version,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
        db.add(calc)
        await db.commit()

    return {
        "overall_zone": envelope_result.overall_zone,
        "in_envelope": envelope_result.in_envelope,
        "species": envelope_result.species,
        "checks": [
            {
                "parameter": c.parameter,
                "value": c.value,
                "unit": c.unit,
                "zone": c.zone,
                "optimal_range": [c.optimal_min, c.optimal_max],
                "safe_range": [c.safe_min, c.safe_max],
                "deviation_pct": c.deviation_pct,
                "message": c.message,
            }
            for c in envelope_result.checks
        ],
        "warnings": envelope_result.warnings,
        "alarms": envelope_result.alarms,
        "computation_time_ms": round(duration_ms, 2),
    }


@router.get("/ranges/{species_code}")
async def get_species_ranges(
    species_code: str,
    current_user: User = Depends(require_minimum_role("viewer")),
):
    """Get optimal and safe operating ranges for a species."""
    from app.engine.species_db import get_optimal_ranges, get_species

    sp = get_species(species_code)
    if not sp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown species: {species_code}")

    ranges = get_optimal_ranges(species_code)

    return {
        "species": {
            "code": sp.code,
            "scientific_name": sp.scientific_name,
            "common_name": sp.common_name,
        },
        "ranges": ranges,
        "lethal_thresholds": {
            "temperature_low": sp.temp_lethal_low,
            "temperature_high": sp.temp_lethal_high,
        },
    }
