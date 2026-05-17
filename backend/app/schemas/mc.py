"""Phase A — Monte Carlo propagation schemas.

Paper map: Eq. 7 (generic Monte Carlo uncertainty propagation), reused
as a standalone tool.

Reference: PHASE_A_PLAN.md §2.4. This is the one Phase A schema that
intentionally retains a typed escape hatch (``target_func_config:
dict[str, Any]``) because each user-selectable target function carries
its own config shape — validation is delegated to the engine per-target.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "A.4"


# ════════════════════════════════════════════════════════════════════
# Sub-models
# ════════════════════════════════════════════════════════════════════


class McInput(BaseModel):
    """Per-variable distribution specification (Eq.7 input)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["normal", "lognormal", "triangular", "uniform"] = Field(
        ...,
        description="Sampling family.",
        examples=["normal"],
    )
    mean: float = Field(
        ...,
        description=(
            "Distribution centre. Interpretation per family:"
            " normal/lognormal/triangular → mean; uniform → centre of band."
        ),
        examples=[10.0],
    )
    std: float = Field(
        ...,
        ge=0.0,
        description="Standard deviation (≥ 0). Zero collapses to a constant.",
        examples=[0.5],
    )
    units: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Optional axis units for downstream provenance.",
        examples=["kg"],
    )


class SobolIndices(BaseModel):
    """First-order + total Sobol sensitivity indices."""

    model_config = ConfigDict(extra="forbid")

    first_order: Dict[str, float] = Field(
        ...,
        description="Per-variable first-order index S_i ∈ [0, 1].",
    )
    total: Dict[str, float] = Field(
        ...,
        description="Per-variable total index S_T,i ∈ [0, 1].",
    )

    @model_validator(mode="after")
    def _check_index_bounds(self) -> "SobolIndices":
        for label, table in (("first_order", self.first_order), ("total", self.total)):
            for k, v in table.items():
                if not (-0.05 <= v <= 1.05):
                    raise ValueError(
                        f"SobolIndices.{label}[{k!r}]={v} outside [0, 1]"
                        f" (small numerical slack ±0.05 allowed)."
                    )
        if set(self.first_order.keys()) != set(self.total.keys()):
            raise ValueError(
                "SobolIndices.first_order and .total must cover the same keys."
            )
        return self


class McDiagnostics(BaseModel):
    """Estimator diagnostics for the propagation run."""

    model_config = ConfigDict(extra="forbid")

    n_samples: int = Field(..., ge=1)
    effective_samples: int = Field(
        ...,
        ge=0,
        description="Samples surviving filtering / validity checks.",
    )
    seed: Optional[int] = Field(default=None, ge=0, le=2**32 - 1)
    distribution_kinds: Dict[str, str] = Field(
        default_factory=dict,
        description="Per-input distribution family used (echo).",
    )
    computation_time_ms: float = Field(..., ge=0.0)
    convergence_check: bool = Field(
        default=False,
        description=(
            "Engine-defined cheap convergence proxy (e.g. CI width vs"
            " /sqrt(n) decay). False does not imply non-convergence,"
            " only that the proxy was not run."
        ),
    )


# ════════════════════════════════════════════════════════════════════
# Top-level request / response
# ════════════════════════════════════════════════════════════════════


class McPropagateRequest(BaseModel):
    """Phase A Monte Carlo propagation input — paper-strict per §2.4."""

    model_config = ConfigDict(extra="forbid")

    inputs: Dict[str, McInput] = Field(
        ...,
        min_length=1,
        max_length=64,
        description=(
            "Per-variable distribution spec; keys are the target"
            " function's input variable names."
        ),
    )
    target_func: Literal[
        "ser", "sfi_score", "relay_final_state", "custom"
    ] = Field(
        ...,
        description="Which downstream BOS compute to propagate through.",
        examples=["ser"],
    )
    target_func_config: Dict[str, Any] = Field(
        ...,
        description=(
            "Target-specific config — schema is per-target and validated by"
            " the engine. This is the single Phase A loose-typed escape hatch."
        ),
    )
    n_samples: int = Field(
        default=10_000,
        ge=100,
        le=200_000,
        description="MC sample count. Eq.7 estimator variance scales 1/√N.",
    )
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        le=2**32 - 1,
        description="PRNG seed for reproducibility.",
    )
    return_samples: bool = Field(
        default=False,
        description="If True, response includes raw sample array (can be large).",
    )
    compute_sobol: bool = Field(
        default=False,
        description="If True, compute first-order + total Sobol indices.",
    )

    @model_validator(mode="after")
    def _check_target_config_nonempty(self) -> "McPropagateRequest":
        if not self.target_func_config:
            raise ValueError(
                f"target_func_config must not be empty for target_func={self.target_func!r}."
            )
        return self


class McPropagateResponse(BaseModel):
    """Phase A Monte Carlo propagation response — paper-strict."""

    model_config = ConfigDict(extra="forbid")

    target_mean: float
    target_std: float = Field(..., ge=0.0)
    ci_lower: float
    ci_upper: float
    samples: Optional[List[float]] = Field(
        default=None,
        description="Raw sample array; returned only when return_samples=True.",
    )
    sobol_indices: Optional[SobolIndices] = Field(
        default=None,
        description="Returned only when compute_sobol=True.",
    )
    diagnostics: McDiagnostics
    evidence_level: Literal["validated", "supported", "planned"]
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")

    @model_validator(mode="after")
    def _check_ci_order(self) -> "McPropagateResponse":
        if self.ci_lower > self.ci_upper:
            raise ValueError(
                f"ci_lower={self.ci_lower} must be <= ci_upper={self.ci_upper}."
            )
        return self
