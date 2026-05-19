"""Schema parity gate (Plan v2 §3.7).

Asserts the agent's mirrored schemas under ``agent/schemas/causal/``
produce identical Pydantic JSON Schemas to their backend
counterparts under ``backend/app/schemas/causal/``. The comparison
is parametrised by module name + class name so any future mirror
addition is auto-picked up.

The contract we pin is ``model_json_schema()`` — Pydantic's
canonical serialisation of field shape (name, type, constraints,
default). It is strict enough to catch a field rename or a
constraint change, lenient enough that docstring / comment edits
don't break it.

Why ``model_json_schema()`` rather than raw source diff: the only
intentional difference between mirror and backend is the import
path (``from agent.schemas.causal.common import ...`` instead of
``from app.schemas.causal_common import ...``). Source diff would
flag that line; ``model_json_schema()`` ignores it because it
serialises the resulting Pydantic model, not its source. The same
contract is what an HTTP client sees over the wire, which is the
right level of correctness to enforce.

The ``SCHEMA_VERSION`` constants are also compared byte-for-byte —
a mirror that ships B.4 while backend ships B.5 (or vice versa) is
a bug regardless of whether the field set happens to match.

This test imports both ``agent.*`` and ``app.*`` (it lives outside
the agent service's runtime; pytest runs it on the dev host where
both packages are importable). The agent module ITSELF never imports
from ``app.*`` — that's enforced by ``test_isolation.py``.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from pydantic import BaseModel


# ────────────────────────────────────────────────────────────────────
# Mirror manifest.
#
# Each tuple = (
#   short_name,
#   agent_module_path,
#   backend_module_path,
#   list[(class_name, ...)] to compare,
# )
# ────────────────────────────────────────────────────────────────────

MIRROR_MANIFEST: list[tuple[str, str, str, tuple[str, ...]]] = [
    (
        "common",
        "agent.schemas.causal.common",
        "app.schemas.causal_common",
        (
            "DagNode",
            "DagEdge",
            "DagSpec",
            "CausalData",
            "IdentifiedEstimandHandle",
            "EstimateHandle",
            "DmlParams",
            "MethodParams",
            "CausalWarning",
        ),
    ),
    (
        "identify",
        "agent.schemas.causal.identify",
        "app.schemas.causal.identify",
        (
            "CausalIdentifyRequest",
            "CausalIdentifyResponse",
        ),
    ),
    (
        "estimate",
        "agent.schemas.causal.estimate",
        "app.schemas.causal.estimate",
        (
            "EstimateDiagnostics",
            "CausalEstimateRequest",
            "CausalEstimateResponse",
        ),
    ),
    (
        "refute",
        "agent.schemas.causal.refute",
        "app.schemas.causal.refute",
        (
            "CausalRefuteRequest",
            "RefuterResult",
            "CausalRefuteResponse",
        ),
    ),
    (
        "mediation",
        "agent.schemas.causal.mediation",
        "app.schemas.causal.mediation",
        (
            "CausalMediationRequest",
            "MediationDecomposition",
            "MediationDiagnostics",
            "CausalMediationResponse",
        ),
    ),
    (
        "sensitivity",
        "agent.schemas.causal.sensitivity",
        "app.schemas.causal.sensitivity",
        (
            "CausalSensitivityRequest",
            "SensitivityEvalueDetail",
            "SensitivityLinearDetail",
            "SensitivityDiagnostics",
            "CausalSensitivityResponse",
        ),
    ),
]


def _import_module(path: str) -> Any:
    return importlib.import_module(path)


def _flatten_class_cases() -> list[tuple[str, str, str, str]]:
    """One pytest case per (mirror_short_name, class_name)."""
    cases = []
    for short_name, agent_path, backend_path, class_names in MIRROR_MANIFEST:
        for class_name in class_names:
            cases.append((short_name, agent_path, backend_path, class_name))
    return cases


# ════════════════════════════════════════════════════════════════════
# SCHEMA_VERSION parity (per-module)
# ════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "short_name,agent_path,backend_path",
    [
        (s, a, b) for (s, a, b, _) in MIRROR_MANIFEST
        if s != "common"
        # common.py has no SCHEMA_VERSION; only the per-endpoint
        # schemas do (B.1 ... B.5).
    ],
)
def test_schema_version_matches(
    short_name: str, agent_path: str, backend_path: str,
) -> None:
    agent_mod = _import_module(agent_path)
    backend_mod = _import_module(backend_path)
    agent_v = getattr(agent_mod, "SCHEMA_VERSION", None)
    backend_v = getattr(backend_mod, "SCHEMA_VERSION", None)
    assert agent_v is not None, (
        f"agent.{short_name} missing SCHEMA_VERSION constant"
    )
    assert backend_v is not None, (
        f"backend.{short_name} missing SCHEMA_VERSION constant"
    )
    assert agent_v == backend_v, (
        f"SCHEMA_VERSION drift for {short_name}: "
        f"agent={agent_v!r} backend={backend_v!r}"
    )


# ════════════════════════════════════════════════════════════════════
# CAUSAL_ENGINE_VERSION parity (single constant, lives in common)
# ════════════════════════════════════════════════════════════════════


def test_causal_engine_version_matches() -> None:
    agent_common = _import_module("agent.schemas.causal.common")
    backend_common = _import_module("app.schemas.causal_common")
    assert (
        agent_common.CAUSAL_ENGINE_VERSION
        == backend_common.CAUSAL_ENGINE_VERSION
    ), (
        f"CAUSAL_ENGINE_VERSION drift: "
        f"agent={agent_common.CAUSAL_ENGINE_VERSION!r} "
        f"backend={backend_common.CAUSAL_ENGINE_VERSION!r}"
    )


# ════════════════════════════════════════════════════════════════════
# Per-class JSON-Schema parity
# ════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "short_name,agent_path,backend_path,class_name",
    _flatten_class_cases(),
)
def test_class_json_schema_matches(
    short_name: str,
    agent_path: str,
    backend_path: str,
    class_name: str,
) -> None:
    agent_mod = _import_module(agent_path)
    backend_mod = _import_module(backend_path)

    agent_cls = getattr(agent_mod, class_name, None)
    backend_cls = getattr(backend_mod, class_name, None)
    assert agent_cls is not None, (
        f"{agent_path}.{class_name} not exported from agent mirror"
    )
    assert backend_cls is not None, (
        f"{backend_path}.{class_name} not exported from backend"
    )
    assert issubclass(agent_cls, BaseModel), (
        f"{agent_path}.{class_name} is not a Pydantic BaseModel"
    )
    assert issubclass(backend_cls, BaseModel), (
        f"{backend_path}.{class_name} is not a Pydantic BaseModel"
    )

    agent_schema = agent_cls.model_json_schema()
    backend_schema = backend_cls.model_json_schema()
    assert agent_schema == backend_schema, (
        f"JSON-schema drift on {class_name} ({short_name}). "
        f"Run `pytest -vv` to see the full diff; the agent mirror "
        f"must produce a byte-identical model_json_schema() to its "
        f"backend counterpart."
    )


# ════════════════════════════════════════════════════════════════════
# Manifest sanity
# ════════════════════════════════════════════════════════════════════


def test_manifest_covers_all_b_series_versions() -> None:
    """The five Phase B endpoints must all be present in the manifest
    (B.1 - B.5). Guards against silent mirror omission when a new
    endpoint ships."""
    short_names = {s for (s, _, _, _) in MIRROR_MANIFEST}
    required = {"common", "identify", "estimate", "refute",
                "mediation", "sensitivity"}
    missing = required - short_names
    assert not missing, (
        f"schema-parity manifest missing required mirrors: {missing}"
    )
