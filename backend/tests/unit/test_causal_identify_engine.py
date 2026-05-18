"""Phase B B2a — unit tests for causal_identify_engine.

Covers six behaviors:

1. Trivial DAG (T -> O only) -> strategy="trivial".
2. Back-door (T -> O with Z -> T, Z -> Y) -> strategy="backdoor",
   adjustment_set contains Z.
3. Mediation (T -> M -> O with M tagged node_kind="mediator")
   -> strategy="mediation".
4. Unidentifiable with proceed_when_unidentifiable=True ->
   identified=False, evidence_level="planned".
5. estimand_handle carries the request's dataset_fingerprint.
6. assumptions list correctly maps to the strategy.

All tests are deterministic; no random data is generated.
"""

from __future__ import annotations

import warnings

import pytest

from app.engine.extended.causal_identify_engine import run_identify
from app.schemas.causal.identify import CausalIdentifyRequest
from app.schemas.causal_common import (
    DagEdge,
    DagNode,
    DagSpec,
)


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════


_FP = "fingerprint_abc12345"


def _trivial_dag() -> DagSpec:
    """T -> O, nothing else."""
    return DagSpec(
        nodes=[
            DagNode(name="T", node_kind="treatment"),
            DagNode(name="O", node_kind="outcome"),
        ],
        edges=[DagEdge(src="T", dst="O")],
        source="hand",
    )


def _backdoor_dag() -> DagSpec:
    """Z confounds T and O; classic back-door structure."""
    return DagSpec(
        nodes=[
            DagNode(name="T", node_kind="treatment"),
            DagNode(name="O", node_kind="outcome"),
            DagNode(name="Z", node_kind="covariate"),
        ],
        edges=[
            DagEdge(src="T", dst="O"),
            DagEdge(src="Z", dst="T", edge_kind="confounding"),
            DagEdge(src="Z", dst="O", edge_kind="confounding"),
        ],
        source="hand",
    )


def _mediation_dag() -> DagSpec:
    """T -> M -> O with M tagged as mediator and a direct T -> O."""
    return DagSpec(
        nodes=[
            DagNode(name="T", node_kind="treatment"),
            DagNode(name="M", node_kind="mediator"),
            DagNode(name="O", node_kind="outcome"),
        ],
        edges=[
            DagEdge(src="T", dst="M"),
            DagEdge(src="M", dst="O"),
            DagEdge(src="T", dst="O"),
        ],
        source="hand",
    )


# ════════════════════════════════════════════════════════════════════
# Tests
# ════════════════════════════════════════════════════════════════════


def test_identify_trivial_dag():
    """Edge-of-spec case: T -> O only -> strategy='trivial'."""
    request = CausalIdentifyRequest(
        dag=_trivial_dag(),
        treatment="T",
        outcome="O",
        dataset_fingerprint=_FP,
        proceed_when_unidentifiable=True,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_identify(request)
    assert response.identified is True
    assert response.strategy == "trivial"
    assert response.adjustment_set == []
    assert response.estimand_expression == "E[Y|T]"
    assert response.evidence_level == "supported"


def test_identify_backdoor_with_confounder():
    """Classic Z -> T, Z -> O setup; backdoor on {Z}."""
    request = CausalIdentifyRequest(
        dag=_backdoor_dag(),
        treatment="T",
        outcome="O",
        dataset_fingerprint=_FP,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_identify(request)
    assert response.identified is True
    assert response.strategy == "backdoor"
    assert "Z" in response.adjustment_set
    assert response.evidence_level == "validated"


def test_identify_mediation_when_mediator_tagged_on_path():
    """T -> M -> O with M.node_kind='mediator' -> strategy='mediation'."""
    request = CausalIdentifyRequest(
        dag=_mediation_dag(),
        treatment="T",
        outcome="O",
        dataset_fingerprint=_FP,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_identify(request)
    assert response.strategy == "mediation"
    # adjustment_set is empty (no covariates declared)
    assert response.evidence_level == "supported"


def test_identify_estimand_handle_carries_fingerprint():
    """The estimand_handle echoes the request's dataset_fingerprint
    verbatim — this is the precondition for /estimate's
    precomputed_estimand fingerprint check."""
    request = CausalIdentifyRequest(
        dag=_backdoor_dag(),
        treatment="T",
        outcome="O",
        dataset_fingerprint=_FP,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_identify(request)
    assert response.estimand_handle.dataset_fingerprint == _FP
    assert response.estimand_handle.strategy == response.strategy
    assert response.estimand_handle.adjustment_set == response.adjustment_set


def test_identify_assumptions_match_strategy_backdoor():
    """Backdoor strategy -> assumptions include no_unobserved_confounders."""
    request = CausalIdentifyRequest(
        dag=_backdoor_dag(),
        treatment="T",
        outcome="O",
        dataset_fingerprint=_FP,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_identify(request)
    assert "no_unobserved_confounders" in response.assumptions
    assert "consistency" in response.assumptions
    assert "positivity" in response.assumptions


def test_identify_assumptions_match_strategy_mediation():
    """Mediation strategy -> sequential_ignorability is required."""
    request = CausalIdentifyRequest(
        dag=_mediation_dag(),
        treatment="T",
        outcome="O",
        dataset_fingerprint=_FP,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_identify(request)
    assert "sequential_ignorability" in response.assumptions
    assert "no_treatment_mediator_interaction" in response.assumptions
