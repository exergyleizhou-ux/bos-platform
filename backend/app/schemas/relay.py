"""Phase A — Relay simulation schemas.

Paper map: M1 (deconstruction) → M2 (assimilation) → M3 (stabilization).
Reference: PHASE_A_PLAN.md §2.3.

Composition pattern: thin schema layer over the existing
``digital_twin_engine`` / ``kinetics_engine`` / ``mass_balance``
modules. Reuses sub-models from sister schemas:
    - ``KDecayBand`` from ``app.schemas.sfi``
    - ``MonteCarloConfig`` from ``app.schemas.ser``
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.sfi import KDecayBand
from app.schemas.ser import MonteCarloConfig

SCHEMA_VERSION = "A.3"


# ════════════════════════════════════════════════════════════════════
# State / config sub-models
# ════════════════════════════════════════════════════════════════════


class TwinState(BaseModel):
    """Initial / final state of the digital twin."""

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
        ..., ge=-10.0, le=100.0,
        description="Bed temperature [°C].",
        examples=[28.0],
    )
    moisture_pct: float = Field(
        ..., ge=0.0, le=100.0,
        description="Bed moisture [% w/w].",
        examples=[70.0],
    )
    nitrogen_g: float = Field(
        ..., ge=0.0, le=1e6,
        description="Nitrogen pool [g].",
        examples=[50.0],
    )
    signal_activity_au: float = Field(
        default=0.0, ge=0.0, le=1e9,
        description=(
            "Signal-molecule activity [arbitrary units; paper BU/mL]."
            " Tracked through M2 to evaluate Eq.6 decay."
        ),
        examples=[100.0],
    )


class RelayConfig(BaseModel):
    """Relay timing + decay parameters (Eq.4–6)."""

    model_config = ConfigDict(extra="forbid")

    tau_m2_h: float = Field(
        ..., gt=0.0, le=720.0,
        description="M2 assimilation time constant [hours] (Eq.4).",
        examples=[24.0],
    )
    k_decay_band: Optional[KDecayBand] = Field(
        default=None,
        description=(
            "Uncertainty band for k_decay (Eq.6). Reused from SFI schema"
            " — see app.schemas.sfi.KDecayBand."
        ),
    )
    s0: float = Field(
        ..., gt=0.0, le=1e9,
        description="Initial signal activity (Eq.4 IC).",
        examples=[100.0],
    )
    s_min: float = Field(
        ..., ge=0.0, le=1e9,
        description="Minimum signal activity before relay-to-M3.",
        examples=[10.0],
    )
    tau_max_h: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=1e5,
        description=(
            "Eq.6 physical horizon tau_max = ln(s0/s_min)/k_decay [hours]."
            " Computed by the engine when omitted; passed-through when"
            " caller pre-computes."
        ),
    )

    @model_validator(mode="after")
    def _check_thresholds(self) -> "RelayConfig":
        if self.s_min >= self.s0:
            raise ValueError(
                f"RelayConfig requires s_min < s0 (received s_min={self.s_min},"
                f" s0={self.s0})."
            )
        return self


class TwinInputStep(BaseModel):
    """Per-step control vector for the twin trajectory."""

    model_config = ConfigDict(extra="forbid")

    step_index: int = Field(..., ge=0, le=10_000)
    dt_hours: float = Field(..., gt=0.0, le=24.0)
    control_inputs: Dict[str, float] = Field(
        ...,
        min_length=0,
        description=(
            "Control vector keys: feed_rate, ventilation, heating."
            " Values match the digital twin engine expectations."
        ),
    )


class ControlProfile(BaseModel):
    """Optional setpoint-driven control profile applied across all stages."""

    model_config = ConfigDict(extra="forbid")

    profile_type: Literal["constant", "ramp", "step", "custom"] = Field(
        ...,
        description="Shape of the setpoint profile.",
    )
    setpoints: Dict[str, float] = Field(
        ...,
        min_length=1,
        description="Per-axis setpoint targets.",
    )
    tolerance: float = Field(
        default=0.1, ge=0.0, le=1.0,
        description="Fractional tolerance band around each setpoint.",
    )


# ════════════════════════════════════════════════════════════════════
# Result sub-models
# ════════════════════════════════════════════════════════════════════


class BoundaryLedger(BaseModel):
    """Mass/N closure ledger for a single relay stage."""

    model_config = ConfigDict(extra="forbid")

    stage: Literal["M1", "M2", "M3"]
    mass_in_kg: float = Field(..., ge=0.0)
    mass_out_kg: float = Field(..., ge=0.0)
    mass_residual_kg: float = Field(
        ...,
        description=(
            "Closure residual [kg]. Should be near zero. Negative means"
            " more out than in (likely measurement/sim error)."
        ),
    )
    nitrogen_in_g: float = Field(..., ge=0.0)
    nitrogen_out_g: float = Field(..., ge=0.0)
    nitrogen_residual_g: float
    closure_pct: float = Field(
        ..., ge=0.0, le=200.0,
        description=(
            "Mass closure percentage from mass_balance.reconcile."
            " Ideal = 100. Below 95 raises a poor_boundary_closure warning."
        ),
    )


class TwinSnapshot(BaseModel):
    """Single time-step snapshot in the relay trajectory."""

    model_config = ConfigDict(extra="forbid")

    step_index: int = Field(..., ge=0, le=100_000)
    stage: Literal["M1", "M2", "M3"]
    cumulative_time_h: float = Field(..., ge=0.0)
    state: TwinState


class RelayHealth(BaseModel):
    """Aggregate health verdict for the whole relay simulation."""

    model_config = ConfigDict(extra="forbid")

    overall_status: Literal["nominal", "degraded", "failed"]
    stage_completion: Dict[Literal["M1", "M2", "M3"], float] = Field(
        ...,
        description=(
            "Per-stage completion fraction in [0, 1]. 1.0 means the stage"
            " ran to its scheduled end without abort. Partial values mean"
            " an internal stop (e.g. k_decay violation)."
        ),
    )
    sfi_check_passed_at_each_stage: Dict[Literal["M1", "M2", "M3"], bool]
    k_decay_violation_at_step: Optional[int] = Field(
        default=None, ge=0,
        description="First step index where Eq.6 horizon was exceeded, or None.",
    )


class Warning(BaseModel):
    """Operator-visible warning recorded during the simulation."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=64)
    severity: Literal["info", "warn", "error"]
    message: str = Field(..., max_length=512)
    step_index: Optional[int] = Field(default=None, ge=0)
    stage: Optional[Literal["M1", "M2", "M3"]] = None


# ════════════════════════════════════════════════════════════════════
# Top-level request / response
# ════════════════════════════════════════════════════════════════════


class RelaySimulateRequest(BaseModel):
    """Phase A relay simulation input — paper-strict per §2.3."""

    model_config = ConfigDict(extra="forbid")

    initial_state: TwinState = Field(
        ...,
        description="Initial biomass / substrate / T / M / N / signal state.",
    )
    relay_config: RelayConfig
    horizon_steps: int = Field(
        ..., ge=1, le=10_000,
        description="Number of dt-sized steps to simulate.",
    )
    dt_hours: float = Field(
        ..., gt=0.0, le=24.0,
        description="Integration step size [hours].",
    )
    species_code: str = Field(
        ..., min_length=1, max_length=64, pattern=r"^[A-Z0-9_\-]+$",
        description="Code from engine/core/species_db.",
        examples=["BSF_LARVA"],
    )
    monte_carlo: Optional[MonteCarloConfig] = Field(
        default=None,
        description="Optional MC propagation on final_ser.",
    )
    control_profile: Optional[ControlProfile] = Field(default=None)

    @model_validator(mode="after")
    def _check_sim_horizon_vs_tau_max(self) -> "RelaySimulateRequest":
        """Sanity check: simulation duration ≤ 5× Eq.6 horizon.

        The 5× multiplier was chosen so the validator stops nonsensical
        ultra-long simulations without blocking realistic k_decay
        violation scenarios. (3× was the original choice but it ruled
        out the very test cases the violation detector exists to catch.
        See A1.3 finding #2 — validator vs M2 violation parameter
        deadlock.)
        """
        sim_hours = self.horizon_steps * self.dt_hours
        tau_max = self.relay_config.tau_max_h
        if tau_max is None and self.relay_config.k_decay_band is not None:
            import math
            k_pt = self.relay_config.k_decay_band.point
            if self.relay_config.s_min > 0:
                tau_max = math.log(
                    self.relay_config.s0 / self.relay_config.s_min
                ) / k_pt
        if tau_max is not None and sim_hours > 5.0 * tau_max:
            raise ValueError(
                f"Simulation duration {sim_hours:.2f} h exceeds 5 * tau_max"
                f" ({5.0 * tau_max:.2f} h). Reduce horizon_steps or dt_hours,"
                f" or increase substrate buffer."
            )
        return self


class RelaySimulateResponse(BaseModel):
    """Phase A relay simulation response — paper-strict."""

    model_config = ConfigDict(extra="forbid")

    trajectory: List[TwinSnapshot] = Field(
        ..., min_length=1, max_length=100_000,
    )
    boundary_ledger: List[BoundaryLedger] = Field(
        ...,
        description="Exactly three entries: M1, M2, M3.",
    )
    relay_health: RelayHealth
    final_ser: float = Field(..., ge=0.0, le=1.0)
    final_ser_ci: Optional[Tuple[float, float]] = Field(
        default=None,
        description="MC 95% CI on final_ser if monte_carlo was requested.",
    )
    warnings: List[Warning] = Field(default_factory=list, max_length=200)
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    evidence_level: Literal["validated", "supported", "planned"]

    @model_validator(mode="after")
    def _check_three_stage_ledger(self) -> "RelaySimulateResponse":
        stages = [b.stage for b in self.boundary_ledger]
        if stages != ["M1", "M2", "M3"]:
            raise ValueError(
                f"boundary_ledger must have exactly M1, M2, M3 in order"
                f" (received {stages})."
            )
        if self.final_ser_ci is not None:
            lo, hi = self.final_ser_ci
            if lo > hi:
                raise ValueError("final_ser_ci lower must be <= upper.")
        return self
