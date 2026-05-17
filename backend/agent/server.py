"""BOS Agent - FastAPI HTTP server (port 8001 by default).

Endpoints:
    GET  /agent/health      ->  {"status": "ok", ...}
    POST /agent/runs        ->  start a new run and return its result
                                synchronously (Phase A simplification;
                                A4/A5 may add SSE streaming).

This module MUST NOT import ``app.*``. A grep test in
``agent/tests/test_isolation.py`` enforces the rule.
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ConfigDict, Field

from agent.graph import build_graph
from agent.state import BOSState
from agent.tools.client import CORE_URL, close_client


# ---- request / response models ---------------------------------------


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(..., min_length=1, max_length=4_000)
    # Optional pre-seeded state fields (Phase A escape hatch so callers
    # can hand the agent the SER inputs directly without parsing prose).
    state: dict[str, Any] = Field(default_factory=dict)
    thread_id: str | None = Field(default=None, max_length=128)


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thread_id: str
    intent: str | None = None
    report: str | None = None
    ser: float | None = None
    sfi_pass: bool | None = None
    sfi_zone: str | None = None
    simulation_result: dict[str, Any] | None = None
    cyber_experiment: dict[str, Any] | None = None
    evidence_level: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


# ---- lifespan: build graph once + close shared httpx client ----------


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.graph = build_graph()
    try:
        yield
    finally:
        await close_client()


app = FastAPI(
    title="BOS Agent",
    version="A.3",
    description=(
        "Independent LangGraph-backed agent process. Talks to BOS Core "
        "(default http://localhost:8000/api/v1) over HTTP only."
    ),
    lifespan=_lifespan,
)


@app.get("/agent/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "bos-agent",
        "version": app.version,
        "core_url": CORE_URL,
    }


@app.post("/agent/runs", response_model=AgentRunResponse)
async def create_run(body: AgentRunRequest) -> AgentRunResponse:
    """Start a new agent run and return the final state."""
    thread_id = body.thread_id or f"run-{uuid.uuid4().hex[:12]}"
    initial_state: BOSState = {
        "messages": [HumanMessage(content=body.message)],
        "tool_calls": [],
    }
    # Merge any caller-supplied scalar inputs (SER fields, species, ...)
    for k, v in body.state.items():
        initial_state[k] = v  # type: ignore[literal-required]

    graph = app.state.graph
    final_state = await graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": thread_id}},
    )

    return AgentRunResponse(
        thread_id=thread_id,
        intent=final_state.get("intent"),
        report=final_state.get("report"),
        ser=final_state.get("ser"),
        sfi_pass=final_state.get("sfi_pass"),
        sfi_zone=final_state.get("sfi_zone"),
        simulation_result=final_state.get("simulation_result"),
        cyber_experiment=final_state.get("cyber_experiment"),
        evidence_level=final_state.get("evidence_level"),
        tool_calls=list(final_state.get("tool_calls") or []),
    )
