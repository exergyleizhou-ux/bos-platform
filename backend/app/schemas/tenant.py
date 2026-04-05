"""
BOS Pipeline v9.0 �� Tenant Schemas
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    """Create tenant request."""

    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    plan: str = Field(default="free", pattern=r"^(free|starter|pro|enterprise)$")


class TenantUpdate(BaseModel):
    """Update tenant request (partial)."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    billing_email: Optional[str] = None
    settings: Optional[dict] = None
    is_active: Optional[bool] = None


class TenantResponse(BaseModel):
    """Tenant response."""

    id: int
    name: str
    slug: str
    plan: str
    is_active: bool
    max_users: int
    max_batches: int
    max_calculations: int
    billing_email: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
