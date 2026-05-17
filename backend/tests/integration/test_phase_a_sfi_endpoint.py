"""Phase A — SFI endpoint integration tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


def _measurements(**overrides) -> dict:
    # density_kg_m3=200 chosen to fall within BSF safe envelope.
    # The current flight_envelope BSF density safe upper bound is well
    # below typical substrate bulk densities (~500-800 kg/m³).
    # TODO (Phase B): substrate density envelope needs explicit axis
    # separate from larvae density. See A1.2 finding #1 (substrate vs
    # larvae density semantic mismatch).
    m = dict(
        temperature_c=28.0,
        moisture_pct=65.0,
        density_kg_m3=200.0,
        ph=6.8,
        ammonia_ppm=120.0,
        oxygen_pct=19.5,
        co2_pct=2.5,
    )
    m.update(overrides)
    return m


def _payload(**overrides) -> dict:
    p = dict(
        species_code="BSF_LARVA",
        measurements=_measurements(),
        horizon_hours=24,
    )
    p.update(overrides)
    return p


@pytest.mark.asyncio
async def test_endpoint_returns_200_for_safe_zone(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/sfi/check", json=_payload(), headers=operator_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["zone"] in {"safe", "caution"}
    assert 0.0 <= data["composite_score"] <= 1.0
    assert "temperature_c" in data["per_axis"]


@pytest.mark.asyncio
async def test_endpoint_classifies_danger_correctly(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """Lethal temperature should push zone to danger."""
    body = _payload(measurements=_measurements(temperature_c=55.0))
    r = await client.post("/api/v1/sfi/check", json=body, headers=operator_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["zone"] in {"danger", "out_of_envelope"}
    assert data["sfi_pass"] is False
    # actions should include a cool_down hint
    actions = data["recommended_actions"]
    assert any(a["action_type"] == "cool_down" for a in actions)


@pytest.mark.asyncio
async def test_endpoint_returns_422_for_invalid_temperature(
    client: AsyncClient, operator_headers: dict[str, str]
):
    body = _payload(measurements=_measurements(temperature_c=200.0))
    r = await client.post("/api/v1/sfi/check", json=body, headers=operator_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_with_k_decay_band_literature_downgrades_evidence(
    client: AsyncClient, operator_headers: dict[str, str]
):
    body = _payload(
        k_decay_band={
            "point": 0.045, "low": 0.030, "high": 0.060,
            "source": "literature",
        },
        s0=120.0,
        s_min=10.0,
    )
    r = await client.post("/api/v1/sfi/check", json=body, headers=operator_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    # k_decay source=literature → planned (honesty rule)
    assert data["evidence_level"] == "planned"
    assert data["k_decay_used"] is not None
    assert data["k_decay_used"]["point"] == 0.045


@pytest.mark.asyncio
async def test_endpoint_eq6_horizon_breach_triggers_out_of_envelope(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """Horizon longer than tau_max = ln(s0/s_min)/k_decay → out_of_envelope.

    tau_max = ln(11/10) / 0.05 ≈ 1.91 h. Requesting 24 h horizon should breach.
    """
    body = _payload(
        horizon_hours=24,
        k_decay_band={
            "point": 0.05, "low": 0.04, "high": 0.06,
            "source": "fitted",
        },
        s0=11.0,
        s_min=10.0,
    )
    r = await client.post("/api/v1/sfi/check", json=body, headers=operator_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["zone"] == "out_of_envelope"
    assert data["sfi_pass"] is False
    actions = [a["action_type"] for a in data["recommended_actions"]]
    assert "horizon_exceeds_physical_limit" in actions


@pytest.mark.asyncio
async def test_endpoint_forecast_breach_when_setpoint_provided(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """Current temp is far from setpoint; forecast_breach should be populated."""
    body = _payload(
        measurements=_measurements(temperature_c=33.0),
        setpoint_profile={
            "target_state": {"temperature_c": 28.0},
            "tolerance_pct": 5.0,  # tight tolerance forces immediate breach
        },
    )
    r = await client.post("/api/v1/sfi/check", json=body, headers=operator_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["forecast_breach"] is not None
    assert data["forecast_breach"]["axis"] == "temperature_c"


@pytest.mark.asyncio
async def test_endpoint_no_forecast_without_setpoint(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/sfi/check", json=_payload(), headers=operator_headers)
    assert r.status_code == 200
    assert r.json()["forecast_breach"] is None


@pytest.mark.asyncio
async def test_engine_version_present(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/sfi/check", json=_payload(), headers=operator_headers)
    assert r.status_code == 200
    import re
    assert re.match(r"^\d+\.\d+\.\d+$", r.json()["engine_version"])


@pytest.mark.asyncio
async def test_endpoint_extra_field_rejected(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post(
        "/api/v1/sfi/check", json=_payload(rogue="oops"), headers=operator_headers
    )
    assert r.status_code == 422
