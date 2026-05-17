"""Agent-side mirror of app.schemas.twin (Phase A V5 /run only).

This mirror covers ONLY the stateless /api/v1/twin/run V5 contract.
The V9 CRUD DTOs (DigitalTwinCreate / Update / Response) are Core-only
and the agent never touches them.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "A.5"


class TwinState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    biomass_kg: float = Field(..., ge=0.0, le=1e6)
    substrate_kg: float = Field(..., ge=0.0, le=1e6)
    temperature_c: float = Field(..., ge=-10.0, le=80.0)
    moisture_pct: float = Field(..., ge=0.0, le=100.0)
    nitrogen_kg: float = Field(..., ge=0.0, le=1e5)


class TwinConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mu_max: float = Field(default=0.025, gt=0.0, le=10.0)
    K_s: float = Field(default=5.0, gt=0.0, le=1e3)
    Y: float = Field(default=0.22, gt=0.0, le=1.0)
    k_death: float = Field(default=0.001, ge=0.0, le=1.0)
    k_n: float = Field(default=0.02, ge=0.0, le=1.0)
    tau_T: float = Field(default=10.0, gt=0.0, le=1e4)
    tau_M: float = Field(default=20.0, gt=0.0, le=1e4)
    T_env: float = Field(default=25.0, ge=-10.0, le=80.0)
    M_env: float = Field(default=60.0, ge=0.0, le=100.0)


class TwinInputStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dt_hours: float = Field(..., gt=0.0, le=24.0)
    feed_rate_kg_h: float = Field(default=0.0, ge=0.0, le=1e4)
    ventilation_m3_h: float = Field(default=0.0, ge=0.0, le=1e5)
    heating_kw: float = Field(default=0.0, ge=0.0, le=1e3)


class TwinObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weight_kg: Optional[float] = Field(default=None, ge=0.0, le=1e6)
    temperature_c: Optional[float] = Field(default=None, ge=-10.0, le=80.0)
    moisture_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)


class TwinSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_index: int = Field(..., ge=0, le=10_000)
    cumulative_time_h: float = Field(..., ge=0.0)
    state: TwinState
    growth_rate_kg_h: Optional[float] = None
    ser_instantaneous: Optional[float] = None


class InnovationStats(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_updates: int = Field(..., ge=0)
    mean_abs_innovation: Dict[str, float] = Field(default_factory=dict)
    rms_innovation: Dict[str, float] = Field(default_factory=dict)


class TwinRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    initial_state: TwinState
    config: TwinConfig = Field(default_factory=TwinConfig)
    inputs: List[TwinInputStep] = Field(..., min_length=1, max_length=10_000)
    observations: Optional[List[TwinObservation]] = None
    enable_ekf: bool = True
    species_code: str = Field(
        default="BSF_LARVA",
        min_length=1, max_length=64, pattern=r"^[A-Z0-9_\-]+$",
    )

    @model_validator(mode="after")
    def _check_observation_length(self) -> "TwinRunRequest":
        if self.observations is not None and len(self.observations) != len(self.inputs):
            raise ValueError("observations length must match inputs length")
        return self


class TwinRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trajectory: List[TwinSnapshot] = Field(..., min_length=1, max_length=10_000)
    estimated_states: List[TwinState] = Field(..., min_length=1, max_length=10_000)
    final_state: TwinState
    innovation_stats: InnovationStats
    evidence_level: Literal["validated", "supported", "planned"]
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")

    @model_validator(mode="after")
    def _check_length_alignment(self) -> "TwinRunResponse":
        if len(self.trajectory) != len(self.estimated_states):
            raise ValueError("trajectory and estimated_states must have equal length")
        return self
