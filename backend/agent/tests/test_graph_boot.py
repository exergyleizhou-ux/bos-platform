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


# ════════════════════════════════════════════════════════════════════
# Phase B B4 v2 causal-intent routing tests
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_graph_causal_ate_intent_routes_to_identify():
    """``causal.ate`` should pick up via keyword fallback. Without
    the dag/data/treatment/outcome inputs the identify node writes
    an error to ``state.causal.errors`` and the graph short-circuits
    to render (Plan v2 §3.3). The intent classification is what we
    pin here; the deeper happy path is exercised in B4 v2 Step 4
    completion + integration tests."""
    graph = build_graph(checkpointer=get_checkpointer())
    final = await graph.ainvoke(
        {
            "messages": [HumanMessage(
                content="what is the ATE of Signal-API on SER?",
            )],
            "tool_calls": [],
        },
        config={"configurable": {"thread_id": "t-causal-ate-1"}},
    )
    assert final.get("intent") == "causal.ate"
    # Identify should have written an error (missing prereqs) and
    # render should have produced a report mentioning the causal
    # error block.
    causal = final.get("causal") or {}
    assert causal.get("errors"), (
        f"identify_node should have written errors when prereqs "
        f"are missing; got causal={causal}"
    )
    assert "report" in final
    assert "Causal errors" in final["report"]


@pytest.mark.asyncio
async def test_graph_causal_mediation_intent_routes_to_identify():
    """``causal.mediation`` should be picked up by the keyword
    fallback (matches 'mediation' / 'proportion mediated')."""
    graph = build_graph(checkpointer=get_checkpointer())
    final = await graph.ainvoke(
        {
            "messages": [HumanMessage(
                content="proportion mediated of kappa pathway",
            )],
            "tool_calls": [],
        },
        config={"configurable": {"thread_id": "t-causal-med-1"}},
    )
    assert final.get("intent") == "causal.mediation"


@pytest.mark.asyncio
async def test_graph_causal_sensitivity_intent_routes_to_identify():
    """``causal.sensitivity`` — keyword 'E-value' / 'robustness'."""
    graph = build_graph(checkpointer=get_checkpointer())
    final = await graph.ainvoke(
        {
            "messages": [HumanMessage(
                content="how robust is this to unmeasured confounders",
            )],
            "tool_calls": [],
        },
        config={"configurable": {"thread_id": "t-causal-sens-1"}},
    )
    assert final.get("intent") == "causal.sensitivity"


@pytest.mark.asyncio
async def test_graph_causal_full_intent_routes_to_identify():
    """``causal.full`` — keyword 'explain in depth' / 'full causal'."""
    graph = build_graph(checkpointer=get_checkpointer())
    final = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="explain in depth")],
            "tool_calls": [],
        },
        config={"configurable": {"thread_id": "t-causal-full-1"}},
    )
    assert final.get("intent") == "causal.full"


@pytest.mark.asyncio
async def test_graph_causal_identify_happy_path(monkeypatch):
    """Mock the 5 causal @tool invocations so the identify -> estimate
    -> refute chain runs end-to-end without hitting the backend.

    Pins the structural contract: state.causal gets populated, the
    audit trail accumulates 2 ok records (identify + estimate +
    refute for causal.ate), and render produces a markdown report
    with the causal analysis block."""
    from datetime import datetime, timezone

    from agent.schemas.causal.common import (
        CausalData, DagEdge, DagNode, DagSpec,
        EstimateHandle, IdentifiedEstimandHandle,
    )
    from agent.schemas.causal.identify import CausalIdentifyResponse
    from agent.schemas.causal.estimate import (
        CausalEstimateResponse, EstimateDiagnostics,
    )
    from agent.schemas.causal.refute import (
        CausalRefuteResponse, RefuterResult,
    )
    from agent.nodes import (
        causal_identify as identify_mod,
        causal_estimate as estimate_mod,
        causal_refute as refute_mod,
    )

    # Build a minimal DagSpec + CausalData payload.
    dag = DagSpec(
        nodes=[
            DagNode(name="T", node_kind="treatment"),
            DagNode(name="Y", node_kind="outcome"),
            DagNode(name="Z", node_kind="covariate"),
        ],
        edges=[
            DagEdge(src="T", dst="Y"),
            DagEdge(src="Z", dst="T", edge_kind="confounding"),
            DagEdge(src="Z", dst="Y", edge_kind="confounding"),
        ],
        source="hand",
    )
    data = CausalData(
        inline=[{"T": 1.0, "Y": 2.0, "Z": 0.5}],
        fingerprint="0" * 16,
    )
    estimand_handle = IdentifiedEstimandHandle(
        strategy="backdoor",
        adjustment_set=["Z"],
        estimand_expression="E[Y|do(T)]",
        dataset_fingerprint=data.fingerprint,
    )
    estimate_handle = EstimateHandle(
        dag=dag,
        treatment="T",
        outcome="Y",
        method_family="linear_regression",
        method_params={},
        data=data,
        seed=42,
    )

    class _FakeIdentifyTool:
        async def ainvoke(self, _args):
            return CausalIdentifyResponse(
                identified=True, strategy="backdoor",
                adjustment_set=["Z"],
                estimand_expression="E[Y|do(T)]",
                assumptions=["no_unobserved_confounders"],
                estimand_handle=estimand_handle,
                evidence_level="supported",
                engine_version="0.9.0",
            )

    class _FakeEstimateTool:
        async def ainvoke(self, _args):
            return CausalEstimateResponse(
                point_estimate=2.0, ci_lower=1.8, ci_upper=2.2,
                std_error=0.1, method_used="linear_regression",
                n_used_per_stratum={"overall": 100},
                n_effective=100,
                heterogeneity_summary=None,
                e_value_cheap=3.1,
                estimate_handle=estimate_handle,
                diagnostics=EstimateDiagnostics(
                    method="linear_regression", n_samples=100,
                    n_treated=50, n_control=50,
                    n_continuous_covariates=1,
                    n_discrete_covariates=0,
                    cv_folds=None, fit_time_ms=5.0,
                    used_precomputed_estimand=True,
                ),
                evidence_level="supported",
                warnings=[],
                engine_version="0.9.0",
            )

    class _FakeRefuteTool:
        async def ainvoke(self, _args):
            return CausalRefuteResponse(
                refute_results=[
                    RefuterResult(
                        refuter="random_common_cause",
                        passed=True, p_value=0.5,
                        delta_estimate=0.01,
                        diagnostic="Refute: Add a random common cause",
                    ),
                ],
                overall_robust=True,
                evidence_level="validated",
                e_value_used=3.1,
                warnings=[],
                engine_version="0.9.0",
            )

    monkeypatch.setattr(identify_mod, "causal_identify", _FakeIdentifyTool())
    monkeypatch.setattr(estimate_mod, "causal_estimate", _FakeEstimateTool())
    monkeypatch.setattr(refute_mod, "causal_refute", _FakeRefuteTool())

    graph = build_graph(checkpointer=get_checkpointer())
    final = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="what is the ATE")],
            "tool_calls": [],
            "causal": {
                "dag": dag,
                "treatment": "T",
                "outcome": "Y",
                "data": data,
            },
        },
        config={"configurable": {"thread_id": "t-causal-happy-1"}},
    )

    assert final["intent"] == "causal.ate"
    causal = final.get("causal") or {}
    assert not causal.get("errors"), (
        f"happy path should not produce errors; got {causal.get('errors')}"
    )
    assert causal.get("identify_result") is not None
    assert causal.get("estimate_result") is not None
    assert causal.get("refute_result") is not None
    # Three ok ToolCallRecords (identify + estimate + refute).
    ok_calls = [
        r for r in final.get("tool_calls", []) if r.get("status") == "ok"
    ]
    assert len(ok_calls) == 3, (
        f"expected 3 ok tool calls (identify+estimate+refute), "
        f"got {len(ok_calls)}: {ok_calls}"
    )
    # Render produced the causal block.
    assert "Causal analysis" in final["report"]
    assert "ATE" in final["report"]
    # Mermaid block emitted.
    assert "```mermaid" in final["report"]
    assert "graph LR" in final["report"]
