"""
BOS Pipeline v9.0 �� Feature Flags Router

Provides read access to current feature flag state.
Admin can override flags at runtime (stored in Redis).
"""

from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.config import get_settings
from app.deps import require_role, set_tenant_context
from app.models import User

router = APIRouter()
settings = get_settings()


def _get_all_flags() -> Dict[str, bool]:
    """Get all feature flags from settings."""
    return {
        "monte_carlo": settings.FF_ENABLE_MONTE_CARLO,
        "digital_twin": settings.FF_ENABLE_DIGITAL_TWIN,
        "automl": settings.FF_ENABLE_AUTOML,
        "websocket": settings.FF_ENABLE_WEBSOCKET,
        "export_parquet": settings.FF_ENABLE_EXPORT_PARQUET,
        "billing": settings.FF_ENABLE_BILLING,
        "multi_language": settings.FF_ENABLE_MULTI_LANGUAGE,
        "dark_mode": settings.FF_ENABLE_DARK_MODE,
    }


@router.get("")
async def get_feature_flags(
    current_user: User = Depends(set_tenant_context),
    request: Request = None,
):
    """Get all feature flags (including runtime overrides)."""
    flags = _get_all_flags()

    # Check Redis for runtime overrides
    redis = getattr(request.app.state, "redis", None) if request else None
    if redis:
        try:
            for flag_name in flags:
                override = await redis.get(f"ff:{current_user.tenant_id}:{flag_name}")
                if override is not None:
                    flags[flag_name] = override.decode() == "1"
        except Exception:
            pass  # Fallback to static flags

    return {"flags": flags, "source": "config+redis"}


@router.get("/{flag_name}")
async def get_feature_flag(
    flag_name: str,
    current_user: User = Depends(set_tenant_context),
    request: Request = None,
):
    """Get a specific feature flag value."""
    flags = _get_all_flags()

    if flag_name not in flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown flag: {flag_name}. Available: {list(flags.keys())}",
        )

    value = flags[flag_name]

    # Redis override
    redis = getattr(request.app.state, "redis", None) if request else None
    if redis:
        try:
            override = await redis.get(f"ff:{current_user.tenant_id}:{flag_name}")
            if override is not None:
                value = override.decode() == "1"
        except Exception:
            pass

    return {"flag": flag_name, "enabled": value}


class FlagOverride(BaseModel):
    """Feature flag override."""

    enabled: bool


@router.put("/{flag_name}")
async def set_feature_flag(
    flag_name: str,
    body: FlagOverride,
    current_user: User = Depends(require_role("admin")),
    request: Request = None,
):
    """Override a feature flag at runtime (admin only, stored in Redis)."""
    flags = _get_all_flags()

    if flag_name not in flags:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown flag: {flag_name}",
        )

    redis = getattr(request.app.state, "redis", None) if request else None
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is not available. Runtime overrides require Redis.",
        )

    try:
        key = f"ff:{current_user.tenant_id}:{flag_name}"
        await redis.set(key, "1" if body.enabled else "0", ex=86400 * 30)  # 30 day TTL
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set flag: {str(e)[:200]}",
        )

    return {
        "flag": flag_name,
        "enabled": body.enabled,
        "scope": f"tenant:{current_user.tenant_id}",
        "ttl_days": 30,
    }


@router.delete("/{flag_name}")
async def reset_feature_flag(
    flag_name: str,
    current_user: User = Depends(require_role("admin")),
    request: Request = None,
):
    """Remove a runtime override, reverting to the default config value."""
    redis = getattr(request.app.state, "redis", None) if request else None
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is not available",
        )

    key = f"ff:{current_user.tenant_id}:{flag_name}"
    await redis.delete(key)

    default_value = _get_all_flags().get(flag_name)

    return {
        "flag": flag_name,
        "override_removed": True,
        "default_value": default_value,
    }
