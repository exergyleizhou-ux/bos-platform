"""Phase A — strict SER endpoint integration tests.

Hits POST /api/v1/ser/compute via TestClient (no live server) and verifies:
- 200 path returns the V5 response shape (ser_point in [0,1], engine_version
  matches, evidence_level present).
- 422 path triggers on each schema constraint AND on each @model_validator.
- With monte_carlo block: response carries CI + MC summary.
- Without monte_carlo block: response has no CI.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


def _payload(**overrides) -> dict:
    p = {
        "dm_in": 120.0,
        "dm_out": 36.0,
        "n_in": 2.8,
        "n_rec": 0.91,
        "d_prime": 0.72,
        "g_prime": 0.65,
        "species_code": "BSF_LARVA",
        "feedstock_code": "FOOD_WASTE_MIXED",
    }
    p.update(overrides)
    return p


@pytest.mark.asyncio
async def test_endpoint_returns_200_for_valid_input(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/ser/compute", json=_payload(), headers=operator_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "ser_point" in data
    assert 0.0 <= data["ser_point"] <= 1.0
    assert data["evidence_level"] in {"validated", "supported", "planned"}


@pytest.mark.asyncio
async def test_endpoint_returns_422_for_mass_conservation_violation(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post(
        "/api/v1/ser/compute",
        json=_payload(dm_in=10.0, dm_out=11.0),
        headers=operator_headers,
    )
    assert r.status_code == 422
    body = r.json()
    # Pydantic v2 returns details under "detail" or our custom "errors"
    # depending on app-level handler; either form is acceptable as long as
    # the message mentions conservation.
    raw = str(body).lower()
    assert "conservation" in raw or "dm_out cannot exceed dm_in" in raw


@pytest.mark.asyncio
async def test_endpoint_returns_422_for_out_of_range_d_prime(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post(
        "/api/v1/ser/compute",
        json=_payload(d_prime=1.5),
        headers=operator_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_returns_422_for_n_conservation_violation(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post(
        "/api/v1/ser/compute",
        json=_payload(n_in=1.0, n_rec=2.0),
        headers=operator_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_returns_valid_ser_in_unit_interval(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post(
        "/api/v1/ser/compute",
        json=_payload(dm_in=100.0, dm_out=30.0),
        headers=operator_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert 0.29 <= data["ser_point"] <= 0.31  # SER = 30/100 = 0.30


@pytest.mark.asyncio
async def test_endpoint_with_mc_returns_ci(
    client: AsyncClient, operator_headers: dict[str, str]
):
    body = _payload(
        monte_carlo={
            "n_samples": 1000,
            "seed": 42,
            "distributions": {
                "dm_in": {"kind": "normal", "mean": 120.0, "std": 5.0},
                "dm_out": {"kind": "normal", "mean": 36.0, "std": 2.0},
            },
        }
    )
    r = await client.post("/api/v1/ser/compute", json=body, headers=operator_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ser_ci_lower"] is not None
    assert data["ser_ci_upper"] is not None
    assert data["ser_ci_lower"] <= data["ser_ci_upper"]
    assert data["monte_carlo"] is not None
    assert data["monte_carlo"]["n_samples"] == 1000


@pytest.mark.asyncio
async def test_endpoint_without_mc_returns_no_ci(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/ser/compute", json=_payload(), headers=operator_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["ser_ci_lower"] is None
    assert data["ser_ci_upper"] is None
    assert data["monte_carlo"] is None


@pytest.mark.asyncio
async def test_engine_version_present_and_matches_pattern(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/ser/compute", json=_payload(), headers=operator_headers)
    assert r.status_code == 200
    data = r.json()
    import re
    assert re.match(r"^\d+\.\d+\.\d+$", data["engine_version"]) is not None


@pytest.mark.asyncio
async def test_endpoint_extra_field_rejected(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post(
        "/api/v1/ser/compute",
        json=_payload(rogue_field="oops"),
        headers=operator_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_legacy_endpoint_still_works(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """V9 /compute_legacy must remain functional (deprecated, not deleted)."""
    legacy_body = {
        "dm_in": 10.0,
        "dm_out": 3.0,
        "n_in": 0.5,
        "n_larvae": 0.3,
        "n_frass": 0.1,
    }
    r = await client.post(
        "/api/v1/ser/compute_legacy", json=legacy_body, headers=operator_headers
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "ser_value" in data
    assert data["ser_value"] == 0.3
