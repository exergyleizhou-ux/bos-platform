"""Phase C C4 — /api/v1/causal/uncertainty_pipeline schemas.

Reference: _reports/PHASE_C_PLAN.md §2.4.

C4 composes end-to-end uncertainty from input posterior samples
(D', G', optionally κ-mediation proportion) through the SER
geometric-mean aggregator, propagating credibility bands all the
way to the final SER. This is the Paper 1 §3.6 Monte Carlo
propagation (n=2×10^5 draws) re-cast as a typed REST surface that
can be wired into the operator agent.

The engine is **deterministic given input posterior samples**.
The "uncertainty" lives entirely in the input distributions
(typically from /bayesian_estimate for D' and G' separately, or
from operator-supplied posterior_samples drawn from any source).

Output is a posterior over SER:
- final_ser_point (posterior mean)
- final_ser_credibility_band (alpha/2, median, 1-alpha/2 quantiles)
- final_ser_posterior_samples (full chain for downstream use)
- proportion_mediated_band (when κ samples supplied)

This batch does NOT introduce new Bayesian/Conformal estimation;
it composes existing posteriors. The operator is responsible for
running /bayesian_estimate (C1) on each component first.
"""

from __future__ import annotations

from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.causal_common import (
    CausalWarning,
    EvidenceLevel,
)


SCHEMA_VERSION = "C.4"


PropagationMethod = Literal[
    "monte_carlo_resample",   # default: resample input posteriors
    "pairwise_alignment",     # require same-length input samples
]


# ════════════════════════════════════════════════════════════════════
# Request
# ════════════════════════════════════════════════════════════════════


class UncertaintyPipelineRequest(BaseModel):
    """Phase C C4 — end-to-end SER uncertainty propagation request.

    Operator supplies posterior samples (typically from
    /bayesian_estimate C1) for the two SER components D' and G';
    optionally also the κ-mediation proportion (typically from
    /mediation C3 bayesian_mediation branch).

    The engine propagates these through:
        SER = sqrt(D' × G')
        proportion_mediated = NIE / total  (when mediation samples)
    using Monte Carlo resampling (default) or pairwise alignment.
    """

    model_config = ConfigDict(extra="forbid")

    # Required: D' posterior samples
    d_prime_posterior: List[float] = Field(
        ...,
        min_length=10,
        max_length=200_000,
        description=(
            "Posterior samples of D' (dry-matter reduction "
            "normalised). Typically the output of /bayesian_estimate "
            "on D' as the outcome. Length 100-10000 is typical."
        ),
    )

    # Required: G' posterior samples
    g_prime_posterior: List[float] = Field(
        ...,
        min_length=10,
        max_length=200_000,
        description=(
            "Posterior samples of G' (nitrogen recovery normalised). "
            "Same source pattern as d_prime_posterior."
        ),
    )

    # Optional: mediation proportion samples
    mediation_proportion_posterior: Optional[List[float]] = Field(
        default=None,
        max_length=200_000,
        description=(
            "Optional posterior samples of the κ-mediation "
            "proportion. When supplied, the response includes "
            "proportion_mediated_band. Typically the output of "
            "/mediation C3 bayesian_mediation branch's "
            "proportion_mediated samples."
        ),
    )

    method: PropagationMethod = Field(
        default="monte_carlo_resample",
        description=(
            "How to combine D' and G' samples. "
            "``monte_carlo_resample`` (default): resample N "
            "independent draws from each posterior, combine "
            "pointwise. Robust to different sample sizes between "
            "D' and G'. "
            "``pairwise_alignment``: requires len(D') == len(G') "
            "and treats the i-th draw of each as a joint sample. "
            "Use when D' and G' came from the same joint posterior."
        ),
    )

    alpha: float = Field(
        default=0.05,
        gt=0.0,
        lt=1.0,
        description=(
            "Credibility level. Output band uses "
            "[alpha/2, median, 1-alpha/2] quantiles. "
            "Default 0.05 → 95% credibility."
        ),
    )

    n_propagated_samples: int = Field(
        default=10_000,
        ge=100,
        le=200_000,
        description=(
            "Number of Monte Carlo draws to generate (only used "
            "when method='monte_carlo_resample'). Default 10,000. "
            "Set higher for tighter quantile estimates at the cost "
            "of runtime."
        ),
    )

    random_seed: int = Field(
        default=42,
        ge=0,
        le=2**32 - 1,
    )

    @model_validator(mode="after")
    def _check_pairwise_alignment_lengths(
        self,
    ) -> "UncertaintyPipelineRequest":
        if self.method == "pairwise_alignment":
            if len(self.d_prime_posterior) != len(self.g_prime_posterior):
                raise ValueError(
                    f"method='pairwise_alignment' requires "
                    f"len(d_prime_posterior) == len(g_prime_posterior); "
                    f"got {len(self.d_prime_posterior)} vs "
                    f"{len(self.g_prime_posterior)}."
                )
        return self


# ════════════════════════════════════════════════════════════════════
# Response sub-models
# ════════════════════════════════════════════════════════════════════


class CredibilityBand(BaseModel):
    """A 3-tuple credibility band: (low, median, high)."""

    model_config = ConfigDict(extra="forbid")

    low: float = Field(..., description="alpha/2 quantile.")
    median: float = Field(..., description="0.5 quantile.")
    high: float = Field(..., description="1-alpha/2 quantile.")

    @model_validator(mode="after")
    def _check_order(self) -> "CredibilityBand":
        if not (self.low <= self.median <= self.high):
            raise ValueError(
                f"CredibilityBand violates ordering: "
                f"low={self.low}, median={self.median}, "
                f"high={self.high}"
            )
        return self


class UncertaintyPipelineDiagnostics(BaseModel):
    """Pipeline diagnostics."""

    model_config = ConfigDict(extra="forbid")

    n_d_prime_input: int = Field(..., ge=0)
    n_g_prime_input: int = Field(..., ge=0)
    n_mediation_input: Optional[int] = Field(default=None, ge=0)
    n_propagated: int = Field(..., ge=0)
    method: PropagationMethod
    propagation_time_ms: float = Field(..., ge=0.0)
    invalid_samples_dropped: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of propagated samples dropped due to invalid "
            "SER computation (e.g. negative product before sqrt)."
        ),
    )


# ════════════════════════════════════════════════════════════════════
# Response
# ════════════════════════════════════════════════════════════════════


class UncertaintyPipelineResponse(BaseModel):
    """Phase C C4 — end-to-end SER posterior."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=SCHEMA_VERSION, frozen=True)

    # SER posterior (always present)
    final_ser_point: float = Field(
        ...,
        description="Posterior mean of SER = sqrt(D' × G').",
    )
    final_ser_credibility_band: CredibilityBand
    final_ser_posterior_samples: List[float] = Field(
        ...,
        description=(
            "Full propagated SER samples. Length = "
            "n_propagated_samples."
        ),
    )

    # Mediation proportion band (present when input supplied)
    proportion_mediated_band: Optional[CredibilityBand] = Field(
        default=None,
        description=(
            "Credibility band on the κ-mediation proportion. "
            "Present only when mediation_proportion_posterior "
            "was supplied in the request."
        ),
    )

    # Pearl-identity sanity (when mediation supplied):
    # E[NIE] / E[total] should approximately equal
    # E[proportion_mediated]. We don't enforce as an error here
    # because the request is decoupled from the upstream
    # mediation engine; just report.
    pearl_consistency_residual: Optional[float] = Field(
        default=None,
        description=(
            "Computed only when mediation_proportion_posterior is "
            "supplied. |E[proportion_mediated] - estimated| from "
            "samples. NOT enforced — informational."
        ),
    )

    # Diagnostics + metadata
    diagnostics: UncertaintyPipelineDiagnostics
    alpha: float
    method: PropagationMethod
    random_seed: int
    evidence_level: EvidenceLevel
    warnings: List[CausalWarning] = Field(default_factory=list)
