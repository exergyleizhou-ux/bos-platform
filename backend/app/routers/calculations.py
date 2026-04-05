"""
BOS Pipeline v9.0 �� Calculations Router

Read-only access to calculation results.
Calculations are created by the SER, simulation, and other engine routers.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import set_tenant_context, get_pagination, PaginationParams
from app.models import User, Calculation
from app.schemas import CalculationResponse, PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[CalculationResponse])
async def list_calculations(
    pagination: PaginationParams = Depends(get_pagination),
    batch_id: Optional[int] = None,
    calc_type: Optional[str] = Query(None, max_length=50),
    status_filter: Optional[str] = Query(None, alias="status", pattern=r"^(pending|running|completed|failed)$"),
    passed: Optional[bool] = None,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """List calculations with filtering."""
    query = select(Calculation).where(Calculation.tenant_id == current_user.tenant_id)

    if batch_id is not None:
        query = query.where(Calculation.batch_id == batch_id)
    if calc_type:
        query = query.where(Calculation.calc_type == calc_type)
    if status_filter:
        query = query.where(Calculation.status == status_filter)
    if passed is not None:
        query = query.where(Calculation.passed == passed)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Calculation.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    calcs = result.scalars().all()

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    return PaginatedResponse(
        items=[CalculationResponse.model_validate(c) for c in calcs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/{calculation_id}", response_model=CalculationResponse)
async def get_calculation(
    calculation_id: int,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific calculation by ID."""
    result = await db.execute(
        select(Calculation).where(
            Calculation.id == calculation_id,
            Calculation.tenant_id == current_user.tenant_id,
        )
    )
    calc = result.scalar_one_or_none()

    if not calc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calculation not found")

    return CalculationResponse.model_validate(calc)


@router.get("/stats/summary")
async def calculation_stats(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get calculation statistics for the current tenant."""
    tid = current_user.tenant_id

    total = (await db.execute(
        select(func.count()).where(Calculation.tenant_id == tid)
    )).scalar() or 0

    completed = (await db.execute(
        select(func.count()).where(Calculation.tenant_id == tid, Calculation.status == "completed")
    )).scalar() or 0

    passed_count = (await db.execute(
        select(func.count()).where(Calculation.tenant_id == tid, Calculation.passed == True)
    )).scalar() or 0

    failed_count = (await db.execute(
        select(func.count()).where(Calculation.tenant_id == tid, Calculation.passed == False)
    )).scalar() or 0

    avg_ser = (await db.execute(
        select(func.avg(Calculation.ser_value)).where(
            Calculation.tenant_id == tid,
            Calculation.ser_value.isnot(None),
        )
    )).scalar()

    avg_duration = (await db.execute(
        select(func.avg(Calculation.duration_ms)).where(
            Calculation.tenant_id == tid,
            Calculation.duration_ms.isnot(None),
        )
    )).scalar()

    return {
        "total": total,
        "completed": completed,
        "pass_rate": round(passed_count / max(completed, 1) * 100, 2),
        "passed": passed_count,
        "failed": failed_count,
        "average_ser": round(float(avg_ser), 4) if avg_ser else None,
        "average_duration_ms": round(float(avg_duration), 2) if avg_duration else None,
    }
