"""Async tool: POST /api/v1/mc/propagate."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.schemas.mc import McPropagateRequest, McPropagateResponse
from agent.tools.client import CORE_URL, ToolError, get_client


@tool
async def mc_propagate(req: McPropagateRequest) -> McPropagateResponse:
    """Run generic MC propagation via BOS Core (/api/v1/mc/propagate)."""
    endpoint = f"{CORE_URL}/mc/propagate"
    r = await get_client().post(endpoint, json=req.model_dump(mode="json"))
    if r.status_code != 200:
        raise ToolError("mc_propagate", endpoint, r.status_code, r.text)
    return McPropagateResponse.model_validate(r.json())
