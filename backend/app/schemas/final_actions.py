"""Read-only final action readiness schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.governance import ReleaseGovernanceEnvelope


FinalActionType = Literal["final_release_approval", "model_activation", "external_release_share"]
FinalActionStatus = Literal["locked", "blocked", "ready_for_final_review"]


class FinalActionEffectSummary(BaseModel):
    release_decision: str = "not_executed"
    model_activation: bool = False
    external_share: bool = False
    hardware_execution: bool = False


class FinalActionReadinessItem(BaseModel):
    action: FinalActionType
    status: FinalActionStatus
    executable: bool = False
    blockers: list[str] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)
    required_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence_ids: list[str] = Field(default_factory=list)
    source_review_packet_required: bool = True
    source_review_packet_id: str | None = None
    side_effects_if_executed: FinalActionEffectSummary = Field(default_factory=FinalActionEffectSummary)


class FinalActionReadinessState(BaseModel):
    latest_release_decision_id: int | None = None
    latest_release_decision: str | None = None
    latest_model_version_id: str | None = None
    latest_model_version_status: str | None = None
    pending_review_items: int
    resolved_review_items: int
    evidence_pack_ids: list[str] = Field(default_factory=list)
    external_share_record_created: bool = False
    final_action_request_drafts_created: bool = False


class FinalActionReadinessResponse(BaseModel):
    schema_version: str
    generated_at: str
    tenant_id: int
    review_only: bool = True
    audit_schema_available: bool = True
    request_draft_schema_available: bool = True
    source_review_packet_required: bool = True
    source_review_packet_id: str | None = None
    current_state: FinalActionReadinessState
    actions: list[FinalActionReadinessItem]
    governance_envelope: ReleaseGovernanceEnvelope
    guardrails: list[str] = Field(default_factory=list)


class FinalActionReviewPacketSnapshotResponse(BaseModel):
    schema_version: str = "final_action_review_packet_snapshot_v1"
    tenant_id: int
    review_only: bool = True
    source_review_packet_id: str
    packet_type: str
    packet_hash: str
    evidence_pack_ids: list[str] = Field(default_factory=list)
    generated_by_user_id: int
    created_at: str
    packet_payload: dict[str, Any]
    guardrails: list[str] = Field(default_factory=list)


class FinalActionAuditRecordResponse(BaseModel):
    final_action_id: str
    tenant_id: int
    action_type: str
    target_type: str
    target_id: str
    requested_by_user_id: int
    reviewed_by_user_id: int | None = None
    role_snapshot: dict[str, Any]
    source_review_packet_id: str
    source_evidence_pack_ids: list[str] = Field(default_factory=list)
    precondition_snapshot: dict[str, Any]
    before_state: dict[str, Any]
    after_state: dict[str, Any] | None = None
    decision: str
    reason: str | None = None
    idempotency_key: str
    status: str
    effect_summary: dict[str, Any]
    created_at: str
    resolved_at: str | None = None


class FinalActionAuditRecordListResponse(BaseModel):
    schema_version: str = "final_action_audit_records_read_model_v1"
    tenant_id: int
    review_only: bool = True
    count: int
    records: list[FinalActionAuditRecordResponse] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


class FinalReleaseApprovalRequest(BaseModel):
    final_action_request_id: str
    expected_current_decision: str = "review_required"
    operator_attestation: str
    idempotency_key: str


class FinalModelActivationRequest(BaseModel):
    final_action_request_id: str
    expected_current_version_status: str = "ready_for_review"
    operator_attestation: str
    idempotency_key: str


class FinalExternalReleaseShareRequest(BaseModel):
    final_action_request_id: str
    release_packet_attachment_id: str
    recipient_scope: str
    redaction_policy_id: str
    operator_attestation: str
    idempotency_key: str


class FinalExternalReleaseDeliveryRequest(BaseModel):
    share_id: str
    expected_delivery_status: str = "not_sent"
    delivery_channel: str = "webhook"
    delivery_endpoint: str
    external_network_send: bool = True
    operator_attestation: str
    idempotency_key: str


class FinalActionRequestDraftResponse(BaseModel):
    final_action_request_id: str
    tenant_id: int
    action_type: str
    target_type: str
    target_id: str
    requested_by_user_id: int
    source_review_packet_id: str
    source_evidence_pack_ids: list[str] = Field(default_factory=list)
    request_payload: dict[str, Any]
    preflight_snapshot: dict[str, Any]
    role_snapshot: dict[str, Any]
    idempotency_key: str
    status: str
    created_at: str
    updated_at: str


class FinalActionRequestDraftListResponse(BaseModel):
    schema_version: str = "final_action_request_drafts_read_model_v1"
    tenant_id: int
    review_only: bool = True
    count: int
    drafts: list[FinalActionRequestDraftResponse] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


class FinalActionRequestDraftCreateRequest(BaseModel):
    action_type: FinalActionType
    target_type: str
    target_id: str
    source_review_packet_id: str
    idempotency_key: str


class FinalActionRequestDraftResolveRequest(BaseModel):
    approved: bool
    reason: str | None = None


class FinalActionExecutionReadinessResponse(BaseModel):
    schema_version: str = "final_action_execution_readiness_v1"
    tenant_id: int
    review_only: bool = True
    final_action_request_id: str
    action_type: str
    target_type: str
    target_id: str
    draft_status: str
    ready_for_audited_execution: bool = False
    executable_now: bool = False
    blockers: list[str] = Field(default_factory=list)
    target_found: bool = False
    target_state: dict[str, Any] = Field(default_factory=dict)
    source_review_packet_found: bool = False
    source_evidence_pack_ids: list[str] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)
    would_write_audit_record_now: bool = False
    side_effects_if_executed: FinalActionEffectSummary = Field(default_factory=FinalActionEffectSummary)
    guardrails: list[str] = Field(default_factory=list)


class FinalActionPreflightInput(BaseModel):
    action_type: FinalActionType
    target_type: str
    target_id: str
    source_review_packet_id: str
    idempotency_key: str
    requested_by_user_id: int


class FinalActionPreflightResult(BaseModel):
    schema_version: str = "final_action_preflight_v1"
    tenant_id: int
    review_only: bool = True
    action_type: FinalActionType
    target_type: str
    target_id: str
    requested_by_user_id: int
    source_review_packet_id: str
    idempotency_key: str
    eligible: bool = False
    executable: bool = False
    blockers: list[str] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)
    source_review_packet_found: bool = False
    evidence_pack_ids: list[str] = Field(default_factory=list)
    would_create_request_draft: bool = False
    would_write_audit_record: bool = False
    side_effects_if_executed: FinalActionEffectSummary = Field(default_factory=FinalActionEffectSummary)
    guardrails: list[str] = Field(default_factory=list)
