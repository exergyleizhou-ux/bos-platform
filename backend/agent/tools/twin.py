"""Async tool: POST /api/v1/twin/run."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.schemas.twin import TwinRunRequest, TwinRunResponse
from agent.tools.client import CORE_URL, ToolError, get_client


@tool
async def twin_run(req: TwinRunRequest) -> TwinRunResponse:
    """Run the stateless digital twin via BOS Core (/api/v1/twin/run)."""
    endpoint = f"{CORE_URL}/twin/run"
    r = await get_client().post(endpoint, json=req.model_dump(mode="json"))
    if r.status_code != 200:
        raise ToolError("twin_run", endpoint, r.status_code, r.text)
    return TwinRunResponse.model_validate(r.json())
