"""Phase A — Relay endpoint integration tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


def _state(**o) -> dict:
    base = dict(
        biomass_kg=0.5,
        substrate_kg=10.0,
        temperature_c=28.0,
        moisture_pct=70.0,
        nitrogen_g=50.0,
        signal_activity_au=100.0,
    )
    base.update(o)
    return base


def _payload(**o) -> dict:
    base = dict(
        initial_state=_state(),
        relay_config={"tau_m2_h": 24.0, "s0": 100.0, "s_min": 10.0},
        horizon_steps=12,
        dt_hours=1.0,
        species_code="BSF_LARVA",
    )
    base.update(o)
    return base


@pytest.mark.asyncio
async def test_endpoint_returns_200_for_minimal_request(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/relay/simulate", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine_version"]
    assert 0.0 <= body["final_ser"] <= 1.0


@pytest.mark.asyncio
async def test_endpoint_returns_three_stage_boundary_ledger(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/relay/simulate", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200
    stages = [b["stage"] for b in r.json()["boundary_ledger"]]
    assert stages == ["M1", "M2", "M3"]


@pytest.mark.asyncio
async def test_endpoint_trajectory_length_matches_horizon(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """Trajectory should have exactly horizon_steps snapshots (split across stages)."""
    r = await client.post("/api/v1/relay/simulate",
                          json=_payload(horizon_steps=9, dt_hours=1.0),
                          headers=operator_headers)
    assert r.status_code == 200
    traj = r.json()["trajectory"]
    # horizon=9 → 3/3/3 split → 9 total
    assert len(traj) == 9


@pytest.mark.asyncio
async def test_endpoint_returns_relay_health_with_stage_completion(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/relay/simulate", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200
    health = r.json()["relay_health"]
    assert set(health["stage_completion"].keys()) == {"M1", "M2", "M3"}
    for v in health["stage_completion"].values():
        assert 0.0 <= v <= 1.0


@pytest.mark.asyncio
async def test_endpoint_returns_422_for_invalid_config(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """s_min >= s0 should fail at the validator."""
    body = _payload(relay_config={"tau_m2_h": 24.0, "s0": 10.0, "s_min": 10.0})
    r = await client.post("/api/v1/relay/simulate", json=body,
                          headers=operator_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_with_k_decay_band_signals_violation_if_breached(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """Aggressive k_decay should push signal below s_min during M2.

    Setup: k=0.8/h, s0=100, s_min=25 → tau_max = ln(100/25)/0.8 ≈ 1.73 h.
    Validator ceiling is 5× tau_max ≈ 8.66 h (raised from 3× in A1.3 to
    allow real violation scenarios). horizon_steps=8 / dt_hours=1.0
    → sim=8 h, inside the ceiling.

    _split_steps(8) → (2, 2, 4); M2 gets 2 steps. Decay during M2:
        step1: 100·exp(-0.8·1) ≈ 44.9 (still > 25)
        step2: 100·exp(-0.8·2) ≈ 20.2 (< 25 → violation)
    Violation triggers at M2 step 2 (global step ≈ 3). ✓
    """
    body = _payload(
        horizon_steps=8,
        dt_hours=1.0,
        relay_config={
            "tau_m2_h": 24.0,
            "s0": 100.0,
            "s_min": 25.0,
            "k_decay_band": {"point": 0.8, "low": 0.6, "high": 1.0,
                             "source": "fitted"},
        },
    )
    r = await client.post("/api/v1/relay/simulate", json=body,
                          headers=operator_headers)
    assert r.status_code == 200, r.text
    body_out = r.json()
    health = body_out["relay_health"]
    assert health["k_decay_violation_at_step"] is not None
    assert health["overall_status"] == "failed"
    codes = [w["code"] for w in body_out["warnings"]]
    assert "k_decay_violation" in codes


@pytest.mark.asyncio
async def test_endpoint_with_mc_returns_ci(
    client: AsyncClient, operator_headers: dict[str, str]
):
    body = _payload(monte_carlo={
        "n_samples": 1000,
        "seed": 42,
        "distributions": {"dm_in": {"kind": "normal", "mean": 10.0, "std": 0.5}},
    })
    r = await client.post("/api/v1/relay/simulate", json=body,
                          headers=operator_headers)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["final_ser_ci"] is not None
    lo, hi = out["final_ser_ci"]
    assert lo <= hi


@pytest.mark.asyncio
async def test_endpoint_without_mc_no_ci(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/relay/simulate", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200
    assert r.json()["final_ser_ci"] is None


@pytest.mark.asyncio
async def test_endpoint_boundary_residuals_recorded(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """Every boundary ledger entry should record an explicit closure_pct
    in [0, 200] (per schema). If closure_pct < 95 the engine emits a
    poor_boundary_closure warning."""
    r = await client.post("/api/v1/relay/simulate", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200
    out = r.json()
    for lg in out["boundary_ledger"]:
        assert 0.0 <= lg["closure_pct"] <= 200.0
        if lg["closure_pct"] < 95.0:
            codes = [w["code"] for w in out["warnings"]]
            assert "poor_boundary_closure" in codes


@pytest.mark.asyncio
async def test_engine_version_present(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/relay/simulate", json=_payload(),
                          headers=operator_headers)
    import re
    assert re.match(r"^\d+\.\d+\.\d+$", r.json()["engine_version"])


@pytest.mark.asyncio
async def test_endpoint_evidence_level_planned_when_k_literature(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """k_decay_band.source=literature → evidence_level=planned (paper honesty)."""
    body = _payload(
        relay_config={
            "tau_m2_h": 24.0, "s0": 100.0, "s_min": 10.0,
            "k_decay_band": {"point": 0.045, "low": 0.030, "high": 0.060,
                             "source": "literature"},
        },
    )
    r = await client.post("/api/v1/relay/simulate", json=body,
                          headers=operator_headers)
    assert r.status_code == 200, r.text
    assert r.json()["evidence_level"] == "planned"


@pytest.mark.asyncio
async def test_endpoint_extra_field_rejected(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/relay/simulate",
                          json=_payload(rogue="oops"),
                          headers=operator_headers)
    assert r.status_code == 422
