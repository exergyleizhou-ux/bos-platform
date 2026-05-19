"""Agent-side mirror of backend/app/schemas/causal_common.py.

Drift policy: must stay in lockstep with the source. See
``agent/tests/test_schema_parity.py`` for the enforcement test
(B4 v2 Step 4 extends parity to cover this module).

Isolation: this module is part of agent runtime — MUST NOT
import ``app.*``.

Source reference: PHASE_B_PLAN.md §2.6.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ════════════════════════════════════════════════════════════════════
# DAG structural types
# ════════════════════════════════════════════════════════════════════


NodeKind = Literal[
    "treatment",
    "outcome",
    "mediator",
    "covariate",
    "instrument",
    "latent",
]

EdgeKind = Literal["direct", "confounding"]

DagSource = Literal["hand", "auto_causal_learn", "hybrid", "library"]

ProvenanceTag = Literal["hand", "auto", "library"]


class DagNode(BaseModel):
    """A single causal-graph node."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description="Identifier (Python-valid).",
        examples=["dm_in"],
    )
    node_kind: NodeKind = Field(
        ...,
        description="Causal role.",
        examples=["treatment"],
    )
    bos_field_ref: Optional[str] = Field(
        default=None,
        max_length=128,
        description=(
            "Optional dotted reference to the Phase A schema field this "
            "node represents, e.g. 'ser.SerComputeRequest.dm_in'. Used "
            "for DAG-library audit + B0.7's time-indexed DSL "
            "(e.g. '@step_at_m3_boundary')."
        ),
    )


class DagEdge(BaseModel):
    """Directed edge between two declared nodes."""

    model_config = ConfigDict(extra="forbid")

    src: str = Field(
        ..., min_length=1, max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
    )
    dst: str = Field(
        ..., min_length=1, max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
    )
    edge_kind: EdgeKind = Field(default="direct")


class DagSpec(BaseModel):
    """Directed acyclic graph plus provenance metadata."""

    model_config = ConfigDict(extra="forbid")

    nodes: List[DagNode] = Field(..., min_length=2, max_length=64)
    edges: List[DagEdge] = Field(..., min_length=1, max_length=256)
    source: DagSource = Field(
        ...,
        description=(
            "Provenance of the DAG: 'hand' (operator-authored), "
            "'auto_causal_learn' (auto-discovery), 'hybrid' (skeleton "
            "+ auto-validate), or 'library' (curated, e.g. B0.7's "
            "PHASE_B_DAGS/*.json)."
        ),
    )
    provenance_meta: Dict[str, ProvenanceTag] = Field(
        default_factory=dict,
        description=(
            "Per-edge provenance. Keys use format 'src->dst'. Lets a "
            "hybrid DAG record which edges came from the hand skeleton "
            "vs the auto-validation pass vs the curated library. "
            "Optional; recommended when source == 'hybrid'."
        ),
    )
    citation: Optional[str] = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def _check_dag_consistency(self) -> "DagSpec":
        names = {n.name for n in self.nodes}
        for e in self.edges:
            if e.src not in names or e.dst not in names:
                raise ValueError(
                    f"Edge {e.src!r}->{e.dst!r} references unknown node."
                )
            if e.src == e.dst:
                raise ValueError(f"Self-loop forbidden ({e.src}).")
        import networkx as nx
        g = nx.DiGraph()
        g.add_nodes_from(names)
        g.add_edges_from((e.src, e.dst) for e in self.edges)
        if not nx.is_directed_acyclic_graph(g):
            cycles = list(nx.simple_cycles(g))
            smallest = min(cycles, key=len)
            cycle_str = " -> ".join(smallest + [smallest[0]])
            raise ValueError(
                f"DAG contains cycle: {cycle_str}. Remove one edge "
                f"in this cycle to make the DAG identifiable."
            )
        return self


# ════════════════════════════════════════════════════════════════════
# Data envelope
# ════════════════════════════════════════════════════════════════════


class CausalData(BaseModel):
    """Tabular data carrier."""

    model_config = ConfigDict(extra="forbid")

    inline: Optional[List[Dict[str, float]]] = Field(
        default=None,
        max_length=200_000,
        description=(
            "Inline row list; each dict is one record with numeric "
            "values. Up to 200k rows. For larger datasets use "
            "batch_query_key."
        ),
    )
    batch_query_key: Optional[str] = Field(
        default=None,
        max_length=128,
        description=(
            "Server-side handle to a previously-registered dataset "
            "(e.g. SHA-256 prefix of a batch DB cursor). Phase B MVP "
            "does not implement the backing store; reserved for "
            "Phase G."
        ),
    )
    fingerprint: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="SHA-256 of (sorted columns) + row count.",
    )

    @model_validator(mode="after")
    def _check_one_source(self) -> "CausalData":
        if (self.inline is None) == (self.batch_query_key is None):
            raise ValueError(
                "Provide exactly one of inline / batch_query_key."
            )
        return self


# ════════════════════════════════════════════════════════════════════
# Handles
# ════════════════════════════════════════════════════════════════════


IdentifyStrategy = Literal[
    "backdoor",
    "frontdoor",
    "iv",
    "mediation",
    "trivial",
    "unidentifiable",
]

EvidenceLevel = Literal["validated", "supported", "planned"]

Assumption = Literal[
    "no_unobserved_confounders",
    "positivity",
    "consistency",
    "sutva",
    "sequential_ignorability",
    "no_treatment_mediator_interaction",
]


class IdentifiedEstimandHandle(BaseModel):
    """Echo of /identify's verdict, sufficient for /estimate to reuse
    the same adjustment strategy without re-running identification.
    """

    model_config = ConfigDict(extra="forbid")

    strategy: IdentifyStrategy
    adjustment_set: List[str] = Field(..., max_length=64)
    estimand_expression: str = Field(..., min_length=1, max_length=2048)
    dataset_fingerprint: str = Field(..., min_length=8, max_length=128)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EstimateHandle(BaseModel):
    """Echo of /estimate's run; sufficient for /refute and /sensitivity
    to re-fit on the same data + DAG + method choice. Stateless."""

    model_config = ConfigDict(extra="forbid")

    dag: DagSpec
    treatment: str
    outcome: str
    method_family: str
    method_params: Dict[str, Any] = Field(default_factory=dict)
    data: CausalData
    seed: Optional[int] = Field(default=None, ge=0, le=2**32 - 1)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ════════════════════════════════════════════════════════════════════
# Method parameters
# ════════════════════════════════════════════════════════════════════


class DmlParams(BaseModel):
    """Parameters for the DML estimator (D9 = α: LinearDML MVP)."""

    model_config = ConfigDict(extra="forbid")

    model_y: Literal["linear_regression", "lasso", "ridge"] = Field(
        default="linear_regression",
        description="Outcome nuisance model.",
    )
    model_t: Literal["linear_regression", "lasso", "ridge", "logistic"] = Field(
        default="linear_regression",
        description="Treatment nuisance model.",
    )
    discrete_treatment: bool = Field(
        default=False,
        description="True when treatment is binary/categorical.",
    )
    cv: int = Field(
        default=2,
        ge=2,
        le=20,
        description="Cross-fitting folds.",
    )
    random_state: Optional[int] = Field(
        default=None,
        ge=0,
        le=2**32 - 1,
    )


class MethodParams(BaseModel):
    """Typed wrapper over per-method-family config."""

    model_config = ConfigDict(extra="forbid")

    linear_regression: Optional[Dict[str, Any]] = None
    propensity_score: Optional[Dict[str, Any]] = None
    dml: Optional[DmlParams] = None


# ════════════════════════════════════════════════════════════════════
# Warning record
# ════════════════════════════════════════════════════════════════════


WarningCode = Literal[
    "small_sample",
    "ci_wider_than_estimate",
    "no_continuous_covariate",
    "identification_unstable",
    "method_fallback",
]


class CausalWarning(BaseModel):
    """Operator-visible warning record carried in response payloads."""

    model_config = ConfigDict(extra="forbid")

    code: WarningCode
    severity: Literal["info", "warn", "error"] = "warn"
    message: str = Field(..., min_length=1, max_length=512)


# ════════════════════════════════════════════════════════════════════
# Engine version constant for the causal layer
# ════════════════════════════════════════════════════════════════════


CAUSAL_ENGINE_VERSION = "0.9.0"
"""Bump on any backwards-incompatible change to the causal engines.
Reported on every causal endpoint response.

History:
- 0.1.0: B2a initial ship (identify + estimate).
- 0.9.0: B7 paper-pin commit (5 endpoints SHIPPED — identify /
  estimate / refute / mediation / sensitivity — aligned with
  the ``v0.9.0-paper1`` git tag for the Paper 1 audit chain).
"""
