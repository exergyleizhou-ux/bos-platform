"""Graph + server boot smoke tests.

Phase A floor: the graph compiles, accepts a state, and produces a
``report``. No real Core API key is needed because:
- router falls back to the deterministic keyword classifier when
  ANTHROPIC_API_KEY is unset / ``AGENT_ROUTER_USE_LLM=0``.
- smalltalk / noop intents short-circuit to render_node (no HTTP).
- where HTTP would happen, we patch the tool functions so the smoke
  test is hermetic.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from agent.graph import build_graph
from agent.persistence import get_checkpointer


@pytest.fixture(autouse=True)
def _force_keyword_router(monkeypatch):
    """Bypass the LLM in router_node for the entire module."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("AGENT_ROUTER_USE_LLM", "0")


# ════════════════════════════════════════════════════════════════════
# Graph compiles and runs end-to-end on a smalltalk message
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_graph_compiles():
    graph = build_graph(checkpointer=get_checkpointer())
    # Compiled CompiledGraph has ``ainvoke``.
    assert hasattr(graph, "ainvoke")


@pytest.mark.asyncio
async def test_graph_smalltalk_path_produces_report():
    graph = build_graph(checkpointer=get_checkpointer())
    final = await graph.ainvoke(
        {"messages": [HumanMessage(content="hi there")], "tool_calls": []},
        config={"configurable": {"thread_id": "t-smalltalk-1"}},
    )
    assert final.get("intent") == "smalltalk"
    assert isinstance(final.get("report"), str)
    assert "BOS Agent run summary" in final["report"]


@pytest.mark.asyncio
async def test_graph_noop_path_produces_report():
    graph = build_graph(checkpointer=get_checkpointer())
    final = await graph.ainvoke(
        {"messages": [HumanMessage(content="qwerty random words")],
         "tool_calls": []},
        config={"configurable": {"thread_id": "t-noop-1"}},
    )
    assert final.get("intent") == "noop"
    assert "report" in final


@pytest.mark.asyncio
async def test_graph_ser_intent_routes_through_ser_node(monkeypatch):
    """SER intent should hit ser_node; we patch the tool so the test is
    hermetic and verify the audit record is appended."""
    from agent.schemas.ser import SerComputeResponse
    from agent.nodes import ser as ser_node_mod

    class _FakeTool:
        async def ainvoke(self, _args):
            return SerComputeResponse(
                ser_point=0.25, ser_ci_lower=0.20, ser_ci_upper=0.30,
                ser_std=0.03, delta_ser=None, engine_version="9.0.0",
                monte_carlo=None, evidence_level="supported",
            )

    # Replace the ``ser_compute`` symbol imported by the node module
    # (StructuredTool itself is a frozen Pydantic model).
    monkeypatch.setattr(ser_node_mod, "ser_compute", _FakeTool())

    graph = build_graph(checkpointer=get_checkpointer())
    final = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="please compute SER for batch")],
            "tool_calls": [],
            "dm_in": 10.0, "dm_out": 2.5,
            "n_in": 1.0, "n_rec": 0.3,
            "d_prime": 0.7, "g_prime": 0.6,
            "species_code": "BSF_LARVA",
        },
        config={"configurable": {"thread_id": "t-ser-1"}},
    )
    assert final["intent"] == "ser"
    assert final["ser"] == pytest.approx(0.25)
    # at least one ok ToolCallRecord present
    assert any(rec.get("tool") == "ser_compute" and rec.get("status") == "ok"
               for rec in final.get("tool_calls", []))
    assert "SER" in final["report"]


# ════════════════════════════════════════════════════════════════════
# FastAPI server boots and answers /agent/health
# ════════════════════════════════════════════════════════════════════


def test_server_health_endpoint():
    from agent.server import app as agent_app

    with TestClient(agent_app) as client:
        r = client.get("/agent/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["service"] == "bos-agent"
        assert body["version"]
        assert "core_url" in body


def test_server_creates_run_for_smalltalk(monkeypatch):
    """End-to-end via FastAPI: send a smalltalk message, expect a run
    response with a report and the correct intent."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("AGENT_ROUTER_USE_LLM", "0")
    from agent.server import app as agent_app

    with TestClient(agent_app) as client:
        r = client.post("/agent/runs", json={"message": "hello"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["intent"] == "smalltalk"
        assert body["report"] and "BOS Agent run summary" in body["report"]
        assert body["thread_id"]
