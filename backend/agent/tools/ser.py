"""Async tool: POST /api/v1/ser/compute."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.schemas.ser import SerComputeRequest, SerComputeResponse
from agent.tools.client import CORE_URL, ToolError, get_client


@tool
async def ser_compute(req: SerComputeRequest) -> SerComputeResponse:
    """Compute SER + Monte Carlo CI via BOS Core (/api/v1/ser/compute)."""
    endpoint = f"{CORE_URL}/ser/compute"
    r = await get_client().post(endpoint, json=req.model_dump(mode="json"))
    if r.status_code != 200:
        raise ToolError("ser_compute", endpoint, r.status_code, r.text)
    return SerComputeResponse.model_validate(r.json())
