"""Phase C C2 — /api/v1/causal/conformal_predict schemas.

Reference: _reports/PHASE_C_PLAN.md §2.2 + _reports/PHASE_C_C2_DESIGN.md.

C2 introduces distribution-free conformal prediction intervals as a
complement to:
- Phase B B.2 frequentist CI (LinearDML),
- Phase C C.1 Bayesian HDI (PyMC posterior).

Coverage guarantee: P(Y ∈ Ĉ(X)) ≥ 1 - α (marginal, finite-sample,
distribution-free). Mondrian variant gives conditional coverage
within each stratum.

Reserved method names raise ValidationError at the Pydantic layer.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.causal_common import (
    CausalData,
    CausalWarning,
    DagSpec,
    EvidenceLevel,
)


SCHEMA_VERSION = "C.2"


ConformalMethod = Literal[
    "split_conformal",      # Lei & Wasserman 2014
    "mondrian_conformal",   # stratified by stratum_variable
]


Mode = Literal["sync", "async_job"]

SYNC_MAX_INLINE_ROWS = 10_000


# ════════════════════════════════════════════════════════════════════
# Per-observation prediction (one entry per new_observations row)
# ════════════════════════════════════════════════════════════════════


class ConformalPrediction(BaseModel):
    """Single conformal prediction for one new observation."""

    model_config = ConfigDict(extra="forbid")

    point: float = Field(..., description="Point prediction μ̂(x).")
    interval_low: float = Field(..., description="Lower bound of "
                                "the (1-α) prediction interval.")
    interval_high: float = Field(..., description="Upper bound.")
    stratum: Optional[str] = Field(
        default=None,
        description=(
            "Stratum value for this observation (Mondrian only). "
            "None for marginal split-conformal."
        ),
    )

    @model_validator(mode="after")
    def _check_interval_order(self) -> "ConformalPrediction":
        if self.interval_low > self.interval_high:
            raise ValueError(
                f"interval_low ({self.interval_low}) > interval_high "
                f"({self.interval_high})"
            )
        return self


# ════════════════════════════════════════════════════════════════════
# Request
# ════════════════════════════════════════════════════════════════════


class ConformalPredictRequest(BaseModel):
    """Phase C C2 — Conformal prediction request.

    Splits the data into training (fit OLS regressor) + calibration
    (compute residual quantile). Predicts on optional
    new_observations with distribution-free (1-α) intervals.
    """

    model_config = ConfigDict(extra="forbid")

    dag: DagSpec
    treatment: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
    )
    outcome: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
    )
    data: CausalData

    method: ConformalMethod = Field(default="split_conformal")

    alpha: float = Field(
        default=0.05,
        gt=0.0,
        lt=1.0,
        description=(
            "Significance level. (1 - alpha) is the coverage "
            "guarantee. Default 0.05 → 95% prediction interval."
        ),
    )

    calibration_fraction: float = Field(
        default=0.3,
        gt=0.05,
        lt=0.95,
        description=(
            "Fraction of data held out for calibration "
            "(quantile estimation). Default 0.3."
        ),
    )

    stratum_variable: Optional[str] = Field(
        default=None,
        max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description=(
            "Stratum column name (required when method="
            "'mondrian_conformal'). Must be a column in data.inline."
        ),
    )

    new_observations: Optional[List[Dict[str, float]]] = Field(
        default=None,
        max_length=10_000,
        description=(
            "Optional list of new x rows to predict on. Each row "
            "must contain all backdoor variables + treatment "
            "(+ stratum_variable for Mondrian). When None, only "
            "calibration stats are returned."
        ),
    )

    random_seed: int = Field(
        default=42,
        ge=0,
        le=2**32 - 1,
    )

    n_min_per_stratum: int = Field(
        default=10,
        ge=1,
        le=10_000,
        description=(
            "Honest power floor for Mondrian. Strata with fewer "
            "than n_min cal samples fall back to the marginal "
            "quantile + a 'small_stratum' warning."
        ),
    )

    mode: Mode = Field(default="sync")

    @model_validator(mode="after")
    def _check_treatment_outcome_in_dag(self) -> "ConformalPredictRequest":
        names = {n.name for n in self.dag.nodes}
        if self.treatment not in names:
            raise ValueError(
                f"treatment {self.treatment!r} not in dag.nodes."
            )
        if self.outcome not in names:
            raise ValueError(
                f"outcome {self.outcome!r} not in dag.nodes."
            )
        if self.treatment == self.outcome:
            raise ValueError("treatment and outcome must differ.")
        return self

    @model_validator(mode="after")
    def _check_mondrian_has_stratum(self) -> "ConformalPredictRequest":
        if self.method == "mondrian_conformal":
            if self.stratum_variable is None:
                raise ValueError(
                    "method='mondrian_conformal' requires "
                    "stratum_variable to be set."
                )
        return self

    @model_validator(mode="after")
    def _check_sync_size_gate(self) -> "ConformalPredictRequest":
        if (
            self.mode == "sync"
            and self.data.inline is not None
            and len(self.data.inline) > SYNC_MAX_INLINE_ROWS
        ):
            raise ValueError(
                f"sync mode with {len(self.data.inline)} rows "
                f"> {SYNC_MAX_INLINE_ROWS}; use mode='async_job'."
            )
        return self


# ════════════════════════════════════════════════════════════════════
# Response
# ════════════════════════════════════════════════════════════════════


class ConformalPredictResponse(BaseModel):
    """Phase C C2 — conformal prediction response."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=SCHEMA_VERSION, frozen=True)

    # Per-observation predictions
    predictions: List[ConformalPrediction] = Field(
        default_factory=list,
        description=(
            "One entry per row in request.new_observations. "
            "Empty if no new_observations were supplied."
        ),
    )

    # Calibration set statistics
    coverage_guarantee: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="1 - alpha (the marginal coverage guarantee).",
    )
    n_calibration_samples: int = Field(..., ge=0)
    n_training_samples: int = Field(..., ge=0)

    # Marginal interval width (sanity check)
    marginal_quantile: float = Field(
        ...,
        ge=0.0,
        description=(
            "The (1-α) quantile of |residuals| on the marginal "
            "calibration set. The marginal split-conformal interval "
            "half-width."
        ),
    )

    median_interval_width: Optional[float] = Field(
        default=None,
        ge=0.0,
        description=(
            "Median width of the prediction intervals on the new "
            "observations. None if no new_observations supplied."
        ),
    )

    # Mondrian-specific
    strata_used: Optional[Dict[str, int]] = Field(
        default=None,
        description=(
            "Stratum value → number of calibration samples in "
            "that stratum. None for marginal split-conformal."
        ),
    )
    per_stratum_quantiles: Optional[Dict[str, float]] = Field(
        default=None,
        description=(
            "Stratum value → (1-α) quantile of |residuals| within "
            "that stratum. None for marginal split-conformal."
        ),
    )

    # Method + diagnostics
    method: ConformalMethod
    alpha: float
    random_seed: int
    evidence_level: EvidenceLevel
    warnings: List[CausalWarning] = Field(default_factory=list)

    # Metadata
    treatment: str
    outcome: str
    backdoor_variables: List[str] = Field(default_factory=list)
