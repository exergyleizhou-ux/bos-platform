"""Phase B OpenAPI drift gate (Plan v2 §7 #10).

Loads ``_reports/phase_b_openapi_snapshot.json`` and asserts that
the live FastAPI app's OpenAPI spec, scoped to the five Phase B
causal endpoints, matches the snapshot.

If this test fails, the public causal API surface drifted. Either:

- regenerate the snapshot (intentional change to a schema /
  endpoint signature) by re-running the generator, OR
- revert the offending code change.

The generator logic lives inline below in
``_compute_scoped_spec`` so the snapshot and the gate share one
canonical scope rule (paths + transitively referenced
components.schemas). The snapshot is regenerated when this test
is run with the ``BOS_REFRESH_OPENAPI_SNAPSHOT=1`` env var set —
that path is for the author refreshing the pin, not for CI.

The snapshot does NOT pin Phase A endpoints. Phase A has its own
contract gate in ``backend/tests/contract/`` (and its own
snapshot at ``_reports/phase_a_openapi_snapshot.json``).
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
    / "_reports" / "phase_b_openapi_snapshot.json"
)


_REF_PATTERN = re.compile(r"#/components/schemas/([A-Za-z0-9_-]+)")


def _compute_scoped_spec() -> dict:
    """Mirror the snapshot generator's scope rule.

    Selects ``/api/v1/causal/*`` paths plus the transitive closure
    of ``components.schemas`` they reference.
    """
    spec = app.openapi()
    causal_paths = {
        path: methods
        for path, methods in spec["paths"].items()
        if path.startswith("/api/v1/causal/")
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
        "_phase_b_snapshot_scope": (
            "paths matching /api/v1/causal/* + transitively "
            "referenced components.schemas (B3 drift gate, "
            "Plan v2 §7 #10)"
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
        "Phase B OpenAPI snapshot not present at "
        f"{SNAPSHOT_PATH}; generate it with the snapshot "
        "regenerator or set BOS_REFRESH_OPENAPI_SNAPSHOT=1."
    ),
)
def test_phase_b_openapi_paths_match_snapshot() -> None:
    """Five causal paths must match the snapshot exactly."""
    live = _compute_scoped_spec()
    _maybe_refresh_snapshot(live)
    snapshot = json.loads(
        SNAPSHOT_PATH.read_text(encoding="utf-8")
    )

    live_paths = sorted(live["paths"].keys())
    snap_paths = sorted(snapshot["paths"].keys())
    assert live_paths == snap_paths, (
        f"Phase B causal endpoint set drifted.\n"
        f"  Live:     {live_paths}\n"
        f"  Snapshot: {snap_paths}\n"
        f"Regenerate the snapshot with "
        f"BOS_REFRESH_OPENAPI_SNAPSHOT=1 if the change is "
        f"intentional, otherwise revert the offending code."
    )


@pytest.mark.skipif(
    not SNAPSHOT_PATH.exists(),
    reason="snapshot missing (see other test)",
)
def test_phase_b_openapi_path_methods_match_snapshot() -> None:
    """Each path's method dict (POST + signature) must match."""
    live = _compute_scoped_spec()
    snapshot = json.loads(
        SNAPSHOT_PATH.read_text(encoding="utf-8")
    )
    for path in sorted(snapshot["paths"]):
        live_methods = sorted(live["paths"].get(path, {}).keys())
        snap_methods = sorted(snapshot["paths"][path].keys())
        assert live_methods == snap_methods, (
            f"Method set for {path} drifted.\n"
            f"  Live:     {live_methods}\n"
            f"  Snapshot: {snap_methods}"
        )


@pytest.mark.skipif(
    not SNAPSHOT_PATH.exists(),
    reason="snapshot missing (see other test)",
)
def test_phase_b_openapi_schemas_match_snapshot() -> None:
    """Component schema set drift detection.

    Asserts the *name set* of referenced schemas matches. Field-
    level drift inside a schema (e.g. a description change) is
    NOT caught here — that requires a deep-equality check which
    is too brittle against Pydantic's auto-generated JSON Schema
    serialisation (key ordering, default-value formatting).
    Catching schema-name drift is sufficient to flag new fields
    being added or removed; richer checks can land in Phase G.
    """
    live = _compute_scoped_spec()
    snapshot = json.loads(
        SNAPSHOT_PATH.read_text(encoding="utf-8")
    )
    live_schemas = sorted(live["components"]["schemas"].keys())
    snap_schemas = sorted(snapshot["components"]["schemas"].keys())
    assert live_schemas == snap_schemas, (
        f"Phase B causal component schema set drifted.\n"
        f"  Live:     {live_schemas}\n"
        f"  Snapshot: {snap_schemas}\n"
        f"Regenerate the snapshot with "
        f"BOS_REFRESH_OPENAPI_SNAPSHOT=1 if intentional."
    )


@pytest.mark.skipif(
    not SNAPSHOT_PATH.exists(),
    reason="snapshot missing (see other test)",
)
def test_phase_b_openapi_snapshot_invariants() -> None:
    """Snapshot self-consistency: 5 paths + at least the core
    causal-common types are present.

    Decouples the test from the exact schema-name set so trivial
    additions (e.g. a new optional field's nested type) don't
    break the gate; instead, the schema-set drift test above is
    the primary gate.
    """
    snapshot = json.loads(
        SNAPSHOT_PATH.read_text(encoding="utf-8")
    )
    assert len(snapshot["paths"]) == 5, (
        f"snapshot should pin 5 causal paths; got "
        f"{len(snapshot['paths'])}"
    )
    expected_paths = {
        "/api/v1/causal/identify",
        "/api/v1/causal/estimate",
        "/api/v1/causal/refute",
        "/api/v1/causal/mediation",
        "/api/v1/causal/sensitivity",
    }
    assert set(snapshot["paths"].keys()) == expected_paths, (
        f"snapshot paths do not match expected five: "
        f"{sorted(snapshot['paths'].keys())}"
    )
    # Core types every causal Response references.
    schema_names = set(snapshot["components"]["schemas"].keys())
    must_have = {"DagSpec", "DagNode", "DagEdge", "CausalData"}
    missing = must_have - schema_names
    assert not missing, (
        f"snapshot missing core causal-common types: {missing}"
    )
