"""Async tool: POST /api/v1/causal/mediation."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.schemas.causal.mediation import (
    CausalMediationRequest,
    CausalMediationResponse,
)
from agent.tools.client import CORE_URL, ToolError, get_client


@tool
async def causal_mediation(
    req: CausalMediationRequest,
) -> CausalMediationResponse:
    """Run Pearl/Rubin mediation decomposition via BOS Core
    (/api/v1/causal/mediation). D14: NOT Baron-Kenny — mediation
    re-fits estimation internally. Pass
    ``req.precomputed_estimand`` (IdentifiedEstimandHandle from
    /identify) to skip identification, but NOT
    ``estimate_handle`` (mediation does not consume that)."""
    endpoint = f"{CORE_URL}/causal/mediation"
    r = await get_client().post(endpoint, json=req.model_dump(mode="json"))
    if r.status_code != 200:
        raise ToolError("causal_mediation", endpoint, r.status_code, r.text)
    return CausalMediationResponse.model_validate(r.json())
