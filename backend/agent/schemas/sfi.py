"""Agent-side mirror of app.schemas.sfi (Phase A V5)."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent.schemas.ser import MonteCarloConfig

SCHEMA_VERSION = "A.2"


class KDecayBand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    point: float = Field(..., gt=0, le=10.0)
    low: float = Field(..., gt=0, le=10.0)
    high: float = Field(..., gt=0, le=10.0)
    source: Literal["literature", "fitted", "measured"]
    citation: Optional[str] = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def _check_band_order(self) -> "KDecayBand":
        if not (self.low <= self.point <= self.high):
            raise ValueError("KDecayBand requires low <= point <= high")
        return self


class SfiMeasurements(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature_c: float = Field(..., ge=-10.0, le=80.0)
    moisture_pct: float = Field(..., ge=0.0, le=100.0)
    density_kg_m3: float = Field(..., gt=0.0, le=2000.0)
    ph: float = Field(..., ge=0.0, le=14.0)
    ammonia_ppm: float = Field(..., ge=0.0, le=10_000.0)
    oxygen_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    co2_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    feed_rate_g_per_larva_day: Optional[float] = Field(default=None, ge=0.0, le=10.0)


class SetpointProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_state: Dict[str, float] = Field(..., min_length=1, max_length=16)
    tolerance_pct: float = Field(default=10.0, ge=0.0, le=100.0)


class AxisStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    axis: str = Field(..., min_length=1, max_length=64)
    value: float
    unit: str = Field(..., max_length=16)
    status: Literal["pass", "warn", "fail"]
    margin_to_breach: Optional[float] = None


class ForecastBreach(BaseModel):
    model_config = ConfigDict(extra="forbid")
    earliest_breach_hour: float = Field(..., ge=0.0)
    axis: str = Field(..., min_length=1, max_length=64)
    confidence: float = Field(..., ge=0.0, le=1.0)


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_type: Literal[
        "cool_down", "heat_up",
        "irrigate", "ventilate",
        "ph_adjust",
        "feed_reduce", "feed_increase",
        "harvest_now", "rest_and_review",
        "horizon_exceeds_physical_limit",
    ]
    urgency: Literal["low", "medium", "high"]
    description: str = Field(..., max_length=512)


class SfiCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    species_code: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Z0-9_\-]+$")
    measurements: SfiMeasurements
    setpoint_profile: Optional[SetpointProfile] = None
    horizon_hours: int = Field(default=24, ge=1, le=720)
    k_decay_band: Optional[KDecayBand] = None
    s0: Optional[float] = Field(default=None, gt=0.0, le=1e6)
    s_min: Optional[float] = Field(default=None, ge=0.0, le=1e6)
    monte_carlo: Optional[MonteCarloConfig] = None

    @model_validator(mode="after")
    def _check_substrate_bounds(self) -> "SfiCheckRequest":
        if (self.s0 is None) != (self.s_min is None):
            raise ValueError("s0 and s_min must be provided together")
        if self.s0 is not None and self.s_min is not None:
            if self.s_min >= self.s0:
                raise ValueError("s_min must be strictly less than s0")
        return self


class SfiCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sfi_pass: bool
    zone: Literal["safe", "caution", "danger", "out_of_envelope"]
    composite_score: float = Field(..., ge=0.0, le=1.0)
    per_axis: Dict[str, AxisStatus]
    forecast_breach: Optional[ForecastBreach] = None
    recommended_actions: List[Action] = Field(default_factory=list, max_length=20)
    evidence_level: Literal["validated", "supported", "planned"]
    k_decay_used: Optional[KDecayBand] = None
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
