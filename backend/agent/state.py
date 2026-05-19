"""BOS Agent - LangGraph state schema.

Plan v2 paragraph 3.1 defines ``BOSState`` as the typed dict that flows
through the StateGraph. Every node reads from + writes to a strict
subset of these keys.

Phase B B4 v2 (Mod 10): added ``CausalSlice`` sub-TypedDict to group
the 14 causal-pipeline fields under ``BOSState.causal``. Phase A's
flat-state pattern stays put for the 5 non-causal nodes (ser / sfi /
relay / cyber_lab / smalltalk); B4 does not refactor those into
slices. Plan v2 §3.1 Mod 10 reasoning: the slice grouping makes Phase
G session-restore code easier and keeps the top-level state model
readable when the 14 causal fields land.
"""

from __future__ import annotations

from typing import Annotated, Any, List, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from agent.schemas.causal.common import (
    CausalData,
    DagSpec,
)
from agent.schemas.causal.identify import CausalIdentifyResponse
from agent.schemas.causal.estimate import CausalEstimateResponse
from agent.schemas.causal.refute import CausalRefuteResponse
from agent.schemas.causal.mediation import CausalMediationResponse
from agent.schemas.causal.sensitivity import CausalSensitivityResponse


# ════════════════════════════════════════════════════════════════════
# BOSState (Plan v2 paragraph 3.1)
# ════════════════════════════════════════════════════════════════════

Intent = Literal[
    "ser",
    "sfi",
    "relay",
    "cyber_lab",
    "render",
    "noop",
    "smalltalk",
    # Phase B B4: causal intents (Plan v2 §3.5).
    "causal.ate",
    "causal.mediation",
    "causal.sensitivity",
    "causal.full",
]

EvidenceLevel = Literal["validated", "supported", "planned"]


class ToolCallRecord(TypedDict, total=False):
    """One audit record per Core HTTP tool invocation."""
    tool: str                       # ser_compute / sfi_check / relay_simulate / mc_propagate / twin_run
    endpoint: str                   # /api/v1/...
    started_at: str                 # ISO8601 UTC
    duration_ms: float
    status: Literal["ok", "error"]
    error: Optional[str]
    evidence_level: Optional[EvidenceLevel]


class ChartSpec(TypedDict, total=False):
    """Lightweight chart hint for the render node + frontend."""
    kind: Literal["line", "bar", "scatter", "trajectory"]
    title: str
    x: list[float]
    y: list[float]
    series: Optional[str]


class BOSState(TypedDict, total=False):
    """LangGraph state for the BOS Agent (Phase A).

    Every key is optional (``total=False``). Nodes write only the keys
    they own; everything else passes through untouched. ``messages``
    uses LangGraph's reducer so concurrent appends are safe.
    """

    # ---- conversation ----
    messages: Annotated[list[BaseMessage], add_messages]
    intent: Intent

    # ---- problem framing ----
    substrate_type: Optional[str]
    species_code: Optional[str]

    # ---- mass / nitrogen inputs ----
    dm_in: Optional[float]
    dm_out: Optional[float]
    n_in: Optional[float]
    n_rec: Optional[float]

    # ---- rate coefficients ----
    d_prime: Optional[float]
    g_prime: Optional[float]

    # ---- SER outcomes ----
    ser: Optional[float]
    ser_ci: Optional[tuple[float, float]]
    delta_ser: Optional[float]

    # ---- relay config ----
    tau_m2: Optional[float]
    k_decay: Optional[float]
    s0: Optional[float]
    s_min: Optional[float]
    tau_max: Optional[float]

    # ---- gating ----
    sfi_pass: Optional[bool]
    sfi_zone: Optional[str]

    # ---- simulation / experiment results ----
    simulation_result: Optional[dict[str, Any]]
    cyber_experiment: Optional[dict[str, Any]]

    # ---- rendering ----
    charts: Optional[list[ChartSpec]]
    report: Optional[str]

    # ---- audit ----
    tool_calls: list[ToolCallRecord]
    evidence_level: Optional[EvidenceLevel]

    # ---- Phase B B4 v2: causal subgraph slice (Mod 10) ----
    causal: Optional["CausalSlice"]


# ════════════════════════════════════════════════════════════════════
# CausalSlice (Plan v2 §3.1 Mod 10) — Phase B B4 v2 add-on
# ════════════════════════════════════════════════════════════════════


class CausalSlice(TypedDict, total=False):
    """Sub-TypedDict grouping causal-pipeline fields.

    Phase A keys stay flat on ``BOSState`` (26 fields). The 14 causal
    fields are nested here so the top-level state stays readable as
    Phase G work lands. Every key is optional (``total=False``); each
    causal node writes a strict subset.

    Field groups:

    - **Input** (set by router_node from the operator's payload):
      ``dag`` / ``data`` / ``treatment`` / ``outcome`` / ``mediators``.
    - **Result** (filled by each causal node on success):
      ``identify_result`` / ``estimate_result`` / ``refute_result`` /
      ``mediation_result`` / ``sensitivity_result``.
    - **Error / warning accumulation** (Plan v2 §3.3
      partial-failure):
      ``errors`` (identify / estimate failed -> subgraph short-circuits)
      vs ``warnings`` (refute / mediation / sensitivity failed -> the
      corresponding result is ``None`` but the chain continues).
    - **Render** (filled by render_node in Step 3):
      ``rendered`` markdown block.

    Note: the causal-node functions write a top-level
    ``{"causal": {...}}`` patch into the state. LangGraph's reducer
    will replace the whole ``causal`` slice each turn, so each node
    must spread the existing slice when augmenting it.
    """

    # ---- Input ----
    dag: DagSpec
    data: CausalData
    treatment: str
    outcome: str
    mediators: List[str]

    # ---- Result ----
    identify_result: CausalIdentifyResponse
    estimate_result: CausalEstimateResponse
    refute_result: Optional[CausalRefuteResponse]
    mediation_result: Optional[CausalMediationResponse]
    sensitivity_result: Optional[CausalSensitivityResponse]

    # ---- Error / warning accumulation ----
    errors: List[str]
    warnings: List[str]

    # ---- Render ----
    rendered: str
