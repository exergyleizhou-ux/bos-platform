"""
BOS Pipeline v9.0 �� Calculation Schemas
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class CalculationResponse(BaseModel):
    """Calculation response."""

    id: int
    batch_id: Optional[int] = None
    calc_type: str
    status: str
    inputs: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    ser_value: Optional[float] = None
    passed: Optional[bool] = None
    fail_codes: Optional[List[str]] = None
    mc_samples: Optional[int] = None
    duration_ms: Optional[float] = None
    engine_version: Optional[str] = None
    user_id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
