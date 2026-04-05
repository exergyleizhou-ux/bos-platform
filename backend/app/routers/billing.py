"""
BOS Pipeline v9.0 �� Billing Router

Manages tenant subscriptions and plan upgrades.
Feature-flagged: requires FF_ENABLE_BILLING.

Plans:
  - free       : 5 users, 100 batches, 500 calculations
  - starter    : 15 users, 1000 batches, 5000 calculations
  - pro        : 50 users, 10000 batches, 50000 calculations
  - enterprise : unlimited
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_async_session
from app.deps import require_role
from app.models import User, Tenant, AuditLog

router = APIRouter()
settings = get_settings()

PLAN_LIMITS = {
    "free": {"max_users": 5, "max_batches": 100, "max_calculations": 500},
    "starter": {"max_users": 15, "max_batches": 1_000, "max_calculations": 5_000},
    "pro": {"max_users": 50, "max_batches": 10_000, "max_calculations": 50_000},
    "enterprise": {"max_users": 999_999, "max_batches": 999_999_999, "max_calculations": 999_999_999},
}

PLAN_PRICES = {
    "free": 0.0,
    "starter": 49.0,
    "pro": 199.0,
    "enterprise": 999.0,
}


class PlanChangeRequest(BaseModel):
    """Plan change request."""

    new_plan: str = Field(..., pattern=r"^(free|starter|pro|enterprise)$")


@router.get("/current")
async def get_billing_info(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Get current billing information for the tenant."""
    if not settings.FF_ENABLE_BILLING:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Billing is not enabled")

    result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    plan = tenant.plan or "free"

    return {
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
        "current_plan": plan,
        "limits": PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]),
        "price_monthly": PLAN_PRICES.get(plan, 0),
        "billing_email": tenant.billing_email,
        "available_plans": [
            {
                "plan": p,
                "price_monthly": PLAN_PRICES[p],
                "limits": PLAN_LIMITS[p],
            }
            for p in PLAN_LIMITS
        ],
    }


@router.post("/change-plan")
async def change_plan(
    body: PlanChangeRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Change the tenant's subscription plan."""
    if not settings.FF_ENABLE_BILLING:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Billing is not enabled")

    result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    old_plan = tenant.plan
    if old_plan == body.new_plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already on this plan")

    # Apply new limits
    new_limits = PLAN_LIMITS.get(body.new_plan, PLAN_LIMITS["free"])
    tenant.plan = body.new_plan
    tenant.max_users = new_limits["max_users"]
    tenant.max_batches = new_limits["max_batches"]
    tenant.max_calculations = new_limits["max_calculations"]

    # Audit
    audit = AuditLog(
        action="PLAN_CHANGE",
        resource="billing",
        resource_id=str(tenant.id),
        username=current_user.username,
        user_id=current_user.id,
        tenant_id=tenant.id,
        details={"old_plan": old_plan, "new_plan": body.new_plan},
    )
    db.add(audit)
    await db.commit()

    return {
        "message": f"Plan changed from '{old_plan}' to '{body.new_plan}'",
        "new_plan": body.new_plan,
        "new_limits": new_limits,
        "price_monthly": PLAN_PRICES.get(body.new_plan, 0),
    }


@router.get("/usage")
async def get_usage(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Get current resource usage vs plan limits."""
    if not settings.FF_ENABLE_BILLING:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Billing is not enabled")

    result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    from sqlalchemy import func
    from app.models import Batch, Calculation

    tid = current_user.tenant_id
    user_count = (await db.execute(select(func.count()).where(User.tenant_id == tid))).scalar() or 0
    batch_count = (await db.execute(select(func.count()).where(Batch.tenant_id == tid))).scalar() or 0
    calc_count = (await db.execute(select(func.count()).where(Calculation.tenant_id == tid))).scalar() or 0

    return {
        "plan": tenant.plan,
        "usage": {
            "users": {"current": user_count, "limit": tenant.max_users, "pct": round(user_count / max(tenant.max_users, 1) * 100, 1)},
            "batches": {"current": batch_count, "limit": tenant.max_batches, "pct": round(batch_count / max(tenant.max_batches, 1) * 100, 1)},
            "calculations": {"current": calc_count, "limit": tenant.max_calculations, "pct": round(calc_count / max(tenant.max_calculations, 1) * 100, 1)},
        },
    }
