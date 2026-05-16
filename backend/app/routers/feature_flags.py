"""
BOS Pipeline v9.0 feature flags router.

Provides read access to current feature flag state.
Admins can override flags at runtime, with database fallback when Redis is unavailable.
"""

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_role, set_tenant_context
from app.models import User
from app.services.feature_flags import (
    clear_db_override,
    clear_redis_override,
    get_default_flags,
    get_effective_flag_value,
    get_effective_flags,
    get_flag_names,
    set_db_override,
    sync_redis_override,
)

router = APIRouter()


@router.get("")
async def get_feature_flags(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
    request: Request = None,
):
    """Get all feature flags including runtime overrides."""
    redis = getattr(request.app.state, "redis", None) if request else None
    flags, source = await get_effective_flags(db, tenant_id=current_user.tenant_id, redis=redis)
    return {"flags": flags, "source": source}


@router.get("/{flag_name}")
async def get_feature_flag(
    flag_name: str,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
    request: Request = None,
):
    """Get a specific feature flag value."""
    defaults = get_default_flags()
    if flag_name not in defaults:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown flag: {flag_name}. Available: {get_flag_names()}",
        )

    redis = getattr(request.app.state, "redis", None) if request else None
    value, source = await get_effective_flag_value(
        db,
        flag_name=flag_name,
        tenant_id=current_user.tenant_id,
        redis=redis,
    )
    return {"flag": flag_name, "enabled": value, "source": source}


class FlagOverride(BaseModel):
    """Feature flag override payload."""

    enabled: bool


@router.put("/{flag_name}")
async def set_feature_flag(
    flag_name: str,
    body: FlagOverride,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
    request: Request = None,
):
    """Override a feature flag at runtime."""
    defaults = get_default_flags()
    if flag_name not in defaults:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown flag: {flag_name}")

    record = await set_db_override(
        db,
        flag_name=flag_name,
        tenant_id=current_user.tenant_id,
        enabled=body.enabled,
    )

    redis = getattr(request.app.state, "redis", None) if request else None
    cache_synced = await sync_redis_override(
        redis,
        flag_name=flag_name,
        tenant_id=current_user.tenant_id,
        enabled=body.enabled,
    )

    return {
        "flag": flag_name,
        "enabled": body.enabled,
        "storage": "database",
        "cache_synced": cache_synced,
        "scope": f"tenant:{current_user.tenant_id}",
        "default_value": record.enabled,
    }


@router.delete("/{flag_name}")
async def reset_feature_flag(
    flag_name: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
    request: Request = None,
):
    """Remove a runtime override and revert to default config value."""
    defaults = get_default_flags()
    if flag_name not in defaults:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown flag: {flag_name}")

    override_removed = await clear_db_override(
        db,
        flag_name=flag_name,
        tenant_id=current_user.tenant_id,
    )

    redis = getattr(request.app.state, "redis", None) if request else None
    cache_cleared = await clear_redis_override(
        redis,
        flag_name=flag_name,
        tenant_id=current_user.tenant_id,
    )

    return {
        "flag": flag_name,
        "override_removed": override_removed,
        "cache_cleared": cache_cleared,
        "default_value": defaults.get(flag_name),
    }
