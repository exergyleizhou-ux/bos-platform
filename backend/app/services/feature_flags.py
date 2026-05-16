"""
Feature flag runtime helpers.

Database-backed tenant overrides are the durable source of truth.
Redis, when available, is treated as an optional cache layer.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import FeatureFlag

settings = get_settings()


def get_default_flags() -> dict[str, bool]:
    """Return static feature-flag defaults from app settings."""
    return {
        "monte_carlo": settings.FF_ENABLE_MONTE_CARLO,
        "digital_twin": settings.FF_ENABLE_DIGITAL_TWIN,
        "automl": settings.FF_ENABLE_AUTOML,
        "websocket": settings.FF_ENABLE_WEBSOCKET,
        "export_parquet": settings.FF_ENABLE_EXPORT_PARQUET,
        "billing": settings.FF_ENABLE_BILLING,
        "multi_language": settings.FF_ENABLE_MULTI_LANGUAGE,
        "dark_mode": settings.FF_ENABLE_DARK_MODE,
        "bos_code": settings.FF_ENABLE_BOS_CODE,
        "bos_guidance": settings.FF_ENABLE_BOS_GUIDANCE,
        "bos_portability_recommendation": settings.FF_ENABLE_BOS_PORTABILITY_RECOMMENDATION,
        "bos_audit_export": settings.FF_ENABLE_BOS_AUDIT_EXPORT,
        "bos_locality_release": settings.FF_ENABLE_BOS_LOCALITY_RELEASE,
        "bos_signal_compile": settings.FF_ENABLE_BOS_SIGNAL_COMPILE,
        "bos_true_boundary_ledger": settings.FF_ENABLE_BOS_TRUE_BOUNDARY_LEDGER,
        "bos_simulation_lab": settings.FF_ENABLE_BOS_SIMULATION_LAB,
    }


def get_flag_names() -> list[str]:
    return list(get_default_flags().keys())


def build_flag_cache_key(*, tenant_id: int, flag_name: str) -> str:
    return f"ff:{tenant_id}:{flag_name}"


def _normalize_override_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return None


def _normalize_tenant_overrides(raw_value: Any) -> dict[str, bool]:
    if not isinstance(raw_value, dict):
        return {}

    normalized: dict[str, bool] = {}
    for tenant_id, value in raw_value.items():
        parsed = _normalize_override_value(value)
        if parsed is not None:
            normalized[str(tenant_id)] = parsed
    return normalized


async def get_flag_record(db: AsyncSession, flag_name: str) -> FeatureFlag | None:
    result = await db.execute(select(FeatureFlag).where(FeatureFlag.name == flag_name))
    return result.scalar_one_or_none()


async def get_db_override(
    db: AsyncSession,
    *,
    flag_name: str,
    tenant_id: int,
) -> bool | None:
    record = await get_flag_record(db, flag_name)
    if not record:
        return None
    overrides = _normalize_tenant_overrides(record.tenant_overrides)
    return overrides.get(str(tenant_id))


async def set_db_override(
    db: AsyncSession,
    *,
    flag_name: str,
    tenant_id: int,
    enabled: bool,
) -> FeatureFlag:
    record = await get_flag_record(db, flag_name)
    default_flags = get_default_flags()

    if record is None:
        record = FeatureFlag(
            name=flag_name,
            enabled=default_flags.get(flag_name, False),
            tenant_overrides={str(tenant_id): enabled},
        )
        db.add(record)
    else:
        overrides = _normalize_tenant_overrides(record.tenant_overrides)
        overrides[str(tenant_id)] = enabled
        record.tenant_overrides = overrides

    await db.commit()
    await db.refresh(record)
    return record


async def clear_db_override(
    db: AsyncSession,
    *,
    flag_name: str,
    tenant_id: int,
) -> bool:
    record = await get_flag_record(db, flag_name)
    if not record:
        return False

    overrides = _normalize_tenant_overrides(record.tenant_overrides)
    removed = overrides.pop(str(tenant_id), None) is not None
    record.tenant_overrides = overrides or None

    await db.commit()
    await db.refresh(record)
    return removed


async def read_redis_override(
    redis: Any,
    *,
    flag_name: str,
    tenant_id: int,
) -> bool | None:
    if not redis:
        return None
    try:
        value = await redis.get(build_flag_cache_key(tenant_id=tenant_id, flag_name=flag_name))
    except Exception:
        return None

    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode()
    return _normalize_override_value(value)


async def sync_redis_override(
    redis: Any,
    *,
    flag_name: str,
    tenant_id: int,
    enabled: bool,
) -> bool:
    if not redis:
        return False
    try:
        await redis.set(
            build_flag_cache_key(tenant_id=tenant_id, flag_name=flag_name),
            "1" if enabled else "0",
            ex=86400 * 30,
        )
        return True
    except Exception:
        return False


async def clear_redis_override(
    redis: Any,
    *,
    flag_name: str,
    tenant_id: int,
) -> bool:
    if not redis:
        return False
    try:
        await redis.delete(build_flag_cache_key(tenant_id=tenant_id, flag_name=flag_name))
        return True
    except Exception:
        return False


async def get_effective_flag_value(
    db: AsyncSession,
    *,
    flag_name: str,
    tenant_id: int,
    redis: Any = None,
) -> tuple[bool, str]:
    defaults = get_default_flags()
    value = defaults[flag_name]
    sources = ["config"]

    db_override = await get_db_override(db, flag_name=flag_name, tenant_id=tenant_id)
    if db_override is not None:
        value = db_override
        sources.append("db")

    redis_override = await read_redis_override(redis, flag_name=flag_name, tenant_id=tenant_id)
    if redis_override is not None:
        value = redis_override
        if "redis" not in sources:
            sources.append("redis")

    return value, "+".join(sources)


async def get_effective_flags(
    db: AsyncSession,
    *,
    tenant_id: int,
    redis: Any = None,
) -> tuple[dict[str, bool], str]:
    flags = get_default_flags()
    applied_sources = {"config"}

    for flag_name in list(flags.keys()):
        db_override = await get_db_override(db, flag_name=flag_name, tenant_id=tenant_id)
        if db_override is not None:
            flags[flag_name] = db_override
            applied_sources.add("db")

    if redis:
        for flag_name in list(flags.keys()):
            redis_override = await read_redis_override(redis, flag_name=flag_name, tenant_id=tenant_id)
            if redis_override is not None:
                flags[flag_name] = redis_override
                applied_sources.add("redis")

    ordered_sources = [source for source in ["config", "db", "redis"] if source in applied_sources]
    return flags, "+".join(ordered_sources)
