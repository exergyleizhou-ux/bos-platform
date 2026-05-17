"""BOS Agent - LangGraph state schema.

Plan v2 paragraph 3.1 defines ``BOSState`` as the typed dict that flows
through the StateGraph. Every node reads from + writes to a strict
subset of these keys.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ════════════════════════════════════════════════════════════════════
# BOSState (Plan v2 paragraph 3.1)
# ════════════════════════════════════════════════════════════════════

Intent = Literal[
    "ser", "sfi", "relay", "cyber_lab", "render", "noop", "smalltalk",
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
