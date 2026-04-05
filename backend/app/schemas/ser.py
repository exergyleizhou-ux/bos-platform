"""
BOS Pipeline v9.0 �� SER Schemas
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SERRequest(BaseModel):
    """SER computation request."""

    batch_id: int
    dm_in: float = Field(..., gt=0, description="Dry matter input (kg)")
    dm_out: float = Field(..., ge=0, description="Dry matter output �� larvae (kg)")
    n_in: float = Field(default=0, ge=0, description="Nitrogen input (g)")
    n_larvae: float = Field(default=0, ge=0, description="Nitrogen in larvae (g)")
    n_frass: float = Field(default=0, ge=0, description="Nitrogen in frass (g)")
    ash_in: Optional[float] = Field(None, ge=0)
    ash_out: Optional[float] = Field(None, ge=0)
    fat_in: Optional[float] = Field(None, ge=0)
    fat_out: Optional[float] = Field(None, ge=0)


class SERResponse(BaseModel):
    """SER computation response."""

    ser_value: float
    eer: float
    mcr: float
    bcr: float
    nitrogen_balance: Optional[Dict[str, float] | float] = None
    ash_balance: Optional[Dict[str, float] | float] = None
    fat_balance: Optional[Dict[str, float] | float] = None
    passed: bool
    fail_codes: List[str]
    grade: str
    recommendations: List[str]
    batch_id: Optional[int] = None
    computed_at: Optional[datetime] = None
    computation_time_ms: Optional[float] = None
