"""
BOS Pipeline v9.0 dependencies.

Shared FastAPI dependencies:
  - JWT token decoding and user extraction
  - Role-based access control (RBAC)
  - Tenant context injection (for RLS)
  - Pagination parameters
"""

import logging
import re
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Query, Request, status
from jose import JWTError, jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_async_session

settings = get_settings()
logger = logging.getLogger("bos.deps")

# Role hierarchy (higher index = more privilege)
FINAL_RELEASE_APPROVER_ROLE = "final_release_approver"
MODEL_GOVERNANCE_APPROVER_ROLE = "model_governance_approver"
EXTERNAL_RELEASE_SHARE_APPROVER_ROLE = "external_release_share_approver"
EXTERNAL_RELEASE_DELIVERY_APPROVER_ROLE = "external_release_delivery_approver"
EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE = "external_runtime_activation_approver"

FINAL_ACTION_APPROVER_ROLES = {
    FINAL_RELEASE_APPROVER_ROLE,
    MODEL_GOVERNANCE_APPROVER_ROLE,
    EXTERNAL_RELEASE_SHARE_APPROVER_ROLE,
    EXTERNAL_RELEASE_DELIVERY_APPROVER_ROLE,
}

ROLE_HIERARCHY = {
    "viewer": 0,
    "billing": 1,
    "operator": 2,
    FINAL_RELEASE_APPROVER_ROLE: 2,
    MODEL_GOVERNANCE_APPROVER_ROLE: 2,
    EXTERNAL_RELEASE_SHARE_APPROVER_ROLE: 2,
    EXTERNAL_RELEASE_DELIVERY_APPROVER_ROLE: 2,
    EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE: 2,
    "scientist": 3,
    "admin": 4,
}
ROLE_SPLIT_RE = re.compile(r"[\s,;|]+")


def parse_user_roles(role_value: str | None) -> set[str]:
    """Parse a stored role string into explicit role grants."""

    if not role_value:
        return set()
    return {role for role in ROLE_SPLIT_RE.split(role_value.strip()) if role}


def user_has_role(user_role: str | None, required_role: str) -> bool:
    return required_role in parse_user_roles(user_role)


def user_has_any_role(user_role: str | None, required_roles: set[str] | list[str] | tuple[str, ...]) -> bool:
    grants = parse_user_roles(user_role)
    return any(role in grants for role in required_roles)


async def resolve_user_roles(db: AsyncSession, user) -> set[str]:
    """Resolve legacy user.role grants plus DB-backed role assignments."""

    from app.models import UserRoleGrant

    roles = parse_user_roles(getattr(user, "role", None))
    result = await db.execute(
        select(UserRoleGrant.role).where(
            UserRoleGrant.user_id == user.id,
            UserRoleGrant.tenant_id == user.tenant_id,
            UserRoleGrant.is_active.is_(True),
        )
    )
    roles.update(role for role in result.scalars().all() if role)
    setattr(user, "_resolved_roles", roles)
    return roles


async def user_has_resolved_role(db: AsyncSession, user, required_role: str) -> bool:
    return required_role in await resolve_user_roles(db, user)


async def user_has_any_resolved_role(
    db: AsyncSession,
    user,
    required_roles: set[str] | list[str] | tuple[str, ...],
) -> bool:
    grants = await resolve_user_roles(db, user)
    return any(role in grants for role in required_roles)


def resolved_role_level(roles: set[str]) -> int:
    if not roles:
        return -1
    return max((ROLE_HIERARCHY.get(role, -1) for role in roles), default=-1)


def role_level(role_value: str | None) -> int:
    grants = parse_user_roles(role_value)
    if not grants:
        return -1
    return max((ROLE_HIERARCHY.get(role, -1) for role in grants), default=-1)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc!s}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _extract_token(request: Request) -> str:
    """Extract the Bearer token from the Authorization header."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_header[7:]


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Extract and validate the current user from the JWT token.

    Returns the User ORM object.
    """
    from app.models import User

    token = _extract_token(request)
    payload = decode_access_token(token)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Expected access token.",
        )

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return user


async def _apply_tenant_rls_context(*, db: AsyncSession, tenant_id: int) -> None:
    """Apply tenant context for PostgreSQL RLS-backed sessions."""
    bind = db.get_bind()
    if bind is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database bind is unavailable for tenant context.",
        )

    # SQLite-backed test and local setups do not support PostgreSQL session variables.
    if bind.dialect.name == "sqlite":
        return

    try:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
    except Exception as exc:
        logger.exception("Failed to establish tenant RLS context", extra={"tenant_id": tenant_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to establish tenant database context.",
        ) from exc


async def set_tenant_context(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get current user and set PostgreSQL RLS tenant context.

    This sets `app.current_tenant_id` on the session so that
    RLS policies automatically filter rows by tenant.
    """
    user = await get_current_user(request, db)
    await _apply_tenant_rls_context(db=db, tenant_id=user.tenant_id)
    return user


def require_role(role: str):
    """Dependency that requires an exact role."""

    async def _check(
        request: Request,
        db: AsyncSession = Depends(get_async_session),
    ):
        user = await get_current_user(request, db)

        roles = await resolve_user_roles(db, user)
        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires the '{role}' role. Your role: '{user.role}'.",
            )
        return user

    return _check


def require_minimum_role(minimum_role: str):
    """
    Dependency that requires at least a given role level.

    Role hierarchy: viewer < billing < operator < scientist < admin
    """
    min_level = ROLE_HIERARCHY.get(minimum_role, 0)

    async def _check(
        request: Request,
        db: AsyncSession = Depends(get_async_session),
    ):
        user = await get_current_user(request, db)
        user_level = resolved_role_level(await resolve_user_roles(db, user))

        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least '{minimum_role}' role. Your role: '{user.role}'.",
            )

        await _apply_tenant_rls_context(db=db, tenant_id=user.tenant_id)
        return user

    return _check


def require_any_role(*roles: str):
    """Dependency that requires at least one explicit role grant."""

    required_roles = set(roles)

    async def _check(
        request: Request,
        db: AsyncSession = Depends(get_async_session),
    ):
        user = await get_current_user(request, db)

        if not await user_has_any_resolved_role(db, user, required_roles):
            readable_roles = "', '".join(sorted(required_roles))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of '{readable_roles}' roles. Your role: '{user.role}'.",
            )

        await _apply_tenant_rls_context(db=db, tenant_id=user.tenant_id)
        return user

    return _check


@dataclass
class PaginationParams:
    """Parsed pagination parameters."""

    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def get_pagination(
    page: int = Query(1, ge=1, le=10000, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    """Parse and validate pagination query parameters."""
    return PaginationParams(page=page, page_size=page_size)
