"""
BOS Pipeline v9.0 — Admin Router

Platform administration endpoints:
  - System-wide statistics
  - Tenant management
  - User management (cross-tenant)
  - Cache management
  - Database maintenance
  - Feature flag overrides
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_async_session
from app.deps import parse_user_roles, require_role
from app.models import AuditLog, Batch, Calculation, Tenant, User, UserRoleGrant
from app.schemas import UserRoleGrantResponse
from app.schemas.user import (
    DB_BACKED_ROLE_ASSIGNMENT_SCOPE,
    FINAL_ACTION_GRANT_ROLES,
    GOVERNANCE_GRANT_ROLES,
    ROLE_GRANT_POLICY_VERSION,
)

router = APIRouter()
settings = get_settings()


@router.get("/stats")
async def platform_stats(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Get platform-wide statistics."""
    tenant_count = (await db.execute(select(func.count()).select_from(Tenant))).scalar() or 0
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    active_users = (await db.execute(select(func.count()).where(User.is_active.is_(True)))).scalar() or 0
    batch_count = (await db.execute(select(func.count()).select_from(Batch))).scalar() or 0
    calc_count = (await db.execute(select(func.count()).select_from(Calculation))).scalar() or 0

    # Recent activity (last 24h)
    yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_batches = (await db.execute(select(func.count()).where(Batch.created_at >= yesterday))).scalar() or 0
    recent_calcs = (await db.execute(select(func.count()).where(Calculation.created_at >= yesterday))).scalar() or 0
    recent_logins = (
        await db.execute(
            select(func.count()).where(
                AuditLog.action == "LOGIN",
                AuditLog.created_at >= yesterday,
            )
        )
    ).scalar() or 0

    # Calculation type distribution
    type_dist_result = await db.execute(
        select(Calculation.calc_type, func.count()).group_by(Calculation.calc_type).order_by(func.count().desc())
    )
    type_distribution = {row[0]: row[1] for row in type_dist_result.all()}

    # Tenant plan distribution
    plan_dist_result = await db.execute(
        select(Tenant.plan, func.count()).group_by(Tenant.plan).order_by(func.count().desc())
    )
    plan_distribution = {row[0]: row[1] for row in plan_dist_result.all()}

    return {
        "totals": {
            "tenants": tenant_count,
            "users": user_count,
            "active_users": active_users,
            "batches": batch_count,
            "calculations": calc_count,
        },
        "last_24h": {
            "new_batches": recent_batches,
            "new_calculations": recent_calcs,
            "logins": recent_logins,
        },
        "distributions": {
            "calculation_types": type_distribution,
            "tenant_plans": plan_distribution,
        },
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
    }


@router.get("/users")
async def list_users(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """List users across tenants for admin review."""
    del current_user
    result = await db.execute(select(User).order_by(User.created_at.desc()).limit(200))
    users = result.scalars().all()
    if not users:
        return {"items": [], "total": 0}

    user_ids = [user.id for user in users]
    tenant_ids = [user.tenant_id for user in users]
    grants_result = await db.execute(
        select(UserRoleGrant)
        .where(
            UserRoleGrant.user_id.in_(user_ids),
            UserRoleGrant.tenant_id.in_(tenant_ids),
            UserRoleGrant.role.in_(GOVERNANCE_GRANT_ROLES),
            UserRoleGrant.is_active.is_(True),
        )
        .order_by(UserRoleGrant.role.asc(), UserRoleGrant.id.asc())
    )
    grants_by_user_tenant: dict[tuple[int, int], list[UserRoleGrant]] = defaultdict(list)
    for grant in grants_result.scalars().all():
        grants_by_user_tenant[(grant.tenant_id, grant.user_id)].append(grant)

    return {
        "items": [
            _admin_user_read_model(
                user=user,
                active_grants=grants_by_user_tenant.get((user.tenant_id, user.id), []),
            )
            for user in users
        ],
        "total": len(users),
    }


def _admin_user_read_model(*, user: User, active_grants: list[UserRoleGrant]) -> dict:
    legacy_roles = parse_user_roles(user.role)
    db_roles = {grant.role for grant in active_grants}
    resolved_roles = legacy_roles | db_roles
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "role_grant_summary": {
            "user_id": user.id,
            "tenant_id": user.tenant_id,
            "assignment_scope": DB_BACKED_ROLE_ASSIGNMENT_SCOPE,
            "grant_policy_version": ROLE_GRANT_POLICY_VERSION,
            "base_role": user.role,
            "legacy_roles": sorted(legacy_roles),
            "db_grants": [UserRoleGrantResponse.model_validate(grant) for grant in active_grants],
            "resolved_roles": sorted(resolved_roles),
            "manageable_governance_grants": sorted(
                role for role in resolved_roles if role in GOVERNANCE_GRANT_ROLES
            ),
            "supported_governance_grants": sorted(GOVERNANCE_GRANT_ROLES),
            "manageable_final_action_grants": sorted(
                role for role in resolved_roles if role in FINAL_ACTION_GRANT_ROLES
            ),
            "supported_final_action_grants": sorted(FINAL_ACTION_GRANT_ROLES),
        },
    }


@router.get("/db-health")
async def database_health(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Check database health and statistics."""
    try:
        # Database size
        db_size_result = await db.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))"))
        db_size = db_size_result.scalar()

        # Connection count
        conn_result = await db.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"))
        conn_count = conn_result.scalar()

        # Table sizes
        table_sizes_result = await db.execute(
            text(
                """
            SELECT relname AS table_name,
                   pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
                   n_live_tup AS row_count
            FROM pg_stat_user_tables
            ORDER BY pg_total_relation_size(relid) DESC
            LIMIT 20
        """
            )
        )
        table_sizes = [{"table": row[0], "size": row[1], "rows": row[2]} for row in table_sizes_result.all()]

        return {
            "status": "healthy",
            "database_size": db_size,
            "active_connections": conn_count,
            "tables": table_sizes,
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)[:500]}


@router.post("/cache/clear")
async def clear_cache(
    request: Request,
    current_user: User = Depends(require_role("admin")),
):
    """Clear the Redis cache."""
    redis = getattr(request.app.state, "redis", None)
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is not configured",
        )

    try:
        await redis.flushdb()
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)[:200]}",
        ) from e


@router.post("/db/vacuum")
async def vacuum_database(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Run VACUUM ANALYZE on key tables (non-blocking)."""
    tables = ["batches", "calculations", "audit_logs"]
    results = {}

    for table in tables:
        try:
            # VACUUM cannot run inside a transaction, so we use raw connection
            raw_conn = await db.get_raw_connection()
            await raw_conn.driver_connection.set_autocommit(True)
            await raw_conn.driver_connection.execute(f"VACUUM ANALYZE {table}")
            await raw_conn.driver_connection.set_autocommit(False)
            results[table] = "success"
        except Exception as e:
            results[table] = f"error: {str(e)[:100]}"

    return {"vacuum_results": results}


@router.get("/active-sessions")
async def active_sessions(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Get recent login sessions (last 24h)."""
    yesterday = datetime.now(timezone.utc) - timedelta(hours=24)

    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.action == "LOGIN",
            AuditLog.created_at >= yesterday,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )
    sessions = result.scalars().all()

    return {
        "sessions": [
            {
                "username": s.username,
                "tenant_id": s.tenant_id,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent[:100] if s.user_agent else None,
                "timestamp": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions
        ],
        "count": len(sessions),
    }
