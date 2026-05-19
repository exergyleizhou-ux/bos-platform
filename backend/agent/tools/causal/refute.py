"""Async tool: POST /api/v1/causal/refute."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.schemas.causal.refute import (
    CausalRefuteRequest,
    CausalRefuteResponse,
)
from agent.tools.client import CORE_URL, ToolError, get_client


@tool
async def causal_refute(req: CausalRefuteRequest) -> CausalRefuteResponse:
    """Run DoWhy refuters against the estimate referenced by
    ``req.estimate_handle`` (echoed from the preceding /estimate
    response). Returns per-refuter verdicts plus an aggregated
    ``evidence_level`` per Plan v2 §2.3 patched rule."""
    endpoint = f"{CORE_URL}/causal/refute"
    r = await get_client().post(endpoint, json=req.model_dump(mode="json"))
    if r.status_code != 200:
        raise ToolError("causal_refute", endpoint, r.status_code, r.text)
    return CausalRefuteResponse.model_validate(r.json())
