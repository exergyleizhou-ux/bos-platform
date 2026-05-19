"""Async tool: POST /api/v1/causal/estimate."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.schemas.causal.estimate import (
    CausalEstimateRequest,
    CausalEstimateResponse,
)
from agent.tools.client import CORE_URL, ToolError, get_client


@tool
async def causal_estimate(req: CausalEstimateRequest) -> CausalEstimateResponse:
    """Estimate ATE / ATT / ATC via BOS Core
    (/api/v1/causal/estimate). When ``req.precomputed_estimand`` is
    set the engine skips re-identification — pass through the handle
    from the preceding identify result to avoid /identify and
    /estimate diverging on adjustment-set choices (Mod 4)."""
    endpoint = f"{CORE_URL}/causal/estimate"
    r = await get_client().post(endpoint, json=req.model_dump(mode="json"))
    if r.status_code != 200:
        raise ToolError("causal_estimate", endpoint, r.status_code, r.text)
    return CausalEstimateResponse.model_validate(r.json())
