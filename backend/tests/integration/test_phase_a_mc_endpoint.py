"""Phase A — MC propagation endpoint integration tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


def _payload(**o) -> dict:
    base = dict(
        inputs={
            "dm_in": {"kind": "normal", "mean": 10.0, "std": 0.5},
            "dm_out": {"kind": "normal", "mean": 2.5, "std": 0.3},
        },
        target_func="ser",
        target_func_config={"constants": {"n_in": 50.0, "n_larvae": 30.0}},
        n_samples=500,
        seed=42,
    )
    base.update(o)
    return base


@pytest.mark.asyncio
async def test_endpoint_returns_200_for_ser_target(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/mc/propagate", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert 0.0 <= data["target_mean"] <= 1.0  # SER is in [0, 1]
    assert data["target_std"] >= 0.0
    assert data["ci_lower"] <= data["ci_upper"]


@pytest.mark.asyncio
async def test_endpoint_ser_target_is_supported_evidence(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """SER target uses the real ser_engine per sample → supported."""
    r = await client.post("/api/v1/mc/propagate", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200
    assert r.json()["evidence_level"] == "supported"


@pytest.mark.asyncio
async def test_endpoint_non_ser_targets_are_planned(
    client: AsyncClient, operator_headers: dict[str, str]
):
    """sfi_score / relay_final_state / custom use placeholder evaluator
    in Phase A → evidence_level=planned."""
    for tgt in ("sfi_score", "relay_final_state", "custom"):
        r = await client.post(
            "/api/v1/mc/propagate",
            json=_payload(target_func=tgt,
                          target_func_config={"intercept": 0.1, "coeffs": {"dm_in": 0.5}}),
            headers=operator_headers,
        )
        assert r.status_code == 200, f"target={tgt}: {r.text}"
        assert r.json()["evidence_level"] == "planned", f"target={tgt}"


@pytest.mark.asyncio
async def test_endpoint_seed_reproducibility(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r1 = await client.post("/api/v1/mc/propagate", json=_payload(seed=123),
                           headers=operator_headers)
    r2 = await client.post("/api/v1/mc/propagate", json=_payload(seed=123),
                           headers=operator_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["target_mean"] == r2.json()["target_mean"]
    assert r1.json()["ci_lower"] == r2.json()["ci_lower"]


@pytest.mark.asyncio
async def test_endpoint_return_samples_off_by_default(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/mc/propagate", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200
    assert r.json()["samples"] is None


@pytest.mark.asyncio
async def test_endpoint_return_samples_returns_array(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/mc/propagate",
                          json=_payload(return_samples=True, n_samples=200),
                          headers=operator_headers)
    assert r.status_code == 200
    samples = r.json()["samples"]
    assert isinstance(samples, list)
    assert len(samples) == 200


@pytest.mark.asyncio
async def test_endpoint_compute_sobol_returns_indices(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/mc/propagate",
                          json=_payload(compute_sobol=True),
                          headers=operator_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    sobol = body["sobol_indices"]
    assert sobol is not None
    assert set(sobol["first_order"].keys()) == {"dm_in", "dm_out"}
    assert set(sobol["total"].keys()) == {"dm_in", "dm_out"}
    # Sobol via correlation proxy in Phase A → evidence_level downgraded.
    assert body["evidence_level"] == "planned"


@pytest.mark.asyncio
async def test_endpoint_no_sobol_by_default(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/mc/propagate", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200
    assert r.json()["sobol_indices"] is None


@pytest.mark.asyncio
async def test_endpoint_returns_422_for_unknown_target(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/mc/propagate",
                          json=_payload(target_func="phlogiston"),
                          headers=operator_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_returns_422_for_empty_target_config(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/mc/propagate",
                          json=_payload(target_func_config={}),
                          headers=operator_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_diagnostics_present(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/mc/propagate", json=_payload(),
                          headers=operator_headers)
    assert r.status_code == 200
    diag = r.json()["diagnostics"]
    assert diag["n_samples"] == 500
    assert diag["effective_samples"] == 500
    assert diag["seed"] == 42
    assert diag["distribution_kinds"]["dm_in"] == "normal"
    assert diag["computation_time_ms"] >= 0.0


@pytest.mark.asyncio
async def test_endpoint_engine_version_present(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/mc/propagate", json=_payload(),
                          headers=operator_headers)
    import re
    assert re.match(r"^\d+\.\d+\.\d+$", r.json()["engine_version"])


@pytest.mark.asyncio
async def test_endpoint_extra_field_rejected(
    client: AsyncClient, operator_headers: dict[str, str]
):
    r = await client.post("/api/v1/mc/propagate", json=_payload(rogue="oops"),
                          headers=operator_headers)
    assert r.status_code == 422
