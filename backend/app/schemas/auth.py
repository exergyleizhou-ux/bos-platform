"""
BOS Pipeline v9.0 �� Authentication Schemas
"""

from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Login request body."""

    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Password change request."""

    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Must be ��8 chars with mixed case, digit, and special character",
    )
