"""Agent-side mirror of app.schemas.relay (Phase A V5)."""

from __future__ import annotations

import math
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent.schemas.sfi import KDecayBand
from agent.schemas.ser import MonteCarloConfig

SCHEMA_VERSION = "A.3"


class TwinState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    biomass_kg: float = Field(..., ge=0.0, le=1e6)
    substrate_kg: float = Field(..., ge=0.0, le=1e6)
    temperature_c: float = Field(..., ge=-10.0, le=100.0)
    moisture_pct: float = Field(..., ge=0.0, le=100.0)
    nitrogen_g: float = Field(..., ge=0.0, le=1e6)
    signal_activity_au: float = Field(default=0.0, ge=0.0, le=1e9)


class RelayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tau_m2_h: float = Field(..., gt=0.0, le=720.0)
    k_decay_band: Optional[KDecayBand] = None
    s0: float = Field(..., gt=0.0, le=1e9)
    s_min: float = Field(..., ge=0.0, le=1e9)
    tau_max_h: Optional[float] = Field(default=None, gt=0.0, le=1e5)

    @model_validator(mode="after")
    def _check_thresholds(self) -> "RelayConfig":
        if self.s_min >= self.s0:
            raise ValueError("RelayConfig requires s_min < s0")
        return self


class TwinInputStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_index: int = Field(..., ge=0, le=10_000)
    dt_hours: float = Field(..., gt=0.0, le=24.0)
    control_inputs: Dict[str, float]


class ControlProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_type: Literal["constant", "ramp", "step", "custom"]
    setpoints: Dict[str, float] = Field(..., min_length=1)
    tolerance: float = Field(default=0.1, ge=0.0, le=1.0)


class BoundaryLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal["M1", "M2", "M3"]
    mass_in_kg: float = Field(..., ge=0.0)
    mass_out_kg: float = Field(..., ge=0.0)
    mass_residual_kg: float
    nitrogen_in_g: float = Field(..., ge=0.0)
    nitrogen_out_g: float = Field(..., ge=0.0)
    nitrogen_residual_g: float
    closure_pct: float = Field(..., ge=0.0, le=200.0)


class TwinSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_index: int = Field(..., ge=0, le=100_000)
    stage: Literal["M1", "M2", "M3"]
    cumulative_time_h: float = Field(..., ge=0.0)
    state: TwinState


class RelayHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overall_status: Literal["nominal", "degraded", "failed"]
    stage_completion: Dict[Literal["M1", "M2", "M3"], float]
    sfi_check_passed_at_each_stage: Dict[Literal["M1", "M2", "M3"], bool]
    k_decay_violation_at_step: Optional[int] = Field(default=None, ge=0)


class Warning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(..., min_length=1, max_length=64)
    severity: Literal["info", "warn", "error"]
    message: str = Field(..., max_length=512)
    step_index: Optional[int] = Field(default=None, ge=0)
    stage: Optional[Literal["M1", "M2", "M3"]] = None


class RelaySimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    initial_state: TwinState
    relay_config: RelayConfig
    horizon_steps: int = Field(..., ge=1, le=10_000)
    dt_hours: float = Field(..., gt=0.0, le=24.0)
    species_code: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Z0-9_\-]+$")
    monte_carlo: Optional[MonteCarloConfig] = None
    control_profile: Optional[ControlProfile] = None

    @model_validator(mode="after")
    def _check_sim_horizon_vs_tau_max(self) -> "RelaySimulateRequest":
        sim_hours = self.horizon_steps * self.dt_hours
        tau_max = self.relay_config.tau_max_h
        if tau_max is None and self.relay_config.k_decay_band is not None:
            k_pt = self.relay_config.k_decay_band.point
            if self.relay_config.s_min > 0:
                tau_max = math.log(
                    self.relay_config.s0 / self.relay_config.s_min
                ) / k_pt
        if tau_max is not None and sim_hours > 5.0 * tau_max:
            raise ValueError(
                f"Simulation duration {sim_hours:.2f} h exceeds 5 * tau_max"
                f" ({5.0 * tau_max:.2f} h)"
            )
        return self


class RelaySimulateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trajectory: List[TwinSnapshot] = Field(..., min_length=1, max_length=100_000)
    boundary_ledger: List[BoundaryLedger]
    relay_health: RelayHealth
    final_ser: float = Field(..., ge=0.0, le=1.0)
    final_ser_ci: Optional[Tuple[float, float]] = None
    warnings: List[Warning] = Field(default_factory=list, max_length=200)
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    evidence_level: Literal["validated", "supported", "planned"]

    @model_validator(mode="after")
    def _check_three_stage_ledger(self) -> "RelaySimulateResponse":
        stages = [b.stage for b in self.boundary_ledger]
        if stages != ["M1", "M2", "M3"]:
            raise ValueError("boundary_ledger must have exactly M1, M2, M3 in order")
        return self
