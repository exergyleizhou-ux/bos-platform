"""
BOS Pipeline v9.0 - SER router.

This router keeps the fuller v9 calculation flow while also exposing a few
compatibility endpoints used by the current frontend and legacy tests.
"""

import time
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role, set_tenant_context
from app.engine.ser_engine import (
    SERInput,
    compute_ser,
    compute_ser_batch,
    compute_ser_statistics,
    grade_ser,
)
from app.models import Batch, Calculation, User
from app.schemas import SERRequest, SERResponse

router = APIRouter()


def _wrap_ratio(value: float | None) -> dict | None:
    if value is None:
        return None
    return {"ratio": float(value)}


def _wrap_nitrogen(body: SERRequest, recovery: float | None) -> dict | None:
    if recovery is None:
        return None
    total_out = float(body.n_larvae or 0.0) + float(body.n_frass or 0.0)
    total_in = float(body.n_in or 0.0)
    return {
        "recovery_pct": float(recovery),
        "n_loss": max(total_in - total_out, 0.0),
    }


def _build_response(
    body: SERRequest,
    result,
    duration_ms: float,
) -> SERResponse:
    return SERResponse(
        ser_value=result.ser_value,
        eer=result.eer,
        mcr=result.mcr,
        bcr=result.bcr,
        nitrogen_balance=_wrap_nitrogen(body, result.nitrogen_balance),
        ash_balance=_wrap_ratio(result.ash_balance),
        fat_balance=_wrap_ratio(result.fat_balance),
        passed=result.passed,
        fail_codes=result.fail_codes,
        grade=result.grade,
        recommendations=result.recommendations,
        batch_id=body.batch_id,
        computed_at=datetime.now(timezone.utc),
        computation_time_ms=round(duration_ms, 2),
    )


@router.post("/compute", response_model=SERResponse)
async def compute_ser_endpoint(
    body: SERRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Compute SER for manual input or a stored batch.

    If `batch_id` is supplied, the result is persisted and the batch score is
    updated. If it is omitted, the computation is treated as an ad hoc
    calculator request and returned directly.
    """
    start_time = time.perf_counter()

    batch = None
    if body.batch_id is not None:
        result = await db.execute(
            select(Batch).where(
                Batch.id == body.batch_id,
                Batch.tenant_id == current_user.tenant_id,
            )
        )
        batch = result.scalar_one_or_none()
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found",
            )

    ser_input = SERInput(
        dm_in=body.dm_in,
        dm_out=body.dm_out,
        n_in=body.n_in,
        n_larvae=body.n_larvae,
        n_frass=body.n_frass,
        ash_in=body.ash_in or 0.0,
        ash_out=body.ash_out or 0.0,
        fat_in=body.fat_in or 0.0,
        fat_out=body.fat_out or 0.0,
    )
    ser_result = compute_ser(ser_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    if batch is not None:
        calc = Calculation(
            batch_id=batch.id,
            calc_type="ser",
            status="completed",
            inputs=body.model_dump(),
            result={
                "ser_value": ser_result.ser_value,
                "eer": ser_result.eer,
                "mcr": ser_result.mcr,
                "bcr": ser_result.bcr,
                "nitrogen_balance": ser_result.nitrogen_balance,
                "ash_balance": ser_result.ash_balance,
                "fat_balance": ser_result.fat_balance,
                "grade": ser_result.grade,
                "recommendations": ser_result.recommendations,
            },
            ser_value=ser_result.ser_value,
            passed=ser_result.passed,
            fail_codes=ser_result.fail_codes,
            duration_ms=round(duration_ms, 2),
            engine_version=ser_result.engine_version,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
        db.add(calc)
        batch.score = ser_result.ser_value
        await db.commit()

    return _build_response(body, ser_result, duration_ms)


@router.post("/compute-batch")
async def compute_ser_batch_endpoint(
    bodies: List[SERRequest],
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    """Compute SER for multiple payloads in one request."""
    del current_user, db
    if len(bodies) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 batches per request",
        )

    results = compute_ser_batch(
        [
            SERInput(
                dm_in=body.dm_in,
                dm_out=body.dm_out,
                n_in=body.n_in,
                n_larvae=body.n_larvae,
                n_frass=body.n_frass,
                ash_in=body.ash_in or 0.0,
                ash_out=body.ash_out or 0.0,
                fat_in=body.fat_in or 0.0,
                fat_out=body.fat_out or 0.0,
            )
            for body in bodies
        ]
    )
    return {
        "results": [
            {
                "batch_id": body.batch_id,
                "ser_value": result.ser_value,
                "grade": result.grade,
                "passed": result.passed,
                "fail_codes": result.fail_codes,
            }
            for body, result in zip(bodies, results)
        ],
        "count": len(results),
    }


@router.post("/compute-batch/{batch_id}", response_model=SERResponse)
@router.post("/compute/batch/{batch_id}", response_model=SERResponse)
async def compute_ser_from_batch_endpoint(
    batch_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    """Compute SER directly from a stored batch."""
    result = await db.execute(
        select(Batch).where(
            Batch.id == batch_id,
            Batch.tenant_id == current_user.tenant_id,
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    body = SERRequest(
        batch_id=batch.id,
        dm_in=batch.dm_in or 0.0,
        dm_out=batch.dm_out or 0.0,
        n_in=batch.n_in or 0.0,
        n_larvae=batch.n_larvae or 0.0,
        n_frass=batch.n_frass or 0.0,
        ash_in=batch.ash_in,
        ash_out=batch.ash_out,
        fat_in=batch.fat_in,
        fat_out=batch.fat_out,
    )
    return await compute_ser_endpoint(body=body, current_user=current_user, db=db)


@router.get("/result/batch/{batch_id}")
async def ser_result_for_batch(
    batch_id: int,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Return the latest SER result for a batch."""
    result = await db.execute(
        select(Calculation)
        .where(
            Calculation.batch_id == batch_id,
            Calculation.tenant_id == current_user.tenant_id,
            Calculation.calc_type == "ser",
        )
        .order_by(Calculation.created_at.desc())
        .limit(1)
    )
    calc = result.scalar_one_or_none()
    if not calc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SER result not found",
        )

    payload = calc.result or {}
    return {
        "id": calc.id,
        "batch_id": calc.batch_id,
        "ser_value": calc.ser_value,
        "eer": payload.get("eer"),
        "mcr": payload.get("mcr"),
        "bcr": payload.get("bcr"),
        "grade": payload.get("grade") or grade_ser(calc.ser_value or 0.0),
        "passed": calc.passed,
        "recommendations": payload.get("recommendations", []),
        "computed_at": calc.created_at.isoformat() if calc.created_at else None,
    }


@router.get("/history")
async def ser_history(
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Paginated SER history for the current tenant."""
    base_query = (
        select(Calculation, Batch.dm_in, Batch.dm_out)
        .join(Batch, Batch.id == Calculation.batch_id)
        .where(
            Calculation.tenant_id == current_user.tenant_id,
            Calculation.calc_type == "ser",
        )
        .order_by(Calculation.created_at.desc())
    )
    total = (
        await db.execute(select(func.count()).select_from(base_query.subquery()))
    ).scalar() or 0
    result = await db.execute(
        base_query.offset((page - 1) * page_size).limit(page_size)
    )

    items = []
    for calc, dm_in, dm_out in result.all():
        payload = calc.result or {}
        items.append(
            {
                "id": calc.id,
                "batch_id": calc.batch_id,
                "dm_in": dm_in,
                "dm_out": dm_out,
                "ser_value": calc.ser_value,
                "eer": payload.get("eer"),
                "mcr": payload.get("mcr"),
                "bcr": payload.get("bcr"),
                "grade": payload.get("grade") or grade_ser(calc.ser_value or 0.0),
                "passed": calc.passed,
                "computed_at": calc.created_at.isoformat() if calc.created_at else None,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/statistics")
async def ser_statistics(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get aggregate SER statistics for the current tenant."""
    result = await db.execute(
        select(Calculation).where(
            Calculation.tenant_id == current_user.tenant_id,
            Calculation.calc_type == "ser",
            Calculation.status == "completed",
        )
    )
    calcs = result.scalars().all()

    if not calcs:
        return {"message": "No SER calculations found", "stats": None}

    from app.engine.ser_engine import SERResult

    ser_results = []
    for calc in calcs:
        ser_val = calc.ser_value or 0.0
        ser_results.append(
            SERResult(
                ser_value=ser_val,
                passed=calc.passed or False,
                grade=grade_ser(ser_val),
            )
        )

    return {"stats": compute_ser_statistics(ser_results)}
