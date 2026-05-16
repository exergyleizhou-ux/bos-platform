export interface BenchmarkCase {
  case_id: string;
  name: string;
  scenario_payload: Record<string, unknown>;
  expected_metrics: Record<string, unknown>;
}

export interface BenchmarkRunCase {
  case_id: string;
  name: string;
  status: "passed" | "failed" | string;
  simulation_id?: string;
  run_id?: string | null;
  evidence_pack_id?: string | null;
  metrics?: {
    ending_risk?: number;
    audit_event_count?: number;
    cycle_count?: number;
  };
  assertions?: Array<Record<string, unknown>>;
  expected_metrics?: Record<string, unknown>;
}

export interface BenchmarkRun {
  benchmark_run_id: string;
  suite_name: string;
  scorecard: {
    status?: string;
    suite_gate?: string;
    case_count?: number;
    passed_count?: number;
    failed_count?: number;
    cases?: BenchmarkRunCase[];
    [key: string]: unknown;
  };
  evidence_pack_id: string | null;
  created_at: string;
}

export interface ModelRegistryItem {
  model_id: string;
  name: string;
  task_type: string;
  status: string;
}

export interface ModelProviderCapability {
  model_id: string;
  provider: string;
  context_window: number | null;
  tool_calling: boolean | null;
  json_schema_output: boolean | null;
  vision: boolean | null;
  embedding: boolean | null;
  pricing_input: number | null;
  pricing_output: number | null;
  rate_limit: string | null;
  data_retention_policy: string | null;
  deployment_region: string | null;
  fallback_candidate: boolean;
  source_ref: string;
  checked_date: string;
  review_status: string;
  human_review_required: boolean;
  source_kind: string;
  license_note: string;
  runtime_activation_status?: string;
  metadata_policy?: string;
  registry_patch_id?: string | null;
  registry_version?: string | null;
  activation_id?: string | null;
  activation_scope?: Record<string, unknown> | null;
}

export interface ModelProviderCapabilityMatrix {
  providers: ModelProviderCapability[];
  count: number;
  active_provider_count?: number;
  review_gate: string;
  human_review_required: boolean;
  checked_date_policy: string;
  runtime_defaults_mutated?: boolean;
  requires_separate_runtime_activation?: boolean;
}

export interface ExternalKnowledgeCandidate {
  candidate_uid: string;
  candidate_type: string;
  key: string;
  source_kind: string;
  source_ref: string;
  license_note: string;
  ingestion_mode: string;
  review_status: string;
  human_review_required: boolean;
  approved_for_kernel_use: boolean;
  checked_date?: string | null;
  provider?: string;
  model_id?: string;
  unit?: string;
  region?: string | null;
  jurisdiction?: string | null;
  payload?: Record<string, unknown>;
}

export interface ExternalKnowledgeCandidateMatrix {
  candidates: ExternalKnowledgeCandidate[];
  count: number;
  review_gate: string;
  human_review_required: boolean;
  promotion_policy: {
    request_only: boolean;
    auto_promote: boolean;
    validated_defaults_mutated: boolean;
    manual_default_patch_required_after_approval: boolean;
  };
}

export interface ExternalKnowledgePromotionResponse {
  approval_request_id: string;
  status: string;
  subject_type: string;
  subject_id: string;
  candidate_type: string;
  candidate_key: string;
  candidate_uid: string;
  reason: string | null;
  evidence_pack_id: string | null;
  knowledge_relation_id: string | null;
  review_gate: string;
  human_review_required: boolean;
  promoted_to_validated_defaults: boolean;
  manual_default_patch_required: boolean;
  side_effects: Record<string, unknown>;
  created_at: string;
  resolved_at: string | null;
}

export interface ExternalKnowledgeRegistryPatchResponse {
  registry_patch_id: string;
  status: string;
  candidate_uid: string;
  registry_key: string;
  registry_version: string;
  approval_request_id: string;
  evidence_pack_id: string | null;
  validated_external_registry_updated: boolean;
  runtime_defaults_mutated: boolean;
  side_effects: Record<string, unknown>;
  created_at: string;
}

export interface ExternalKnowledgeValidatedRegistry {
  registry: ExternalKnowledgeRegistryPatchResponse[];
  count: number;
  registry_type: string;
  runtime_defaults_mutated: boolean;
  requires_separate_runtime_activation: boolean;
}

export interface ExternalKnowledgeRuntimeActivationReadiness {
  schema_version: string;
  tenant_id: number;
  activation_ready: boolean;
  executable?: boolean;
  executable_now?: boolean;
  target_found: boolean;
  registry_patch_id?: string | null;
  activation_scope?: Record<string, unknown>;
  current_active_state?: Record<string, unknown>;
  blockers: string[];
  required_roles: string[];
  side_effects_if_executed?: Record<string, unknown>;
  guardrails: string[];
}

export interface ExternalKnowledgeRuntimeActivationState {
  schema_version: string;
  tenant_id: number;
  runtime_defaults_mutated: boolean;
  active_scopes: Array<Record<string, unknown>>;
  activation_event_count: number;
  guardrails: string[];
}

export interface ExternalKnowledgeRuntimeActivationDraft {
  activation_request_id: string;
  status: string;
  registry_patch_id: string;
  candidate_type: string | null;
  candidate_key: string | null;
  registry_version: string | null;
  activation_scope: Record<string, unknown>;
  previous_active_registry_patch_id: string | null;
  previous_active_registry_version: string | null;
  rollback_target_registry_patch_id: string | null;
  rollback_target_activation_id: string | null;
  operator_attestation: string | null;
  review_evidence_ids: string[];
  evidence_pack_id: string | null;
  review_gate: string;
  human_review_required: boolean;
  runtime_activation_executed: boolean;
  side_effects: Record<string, unknown>;
  created_at: string;
  resolved_at: string | null;
}

export interface ExternalKnowledgeRuntimeActivationExecutionReadiness {
  activation_request_id: string;
  registry_patch_id?: string;
  status?: string;
  activation_ready: boolean;
  executable_now: boolean;
  blockers: string[];
  target_found: boolean;
  activation_scope?: Record<string, unknown>;
  previous_active_registry_patch_id?: string | null;
  previous_active_registry_version?: string | null;
  rollback_target_registry_patch_id?: string | null;
  rollback_target_activation_id?: string | null;
  source_evidence_pack_ids: string[];
  required_roles: string[];
  would_write_activation_record_now: boolean;
  side_effects_if_executed: Record<string, unknown>;
  guardrails: string[];
}

export interface ExternalKnowledgeRuntimeActivationRecord {
  activation_id: string;
  registry_patch_id: string;
  predicate: string;
  activation_scope: Record<string, unknown>;
  registry_version: string | null;
  previous_active_registry_patch_id: string | null;
  previous_active_registry_version: string | null;
  rollback_target_registry_patch_id: string | null;
  rollback_target_activation_id: string | null;
  idempotency_key: string | null;
  status: string;
  side_effects: Record<string, unknown>;
  evidence_pack_id: string | null;
  created_at: string;
}

export interface ModelRegistrationResponse {
  model_id: string;
  model_version_id: string;
  status: string;
  version_status: string;
  metadata_payload: Record<string, unknown>;
}

export interface ModelGovernanceResponse {
  model_id: string;
  model_version_id: string;
  model_status: string;
  version_status: string;
  knowledge_relation_id: string;
  evidence_pack_id: string | null;
  approval_request_id: string | null;
}

export interface KnowledgeRelation {
  relation_id: string;
  subject_type: string;
  subject_id: string;
  predicate: string;
  object_type: string;
  object_id: string;
  evidence_pack_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}
