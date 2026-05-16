import type { VisionObservation } from "@/types/vision";

export interface MechanisticCDISER {
  score: number;
  alpha_s: number;
  beta_s: number;
  penalty: number;
  information_loss: number;
  evidence_balance: number;
}

export interface MechanisticHandoverEnvelope {
  tau_star_min: number;
  c_peak: number;
  f_clock: number;
  rise_rate: number;
  decay_rate: number;
}

export interface MechanisticInputs {
  mass_balance_ratio: number;
  metering_completeness: number;
  locality_shift_pct: number;
}

export interface MechanisticContext {
  c_di_ser: MechanisticCDISER;
  handover_envelope: MechanisticHandoverEnvelope;
  inputs: MechanisticInputs;
}

export interface SupervisorObservationSnapshot {
  uv254?: number;
  od280?: number;
  do?: number;
  ph?: number;
  elapsed_hours?: number;
  previous_c_signal_hat?: number;
  previous_elapsed_hours?: number;
  previous_dc_dt_hat?: number;
  previous_negative_slope_streak?: number;
  confidence_threshold?: number;
  negative_slope_persistence?: number;
  observability_required?: boolean;
}

export interface SupervisorDecisionSnapshot {
  c_signal_hat?: number;
  dc_dt_hat?: number | null;
  confidence?: number;
  missing_channels?: string[];
  channels_used?: string[];
  information_loss?: number;
  observability_score?: number;
  negative_slope_streak?: number;
  trigger_reason?: string | null;
  recommended_handover?: boolean;
  expected_freshness_window_hours?: number | null;
}

export interface SupervisorSnapshot {
  mode: string;
  recorded_at: string;
  observation?: SupervisorObservationSnapshot;
  decision?: SupervisorDecisionSnapshot;
}

export interface SignalCompileContext {
  compiler_version: string;
  source_batch_id: number;
  control_profile_id: number | null;
  locality_profile_id: number | null;
  applied_locality_shift: Record<string, unknown> | null;
  freshness_score: number;
  release_readiness_score: number;
  mechanistic_context?: MechanisticContext;
  native_model_stack?: Record<string, unknown>;
}

export interface SignalQcMarkers extends Record<string, unknown> {
  metering_completeness?: number;
  ser_proxy?: number | null;
  compile_context?: SignalCompileContext;
  supervisor_latest?: SupervisorSnapshot;
  supervisor_history?: SupervisorSnapshot[];
  vision_observation?: (VisionObservation & Record<string, unknown>) | null;
}

export interface SignalBatch {
  id: number;
  batch_id: number;
  user_id: number;
  tenant_id: number;
  signal_api_version: string;
  compiled_signal_id: string | null;
  potency: number | null;
  potency_unit: string | null;
  potency_basis: string | null;
  dose_window_min: number | null;
  dose_window_max: number | null;
  stability_window_hours: number | null;
  kernel_residence_time_hours: number | null;
  handover_time: string | null;
  freshness_state: string | null;
  qc_markers: SignalQcMarkers | null;
  notes: string | null;
  released_at: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SignalCompileRequest {
  batch_id: number;
  control_profile_id?: number;
  locality_profile_id?: number;
  dose_window_min?: number;
  dose_window_max?: number;
  stability_window_hours?: number;
  kernel_residence_time_hours?: number;
  compiler_version?: string;
  notes?: string;
  apply_locality_shifts?: boolean;
}

export interface SignalCompileResponse extends SignalBatch {
  compile_status: string;
  source_mode: string;
}

export interface SignalRefreshResponse {
  signal_batch: SignalBatch;
  refreshed_state: string;
  metering_age_hours: number | null;
  freshness_score: number;
  release_readiness_score: number;
}

export interface SignalBatchCreate {
  batch_id: number;
  signal_api_version?: string;
  compiled_signal_id?: string;
  potency?: number;
  potency_unit?: string;
  potency_basis?: string;
  dose_window_min?: number;
  dose_window_max?: number;
  stability_window_hours?: number;
  kernel_residence_time_hours?: number;
  handover_time?: string;
  freshness_state?: string;
  qc_markers?: Record<string, unknown>;
  notes?: string;
  released_at?: string;
  expires_at?: string;
}

export interface ControlAPIProfile {
  id: number;
  user_id: number;
  tenant_id: number;
  name: string;
  version: string;
  hal_min: number | null;
  hal_max: number | null;
  mtt: number | null;
  dose_window_min: number | null;
  dose_window_max: number | null;
  stability_window_hours: number | null;
  dwell_time_min_hours: number | null;
  dwell_time_max_hours: number | null;
  qc_thresholds: Record<string, unknown> | null;
  release_rules: Record<string, unknown> | null;
  active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ControlAPIProfileCreate {
  name: string;
  version: string;
  hal_min?: number;
  hal_max?: number;
  mtt?: number;
  dose_window_min?: number;
  dose_window_max?: number;
  stability_window_hours?: number;
  dwell_time_min_hours?: number;
  dwell_time_max_hours?: number;
  qc_thresholds?: Record<string, unknown>;
  release_rules?: Record<string, unknown>;
  active?: boolean;
  notes?: string;
}

export interface LocalityProfile {
  id: number;
  user_id: number;
  tenant_id: number;
  name: string;
  site_code: string | null;
  substrate_class: string | null;
  waste_state: Record<string, unknown> | null;
  pretreat_flags: Record<string, unknown> | null;
  dose_window_shift_pct: number | null;
  mtt_shift_pct: number | null;
  notes: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LocalityProfileCreate {
  name: string;
  site_code?: string;
  substrate_class?: string;
  waste_state?: Record<string, unknown>;
  pretreat_flags?: Record<string, unknown>;
  dose_window_shift_pct?: number;
  mtt_shift_pct?: number;
  notes?: string;
  active?: boolean;
}

export interface ExecutorProfile {
  id: number;
  locality_profile_id: number | null;
  user_id: number;
  tenant_id: number;
  executor_code: string;
  name: string;
  executor_type: string | null;
  hal_min: number | null;
  hal_max: number | null;
  mtt_nominal: number | null;
  plugin_mode: string | null;
  notes: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExecutorProfileCreate {
  locality_profile_id?: number;
  executor_code: string;
  name: string;
  executor_type?: string;
  hal_min?: number;
  hal_max?: number;
  mtt_nominal?: number;
  plugin_mode?: string;
  notes?: string;
  active?: boolean;
}

export interface BoundaryLedger {
  id: number;
  batch_id: number;
  signal_batch_id: number | null;
  user_id: number;
  tenant_id: number;
  d_prime: number | null;
  g_prime: number | null;
  ser_value: number | null;
  delta_delta_ser: number | null;
  closure_residual: number | null;
  metering_completeness: number | null;
  qc_flags: string[] | null;
  measured_vs_estimated: Record<string, unknown> | null;
  evidence_level: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReleaseDecision {
  id: number;
  batch_id: number;
  signal_batch_id: number | null;
  boundary_ledger_id: number | null;
  control_profile_id: number | null;
  user_id: number;
  tenant_id: number;
  decision: string;
  reason_codes: string[] | null;
  blocking_factors: string[] | null;
  warning_factors: string[] | null;
  passed_checks: string[] | null;
  trigger_metrics: (Record<string, unknown> & {
    mechanistic_context?: MechanisticContext;
  }) | null;
  applied_contract?: Record<string, unknown> | null;
  applied_locality_shift?: Record<string, unknown> | null;
  decision_confidence?: number | null;
  approver: string | null;
  rationale: string | null;
  decision_time: string;
  created_at: string;
}

export interface ReleaseEvaluationRequest {
  batch_id: number;
  control_profile_id?: number;
  signal_batch_id?: number;
  persist?: boolean;
  locality_profile_id?: number;
}

export interface PortabilityAudit {
  id: number;
  signal_batch_id: number;
  executor_profile_id: number;
  locality_profile_id: number | null;
  user_id: number;
  tenant_id: number;
  outcome: string;
  retuning_required: boolean;
  override_outcome: string | null;
  notes: string | null;
  trigger_metrics: Record<string, unknown> | null;
  created_at: string;
  recommended_outcome: string | null;
  rationale?: string | null;
  recommended_action?: string | null;
  requires_requalification?: boolean;
  retuning_axes: string[] | null;
  retuning_magnitude: number | null;
  portability_score: number | null;
}

export interface PortabilityAuditCreate {
  signal_batch_id: number;
  executor_profile_id: number;
  locality_profile_id?: number;
  outcome: string;
  retuning_required?: boolean;
  notes?: string;
  trigger_metrics?: Record<string, unknown>;
}

export interface PortabilityRecommendationRequest {
  signal_batch_id: number;
  executor_profile_id: number;
  locality_profile_id?: number;
}

export interface PortabilityRecommendationResponse {
  signal_batch_id: number;
  executor_profile_id: number;
  locality_profile_id: number | null;
  recommended_outcome: string;
  rationale: string;
  recommended_action: string;
  requires_requalification: boolean;
  retuning_axes: string[];
  retuning_magnitude: number | null;
  override_outcome: string | null;
  portability_score: number | null;
}

export interface BrainRuntimeDocument {
  key: string;
  title: string;
  relative_path: string;
  content: string;
  updated_at: string | null;
  line_count: number;
  is_missing: boolean;
}

export interface BrainRuntimeResponse {
  root_path: string;
  documents: BrainRuntimeDocument[];
  total_line_count: number;
  last_updated_at: string | null;
}

export interface BrainRuntimeUpdateRequest {
  content: string;
}

export interface AuditPacketPortabilityEntry {
  id: number;
  executor_profile_id: number;
  locality_profile_id: number | null;
  executor_name: string | null;
  locality_name: string | null;
  outcome: string;
  retuning_required: boolean;
  recommended_outcome?: string | null;
  rationale?: string | null;
  recommended_action?: string | null;
  requires_requalification?: boolean;
  retuning_axes?: string[] | null;
  retuning_magnitude?: number | null;
  portability_score?: number | null;
  trigger_metrics: Record<string, unknown> | null;
}

export interface AuditPacketPayload {
  batch: {
    id: number;
    batch_id: string;
    species: string;
    status: string;
  };
  signal_batch: {
    id: number;
    signal_api_version: string;
    compiled_signal_id: string | null;
    potency: number | null;
    potency_unit: string | null;
    freshness_state: string | null;
  } | null;
  control_profile: {
    id: number;
    name: string;
    version: string;
    mtt: number | null;
    hal_min: number | null;
    hal_max: number | null;
    dose_window_min: number | null;
    dose_window_max: number | null;
    stability_window_hours: number | null;
  } | null;
  boundary_ledger: {
    id: number | null;
    d_prime: number | null;
    g_prime: number | null;
    ser_value: number | null;
    delta_delta_ser: number | null;
    closure_residual: number | null;
    metering_completeness: number | null;
    qc_flags: string[];
    evidence_level: string | null;
    notes: string | null;
  } | null;
  release_decision: {
    decision: string;
    reason_codes: string[];
    blocking_factors: string[];
    warning_factors: string[];
    passed_checks: string[];
    trigger_metrics: Record<string, unknown>;
    decision_confidence?: number | null;
    rationale: string | null;
  } | null;
  portability_audits: AuditPacketPortabilityEntry[];
  native_model_stack?: NativeModelCatalog | Record<string, unknown> | null;
  native_forecast_evidence?: {
    model_key?: string;
    modality?: string;
    evidence_tier?: string;
    evidence_label?: string;
    evidence_summary?: string;
    execution_mode?: string;
    recorded_at?: string;
    artifact_path?: string;
    metric_name?: string;
    prediction_horizon?: number;
    forecast_preview?: string[];
    detection_count?: number;
    top_label?: string;
    top_candidates?: string[];
    bbox_summary?: string;
    is_live?: boolean;
  } | null;
  generation_context: {
    schema_version: string;
    compiled_at: string;
    compiled_by_user_id: number;
    source_mode?: string | null;
    source_ids: {
      signal_batch_id: number | null;
      control_profile_id: number | null;
      boundary_ledger_id: number | null;
      release_decision_id: number | null;
      portability_audit_ids: number[];
    };
    hash: string;
  };
}

export interface AuditPacket {
  id: number;
  batch_id: number;
  release_decision_id: number | null;
  user_id: number;
  tenant_id: number;
  packet_version: string;
  evidence_level: string | null;
  contract_evaluation: {
    status?: string;
    threshold_breaches?: string[];
    [key: string]: unknown;
  } | null;
  signal_validity: (Record<string, unknown> & {
    mechanistic_context?: MechanisticContext;
    supervisor_snapshot?: SupervisorSnapshot | null;
    supervisor_history?: SupervisorSnapshot[];
    vision_observation?: (VisionObservation & Record<string, unknown>) | null;
  }) | null;
  retuning_axes: Record<string, unknown> | null;
  packet: AuditPacketPayload | null;
  generated_at: string;
  created_at: string;
}

export interface BatchBosOverview {
  signal_batch: SignalBatch | null;
  control_profile: ControlAPIProfile | null;
  boundary_ledger: BoundaryLedger | null;
  release_decision: ReleaseDecision | null;
  audit_packet: AuditPacket | null;
  portability_audits: PortabilityAudit[];
  compile_status: string | null;
  latest_signal_status: string | null;
  latest_native_run?: NativeRunSummary | null;
}

export interface GuidanceItem {
  code: string;
  severity: "info" | "warning" | "critical";
  title: string;
  message: string;
  recommended_action: string;
  blocking: boolean;
}

export interface BatchGuidanceResponse {
  batch_id: number;
  gap_items: GuidanceItem[];
  recommended_actions: string[];
}

export interface SpeciesCatalogEntry {
  code: string;
  scientific_name: string;
  common_name: string;
  aliases: string[];
  source_basis: string;
  notes: string;
  references: string[];
  ser_typical: number;
  development_days: number;
  protein_content: number;
  fat_content: number;
}

export interface SpeciesCatalogResponse {
  species: SpeciesCatalogEntry[];
  count: number;
}

export type ReferenceReviewStatus = "pending_review" | "reviewed" | "rejected";

export interface BioexecutorCandidate {
  code: string;
  scientific_name: string;
  common_name: string;
  source_kind: string;
  source_ref: string;
  license_note: string;
  ingestion_mode: string;
  human_review_required: boolean;
  review_status: ReferenceReviewStatus;
  candidate_scope: string;
  notes: string;
  references: string[];
  related_feedstocks: string[];
}

export interface BioexecutorCandidateCatalogResponse {
  candidates: BioexecutorCandidate[];
  count: number;
  validated_species_codes: string[];
  candidate_codes: string[];
}

export interface FeedstockProfile {
  key: string;
  display_name: string;
  category: string;
  typical_cn_min: number | null;
  typical_cn_max: number | null;
  moisture_risk: string;
  contamination_risk: string;
  lignocellulose_severity: string;
  suitability_notes: string;
  evidence_basis: string;
  references: string[];
}

export interface FeedstockCatalogResponse {
  feedstocks: FeedstockProfile[];
  count: number;
}

export interface FeedstockCandidate {
  key: string;
  display_name: string;
  category: string;
  risk_tier: string;
  source_kind: string;
  source_ref: string;
  license_note: string;
  ingestion_mode: string;
  human_review_required: boolean;
  review_status: ReferenceReviewStatus;
  candidate_scope: string;
  suitability_notes: string;
  references: string[];
  aliases: string[];
}

export interface FeedstockCandidateCatalogResponse {
  candidates: FeedstockCandidate[];
  count: number;
  validated_feedstock_keys: string[];
  candidate_keys: string[];
}

export interface FeedstockDatasetCandidate {
  candidate_uid: string;
  candidate_type: "feedstock_dataset_candidate";
  source_id: string;
  source_name: string;
  source_owner: string | null;
  source_kind: string;
  source_ref: string;
  license_note: string | null;
  ingestion_mode: string;
  geography: string | null;
  units: string | null;
  source_version_required: boolean;
  checked_at_required: boolean;
  mapping_confidence: "unmapped";
  waste_proxy_warning: string;
  review_status: "pending_review";
  human_review_required: boolean;
  numeric_values_included: boolean;
  runtime_activated: boolean;
  validated_default_write_enabled: boolean;
  next_action: string | null;
}

export interface FeedstockDatasetCandidateListResponse {
  items: FeedstockDatasetCandidate[];
  count: number;
  guardrails: string[];
}

export interface LiteratureExtractionCandidate {
  candidate_uid: string;
  candidate_id: string;
  candidate_type: "literature_extraction_candidate";
  source_id: string;
  doi: string | null;
  source_ref: string;
  title: string;
  species: string;
  feedstock: string;
  treatment: string;
  metric_key: string;
  metric_label: string;
  raw_value: string;
  unit: string;
  condition_context: string;
  experiment_context: string;
  table_or_section_ref: string;
  extraction_note: string;
  license_note: string;
  source_kind: string;
  review_status: "pending_review";
  human_review_required: boolean;
  numeric_values_included: boolean;
  release_evidence_allowed: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  promotion_enabled: boolean;
  guardrails: string[];
}

export interface LiteratureExtractionCandidateListResponse {
  schema_version: "literature_extraction_candidate_list_v1";
  items: LiteratureExtractionCandidate[];
  count: number;
  metric_counts: Record<string, number>;
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export interface LiteratureExtractionCandidateReviewPacketResponse {
  schema_version: "literature_extraction_candidate_review_packet_v1";
  tenant_id: number;
  candidate: LiteratureExtractionCandidate;
  candidate_payload: Record<string, unknown>;
  source_trace: Record<string, unknown>;
  raw_value: string;
  unit: string;
  conditions: Record<string, string>;
  license_note: string;
  review_status: "pending_review";
  human_review_required: boolean;
  numeric_values_included: boolean;
  release_evidence_allowed: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  promotion_enabled: boolean;
  final_action_execution: boolean;
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export interface LiteratureExtractionCandidateReviewPacketExportResponse {
  schema_version: "literature_extraction_candidate_review_packet_export_v1";
  tenant_id: number;
  export_format: "json";
  export_filename: string;
  content_hash: string;
  export_manifest: Record<string, unknown>;
  review_packet: LiteratureExtractionCandidateReviewPacketResponse;
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export interface LiteratureExtractionCandidateReviewPacketBulkExportResponse {
  schema_version: "literature_extraction_candidate_review_packet_bulk_export_v1";
  tenant_id: number;
  export_format: "json";
  export_filename: string;
  content_hash: string;
  export_manifest: Record<string, unknown>;
  packet_exports: LiteratureExtractionCandidateReviewPacketExportResponse[];
  count: number;
  metric_counts: Record<string, number>;
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export type LiteratureExtractionReviewIntent =
  | "needs_review"
  | "approve_candidate_use_intent"
  | "reject_candidate_intent"
  | "needs_license_clearance";

export interface LiteratureExtractionReviewDraftCreateRequest {
  review_intent: LiteratureExtractionReviewIntent;
  reviewer_notes?: string;
  idempotency_key: string;
}

export interface LiteratureExtractionReviewDraftResponse {
  schema_version: "literature_extraction_review_draft_v1";
  review_draft_id: string;
  tenant_id: number;
  candidate_id: string;
  source_id: string;
  reviewer_user_id: number;
  review_intent: LiteratureExtractionReviewIntent;
  reviewer_notes: string;
  status: "draft_intent_recorded";
  source_review_packet_export_id: string;
  source_review_packet_hash: string;
  candidate_snapshot: Record<string, unknown>;
  export_manifest: Record<string, unknown>;
  release_evidence_allowed: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  promotion_enabled: boolean;
  final_action_execution: boolean;
  side_effects: Record<string, boolean>;
  guardrails: string[];
  idempotency_key: string;
  created_at: string;
  updated_at: string;
}

export interface LiteratureExtractionReviewDraftListResponse {
  schema_version: "literature_extraction_review_draft_list_v1";
  tenant_id: number;
  count: number;
  drafts: LiteratureExtractionReviewDraftResponse[];
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export interface LiteratureExtractionReviewDraftRevisionRead {
  review_draft_id: string;
  revision_index: number;
  revision_hash: string;
  candidate_snapshot_hash: string;
  export_manifest_hash: string;
  source_review_packet_hash: string;
  review_intent: LiteratureExtractionReviewIntent;
  changed_fields: string[];
  side_effects: Record<string, boolean>;
  created_at: string;
}

export interface LiteratureExtractionReviewDraftComparisonResponse {
  schema_version: "literature_extraction_review_draft_comparison_v1";
  tenant_id: number;
  candidate_id: string;
  current_review_draft_id: string;
  previous_review_draft_id: string | null;
  current_revision_hash: string;
  current_candidate_snapshot_hash: string;
  current_export_manifest_hash: string;
  source_review_packet_hash: string;
  current_response_packet_hash: string | null;
  changed_field_filter: string | null;
  comparison_manifest: Record<string, unknown>;
  report_manifest: Record<string, unknown>;
  report_payload: Record<string, unknown>;
  comparison_summary: Record<string, boolean>;
  changed_fields: string[];
  audit_trail: LiteratureExtractionReviewDraftRevisionRead[];
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export interface LiteratureExtractionEvidenceChainReadinessResponse {
  schema_version: "literature_extraction_evidence_chain_readiness_v1";
  tenant_id: number;
  chain_complete: boolean;
  candidate_count: number;
  packet_export_ready: boolean;
  bulk_export_ready: boolean;
  review_draft_count: number;
  comparison_ready: boolean;
  report_ready: boolean;
  auto_use_allowed: boolean;
  release_evidence_allowed: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  promotion_enabled: boolean;
  final_action_execution: boolean;
  side_effects: Record<string, boolean>;
  guardrails: string[];
  blocking_reason: string | null;
  readiness_notes: string[];
}

export type LiteratureValuePromotionRequestStatus =
  | "not_requested"
  | "requested"
  | "approved"
  | "approved_for_promotion"
  | "rejected";

export interface LiteratureValuePromotionReadinessResponse {
  schema_version: "literature_value_promotion_readiness_v1";
  tenant_id: number;
  candidate_id: string;
  chain_complete: boolean;
  promotion_ready: boolean;
  review_draft_id: string | null;
  source_review_packet_hash: string | null;
  comparison_hash: string | null;
  raw_value: string | null;
  unit: string | null;
  conditions: Record<string, string>;
  request_status: LiteratureValuePromotionRequestStatus;
  existing_promotion_request_id: string | null;
  target_use_options: string[];
  auto_use_allowed: boolean;
  release_evidence_allowed: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  promotion_enabled: boolean;
  final_action_execution: boolean;
  side_effects: Record<string, boolean>;
  guardrails: string[];
  blocking_reason: string | null;
}

export interface LiteratureValuePromotionRequestCreateRequest {
  target_use: string;
  target_scope: Record<string, unknown>;
  idempotency_key: string;
}

export interface LiteratureValuePromotionRequestResponse {
  schema_version: "literature_value_promotion_request_v1";
  promotion_request_id: string;
  tenant_id: number;
  candidate_id: string;
  source_review_packet_hash: string;
  review_draft_id: string;
  comparison_hash: string;
  raw_value: string;
  unit: string;
  conditions: Record<string, string>;
  target_use: string;
  target_scope: Record<string, unknown>;
  request_status: Exclude<LiteratureValuePromotionRequestStatus, "not_requested">;
  requested_by_user_id: number;
  idempotency_key: string;
  auto_use_allowed: boolean;
  release_evidence_allowed: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  promotion_enabled: boolean;
  final_action_execution: boolean;
  side_effects: Record<string, boolean>;
  guardrails: string[];
  created_at: string;
  updated_at: string;
}

export interface LiteratureValuePromotionApprovalCreateRequest {
  approval_action: "approve" | "reject";
  approver_notes: string;
  idempotency_key: string;
}

export interface LiteratureValuePromotionRejectRequest {
  rejector_notes: string;
  idempotency_key: string;
}

export interface LiteratureValuePromotionApprovalResponse {
  schema_version: "literature_value_promotion_approval_v1";
  approval_id: string;
  tenant_id: number;
  promotion_request_id: string;
  candidate_id: string;
  approval_action: "approve" | "reject";
  request_status_before: Exclude<LiteratureValuePromotionRequestStatus, "not_requested">;
  request_status_after: Exclude<LiteratureValuePromotionRequestStatus, "not_requested">;
  approved_by_user_id: number;
  approved_by_user_roles: string[];
  approver_notes: string;
  idempotency_key: string;
  source_review_packet_hash: string;
  review_draft_id: string;
  comparison_hash: string;
  target_use: string;
  target_scope: Record<string, unknown>;
  approval_audit_only: boolean;
  overlay_write_enabled: boolean;
  release_evidence_allowed: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  promotion_enabled: boolean;
  final_action_execution: boolean;
  side_effects: Record<string, boolean>;
  guardrails: string[];
  created_at: string;
  updated_at: string;
}

export interface LiteratureValueOverlayCreateRequest {
  overlay_notes: string;
  idempotency_key: string;
}

export interface LiteratureValueOverlayResponse {
  schema_version: "literature_value_overlay_v1";
  overlay_id: string;
  tenant_id: number;
  promotion_request_id: string;
  approval_id: string;
  candidate_id: string;
  overlay_status: "inactive" | "promoted_inactive" | "rolled_back";
  overlay_active: boolean;
  source_review_packet_hash: string;
  review_draft_id: string;
  comparison_hash: string;
  raw_value: string;
  normalized_value: string;
  unit: string;
  source_ref: string;
  approval_hash: string;
  overlay_hash: string;
  conditions: Record<string, string>;
  target_use: string;
  target_scope: Record<string, unknown>;
  validity_scope: Record<string, unknown>;
  rollback_pointer: Record<string, unknown>;
  created_by_user_id: number;
  overlay_notes: string;
  idempotency_key: string;
  release_evidence_allowed: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  final_action_execution: boolean;
  rollback_required_before_use_change: boolean;
  side_effects: Record<string, boolean>;
  guardrails: string[];
  created_at: string;
  updated_at: string;
}

export interface LiteratureValueRuntimeActivationPreviewResponse {
  schema_version: "literature_value_runtime_activation_preview_v1";
  tenant_id: number;
  overlay_id: string;
  candidate_id: string;
  overlay_status: "inactive" | "rolled_back";
  approved_overlay: boolean;
  activation_scope_options: string[];
  can_activate_scoped_runtime: boolean;
  blocking_reason: string | null;
  global_activation_allowed: boolean;
  release_evidence_allowed: boolean;
  validated_default_write_enabled: boolean;
  final_action_execution: boolean;
  guardrails: string[];
}

export interface LiteratureValueRuntimeActivationCreateRequest {
  activation_scope: Record<string, unknown>;
  operator_attestation: string;
  idempotency_key: string;
}

export interface LiteratureValueRuntimeActivationDeactivateRequest {
  deactivation_reason: string;
  operator_attestation: string;
  idempotency_key: string;
}

export interface LiteratureValueRuntimeActivationResponse {
  schema_version: "literature_value_runtime_activation_v1";
  activation_id: string;
  tenant_id: number;
  overlay_id: string;
  promotion_request_id: string;
  approval_id: string;
  candidate_id: string;
  activation_status: "active" | "deactivated";
  activation_scope: Record<string, unknown>;
  scope_key: string;
  activated_by_user_id: number;
  operator_attestation: string;
  deactivated_by_user_id: number | null;
  deactivation_reason: string | null;
  deactivated_at: string | null;
  idempotency_key: string;
  runtime_display: string;
  scoped_runtime_activation_enabled: boolean;
  global_activation_allowed: boolean;
  release_evidence_allowed: boolean;
  validated_default_write_enabled: boolean;
  final_action_execution: boolean;
  side_effects: Record<string, boolean>;
  guardrails: string[];
  created_at: string;
  updated_at: string;
}

export interface LiteratureValueReleaseEvidenceLinkCreateRequest {
  activation_id: string;
  link_notes: string;
  idempotency_key: string;
}

export interface LiteratureValueReleaseEvidenceLinkResponse {
  schema_version: "literature_value_release_evidence_link_v1";
  link_id: string;
  tenant_id: number;
  release_decision_id: number;
  activation_id: string;
  overlay_id: string;
  promotion_request_id: string;
  approval_id: string;
  candidate_id: string;
  link_status: "active" | "superseded" | "rolled_back";
  rollback_status: "none" | "superseded" | "rolled_back";
  activation_scope: Record<string, unknown>;
  scope_key: string;
  source_review_packet_hash: string;
  comparison_hash: string;
  release_decision_before: "review_required";
  release_decision_after: "review_required";
  linked_by_user_id: number;
  link_notes: string;
  idempotency_key: string;
  release_decision_unchanged: boolean;
  human_review_required: boolean;
  final_action_execution: boolean;
  side_effects: Record<string, boolean>;
  guardrails: string[];
  created_at: string;
  updated_at: string;
}

export interface LiteratureValueRollbackCreateRequest {
  rollback_reason: string;
  operator_attestation: string;
  idempotency_key: string;
}

export interface LiteratureValueRollbackResponse {
  schema_version: "literature_value_rollback_v1";
  rollback_id: string;
  tenant_id: number;
  activation_id: string;
  overlay_id: string;
  promotion_request_id: string;
  approval_id: string;
  candidate_id: string;
  rollback_status: "completed";
  activation_status_before: "active" | "deactivated";
  activation_status_after: "deactivated";
  overlay_status_before: "inactive" | "rolled_back";
  overlay_status_after: "rolled_back";
  affected_release_evidence_link_ids: string[];
  release_evidence_link_status_updates: Record<string, unknown>[];
  release_decision_states: Record<string, unknown>[];
  rolled_back_by_user_id: number;
  rollback_reason: string;
  operator_attestation: string;
  idempotency_key: string;
  release_decision_unchanged: boolean;
  human_review_required: boolean;
  final_action_execution: boolean;
  side_effects: Record<string, boolean>;
  guardrails: string[];
  created_at: string;
  updated_at: string;
}

export interface LiteratureValuePromotionLifecycleResponse {
  schema_version: "literature_value_promotion_lifecycle_v1";
  tenant_id: number;
  candidate_id: string;
  promotion_request_count: number;
  approval_count: number;
  overlay_count: number;
  runtime_activation_count: number;
  release_evidence_link_count: number;
  rollback_count: number;
  promotion_request_ids: string[];
  approval_ids: string[];
  overlay_ids: string[];
  activation_ids: string[];
  release_evidence_link_ids: string[];
  rollback_ids: string[];
  request_statuses: string[];
  approval_actions: string[];
  overlay_statuses: string[];
  activation_statuses: string[];
  release_evidence_link_statuses: string[];
  rollback_statuses: string[];
  release_decision_states: Record<string, unknown>[];
  lifecycle_read_only: boolean;
  release_decision_unchanged: boolean;
  human_review_required: boolean;
  final_action_execution: boolean;
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export interface LiteratureValuePromotionAuditExportResponse {
  schema_version: "literature_value_promotion_audit_export_v1";
  tenant_id: number;
  candidate_id: string;
  export_format: "json";
  export_policy: "response_only_no_file_write";
  content_hash: string;
  export_manifest: Record<string, unknown>;
  request: Record<string, unknown> | null;
  approvals: Record<string, unknown>[];
  overlay: Record<string, unknown> | null;
  runtime_activation: Record<string, unknown> | null;
  release_evidence_link: Record<string, unknown> | null;
  rollback: Record<string, unknown> | null;
  db_pollution_proof: Record<string, unknown>;
  final_action_non_execution_proof: Record<string, unknown>;
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export type ExternalSourceReviewStatus =
  | "pending_review"
  | "extracted_metadata"
  | "needs_license_clearance"
  | "rejected"
  | "approved_for_candidate_use";

export type ExternalSourceReviewAction =
  | "approve_metadata"
  | "request_license_clearance"
  | "reject"
  | "approve_for_candidate_use";

export type ExternalSourceReviewActionState = "pending_review" | ExternalSourceReviewAction;

export interface ExternalSourceRecord {
  source_id: string;
  source_name: string;
  source_owner: string | null;
  source_category: string | null;
  license_note: string | null;
  bos_module: string | null;
  evidence_source_kind: string;
  ingestion_mode: string;
  auto_ingestion_note: string | null;
  human_review_note: string | null;
  next_action: string | null;
  raw_payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ExternalSourceCatalogResponse {
  items: ExternalSourceRecord[];
  count: number;
  guardrails: string[];
}

export interface ExternalSourceProcurementSummary {
  schema_version: "external_source_procurement_summary_v1";
  source_count: number;
  source_kind_counts: Record<string, number>;
  ingestion_mode_counts: Record<string, number>;
  bos_module_counts: Record<string, number>;
  review_required_count: number;
  metadata_only_count: number;
  manual_review_first_count: number;
  other_ingestion_mode_count: number;
  commercial_or_restricted_count: number;
  guardrails: string[];
}

export interface ExternalSourceSchemaReadinessTable {
  table_name: string;
  present: boolean;
  row_count: number | null;
}

export interface ExternalKnowledgeCoverageDomain {
  domain_key: string;
  label: string;
  coverage_basis: "source_metadata";
  expected_source_count: number;
  covered_source_count: number;
  coverage_percent: number;
  status: "covered" | "partial" | "missing";
  review_gated: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  numeric_values_included: boolean;
}

export type BusinessKnowledgeCoverageStatus =
  | "validated_read_model"
  | "candidate_read_model"
  | "source_metadata_only"
  | "partial"
  | "candidate_needed"
  | "missing";

export interface BusinessKnowledgeReviewWorkflow {
  review_packet_id: string;
  review_state: "pending_review" | "approved_for_candidate_use" | "rejected" | "needs_license_clearance";
  source_packet_persistence: "read_model_only" | "persisted_review_packet_required";
  reviewer_notes_required: boolean;
  reviewer_notes: string;
  allowed_review_actions: string[];
  approval_enabled: boolean;
  rejection_enabled: boolean;
  release_evidence_allowed: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  numeric_values_allowed: boolean;
  guardrails: string[];
}

export interface BusinessKnowledgeCoverageItem {
  item_key: string;
  label: string;
  status: BusinessKnowledgeCoverageStatus;
  coverage_basis: "validated_read_model" | "candidate_read_model" | "source_metadata" | "partial" | "missing";
  evidence_refs: string[];
  notes: string;
  review_gated: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  numeric_values_included: boolean;
  review_workflow?: BusinessKnowledgeReviewWorkflow | null;
}

export interface BusinessKnowledgeCoverageGroup {
  group_key: string;
  label: string;
  expected_item_count: number;
  covered_item_count: number;
  coverage_percent: number;
  status: "covered" | "partial" | "missing";
  items: BusinessKnowledgeCoverageItem[];
  review_gated: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  numeric_values_included: boolean;
}

export interface BusinessKnowledgeReviewPacketResponse {
  schema_version: "business_knowledge_review_packet_v1";
  tenant_id: number;
  group_key: string;
  item: BusinessKnowledgeCoverageItem;
  review_workflow: BusinessKnowledgeReviewWorkflow;
  candidate_payload: Record<string, unknown>;
  source_trace: Record<string, unknown>;
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export interface BusinessKnowledgeReviewPacketExportResponse {
  schema_version: "business_knowledge_review_packet_export_v1";
  tenant_id: number;
  export_format: "json";
  export_filename: string;
  content_hash: string;
  export_manifest: Record<string, unknown>;
  review_packet: BusinessKnowledgeReviewPacketResponse;
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export interface ExternalSourceSchemaReadinessResponse {
  schema_version: "external_source_schema_readiness_v1";
  status: "ready" | "blocked";
  schema_ready: boolean;
  source_catalog_ready: boolean;
  knowledge_coverage_ready?: boolean;
  knowledge_coverage_percent?: number;
  source_metadata_coverage_percent?: number;
  knowledge_coverage_domains?: ExternalKnowledgeCoverageDomain[];
  business_knowledge_coverage_percent?: number;
  business_knowledge_coverage_groups?: BusinessKnowledgeCoverageGroup[];
  feedstock_dataset_candidate_count: number;
  literature_extraction_candidate_count?: number;
  phase4a_domain_metadata_ready?: boolean;
  phase4a_domain_candidate_counts?: Record<string, number>;
  phase4a_domain_expected_counts?: Record<string, number>;
  phase4a_domain_missing_counts?: Record<string, number>;
  reviewed_metadata_lane_ready: boolean;
  required_tables: ExternalSourceSchemaReadinessTable[];
  missing_required_tables: string[];
  blockers: string[];
  guardrails: string[];
}

export interface ExternalSourcePhase4AReviewedCandidateFillResponse {
  schema_version: "external_source_phase4a_reviewed_candidate_fill_v1";
  source_count: number;
  reviewed_candidate_count: number;
  created_reviewed_candidate_count: number;
  updated_reviewed_candidate_count: number;
  reviewed_candidate_ids: string[];
  candidate_types: Record<string, number>;
  candidate_domains: Record<string, number>;
  runtime_activated_count: number;
  validated_default_write_enabled_count: number;
  numeric_value_candidate_count: number;
  guardrails: string[];
}

export interface ExternalSourceReviewCard {
  tenant_id: number;
  card_id: string;
  shortlist_id: string;
  source_id: string;
  doi: string;
  source_url: string;
  title: string;
  review_status: ExternalSourceReviewStatus;
  review_action: ExternalSourceReviewActionState;
  reviewer: string;
  reviewer_user_id: number | null;
  reviewed_at: string | null;
  license_status: string;
  evidence_source_kind: string;
  ingestion_mode: string;
  human_review_required: boolean;
  extracted_numeric_values_allowed: boolean;
  boundary_condition_required: boolean;
  allowed_use: string;
  blocked_use: string;
  next_action: string;
  boundary_metadata: Record<string, unknown>;
  raw_payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  promotion_enabled: boolean;
  runtime_activated: boolean;
  validated_default_write_enabled: boolean;
}

export interface ExternalSourceReviewCardListResponse {
  items: ExternalSourceReviewCard[];
  count: number;
}

export interface ExternalSourceReviewCardResolveRequest {
  review_action: ExternalSourceReviewAction;
  review_status?: ExternalSourceReviewStatus | null;
  reviewer: string;
  reviewed_at: string;
  license_status: string;
  boundary_condition: string;
  allowed_use: string;
  blocked_use: string;
  candidate_type?: string;
  candidate_key?: string | null;
  candidate_payload?: Record<string, unknown>;
  extracted_metadata?: Record<string, unknown>;
  extracted_numeric_values?: Record<string, unknown>;
  numeric_values_included?: boolean;
  human_review_required?: boolean;
  promotion_enabled?: boolean;
  runtime_activated?: boolean;
  validated_default_write_enabled?: boolean;
  next_action?: string;
}

export interface ExternalSourceExtractionRecord {
  tenant_id: number;
  extraction_id: string;
  card_id: string;
  source_id: string;
  extraction_status: string;
  extracted_metadata: Record<string, unknown>;
  extracted_numeric_values: Record<string, unknown>;
  numeric_values_included: boolean;
  boundary_metadata: Record<string, unknown>;
  human_review_required: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExternalSourceExtractionListResponse {
  items: ExternalSourceExtractionRecord[];
  count: number;
  guardrails: string[];
}

export interface BsfReviewedMetadataCandidatePayload {
  payload_version: "bsf-reviewed-metadata-v1";
  candidate_family: "bsf_reviewed_metadata";
  card_id: string;
  shortlist_id: string;
  source_catalog_id: string;
  doi: string;
  source_url: string;
  title: string;
  article_type: string;
  target_boundary_fields: string;
  boundary_condition: string;
  allowed_use: string;
  blocked_use: string;
  evidence_source_kind: string;
  ingestion_mode: string;
  license_status: string;
  source_kind: string;
  source_ref: string;
  numeric_values_included: boolean;
  extracted_numeric_values: Record<string, unknown>;
  promotion_enabled: boolean;
  runtime_activated: boolean;
  validated_default_write_enabled: boolean;
  runtime_activation_required_before_use: boolean;
  reviewer_annotations: Record<string, unknown>;
}

export interface ReviewedExternalCandidate {
  tenant_id: number;
  candidate_id: string;
  candidate_type: string;
  candidate_type_group?: string;
  candidate_domain?: string;
  candidate_type_counts?: Record<string, number>;
  candidate_domain_counts?: Record<string, number>;
  candidate_key: string;
  card_id: string;
  source_id: string;
  source_kind: string;
  source_ref: string;
  license_status: string;
  license_note: string | null;
  ingestion_mode: string;
  review_status: ExternalSourceReviewStatus;
  reviewer: string;
  reviewed_at: string;
  boundary_condition: string;
  allowed_use: string;
  blocked_use: string;
  candidate_payload: BsfReviewedMetadataCandidatePayload | Record<string, unknown>;
  human_review_required: boolean;
  promotion_enabled: boolean;
  runtime_activated: boolean;
  validated_default_write_enabled: boolean;
  activation_relation_id: string | null;
  audit_payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ExternalSourceReviewCardResolveResponse {
  review_card: ExternalSourceReviewCard;
  reviewed_candidate: ReviewedExternalCandidate | null;
  created_reviewed_candidate: boolean;
  guardrails: string[];
}

export interface ReviewedExternalCandidateActivationPreviewResponse {
  schema_version: "reviewed_external_candidate_activation_preview_v1";
  tenant_id: number;
  candidate: ReviewedExternalCandidate;
  activation_scope: Record<string, unknown>;
  active_overlay_state: Record<string, unknown>;
  activation_audit_contract: Record<string, unknown>;
  can_execute_activation: boolean;
  runtime_overlay_preview_only: boolean;
  rollback_required: boolean;
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export interface ReviewedExternalCandidateRuntimeReadinessResponse {
  schema_version: "reviewed_external_candidate_runtime_readiness_v1";
  tenant_id: number;
  candidate: ReviewedExternalCandidate;
  activation_scope: Record<string, unknown>;
  active_overlay_state: Record<string, unknown>;
  active_candidate_payload: Record<string, unknown> | null;
  can_read_runtime_payload: boolean;
  runtime_read_path_enabled: boolean;
  rollback_required: boolean;
  rollback_contract: Record<string, unknown>;
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export interface ReviewedExternalCandidateRollbackPreviewResponse {
  schema_version: "reviewed_external_candidate_rollback_preview_v1";
  tenant_id: number;
  candidate: ReviewedExternalCandidate;
  activation_scope: Record<string, unknown>;
  active_overlay_state: Record<string, unknown>;
  rollback_contract: Record<string, unknown>;
  rollback_audit_packet: Record<string, unknown>;
  rollback_target_available: boolean;
  can_execute_rollback: boolean;
  rollback_preview_only: boolean;
  rollback_required: boolean;
  rollback_blockers: string[];
  side_effects: Record<string, boolean>;
  guardrails: string[];
}

export interface ReviewedExternalCandidateListResponse {
  items: ReviewedExternalCandidate[];
  count: number;
  total_count?: number;
  offset?: number;
  limit?: number | null;
  has_more?: boolean;
  candidate_types?: Record<string, number>;
  candidate_domains?: Record<string, number>;
  guardrails: string[];
}

export interface ReviewedExternalCandidateLaneSummary {
  schema_version: "reviewed_external_candidate_lane_summary_v1";
  tenant_id: number;
  reviewed_candidate_count: number;
  reviewed_metadata_candidate_count: number;
  pending_runtime_activation_count: number;
  runtime_activated_count: number;
  validated_default_write_enabled_count: number;
  numeric_value_candidate_count: number;
  release_evidence_blocked_count: number;
  statuses: Record<string, number>;
  candidate_types: Record<string, number>;
  candidate_domains?: Record<string, number>;
  latest_reviewed_at: string | null;
  guardrails: string[];
}

export interface ReviewedExternalCandidateKnowledgeBaseResponse {
  schema_version: "reviewed_external_candidate_knowledge_base_v1";
  tenant_id: number;
  status: "ready_for_review" | "blocked";
  schema_ready: boolean;
  source_catalog_ready: boolean;
  reviewed_metadata_lane_ready: boolean;
  knowledge_coverage_ready: boolean;
  knowledge_coverage_percent: number;
  source_metadata_coverage_percent: number;
  knowledge_coverage_domains: ExternalKnowledgeCoverageDomain[];
  business_knowledge_coverage_percent: number;
  business_knowledge_coverage_groups: BusinessKnowledgeCoverageGroup[];
  supported_candidate_types: string[];
  supported_candidate_domains: string[];
  phase4a_domain_metadata_ready: boolean;
  phase4a_domain_candidate_counts: Record<string, number>;
  phase4a_domain_expected_counts: Record<string, number>;
  phase4a_domain_missing_counts: Record<string, number>;
  reviewed_candidate_count: number;
  reviewed_metadata_candidate_count: number;
  pending_runtime_activation_count: number;
  runtime_activated_count: number;
  validated_default_write_enabled_count: number;
  numeric_value_candidate_count: number;
  candidate_types: Record<string, number>;
  candidate_domains: Record<string, number>;
  blockers: string[];
  guardrails: string[];
}

export interface ManuscriptCampaignReference {
  key: string;
  title: string;
  species_chain: string[];
  feedstocks: string[];
  campaign_type: string;
  evidence_level: string;
  summary: string;
  key_parameters: Record<string, unknown>;
  observed_outputs: Record<string, unknown>;
  source_anchor: string;
  references: string[];
}

export interface ManuscriptCampaignCatalogResponse {
  campaigns: ManuscriptCampaignReference[];
  count: number;
}

export interface ReferenceParserMetadata {
  parser_name: string;
  parser_version: string | null;
  execution_mode: string;
  raw_markdown_path: string | null;
  raw_json_path: string | null;
  source_file_path: string | null;
  warnings: string[];
  fallback_reason: string | null;
  extracted_field_count: number;
  parsed_at: string;
}

export type ReferenceIngestionStatus = "staged" | "promoted" | "failed";

export interface ReferenceIngestionStagedItem {
  id: string;
  tenant_id: number;
  source_title: string;
  source_anchor: string;
  source_type: string;
  source_owner: string | null;
  license_note: string | null;
  region: string | null;
  units: Record<string, string>;
  ingestion_mode: string;
  human_review_required: boolean;
  species_chain: string[];
  feedstocks: string[];
  evidence_level: string;
  campaign_type: string;
  summary: string;
  key_parameters: Record<string, unknown>;
  observed_outputs: Record<string, unknown>;
  references: string[];
  parser_metadata: ReferenceParserMetadata;
  status: ReferenceIngestionStatus;
  promoted_campaign_key: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReferenceIngestionListResponse {
  items: ReferenceIngestionStagedItem[];
  count: number;
}

export interface ReferenceIngestionHealthResponse {
  parser_name: string;
  parser_command: string;
  parser_extra_args: string;
  parser_available: boolean;
  promotion_enabled: boolean;
  storage_root: string;
  staged_count: number;
  promoted_count: number;
  rollback_mode: string;
}

export interface ReferenceIngestionParseRequest {
  file: File;
  source_title?: string;
  source_type?: string;
  source_owner?: string;
  license_note?: string;
  region?: string;
  units?: Record<string, string>;
  ingestion_mode?: string;
  human_review_required?: boolean;
}

export interface ReferenceIngestionPromoteRequest {
  target_type?: "campaign";
  notes?: string;
}

export interface ReferenceIngestionCampaignCandidate extends ManuscriptCampaignReference {
  staging_meta: Record<string, unknown>;
}

export interface ReferenceIngestionPromoteResponse {
  staged_item: ReferenceIngestionStagedItem;
  campaign: ReferenceIngestionCampaignCandidate;
}

export interface NativeModelSource {
  label: string;
  url: string;
  provider: string;
}

export interface NativeModelCapability {
  key: string;
  name: string;
  family: string;
  frontier_window: string;
  modality: string;
  maturity: string;
  primary_fit: string;
  dialectical_role: string;
  native_outputs: string[];
  bos_touchpoints: string[];
  operational_triggers: string[];
  recommended_deployment: string[];
  sources: NativeModelSource[];
}

export interface NativeModelComposition {
  key: string;
  title: string;
  objective: string;
  model_keys: string[];
  why_it_matters: string;
  native_outputs: string[];
  bos_agents: string[];
}

export interface NativeModelRecommendation {
  key: string;
  title: string;
  fit: string;
  rationale: string;
  model_keys: string[];
  native_outputs: string[];
}

export interface NativeModelRolloutStep {
  phase: string;
  title: string;
  objective: string;
}

export interface NativeModelCatalog {
  version: string;
  catalog_version: string;
  verified_on: string;
  models: NativeModelCapability[];
  compositions: NativeModelComposition[];
  recommendations: NativeModelRecommendation[];
  rollout: NativeModelRolloutStep[];
}

export interface NativeModelRuntimeArtifact {
  expected_location: string;
  configured_location: string | null;
  exists: boolean;
  source_reference: string | null;
  artifact_kind?: string | null;
}

export interface NativeModelRuntimeDependency {
  package: string;
  installed: boolean;
}

export interface NativeModelRuntimeEntry {
  key: string;
  ready: boolean;
  runtime_state: string;
  modality: string;
  adapter_status: string;
  artifact: NativeModelRuntimeArtifact;
  dependencies: NativeModelRuntimeDependency[];
  expected_inputs: string[];
  next_steps: string[];
}

export interface NativeModelRuntimeStatus {
  version: string;
  enabled: boolean;
  cache_dir: string;
  summary: Record<string, unknown>;
  runtimes: NativeModelRuntimeEntry[];
}

export interface NativeModelInferenceRequest {
  model_key: string;
  batch_id?: number;
  dry_run?: boolean;
  payload?: Record<string, unknown>;
}

export interface NativeModelInferenceResponse {
  version: string;
  model_key: string;
  batch_id: number | null;
  ready: boolean;
  runtime_state: string;
  execution_mode: string;
  payload_echo: Record<string, unknown>;
  result: Record<string, unknown>;
  warnings: string[];
  next_steps: string[];
}

export interface NativeModelDownloadPlan {
  version: string;
  model_key: string;
  supported: boolean;
  source_kind: string;
  source_reference: string | null;
  target_path: string;
  notes: string[];
}

export interface NativeModelDownloadResponse {
  version: string;
  model_key: string;
  downloaded: boolean;
  runtime_state: string;
  target_path: string;
  source_reference: string | null;
  detail: string;
  extracted_path: string | null;
}

export interface NativeModelRunArtifact {
  model_key: string;
  execution_mode: string;
  recorded_at: string;
  artifact_path: string;
  payload_echo: Record<string, unknown>;
  result: Record<string, unknown>;
  warnings: string[];
}

export interface NativeRunSummary {
  modelKey: string;
  modality: string;
  evidenceTier: string;
  evidenceLabel: string;
  evidenceSummary?: string | null;
  executionMode: string;
  recordedAt: string;
  artifactPath: string;
  metricName: string | null;
  predictionHorizon: number | null;
  forecastPreview: string[];
  detectionCount?: number | null;
  topLabel?: string | null;
  topCandidates?: string[];
  bboxSummary?: string | null;
  isLive: boolean;
}

export interface TimeseriesRiskConfidenceBand {
  lower: number;
  upper: number;
}

export interface TimeseriesRiskResponse {
  version: string;
  batch_id: number;
  batch_label: string;
  future_risk_score: number;
  freshness_drift_score: number;
  release_warning_score: number;
  driver_features: string[];
  forecast_window: string;
  model_name: string;
  confidence_band: TimeseriesRiskConfidenceBand;
  execution_mode: string;
  fallback_used: boolean;
  forecast_preview: number[];
  heuristic_baseline: Record<string, unknown>;
  explanation: string;
}

export interface RecentTimeseriesRiskResponse {
  version: string;
  items: TimeseriesRiskResponse[];
  count: number;
}

export interface SupervisorObservationRequest {
  uv254: number;
  od280: number;
  do: number;
  ph: number;
  elapsed_hours: number;
  previous_c_signal_hat?: number;
  previous_elapsed_hours?: number;
  previous_dc_dt_hat?: number;
  previous_negative_slope_streak?: number;
  confidence_threshold?: number;
  negative_slope_persistence?: number;
  observability_required?: boolean;
}

export interface SupervisorStateResponse {
  id: number;
  signal_batch_id: number;
  c_signal_hat: number;
  dc_dt_hat: number | null;
  confidence: number;
  observed_at: string;
  missing_channels: string[];
  channels_used: string[];
  information_loss: number | null;
  observability_score: number | null;
  negative_slope_streak: number | null;
  trigger_reason: string | null;
  expected_handover: string | null;
  mechanistic_context: MechanisticContext | null;
}

export interface HandoverRecommendationResponse {
  signal_batch_id: number;
  recommended_handover: boolean;
  trigger_reason: string;
  expected_freshness_window_hours: number | null;
  c_signal_hat: number | null;
  dc_dt_hat: number | null;
  confidence: number | null;
  expected_handover: string | null;
  confidence_threshold: number;
  negative_slope_persistence: number | null;
  observability_required: boolean;
  missing_channels: string[];
  channels_used: string[];
  information_loss: number | null;
  observability_score: number | null;
  mechanistic_context: MechanisticContext | null;
}
