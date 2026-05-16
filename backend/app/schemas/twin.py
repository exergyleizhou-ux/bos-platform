"""
BOS Pipeline v9.0 -Digital Twin Schemas
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DigitalTwinCreate(BaseModel):
    """Create digital twin request."""

    twin_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    species: str = Field(default="BSF", max_length=100)
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {
            "mu_max": 0.025,
            "K_s": 5.0,
            "Y": 0.22,
            "k_death": 0.001,
            "tau_T": 10.0,
            "tau_M": 20.0,
            "T_env": 25.0,
            "M_env": 60.0,
        },
    )


class DigitalTwinUpdate(BaseModel):
    """Update digital twin request (partial)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    config: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class DigitalTwinResponse(BaseModel):
    """Digital twin response."""

    id: int
    twin_id: str
    name: str
    species: str
    is_active: bool
    state: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    version: int = 0
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
