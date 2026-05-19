"""Async tool: POST /api/v1/causal/sensitivity."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.schemas.causal.sensitivity import (
    CausalSensitivityRequest,
    CausalSensitivityResponse,
)
from agent.tools.client import CORE_URL, ToolError, get_client


@tool
async def causal_sensitivity(
    req: CausalSensitivityRequest,
) -> CausalSensitivityResponse:
    """Bound the unmeasured-confounder bias on the estimate referenced
    by ``req.estimate_handle``. Two methods: ``evalue`` (default,
    DoWhy class + Chinn-VWD fallback) / ``linear`` (Cinelli-Hazlett
    closed-form). ``partial_linear`` is reserved at the engine."""
    endpoint = f"{CORE_URL}/causal/sensitivity"
    r = await get_client().post(endpoint, json=req.model_dump(mode="json"))
    if r.status_code != 200:
        raise ToolError(
            "causal_sensitivity", endpoint, r.status_code, r.text,
        )
    return CausalSensitivityResponse.model_validate(r.json())
