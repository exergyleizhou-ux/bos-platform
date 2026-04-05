"""
BOS Pipeline v9.0 �� Webhooks Router

Manages outgoing webhook subscriptions for event-driven integrations.
Events:
  - batch.created / batch.updated / batch.archived
  - calculation.completed
  - alert.triggered (flight envelope alarm)
  - risk.critical (contaminant exceedance)
"""

import hashlib
import hmac
import json
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_role, set_tenant_context, get_pagination, PaginationParams
from app.models import User, Webhook
from app.schemas import PaginatedResponse

router = APIRouter()

SUPPORTED_EVENTS = [
    "batch.created",
    "batch.updated",
    "batch.archived",
    "calculation.completed",
    "alert.triggered",
    "risk.critical",
    "twin.state_updated",
]


class WebhookCreate(BaseModel):
    """Create a webhook subscription."""

    url: HttpUrl
    events: List[str] = Field(..., min_length=1)
    secret: Optional[str] = Field(None, min_length=16, max_length=256)
    description: Optional[str] = Field(None, max_length=500)
    is_active: bool = True
    headers: Optional[Dict[str, str]] = None  # Custom headers to include


class WebhookUpdate(BaseModel):
    """Update a webhook."""

    url: Optional[HttpUrl] = None
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


class WebhookResponse(BaseModel):
    """Webhook response."""

    id: int
    url: str
    events: List[str]
    is_active: bool
    description: Optional[str]
    created_at: Optional[str]
    last_triggered: Optional[str]
    failure_count: int = 0

    model_config = {"from_attributes": True}


@router.get("/events")
async def list_supported_events(
    current_user: User = Depends(set_tenant_context),
):
    """List all supported webhook events."""
    return {"events": SUPPORTED_EVENTS}


@router.get("", response_model=PaginatedResponse[WebhookResponse])
async def list_webhooks(
    pagination: PaginationParams = Depends(get_pagination),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """List webhook subscriptions for the current tenant."""
    query = select(Webhook).where(Webhook.tenant_id == current_user.tenant_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Webhook.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    hooks = result.scalars().all()

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    items = []
    for h in hooks:
        items.append(WebhookResponse(
            id=h.id,
            url=str(h.url),
            events=h.events or [],
            is_active=h.is_active,
            description=h.description,
            created_at=h.created_at.isoformat() if h.created_at else None,
            last_triggered=h.last_triggered.isoformat() if h.last_triggered else None,
            failure_count=h.failure_count or 0,
        ))

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new webhook subscription (admin only)."""
    # Validate events
    invalid_events = [e for e in body.events if e not in SUPPORTED_EVENTS]
    if invalid_events:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid events: {invalid_events}. Supported: {SUPPORTED_EVENTS}",
        )

    webhook = Webhook(
        url=str(body.url),
        events=body.events,
        secret=body.secret,
        description=body.description,
        is_active=body.is_active,
        headers=body.headers,
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    return {
        "id": webhook.id,
        "url": webhook.url,
        "events": webhook.events,
        "is_active": webhook.is_active,
        "message": "Webhook created successfully",
    }


@router.patch("/{webhook_id}")
async def update_webhook(
    webhook_id: int,
    body: WebhookUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Update a webhook subscription."""
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.tenant_id == current_user.tenant_id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    update_data = body.model_dump(exclude_unset=True)

    if "events" in update_data:
        invalid = [e for e in update_data["events"] if e not in SUPPORTED_EVENTS]
        if invalid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid events: {invalid}")

    for key, value in update_data.items():
        if key == "url":
            value = str(value)
        setattr(webhook, key, value)

    await db.commit()

    return {"message": "Webhook updated", "id": webhook_id}


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a webhook subscription."""
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.tenant_id == current_user.tenant_id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    await db.delete(webhook)
    await db.commit()

    return {"message": "Webhook deleted", "id": webhook_id}


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_session),
):
    """Send a test payload to the webhook."""
    result = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.tenant_id == current_user.tenant_id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    test_payload = {
        "event": "test.ping",
        "timestamp": time.time(),
        "tenant_id": current_user.tenant_id,
        "data": {"message": "This is a test webhook delivery from BOS Pipeline v9.0"},
    }

    # Sign payload
    signature = None
    if webhook.secret:
        payload_bytes = json.dumps(test_payload).encode("utf-8")
        signature = hmac.new(webhook.secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    return {
        "message": "Test payload generated (actual delivery via async worker)",
        "webhook_id": webhook_id,
        "url": webhook.url,
        "payload": test_payload,
        "signature": signature,
    }
