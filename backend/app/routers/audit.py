"""
BOS Pipeline v9.0 — Audit Log Router

Provides read access to the audit trail.
All actions are immutable (append-only).
"""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role, set_tenant_context, get_pagination, PaginationParams
from app.models import User, AuditLog
from app.schemas import PaginatedResponse

router = APIRouter()


@router.get("")
async def list_audit_logs(
    pagination: PaginationParams = Depends(get_pagination),
    action: Optional[str] = Query(None, max_length=50),
    resource: Optional[str] = Query(None, max_length=50),
    username: Optional[str] = Query(None, max_length=100),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user: User = Depends(require_minimum_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """
    List audit logs (admin only).
    Scoped to the current tenant.
    """
    query = select(AuditLog).where(AuditLog.tenant_id == current_user.tenant_id)

    if action:
        query = query.where(AuditLog.action == action)
    if resource:
        query = query.where(AuditLog.resource == resource)
    if username:
        query = query.where(AuditLog.username.ilike(f"%{username}%"))
    if date_from:
        query = query.where(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        next_day = date_to + __import__("datetime").timedelta(days=1)
        query = query.where(AuditLog.created_at < datetime.combine(next_day, datetime.min.time()))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    return {
        "items": [
            {
                "id": log.id,
                "action": log.action,
                "resource": log.resource,
                "resource_id": log.resource_id,
                "username": log.username,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent[:100] if log.user_agent else None,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
        "total_pages": total_pages,
    }


@router.get("/actions")
async def list_audit_actions(
    current_user: User = Depends(require_minimum_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Get distinct audit actions for filtering."""
    result = await db.execute(
        select(AuditLog.action)
        .where(AuditLog.tenant_id == current_user.tenant_id)
        .distinct()
        .order_by(AuditLog.action)
    )
    actions = [row[0] for row in result.all()]

    return {"actions": actions}


@router.get("/stats")
async def audit_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_minimum_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Get audit log statistics for the last N days."""
    since = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=days)

    total = (await db.execute(
        select(func.count()).where(
            AuditLog.tenant_id == current_user.tenant_id,
            AuditLog.created_at >= since,
        )
    )).scalar() or 0

    # By action
    action_result = await db.execute(
        select(AuditLog.action, func.count())
        .where(AuditLog.tenant_id == current_user.tenant_id, AuditLog.created_at >= since)
        .group_by(AuditLog.action)
        .order_by(func.count().desc())
    )
    by_action = {row[0]: row[1] for row in action_result.all()}

    # By user
    user_result = await db.execute(
        select(AuditLog.username, func.count())
        .where(AuditLog.tenant_id == current_user.tenant_id, AuditLog.created_at >= since)
        .group_by(AuditLog.username)
        .order_by(func.count().desc())
        .limit(10)
    )
    by_user = {row[0]: row[1] for row in user_result.all()}

    return {
        "period_days": days,
        "total_events": total,
        "by_action": by_action,
        "top_users": by_user,
    }
