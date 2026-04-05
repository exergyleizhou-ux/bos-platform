"""
BOS Pipeline v9.0 �� User Schemas
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Create user request."""

    username: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    role: str = Field(default="operator", pattern=r"^(admin|scientist|operator|viewer|billing)$")


class UserUpdate(BaseModel):
    """Update user request (partial)."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    role: Optional[str] = Field(None, pattern=r"^(admin|scientist|operator|viewer|billing)$")
    is_active: Optional[bool] = None
    preferences: Optional[Dict[str, Any]] = None


class UserResponse(BaseModel):
    """User list/create response."""

    id: int
    username: str
    full_name: str
    email: str
    role: str
    is_active: bool
    tenant_id: int
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserProfileResponse(UserResponse):
    """Detailed user profile response."""

    preferences: Optional[Dict[str, Any]] = None
    password_changed_at: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
