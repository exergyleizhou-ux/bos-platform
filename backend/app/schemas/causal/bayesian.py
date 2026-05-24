"""Phase C C1 — /api/v1/causal/bayesian_estimate schemas.

Reference: _reports/PHASE_C_PLAN.md §2.1 + _reports/PHASE_C_C1_DESIGN.md.

C1 introduces Bayesian posterior estimation of the ATE as an
**alternative to** Phase B B2a's LinearDML point estimate. It does
**not replace** LinearDML; the two approaches are reported side-by-
side, satisfying the methodology paper (Paper 3)'s "dual Bayesian–
frequentist reporting" claim.

PyMC NUTS sampler with weakly informative priors (Gelman et al. 2008
style) by default. Operator can override priors via request
parameters when domain knowledge is available.

Seed locked at 42 to match Paper 1 reproducibility convention.

Reserved method family ``bayesian_dml`` is rejected with HTTP 422
``code='method_reserved'`` (mirrors B2a's ``method_family_reserved``
pattern).
"""

from __future__ import annotations

from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.causal_common import (
    CausalData,
    CausalWarning,
    DagSpec,
    EvidenceLevel,
    IdentifiedEstimandHandle,
)


SCHEMA_VERSION = "C.1"


# ════════════════════════════════════════════════════════════════════
# Method family taxonomy (C1 introduces 1 method; reserves 1 for
# future C-series releases).
# ════════════════════════════════════════════════════════════════════


BayesianMethod = Literal[
    # Phase C C1:
    "bayesian_backdoor",
    # Reserved (Phase C C2+):
    "bayesian_dml",
]


Mode = Literal["sync", "async_job"]


SYNC_MAX_INLINE_ROWS = 10_000
"""Sync-mode request with ``inline`` row count above this threshold
is 422-rejected at validation time. Use ``mode='async_job'`` for
larger datasets. Mirrors Phase B B2a estimate gate."""


# ════════════════════════════════════════════════════════════════════
# Diagnostics sub-model (PyMC posterior diagnostics)
# ════════════════════════════════════════════════════════════════════


class BayesianDiagnostics(BaseModel):
    """PyMC NUTS sampler diagnostics returned alongside posterior.

    Quality criteria (per C1 design §3.4):
    - r_hat < 1.01 → chains well-mixed
    - effective_sample_size > 400 → enough independent draws
    - n_divergent == 0 → no sampler pathologies
    """

    model_config = ConfigDict(extra="forbid")

    r_hat: float = Field(
        ...,
        ge=0.0,
        description=(
            "Gelman-Rubin convergence statistic. < 1.01 indicates "
            "chains have mixed. 1.05+ indicates problems."
        ),
    )
    effective_sample_size: float = Field(
        ...,
        ge=0.0,
        description=(
            "Effective number of independent posterior draws. "
            "Should be > 400 for stable HDI estimation."
        ),
    )
    n_divergent: int = Field(
        ...,
        ge=0,
        description=(
            "Number of divergent transitions during NUTS sampling. "
            "Should be 0; >0 indicates sampler pathology (often a "
            "prior misspecification or model identification issue)."
        ),
    )
    n_chains: int = Field(..., ge=1)
    n_draws_per_chain: int = Field(..., ge=1)
    n_tune: int = Field(..., ge=1)
    sampling_time_seconds: float = Field(..., ge=0.0)


# ════════════════════════════════════════════════════════════════════
# Request
# ════════════════════════════════════════════════════════════════════


class BayesianEstimateRequest(BaseModel):
    """Phase C C1 — Bayesian backdoor ATE estimation request.

    Wraps PyMC NUTS sampler with weakly informative priors over the
    treatment-effect coefficient (the parameter of interest). The
    posterior over this coefficient is interpreted as the ATE
    posterior.

    When ``precomputed_estimand`` is provided, the engine reuses the
    Phase B /identify endpoint's adjustment set verbatim (matching
    the precomputed_estimand pattern from B2a).
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
    method: BayesianMethod = Field(
        default="bayesian_backdoor",
        description=(
            "Bayesian estimator family. C1 ships ``bayesian_backdoor`` "
            "only; ``bayesian_dml`` is reserved for Phase C C2+ and "
            "rejected at runtime with HTTP 422 "
            "``code='method_reserved'``."
        ),
    )
    precomputed_estimand: Optional[IdentifiedEstimandHandle] = Field(
        default=None,
        description=(
            "Echo of /identify response's estimand_handle. When "
            "provided, /bayesian_estimate skips re-running "
            "identification and uses the recorded adjustment set "
            "verbatim."
        ),
    )

    # Sampler parameters
    n_chains: int = Field(
        default=2,
        ge=2,
        le=8,
        description=(
            "Number of NUTS chains. Default 2 (minimum for r_hat "
            "computation). Higher chains improve convergence "
            "detection but multiply runtime."
        ),
    )
    n_draws: int = Field(
        default=1000,
        ge=500,
        le=5000,
        description=(
            "Posterior draws per chain after tuning. Default 1000 "
            "→ 2000 total samples with n_chains=2."
        ),
    )
    n_tune: int = Field(
        default=1000,
        ge=500,
        le=5000,
        description=(
            "Tuning iterations per chain (discarded). Default 1000."
        ),
    )
    target_accept: float = Field(
        default=0.95,
        ge=0.8,
        le=0.99,
        description=(
            "NUTS step-size adaptation target. Higher → more "
            "conservative, fewer divergences, slower."
        ),
    )

    # Prior specification (weakly informative by default per Gelman 2008)
    prior_treatment_mean: float = Field(
        default=0.0,
        description=(
            "Prior mean on the treatment-effect coefficient. Default "
            "0 (null hypothesis as prior centre). Override when "
            "domain knowledge supports a non-null prior."
        ),
    )
    prior_treatment_sd: float = Field(
        default=1.0,
        gt=0,
        le=100,
        description=(
            "Prior standard deviation on the treatment-effect "
            "coefficient. Default 1.0 (weakly informative on "
            "standardised-scale data; widen if data un-standardised)."
        ),
    )
    prior_covariate_sd: float = Field(
        default=5.0,
        gt=0,
        le=100,
        description=(
            "Prior standard deviation on covariate coefficients. "
            "Default 5.0 (broad)."
        ),
    )
    prior_noise_sd: float = Field(
        default=1.0,
        gt=0,
        le=100,
        description=(
            "Prior scale on the HalfNormal noise distribution. "
            "Default 1.0."
        ),
    )

    # Seed (matches Paper 1 reproducibility convention)
    random_seed: int = Field(
        default=42,
        ge=0,
        le=2**32 - 1,
        description=(
            "PyMC sampler seed. Default 42 to match Paper 1 "
            "convention. Different seeds give different posterior "
            "samples but same posterior mean within ~5%."
        ),
    )

    # Honest-power floor (mirrors B2a estimate)
    n_min_per_stratum: int = Field(
        default=30,
        ge=1,
        le=10_000,
        description=(
            "Honest power floor. If effective per-stratum sample "
            "size falls below this, response is forced to "
            "evidence_level='planned' and a 'small_sample' warning "
            "is added — no error raised, because n=4 demonstrator "
            "experiments are valid."
        ),
    )

    confidence_level: float = Field(
        default=0.95,
        ge=0.5,
        le=0.999,
        description=(
            "HDI probability mass. 0.95 → 95% Highest Density "
            "Interval. Reported as ate_hdi_95 in response."
        ),
    )

    mode: Mode = Field(default="sync")

    @model_validator(mode="after")
    def _check_treatment_outcome_in_dag(self) -> "BayesianEstimateRequest":
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
    def _check_sync_size_gate(self) -> "BayesianEstimateRequest":
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
    def _check_precomputed_estimand_fingerprint(
        self,
    ) -> "BayesianEstimateRequest":
        if self.precomputed_estimand is not None:
            if (
                self.precomputed_estimand.dataset_fingerprint
                != self.data.fingerprint
            ):
                raise ValueError(
                    "precomputed_estimand.dataset_fingerprint does "
                    "not match data.fingerprint; the precomputed "
                    "estimand was identified on a different dataset."
                )
        return self


# ════════════════════════════════════════════════════════════════════
# Response
# ════════════════════════════════════════════════════════════════════


class BayesianEstimateResponse(BaseModel):
    """Phase C C1 — Bayesian backdoor ATE response.

    Returns posterior over the treatment-effect coefficient
    (interpreted as the ATE posterior under backdoor adjustment).
    Includes point summary (mean), uncertainty (HDI + SD), full
    posterior samples for downstream uncertainty propagation in
    Batch C4, and sampler diagnostics.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=SCHEMA_VERSION, frozen=True)

    # Point estimate (posterior mean; backward-compat field naming
    # mirrors B.2 estimate response where ``ate_point`` is the
    # primary scalar estimate)
    ate_point: float = Field(
        ...,
        description=(
            "Posterior mean of the ATE. Backward-compat with B.2 "
            "estimate response field naming."
        ),
    )
    ate_posterior_mean: float = Field(
        ...,
        description=(
            "Explicit posterior mean of the ATE. Equals ate_point. "
            "Provided for clarity in Bayesian contexts."
        ),
    )

    # Uncertainty
    ate_hdi_low: float = Field(
        ...,
        description=(
            "Lower bound of the 95% Highest Density Interval (HDI). "
            "When confidence_level != 0.95, this is the lower bound "
            "of the configured HDI."
        ),
    )
    ate_hdi_high: float = Field(
        ...,
        description=(
            "Upper bound of the HDI. ``ate_hdi_high - ate_hdi_low`` "
            "is the HDI width."
        ),
    )
    ate_posterior_sd: float = Field(
        ...,
        ge=0.0,
        description=(
            "Posterior standard deviation of the ATE. Bayesian "
            "analog of the frequentist SE."
        ),
    )

    # Posterior samples (for C4 uncertainty propagation)
    ate_posterior_samples: List[float] = Field(
        ...,
        description=(
            "Flat list of all posterior samples across chains. "
            "Length = n_chains * n_draws. Used by Batch C4 "
            "uncertainty pipeline."
        ),
    )

    # Diagnostics
    diagnostics: BayesianDiagnostics
    evidence_level: EvidenceLevel
    warnings: List[CausalWarning] = Field(default_factory=list)

    # Metadata
    method: BayesianMethod = Field(default="bayesian_backdoor")
    random_seed: int
    treatment: str
    outcome: str
    n_samples_observed: int = Field(
        ...,
        ge=0,
        description="Number of rows in the input dataset.",
    )
    backdoor_variables: List[str] = Field(
        default_factory=list,
        description=(
            "Adjustment set used for backdoor identification "
            "(either echo of precomputed_estimand or freshly "
            "derived from the DAG)."
        ),
    )

    # Provenance hash (matches Phase B audit-chain pattern)
    request_fingerprint: Optional[str] = Field(
        default=None,
        description=(
            "SHA-256 hex of the canonicalised request body. Used "
            "by downstream pipelines for cross-endpoint linkage."
        ),
    )
