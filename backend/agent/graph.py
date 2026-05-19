"""BOS Agent - LangGraph StateGraph wiring.

Topology (Plan v2 paragraph 3.2):

    START
      |
      v
    router_node
      |  (conditional edges keyed on state["intent"])
      +-> ser_node       -> render_node -> END
      +-> sfi_node       -> render_node -> END
      +-> relay_node     -> render_node -> END
      +-> cyber_lab_node -> render_node -> END
      +-> render_node    -> END   (smalltalk / noop / render)
      +-> causal_identify_node ─┐
                                 v
                          causal_estimate_node ─┐
                                                 v
                                  +─-> causal_refute_node          ─┐
                                  +─-> causal_mediation_dispatcher  ─┤
                                  +─-> causal_sensitivity_node     ─┼─> render_node -> END
                                  +─-> causal_fanout_full          ─┘

Every node returns a dict patch into BOSState; render_node writes the
markdown report into state["report"].

Phase B B4 v2 (Plan v2 §3.2, §3.3): the causal sub-cascade goes
identify → estimate → (intent-driven dispatch) → render. Failures
in identify/estimate write to ``state.causal.errors`` and short-
circuit to render via the ``_check_causal_errors`` conditional
edge; failures in refute/mediation/sensitivity write to
``state.causal.warnings`` and continue (set the matching ``*_result``
to ``None``). The ``causal.mediation`` intent does parallel refute +
mediation via ``asyncio.gather`` (Plan v2 §3.2 fanout); the
``causal.full`` intent does parallel refute + mediation +
sensitivity.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    causal_estimate_node,
    causal_identify_node,
    causal_mediation_node,
    causal_refute_node,
    causal_sensitivity_node,
    cyber_lab_node,
    relay_node,
    render_node,
    router_node,
    ser_node,
    sfi_node,
)
from agent.persistence import get_checkpointer
from agent.state import BOSState


# ════════════════════════════════════════════════════════════════════
# Intent → entry-node routing (Plan v2 §3.2)
# ════════════════════════════════════════════════════════════════════


_INTENT_TO_NODE: dict[str, str] = {
    # Phase A intents.
    "ser": "ser",
    "sfi": "sfi",
    "relay": "relay",
    "cyber_lab": "cyber_lab",
    # render / smalltalk / noop all short-circuit to render
    "render": "render",
    "smalltalk": "render",
    "noop": "render",
    # Phase B B4 v2 causal intents — all entry through identify.
    # The downstream dispatcher (after estimate) reads the same
    # ``state.intent`` to pick refute / mediation / sensitivity /
    # fanout.
    "causal.ate": "causal_identify",
    "causal.mediation": "causal_identify",
    "causal.sensitivity": "causal_identify",
    "causal.full": "causal_identify",
}


def _route_from_intent(state: BOSState) -> Literal[
    "ser", "sfi", "relay", "cyber_lab", "render", "causal_identify"
]:
    intent = state.get("intent", "noop")
    return _INTENT_TO_NODE.get(intent, "render")  # type: ignore[return-value]


# ════════════════════════════════════════════════════════════════════
# Causal subgraph conditional edges (Plan v2 §3.2 + §3.3)
# ════════════════════════════════════════════════════════════════════


def _check_causal_errors_after_identify(state: BOSState) -> Literal[
    "causal_estimate", "render"
]:
    """If identify failed (wrote to ``state.causal.errors``), short-
    circuit to render; otherwise advance to estimate."""
    causal = state.get("causal") or {}
    if causal.get("errors"):
        return "render"
    if causal.get("identify_result") is None:
        # Defensive: identify did not write a result and didn't push
        # an error either — treat as soft failure, short-circuit.
        return "render"
    return "causal_estimate"


def _dispatch_after_estimate(state: BOSState) -> Literal[
    "causal_refute",
    "causal_mediation_dispatch",
    "causal_sensitivity",
    "causal_fanout_full",
    "render",
]:
    """Branch on intent after estimate succeeds.

    Plan v2 §3.2:
      - ``causal.ate``         → refute → render
      - ``causal.mediation``   → parallel(refute, mediation) → render
      - ``causal.sensitivity`` → sensitivity → render
      - ``causal.full``        → parallel(refute, mediation, sensitivity)
                                 → render
    """
    causal = state.get("causal") or {}
    if causal.get("errors"):
        return "render"
    if causal.get("estimate_result") is None:
        return "render"

    intent = state.get("intent", "noop")
    if intent == "causal.mediation":
        return "causal_mediation_dispatch"
    if intent == "causal.sensitivity":
        return "causal_sensitivity"
    if intent == "causal.full":
        return "causal_fanout_full"
    # Default for causal.ate (and any other causal intent leak).
    return "causal_refute"


# ════════════════════════════════════════════════════════════════════
# Fanout nodes (asyncio.gather)
# ════════════════════════════════════════════════════════════════════


def _merge_partial_patches(
    state: BOSState,
    patches: list[dict[str, Any] | BaseException],
) -> dict[str, Any]:
    """Merge an ``asyncio.gather(return_exceptions=True)`` payload.

    The five causal nodes all return dict patches with this shape::

        {
            "causal": {<merged into state.causal>},
            "tool_calls": [<extended audit list>],
            "evidence_level": <optional>,
        }

    A bare exception means the node itself raised (which our nodes
    don't, since refute/mediation/sensitivity catch and warn-and-
    continue). Defensive treatment: append the exception to
    ``state.causal.warnings`` and treat as a partial-failure.
    """
    base_causal = dict(state.get("causal") or {})
    tool_calls = list(state.get("tool_calls") or [])
    evidence_level: str | None = state.get("evidence_level")

    for patch in patches:
        if isinstance(patch, BaseException):
            base_causal.setdefault("warnings", [])
            base_causal["warnings"].append(
                f"fanout node raised: {type(patch).__name__}: "
                f"{str(patch)[:200]}"
            )
            continue
        # Merge the node-emitted causal dict into the running base.
        node_causal = patch.get("causal") or {}
        for key, value in node_causal.items():
            if key == "warnings":
                existing = base_causal.get("warnings") or []
                base_causal["warnings"] = list(existing) + list(value or [])
            elif key == "errors":
                existing = base_causal.get("errors") or []
                base_causal["errors"] = list(existing) + list(value or [])
            else:
                base_causal[key] = value
        # Tool-call records.
        for record in (patch.get("tool_calls") or [])[len(tool_calls):]:
            tool_calls.append(record)
        # Evidence level: keep the strongest tier (validated >
        # supported > planned). For Phase B B4 v2 we just take
        # whatever the latest node emitted — render decides what to
        # surface.
        if patch.get("evidence_level"):
            evidence_level = patch["evidence_level"]

    merged: dict[str, Any] = {
        "causal": base_causal,
        "tool_calls": tool_calls,
    }
    if evidence_level is not None:
        merged["evidence_level"] = evidence_level
    return merged


async def causal_mediation_dispatch_node(state: BOSState) -> dict[str, Any]:
    """``causal.mediation`` fanout: parallel refute + mediation.

    Plan v2 §3.2: "estimate -> mediation -> refute (in parallel via
    asyncio.gather inside a router edge) -> render". Both are
    partial-failure-tolerant per §3.3.
    """
    results = await asyncio.gather(
        causal_refute_node(state),
        causal_mediation_node(state),
        return_exceptions=True,
    )
    return _merge_partial_patches(state, list(results))


async def causal_fanout_full_node(state: BOSState) -> dict[str, Any]:
    """``causal.full`` fanout: parallel refute + mediation + sensitivity.

    Plan v2 §3.2: "estimate -> asyncio.gather(refute, mediation,
    sensitivity) -> render". All three are partial-failure-tolerant.
    """
    results = await asyncio.gather(
        causal_refute_node(state),
        causal_mediation_node(state),
        causal_sensitivity_node(state),
        return_exceptions=True,
    )
    return _merge_partial_patches(state, list(results))


# ════════════════════════════════════════════════════════════════════
# Graph builder
# ════════════════════════════════════════════════════════════════════


def build_graph(checkpointer=None):
    """Build and return a compiled LangGraph StateGraph.

    The default checkpointer comes from ``agent.persistence.get_checkpointer``
    (Phase A = InMemorySaver). Pass an explicit override for tests.
    """
    g = StateGraph(BOSState)

    # Phase A nodes.
    g.add_node("router", router_node)
    g.add_node("ser", ser_node)
    g.add_node("sfi", sfi_node)
    g.add_node("relay", relay_node)
    g.add_node("cyber_lab", cyber_lab_node)
    g.add_node("render", render_node)

    # Phase B B4 v2 causal nodes.
    g.add_node("causal_identify", causal_identify_node)
    g.add_node("causal_estimate", causal_estimate_node)
    g.add_node("causal_refute", causal_refute_node)
    g.add_node("causal_sensitivity", causal_sensitivity_node)
    g.add_node("causal_mediation_dispatch", causal_mediation_dispatch_node)
    g.add_node("causal_fanout_full", causal_fanout_full_node)

    # Entry edge: START -> router.
    g.add_edge(START, "router")

    # Phase A intent routing.
    g.add_conditional_edges(
        "router",
        _route_from_intent,
        {
            "ser": "ser",
            "sfi": "sfi",
            "relay": "relay",
            "cyber_lab": "cyber_lab",
            "render": "render",
            "causal_identify": "causal_identify",
        },
    )
    g.add_edge("ser", "render")
    g.add_edge("sfi", "render")
    g.add_edge("relay", "render")
    g.add_edge("cyber_lab", "render")

    # Causal subgraph: identify -> (error check) -> estimate ->
    # (intent dispatch) -> refute/mediation_dispatch/sensitivity/
    # fanout_full -> render.
    g.add_conditional_edges(
        "causal_identify",
        _check_causal_errors_after_identify,
        {
            "causal_estimate": "causal_estimate",
            "render": "render",
        },
    )
    g.add_conditional_edges(
        "causal_estimate",
        _dispatch_after_estimate,
        {
            "causal_refute": "causal_refute",
            "causal_mediation_dispatch": "causal_mediation_dispatch",
            "causal_sensitivity": "causal_sensitivity",
            "causal_fanout_full": "causal_fanout_full",
            "render": "render",
        },
    )
    g.add_edge("causal_refute", "render")
    g.add_edge("causal_sensitivity", "render")
    g.add_edge("causal_mediation_dispatch", "render")
    g.add_edge("causal_fanout_full", "render")

    g.add_edge("render", END)

    return g.compile(checkpointer=checkpointer or get_checkpointer())
