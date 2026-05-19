"""Phase B B2b.3 — /api/v1/causal/sensitivity schemas.

Reference: Plan v2 §2.5 (PHASE_B_PLAN.md) for the Request shape
(verbatim); the Response shape is designed in this batch because
Plan v2 §2.5 delegates Response to "Plan v1 §2.5 same shape" but
no Plan v1 doc exists (recorded in PHASE_B2b3_DESIGN.md §10).
Method-selection rationale + scratch evidence live in
``PHASE_B2b3_DESIGN.md`` §1.

Three branches keyed on ``method``:

- ``"evalue"`` — DoWhy ``EValueSensitivityAnalyzer`` standalone class
  (Candidate 1) as primary, self-implemented Chinn-VWD E-value
  (Candidate 2) as a delta-style fallback when the primary raises.
- ``"linear"`` — Self-implemented Cinelli-Hazlett 2020 robustness
  value + partial R^2 (Candidate 5). Closed form on top of a single
  ``statsmodels`` OLS fit; no extra deps (PySensemakr was Candidate 4,
  rejected because B1 deps are locked).
- ``"partial_linear"`` — Reserved. Plan v2 §2.5 lists the enum value
  but does not expose the ``theta_s`` parameter DoWhy's
  ``NonParametricSensitivityAnalyzer`` requires (Candidate 3). Engine
  422-rejects with ``code='method_reserved'`` (D9-style pattern,
  mirroring B2a estimate's ``method_family_reserved``, B2b.1 refute's
  ``refuter_reserved``, and B2b.2 mediation's
  ``decomposition_reserved``).

The Response carries one of two ``detail`` payloads keyed by the
echoed ``method`` field, plus a single boolean ``overall_robust``
that operationalises the paper's *"Γ-bound ≥ 1.5"* falsification
gate (paper line 101): for ``evalue`` the gate is
``e_value_lower_ci > 1.5``; for ``linear`` the gate is
``robustness_value_alpha > 0.10`` (Cinelli-Hazlett 2020
conventional threshold; the two numbers live on different scales so
the engine thresholds them separately and exposes only the boolean).

The cross-field validator ``_check_detail_present`` enforces the
detail/method consistency (e.g. ``method='evalue'`` requires
``evalue_detail`` non-None and ``linear_detail`` None). Mirrors the
B2b.2 fix-1 validator-placement decision: the Response-level
invariant lives on the Response, not split across the detail
sub-models.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent.schemas.causal.common import (
    CausalWarning,
    EstimateHandle,
    EvidenceLevel,
)


SCHEMA_VERSION = "B.5"


# Plan v2 §2.5 verbatim. ``partial_linear`` is accepted at the
# schema layer and rejected by the engine with HTTP 422 (D9-style
# reserved-enum pattern). See PHASE_B2b3_DESIGN.md §1 for the
# DoWhy NonParametricSensitivityAnalyzer ``theta_s`` gap that
# motivates the reservation.
SensitivityMethod = Literal["evalue", "linear", "partial_linear"]


Mode = Literal["sync", "async_job"]


# Branch tag echoed in the Response.method field. Distinct from
# ``SensitivityMethod`` because the Response only ever carries the
# two branches that actually ran; ``partial_linear`` is rejected
# upstream and never reaches the Response.
RunMethod = Literal["evalue", "linear"]


# Records which E-value implementation produced the Response when
# ``method='evalue'``. ``dowhy_class`` = Candidate 1 primary path;
# ``self_chinn_vwd`` = Candidate 2 fallback (when the DoWhy path
# raises). The fallback always emits a ``method_fallback`` warning
# (delta-based pattern mirroring B2b.1 refute).
EvalueSource = Literal["dowhy_class", "self_chinn_vwd"]


# ════════════════════════════════════════════════════════════════════
# Request
# ════════════════════════════════════════════════════════════════════


class CausalSensitivityRequest(BaseModel):
    """Sensitivity phase input (Plan v2 §2.5 verbatim Request).

    Bounds the unmeasured-confounder bias on the upstream
    ``/estimate`` result without re-running the estimation. Two
    methods are implemented; ``partial_linear`` is reserved at the
    engine layer (HTTP 422 ``code='method_reserved'``).

    Plan v2 §2.5 does not expose ``assumptions_acknowledged`` (unlike
    B2b.2 mediation's Mod 8) — for sensitivity, the *bounds
    themselves* are the assumptions and a separate acknowledgement
    field would be redundant. Surface intentionally minimal.
    """

    model_config = ConfigDict(extra="forbid")

    estimate_handle: EstimateHandle = Field(
        ...,
        description=(
            "Echo of the EstimateHandle returned by "
            "/api/v1/causal/estimate. Carries the DAG, treatment, "
            "outcome, method_family, data, and seed so the engine "
            "can re-fit identically without a server-side cache."
        ),
    )
    method: SensitivityMethod = Field(
        default="evalue",
        description=(
            "Sensitivity bound method. ``evalue`` is the default "
            "(VanderWeele-Ding E-value, paper Gamma-bound style, "
            "cheap). ``linear`` runs Cinelli-Hazlett 2020 robustness "
            "value + partial R^2. ``partial_linear`` is reserved and "
            "rejected at the engine layer."
        ),
    )
    benchmark_covariate: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description=(
            "Optional adjustment-set covariate name to use as the "
            "benchmarking strength for the Cinelli-Hazlett RV "
            "interpretation. When supplied, must appear in "
            "``estimate_handle.dag.nodes`` with "
            "``node_kind='covariate'`` (enforced by "
            "``_check_benchmark_covariate_in_dag``). Ignored on the "
            "``evalue`` branch."
        ),
    )
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        le=2**32 - 1,
        description="Optional RNG seed (re-used by primary DoWhy path).",
    )
    mode: Mode = Field(
        default="sync",
        description=(
            "Execution mode. B2b.3 implements ``sync`` only; "
            "``async_job`` is reserved and currently rejected with "
            "HTTP 422 (``_check_async_not_implemented``)."
        ),
    )

    @model_validator(mode="after")
    def _check_benchmark_covariate_in_dag(
        self,
    ) -> "CausalSensitivityRequest":
        if self.benchmark_covariate is None:
            return self
        names_by_kind = {
            n.name: n.node_kind for n in self.estimate_handle.dag.nodes
        }
        if self.benchmark_covariate not in names_by_kind:
            raise ValueError(
                f"benchmark_covariate {self.benchmark_covariate!r} "
                f"not declared in estimate_handle.dag.nodes"
            )
        kind = names_by_kind[self.benchmark_covariate]
        if kind != "covariate":
            raise ValueError(
                f"benchmark_covariate {self.benchmark_covariate!r} "
                f"must have node_kind='covariate' in the DAG "
                f"(got {kind!r})"
            )
        return self

    @model_validator(mode="after")
    def _check_async_not_implemented(
        self,
    ) -> "CausalSensitivityRequest":
        if self.mode != "sync":
            raise ValueError(
                "mode='async_job' reserved for a later batch; "
                "B2b.3 sync only."
            )
        return self


# ════════════════════════════════════════════════════════════════════
# Branch-specific detail sub-models
# ════════════════════════════════════════════════════════════════════


class SensitivityEvalueDetail(BaseModel):
    """E-value branch payload.

    Populated when ``method='evalue'`` ran. The two E-value fields
    are sourced from DoWhy's ``EValueSensitivityAnalyzer.stats`` dict
    when ``source='dowhy_class'`` (verified field names:
    ``evalue_estimate`` and ``evalue_lower_ci``); from the
    Chinn (2000) / VanderWeele-Ding 2017 approximation when
    ``source='self_chinn_vwd'`` (fallback).
    """

    model_config = ConfigDict(extra="forbid")

    e_value_point: float = Field(
        ...,
        ge=1.0,
        description=(
            "E-value computed on the point estimate. >= 1.0 by "
            "construction (E-value = 1 indicates 'no robustness "
            "margin'); larger is more robust."
        ),
    )
    e_value_lower_ci: float = Field(
        ...,
        ge=1.0,
        description=(
            "E-value computed on the lower 95% CI bound of the "
            "estimate (the bound closer to the null). The robust "
            "variant — Plan v2 §2.5's 'Gamma-bound >= 1.5' gate "
            "evaluates this field, not ``e_value_point``."
        ),
    )
    source: EvalueSource = Field(
        ...,
        description=(
            "Which implementation produced the E-value. "
            "``dowhy_class`` = DoWhy EValueSensitivityAnalyzer "
            "primary path; ``self_chinn_vwd`` = fallback after a "
            "DoWhy-side exception (always pairs with a "
            "``method_fallback`` warning in ``warnings``)."
        ),
    )


class SensitivityLinearDetail(BaseModel):
    """Cinelli-Hazlett branch payload.

    Populated when ``method='linear'`` ran. Closed-form expressions
    from Cinelli-Hazlett 2020 Eq. 4 applied to a single
    ``statsmodels`` OLS fit of ``Y ~ T + adjustment_set``.
    """

    model_config = ConfigDict(extra="forbid")

    robustness_value: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Cinelli-Hazlett robustness value RV(q=1). Fraction in "
            "[0, 1]: the minimum strength a confounder would need "
            "to both predict treatment and outcome (in partial R^2 "
            "terms) to fully explain away the observed effect. "
            "Larger is more robust; 0 = trivially explained away."
        ),
    )
    robustness_value_alpha: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "RV at significance threshold alpha=0.05 — the minimum "
            "strength to push the t-statistic below the 0.05 "
            "critical value. The ``overall_robust`` gate on this "
            "branch is ``robustness_value_alpha > 0.10`` (Cinelli-"
            "Hazlett 2020 conventional 'highly robust' threshold)."
        ),
    )
    partial_r2_yd: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Partial R^2 of the outcome on the treatment given the "
            "adjustment set. Derived from the same OLS fit: "
            "f^2 / (1 + f^2) where f^2 = t^2 / df_resid."
        ),
    )
    partial_r2_yz_given_d: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Partial R^2 of the outcome on the benchmark covariate "
            "given treatment + the rest of the adjustment set. "
            "Populated only when ``request.benchmark_covariate`` "
            "was provided; otherwise ``None``. Engine computes via "
            "leave-one-out OLS where the benchmark covariate is "
            "the *omitted* control."
        ),
    )


# ════════════════════════════════════════════════════════════════════
# Diagnostics
# ════════════════════════════════════════════════════════════════════


class SensitivityDiagnostics(BaseModel):
    """Engine-side telemetry attached to every successful Response."""

    model_config = ConfigDict(extra="forbid")

    method: RunMethod = Field(
        ...,
        description=(
            "Which engine branch produced this Response. Never "
            "``partial_linear`` because that enum value is "
            "422-rejected upstream."
        ),
    )
    n_samples: int = Field(
        ...,
        ge=0,
        description="Number of rows the engine actually fit on.",
    )
    fit_time_ms: float = Field(
        ...,
        ge=0.0,
        description="Wall-clock fit time in milliseconds.",
    )
    benchmark_covariate_used: Optional[str] = Field(
        default=None,
        description=(
            "Echo of ``request.benchmark_covariate`` when the linear "
            "branch actually used it (leave-one-out OLS fired). "
            "``None`` on the evalue branch even if the request "
            "carried a benchmark covariate — sensitivity-analyzer "
            "benchmarking is not consumed on that branch."
        ),
    )


# ════════════════════════════════════════════════════════════════════
# Response
# ════════════════════════════════════════════════════════════════════


class CausalSensitivityResponse(BaseModel):
    """Sensitivity phase output.

    Carries exactly one of ``evalue_detail`` / ``linear_detail`` keyed
    by ``method`` (Response-level validator
    ``_check_detail_present``), plus an ``overall_robust`` boolean
    that operationalises Plan v2 §2.5's paper Gamma-bound gate and an
    aggregated ``evidence_level``.
    """

    model_config = ConfigDict(extra="forbid")

    method: RunMethod = Field(
        ...,
        description=(
            "Echo of the branch that ran. Distinct from "
            "``SensitivityMethod`` because the Response only ever "
            "carries the two implemented branches."
        ),
    )
    evalue_detail: Optional[SensitivityEvalueDetail] = Field(
        default=None,
        description=(
            "E-value branch payload. Populated iff ``method='evalue'``; "
            "``None`` otherwise (enforced by Response validator)."
        ),
    )
    linear_detail: Optional[SensitivityLinearDetail] = Field(
        default=None,
        description=(
            "Cinelli-Hazlett branch payload. Populated iff "
            "``method='linear'``; ``None`` otherwise (enforced by "
            "Response validator)."
        ),
    )
    overall_robust: bool = Field(
        ...,
        description=(
            "Boolean rollup of the paper's 'Gamma-bound >= 1.5' "
            "falsification gate (paper line 101). For "
            "``method='evalue'``: ``e_value_lower_ci > 1.5``. For "
            "``method='linear'``: ``robustness_value_alpha > 0.10`` "
            "(Cinelli-Hazlett 2020 conventional threshold; E-value "
            "and RV live on different scales so the engine "
            "thresholds them separately and surfaces only this "
            "boolean)."
        ),
    )
    evidence_level: EvidenceLevel = Field(
        ...,
        description=(
            "Aggregated evidence per Plan v2 §2.5. ``validated`` "
            "when ``overall_robust=True``; ``supported`` otherwise "
            "(the estimate exists but the bound is too tight); "
            "``planned`` reserved for Phase G integration paths."
        ),
    )
    diagnostics: SensitivityDiagnostics
    warnings: List[CausalWarning] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "Engine warnings. The most important is "
            "``method_fallback`` on the evalue branch — signals that "
            "the DoWhy primary path raised and the engine fell back "
            "to the self-implemented Chinn-VWD E-value."
        ),
    )
    engine_version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="``CAUSAL_ENGINE_VERSION`` at the time of fit.",
    )

    @model_validator(mode="after")
    def _check_detail_present(self) -> "CausalSensitivityResponse":
        """Detail / method consistency. Mirrors B2b.2 fix-1 placement:
        a Response-level invariant lives on the Response.
        """
        if self.method == "evalue":
            if self.evalue_detail is None:
                raise ValueError(
                    "evalue_detail is required when method='evalue'"
                )
            if self.linear_detail is not None:
                raise ValueError(
                    "linear_detail must be None when method='evalue'"
                )
        elif self.method == "linear":
            if self.linear_detail is None:
                raise ValueError(
                    "linear_detail is required when method='linear'"
                )
            if self.evalue_detail is not None:
                raise ValueError(
                    "evalue_detail must be None when method='linear'"
                )
        return self

    @model_validator(mode="after")
    def _check_diagnostics_method_matches(
        self,
    ) -> "CausalSensitivityResponse":
        """Defensive: ``diagnostics.method`` must echo the
        Response-level ``method``. Prevents an engine-side bug from
        emitting an inconsistent Response (e.g. method='evalue' +
        diagnostics.method='linear')."""
        if self.diagnostics.method != self.method:
            raise ValueError(
                f"diagnostics.method {self.diagnostics.method!r} "
                f"differs from response.method {self.method!r}"
            )
        return self


__all__ = [
    "SCHEMA_VERSION",
    "SensitivityMethod",
    "Mode",
    "RunMethod",
    "EvalueSource",
    "CausalSensitivityRequest",
    "SensitivityEvalueDetail",
    "SensitivityLinearDetail",
    "SensitivityDiagnostics",
    "CausalSensitivityResponse",
]
