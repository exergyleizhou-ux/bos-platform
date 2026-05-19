"""Phase B — /api/v1/causal/refute schemas.

Reference: PHASE_B_PLAN.md §2.3, with revisions per
PHASE_B_PLAN_V2_PATCH_S2_3.md (mandatory refuter count 5 → 4 because
``evalue_sensitivity_analyzer`` is not in DoWhy 0.14's
``model.refute_estimate(method_name=...)`` dispatch table; E-value
moves to ``/api/v1/causal/sensitivity`` in B2b.3).

Design: PHASE_B2b1_DESIGN.md §3 / §4 / §5.

D9-style reserved-enum pattern (mirrors B2a estimate's
``causal_forest_dml`` / ``x_learner``): the
``non_parametric_sensitivity_analyzer`` enum value is accepted at
the schema layer but rejected by the engine with HTTP 422
``code='refuter_reserved'``. This keeps the OpenAPI surface
forward-compatible across B-series releases.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent.schemas.causal.common import (
    CausalWarning,
    EstimateHandle,
    EvidenceLevel,
)


SCHEMA_VERSION = "B.3"


# Refuter taxonomy. The mandatory four are implemented end-to-end in
# B2b.1; ``bootstrap_refuter`` is the lone optional that *is* shipped
# (DoWhy 0.14 API verified identical to the mandatory four);
# ``non_parametric_sensitivity_analyzer`` is the lone optional that
# is *reserved* (engine 422-rejects with code='refuter_reserved').
RefuterName = Literal[
    # Mandatory — Phase B B2b.1 implements all 4
    "random_common_cause",
    "placebo_treatment_refuter",
    "data_subset_refuter",
    "add_unobserved_common_cause",
    # Optional — implemented
    "bootstrap_refuter",
    # Optional — reserved (Phase G / B2b future)
    "non_parametric_sensitivity_analyzer",
]


Mode = Literal["sync", "async_job"]


# ════════════════════════════════════════════════════════════════════
# Request
# ════════════════════════════════════════════════════════════════════


class CausalRefuteRequest(BaseModel):
    """Refutation phase input.

    Runs one or more DoWhy refuters against the estimate referenced by
    ``estimate_handle`` (echoed from a previous /estimate response).
    Returns per-refuter pass/fail verdicts plus an aggregated
    ``evidence_level`` per Plan v2 §2.3 (patched).
    """

    model_config = ConfigDict(extra="forbid")

    estimate_handle: EstimateHandle = Field(
        ...,
        description=(
            "Echo of the EstimateHandle returned by /api/v1/causal/"
            "estimate. Carries the DAG, treatment, outcome, method, "
            "data, and seed so the engine can re-fit identically "
            "without a server-side cache."
        ),
    )
    refuters: List[RefuterName] = Field(
        ...,
        min_length=1,
        max_length=6,
        description=(
            "One or more refuter names to run. Duplicates rejected by "
            "validator. At least one refuter required so the response "
            "is always non-empty."
        ),
    )
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        le=2**32 - 1,
        description=(
            "Optional RNG seed for refuters that sample (random_common_"
            "cause, placebo_treatment_refuter, data_subset_refuter, "
            "bootstrap_refuter). When None, DoWhy's per-refuter default "
            "is used."
        ),
    )
    significance_alpha: float = Field(
        default=0.05,
        ge=0.001,
        le=0.5,
        description=(
            "Two-sided alpha used by significance-test refuters. The "
            "engine derives ``passed`` as ``p_value > "
            "max(significance_alpha, 0.10)`` for the ``validated`` "
            "evidence-level rule, and ``p_value > significance_alpha`` "
            "for the ``supported`` rule (Plan v2 §2.3 patched)."
        ),
    )
    mode: Mode = Field(
        default="sync",
        description=(
            "Sync only in B2b.1. ``async_job`` reserved for a later "
            "batch."
        ),
    )
    original_e_value: Optional[float] = Field(
        default=None,
        ge=1.0,
        description=(
            "Echo of e_value_cheap from the preceding /estimate "
            "response. When present, used in the evidence_level rule "
            "verbatim. When absent, the engine recomputes via a "
            "lightweight LR estimate (one extra pass; ~20% engine "
            "cost) and adds an 'e_value_recomputed' warning. "
            "Strongly recommended to pass it through to preserve the "
            "audit trail (matches the precedent of "
            "``precomputed_estimand`` in /estimate's request schema)."
        ),
    )

    @model_validator(mode="after")
    def _check_async_not_implemented(self) -> "CausalRefuteRequest":
        if self.mode != "sync":
            raise ValueError(
                "mode='async_job' reserved for B2b future; "
                "B2b.1 sync only."
            )
        return self

    @model_validator(mode="after")
    def _check_no_duplicate_refuters(self) -> "CausalRefuteRequest":
        if len(self.refuters) != len(set(self.refuters)):
            raise ValueError("Duplicate refuter names not allowed.")
        return self


# ════════════════════════════════════════════════════════════════════
# Per-refuter result
# ════════════════════════════════════════════════════════════════════


class RefuterResult(BaseModel):
    """One refuter's verdict.

    ``p_value`` is **Optional** because
    ``add_unobserved_common_cause`` does not perform a significance
    test — it returns a confounder-strength scan instead. For that
    refuter, ``passed`` is derived from
    ``abs(delta_estimate / original_estimate) < 0.1`` (see
    PHASE_B2b1_DESIGN.md §7), and ``p_value`` stays ``None``.
    """

    model_config = ConfigDict(extra="forbid")

    refuter: RefuterName
    passed: bool = Field(
        ...,
        description=(
            "True when the refuter's diagnostic supports the original "
            "estimate (e.g. non-significant p-value, or small relative "
            "delta for add_unobserved)."
        ),
    )
    p_value: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Significance-test p-value when applicable. None for "
            "``add_unobserved_common_cause`` (no hypothesis test)."
        ),
    )
    delta_estimate: float = Field(
        ...,
        description=(
            "``new_effect - estimated_effect`` returned by DoWhy. "
            "Positive means the refuter's perturbation pushed the "
            "estimate higher; negative means lower. Magnitude near "
            "zero indicates robustness."
        ),
    )
    diagnostic: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description=(
            "Free-form refuter description. For DoWhy refuters this "
            "echoes ``refutation_type`` (e.g. 'Refute: Add a random "
            "common cause'); for add_unobserved it records the "
            "relative-delta and the threshold used."
        ),
    )


# ════════════════════════════════════════════════════════════════════
# Response
# ════════════════════════════════════════════════════════════════════


class CausalRefuteResponse(BaseModel):
    """Refutation phase output.

    Aggregates per-refuter results into ``overall_robust`` (boolean,
    True only when all *mandatory* refuters passed) and
    ``evidence_level`` per Plan v2 §2.3 (patched) rule:

    - ``validated``: 4 mandatory pass with p>0.10 AND
      identify.strategy == 'backdoor' AND e_value > 1.5.
    - ``supported``: >=2/4 mandatory pass with p>0.05 AND
      identify.strategy in {'backdoor', 'frontdoor', 'mediation'}.
    - ``planned``: otherwise.
    """

    model_config = ConfigDict(extra="forbid")

    refute_results: List[RefuterResult] = Field(
        ...,
        min_length=1,
        description=(
            "Per-refuter verdicts in the order the engine ran them "
            "(generally the same order as request.refuters but the "
            "engine may re-order to put cheap refuters first)."
        ),
    )
    overall_robust: bool = Field(
        ...,
        description=(
            "True when **all mandatory refuters** (random_common_cause, "
            "placebo_treatment_refuter, data_subset_refuter, "
            "add_unobserved_common_cause) passed. Optional refuters "
            "(bootstrap) do not count toward this; they appear in "
            "refute_results for transparency."
        ),
    )
    evidence_level: EvidenceLevel = Field(
        ...,
        description=(
            "Aggregated evidence level. See class docstring for the "
            "three-tier rule (Plan v2 §2.3 patched)."
        ),
    )
    e_value_used: float = Field(
        ...,
        ge=1.0,
        description=(
            "Echo of the e_value the rule consumed. Equal to "
            "request.original_e_value when provided; equal to the "
            "engine's recomputed e_value_cheap otherwise. In the "
            "second case the response carries an 'e_value_recomputed' "
            "warning."
        ),
    )
    warnings: List[CausalWarning] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "Operator-visible warnings collected during the run "
            "(e_value fallback, threshold heuristics, etc.)."
        ),
    )
    engine_version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Causal-engine version; bumped on breaking changes.",
    )
