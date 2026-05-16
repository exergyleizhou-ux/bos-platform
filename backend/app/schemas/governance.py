"""Shared governance envelope schemas for release-facing BOS surfaces."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


GateState = Literal["review_required"]
ActionBoundary = Literal["forbidden", "requires_confirmation"]
ClaimStatus = Literal["validated", "supported_not_closed", "planned"]


class ReleaseGovernanceActionBoundary(BaseModel):
    action: str
    boundary: ActionBoundary
    reason: str


class ReleaseGovernanceClaim(BaseModel):
    claim: str
    status: ClaimStatus
    source_boundary: str


class ReleaseGovernanceEnvelope(BaseModel):
    schema_version: str = "release_governance_envelope_v1"
    gate_state: GateState = "review_required"
    evidence_chain_id: str | None = None
    source_boundary: str
    human_review_required: bool = True
    review_required_reason: str
    validated_default_write_enabled: bool = False
    final_action_execution_enabled: bool = False
    runtime_activation_enabled: bool = False
    hardware_execution_enabled: bool = False
    external_share_status: ActionBoundary = "requires_confirmation"
    action_boundaries: list[ReleaseGovernanceActionBoundary] = Field(default_factory=list)
    claim_ledger: list[ReleaseGovernanceClaim] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


class BOSV9RCManifestSafetyBoundary(BaseModel):
    release_decision: Literal["review_required"]
    model_version: Literal["ready_for_review"]
    final_action_draft_count: Literal[0]
    final_action_audit_record_count: Literal[0]
    external_share_record_created: Literal[False]
    final_action_execute_call_count: Literal[0]
    validated_default_write_enabled: Literal[False]
    runtime_activation_enabled: Literal[False]
    hardware_execution_enabled: Literal[False]
    final_action_execution_enabled: Literal[False]


class BOSV9RCManifestResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    generated_at: str
    release_state: Literal["review_required"]
    candidate_evidence_state: Literal["pending", "review_required", "ready_for_review"]
    preflight_pass_count: int
    preflight_warn_count: int
    preflight_fail_count: int
    review_required_items: list[str]
    local_validation_notes: list[str]
    recommended_next_action: str | None = None
    bos_v9_target_progress_percent: int
    bos_v9_target_scorecard: list[dict[str, Any]]
    safety_boundary: BOSV9RCManifestSafetyBoundary
    release_reference_smoke_passed: bool
    checks: list[dict[str, Any]]
    artifacts: dict[str, str]
