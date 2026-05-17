"""Regenerate the Phase A OpenAPI snapshot.

Run from the ``backend`` directory:

    cd backend && python scripts/freeze_phase_a_openapi.py

This script boots the FastAPI app via TestClient, filters the
``/openapi.json`` down to the Phase A V5 surface plus the three
D1-sunset legacy twin compute endpoints, then writes a
deterministically-ordered JSON to
``_reports/phase_a_openapi_snapshot.json``.

Drift workflow (matches ``tests/contract/test_phase_a_openapi.py``):

1. Make the schema change in code.
2. Run ``pytest tests/contract/test_phase_a_openapi.py`` — it will
   fail with a precise diff.
3. If the change is intentional, re-run this script to regenerate the
   snapshot.
4. Re-run the contract tests — green.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Set

# Make sure imports work when run from backend/ via either python -m or as
# a script.
HERE = Path(__file__).resolve()
BACKEND_DIR = HERE.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402  (after sys.path fix)

from app.main import app  # noqa: E402


PHASE_A_PATHS: Set[str] = {
    # V5 strict
    "/api/v1/ser/compute",
    "/api/v1/sfi/check",
    "/api/v1/relay/simulate",
    "/api/v1/mc/propagate",
    "/api/v1/twin/run",
    # D1 sunset legacy
    "/api/v1/twin/{twin_id}/predict",
    "/api/v1/twin/{twin_id}/update",
    "/api/v1/twin/{twin_id}/simulate",
}


def _collect_refs(node: Any, out: Set[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str) and v.startswith("#/components/schemas/"):
                out.add(v.rsplit("/", 1)[-1])
            _collect_refs(v, out)
    elif isinstance(node, list):
        for x in node:
            _collect_refs(x, out)


def freeze() -> Path:
    client = TestClient(app)
    r = client.get("/openapi.json")
    r.raise_for_status()
    spec = r.json()

    schemas_keep: Set[str] = set()
    filtered_paths: Dict[str, Any] = {}
    for path, methods in spec["paths"].items():
        if path in PHASE_A_PATHS:
            filtered_paths[path] = methods
            _collect_refs(methods, schemas_keep)

    # Transitive closure.
    all_schemas = spec.get("components", {}).get("schemas", {})
    prev: Set[str] = set()
    while schemas_keep != prev:
        prev = set(schemas_keep)
        for name in list(schemas_keep):
            if name in all_schemas:
                _collect_refs(all_schemas[name], schemas_keep)

    frozen = {
        "openapi": spec.get("openapi", "3.0.2"),
        "info": {
            "title": "BOS Core — Phase A V5 contract",
            "version": "A.1",
            "description": (
                "Frozen Phase A surface. Covers /ser/compute /sfi/check "
                "/relay/simulate /mc/propagate /twin/run plus D1 sunset "
                "legacy twin compute endpoints."
            ),
        },
        "paths": dict(sorted(filtered_paths.items())),
        "components": {
            "schemas": dict(sorted(
                (k, v) for k, v in all_schemas.items() if k in schemas_keep
            )),
        },
    }

    out_path = BACKEND_DIR.parent / "_reports" / "phase_a_openapi_snapshot.json"
    out_path.write_text(
        json.dumps(frozen, indent=2, sort_keys=False, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"snapshot written: {out_path}")
    print(f"  paths   = {len(frozen['paths'])}")
    print(f"  schemas = {len(frozen['components']['schemas'])}")
    print(f"  bytes   = {out_path.stat().st_size}")
    return out_path


if __name__ == "__main__":
    freeze()
