"""Agent-side mirror of app.schemas.mc (Phase A V5)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "A.4"


class McInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["normal", "lognormal", "triangular", "uniform"]
    mean: float
    std: float = Field(..., ge=0.0)
    units: Optional[str] = Field(default=None, max_length=32)


class SobolIndices(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first_order: Dict[str, float]
    total: Dict[str, float]

    @model_validator(mode="after")
    def _check_index_bounds(self) -> "SobolIndices":
        for label, table in (("first_order", self.first_order), ("total", self.total)):
            for k, v in table.items():
                if not (-0.05 <= v <= 1.05):
                    raise ValueError(f"{label}[{k}]={v} outside [0, 1]")
        if set(self.first_order.keys()) != set(self.total.keys()):
            raise ValueError("first_order and total must cover the same keys")
        return self


class McDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_samples: int = Field(..., ge=1)
    effective_samples: int = Field(..., ge=0)
    seed: Optional[int] = Field(default=None, ge=0, le=2**32 - 1)
    distribution_kinds: Dict[str, str] = Field(default_factory=dict)
    computation_time_ms: float = Field(..., ge=0.0)
    convergence_check: bool = False


class McPropagateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inputs: Dict[str, McInput] = Field(..., min_length=1, max_length=64)
    target_func: Literal["ser", "sfi_score", "relay_final_state", "custom"]
    target_func_config: Dict[str, Any]
    n_samples: int = Field(default=10_000, ge=100, le=200_000)
    seed: Optional[int] = Field(default=None, ge=0, le=2**32 - 1)
    return_samples: bool = False
    compute_sobol: bool = False

    @model_validator(mode="after")
    def _check_target_config_nonempty(self) -> "McPropagateRequest":
        if not self.target_func_config:
            raise ValueError("target_func_config must not be empty")
        return self


class McPropagateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_mean: float
    target_std: float = Field(..., ge=0.0)
    ci_lower: float
    ci_upper: float
    samples: Optional[List[float]] = None
    sobol_indices: Optional[SobolIndices] = None
    diagnostics: McDiagnostics
    evidence_level: Literal["validated", "supported", "planned"]
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")

    @model_validator(mode="after")
    def _check_ci_order(self) -> "McPropagateResponse":
        if self.ci_lower > self.ci_upper:
            raise ValueError("ci_lower must be <= ci_upper")
        return self
