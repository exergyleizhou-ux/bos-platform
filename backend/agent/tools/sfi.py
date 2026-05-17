"""Async tool: POST /api/v1/sfi/check."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.schemas.sfi import SfiCheckRequest, SfiCheckResponse
from agent.tools.client import CORE_URL, ToolError, get_client


@tool
async def sfi_check(req: SfiCheckRequest) -> SfiCheckResponse:
    """Verify operating envelope via BOS Core (/api/v1/sfi/check)."""
    endpoint = f"{CORE_URL}/sfi/check"
    r = await get_client().post(endpoint, json=req.model_dump(mode="json"))
    if r.status_code != 200:
        raise ToolError("sfi_check", endpoint, r.status_code, r.text)
    return SfiCheckResponse.model_validate(r.json())
