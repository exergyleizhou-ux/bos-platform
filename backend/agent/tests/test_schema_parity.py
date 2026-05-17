"""Schema-parity: every agent mirror MUST advertise the same
SCHEMA_VERSION as its Core counterpart (Plan v2 paragraph 3.4).

If a Core schema bumps but the agent mirror does not, this test fails
and forces the maintainer to update both sides in the same change.

Note: this is the one place in the agent test suite where importing
``app.schemas.*`` is allowed - the parity check by definition needs
both sides. The architectural isolation rule covers runtime code only.
"""

from __future__ import annotations

import pytest

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
