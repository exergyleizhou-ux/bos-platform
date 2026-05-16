export type SimulationScenario =
  | "normal"
  | "moisture_drift"
  | "temperature_spike"
  | "underfeeding";

export type SimulationPolicy =
  | "rule_based"
  | "conservative"
  | "growth_optimized"
  | "risk_minimizing";

export interface SimulationInitialState {
  biomass: number;
  substrate: number;
  temperature: number;
  moisture: number;
  nitrogen: number;
}

export interface LabAssayMeasurements {
  biomass?: number | null;
  substrate?: number | null;
  moisture?: number | null;
  heavy_metal_index?: number | null;
}

export type EvidenceSourceKind =
  | "operator_input"
  | "imported_reference"
  | "manuscript_campaign"
  | "staged_reference"
  | "promoted_campaign"
  | "synthetic"
  | "deterministic_model"
  | "chronos_model"
  | "fallback_default"
  | "assumed"
  | "official_standard"
  | "peer_reviewed_literature"
  | "public_dataset"
  | "industry_reference"
  | "commercial_database"
  | "model_provider_docs"
  | "github_reference";

export interface SimulationEvidenceSource {
  field: string;
  source_kind: EvidenceSourceKind;
  source_ref: string | null;
  confidence: number;
  fallback_used: boolean;
  notes: string | null;
  payload?: Record<string, number> | null;
  measurement_mode?: string | null;
  review_status?: string | null;
  human_review_required?: boolean | null;
  numeric_values_included?: boolean | null;
  release_evidence_allowed?: boolean | null;
  runtime_activation_enabled?: boolean | null;
  validated_default_write_enabled?: boolean | null;
  promotion_enabled?: boolean | null;
}

export interface SimulationScenarioCreate {
  species: string;
  feedstock: string;
  scenario: SimulationScenario;
  initial_state: SimulationInitialState;
  cycles: number;
  seed: number;
  policy: SimulationPolicy;
  lab_assay_measurements?: LabAssayMeasurements | null;
}

export interface SimulationScenarioResponse extends SimulationScenarioCreate {
  simulation_id: string;
  batch_id: string;
  tenant_id: number;
  status: string;
  created_at: string;
  evidence_sources: SimulationEvidenceSource[];
}

export interface SimulationLabCycle {
  cycle: number;
  timestamp: string;
  state_before: Record<string, number>;
  sensor_observation: Record<string, number | string>;
  supervisor_decision: Record<string, unknown>;
  risk_prediction: {
    future_risk_score: number;
    release_warning_score: number;
    forecast_window: string;
    model_name: string;
    driver_features: Record<string, number>;
    source?: string;
    execution_mode?: string;
    confidence_band?: {
      lower: number;
      median: number;
      upper: number;
    };
    lab_governance?: {
      profile_id: string;
      heavy_metal_gate: string;
      product_use_lock: string;
      review_status: string;
    };
    lab_assay_comparison?: {
      source_kind: string;
      source_ref: string;
      review_status: string;
      measurement_mode: string;
      human_review_required?: boolean;
      numeric_values_included?: boolean;
      release_evidence_allowed?: boolean;
      runtime_activation_enabled?: boolean;
      validated_default_write_enabled?: boolean;
      promotion_enabled?: boolean;
      predicted: Record<string, number>;
      measured_anchor: Record<string, number>;
      residuals: Record<string, number>;
      out_of_band: string[];
      calibration_status: string;
    };
  };
  visual_observation: {
    source: string;
    frame_id: string;
    anomaly_labels: string[];
    confidence: number;
    ultralytics_dry_run: boolean;
    hardware_camera_used: boolean;
  } | null;
  evidence_sources: SimulationEvidenceSource[];
  agent_action: {
    policy: SimulationPolicy;
    recommended_action: string;
    intensity: number;
    duration_minutes: number;
    reason_codes: string[];
    confidence: number;
    expected_risk_reduction: number;
  };
  actuator_result: {
    action: string;
    status: string;
    expected_effect: Record<string, string>;
    actual_effect: Record<string, string>;
    hardware_execution: boolean;
  };
  state_after: Record<string, number>;
  audit_event: Record<string, unknown>;
}

export interface SimulationLabSummary {
  simulation_id: string;
  cycle_count: number;
  scenario: SimulationScenario;
  policy: SimulationPolicy;
  starting_risk: number;
  ending_risk: number;
  risk_delta: number;
  action_count: number;
  audit_event_count: number;
  final_state: Record<string, number>;
}

export interface SimulationLabRunResponse {
  scenario: SimulationScenarioResponse;
  summary: SimulationLabSummary;
  cycles: SimulationLabCycle[];
}

export interface SimulationLabRunHistoryItem extends SimulationLabSummary {
  run_id: string;
  tenant_id: number;
  status: string;
  engine_version: string;
  model_version: string | null;
  input_snapshot_id: string | null;
  input_snapshot_hash: string | null;
  replay_of_run_id: string | null;
  evidence_pack_id: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
}

export interface SimulationPolicyCompareRequest {
  policies: SimulationPolicy[];
  baseline_policy: SimulationPolicy;
}

export interface SimulationScenarioImportRequest {
  reference_id: string;
  scenario_name?: string | null;
  policy: SimulationPolicy;
  cycles: number;
  seed: number;
}

export interface SimulationScenarioImportMetadata {
  reference_id: string;
  reference_source: string;
  source_title: string;
  review_status: string;
  human_review_required: boolean;
  numeric_values_included: boolean;
  release_evidence_allowed: boolean;
  runtime_activation_enabled: boolean;
  validated_default_write_enabled: boolean;
  promotion_enabled: boolean;
  extraction_confidence: number;
  field_sources: Record<string, string>;
  fallbacks: string[];
  environmental_drift_assumptions: Record<string, unknown>;
  expected_risk_constraints: Record<string, unknown>;
}

export interface SimulationScenarioImportResponse {
  scenario: SimulationScenarioResponse;
  import_metadata: SimulationScenarioImportMetadata;
}

export interface SimulationPolicyComparisonMetrics {
  risk_delta: number;
  biomass_gain: number;
  substrate_use: number;
  intervention_count: number;
  human_review_count: number;
  audit_completeness: number;
  conversion_rate_estimate: number;
  mortality_risk: number;
  moisture_risk: number;
  nh3_risk: number;
  energy_kwh_estimate: number;
  water_kg_estimate: number;
  co2e_estimate: number;
  labor_hour_estimate: number;
  gross_margin_estimate: number;
  release_readiness: string;
  missing_evidence: string[];
  human_review_required: boolean;
}

export interface SimulationPolicyComparisonRun {
  policy: SimulationPolicy;
  run_id: string;
  summary: SimulationLabSummary;
  metrics: SimulationPolicyComparisonMetrics;
}

export interface SimulationPolicyComparisonResponse {
  simulation_id: string;
  baseline_policy: SimulationPolicy;
  runs: SimulationPolicyComparisonRun[];
  winner: {
    lowest_risk: SimulationPolicy | null;
    highest_biomass_gain: SimulationPolicy | null;
    fewest_interventions: SimulationPolicy | null;
  };
}

export interface SimulationReleaseAppendixAuditHash {
  cycle: number | null;
  event_type: string;
  payload_hash: string;
  recorded_at: string;
}

export interface SimulationReleaseAppendixResponse {
  simulation_id: string;
  generated_at: string;
  scenario: SimulationScenarioResponse;
  selected_run: SimulationLabRunHistoryItem | null;
  comparison_runs: SimulationPolicyComparisonRun[];
  audit_trace_hashes: SimulationReleaseAppendixAuditHash[];
  evidence_pack_id: string | null;
  input_snapshot_id: string | null;
  disclaimer: string;
}

export interface SimulationEvidenceSourcesResponse {
  simulation_id: string;
  scenario_sources: SimulationEvidenceSource[];
  latest_run_sources: SimulationEvidenceSource[];
  cycle_sources: Array<{ cycle: number; evidence_sources: SimulationEvidenceSource[] }>;
}

export interface SimulationReplayResponse {
  source_run_id: string;
  replay_run: SimulationLabRunHistoryItem;
  deterministic_core_match: boolean;
  warnings: string[];
}

export interface SimulationRunDiffResponse {
  run_id: string;
  against_run_id: string;
  deterministic_core_match: boolean;
  differences: Array<Record<string, unknown>>;
}

export interface SimulationLabCycleListResponse {
  simulation_id: string;
  cycles: SimulationLabCycle[];
}

export interface SimulationLabAuditTraceResponse {
  simulation_id: string;
  audit_trace: Array<Record<string, unknown>>;
}

export interface SimulationLabExportResponse {
  simulation_id: string;
  exported_at: string;
  scenario: SimulationScenarioResponse;
  summary: SimulationLabSummary | null;
  cycles: SimulationLabCycle[];
  audit_trace: Array<Record<string, unknown>>;
  evidence_sources: SimulationEvidenceSource[];
  evidence_pack_id: string | null;
  input_snapshot_id: string | null;
  disclaimer: string;
}
