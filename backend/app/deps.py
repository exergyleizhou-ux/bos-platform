"""
BOS Pipeline v9.0 �� Dependencies

Shared FastAPI dependencies:
  - JWT token decoding & user extraction
  - Role-based access control (RBAC)
  - Tenant context injection (for RLS)
  - Pagination parameters
"""

from dataclasses import dataclass
from typing import List, Optional

from fastapi import Depends, HTTPException, Query, Request, status
from jose import JWTError, jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_async_session

settings = get_settings()

# Role hierarchy (higher index = more privilege)
ROLE_HIERARCHY = {
    "viewer": 0,
    "billing": 1,
    "operator": 2,
    "scientist": 3,
    "admin": 4,
}


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# JWT Decoding
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


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


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Current User
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


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


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Tenant Context (Row-Level Security)
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


async def set_tenant_context(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get current user AND set PostgreSQL RLS tenant context.

    This sets `app.current_tenant_id` on the session so that
    RLS policies automatically filter rows by tenant.
    """
    from app.models import User

    user = await get_current_user(request, db)

    # Set RLS context variable
    try:
        await db.execute(
            text(f"SET LOCAL app.current_tenant_id = '{user.tenant_id}'")
        )
    except Exception:
        pass  # Graceful fallback if RLS is not configured

    return user


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Role-Based Access Control
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def require_role(role: str):
    """Dependency that requires an exact role."""

    async def _check(
        request: Request,
        db: AsyncSession = Depends(get_async_session),
    ):
        user = await get_current_user(request, db)

        if user.role != role:
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
        user_level = ROLE_HIERARCHY.get(user.role, 0)

        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least '{minimum_role}' role. Your role: '{user.role}'.",
            )

        # Set RLS context
        try:
            await db.execute(
                text(f"SET LOCAL app.current_tenant_id = '{user.tenant_id}'")
            )
        except Exception:
            pass

        return user

    return _check


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Pagination
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


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
