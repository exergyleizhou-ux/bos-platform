"""Phase C OpenAPI drift gate (Plan v3 §2.1 + §12).

Loads ``_reports/phase_c_openapi_snapshot.json`` and asserts that
the live FastAPI app's OpenAPI spec, scoped to the Phase C causal
endpoints, matches the snapshot.

Phase C endpoints (so far):

- ``/api/v1/causal/bayesian_estimate`` (C1, SCHEMA_VERSION C.1)

To be added in future C batches:

- ``/api/v1/causal/conformal_predict`` (C2, SCHEMA_VERSION C.2)
- ``/api/v1/causal/uncertainty_pipeline`` (C4, SCHEMA_VERSION C.4)

Note: C3 (Bayesian mediation) is a schema extension of the
existing B.4 mediation endpoint (new ``method = "bayesian"`` enum
value), NOT a new endpoint. C3 will trigger a Phase B drift
re-pin when shipped, not a new Phase C endpoint.

If this test fails, the public Phase C causal API surface
drifted. Either:

- regenerate the snapshot (intentional change to a schema /
  endpoint signature) by re-running this test with the
  ``BOS_REFRESH_OPENAPI_SNAPSHOT=1`` env var set, OR
- revert the offending code change.

The snapshot regeneration scope mirrors Phase B's
``test_phase_b_openapi.py`` — paths + transitive
``components.schemas`` closure.

The snapshot does NOT pin Phase A or Phase B endpoints; those have
their own gates.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from app.main import app


SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "_reports" / "phase_c_openapi_snapshot.json"
)


_REF_PATTERN = re.compile(r"#/components/schemas/([A-Za-z0-9_-]+)")


PHASE_C_CAUSAL_PATHS = frozenset({
    "/api/v1/causal/bayesian_estimate",   # C1
    "/api/v1/causal/conformal_predict",   # C2
})
"""The Phase C causal endpoints pinned by this gate.

Currently 2 endpoints:
- C1 Bayesian baseline (SCHEMA_VERSION C.1)
- C2 Conformal prediction (SCHEMA_VERSION C.2)

Will grow as C3-C4 ship. Each addition needs a corresponding
snapshot refresh under ``BOS_REFRESH_OPENAPI_SNAPSHOT=1``.
"""


def _compute_scoped_spec() -> dict:
    """Mirror the snapshot generator's scope rule.

    Selects ``PHASE_C_CAUSAL_PATHS`` plus the transitive closure
    of ``components.schemas`` they reference.
    """
    spec = app.openapi()
    causal_paths = {
        path: methods
        for path, methods in spec["paths"].items()
        if path in PHASE_C_CAUSAL_PATHS
    }
    all_schemas = spec.get("components", {}).get("schemas", {})

    def collect_refs(name: str, acc: set[str]) -> None:
        if name in acc or name not in all_schemas:
            return
        acc.add(name)
        payload = json.dumps(all_schemas[name])
        for ref in _REF_PATTERN.findall(payload):
            collect_refs(ref, acc)

    initial = set(
        _REF_PATTERN.findall(json.dumps({"paths": causal_paths}))
    )
    needed: set[str] = set()
    for ref_name in initial:
        collect_refs(ref_name, needed)

    scoped_schemas = {
        name: all_schemas[name]
        for name in sorted(needed) if name in all_schemas
    }
    return {
        "openapi": spec.get("openapi"),
        "info": {
            "title": spec.get("info", {}).get("title"),
            "version": spec.get("info", {}).get("version"),
        },
        "_phase_c_snapshot_scope": (
            "paths matching PHASE_C_CAUSAL_PATHS + transitively "
            "referenced components.schemas (Plan v3 §2.1 / §12)"
        ),
        "paths": causal_paths,
        "components": {"schemas": scoped_schemas},
    }


def _maybe_refresh_snapshot(live: dict) -> None:
    """Refresh the snapshot when ``BOS_REFRESH_OPENAPI_SNAPSHOT=1``.

    Author-only path; not exercised by normal test runs.
    """
    if os.environ.get("BOS_REFRESH_OPENAPI_SNAPSHOT") != "1":
        return
    SNAPSHOT_PATH.write_text(
        json.dumps(live, indent=2, ensure_ascii=False, sort_keys=False)
        + "\n",
        encoding="utf-8",
    )


@pytest.mark.skipif(
    not SNAPSHOT_PATH.exists(),
    reason=(
        "Phase C OpenAPI snapshot not yet generated. Run this test "
        "with BOS_REFRESH_OPENAPI_SNAPSHOT=1 to generate it for the "
        "first time."
    ),
)
def test_phase_c_openapi_paths_match_snapshot():
    live = _compute_scoped_spec()
    _maybe_refresh_snapshot(live)

    snapshot = json.loads(
        SNAPSHOT_PATH.read_text(encoding="utf-8")
    )
    assert sorted(live["paths"].keys()) == sorted(snapshot["paths"].keys()), (
        "Phase C causal endpoint set drifted.\n"
        f"  Live: {sorted(live['paths'].keys())}\n"
        f"  Snap: {sorted(snapshot['paths'].keys())}\n"
        "Run with BOS_REFRESH_OPENAPI_SNAPSHOT=1 to refresh if "
        "the change is intentional."
    )


@pytest.mark.skipif(
    not SNAPSHOT_PATH.exists(),
    reason="Phase C OpenAPI snapshot not yet generated.",
)
def test_phase_c_openapi_path_methods_match_snapshot():
    live = _compute_scoped_spec()
    snapshot = json.loads(
        SNAPSHOT_PATH.read_text(encoding="utf-8")
    )
    for path, methods in snapshot["paths"].items():
        assert path in live["paths"], (
            f"Path {path!r} missing from live spec"
        )
        assert sorted(methods.keys()) == sorted(
            live["paths"][path].keys()
        ), (
            f"Path {path!r} method set drifted.\n"
            f"  Live: {sorted(live['paths'][path].keys())}\n"
            f"  Snap: {sorted(methods.keys())}"
        )


@pytest.mark.skipif(
    not SNAPSHOT_PATH.exists(),
    reason="Phase C OpenAPI snapshot not yet generated.",
)
def test_phase_c_openapi_schemas_match_snapshot():
    live = _compute_scoped_spec()
    snapshot = json.loads(
        SNAPSHOT_PATH.read_text(encoding="utf-8")
    )
    live_schemas = sorted(live["components"]["schemas"].keys())
    snap_schemas = sorted(snapshot["components"]["schemas"].keys())
    assert live_schemas == snap_schemas, (
        "Phase C causal component schema set drifted.\n"
        f"  Live ({len(live_schemas)}): {live_schemas}\n"
        f"  Snap ({len(snap_schemas)}): {snap_schemas}\n"
        "Run with BOS_REFRESH_OPENAPI_SNAPSHOT=1 to refresh."
    )


@pytest.mark.skipif(
    not SNAPSHOT_PATH.exists(),
    reason="Phase C OpenAPI snapshot not yet generated.",
)
def test_phase_c_openapi_snapshot_invariants():
    """Invariants that should hold regardless of which Phase C
    batches have shipped."""
    snapshot = json.loads(
        SNAPSHOT_PATH.read_text(encoding="utf-8")
    )
    assert "openapi" in snapshot
    assert "info" in snapshot
    assert "paths" in snapshot
    assert "components" in snapshot
    assert snapshot["_phase_c_snapshot_scope"].startswith(
        "paths matching PHASE_C_CAUSAL_PATHS"
    )
    # At least one path pinned (C1 minimum)
    assert len(snapshot["paths"]) >= 1
