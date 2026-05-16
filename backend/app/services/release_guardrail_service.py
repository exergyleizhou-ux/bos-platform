"""Central release-facing guardrail contract.

This module is intentionally read-only. It gives Assistant, Release Center,
Reference Atlas, Simulation Lab, and final-action readiness the same safety
language without enabling any production action.
"""

from __future__ import annotations

from app.schemas.governance import (
    ReleaseGovernanceActionBoundary,
    ReleaseGovernanceClaim,
    ReleaseGovernanceEnvelope,
)

DEFAULT_RELEASE_GUARDRAILS = [
    "release_decision_remains_review_required",
    "human_review_required_before_state_promotion",
    "validated_default_write_enabled_false",
    "final_action_execution_enabled_false",
    "runtime_activation_enabled_false",
    "hardware_execution_enabled_false",
    "external_share_requires_confirmation",
    "no_cross_tenant_action",
]

DEFAULT_ACTION_BOUNDARIES = [
    ReleaseGovernanceActionBoundary(
        action="external_share",
        boundary="requires_confirmation",
        reason="External release sharing needs explicit human confirmation and a separate audited delivery gate.",
    ),
    ReleaseGovernanceActionBoundary(
        action="final_decision",
        boundary="forbidden",
        reason="Assistant, review packets, simulations, and evidence packs cannot approve release decisions automatically.",
    ),
    ReleaseGovernanceActionBoundary(
        action="hardware_run",
        boundary="forbidden",
        reason="Hardware execution is outside the current BOS release candidate boundary.",
    ),
    ReleaseGovernanceActionBoundary(
        action="validated_default_write",
        boundary="forbidden",
        reason="External literature, public datasets, and staged references cannot mutate validated BOS defaults.",
    ),
    ReleaseGovernanceActionBoundary(
        action="runtime_activation",
        boundary="forbidden",
        reason="Runtime activation requires a separately audited workflow and is blocked for review evidence.",
    ),
]

DEFAULT_CLAIM_LEDGER = [
    ReleaseGovernanceClaim(
        claim="BOS protocol surfaces are inspectable software evidence.",
        status="validated",
        source_boundary="current_code_surface",
    ),
    ReleaseGovernanceClaim(
        claim="Literature and public-data values can inform review-gated candidates.",
        status="supported_not_closed",
        source_boundary="review_gated_external_seed",
    ),
    ReleaseGovernanceClaim(
        claim="Factory hardware execution and production release movement are available.",
        status="planned",
        source_boundary="deferred_runtime_workflow",
    ),
]


def build_release_governance_envelope(
    *,
    evidence_chain_id: str | None = None,
    source_boundary: str,
    review_required_reason: str = "human_review_required_before_state_promotion",
    guardrails: list[str] | None = None,
) -> ReleaseGovernanceEnvelope:
    merged_guardrails = list(dict.fromkeys([*(guardrails or []), *DEFAULT_RELEASE_GUARDRAILS]))
    return ReleaseGovernanceEnvelope(
        evidence_chain_id=evidence_chain_id,
        source_boundary=source_boundary,
        review_required_reason=review_required_reason,
        action_boundaries=DEFAULT_ACTION_BOUNDARIES,
        claim_ledger=DEFAULT_CLAIM_LEDGER,
        guardrails=merged_guardrails,
    )


def unsafe_governance_flags(envelope: ReleaseGovernanceEnvelope) -> list[str]:
    failures: list[str] = []
    if envelope.gate_state != "review_required":
        failures.append(f"gate_state_not_review_required:{envelope.gate_state}")
    if not envelope.human_review_required:
        failures.append("human_review_required_false")
    if envelope.validated_default_write_enabled:
        failures.append("validated_default_write_enabled_true")
    if envelope.final_action_execution_enabled:
        failures.append("final_action_execution_enabled_true")
    if envelope.runtime_activation_enabled:
        failures.append("runtime_activation_enabled_true")
    if envelope.hardware_execution_enabled:
        failures.append("hardware_execution_enabled_true")
    return failures
