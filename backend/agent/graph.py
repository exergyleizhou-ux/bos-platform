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

Every node returns a dict patch into BOSState; render_node writes the
markdown report into state["report"].
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    cyber_lab_node,
    relay_node,
    render_node,
    router_node,
    ser_node,
    sfi_node,
)
from agent.persistence import get_checkpointer
from agent.state import BOSState


_INTENT_TO_NODE: dict[str, str] = {
    "ser": "ser",
    "sfi": "sfi",
    "relay": "relay",
    "cyber_lab": "cyber_lab",
    # render / smalltalk / noop all short-circuit to render
    "render": "render",
    "smalltalk": "render",
    "noop": "render",
}


def _route_from_intent(state: BOSState) -> Literal[
    "ser", "sfi", "relay", "cyber_lab", "render"
]:
    intent = state.get("intent", "noop")
    return _INTENT_TO_NODE.get(intent, "render")  # type: ignore[return-value]


def build_graph(checkpointer=None):
    """Build and return a compiled LangGraph StateGraph.

    The default checkpointer comes from ``agent.persistence.get_checkpointer``
    (Phase A = InMemorySaver). Pass an explicit override for tests.
    """
    g = StateGraph(BOSState)
    g.add_node("router", router_node)
    g.add_node("ser", ser_node)
    g.add_node("sfi", sfi_node)
    g.add_node("relay", relay_node)
    g.add_node("cyber_lab", cyber_lab_node)
    g.add_node("render", render_node)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        _route_from_intent,
        {
            "ser": "ser",
            "sfi": "sfi",
            "relay": "relay",
            "cyber_lab": "cyber_lab",
            "render": "render",
        },
    )
    g.add_edge("ser", "render")
    g.add_edge("sfi", "render")
    g.add_edge("relay", "render")
    g.add_edge("cyber_lab", "render")
    g.add_edge("render", END)

    return g.compile(checkpointer=checkpointer or get_checkpointer())
