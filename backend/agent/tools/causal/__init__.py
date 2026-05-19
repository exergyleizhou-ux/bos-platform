"""Async tools for ``POST /api/v1/causal/*`` endpoints (Phase B B4 v2).

Five tools wrap the five Phase B causal endpoints (identify, estimate,
refute, mediation, sensitivity). They share the process-wide
``httpx.AsyncClient`` from ``agent.tools.client`` and follow the
Phase A 3-layer pattern (tools / nodes / audit).

The ``@tool`` decorator (langchain_core.tools) registers each
function so the agent's render path can name it in tool_calls
audit. Each tool raises ``ToolError`` on non-2xx HTTP; partial-
failure logic (decide whether to abort the subgraph or downgrade
evidence_level) lives in the corresponding node, not in the tool.
"""

from agent.tools.causal.identify import causal_identify
from agent.tools.causal.estimate import causal_estimate
from agent.tools.causal.refute import causal_refute
from agent.tools.causal.mediation import causal_mediation
from agent.tools.causal.sensitivity import causal_sensitivity

__all__ = [
    "causal_identify",
    "causal_estimate",
    "causal_refute",
    "causal_mediation",
    "causal_sensitivity",
]
