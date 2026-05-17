"""Phase A — Agent ↔ Core end-to-end integration tests (Batch A4).

These tests run **both** services in-process:
- BOS Core is mounted via FastAPI's ASGI app (no real :8000 listener).
- BOS Agent's shared ``httpx.AsyncClient`` is swapped for one whose
  ``transport`` is an ``ASGITransport`` over the same Core app.
- ``agent.tools.{ser,sfi,relay,mc,twin}.CORE_URL`` is monkeypatched to
  the test base URL so the tools build the right paths.

The result: when the agent graph runs, every Core call goes through
the real BOS Core stack (Pydantic validation + engines + middleware),
but no real network port is opened. This is hermetic, deterministic,
and exercises the same code paths as a two-process deployment.

Plan v2 §5 Batch A4 + §7 acceptance criteria #4–5.
"""

from __future__ import annotations

import os
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import HumanMessage

from app.main import app as core_app
from agent import tools as agent_tools_pkg
from agent.graph import build_graph
from agent.persistence import get_checkpointer
from agent.tools import client as agent_client_mod
from agent.tools import ser as tool_ser_mod
from agent.tools import sfi as tool_sfi_mod
from agent.tools import relay as tool_relay_mod
from agent.tools import mc as tool_mc_mod
from agent.tools import twin as tool_twin_mod


# ════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _force_keyword_router(monkeypatch):
    """Router never calls the LLM in e2e tests."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("AGENT_ROUTER_USE_LLM", "0")


@pytest_asyncio.fixture
async def core_asgi_client(operator_headers) -> AsyncGenerator[AsyncClient, None]:
    """Build an httpx.AsyncClient bound to Core via ASGITransport.

    Uses the operator JWT from conftest so calls to ``require_minimum_role
    ("operator")`` succeed.
    """
    transport = ASGITransport(app=core_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://e2e-core",
        headers=operator_headers,
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def agent_wired_to_core(core_asgi_client, monkeypatch):
    """Install the ASGI-bound client into the agent's tools layer.

    All five tools (ser/sfi/relay/mc/twin) have their CORE_URL patched
    to point at the test base. The shared singleton is replaced for the
    duration of the test, then restored.
    """
    base_url = "http://e2e-core/api/v1"
    monkeypatch.setattr(tool_ser_mod, "CORE_URL", base_url)
    monkeypatch.setattr(tool_sfi_mod, "CORE_URL", base_url)
    monkeypatch.setattr(tool_relay_mod, "CORE_URL", base_url)
    monkeypatch.setattr(tool_mc_mod, "CORE_URL", base_url)
    monkeypatch.setattr(tool_twin_mod, "CORE_URL", base_url)
    # Also patch the node modules — they import CORE_URL eagerly for
    # error-record endpoints.
    from agent.nodes import ser as node_ser_mod
    from agent.nodes import sfi as node_sfi_mod
    from agent.nodes import relay as node_relay_mod
    from agent.nodes import cyber_lab as node_cyber_mod
    for nm in (node_ser_mod, node_sfi_mod, node_relay_mod, node_cyber_mod):
        if hasattr(nm, "CORE_URL"):
            monkeypatch.setattr(nm, "CORE_URL", base_url)

    agent_client_mod.set_client(core_asgi_client)
    try:
        yield
    finally:
        agent_client_mod.set_client(None)


@pytest.fixture
def graph():
    return build_graph(checkpointer=get_checkpointer())


def _ser_state(**o) -> dict[str, Any]:
    base = dict(
        messages=[HumanMessage(content="please compute SER")],
        tool_calls=[],
        dm_in=10.0,
        dm_out=2.5,
        n_in=1.0,
        n_rec=0.3,
        d_prime=0.7,
        g_prime=0.6,
        species_code="BSF_LARVA",
    )
    base.update(o)
    return base


# ════════════════════════════════════════════════════════════════════
# SER: agent → Core via HTTP matches a direct Core call
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ser_value_matches_direct_core_call(
    agent_wired_to_core, graph, core_asgi_client
):
    state = _ser_state()
    final = await graph.ainvoke(
        state,
        config={"configurable": {"thread_id": "e2e-ser-match"}},
    )
    agent_ser = final.get("ser")
    assert agent_ser is not None, final

    # Now hit Core directly with the same payload.
    direct = await core_asgi_client.post(
        "/api/v1/ser/compute",
        json={
            "dm_in": state["dm_in"],
            "dm_out": state["dm_out"],
            "n_in": state["n_in"],
            "n_rec": state["n_rec"],
            "d_prime": state["d_prime"],
            "g_prime": state["g_prime"],
            "species_code": state["species_code"],
        },
    )
    assert direct.status_code == 200, direct.text
    direct_ser = direct.json()["ser_point"]
    assert agent_ser == pytest.approx(direct_ser, abs=1e-6)


@pytest.mark.asyncio
async def test_ser_tool_call_record_marked_ok(agent_wired_to_core, graph):
    final = await graph.ainvoke(
        _ser_state(),
        config={"configurable": {"thread_id": "e2e-ser-audit"}},
    )
    records = final.get("tool_calls") or []
    ser_records = [r for r in records if r.get("tool") == "ser_compute"]
    assert ser_records, records
    assert all(r["status"] == "ok" for r in ser_records)
    assert all(r.get("duration_ms", 0) > 0 for r in ser_records)


@pytest.mark.asyncio
async def test_ser_evidence_level_propagated(agent_wired_to_core, graph):
    final = await graph.ainvoke(
        _ser_state(),
        config={"configurable": {"thread_id": "e2e-ser-evidence"}},
    )
    # SER without MC → Core returns evidence_level="supported"
    assert final.get("evidence_level") == "supported"


# ════════════════════════════════════════════════════════════════════
# Cyber-lab: parallel SER + MC, both audit records, evidence_level
# downgraded by the MC branch's "planned" sobol/non-ser placeholder
# (or stays supported when MC target=ser and no sobol).
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_cyber_lab_runs_both_branches(agent_wired_to_core, graph):
    state = _ser_state(messages=[HumanMessage(content="compare scenarios")])
    final = await graph.ainvoke(
        state,
        config={"configurable": {"thread_id": "e2e-cyber-1"}},
    )
    assert final.get("intent") == "cyber_lab"
    records = final.get("tool_calls") or []
    tools_hit = {r["tool"] for r in records if r.get("status") == "ok"}
    assert "ser_compute" in tools_hit
    assert "mc_propagate" in tools_hit
    cyber = final.get("cyber_experiment") or {}
    assert "baseline_ser" in cyber
    assert "mc_target_mean" in cyber
    assert "mc_ci" in cyber


@pytest.mark.asyncio
async def test_cyber_lab_report_mentions_both_results(agent_wired_to_core, graph):
    final = await graph.ainvoke(
        _ser_state(messages=[HumanMessage(content="compare scenarios")]),
        config={"configurable": {"thread_id": "e2e-cyber-report"}},
    )
    report = final.get("report") or ""
    assert "Cyber lab baseline SER" in report
    assert "Cyber lab MC mean" in report


# ════════════════════════════════════════════════════════════════════
# Error injection: Core returns 422 → agent records status="error"
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ser_invalid_input_records_error(agent_wired_to_core, graph):
    """dm_out > dm_in violates the mass-conservation validator and
    Core returns 422. The agent must surface this as an error record
    without crashing the graph."""
    bad = _ser_state(dm_in=2.0, dm_out=10.0)  # violates dm_out ≤ dm_in
    # NOTE: agent schema mirror also enforces the validator client-side,
    # so the bad request never leaves the agent — the ToolCallRecord
    # captures the failure as a serialization error. Either way, we
    # require status="error".
    final = await graph.ainvoke(
        bad,
        config={"configurable": {"thread_id": "e2e-ser-bad"}},
    )
    records = final.get("tool_calls") or []
    ser_records = [r for r in records if r.get("tool") == "ser_compute"]
    assert ser_records
    assert any(r["status"] == "error" for r in ser_records)
    # No SER number should leak into state when the call failed.
    assert final.get("ser") is None


# ════════════════════════════════════════════════════════════════════
# Smoke for the three remaining V5 endpoints (lightweight - just
# confirm the HTTP path works in-process).
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_direct_relay_simulate_via_asgi(agent_wired_to_core, core_asgi_client):
    """Cheapest end-to-end exercise of the relay path (Phase A doesn't
    have an intent that consistently hits relay_node without prior
    state; we use the direct path through the same transport)."""
    r = await core_asgi_client.post(
        "/api/v1/relay/simulate",
        json={
            "initial_state": {
                "biomass_kg": 0.5, "substrate_kg": 10.0,
                "temperature_c": 28.0, "moisture_pct": 70.0,
                "nitrogen_g": 50.0, "signal_activity_au": 100.0,
            },
            "relay_config": {"tau_m2_h": 24.0, "s0": 100.0, "s_min": 10.0},
            "horizon_steps": 9,
            "dt_hours": 1.0,
            "species_code": "BSF_LARVA",
        },
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["trajectory"]) == 9


@pytest.mark.asyncio
async def test_direct_mc_propagate_via_asgi(agent_wired_to_core, core_asgi_client):
    r = await core_asgi_client.post(
        "/api/v1/mc/propagate",
        json={
            "inputs": {
                "dm_in": {"kind": "normal", "mean": 10.0, "std": 0.5},
                "dm_out": {"kind": "normal", "mean": 2.5, "std": 0.3},
            },
            "target_func": "ser",
            "target_func_config": {
                "constants": {"n_in": 1.0, "n_larvae": 0.3}
            },
            "n_samples": 200,
            "seed": 42,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["evidence_level"] == "supported"
    assert body["target_std"] >= 0.0


@pytest.mark.asyncio
async def test_direct_twin_run_via_asgi(agent_wired_to_core, core_asgi_client):
    r = await core_asgi_client.post(
        "/api/v1/twin/run",
        json={
            "initial_state": {
                "biomass_kg": 0.5, "substrate_kg": 10.0,
                "temperature_c": 28.0, "moisture_pct": 70.0,
                "nitrogen_kg": 0.05,
            },
            "inputs": [
                {"dt_hours": 1.0, "feed_rate_kg_h": 0.05} for _ in range(3)
            ],
        },
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["trajectory"]) == 3
