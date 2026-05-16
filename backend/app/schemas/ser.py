"""
BOS Pipeline v9.0 SER schemas.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SERRequest(BaseModel):
    """SER computation request."""

    batch_id: Optional[int] = None
    dm_in: float = Field(..., gt=0, description="Dry matter input (kg)")
    dm_out: float = Field(..., ge=0, description="Dry matter output in larvae (kg)")
    n_in: float = Field(default=0, ge=0, description="Nitrogen input (g)")
    n_larvae: float = Field(default=0, ge=0, description="Nitrogen in larvae (g)")
    n_frass: float = Field(default=0, ge=0, description="Nitrogen in frass (g)")
    ash_in: Optional[float] = Field(None, ge=0)
    ash_out: Optional[float] = Field(None, ge=0)
    fat_in: Optional[float] = Field(None, ge=0)
    fat_out: Optional[float] = Field(None, ge=0)
    measured_fields_present: Optional[List[str]] = Field(default=None)
    measured_channels: Optional[List[str]] = Field(default=None)
    closure_mode: str = Field(default="standard", max_length=50)
    evidence_mode: str = Field(default="standard", max_length=50)


class SERResponse(BaseModel):
    """SER computation response."""

    ser_value: float
    d_prime: Optional[float] = None
    g_prime: Optional[float] = None
    ser_system: float
    closure_residual: Optional[float] = None
    closure_penalty: Optional[float] = None
    evidence_penalty: Optional[float] = None
    metering_completeness: Optional[float] = None
    ser_confidence: Optional[float] = None
    release_ready: bool = False
    reason_codes: List[str] = Field(default_factory=list)
    pass_basis: List[str] = Field(default_factory=list)
    evidence_level: Optional[str] = None
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
    engine_version: str
    batch_id: Optional[int] = None
    computed_at: Optional[datetime] = None
    computation_time_ms: Optional[float] = None
