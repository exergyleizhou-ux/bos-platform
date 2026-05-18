"""Phase B — /api/v1/causal/estimate schemas.

Reference: PHASE_B_PLAN.md §2.2.

D9 = α: Phase B MVP implements LinearDML only. ``causal_forest_dml``
and ``x_learner`` are *reserved* enum values rejected at runtime by
422 (preserves a forward-compatible API surface without shipping the
estimators).
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.causal_common import (
    CausalData,
    CausalWarning,
    DagSpec,
    EstimateHandle,
    EvidenceLevel,
    IdentifiedEstimandHandle,
    MethodParams,
)


SCHEMA_VERSION = "B.2"


# Method family taxonomy. Reserved values are accepted at the schema
# layer but rejected at the engine layer with HTTP 422 +
# code='method_family_reserved'. This keeps the public OpenAPI surface
# forward-compatible across B-series releases.
MethodFamily = Literal[
    "linear_regression",
    "propensity_score",
    "dml",
    # Reserved (Phase-B-2):
    "causal_forest_dml",
    "x_learner",
]


TargetUnits = Literal["ate", "att", "atc"]

Mode = Literal["sync", "async_job"]


SYNC_MAX_INLINE_ROWS = 10_000
"""Sync-mode request with ``inline`` row count above this threshold is
422-rejected at validation time. Use ``mode='async_job'`` for larger
datasets."""


# ════════════════════════════════════════════════════════════════════
# Diagnostics sub-model
# ════════════════════════════════════════════════════════════════════


class EstimateDiagnostics(BaseModel):
    """Estimator diagnostics returned alongside the point estimate."""

    model_config = ConfigDict(extra="forbid")

    method: str = Field(..., max_length=64)
    n_samples: int = Field(..., ge=0)
    n_treated: Optional[int] = Field(default=None, ge=0)
    n_control: Optional[int] = Field(default=None, ge=0)
    n_continuous_covariates: int = Field(..., ge=0)
    n_discrete_covariates: int = Field(..., ge=0)
    cv_folds: Optional[int] = Field(default=None, ge=0)
    fit_time_ms: float = Field(..., ge=0.0)
    used_precomputed_estimand: bool = Field(default=False)


# ════════════════════════════════════════════════════════════════════
# Request
# ════════════════════════════════════════════════════════════════════


class CausalEstimateRequest(BaseModel):
    """Estimation phase input.

    Computes an ATE (or ATT / ATC) for the (treatment, outcome) pair
    under the supplied DAG. When ``precomputed_estimand`` is provided,
    the engine skips re-running identification and uses the
    pre-recorded adjustment set verbatim.
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
    method_family: MethodFamily
    method_params: MethodParams = Field(default_factory=MethodParams)
    precomputed_estimand: Optional[IdentifiedEstimandHandle] = Field(
        default=None,
        description=(
            "Echo of /identify response's estimand_handle. When "
            "provided, /estimate skips re-running identification and "
            "uses the recorded adjustment set verbatim. Removes the "
            "divergence risk where /identify says backdoor on {X,Z} "
            "and /estimate re-picks {X} only."
        ),
    )
    seed: Optional[int] = Field(default=None, ge=0, le=2**32 - 1)
    target_units: TargetUnits = Field(default="ate")
    confidence_level: float = Field(
        default=0.95,
        ge=0.5,
        le=0.999,
        description="Two-sided CI level (e.g. 0.95 → 95% CI).",
    )
    n_min_per_stratum: int = Field(
        default=30,
        ge=1,
        le=10_000,
        description=(
            "Honest power floor. If the effective per-stratum sample "
            "size falls below this number, the response is forced to "
            "evidence_level='planned' and a 'small_sample' warning is "
            "added — but no error is raised, because the paper's "
            "n=4 / arm experiment is itself a valid demonstrator."
        ),
    )
    mode: Mode = Field(default="sync")

    @model_validator(mode="after")
    def _check_treatment_outcome_in_dag(self) -> "CausalEstimateRequest":
        names = {n.name for n in self.dag.nodes}
        if self.treatment not in names:
            raise ValueError(
                f"treatment {self.treatment!r} is not declared in dag.nodes."
            )
        if self.outcome not in names:
            raise ValueError(
                f"outcome {self.outcome!r} is not declared in dag.nodes."
            )
        if self.treatment == self.outcome:
            raise ValueError("treatment and outcome must differ.")
        return self

    @model_validator(mode="after")
    def _check_sync_size_gate(self) -> "CausalEstimateRequest":
        if (
            self.mode == "sync"
            and self.data.inline is not None
            and len(self.data.inline) > SYNC_MAX_INLINE_ROWS
        ):
            raise ValueError(
                f"sync mode with inline row count "
                f"{len(self.data.inline)} > {SYNC_MAX_INLINE_ROWS}; "
                f"use mode='async_job' for larger datasets."
            )
        return self

    @model_validator(mode="after")
    def _check_method_params_align(self) -> "CausalEstimateRequest":
        # The MethodParams sub-block matching method_family should be
        # populated; the others should be None. This is permissive —
        # an empty MethodParams for any method_family is OK (engine
        # defaults apply).
        mapping = {
            "linear_regression": self.method_params.linear_regression,
            "propensity_score": self.method_params.propensity_score,
            "dml": self.method_params.dml,
        }
        for fam, params in mapping.items():
            if fam != self.method_family and params is not None:
                raise ValueError(
                    f"method_params.{fam} is set but method_family is "
                    f"{self.method_family!r}; clear unused method_params "
                    f"sub-blocks."
                )
        return self

    @model_validator(mode="after")
    def _check_precomputed_estimand_fingerprint(
        self,
    ) -> "CausalEstimateRequest":
        if self.precomputed_estimand is not None:
            if (
                self.precomputed_estimand.dataset_fingerprint
                != self.data.fingerprint
            ):
                raise ValueError(
                    "precomputed_estimand.dataset_fingerprint does not "
                    "match data.fingerprint; identification was issued "
                    "for a different dataset."
                )
        return self


# ════════════════════════════════════════════════════════════════════
# Response
# ════════════════════════════════════════════════════════════════════


class CausalEstimateResponse(BaseModel):
    """Estimation phase output."""

    model_config = ConfigDict(extra="forbid")

    point_estimate: float = Field(
        ...,
        description="The ATE / ATT / ATC value, depending on target_units.",
    )
    ci_lower: float
    ci_upper: float
    std_error: Optional[float] = Field(default=None, ge=0.0)
    method_used: str = Field(..., max_length=64)
    n_used_per_stratum: Dict[str, int] = Field(
        ...,
        description=(
            "Effective per-stratum sample sizes. Keys are stratum "
            "labels (e.g. feedstock codes); a single 'overall' key when "
            "no stratification was applied."
        ),
    )
    n_effective: int = Field(..., ge=0)
    heterogeneity_summary: Optional[Dict[str, float]] = Field(
        default=None,
        description=(
            "Optional CATE-style summary (mean, std, min, max of the "
            "estimated treatment effect across rows). Populated only "
            "for heterogeneous-effect estimators."
        ),
    )
    e_value_cheap: Optional[float] = Field(
        default=None,
        ge=1.0,
        description=(
            "Cheap E-value computed in-line during estimation "
            "(VanderWeele-Ding worst-case bias). For partial-linear "
            "sensitivity call /api/v1/causal/sensitivity."
        ),
    )
    estimate_handle: EstimateHandle = Field(
        ...,
        description=(
            "Pass this verbatim to /api/v1/causal/refute or "
            "/api/v1/causal/sensitivity to re-fit on the same data + "
            "DAG + method choice. Stateless."
        ),
    )
    diagnostics: EstimateDiagnostics
    evidence_level: EvidenceLevel
    warnings: List[CausalWarning] = Field(
        default_factory=list,
        max_length=20,
    )
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")

    @model_validator(mode="after")
    def _check_ci_bracketing(self) -> "CausalEstimateResponse":
        if not (self.ci_lower <= self.point_estimate <= self.ci_upper):
            raise ValueError(
                f"Response invariant violated: "
                f"ci_lower={self.ci_lower} <= "
                f"point_estimate={self.point_estimate} <= "
                f"ci_upper={self.ci_upper} required."
            )
        return self
