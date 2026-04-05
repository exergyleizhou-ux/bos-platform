"""
BOS Pipeline v9.0 �� Tenants Router

Tenant management endpoints. Most operations are admin-only.
Regular users can view their own tenant info.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import get_current_user, require_role, get_pagination, PaginationParams
from app.models import Tenant, User, Batch, Calculation
from app.schemas import (
    MessageResponse,
    PaginatedResponse,
    TenantCreate,
    TenantResponse,
    TenantUpdate,
)

router = APIRouter()


@router.get("/current", response_model=TenantResponse)
async def get_current_tenant(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get the current user's tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    return TenantResponse.model_validate(tenant)


@router.get("/current/stats")
async def get_tenant_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get usage statistics for the current tenant."""
    tid = current_user.tenant_id

    user_count = (await db.execute(
        select(func.count()).where(User.tenant_id == tid)
    )).scalar() or 0

    batch_count = (await db.execute(
        select(func.count()).where(Batch.tenant_id == tid)
    )).scalar() or 0

    calc_count = (await db.execute(
        select(func.count()).where(Calculation.tenant_id == tid)
    )).scalar() or 0

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tid))
    tenant = tenant_result.scalar_one_or_none()

    return {
        "tenant_id": tid,
        "users": {"current": user_count, "max": tenant.max_users if tenant else 0},
        "batches": {"current": batch_count, "max": tenant.max_batches if tenant else 0},
        "calculations": {"current": calc_count, "max": tenant.max_calculations if tenant else 0},
        "plan": tenant.plan if tenant else "free",
    }


@router.patch("/current", response_model=TenantResponse)
async def update_current_tenant(
    body: TenantUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Update the current tenant settings (admin only)."""
    result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    update_data = body.model_dump(exclude_unset=True)

    # Prevent plan changes via this endpoint (use billing)
    if "plan" in update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan changes must be done through the billing endpoint",
        )

    for key, value in update_data.items():
        setattr(tenant, key, value)

    await db.commit()
    await db.refresh(tenant)

    return TenantResponse.model_validate(tenant)


# ���� Super-admin endpoints (for platform management) ����

@router.get("", response_model=PaginatedResponse[TenantResponse])
async def list_all_tenants(
    pagination: PaginationParams = Depends(get_pagination),
    plan: Optional[str] = Query(None),
    is_active: Optional[bool] = None,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """
    List all tenants (platform admin only).
    In a real deployment, add a super-admin check here.
    """
    query = select(Tenant)

    if plan:
        query = query.where(Tenant.plan == plan)
    if is_active is not None:
        query = query.where(Tenant.is_active == is_active)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Tenant.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    tenants = result.scalars().all()

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    return PaginatedResponse(
        items=[TenantResponse.model_validate(t) for t in tenants],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: TenantCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new tenant (platform admin only)."""
    # Check slug uniqueness
    existing = await db.execute(select(Tenant).where(Tenant.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant slug '{body.slug}' already exists",
        )

    tenant = Tenant(
        name=body.name,
        slug=body.slug,
        plan=body.plan,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return TenantResponse.model_validate(tenant)
