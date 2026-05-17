"""Phase A — SFI (Signal/Flight Integrity) schemas.

Paper map: Eq. 5–6 (operating envelope + risk conditions).
Reference: PHASE_A_PLAN.md §2.2.

Honest treatment of ``k_decay``: the paper states this constant is
*literature-estimated, not measured*. The schema therefore forces callers
to declare the source of the value (literature / fitted / measured) and
to provide an explicit uncertainty band — never a bare point.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Reused: the V5 Monte Carlo configuration lives in ser.py because it is
# shared across endpoints. Importing here keeps a single source of truth.
from app.schemas.ser import MonteCarloConfig

SCHEMA_VERSION = "A.2"


# ════════════════════════════════════════════════════════════════════
# Sub-models
# ════════════════════════════════════════════════════════════════════


class KDecayBand(BaseModel):
    """Uncertainty band for the first-order decay constant k_decay.

    Honest: callers MUST declare ``source`` so the API can downgrade
    ``evidence_level`` when the value is literature-prior rather than
    measured (paper §SFI honesty rule).
    """

    model_config = ConfigDict(extra="forbid")

    point: float = Field(
        ...,
        gt=0,
        le=10.0,
        description="Point estimate of k_decay [1/h] (Eq.6).",
        examples=[0.045],
    )
    low: float = Field(
        ...,
        gt=0,
        le=10.0,
        description="Lower bound of the uncertainty band [1/h].",
        examples=[0.030],
    )
    high: float = Field(
        ...,
        gt=0,
        le=10.0,
        description="Upper bound of the uncertainty band [1/h].",
        examples=[0.060],
    )
    source: Literal["literature", "fitted", "measured"] = Field(
        ...,
        description=(
            "Provenance of the value. Drives evidence_level downgrade:"
            " 'measured' -> validated, 'fitted' -> supported,"
            " 'literature' -> planned."
        ),
        examples=["literature"],
    )
    citation: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Optional reference (DOI, paper ID, internal dataset).",
    )

    @model_validator(mode="after")
    def _check_band_order(self) -> "KDecayBand":
        if not (self.low <= self.point <= self.high):
            raise ValueError(
                "KDecayBand requires low <= point <= high (received "
                f"low={self.low}, point={self.point}, high={self.high})."
            )
        return self


class SfiMeasurements(BaseModel):
    """Current sensor snapshot. Each axis bounded by physical limits."""

    model_config = ConfigDict(extra="forbid")

    temperature_c: float = Field(
        ..., ge=-10.0, le=80.0,
        description="Ambient temperature [°C].",
        examples=[28.0],
    )
    moisture_pct: float = Field(
        ..., ge=0.0, le=100.0,
        description="Substrate moisture [% w/w].",
        examples=[65.0],
    )
    density_kg_m3: float = Field(
        ..., gt=0.0, le=2000.0,
        description="Bulk density [kg/m³].",
        examples=[680.0],
    )
    ph: float = Field(
        ..., ge=0.0, le=14.0,
        description="Substrate pH.",
        examples=[6.8],
    )
    ammonia_ppm: float = Field(
        ..., ge=0.0, le=10_000.0,
        description="Ammonia in headspace [ppm v/v].",
        examples=[120.0],
    )
    oxygen_pct: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Atmospheric O2 [% v/v] (optional sensor).",
        examples=[19.5],
    )
    co2_pct: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Atmospheric CO2 [% v/v] (optional sensor).",
        examples=[2.5],
    )
    feed_rate_g_per_larva_day: Optional[float] = Field(
        default=None, ge=0.0, le=10.0,
        description="Feed rate [g DM / larva / day] (optional).",
    )


class SetpointProfile(BaseModel):
    """Desired operating envelope for the forecast-breach check."""

    model_config = ConfigDict(extra="forbid")

    target_state: Dict[str, float] = Field(
        ...,
        min_length=1,
        max_length=16,
        description=(
            "Per-axis target values. Keys must match SfiMeasurements fields"
            " (e.g. temperature_c, moisture_pct, ph)."
        ),
    )
    tolerance_pct: float = Field(
        default=10.0,
        ge=0.0,
        le=100.0,
        description="Tolerance as % of axis range; bracketed forecast band.",
    )


class AxisStatus(BaseModel):
    """Per-axis verdict returned to the caller."""

    model_config = ConfigDict(extra="forbid")

    axis: str = Field(..., min_length=1, max_length=64)
    value: float
    unit: str = Field(..., max_length=16)
    status: Literal["pass", "warn", "fail"]
    margin_to_breach: Optional[float] = Field(
        default=None,
        description=(
            "Absolute distance to the nearest envelope breach in axis units."
            " Negative means already over the boundary."
        ),
    )


class ForecastBreach(BaseModel):
    """Earliest predicted envelope breach within ``horizon_hours``."""

    model_config = ConfigDict(extra="forbid")

    earliest_breach_hour: float = Field(
        ..., ge=0.0,
        description="Hours from t0 until the predicted breach.",
    )
    axis: str = Field(..., min_length=1, max_length=64)
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confidence the breach occurs within horizon.",
    )


class Action(BaseModel):
    """Operator-facing remediation hint."""

    model_config = ConfigDict(extra="forbid")

    action_type: Literal[
        "cool_down", "heat_up",
        "irrigate", "ventilate",
        "ph_adjust",
        "feed_reduce", "feed_increase",
        "harvest_now", "rest_and_review",
        "horizon_exceeds_physical_limit",
    ] = Field(..., description="Discrete action category.")
    urgency: Literal["low", "medium", "high"] = Field(...)
    description: str = Field(..., max_length=512)


# ════════════════════════════════════════════════════════════════════
# Top-level request / response
# ════════════════════════════════════════════════════════════════════


class SfiCheckRequest(BaseModel):
    """Phase A SFI check input — paper-strict per §2.2."""

    model_config = ConfigDict(extra="forbid")

    species_code: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Z0-9_\-]+$",
        description="Code from engine/core/species_db.",
        examples=["BSF_LARVA"],
    )
    measurements: SfiMeasurements = Field(
        ...,
        description="Current sensor snapshot.",
    )
    setpoint_profile: Optional[SetpointProfile] = Field(
        default=None,
        description="If provided, enables forecast-breach computation.",
    )
    horizon_hours: int = Field(
        default=24, ge=1, le=720,
        description="Forward-projection horizon (1 h to 30 days).",
        examples=[24],
    )
    k_decay_band: Optional[KDecayBand] = Field(
        default=None,
        description=(
            "Uncertainty band for k_decay (Eq.6 input). Required to enable"
            " the physical-horizon check."
        ),
    )
    s0: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=1e6,
        description=(
            "Initial substrate pool [kg]. Combined with s_min + k_decay to"
            " evaluate Eq.6 tau_max = ln(s0/s_min)/k_decay."
        ),
    )
    s_min: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1e6,
        description="Minimum substrate threshold [kg].",
    )
    monte_carlo: Optional[MonteCarloConfig] = Field(
        default=None,
        description="Optional MC propagation on the composite score.",
    )

    @model_validator(mode="after")
    def _check_substrate_bounds(self) -> "SfiCheckRequest":
        if (self.s0 is None) != (self.s_min is None):
            raise ValueError("s0 and s_min must be provided together.")
        if self.s0 is not None and self.s_min is not None:
            if self.s_min >= self.s0:
                raise ValueError("s_min must be strictly less than s0.")
        return self


class SfiCheckResponse(BaseModel):
    """Phase A SFI check response — paper-strict."""

    model_config = ConfigDict(extra="forbid")

    sfi_pass: bool
    zone: Literal["safe", "caution", "danger", "out_of_envelope"]
    composite_score: float = Field(..., ge=0.0, le=1.0)
    per_axis: Dict[str, AxisStatus] = Field(
        ...,
        description="Keys are SfiMeasurements field names.",
    )
    forecast_breach: Optional[ForecastBreach] = Field(
        default=None,
        description="Earliest predicted envelope breach within horizon.",
    )
    recommended_actions: List[Action] = Field(
        default_factory=list, max_length=20,
    )
    evidence_level: Literal["validated", "supported", "planned"]
    k_decay_used: Optional[KDecayBand] = Field(
        default=None,
        description="Echo of the k_decay_band actually used (for audit).",
    )
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
