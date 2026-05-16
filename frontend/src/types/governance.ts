export interface BOSV9RCManifestSafetyBoundary {
  release_decision: "review_required";
  model_version: "ready_for_review";
  final_action_draft_count: 0;
  final_action_audit_record_count: 0;
  external_share_record_created: false;
  final_action_execute_call_count: 0;
  validated_default_write_enabled: false;
  runtime_activation_enabled: false;
  hardware_execution_enabled: false;
  final_action_execution_enabled: false;
}

export interface BOSV9RCManifestCheck {
  status: string;
  raw_status?: string;
  name: string;
  summary: string;
}

export interface BOSV9RCManifestScorecardItem {
  dimension: string;
  score: number;
  target: number;
  evidence: string;
}

export interface BOSV9RCManifestResponse {
  generated_at: string;
  release_state: "review_required";
  candidate_evidence_state: "pending" | "review_required" | "ready_for_review";
  preflight_pass_count: number;
  preflight_warn_count: number;
  preflight_fail_count: number;
  review_required_items: string[];
  local_validation_notes: string[];
  recommended_next_action: string | null;
  bos_v9_target_progress_percent: number;
  bos_v9_target_scorecard: BOSV9RCManifestScorecardItem[];
  safety_boundary: BOSV9RCManifestSafetyBoundary;
  release_reference_smoke_passed: boolean;
  checks: BOSV9RCManifestCheck[];
  artifacts: Record<string, string>;
}
