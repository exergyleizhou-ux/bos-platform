"""
BOS Pipeline v9.0 �� Monte Carlo Simulation Schemas
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MonteCarloRequest(BaseModel):
    """Monte Carlo simulation request."""

    batch_id: int
    n_samples: int = Field(default=10000, ge=100, le=1_000_000)
    dm_in_mean: float = Field(..., gt=0)
    dm_in_std: float = Field(default=0.5, ge=0)
    dm_out_mean: float = Field(..., ge=0)
    dm_out_std: float = Field(default=0.3, ge=0)
    seed: Optional[int] = None


class MonteCarloResponse(BaseModel):
    """Monte Carlo simulation response."""

    n_samples: int
    ser_mean: float
    ser_std: float
    ser_median: float
    ser_ci_lower: float
    ser_ci_upper: float
    percentiles: Dict[str, float]
    pass_probability: float
    histogram_bins: List[float]
    histogram_counts: List[int]
    computation_time_ms: float
