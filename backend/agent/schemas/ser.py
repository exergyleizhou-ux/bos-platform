"""Agent-side mirror of app.schemas.ser (Phase A V5).

Drift policy: must stay in lockstep with app/schemas/ser.py.
See agent/tests/test_schema_parity.py for the enforcement test.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "A.1"


class DistSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["normal", "lognormal", "triangular", "uniform"]
    mean: float
    std: float = Field(..., ge=0.0)


class MonteCarloConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_samples: int = Field(ge=100, le=100_000, default=10_000)
    seed: Optional[int] = Field(default=None, ge=0, le=2**32 - 1)
    distributions: Dict[str, DistSpec]


class McSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_samples: int = Field(..., ge=0)
    effective_samples: Optional[int] = Field(default=None, ge=0)
    convergence_check: Optional[bool] = None
    divergences: Optional[int] = Field(default=None, ge=0)


class SerComputeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dm_in: float = Field(..., gt=0, le=1e6)
    dm_out: float = Field(..., gt=0, le=1e6)
    n_in: float = Field(..., ge=0, le=1e5)
    n_rec: float = Field(..., ge=0, le=1e5)
    d_prime: float = Field(..., ge=0.0, le=1.0)
    g_prime: float = Field(..., ge=0.0, le=1.0)
    species_code: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Z0-9_\-]+$")
    feedstock_code: Optional[str] = Field(default=None, max_length=64, pattern=r"^[A-Z0-9_\-]+$")
    monte_carlo: Optional[MonteCarloConfig] = None

    @model_validator(mode="after")
    def _check_mass_conservation(self) -> "SerComputeRequest":
        if self.dm_out > self.dm_in:
            raise ValueError("dm_out cannot exceed dm_in")
        if self.n_rec > self.n_in:
            raise ValueError("n_rec cannot exceed n_in")
        return self


class SerComputeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ser_point: float = Field(..., ge=0.0, le=1.0)
    ser_ci_lower: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ser_ci_upper: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ser_std: Optional[float] = Field(default=None, ge=0.0)
    delta_ser: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    monte_carlo: Optional[McSummary] = None
    evidence_level: Literal["validated", "supported", "planned"]
