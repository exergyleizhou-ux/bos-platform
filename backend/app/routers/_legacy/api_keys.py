"""
BOS Pipeline v9.0 API keys router.

Manages API key lifecycle for programmatic access.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_role, set_tenant_context
from app.models import APIKey, User

router = APIRouter()


class APIKeyCreate(BaseModel):
    """Create an API key."""

    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = Field(default=["read"], description="Allowed scopes: read, write, compute, admin")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """API key response (key shown only at creation)."""

    id: int
    name: str
    prefix: str
    scopes: List[str]
    is_active: bool
    created_at: Optional[str]
    expires_at: Optional[str]
    last_used_at: Optional[str]

    model_config = {"from_attributes": True}


VALID_SCOPES = {"read", "write", "compute", "admin"}


@router.get("")
async def list_api_keys(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """List API keys for the current tenant."""
    result = await db.execute(
        select(APIKey).where(APIKey.tenant_id == current_user.tenant_id).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()

    return {
        "keys": [
            APIKeyResponse(
                id=k.id,
                name=k.name,
                prefix=k.prefix,
                scopes=k.scopes or [],
                is_active=k.is_active,
                created_at=k.created_at.isoformat() if k.created_at else None,
                expires_at=k.expires_at.isoformat() if k.expires_at else None,
                last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
            )
            for k in keys
        ],
        "count": len(keys),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: APIKeyCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Create a new API key.

    The full key is returned only at creation time.
    """
    invalid = set(body.scopes) - VALID_SCOPES
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scopes: {invalid}. Valid: {VALID_SCOPES}",
        )

    raw_key = f"bos_{secrets.token_urlsafe(48)}"
    prefix = raw_key[:12]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    expires_at = None
    if body.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)

    api_key = APIKey(
        name=body.name,
        prefix=prefix,
        key_hash=key_hash,
        scopes=body.scopes,
        expires_at=expires_at,
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": raw_key,
        "prefix": prefix,
        "scopes": api_key.scopes,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "warning": "Save this key now. It will not be shown again.",
    }


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Revoke (deactivate) an API key."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id, APIKey.tenant_id == current_user.tenant_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    key.is_active = False
    await db.commit()
    return {"message": f"API key '{key.name}' has been revoked", "id": key_id}


@router.post("/{key_id}/rotate")
async def rotate_api_key(
    key_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Rotate an API key by revoking the old one and creating a new one."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id, APIKey.tenant_id == current_user.tenant_id))
    old_key = result.scalar_one_or_none()
    if not old_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    old_key.is_active = False

    raw_key = f"bos_{secrets.token_urlsafe(48)}"
    prefix = raw_key[:12]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    new_key = APIKey(
        name=f"{old_key.name} (rotated)",
        prefix=prefix,
        key_hash=key_hash,
        scopes=old_key.scopes,
        expires_at=old_key.expires_at,
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    return {
        "old_key_id": key_id,
        "old_key_status": "revoked",
        "new_key_id": new_key.id,
        "new_key": raw_key,
        "prefix": prefix,
        "warning": "Save this key now. It will not be shown again.",
    }
