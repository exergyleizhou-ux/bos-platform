"""Phase B E2E full-chain causal test (Plan v2 §7 #5 + #11).

Exercises all five `/api/v1/causal/*` endpoint engines in
sequence, verifying the handle chain (``estimand_handle`` from
identify -> precomputed_estimand on estimate; ``estimate_handle``
from estimate -> refute + sensitivity). The mediation branch
uses a separate single-mediator DAG because the B2a backdoor
bench has no mediator node.

No FastAPI / TestClient: tests call engine functions directly,
matching the strict "no app.main import" convention from B2a
onwards. Each step asserts that:

1. The engine returns a typed Response (Pydantic-validated).
2. Cross-step handles round-trip cleanly (the
   estimand_handle / estimate_handle from step N is accepted by
   step N+1 verbatim).
3. The aggregate evidence_level chain is honest: identify can
   produce 'validated'; refute can promote / hold; sensitivity
   reflects the bound.

This is the closest the unit suite gets to a real-world flow.
The agent-layer LangGraph wiring (Plan v2 §3) is out of scope
for B5 — that's B4. B5 only verifies the engine handles compose.
"""

from __future__ import annotations

import hashlib
import warnings

import numpy as np
import pytest

from app.engine.extended.causal_estimate_engine import run_estimate
from app.engine.extended.causal_identify_engine import run_identify
from app.engine.extended.causal_mediation_engine import run_mediation
from app.engine.extended.causal_refute_engine import run_refute
from app.engine.extended.causal_sensitivity_engine import run_sensitivity
from app.schemas.causal.estimate import CausalEstimateRequest
from app.schemas.causal.identify import CausalIdentifyRequest
from app.schemas.causal.mediation import CausalMediationRequest
from app.schemas.causal.refute import CausalRefuteRequest
from app.schemas.causal.sensitivity import CausalSensitivityRequest
from app.schemas.causal_common import (
    CausalData,
    DagEdge,
    DagNode,
    DagSpec,
    MethodParams,
)


# ════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════


def _fingerprint(columns, n):
    cols = ",".join(sorted(columns))
    return hashlib.sha256(
        f"{cols}|n={n}".encode("utf-8")
    ).hexdigest()[:32]


def _backdoor_dag() -> DagSpec:
    """Z -> T, Z -> Y, T -> Y."""
    return DagSpec(
        nodes=[
            DagNode(name="T", node_kind="treatment"),
            DagNode(name="Y", node_kind="outcome"),
            DagNode(name="Z", node_kind="covariate"),
        ],
        edges=[
            DagEdge(src="T", dst="Y"),
            DagEdge(src="Z", dst="T", edge_kind="confounding"),
            DagEdge(src="Z", dst="Y", edge_kind="confounding"),
        ],
        source="hand",
    )


def _backdoor_bench(n: int = 200, true_ate: float = 2.0, seed: int = 42):
    rng = np.random.default_rng(seed)
    Z = rng.normal(0, 1, n)
    T = 0.5 * Z + rng.normal(0, 1, n)
    Y = true_ate * T + 0.7 * Z + rng.normal(0, 1, n)
    rows = [
        {"T": float(T[i]), "Y": float(Y[i]), "Z": float(Z[i])}
        for i in range(n)
    ]
    return rows, _fingerprint(["T", "Y", "Z"], n)


def _mediation_dag() -> DagSpec:
    """T -> M -> Y, T -> Y, Z -> {T,Y}. Single mediator."""
    return DagSpec(
        nodes=[
            DagNode(name="T", node_kind="treatment"),
            DagNode(name="M", node_kind="mediator"),
            DagNode(name="Y", node_kind="outcome"),
            DagNode(name="Z", node_kind="covariate"),
        ],
        edges=[
            DagEdge(src="T", dst="M"),
            DagEdge(src="M", dst="Y"),
            DagEdge(src="T", dst="Y"),
            DagEdge(src="Z", dst="T", edge_kind="confounding"),
            DagEdge(src="Z", dst="Y", edge_kind="confounding"),
        ],
        source="hand",
    )


def _mediation_bench(n: int = 200, seed: int = 42):
    """B2b.2 §3 mediation bench targeting proportion_mediated ≈ 0.789."""
    rng = np.random.default_rng(seed)
    Z = rng.normal(0, 1, n)
    T = 0.5 * Z + rng.normal(0, 1, n)
    M = 1.0 * T + 0.4 * Z + rng.normal(0, 1, n)
    Y = 1.5 * M + 0.4 * T + 0.5 * Z + rng.normal(0, 1, n)
    rows = [
        {"T": float(T[i]), "M": float(M[i]),
         "Y": float(Y[i]), "Z": float(Z[i])}
        for i in range(n)
    ]
    return rows, _fingerprint(["T", "Y", "M", "Z"], n)


# ════════════════════════════════════════════════════════════════════
# The full E2E chain — identify → estimate → refute → sensitivity,
# plus a separate mediation pass on the mediator DAG.
# ════════════════════════════════════════════════════════════════════


def test_phase_b_e2e_full_chain():
    """One pytest case, five engines, one auditable chain."""
    rows, fp = _backdoor_bench(n=200, true_ate=2.0, seed=42)

    # ──────────────────────────────────────────────────────────────
    # Step 1: /identify
    # ──────────────────────────────────────────────────────────────
    identify_req = CausalIdentifyRequest(
        dag=_backdoor_dag(),
        treatment="T",
        outcome="Y",
        dataset_fingerprint=fp,
        proceed_when_unidentifiable=False,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        identify_res = run_identify(identify_req)

    # The backdoor DAG should resolve to a backdoor strategy on {Z}.
    assert identify_res.identified is True
    assert identify_res.strategy == "backdoor", (
        f"expected backdoor strategy on Z->T->Y; got "
        f"{identify_res.strategy!r}"
    )
    assert "Z" in identify_res.adjustment_set
    assert identify_res.evidence_level in {"validated", "supported"}

    estimand_handle = identify_res.estimand_handle
    assert estimand_handle.strategy == "backdoor"
    assert estimand_handle.dataset_fingerprint == fp

    # ──────────────────────────────────────────────────────────────
    # Step 2: /estimate (precomputed_estimand from step 1)
    # ──────────────────────────────────────────────────────────────
    estimate_req = CausalEstimateRequest(
        dag=_backdoor_dag(),
        treatment="T",
        outcome="Y",
        data=CausalData(inline=rows, fingerprint=fp),
        method_family="linear_regression",
        method_params=MethodParams(),
        precomputed_estimand=estimand_handle,
        seed=42,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        estimate_res = run_estimate(estimate_req)

    # ATE ~ 2.0 on the strong-effect bench.
    assert abs(estimate_res.point_estimate - 2.0) < 0.25, (
        f"estimate.point_estimate {estimate_res.point_estimate} not "
        f"within 0.25 of true 2.0"
    )
    # CI brackets the point (schema validator already enforces, but
    # we re-assert for evidence in this E2E trace).
    assert (
        estimate_res.ci_lower
        <= estimate_res.point_estimate
        <= estimate_res.ci_upper
    )
    # Engine should have used the precomputed estimand (no
    # re-identification).
    assert estimate_res.diagnostics.used_precomputed_estimand is True, (
        "step 2 should report used_precomputed_estimand=True after "
        "step 1's handle was passed verbatim"
    )

    estimate_handle = estimate_res.estimate_handle
    assert estimate_handle.dag.source == "hand"
    assert estimate_handle.treatment == "T"
    assert estimate_handle.outcome == "Y"
    assert estimate_handle.method_family == "linear_regression"

    # ──────────────────────────────────────────────────────────────
    # Step 3: /refute (estimate_handle from step 2)
    # ──────────────────────────────────────────────────────────────
    refute_req = CausalRefuteRequest(
        estimate_handle=estimate_handle,
        refuters=[
            "random_common_cause",
            "placebo_treatment_refuter",
        ],
        seed=42,
        original_e_value=estimate_res.e_value_cheap,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        refute_res = run_refute(refute_req)

    # The two refuters above should both pass on the well-specified
    # backdoor bench. Schema uses ``refute_results`` (plural of the
    # outer list) and each item carries ``refuter`` (not
    # ``refuter_name``) per ``schemas/causal/refute.py``.
    assert len(refute_res.refute_results) == 2
    refuter_names = [r.refuter for r in refute_res.refute_results]
    assert set(refuter_names) == {
        "random_common_cause", "placebo_treatment_refuter",
    }
    assert all(r.passed for r in refute_res.refute_results), (
        f"all sampled refuters should pass on the well-specified "
        f"bench; got verdicts "
        f"{[(r.refuter, r.passed) for r in refute_res.refute_results]}"
    )
    # evidence_level: 'supported' is the typical outcome with only
    # 2 of 4 mandatory refuters run; 'validated' would require all 4.
    assert refute_res.evidence_level in {"supported", "validated"}

    # ──────────────────────────────────────────────────────────────
    # Step 4: /sensitivity (estimate_handle from step 2)
    # ──────────────────────────────────────────────────────────────
    sensitivity_req = CausalSensitivityRequest(
        estimate_handle=estimate_handle,
        method="evalue",
        seed=42,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sensitivity_res = run_sensitivity(sensitivity_req)

    assert sensitivity_res.method == "evalue"
    assert sensitivity_res.evalue_detail is not None
    # Strong-effect bench → E-value > 1.5 → overall_robust=True →
    # evidence_level='validated' on this branch.
    assert sensitivity_res.overall_robust is True
    assert sensitivity_res.evidence_level == "validated"
    assert sensitivity_res.evalue_detail.e_value_lower_ci > 1.5

    # ──────────────────────────────────────────────────────────────
    # Step 5: /mediation (separate DAG with a mediator)
    # ──────────────────────────────────────────────────────────────
    med_rows, med_fp = _mediation_bench(n=200, seed=42)
    mediation_req = CausalMediationRequest(
        dag=_mediation_dag(),
        treatment="T",
        outcome="Y",
        mediators=["M"],
        data=CausalData(inline=med_rows, fingerprint=med_fp),
        decomposition="natural",
        seed=42,
        n_bootstrap=100,
        assumptions_acknowledged=["consistency"],
        mode="sync",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mediation_res = run_mediation(mediation_req)

    # Pearl identity holds on the point estimate (engine snap).
    d = mediation_res.decomposition
    pearl_gap = abs(d.direct_effect + d.indirect_effect - d.total_effect)
    assert pearl_gap < 1e-3, (
        f"Pearl identity violated: gap={pearl_gap}"
    )
    # proportion_mediated in [0.55, 1.05] — paper-headline anchored
    # range from B2b.2 (DoWhy NDE underestimation known limitation).
    assert 0.55 < mediation_res.proportion_mediated < 1.05
    assert mediation_res.diagnostics.method == "dowhy_two_stage"


# ════════════════════════════════════════════════════════════════════
# Aggregate audit: the chain produces a coherent evidence story.
# ════════════════════════════════════════════════════════════════════


def test_phase_b_e2e_evidence_chain_coherent():
    """Quick lightweight repeat: identify → estimate → sensitivity
    only, asserting evidence_level monotonicity (sensitivity 'validated'
    requires the upstream estimate to exist and the bound to be safe).
    Refute + mediation are covered by the main E2E above; this
    sub-test is the cheap sanity that the evidence_level field flows
    coherently from one stage to the next.
    """
    rows, fp = _backdoor_bench(n=200, true_ate=2.0, seed=42)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        identify_res = run_identify(
            CausalIdentifyRequest(
                dag=_backdoor_dag(),
                treatment="T",
                outcome="Y",
                dataset_fingerprint=fp,
            )
        )
        estimate_res = run_estimate(
            CausalEstimateRequest(
                dag=_backdoor_dag(),
                treatment="T",
                outcome="Y",
                data=CausalData(inline=rows, fingerprint=fp),
                method_family="linear_regression",
                method_params=MethodParams(),
                precomputed_estimand=identify_res.estimand_handle,
                seed=42,
            )
        )
        sensitivity_res = run_sensitivity(
            CausalSensitivityRequest(
                estimate_handle=estimate_res.estimate_handle,
                method="evalue",
                seed=42,
            )
        )

    # identify: validated when backdoor with non-empty adj set.
    assert identify_res.evidence_level in {"validated", "supported"}
    # estimate: supported when no small-sample clamp, validated only
    # after refute. Here we expect supported.
    assert estimate_res.evidence_level == "supported"
    # sensitivity: validated when overall_robust (true on this bench).
    assert sensitivity_res.evidence_level == "validated"


# ════════════════════════════════════════════════════════════════════
# Handle round-trip
# ════════════════════════════════════════════════════════════════════


def test_phase_b_e2e_handle_round_trip():
    """The handles serialise + deserialise cleanly.

    Stricter than the engine chain above — checks that an
    IdentifiedEstimandHandle / EstimateHandle survive
    ``model_dump_json`` + ``model_validate_json`` without information
    loss. This is what the Phase B router actually does when the
    handles cross a JSON boundary (Plan v2's stateless audit
    rationale).
    """
    rows, fp = _backdoor_bench(n=200, true_ate=2.0, seed=42)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        identify_res = run_identify(
            CausalIdentifyRequest(
                dag=_backdoor_dag(),
                treatment="T",
                outcome="Y",
                dataset_fingerprint=fp,
            )
        )

    handle = identify_res.estimand_handle
    serialised = handle.model_dump_json()
    rehydrated = type(handle).model_validate_json(serialised)
    assert rehydrated.strategy == handle.strategy
    assert rehydrated.adjustment_set == handle.adjustment_set
    assert rehydrated.dataset_fingerprint == handle.dataset_fingerprint
    assert rehydrated.estimand_expression == handle.estimand_expression

    # Continue the chain with the rehydrated handle.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        estimate_res = run_estimate(
            CausalEstimateRequest(
                dag=_backdoor_dag(),
                treatment="T",
                outcome="Y",
                data=CausalData(inline=rows, fingerprint=fp),
                method_family="linear_regression",
                method_params=MethodParams(),
                precomputed_estimand=rehydrated,
                seed=42,
            )
        )
    assert estimate_res.diagnostics.used_precomputed_estimand is True, (
        "rehydrated handle should still trigger the "
        "precomputed-estimand short-circuit"
    )
    assert abs(estimate_res.point_estimate - 2.0) < 0.25


# ════════════════════════════════════════════════════════════════════
# Mediation isolation
# ════════════════════════════════════════════════════════════════════


def test_phase_b_e2e_mediation_independent_branch():
    """Mediation does not require the upstream identify/estimate chain.

    /mediation accepts a fresh DAG + data and runs Pearl
    decomposition standalone (its API takes data + DAG verbatim,
    not an EstimateHandle). This test pins that contract — a
    future refactor that tries to thread an estimate_handle
    through /mediation would have to update this test
    intentionally.
    """
    med_rows, med_fp = _mediation_bench(n=200, seed=42)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = run_mediation(
            CausalMediationRequest(
                dag=_mediation_dag(),
                treatment="T",
                outcome="Y",
                mediators=["M"],
                data=CausalData(inline=med_rows, fingerprint=med_fp),
                decomposition="natural",
                seed=42,
                n_bootstrap=100,
                assumptions_acknowledged=["consistency"],
                mode="sync",
            )
        )
    # Mediation Response carries the branch tag on diagnostics.method
    # (not on a top-level field — top-level is the Pearl decomposition
    # + CI bands). Single mediator -> DoWhy two-stage branch.
    assert res.diagnostics.method == "dowhy_two_stage"
    assert 0.55 < res.proportion_mediated < 1.05


# ════════════════════════════════════════════════════════════════════
# Negative path: handle drift between identify and estimate
# ════════════════════════════════════════════════════════════════════


def test_phase_b_e2e_dataset_fingerprint_drift_audit():
    """Sanity: the dataset_fingerprint on the IdentifiedEstimandHandle
    reflects the dataset fed to identify. If a caller passes a
    handle whose fingerprint doesn't match the dataset they then
    feed to /estimate, the audit chain can detect this — the
    handle's fingerprint is preserved verbatim across the chain
    (it's a contract field on the handle, not derived).

    This test is paranoia, not a 422 expectation: B2a's /estimate
    does not validate fingerprint match (the schema is structural).
    Phase G could add a contract gate. For now we assert that the
    handle simply carries the fingerprint forward unaltered.
    """
    rows, fp = _backdoor_bench(n=200, true_ate=2.0, seed=42)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        identify_res = run_identify(
            CausalIdentifyRequest(
                dag=_backdoor_dag(),
                treatment="T",
                outcome="Y",
                dataset_fingerprint=fp,
            )
        )
    assert identify_res.estimand_handle.dataset_fingerprint == fp
    # Same handle field after serialisation round-trip.
    handle_json = identify_res.estimand_handle.model_dump_json()
    assert fp in handle_json
