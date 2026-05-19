"""BOS Agent - LangGraph node implementations.

Async node functions, each ``async def fn(state: BOSState) -> dict``
returning only the state keys it owns. The graph in ``agent.graph``
wires them in sequence with conditional edges from router_node.

Phase A nodes (6): router / ser / sfi / relay / cyber_lab / render.
Phase B B4 v2 causal nodes (5): causal_identify / causal_estimate /
causal_refute / causal_mediation / causal_sensitivity. Per Plan v2
§3.3 partial-failure semantics, the causal nodes write
errors/warnings into ``state.causal`` rather than raising — the
graph's conditional edge checks ``state.causal.errors`` to decide
whether to short-circuit.
"""

from agent.nodes.router import router_node
from agent.nodes.ser import ser_node
from agent.nodes.sfi import sfi_node
from agent.nodes.relay import relay_node
from agent.nodes.cyber_lab import cyber_lab_node
from agent.nodes.render import render_node

# Phase B B4 v2 causal nodes.
from agent.nodes.causal_identify import causal_identify_node
from agent.nodes.causal_estimate import causal_estimate_node
from agent.nodes.causal_refute import causal_refute_node
from agent.nodes.causal_mediation import causal_mediation_node
from agent.nodes.causal_sensitivity import causal_sensitivity_node

__all__ = [
    "router_node",
    "ser_node",
    "sfi_node",
    "relay_node",
    "cyber_lab_node",
    "render_node",
    "causal_identify_node",
    "causal_estimate_node",
    "causal_refute_node",
    "causal_mediation_node",
    "causal_sensitivity_node",
]
