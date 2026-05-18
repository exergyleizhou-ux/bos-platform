"""Phase B — /api/v1/causal/identify schemas.

Reference: PHASE_B_PLAN.md §2.1.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.causal_common import (
    Assumption,
    DagSpec,
    EvidenceLevel,
    IdentifiedEstimandHandle,
    IdentifyStrategy,
)


SCHEMA_VERSION = "B.1"


# ════════════════════════════════════════════════════════════════════
# Request
# ════════════════════════════════════════════════════════════════════


class CausalIdentifyRequest(BaseModel):
    """Identification phase input.

    Operationalises the DAG formalisation step of DoWhy: given a DAG,
    a treatment, and an outcome, return the identifiable estimand
    (back-door / front-door / IV) or an honest ``unidentifiable``
    verdict.
    """

    model_config = ConfigDict(extra="forbid")

    dag: DagSpec
    treatment: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description="Node name; must appear in dag.nodes.",
    )
    outcome: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description="Node name; must appear in dag.nodes.",
    )
    dataset_fingerprint: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description=(
            "SHA-256 prefix or stable hash of the dataset's column set "
            "+ row count. Lets identify-verdicts be audited against "
            "the data they were issued for."
        ),
    )
    proceed_when_unidentifiable: bool = Field(default=False)

    @model_validator(mode="after")
    def _check_treatment_outcome_in_dag(self) -> "CausalIdentifyRequest":
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
        # Treatment must have at least one outgoing edge in the DAG.
        treatment_has_outgoing = any(
            e.src == self.treatment for e in self.dag.edges
        )
        if not treatment_has_outgoing:
            raise ValueError(
                f"treatment {self.treatment!r} has no outgoing edges in "
                f"the DAG; identification is meaningless. Add at least "
                f"one outgoing edge or pick a different treatment."
            )
        return self


# ════════════════════════════════════════════════════════════════════
# Response
# ════════════════════════════════════════════════════════════════════


class CausalIdentifyResponse(BaseModel):
    """Identification phase output."""

    model_config = ConfigDict(extra="forbid")

    identified: bool = Field(
        ...,
        description=(
            "True when the do-calculus produced an identifiable "
            "estimand. False when the DAG is non-identifiable under "
            "the standard assumptions."
        ),
    )
    strategy: IdentifyStrategy = Field(
        ...,
        description=(
            "Which identification strategy resolved. 'trivial' means "
            "the DAG had no edges other than T->O (E[Y|T] applies). "
            "'unidentifiable' means none of backdoor/frontdoor/iv/"
            "mediation closed."
        ),
    )
    adjustment_set: List[str] = Field(
        ...,
        max_length=64,
        description=(
            "Variables to condition on for the chosen strategy. Empty "
            "for 'trivial' or 'unidentifiable'."
        ),
    )
    estimand_expression: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description=(
            "Human-readable estimand, e.g. 'E[Y|do(T)] = "
            "sum_Z E[Y|T,Z] P(Z)'."
        ),
    )
    assumptions: List[Assumption] = Field(
        default_factory=list,
        description=(
            "Identification assumptions that the chosen strategy makes."
        ),
    )
    estimand_handle: IdentifiedEstimandHandle = Field(
        ...,
        description=(
            "Pass this verbatim as precomputed_estimand in the next "
            "/api/v1/causal/estimate request to skip a re-identification "
            "pass and avoid divergence between identify and estimate "
            "adjustment-set choices."
        ),
    )
    evidence_level: EvidenceLevel = Field(
        ...,
        description=(
            "For identify alone the level is 'validated' when "
            "strategy is backdoor/frontdoor/iv with a non-empty "
            "adjustment_set, 'supported' for trivial/mediation, and "
            "'planned' for unidentifiable. The refute endpoint "
            "(B2b) tightens this further."
        ),
    )
    engine_version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Causal-engine version; bumped on breaking changes.",
    )
