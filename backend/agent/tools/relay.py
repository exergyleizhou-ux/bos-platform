"""Async tool: POST /api/v1/relay/simulate."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.schemas.relay import RelaySimulateRequest, RelaySimulateResponse
from agent.tools.client import CORE_URL, ToolError, get_client


@tool
async def relay_simulate(req: RelaySimulateRequest) -> RelaySimulateResponse:
    """Run M1->M2->M3 relay via BOS Core (/api/v1/relay/simulate)."""
    endpoint = f"{CORE_URL}/relay/simulate"
    r = await get_client().post(endpoint, json=req.model_dump(mode="json"))
    if r.status_code != 200:
        raise ToolError("relay_simulate", endpoint, r.status_code, r.text)
    return RelaySimulateResponse.model_validate(r.json())
