"""
BOS Pipeline v9.0 — Digital Twin Schemas.

Contains both V9 stateful CRUD DTOs (DigitalTwinCreate / Update /
Response) and the Phase A V5-strict stateless ``/run`` contract
(see ``# Phase A`` banner below). PHASE_A_PLAN.md §2.5.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


# ════════════════════════════════════════════════════════════════════
# Phase A — V5 strict /api/v1/twin/run contract
# ════════════════════════════════════════════════════════════════════
#
# Names here intentionally match PHASE_A_PLAN.md §2.5. They live in
# this module rather than schemas/relay.py so callers of the stateless
# /run endpoint can ``from app.schemas.twin import TwinRunRequest``
# without dragging in relay-stage submodels.

SCHEMA_VERSION = "A.5"


class TwinState(BaseModel):
    """Twin state at a single instant. Used as initial + final state."""

    model_config = ConfigDict(extra="forbid")

    biomass_kg: float = Field(
        ..., ge=0.0, le=1e6,
        description="Biomass dry matter [kg].",
        examples=[0.5],
    )
    substrate_kg: float = Field(
        ..., ge=0.0, le=1e6,
        description="Substrate dry matter [kg].",
        examples=[10.0],
    )
    temperature_c: float = Field(
        ..., ge=-10.0, le=80.0,
        description="Bed temperature [°C].",
        examples=[28.0],
    )
    moisture_pct: float = Field(
        ..., ge=0.0, le=100.0,
        description="Bed moisture [% w/w].",
        examples=[70.0],
    )
    nitrogen_kg: float = Field(
        ..., ge=0.0, le=1e5,
        description="Nitrogen pool [kg].",
        examples=[0.05],
    )


class TwinConfig(BaseModel):
    """Kinetic parameters passed to digital_twin_engine.TwinParameters."""

    model_config = ConfigDict(extra="forbid")

    mu_max: float = Field(
        default=0.025, gt=0.0, le=10.0,
        description="Max specific growth rate [1/h].",
    )
    K_s: float = Field(
        default=5.0, gt=0.0, le=1e3,
        description="Half-saturation constant [kg DM].",
    )
    Y: float = Field(
        default=0.22, gt=0.0, le=1.0,
        description="Yield coefficient [kg biomass / kg substrate].",
    )
    k_death: float = Field(
        default=0.001, ge=0.0, le=1.0,
        description="Death rate [1/h].",
    )
    k_n: float = Field(
        default=0.02, ge=0.0, le=1.0,
        description="Nitrogen uptake coefficient.",
    )
    tau_T: float = Field(
        default=10.0, gt=0.0, le=1e4,
        description="Thermal time constant [h].",
    )
    tau_M: float = Field(
        default=20.0, gt=0.0, le=1e4,
        description="Moisture time constant [h].",
    )
    T_env: float = Field(
        default=25.0, ge=-10.0, le=80.0,
        description="Ambient temperature [°C].",
    )
    M_env: float = Field(
        default=60.0, ge=0.0, le=100.0,
        description="Ambient moisture [%].",
    )


class TwinInputStep(BaseModel):
    """Per-step control vector. Matches digital_twin_engine.predict_step
    inputs dict (feed_rate / ventilation / heating)."""

    model_config = ConfigDict(extra="forbid")

    dt_hours: float = Field(
        ..., gt=0.0, le=24.0,
        description="Integration step length [hours].",
        examples=[1.0],
    )
    feed_rate_kg_h: float = Field(
        default=0.0, ge=0.0, le=1e4,
        description="Substrate addition rate [kg DM / h].",
    )
    ventilation_m3_h: float = Field(
        default=0.0, ge=0.0, le=1e5,
        description="Air-flow [m³ / h].",
    )
    heating_kw: float = Field(
        default=0.0, ge=0.0, le=1e3,
        description="Heating power [kW].",
    )


class TwinObservation(BaseModel):
    """Per-step sensor observation for the EKF update path."""

    model_config = ConfigDict(extra="forbid")

    weight_kg: Optional[float] = Field(
        default=None, ge=0.0, le=1e6,
        description="Aggregate bed weight (biomass + substrate) [kg].",
    )
    temperature_c: Optional[float] = Field(
        default=None, ge=-10.0, le=80.0,
        description="Bed temperature sensor [°C].",
    )
    moisture_pct: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Bed moisture sensor [%].",
    )


class TwinSnapshot(BaseModel):
    """Single-step predicted state + per-step diagnostics."""

    model_config = ConfigDict(extra="forbid")

    step_index: int = Field(..., ge=0, le=10_000)
    cumulative_time_h: float = Field(..., ge=0.0)
    state: TwinState
    growth_rate_kg_h: Optional[float] = Field(
        default=None,
        description="Instantaneous growth rate dB/dt [kg/h].",
    )
    ser_instantaneous: Optional[float] = Field(
        default=None,
        description="Instantaneous SER (per-step view).",
    )


class InnovationStats(BaseModel):
    """Aggregate EKF innovation diagnostics across the run."""

    model_config = ConfigDict(extra="forbid")

    n_updates: int = Field(
        ..., ge=0,
        description="Count of EKF update steps applied.",
    )
    mean_abs_innovation: Dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Mean absolute innovation per observed channel"
            " (weight / temperature / moisture)."
        ),
    )
    rms_innovation: Dict[str, float] = Field(
        default_factory=dict,
        description="Root-mean-square innovation per observed channel.",
    )


class TwinRunRequest(BaseModel):
    """Phase A stateless digital-twin run — V5 strict.

    No DB persistence, no batch/twin record required. Initial state
    is supplied in the body and the engine produces a trajectory.
    """

    model_config = ConfigDict(extra="forbid")

    initial_state: TwinState
    config: TwinConfig = Field(
        default_factory=TwinConfig,
        description="Kinetic parameters; defaults match the V9 baseline.",
    )
    inputs: List[TwinInputStep] = Field(
        ..., min_length=1, max_length=10_000,
        description="Per-step control vector.",
    )
    observations: Optional[List[TwinObservation]] = Field(
        default=None,
        description=(
            "Optional per-step observations for EKF correction. When"
            " provided, MUST have the same length as ``inputs``."
        ),
    )
    enable_ekf: bool = Field(
        default=True,
        description=(
            "If True and observations present, run EKF update after each"
            " predict step. Ignored when observations is None."
        ),
    )
    species_code: str = Field(
        default="BSF_LARVA",
        min_length=1, max_length=64, pattern=r"^[A-Z0-9_\-]+$",
        description="Code from engine/core/species_db.",
    )

    @model_validator(mode="after")
    def _check_observation_length(self) -> "TwinRunRequest":
        if self.observations is not None and len(self.observations) != len(self.inputs):
            raise ValueError(
                f"observations length must match inputs length when"
                f" provided (got obs={len(self.observations)},"
                f" inputs={len(self.inputs)})."
            )
        return self


class TwinRunResponse(BaseModel):
    """Phase A stateless digital-twin response — V5 strict."""

    model_config = ConfigDict(extra="forbid")

    trajectory: List[TwinSnapshot] = Field(
        ..., min_length=1, max_length=10_000,
    )
    estimated_states: List[TwinState] = Field(
        ..., min_length=1, max_length=10_000,
        description="Post-EKF estimates (= predicted states when EKF off).",
    )
    final_state: TwinState
    innovation_stats: InnovationStats
    evidence_level: Literal["validated", "supported", "planned"]
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")

    @model_validator(mode="after")
    def _check_length_alignment(self) -> "TwinRunResponse":
        if len(self.trajectory) != len(self.estimated_states):
            raise ValueError(
                f"trajectory and estimated_states must have equal length"
                f" (got {len(self.trajectory)} vs {len(self.estimated_states)})."
            )
        return self
