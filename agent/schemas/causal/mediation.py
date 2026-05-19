"""Phase B B2b.2 — /api/v1/causal/mediation schemas.

Reference: Plan v2 §2.4 (PHASE_B_PLAN.md), with the design decisions
recorded in PHASE_B2b2_DESIGN.md §2.

Paper map (V14 line 11 + line 153): operationalises the Pearl/Rubin
counterfactual mediation analysis on the Signal-API -> kappa -> SER
pathway (Eq. 4), targeting the abstract's "~70% proportion mediated"
claim. Treatment / mediator / outcome are caller-supplied; the engine
selects between a DoWhy two-stage branch (single mediator, candidate 2
in the design doc's mini-verify) and a Farbmacher leave-one-out DML
branch (multiple mediators, candidate 4). D14 = gamma confirms
Pearl/Rubin (NDE/ADE + NIE/ACME) over Baron-Kenny/Sobel.

The ``decomposition`` enum is Plan v2 §2.4 verbatim: only ``natural``
is implemented in B2b.2; ``controlled`` and ``interventional`` are
reserved for a later release and currently rejected at the engine
layer (D9-style reserved-enum pattern, mirroring B2a estimate and
B2b.1 refute).

Validator placement (deliberate divergence from Plan v2 §2.4 / design
doc §2): the Pearl-identity and mediator_share-sum checks live on
``CausalMediationResponse`` (Response-level) rather than on
``MediationDecomposition``. The Response carries three
``MediationDecomposition`` instances — the point estimate plus the
lower/upper bootstrap CI bands — and bootstrap CI bands provably
violate both invariants (additivity is not preserved by quantile
slicing across bootstrap iterations, and per-mediator shares can drift
outside the [0.7, 1.3] slack at the band edges). The validators
therefore only inspect ``self.decomposition`` and treat ``ci_lower`` /
``ci_upper`` as pure data holders. This matches the design intent
recorded in PHASE_B2b2_DESIGN.md §8 R3.

The ``n_bootstrap`` default is 200 rather than Plan v2's 1000. This is
the R1 mitigation in PHASE_B2b2_DESIGN.md §8: with K=5 mediators on the
Farbmacher branch, n_bootstrap=1000 implies ~5000 LinearDML fits per
request, putting wall-clock above the 30 s budget. Phase G can raise
the default after a normal-approximation CI fallback is added.

Mod 4 (precomputed_estimand) and Mod 8 (mediator_share sum slack
[0.7, 1.3]) are inherited from Plan v2 mods; Mod 6 (significance_alpha
floor) is not relevant here because mediation CI is expressed as
bootstrap quantile bands rather than a single alpha-level test.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent.schemas.causal.common import (
    CausalData,
    CausalWarning,
    DagSpec,
    EvidenceLevel,
    IdentifiedEstimandHandle,
)


SCHEMA_VERSION = "B.4"


# Inline-row ceiling for ``mode='sync'``. Above this, the request must
# use ``mode='async_job'`` (reserved for B2b.3 — currently rejected by
# ``_check_async_not_implemented``). Mirrors the size gate used in B2a
# estimate / B2b.1 refute.
SYNC_MAX_INLINE_ROWS = 10_000


# Plan v2 §2.4 verbatim. B2b.2 MVP implements ``natural`` only;
# ``controlled`` and ``interventional`` are reserved values accepted at
# the schema layer and rejected by the engine with HTTP 422
# (D9-style reserved-enum pattern).
DecompositionType = Literal["natural", "controlled", "interventional"]


Mode = Literal["sync", "async_job"]


# The four Pearl-style identification assumptions the operator may
# acknowledge. ``assumptions_acknowledged`` (request) and
# ``assumptions_echo`` (response) both use this Literal so the
# response is auditable against the request without renaming.
AssumptionAck = Literal[
    "sequential_ignorability",
    "no_treatment_mediator_interaction",
    "consistency",
    "positivity",
]


# Engine-branch tag used by ``MediationDiagnostics.method``. The
# single-mediator branch routes to DoWhy ``mediation.two_stage_regression``;
# the multi-mediator branch routes to a Farbmacher 2022-style leave-one-out
# LinearDML loop (per PHASE_B2b2_DESIGN.md §1).
MediationMethod = Literal["dowhy_two_stage", "farbmacher_dml_loo"]


# ════════════════════════════════════════════════════════════════════
# Request
# ════════════════════════════════════════════════════════════════════


class CausalMediationRequest(BaseModel):
    """Mediation phase input.

    Decomposes the treatment -> outcome ATE into a direct (ADE/NDE)
    effect plus a per-mediator indirect (ACME/NIE) effect via the
    Pearl/Rubin counterfactual framework. Returns point estimates,
    bootstrap quantile CIs, and a proportion_mediated summary
    (Plan v2 §2.4).
    """

    model_config = ConfigDict(extra="forbid")

    dag: DagSpec = Field(
        ...,
        description=(
            "DAG that includes the treatment, the outcome, and every "
            "mediator. Each mediator name in ``mediators`` must appear "
            "in ``dag.nodes`` with ``node_kind='mediator'`` "
            "(``_check_mediators_in_dag``)."
        ),
    )
    treatment: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description="Treatment node name; must be in ``dag.nodes``.",
    )
    outcome: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description="Outcome node name; must be in ``dag.nodes`` and differ from ``treatment``.",
    )
    mediators: List[str] = Field(
        ...,
        min_length=1,
        max_length=8,
        description=(
            "One or more mediator node names. Single-mediator requests "
            "route to the DoWhy two-stage branch; multi-mediator "
            "requests route to the Farbmacher leave-one-out DML branch "
            "(PHASE_B2b2_DESIGN.md §1)."
        ),
    )
    data: CausalData
    decomposition: DecompositionType = Field(
        default="natural",
        description=(
            "Mediation decomposition flavour. B2b.2 MVP implements "
            "``natural`` only (Pearl NDE/NIE); ``controlled`` and "
            "``interventional`` are reserved values rejected by the "
            "engine with HTTP 422 (D9-style)."
        ),
    )
    seed: Optional[int] = Field(
        default=None,
        ge=0,
        le=2**32 - 1,
        description="Optional RNG seed for reproducible bootstrap.",
    )
    n_bootstrap: int = Field(
        default=200,
        ge=100,
        le=10_000,
        description=(
            "Bootstrap iterations for the decomposition CI. Default "
            "200 (vs Plan v2 §2.4's 1000) per PHASE_B2b2_DESIGN.md §8 "
            "R1: with K=5 mediators on the Farbmacher branch, 1000 "
            "iterations imply ~5000 LinearDML fits per request, "
            "exceeding the 30 s wall-clock budget. Phase G can raise "
            "this once a normal-approximation CI fallback exists."
        ),
    )
    assumptions_acknowledged: List[AssumptionAck] = Field(
        ...,
        min_length=1,
        description=(
            "Operator MUST acknowledge at least one Pearl-style "
            "identification assumption. Empty list -> HTTP 422. "
            "The response echoes this list verbatim in "
            "``assumptions_echo`` so the mediation result is "
            "audit-traceable (Mod 8)."
        ),
    )
    precomputed_estimand: Optional[IdentifiedEstimandHandle] = Field(
        default=None,
        description=(
            "Optional echo of an /identify response's ``estimand_handle`` "
            "for the parent ATE; saves one identification re-run on "
            "the DoWhy single-mediator branch. Same audit-trail "
            "rationale as B2a estimate's Mod 4."
        ),
    )
    mode: Mode = Field(
        default="sync",
        description=(
            "Execution mode. B2b.2 implements ``sync`` only; "
            "``async_job`` is reserved for B2b.3 and currently "
            "rejected with HTTP 422 (``_check_async_not_implemented``)."
        ),
    )

    @model_validator(mode="after")
    def _check_treatment_outcome_in_dag(self) -> "CausalMediationRequest":
        names = {n.name for n in self.dag.nodes}
        if self.treatment not in names:
            raise ValueError(
                f"treatment {self.treatment!r} not declared in dag.nodes"
            )
        if self.outcome not in names:
            raise ValueError(
                f"outcome {self.outcome!r} not declared in dag.nodes"
            )
        if self.treatment == self.outcome:
            raise ValueError("treatment and outcome must differ")
        return self

    @model_validator(mode="after")
    def _check_mediators_in_dag(self) -> "CausalMediationRequest":
        names_by_kind = {n.name: n.node_kind for n in self.dag.nodes}
        for m in self.mediators:
            if m not in names_by_kind:
                raise ValueError(
                    f"mediator {m!r} not declared in dag.nodes"
                )
            if names_by_kind[m] != "mediator":
                raise ValueError(
                    f"mediator {m!r} must have node_kind='mediator' "
                    f"in the DAG (got {names_by_kind[m]!r})"
                )
        if len(set(self.mediators)) != len(self.mediators):
            raise ValueError("duplicate mediator names not allowed")
        if self.treatment in self.mediators:
            raise ValueError(
                f"treatment {self.treatment!r} cannot also be a mediator"
            )
        if self.outcome in self.mediators:
            raise ValueError(
                f"outcome {self.outcome!r} cannot also be a mediator"
            )
        return self

    @model_validator(mode="after")
    def _check_sync_size_gate(self) -> "CausalMediationRequest":
        if (
            self.mode == "sync"
            and self.data.inline is not None
            and len(self.data.inline) > SYNC_MAX_INLINE_ROWS
        ):
            raise ValueError(
                f"sync mode + inline rows {len(self.data.inline)} > "
                f"{SYNC_MAX_INLINE_ROWS}; use mode='async_job' "
                f"(B2b.3 will implement)."
            )
        return self

    @model_validator(mode="after")
    def _check_async_not_implemented(self) -> "CausalMediationRequest":
        if self.mode != "sync":
            raise ValueError(
                "mode='async_job' reserved for a later batch; "
                "B2b.2 sync only."
            )
        return self


# ════════════════════════════════════════════════════════════════════
# Sub-models
# ════════════════════════════════════════════════════════════════════


class MediationDecomposition(BaseModel):
    """Pearl decomposition triple plus per-mediator share.

    Used three times in ``CausalMediationResponse``: once for the point
    estimate (``decomposition``) and once each for the lower / upper
    bootstrap quantile bands (``ci_lower`` / ``ci_upper``).

    Deliberately a pure data holder — no ``@model_validator``. The
    Pearl-identity (``direct + indirect == total``) and
    mediator_share-sum invariants are validated at the Response level
    on ``self.decomposition`` only (see module docstring). Bootstrap CI
    bands provably violate both invariants by construction, so
    validating them here would false-positive every Response
    instantiation that carries CI bands.
    """

    model_config = ConfigDict(extra="forbid")

    total_effect: float = Field(
        ...,
        description="Total ATE: treatment -> outcome on this branch.",
    )
    direct_effect: float = Field(
        ...,
        description=(
            "Average direct effect (ADE / NDE) — treatment -> outcome "
            "with all mediators held at their natural baseline value."
        ),
    )
    indirect_effect: float = Field(
        ...,
        description=(
            "Average causal mediation effect (ACME / NIE) summed over "
            "all mediators. Per-mediator decomposition lives in "
            "``mediator_share``."
        ),
    )
    mediator_share: Dict[str, float] = Field(
        ...,
        min_length=1,
        description=(
            "Per-mediator share of ``indirect_effect``. Keys are the "
            "mediator names from the request; values sum to approximately "
            "1.0. The Response-level validator enforces a [0.7, 1.3] "
            "slack on this sum for ``self.decomposition`` only (Mod 8): "
            "the slack is wider than Plan v1's [0.95, 1.05] because "
            "nonparametric mediation under treatment-mediator interaction "
            "routinely sums outside the tight band."
        ),
    )


class MediationDiagnostics(BaseModel):
    """Engine-side telemetry attached to every successful Response.

    Mirrors B2a estimate's diagnostics pattern: lets the caller audit
    which branch ran, how large the bootstrap sample was, and whether
    the precomputed_estimand short-circuit fired.
    """

    model_config = ConfigDict(extra="forbid")

    method: MediationMethod = Field(
        ...,
        description=(
            "Which engine branch produced this Response. "
            "``dowhy_two_stage`` for single-mediator requests; "
            "``farbmacher_dml_loo`` for multi-mediator requests."
        ),
    )
    n_samples: int = Field(
        ...,
        ge=0,
        description="Number of rows the engine actually fit on.",
    )
    n_bootstrap_used: int = Field(
        ...,
        ge=0,
        description=(
            "Number of bootstrap iterations actually completed. Equals "
            "the request's ``n_bootstrap`` on the happy path; may be "
            "lower if the engine emitted a small_sample warning."
        ),
    )
    n_mediators: int = Field(
        ...,
        ge=1,
        description="Number of mediators in the request.",
    )
    fit_time_ms: float = Field(
        ...,
        ge=0.0,
        description="Wall-clock fit time in milliseconds.",
    )
    used_precomputed_estimand: bool = Field(
        default=False,
        description=(
            "True iff the DoWhy branch reused the request's "
            "``precomputed_estimand`` instead of running identify again."
        ),
    )


# ════════════════════════════════════════════════════════════════════
# Response
# ════════════════════════════════════════════════════════════════════


class CausalMediationResponse(BaseModel):
    """Mediation phase output.

    Carries the point-estimate decomposition plus bootstrap quantile
    bands, a proportion_mediated summary, the echoed assumption set
    (audit trail), an aggregated ``evidence_level`` per Plan v2 §2.4,
    and engine diagnostics.

    Two Response-level validators enforce the Pearl identity and the
    mediator_share-sum slack on ``self.decomposition`` only (see module
    docstring on validator placement).
    """

    model_config = ConfigDict(extra="forbid")

    decomposition: MediationDecomposition = Field(
        ...,
        description="Point-estimate Pearl decomposition.",
    )
    ci_lower: MediationDecomposition = Field(
        ...,
        description=(
            "Lower bootstrap-quantile band of the decomposition. Not "
            "subject to the Pearl identity or share-sum slack."
        ),
    )
    ci_upper: MediationDecomposition = Field(
        ...,
        description=(
            "Upper bootstrap-quantile band of the decomposition. Not "
            "subject to the Pearl identity or share-sum slack."
        ),
    )
    assumptions_echo: List[AssumptionAck] = Field(
        ...,
        min_length=1,
        description=(
            "Verbatim echo of the request's "
            "``assumptions_acknowledged`` (audit trail, Mod 8)."
        ),
    )
    proportion_mediated: float = Field(
        ...,
        ge=-1.0,
        le=2.0,
        description=(
            "indirect_effect / total_effect on the point estimate. "
            "Bounded [-1.0, 2.0] because nonparametric mediation can "
            "produce direction-reversed (negative) or super-additive "
            "(>1) shares under treatment-mediator interaction."
        ),
    )
    proportion_mediated_ci: Tuple[float, float] = Field(
        ...,
        description=(
            "Bootstrap quantile CI on proportion_mediated, paired with "
            "``ci_lower`` / ``ci_upper`` quantile level."
        ),
    )
    evidence_level: EvidenceLevel = Field(
        ...,
        description=(
            "Aggregated evidence per Plan v2 §2.4. ``planned`` when "
            "the small-sample clamp fires; ``supported`` for a normal "
            "run; ``validated`` reserved for Phase G."
        ),
    )
    diagnostics: MediationDiagnostics
    warnings: List[CausalWarning] = Field(
        default_factory=list,
        max_length=20,
        description="Engine warnings (small_sample, reserved enum, etc.).",
    )
    engine_version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="``CAUSAL_ENGINE_VERSION`` at the time of fit.",
    )

    @model_validator(mode="after")
    def _check_decomposition_pearl_invariant(
        self,
    ) -> "CausalMediationResponse":
        d = self.decomposition
        gap = abs(d.direct_effect + d.indirect_effect - d.total_effect)
        if gap > 1e-3:
            raise ValueError(
                f"Pearl identity violated on point estimate: "
                f"|direct + indirect - total| = {gap:.4e} > 1e-3. "
                f"Engine must always satisfy this."
            )
        return self

    @model_validator(mode="after")
    def _check_decomposition_share_sum(
        self,
    ) -> "CausalMediationResponse":
        s = sum(self.decomposition.mediator_share.values())
        if not (0.7 <= s <= 1.3):
            raise ValueError(
                f"mediator_share on point estimate sums to {s:.3f}; "
                f"must be in [0.7, 1.3] under nonparametric mediation "
                f"(Mod 8)."
            )
        return self


__all__ = [
    "SCHEMA_VERSION",
    "SYNC_MAX_INLINE_ROWS",
    "DecompositionType",
    "Mode",
    "AssumptionAck",
    "MediationMethod",
    "CausalMediationRequest",
    "MediationDecomposition",
    "MediationDiagnostics",
    "CausalMediationResponse",
]
