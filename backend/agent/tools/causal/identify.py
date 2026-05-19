"""Async tool: POST /api/v1/causal/identify."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.schemas.causal.identify import (
    CausalIdentifyRequest,
    CausalIdentifyResponse,
)
from agent.tools.client import CORE_URL, ToolError, get_client


@tool
async def causal_identify(req: CausalIdentifyRequest) -> CausalIdentifyResponse:
    """Identify the causal estimand (backdoor / frontdoor / IV / mediation)
    via BOS Core (/api/v1/causal/identify). Returns the estimand handle
    that downstream nodes (estimate, mediation) can echo back as
    ``precomputed_estimand``."""
    endpoint = f"{CORE_URL}/causal/identify"
    r = await get_client().post(endpoint, json=req.model_dump(mode="json"))
    if r.status_code != 200:
        raise ToolError("causal_identify", endpoint, r.status_code, r.text)
    return CausalIdentifyResponse.model_validate(r.json())
