"""Phase A — Twin /run endpoint integration tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


def _state(**o) -> dict:
    base = dict(
        biomass_kg=0.5,
        substrate_kg=10.0,
        temperature_c=28.0,
        moisture_pct=70.0,
        nitrogen_kg=0.05,
    )
    base.update(o)
    return base


def _inputs(n: int = 3, dt: float = 1.0) -> list[dict]:
    return [{"dt_hours": dt, "feed_rate_kg_h": 0.05,
             "ventilation_m3_h": 1.0, "heating_kw": 0.0} for _ in range(n)]


def _payload(**o) -> dict:
    base = dict(initial_state=_state(), inputs=_inputs(3))
    base.update(o)
    return base


@pytest.mark.asyncio
async def test_endpoint_returns_200_for_minimal_request(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/twin/run", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["trajectory"]) == 3
    assert len(data["estimated_states"]) == 3


@pytest.mark.asyncio
async def test_endpoint_trajectory_length_matches_inputs(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/twin/run",
                          json=_payload(inputs=_inputs(8, dt=0.5)),
                          headers=operator_headers)
    assert r.status_code == 200
    assert len(r.json()["trajectory"]) == 8


@pytest.mark.asyncio
async def test_endpoint_final_state_matches_last_estimated(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/twin/run", json=_payload(),
                          headers=operator_headers)
    body = r.json()
    assert body["final_state"] == body["estimated_states"][-1]


@pytest.mark.asyncio
async def test_endpoint_with_observations_runs_ekf(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """3 inputs, 3 observations → 3 EKF updates, innovation stats populated."""
    body = _payload(
        inputs=_inputs(3),
        observations=[
            {"weight_kg": 10.4, "temperature_c": 28.5, "moisture_pct": 69.0},
            {"weight_kg": 10.7, "temperature_c": 28.7, "moisture_pct": 68.5},
            {"weight_kg": 11.0, "temperature_c": 28.9, "moisture_pct": 68.0},
        ],
    )
    r = await client.post("/api/v1/twin/run", json=body, headers=operator_headers)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["innovation_stats"]["n_updates"] == 3
    assert "weight" in out["innovation_stats"]["mean_abs_innovation"]
    assert out["evidence_level"] == "supported"


@pytest.mark.asyncio
async def test_endpoint_without_observations_no_ekf(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/twin/run", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200
    out = r.json()
    assert out["innovation_stats"]["n_updates"] == 0
    assert out["evidence_level"] == "planned"


@pytest.mark.asyncio
async def test_endpoint_observations_length_mismatch_rejected(
    client: AsyncClient, operator_headers: dict[str, str]
):
    body = _payload(
        inputs=_inputs(3),
        observations=[{"weight_kg": 10.0}, {"weight_kg": 10.1}],  # 2 vs 3
    )
    r = await client.post("/api/v1/twin/run", json=body, headers=operator_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_invalid_state_rejected(
    client: AsyncClient, operator_headers: dict[str, str]
):
    body = _payload(initial_state=_state(temperature_c=200.0))
    r = await client.post("/api/v1/twin/run", json=body, headers=operator_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_enable_ekf_false_skips_update_even_with_obs(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """When enable_ekf=False, observations are accepted but ignored."""
    body = _payload(
        inputs=_inputs(2),
        observations=[
            {"weight_kg": 10.4}, {"weight_kg": 10.7},
        ],
        enable_ekf=False,
    )
    r = await client.post("/api/v1/twin/run", json=body, headers=operator_headers)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["innovation_stats"]["n_updates"] == 0
    assert out["evidence_level"] == "planned"


@pytest.mark.asyncio
async def test_endpoint_cumulative_time_monotonic(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/twin/run",
                          json=_payload(inputs=_inputs(5, dt=2.0)),
                          headers=operator_headers)
    assert r.status_code == 200
    times = [s["cumulative_time_h"] for s in r.json()["trajectory"]]
    assert times == sorted(times)
    # dt=2.0 → final time = 10 h
    assert abs(times[-1] - 10.0) < 1e-6


@pytest.mark.asyncio
async def test_endpoint_step_indices_dense(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/twin/run", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200
    indices = [s["step_index"] for s in r.json()["trajectory"]]
    assert indices == [0, 1, 2]


@pytest.mark.asyncio
async def test_endpoint_engine_version_present(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/twin/run", json=_payload(),
                          headers=operator_headers)
    import re
    assert re.match(r"^\d+\.\d+\.\d+$", r.json()["engine_version"])


@pytest.mark.asyncio
async def test_endpoint_extra_field_rejected(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/twin/run",
                          json=_payload(rogue="oops"),
                          headers=operator_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_legacy_predict_endpoint_marked_deprecated_in_openapi(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """D1 sunset: /api/v1/twin/{id}/predict carries deprecated=True."""
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    op = spec["paths"]["/api/v1/twin/{twin_id}/predict"]["post"]
    assert op.get("deprecated") is True
