"""Phase A — OpenAPI contract / drift tests.

Verifies the live ``/openapi.json`` against the frozen snapshot at
``_reports/phase_a_openapi_snapshot.json``. The snapshot is the
authoritative V5 surface; any drift (added/removed paths, renamed
required fields, broken types, removed deprecation markers) trips
these tests.

Drift workflow:
1. Make the schema change.
2. Run these tests — they fail with a precise diff.
3. Update the snapshot via the helper script (see freeze doc).
4. Re-run — green.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from httpx import AsyncClient


# ════════════════════════════════════════════════════════════════════
# Locations
# ════════════════════════════════════════════════════════════════════

SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "_reports" / "phase_a_openapi_snapshot.json"
)


# ════════════════════════════════════════════════════════════════════
# Frozen surface — declared inline so the snapshot file is just an
# evidence artefact, not the source of truth for what tests check.
# ════════════════════════════════════════════════════════════════════

V5_PATHS = [
    "/api/v1/ser/compute",
    "/api/v1/sfi/check",
    "/api/v1/relay/simulate",
    "/api/v1/mc/propagate",
    "/api/v1/twin/run",
]

D1_SUNSET_PATHS = [
    "/api/v1/twin/{twin_id}/predict",
    "/api/v1/twin/{twin_id}/update",
    "/api/v1/twin/{twin_id}/simulate",
]

# Required request fields per endpoint (the bedrock of the V5 contract).
REQUIRED_REQUEST_FIELDS = {
    "/api/v1/ser/compute": [
        "dm_in", "dm_out", "n_in", "n_rec", "d_prime", "g_prime", "species_code",
    ],
    "/api/v1/sfi/check": [
        "species_code", "measurements",
    ],
    "/api/v1/relay/simulate": [
        "initial_state", "relay_config", "horizon_steps", "dt_hours", "species_code",
    ],
    "/api/v1/mc/propagate": [
        "inputs", "target_func", "target_func_config",
    ],
    "/api/v1/twin/run": [
        "initial_state", "inputs",
    ],
}

# Required response fields per endpoint.
REQUIRED_RESPONSE_FIELDS = {
    "/api/v1/ser/compute": [
        "ser_point", "engine_version", "evidence_level",
    ],
    "/api/v1/sfi/check": [
        "sfi_pass", "zone", "composite_score", "per_axis",
        "evidence_level", "engine_version",
    ],
    "/api/v1/relay/simulate": [
        "trajectory", "boundary_ledger", "relay_health",
        "final_ser", "engine_version", "evidence_level",
    ],
    "/api/v1/mc/propagate": [
        "target_mean", "target_std", "ci_lower", "ci_upper",
        "diagnostics", "evidence_level", "engine_version",
    ],
    "/api/v1/twin/run": [
        "trajectory", "estimated_states", "final_state",
        "innovation_stats", "evidence_level", "engine_version",
    ],
}


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def snapshot() -> Dict[str, Any]:
    with SNAPSHOT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
async def live_spec(client: AsyncClient) -> Dict[str, Any]:  # type: ignore[override]
    r = await client.get("/openapi.json")
    assert r.status_code == 200, r.text
    return r.json()


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _resolve_request_schema(spec: Dict[str, Any], path: str) -> Dict[str, Any]:
    op = spec["paths"][path]["post"]
    media = op["requestBody"]["content"]["application/json"]
    ref = media["schema"]["$ref"]
    return spec["components"]["schemas"][_ref_name(ref)]


def _resolve_response_schema(spec: Dict[str, Any], path: str) -> Dict[str, Any]:
    op = spec["paths"][path]["post"]
    media = op["responses"]["200"]["content"]["application/json"]
    ref = media["schema"]["$ref"]
    return spec["components"]["schemas"][_ref_name(ref)]


# ════════════════════════════════════════════════════════════════════
# Snapshot existence
# ════════════════════════════════════════════════════════════════════


def test_snapshot_file_exists():
    assert SNAPSHOT_PATH.exists(), (
        f"OpenAPI snapshot missing at {SNAPSHOT_PATH}. Regenerate via the "
        f"helper documented in _reports/PHASE_A_API_FREEZE.md."
    )


def test_snapshot_has_all_v5_paths(snapshot):
    for p in V5_PATHS:
        assert p in snapshot["paths"], f"snapshot missing V5 path {p!r}"


def test_snapshot_has_all_d1_sunset_paths(snapshot):
    for p in D1_SUNSET_PATHS:
        assert p in snapshot["paths"], f"snapshot missing D1 sunset path {p!r}"


# ════════════════════════════════════════════════════════════════════
# Live spec: V5 paths present + POST + required fields
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_live_spec_has_all_v5_paths(client: AsyncClient):
    r = await client.get("/openapi.json")
    spec = r.json()
    for p in V5_PATHS:
        assert p in spec["paths"], f"live spec missing V5 path {p!r}"
        assert "post" in spec["paths"][p], f"V5 path {p!r} is not POST"


@pytest.mark.asyncio
async def test_live_request_fields_present(client: AsyncClient):
    r = await client.get("/openapi.json")
    spec = r.json()
    for path, fields in REQUIRED_REQUEST_FIELDS.items():
        schema = _resolve_request_schema(spec, path)
        props = schema.get("properties", {})
        for f in fields:
            assert f in props, f"{path}: request schema missing field {f!r}"


@pytest.mark.asyncio
async def test_live_response_fields_present(client: AsyncClient):
    r = await client.get("/openapi.json")
    spec = r.json()
    for path, fields in REQUIRED_RESPONSE_FIELDS.items():
        schema = _resolve_response_schema(spec, path)
        props = schema.get("properties", {})
        for f in fields:
            assert f in props, f"{path}: response schema missing field {f!r}"


# ════════════════════════════════════════════════════════════════════
# D1 sunset: deprecated=True on legacy twin compute endpoints
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_d1_sunset_endpoints_marked_deprecated(client: AsyncClient):
    r = await client.get("/openapi.json")
    spec = r.json()
    for p in D1_SUNSET_PATHS:
        op = spec["paths"][p]["post"]
        assert op.get("deprecated") is True, (
            f"{p} should carry deprecated=True per D1 sunset"
        )


# ════════════════════════════════════════════════════════════════════
# Numeric guard rails — paper-strict constraints must survive in OpenAPI
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ser_request_d_prime_bounded_unit_interval(client: AsyncClient):
    r = await client.get("/openapi.json")
    spec = r.json()
    schema = _resolve_request_schema(spec, "/api/v1/ser/compute")
    d_prime = schema["properties"]["d_prime"]
    assert d_prime.get("minimum") == 0.0 and d_prime.get("maximum") == 1.0


@pytest.mark.asyncio
async def test_ser_response_point_bounded_unit_interval(client: AsyncClient):
    r = await client.get("/openapi.json")
    spec = r.json()
    schema = _resolve_response_schema(spec, "/api/v1/ser/compute")
    ser_point = schema["properties"]["ser_point"]
    assert ser_point.get("minimum") == 0.0 and ser_point.get("maximum") == 1.0


@pytest.mark.asyncio
async def test_sfi_zone_literal_set(client: AsyncClient):
    r = await client.get("/openapi.json")
    spec = r.json()
    schema = _resolve_response_schema(spec, "/api/v1/sfi/check")
    zone = schema["properties"]["zone"]
    assert set(zone.get("enum", [])) == {"safe", "caution", "danger", "out_of_envelope"}


@pytest.mark.asyncio
async def test_mc_target_func_literal_set(client: AsyncClient):
    r = await client.get("/openapi.json")
    spec = r.json()
    schema = _resolve_request_schema(spec, "/api/v1/mc/propagate")
    target = schema["properties"]["target_func"]
    assert set(target.get("enum", [])) == {"ser", "sfi_score", "relay_final_state", "custom"}


@pytest.mark.asyncio
async def test_relay_ledger_stage_literal_set(client: AsyncClient):
    r = await client.get("/openapi.json")
    spec = r.json()
    schemas = spec["components"]["schemas"]
    assert "BoundaryLedger" in schemas
    stage = schemas["BoundaryLedger"]["properties"]["stage"]
    assert set(stage.get("enum", [])) == {"M1", "M2", "M3"}


# ════════════════════════════════════════════════════════════════════
# Drift detection — snapshot must match live spec on key surface bits
# ════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_drift_v5_path_set_unchanged(client: AsyncClient, snapshot):
    r = await client.get("/openapi.json")
    spec = r.json()
    snap_v5 = {p for p in snapshot["paths"] if p in V5_PATHS}
    live_v5 = {p for p in spec["paths"] if p in V5_PATHS}
    assert snap_v5 == live_v5, (
        f"V5 path set drifted: only-in-snapshot={snap_v5 - live_v5}, "
        f"only-in-live={live_v5 - snap_v5}"
    )


@pytest.mark.asyncio
async def test_drift_request_schema_property_keys_unchanged(client: AsyncClient, snapshot):
    """Per-endpoint request schema must keep the same property keys."""
    r = await client.get("/openapi.json")
    spec = r.json()
    for path in V5_PATHS:
        snap_schema = _resolve_request_schema(snapshot, path)
        live_schema = _resolve_request_schema(spec, path)
        snap_keys = set(snap_schema.get("properties", {}).keys())
        live_keys = set(live_schema.get("properties", {}).keys())
        # Drift = symmetric difference. Allow nothing here; if a field is
        # legitimately added, regenerate the snapshot first.
        assert snap_keys == live_keys, (
            f"{path}: request schema keys drifted. "
            f"added={live_keys - snap_keys}, removed={snap_keys - live_keys}"
        )


@pytest.mark.asyncio
async def test_drift_response_schema_property_keys_unchanged(client: AsyncClient, snapshot):
    r = await client.get("/openapi.json")
    spec = r.json()
    for path in V5_PATHS:
        snap_schema = _resolve_response_schema(snapshot, path)
        live_schema = _resolve_response_schema(spec, path)
        snap_keys = set(snap_schema.get("properties", {}).keys())
        live_keys = set(live_schema.get("properties", {}).keys())
        assert snap_keys == live_keys, (
            f"{path}: response schema keys drifted. "
            f"added={live_keys - snap_keys}, removed={snap_keys - live_keys}"
        )


@pytest.mark.asyncio
async def test_drift_required_lists_unchanged(client: AsyncClient, snapshot):
    """The `required` set on each request schema is the contract floor."""
    r = await client.get("/openapi.json")
    spec = r.json()
    for path in V5_PATHS:
        snap_schema = _resolve_request_schema(snapshot, path)
        live_schema = _resolve_request_schema(spec, path)
        snap_req = set(snap_schema.get("required", []))
        live_req = set(live_schema.get("required", []))
        assert snap_req == live_req, (
            f"{path}: required-fields drifted. "
            f"now-required={live_req - snap_req}, "
            f"no-longer-required={snap_req - live_req}"
        )


@pytest.mark.asyncio
async def test_drift_schema_count_within_tolerance(client: AsyncClient, snapshot):
    """Phase A freeze captured N transitive schemas; live spec adds new
    routes outside V5 over time, but the V5 transitive closure shouldn't
    shrink. This is a coarse safety net; the per-property tests above
    catch the precise cases."""
    snap_n = len(snapshot.get("components", {}).get("schemas", {}))
    r = await client.get("/openapi.json")
    spec = r.json()
    # live spec includes the whole app — only check Phase A schemas survived.
    live_schemas = spec.get("components", {}).get("schemas", {})
    for name in snapshot["components"]["schemas"]:
        assert name in live_schemas, (
            f"Schema {name!r} present in snapshot but missing from live spec"
        )
    assert snap_n > 0
