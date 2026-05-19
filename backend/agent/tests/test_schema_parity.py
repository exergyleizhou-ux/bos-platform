"""Schema-parity: every agent mirror MUST advertise the same
SCHEMA_VERSION as its Core counterpart (Plan v2 paragraph 3.4).

If a Core schema bumps but the agent mirror does not, this test fails
and forces the maintainer to update both sides in the same change.

Note: this is the one place in the agent test suite where importing
``app.schemas.*`` is allowed - the parity check by definition needs
both sides. The architectural isolation rule covers runtime code only.

Phase B B4 v2: added parity coverage for the 5 causal schemas
(B.1 - B.5) plus a JSON-schema deep-equality check on the causal
common types. The same gate behaviour applies: any Core-side bump
without a matching agent-side bump fails this test.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

# Importing Core schema modules here is intentional: this test exists
# precisely to compare versions across the boundary.
from app.schemas import ser as core_ser
from app.schemas import sfi as core_sfi
from app.schemas import relay as core_relay
from app.schemas import mc as core_mc
from app.schemas import twin as core_twin

from agent.schemas import ser as agent_ser
from agent.schemas import sfi as agent_sfi
from agent.schemas import relay as agent_relay
from agent.schemas import mc as agent_mc
from agent.schemas import twin as agent_twin

# Phase B B4 v2 causal mirrors.
from app.schemas import causal_common as core_causal_common
from app.schemas.causal import (
    identify as core_causal_identify,
    estimate as core_causal_estimate,
    refute as core_causal_refute,
    mediation as core_causal_mediation,
    sensitivity as core_causal_sensitivity,
)
from agent.schemas.causal import (
    common as agent_causal_common,
    identify as agent_causal_identify,
    estimate as agent_causal_estimate,
    refute as agent_causal_refute,
    mediation as agent_causal_mediation,
    sensitivity as agent_causal_sensitivity,
)


@pytest.mark.parametrize(
    "label,core_mod,agent_mod",
    [
        ("ser",   core_ser,   agent_ser),
        ("sfi",   core_sfi,   agent_sfi),
        ("relay", core_relay, agent_relay),
        ("mc",    core_mc,    agent_mc),
        ("twin",  core_twin,  agent_twin),
    ],
)
def test_schema_version_parity(label: str, core_mod, agent_mod):
    core_v = getattr(core_mod, "SCHEMA_VERSION", None)
    agent_v = getattr(agent_mod, "SCHEMA_VERSION", None)
    assert core_v is not None, f"core {label} missing SCHEMA_VERSION"
    assert agent_v is not None, f"agent {label} missing SCHEMA_VERSION"
    assert core_v == agent_v, (
        f"SCHEMA_VERSION drift on {label}: core={core_v!r} vs agent={agent_v!r}."
        f" Update agent/schemas/{label}.py to match before landing."
    )


def test_request_response_class_names_match():
    """Cheap sanity check that the V5 contract class names are present
    on both sides (catches typos in the mirror)."""
    mapping = [
        (core_ser,   agent_ser,   ["SerComputeRequest", "SerComputeResponse"]),
        (core_sfi,   agent_sfi,   ["SfiCheckRequest", "SfiCheckResponse"]),
        (core_relay, agent_relay, ["RelaySimulateRequest", "RelaySimulateResponse"]),
        (core_mc,    agent_mc,    ["McPropagateRequest", "McPropagateResponse"]),
        (core_twin,  agent_twin,  ["TwinRunRequest", "TwinRunResponse"]),
    ]
    for core_mod, agent_mod, names in mapping:
        for name in names:
            assert hasattr(core_mod, name), f"core missing {name}"
            assert hasattr(agent_mod, name), f"agent missing {name}"


# ════════════════════════════════════════════════════════════════════
# Phase B B4 v2 causal-schema parity (B.1 - B.5)
# ════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "label,core_mod,agent_mod",
    [
        ("causal.identify",
         core_causal_identify, agent_causal_identify),
        ("causal.estimate",
         core_causal_estimate, agent_causal_estimate),
        ("causal.refute",
         core_causal_refute, agent_causal_refute),
        ("causal.mediation",
         core_causal_mediation, agent_causal_mediation),
        ("causal.sensitivity",
         core_causal_sensitivity, agent_causal_sensitivity),
    ],
)
def test_causal_schema_version_parity(
    label: str, core_mod, agent_mod,
) -> None:
    """SCHEMA_VERSION must match across the causal mirror."""
    core_v = getattr(core_mod, "SCHEMA_VERSION", None)
    agent_v = getattr(agent_mod, "SCHEMA_VERSION", None)
    assert core_v is not None, f"core {label} missing SCHEMA_VERSION"
    assert agent_v is not None, f"agent {label} missing SCHEMA_VERSION"
    assert core_v == agent_v, (
        f"SCHEMA_VERSION drift on {label}: "
        f"core={core_v!r} vs agent={agent_v!r}. "
        f"Update agent/schemas/causal/* to match before landing."
    )


def test_causal_engine_version_parity() -> None:
    """``CAUSAL_ENGINE_VERSION`` must match across the common mirror.

    Lives in ``app.schemas.causal_common`` and
    ``agent.schemas.causal.common``. Drift here surfaces as a
    response-payload mismatch (the agent would echo a different
    version than the engine produced).
    """
    core_v = getattr(core_causal_common, "CAUSAL_ENGINE_VERSION", None)
    agent_v = getattr(agent_causal_common, "CAUSAL_ENGINE_VERSION", None)
    assert core_v == agent_v, (
        f"CAUSAL_ENGINE_VERSION drift: core={core_v!r} vs "
        f"agent={agent_v!r}"
    )


def _flatten_causal_class_cases() -> list[
    tuple[str, str, BaseModel, BaseModel]
]:
    """One pytest case per (mirror, class). Covers the
    request/response/sub-model shapes the agent must echo back-and-
    forth with the engine."""
    cases: list[tuple[str, str, BaseModel, BaseModel]] = []
    manifest: list[tuple[str, Any, Any, tuple[str, ...]]] = [
        (
            "common",
            core_causal_common,
            agent_causal_common,
            (
                "DagNode", "DagEdge", "DagSpec", "CausalData",
                "IdentifiedEstimandHandle", "EstimateHandle",
                "DmlParams", "MethodParams", "CausalWarning",
            ),
        ),
        (
            "identify",
            core_causal_identify,
            agent_causal_identify,
            ("CausalIdentifyRequest", "CausalIdentifyResponse"),
        ),
        (
            "estimate",
            core_causal_estimate,
            agent_causal_estimate,
            (
                "EstimateDiagnostics",
                "CausalEstimateRequest", "CausalEstimateResponse",
            ),
        ),
        (
            "refute",
            core_causal_refute,
            agent_causal_refute,
            ("CausalRefuteRequest", "RefuterResult", "CausalRefuteResponse"),
        ),
        (
            "mediation",
            core_causal_mediation,
            agent_causal_mediation,
            (
                "CausalMediationRequest",
                "MediationDecomposition",
                "MediationDiagnostics",
                "CausalMediationResponse",
            ),
        ),
        (
            "sensitivity",
            core_causal_sensitivity,
            agent_causal_sensitivity,
            (
                "CausalSensitivityRequest",
                "SensitivityEvalueDetail",
                "SensitivityLinearDetail",
                "SensitivityDiagnostics",
                "CausalSensitivityResponse",
            ),
        ),
    ]
    for label, core_mod, agent_mod, classes in manifest:
        for cls_name in classes:
            core_cls = getattr(core_mod, cls_name, None)
            agent_cls = getattr(agent_mod, cls_name, None)
            assert core_cls is not None, (
                f"core.{label}.{cls_name} missing on the source side"
            )
            assert agent_cls is not None, (
                f"agent.{label}.{cls_name} missing on the mirror side"
            )
            cases.append((label, cls_name, core_cls, agent_cls))
    return cases


# Module-level flatten so parametrize ids are stable across runs.
_CAUSAL_CASES = _flatten_causal_class_cases()


_PROSE_KEYS = frozenset({"description", "title", "examples"})


def _strip_prose(obj: Any) -> Any:
    """Recursively drop description / title / examples keys.

    Plan v2 §3.4 spells out the parity contract as
    "field-by-field (name + type + constraints + default)" — prose
    fields (class docstrings rendered as ``description``, auto-
    generated ``title``, ``examples`` blocks) are documentation,
    not contract. Comparing them would force the agent mirrors to
    duplicate every docstring verbatim, which we deliberately
    skipped to keep the mirrors readable.
    """
    if isinstance(obj, dict):
        return {
            k: _strip_prose(v)
            for k, v in obj.items()
            if k not in _PROSE_KEYS
        }
    if isinstance(obj, list):
        return [_strip_prose(v) for v in obj]
    return obj


@pytest.mark.parametrize(
    "label,class_name,core_cls,agent_cls",
    [(c[0], c[1], c[2], c[3]) for c in _CAUSAL_CASES],
    ids=[f"{c[0]}-{c[1]}" for c in _CAUSAL_CASES],
)
def test_causal_class_json_schema_parity(
    label: str, class_name: str, core_cls, agent_cls,
) -> None:
    """Pydantic JSON-schema deep equality (prose-stripped).

    Catches field-name, type, constraint, and default drift between
    Core and the agent mirror. Docstring / title / examples drift
    is intentionally ignored — see ``_strip_prose`` for rationale.
    The contract pinned is the wire-level shape.
    """
    assert issubclass(core_cls, BaseModel), (
        f"core.{label}.{class_name} not a BaseModel"
    )
    assert issubclass(agent_cls, BaseModel), (
        f"agent.{label}.{class_name} not a BaseModel"
    )
    core_schema = _strip_prose(core_cls.model_json_schema())
    agent_schema = _strip_prose(agent_cls.model_json_schema())
    assert core_schema == agent_schema, (
        f"JSON-schema drift on {label}.{class_name}. "
        f"Run pytest -vv for the full diff; the agent mirror must "
        f"produce a structurally identical model_json_schema() "
        f"(field names, types, constraints, defaults) to its core "
        f"counterpart. Docstring / title / examples drift is "
        f"ignored."
    )
