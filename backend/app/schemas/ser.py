"""
BOS Pipeline v9.0 SER schemas.

This module hosts both the V9 (legacy, persisted) and the V5 (Phase A,
stateless paper-strict) schemas. The V5 classes are appended at the
bottom of this file.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SERRequest(BaseModel):
    """SER computation request."""

    batch_id: Optional[int] = None
    dm_in: float = Field(..., gt=0, description="Dry matter input (kg)")
    dm_out: float = Field(..., ge=0, description="Dry matter output in larvae (kg)")
    n_in: float = Field(default=0, ge=0, description="Nitrogen input (g)")
    n_larvae: float = Field(default=0, ge=0, description="Nitrogen in larvae (g)")
    n_frass: float = Field(default=0, ge=0, description="Nitrogen in frass (g)")
    ash_in: Optional[float] = Field(None, ge=0)
    ash_out: Optional[float] = Field(None, ge=0)
    fat_in: Optional[float] = Field(None, ge=0)
    fat_out: Optional[float] = Field(None, ge=0)
    measured_fields_present: Optional[List[str]] = Field(default=None)
    measured_channels: Optional[List[str]] = Field(default=None)
    closure_mode: str = Field(default="standard", max_length=50)
    evidence_mode: str = Field(default="standard", max_length=50)


class SERResponse(BaseModel):
    """SER computation response."""

    ser_value: float
    d_prime: Optional[float] = None
    g_prime: Optional[float] = None
    ser_system: float
    closure_residual: Optional[float] = None
    closure_penalty: Optional[float] = None
    evidence_penalty: Optional[float] = None
    metering_completeness: Optional[float] = None
    ser_confidence: Optional[float] = None
    release_ready: bool = False
    reason_codes: List[str] = Field(default_factory=list)
    pass_basis: List[str] = Field(default_factory=list)
    evidence_level: Optional[str] = None
    eer: float
    mcr: float
    bcr: float
    nitrogen_balance: Optional[Dict[str, float] | float] = None
    ash_balance: Optional[Dict[str, float] | float] = None
    fat_balance: Optional[Dict[str, float] | float] = None
    passed: bool
    fail_codes: List[str]
    grade: str
    recommendations: List[str]
    engine_version: str
    batch_id: Optional[int] = None
    computed_at: Optional[datetime] = None
    computation_time_ms: Optional[float] = None


# ════════════════════════════════════════════════════════════════════
# Phase A (V5) — paper-strict, stateless SER contract.
# Reference: PHASE_A_PLAN.md §2.1.
# Schema version constant is read by tests/architecture/test_schema_parity.py.
# ════════════════════════════════════════════════════════════════════

SCHEMA_VERSION = "A.1"


class DistSpec(BaseModel):
    """Per-field uncertainty distribution spec for Monte Carlo propagation.

    The engine maps these to ``app.engine.core.monte_carlo_engine.MCInput``.
    For Phase A the supported distributions are the same set the engine
    already implements.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["normal", "lognormal", "triangular", "uniform"] = Field(
        ...,
        description="Distribution family (paper Eq.7 inputs).",
        examples=["normal"],
    )
    mean: float = Field(
        ...,
        description="Distribution mean.",
        examples=[120.0],
    )
    std: float = Field(
        ...,
        ge=0.0,
        description="Standard deviation (or scale-equivalent).",
        examples=[5.0],
    )


class MonteCarloConfig(BaseModel):
    """MC propagation config; omit on the request to get deterministic only."""

    model_config = ConfigDict(extra="forbid")

    n_samples: int = Field(
        default=10_000,
        ge=100,
        le=100_000,
        description=(
            "Number of MC samples. Eq.7 estimator variance scales 1/sqrt(N)."
        ),
        examples=[10_000],
    )
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        le=2**32 - 1,
        description="PRNG seed for reproducibility.",
        examples=[42],
    )
    distributions: Dict[str, DistSpec] = Field(
        ...,
        description=(
            "Per-field uncertainty spec. Keys must be SerComputeRequest field"
            " names (dm_in, dm_out, n_in, n_rec)."
        ),
    )


class McSummary(BaseModel):
    """Diagnostics returned when monte_carlo was requested."""

    model_config = ConfigDict(extra="forbid")

    n_samples: int = Field(..., ge=0)
    ess: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Effective sample size (None when not computed).",
    )
    divergences: Optional[int] = Field(default=None, ge=0)


class SerComputeRequest(BaseModel):
    """Phase A SER compute input — paper-strict per §2.1 of PHASE_A_PLAN."""

    model_config = ConfigDict(extra="forbid")

    # Mass balance inputs (kg of dry matter). Eq.1 numerator/denominator.
    dm_in: float = Field(
        ...,
        gt=0,
        le=1e6,
        description="Input dry matter [kg]. Eq.1 denominator.",
        examples=[120.0],
    )
    dm_out: float = Field(
        ...,
        gt=0,
        le=1e6,
        description="Recovered dry matter [kg]. Must be <= dm_in (validator).",
        examples=[36.0],
    )

    # Nitrogen recovery. Eq.2 ratio bounded by N conservation.
    n_in: float = Field(
        ...,
        ge=0,
        le=1e5,
        description="Input N [kg].",
        examples=[2.8],
    )
    n_rec: float = Field(
        ...,
        ge=0,
        le=1e5,
        description="Recovered N [kg]. Must be <= n_in (validator).",
        examples=[0.91],
    )

    # Deconstruction / growth coefficients. Eq.3 normalized to [0, 1].
    d_prime: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized deconstruction rate D' in [0,1] (paper Eq.3).",
        examples=[0.72],
    )
    g_prime: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized growth rate G' in [0,1] (paper Eq.3).",
        examples=[0.65],
    )

    # Species + feedstock for sanity bounds (must exist in core data tables).
    species_code: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Z0-9_\-]+$",
        description="Code from engine/core/species_db.",
        examples=["BSF_LARVA"],
    )
    feedstock_code: Optional[str] = Field(
        default=None,
        max_length=64,
        pattern=r"^[A-Z0-9_\-]+$",
        description="Optional feedstock code from engine/core/feedstock_db.",
        examples=["FOOD_WASTE_MIXED"],
    )

    # Optional MC config (omit → deterministic only). Eq.7 propagation.
    monte_carlo: Optional[MonteCarloConfig] = Field(
        default=None,
        description="Omit for deterministic-only result.",
    )

    @model_validator(mode="after")
    def _check_mass_conservation(self) -> "SerComputeRequest":
        if self.dm_out > self.dm_in:
            raise ValueError("dm_out cannot exceed dm_in (mass conservation).")
        if self.n_rec > self.n_in:
            raise ValueError("n_rec cannot exceed n_in (N conservation).")
        return self


class SerComputeResponse(BaseModel):
    """Phase A SER compute response — paper-strict."""

    model_config = ConfigDict(extra="forbid")

    ser_point: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Deterministic SER in [0,1] (Eq.1).",
    )
    ser_ci_lower: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="MC lower 95% CI bound; None if MC not run.",
    )
    ser_ci_upper: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="MC upper 95% CI bound; None if MC not run.",
    )
    ser_std: Optional[float] = Field(default=None, ge=0.0)
    delta_ser: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="SER delta vs baseline; positive = improvement.",
    )
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    monte_carlo: Optional[McSummary] = None
    evidence_level: Literal["validated", "supported", "planned"] = Field(
        ...,
        description="Evidence tier for the result (per BOS evidence policy).",
    )

    @model_validator(mode="after")
    def _check_ci_order(self) -> "SerComputeResponse":
        if (
            self.ser_ci_lower is not None
            and self.ser_ci_upper is not None
            and self.ser_ci_lower > self.ser_ci_upper
        ):
            raise ValueError("ser_ci_lower must be <= ser_ci_upper.")
        return self
