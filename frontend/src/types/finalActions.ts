export type FinalActionStatus = "locked" | "blocked" | "ready_for_final_review";

export interface ReleaseGovernanceActionBoundary {
  action: string;
  boundary: "forbidden" | "requires_confirmation";
  reason: string;
}

export interface ReleaseGovernanceClaim {
  claim: string;
  status: "validated" | "supported_not_closed" | "planned";
  source_boundary: string;
}

export interface ReleaseGovernanceEnvelope {
  schema_version: string;
  gate_state: "review_required";
  evidence_chain_id: string | null;
  source_boundary: string;
  human_review_required: boolean;
  review_required_reason: string;
  validated_default_write_enabled: boolean;
  final_action_execution_enabled: boolean;
  runtime_activation_enabled: boolean;
  hardware_execution_enabled: boolean;
  external_share_status: "forbidden" | "requires_confirmation";
  action_boundaries: ReleaseGovernanceActionBoundary[];
  claim_ledger: ReleaseGovernanceClaim[];
  guardrails: string[];
}

export interface FinalActionEffectSummary {
  release_decision: string;
  model_activation: boolean;
  external_share: boolean;
  hardware_execution: boolean;
}

export interface FinalActionReadinessItem {
  action: "final_release_approval" | "model_activation" | "external_release_share";
  status: FinalActionStatus;
  executable: boolean;
  blockers: string[];
  required_roles: string[];
  required_evidence_ids: string[];
  missing_evidence_ids: string[];
  source_review_packet_required: boolean;
  source_review_packet_id: string | null;
  side_effects_if_executed: FinalActionEffectSummary;
}

export interface FinalActionReadinessState {
  latest_release_decision_id: number | null;
  latest_release_decision: string | null;
  latest_model_version_id: string | null;
  latest_model_version_status: string | null;
  pending_review_items: number;
  resolved_review_items: number;
  evidence_pack_ids: string[];
  external_share_record_created: boolean;
  final_action_request_drafts_created: boolean;
}

export interface FinalActionReadinessResponse {
  schema_version: string;
  generated_at: string;
  tenant_id: number;
  review_only: boolean;
  audit_schema_available: boolean;
  request_draft_schema_available: boolean;
  source_review_packet_required: boolean;
  source_review_packet_id: string | null;
  current_state: FinalActionReadinessState;
  actions: FinalActionReadinessItem[];
  governance_envelope: ReleaseGovernanceEnvelope;
  guardrails: string[];
}

export interface FinalActionReviewPacketSnapshotResponse {
  schema_version: string;
  tenant_id: number;
  review_only: boolean;
  source_review_packet_id: string;
  packet_type: string;
  packet_hash: string;
  evidence_pack_ids: string[];
  generated_by_user_id: number;
  created_at: string;
  packet_payload: Record<string, unknown>;
  guardrails: string[];
}

export interface FinalActionAuditRecordItem {
  final_action_id: string;
  tenant_id: number;
  action_type: string;
  target_type: string;
  target_id: string;
  requested_by_user_id: number;
  reviewed_by_user_id: number | null;
  role_snapshot: Record<string, unknown>;
  source_review_packet_id: string;
  source_evidence_pack_ids: string[];
  precondition_snapshot: Record<string, unknown>;
  before_state: Record<string, unknown>;
  after_state: Record<string, unknown> | null;
  decision: string;
  reason: string | null;
  idempotency_key: string;
  status: string;
  effect_summary: Record<string, unknown>;
  created_at: string;
  resolved_at: string | null;
}

export interface FinalActionAuditRecordListResponse {
  schema_version: string;
  tenant_id: number;
  review_only: boolean;
  count: number;
  records: FinalActionAuditRecordItem[];
  guardrails: string[];
}

export interface FinalReleaseApprovalRequest {
  final_action_request_id: string;
  expected_current_decision: string;
  operator_attestation: string;
  idempotency_key: string;
}

export interface FinalModelActivationRequest {
  final_action_request_id: string;
  expected_current_version_status: string;
  operator_attestation: string;
  idempotency_key: string;
}

export interface FinalExternalReleaseShareRequest {
  final_action_request_id: string;
  release_packet_attachment_id: string;
  recipient_scope: string;
  redaction_policy_id: string;
  operator_attestation: string;
  idempotency_key: string;
}

export interface FinalExternalReleaseDeliveryRequest {
  share_id: string;
  expected_delivery_status: string;
  delivery_channel: string;
  delivery_endpoint: string;
  external_network_send: boolean;
  operator_attestation: string;
  idempotency_key: string;
}

export interface FinalActionRequestDraftItem {
  final_action_request_id: string;
  tenant_id: number;
  action_type: string;
  target_type: string;
  target_id: string;
  requested_by_user_id: number;
  source_review_packet_id: string;
  source_evidence_pack_ids: string[];
  request_payload: Record<string, unknown>;
  preflight_snapshot: Record<string, unknown>;
  role_snapshot: Record<string, unknown>;
  idempotency_key: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface FinalActionRequestDraftListResponse {
  schema_version: string;
  tenant_id: number;
  review_only: boolean;
  count: number;
  drafts: FinalActionRequestDraftItem[];
  guardrails: string[];
}

export interface FinalActionRequestDraftCreateRequest {
  action_type: "final_release_approval" | "model_activation" | "external_release_share";
  target_type: string;
  target_id: string;
  source_review_packet_id: string;
  idempotency_key: string;
}

export interface FinalActionRequestDraftResolveRequest {
  approved: boolean;
  reason?: string | null;
}

export interface FinalActionExecutionReadinessResponse {
  schema_version: string;
  tenant_id: number;
  review_only: boolean;
  final_action_request_id: string;
  action_type: string;
  target_type: string;
  target_id: string;
  draft_status: string;
  ready_for_audited_execution: boolean;
  executable_now: boolean;
  blockers: string[];
  target_found: boolean;
  target_state: Record<string, unknown>;
  source_review_packet_found: boolean;
  source_evidence_pack_ids: string[];
  required_roles: string[];
  would_write_audit_record_now: boolean;
  side_effects_if_executed: FinalActionEffectSummary;
  guardrails: string[];
}
