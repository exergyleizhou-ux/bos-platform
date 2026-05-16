export type CodeSessionStatus =
  | "created"
  | "spawning"
  | "trust_required"
  | "ready_for_prompt"
  | "prompt_accepted"
  | "ready"
  | "running"
  | "blocked"
  | "completed"
  | "failed"
  | "cancelled";

export type CodeVerificationStatus =
  | "pending"
  | "running"
  | "passed"
  | "failed"
  | "skipped";

export type CodeActionPolicy =
  | "automation_safe"
  | "human_only"
  | "review_gated";

export interface CodeWorkspaceLease {
  id: number;
  workspace_id: number;
  active_session_id: number | null;
  lease_owner_user_id: number | null;
  lease_status: string;
  lease_expires_at: string | null;
  heartbeat_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CodeWorkspace {
  id: number;
  tenant_id: number;
  repo_root: string;
  worktree_root: string;
  base_branch: string;
  default_branch: string;
  active_branch: string;
  workspace_status: string;
  base_commit: string | null;
  head_commit: string | null;
  dirty_state: boolean;
  created_at: string | null;
  updated_at: string | null;
  lease: CodeWorkspaceLease | null;
}

export interface CodeWorkspaceStatus {
  workspace: CodeWorkspace;
  lease: CodeWorkspaceLease | null;
  can_write: boolean;
  permission_mode: string;
  latest_event_time: string | null;
}

export interface CodeWorkspaceTreeItem {
  path: string;
  name: string;
  node_type: "file" | "directory";
  has_children: boolean;
  size_bytes: number | null;
}

export interface CodeWorkspaceTreeResponse {
  root: string;
  items: CodeWorkspaceTreeItem[];
}

export interface CodeWorkspaceFileResponse {
  path: string;
  content: string;
  encoding: string;
  truncated: boolean;
  size_bytes: number | null;
}

export interface CodeBranchState {
  id: number;
  workspace_id: number;
  branch_name: string;
  base_branch: string;
  head_commit: string | null;
  base_commit: string | null;
  merge_base_commit: string | null;
  is_dirty: boolean;
  is_stale_against_base: boolean;
  ahead_count: number | null;
  behind_count: number | null;
  branch_status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface CodeReadinessResponse {
  session_id: number;
  branch_state: CodeBranchState;
  readiness: string;
  blocking_reasons: string[];
  failure_class: string | null;
  headline: string | null;
  recommended_actions: string[];
  evidence: Record<string, unknown>;
}

export interface CodeRecoveryResponse {
  session_id: number;
  status: string;
  failure_class: string | null;
  headline: string;
  recommended_actions: string[];
  next_safe_action: string | null;
  blocking_reasons: string[];
  evidence: Record<string, unknown>;
}

export interface CodeMcpServer {
  id: number;
  tenant_id: number;
  workspace_id: number;
  server_name: string;
  transport: string;
  connection_status: string;
  capabilities: Record<string, unknown> | null;
  startup_phase?: string | null;
  discovery_status?: string | null;
  resource_count: number;
  tool_count: number;
  failure_class?: string | null;
  degraded_scope?: string | null;
  recovery_recommendations: string[];
  error_message: string | null;
  last_connected_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CodeMcpResource {
  uri: string;
  name: string;
  description: string | null;
  mime_type: string | null;
}

export interface CodeMcpResourceReadResponse {
  uri: string;
  contents: Record<string, unknown>;
}

export interface CodeLspSession {
  id: number;
  workspace_id: number;
  language: string;
  server_name: string;
  status: string;
  root_uri: string | null;
  error_message: string | null;
  last_heartbeat_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CodeLspDiagnostic {
  path: string;
  severity: string;
  message: string;
  line: number;
  code: string | null;
}

export interface CodeLspSymbol {
  name: string;
  kind: string;
  path: string;
}

export interface CodeLspDiagnosticsPayload {
  session: CodeLspSession;
  diagnostics: CodeLspDiagnostic[];
}

export interface CodeLspSymbolsPayload {
  session: CodeLspSession;
  symbols: CodeLspSymbol[];
}

export interface CodeSession {
  id: number;
  tenant_id: number;
  user_id: number;
  workspace_id: number;
  provider: string;
  model: string;
  permission_mode: string;
  title: string | null;
  session_branch: string;
  session_status: CodeSessionStatus;
  verification_status: CodeVerificationStatus;
  token_usage: Record<string, number> | null;
  estimated_cost: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CodeProviderCatalog {
  name: string;
  label: string;
  base_url: string;
  default_model: string;
  is_default: boolean;
}

export interface CodeTurn {
  id: number;
  session_id: number;
  turn_index: number;
  user_message: string;
  assistant_summary: string | null;
  turn_status: string;
  created_at: string | null;
}

export interface CodeToolCall {
  id: number;
  session_id: number;
  turn_id: number | null;
  tool_name: string;
  tool_class: string;
  input_summary: string | null;
  result_summary: string | null;
  duration_ms: number | null;
  exit_code: number | null;
  was_denied: boolean;
  denial_reason: string | null;
  created_at: string | null;
}

export interface CodeEvent {
  id: number;
  session_id: number;
  seq_no: number;
  event_type: string;
  payload: Record<string, unknown>;
  idempotency_key: string | null;
  request_id: string | null;
  created_at: string | null;
}

export interface CodeEventListResponse {
  items: CodeEvent[];
  after_seq: number | null;
  next_seq: number | null;
}

export interface CodeArtifact {
  id: number;
  session_id: number;
  artifact_type: string;
  base_commit: string | null;
  head_commit: string | null;
  changed_files: string[];
  diff_summary: string | null;
  export_path: string | null;
  verification_summary: Record<string, unknown> | null;
  created_at: string | null;
}

export interface CodeDiffResponse {
  session_id: number;
  base_commit: string | null;
  head_commit: string | null;
  changed_files: string[];
  diff_summary: string | null;
  patch: string | null;
}

export interface CodeVerificationRun {
  id: number;
  session_id: number;
  verification_stage: string;
  verification_status: CodeVerificationStatus;
  summary: string | null;
  log_excerpt: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface CodeVerificationResponse {
  session_id: number;
  overall_status: CodeVerificationStatus;
  stages: CodeVerificationRun[];
}

export interface CodeVerificationRunRequest {
  stage?: string;
  stop_on_failure?: boolean;
}

export interface CodeMcpServerConnectRequest {
  server_name: string;
  transport?: string;
}

export interface CodeTask {
  id: number;
  tenant_id: number;
  user_id: number;
  workspace_id: number;
  session_id: number | null;
  title: string;
  objective: string;
  scope: string | null;
  task_packet?: CodeTaskPacket | null;
  task_status: string;
  priority: string;
  acceptance_criteria: unknown[];
  created_at: string | null;
  updated_at: string | null;
}

export interface CodeTaskPacket {
  objective: string;
  scope: string;
  repo: string;
  branch_policy: string;
  acceptance_tests: string[];
  commit_policy: string;
  reporting_contract: string;
  escalation_policy: string;
}

export interface CodeTaskCreateRequest {
  title: string;
  objective: string;
  scope?: string;
  session_id?: number;
  acceptance_criteria?: string[];
  task_packet?: CodeTaskPacket;
}

export interface CodeTaskArchitectRouteRequest {
  acceptance_criteria?: string[];
  summary?: string;
  route_to?: string;
  payload?: Record<string, unknown>;
}

export interface CodeTaskArchitectPlanRequest {
  regenerate?: boolean;
  summary?: string;
  payload?: Record<string, unknown>;
}

export interface CodeTaskArchitectPlanResponse {
  task: CodeTask;
  route_to: string;
  plan_summary: string;
  acceptance_criteria: string[];
  payload: Record<string, unknown>;
}

export interface CodeTaskReviewRequest {
  summary?: string;
  payload?: Record<string, unknown>;
}

export interface CodeTaskReviewDecisionRequest {
  decision: "accept" | "reject";
  summary?: string;
  reason?: string;
  reason_code?: string;
  checklist?: string[];
  payload?: Record<string, unknown>;
}

export interface CodeWorker {
  id: number;
  workspace_id: number;
  task_id: number | null;
  worker_name: string;
  worker_role: string;
  worker_status: string;
  allowed_actions: string[];
  allowed_action_policies: Record<string, CodeActionPolicy>;
  last_error: string | null;
  last_event_summary: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CodeWorkerAssignRequest {
  task_id: number;
  worker_name: string;
}

export interface CodeWorkerStatusUpdateRequest {
  worker_status: string;
  last_error?: string;
  last_event_summary?: string;
  lane?: string;
  event_name?: string;
  payload?: Record<string, unknown>;
}

export interface CodeWorkerEvent {
  id: number;
  workspace_id: number;
  task_id: number | null;
  worker_id: number | null;
  lane: string;
  event_name: string;
  status: string;
  summary: string | null;
  payload: Record<string, unknown>;
  reflection_id?: number | null;
  subagent_run_id?: number | null;
  skill_id?: number | null;
  event_data_version?: number;
  phase?: string | null;
  severity?: "info" | "warning" | "error" | "success" | string | null;
  failure_class?: string | null;
  headline?: string | null;
  recommended_action?: string | null;
  recommended_actions?: string[];
  degraded_scope?: string | null;
  blocking?: boolean;
  created_at: string | null;
}

export interface CodeWorkerEventListResponse {
  items: CodeWorkerEvent[];
  after_id: number | null;
  next_id: number | null;
}

export interface CodeOrchestrationTotals {
  tasks: number;
  workers: number;
  running_tasks: number;
  blocked_tasks: number;
  completed_tasks: number;
  active_lanes: number;
  blocked_lanes: number;
}

export interface CodeOrchestrationLane {
  lane: string;
  worker_name: string | null;
  worker_role: string | null;
  worker_status: string | null;
  task_id: number | null;
  task_title: string | null;
  task_status: string | null;
  latest_event_id: number | null;
  latest_event_name: string | null;
  latest_status: string | null;
  latest_summary: string | null;
  latest_event_at: string | null;
  event_count: number;
  blocked: boolean;
  tone: string;
  headline: string;
  lane_actions: string[];
  lane_action_policies: Record<string, CodeActionPolicy>;
  automation_actions: string[];
  human_actions: string[];
  review_gated_actions: string[];
  automation_ready: boolean;
  automation_blockers: string[];
  automation_summary: string | null;
  next_automation_action: string | null;
  primary_action: string | null;
  primary_action_policy: CodeActionPolicy | null;
}

export interface CodeOrchestrationSnapshot {
  workspace_id: number;
  latest_event_time: string | null;
  verification_gate: string;
  merge_readiness: string;
  operator_posture: string;
  operator_actions: string[];
  operator_action_policies: Record<string, CodeActionPolicy>;
  automation_actions: string[];
  human_actions: string[];
  review_gated_actions: string[];
  automation_ready: boolean;
  automation_blockers: string[];
  automation_summary: string | null;
  next_automation_action: string | null;
  next_human_action: string | null;
  operator_action_classes: Record<string, string>;
  merge_blockers: string[];
  merge_summary: string;
  merge_next_action: string | null;
  merge_evidence: string[];
  heartbeat_status: string;
  heartbeat_summary: string | null;
  reflection_posture: string;
  focus_task_id: number | null;
  focus_task_title: string | null;
  focus_task_status: string | null;
  focus_task_headline: string | null;
  totals: CodeOrchestrationTotals;
  lanes: CodeOrchestrationLane[];
}

export interface CodeAutomationExecutionResponse {
  workspace_id: number;
  session_id: number | null;
  executed_action: string;
  execution_status: string;
  summary: string;
  executed_at: string;
  resulting_session_status?: string | null;
  resulting_verification_status?: string | null;
  snapshot: CodeOrchestrationSnapshot;
}

export interface CodeSessionDetail {
  session: CodeSession;
  workspace: CodeWorkspace;
  lease: CodeWorkspaceLease | null;
  turns: CodeTurn[];
  tool_calls: CodeToolCall[];
  latest_event: CodeEvent | null;
  memory_snapshots: CodeMemorySnapshot[];
  reflection_runs: CodeReflectionRun[];
  subagent_runs: CodeSubagentRun[];
}

export interface CodeSessionListResponse {
  items: CodeSession[];
  active_session_id: number | null;
}

export interface CodeWorkspaceInitRequest {
  repo_root?: string;
  base_branch?: string;
  default_branch?: string;
}

export interface CodeSessionCreateRequest {
  provider?: string;
  model?: string;
  permission_mode?: string;
  resume_session_id?: number;
  acquire_write_lease?: boolean;
}

export interface CodeSessionUpdateRequest {
  title?: string | null;
}

export interface CodeTurnCreateRequest {
  user_message: string;
  stream?: boolean;
  provider?: string;
  model?: string;
}

export interface CodeCancelSessionRequest {
  reason?: string;
}

export interface CodeSafeBashRequest {
  command: string;
}

export interface CodeToolExecutionResponse {
  tool_name: string;
  success: boolean;
  output: string;
  exit_code: number | null;
  denied_reason: string | null;
}

export interface CodeGitStatusResponse {
  session_id: number;
  branch: string;
  success: boolean;
  output: string;
  diff_summary: string | null;
  exit_code: number | null;
}

export interface CodeAutomationJob {
  id: number;
  tenant_id: number;
  workspace_id: number;
  name: string;
  job_type: string;
  enabled: boolean;
  schedule_kind: string;
  cron_expr: string | null;
  interval_sec: number | null;
  timezone: string | null;
  prompt_template: string | null;
  target_scope: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CodeAutomationJobCreateRequest {
  name: string;
  job_type?: string;
  enabled?: boolean;
  schedule_kind?: string;
  cron_expr?: string;
  interval_sec?: number;
  timezone?: string;
  prompt_template?: string;
  target_scope?: string;
}

export interface CodeAutomationJobUpdateRequest {
  enabled?: boolean;
  schedule_kind?: string;
  cron_expr?: string;
  interval_sec?: number;
  timezone?: string;
  prompt_template?: string;
  target_scope?: string;
  last_error?: string;
}

export interface CodeAgentRuntimeState {
  id: number;
  workspace_id: number;
  heartbeat_enabled: boolean;
  memory_enabled: boolean;
  reflections_enabled: boolean;
  last_heartbeat_decision: string | null;
  last_heartbeat_at: string | null;
  last_memory_sync_at: string | null;
  last_reflection_at: string | null;
  last_compressed_turn_index: number | null;
  runtime_metrics: CodeRuntimeMetrics;
  created_at: string | null;
  updated_at: string | null;
}

export interface CodeRunLedgerArtifactSummary {
  slice?: string;
  outcome?: string;
  target_surface?: string;
  target_id?: string;
  target_route?: string;
  recorded_at?: string;
}

export interface CodeRuntimeMetrics extends Record<string, unknown> {
  last_heartbeat_summary?: string;
  last_heartbeat_risk_level?: string;
  last_heartbeat_planner_recommendation?: string;
  last_heartbeat_planner_steps?: string[];
  last_heartbeat_critic_notes?: string[];
  last_heartbeat_critic_checks?: string[];
  last_heartbeat_loop_budget?: string;
  last_heartbeat_convergence_signal?: string;
  last_heartbeat_difficulty_signals?: string[];
  last_heartbeat_policy_learning_snapshot?: Record<string, Record<string, number>>;
  last_heartbeat_focus_task_id?: number;
  last_heartbeat_focus_task_title?: string;
  last_heartbeat_next_automation_action?: string;
  last_heartbeat_executed_action?: string;
  last_heartbeat_execution_status?: string;
  last_reflection_verified_signal?: boolean | null;
  last_reflection_verification_signals?: string[];
  last_automation_execution?: {
    session_id?: number | null;
    executed_action?: string;
    execution_status?: string;
    summary?: string;
    executed_at?: string;
    resulting_session_status?: string | null;
    resulting_verification_status?: string | null;
  } | null;
  last_maintenance_summary?: string;
  last_maintenance_generated_at?: string;
  last_maintenance_report_markdown_path?: string;
  last_maintenance_report_json_path?: string;
  last_maintenance_project_brain_path?: string;
  last_maintenance_decision_journal_path?: string;
  last_maintenance_evolution_log_path?: string;
  next_autonomy_mode?: string;
  next_autonomy_objective?: string;
  last_seeded_autonomy_task_id?: number;
  last_seeded_autonomy_objective?: string;
  last_seeded_autonomy_at?: string;
  last_recovery_task_id?: number;
  last_recovery_failure_class?: string;
  last_recovery_task_at?: string;
  last_provider_failure_class?: string;
  last_provider_backpressure_at?: string;
  provider_backpressure_count?: number;
  provider_pause_until?: string;
  last_provider_resume_at?: string;
  workflow_mode?: string;
  workflow_skills?: string[];
  workflow_rationale?: string[];
  experience_quality?: {
    score?: number;
    posture?: string;
    notes?: string[];
  };
  last_run_ledger_artifact?: CodeRunLedgerArtifactSummary;
  policy_learning?: Record<string, Record<string, number>>;
}

export interface CodeSubagentRun {
  id: number;
  workspace_id: number;
  session_id: number | null;
  task_id: number | null;
  worker_id: number | null;
  objective: string;
  run_status: string;
  result_summary: string | null;
  metadata_json: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
}

export interface CodeRuntimeResponse {
  workspace_id: number;
  runtime_state: CodeAgentRuntimeState;
  automation_jobs: CodeAutomationJob[];
  active_subagents: CodeSubagentRun[];
  pending_reflections: number;
  available_providers?: CodeProviderCatalog[];
  team_models?: string[];
}

export interface CodeMemorySnapshot {
  id: number;
  workspace_id: number;
  session_id: number;
  snapshot_kind: string;
  source_turn_start: number | null;
  source_turn_end: number | null;
  summary_markdown: string;
  history_excerpt: string | null;
  token_estimate: number | null;
  created_at: string | null;
}

export interface CodeMemoryRefreshResponse {
  session_id: number;
  snapshot: CodeMemorySnapshot;
}

export interface CodeSessionSearchRequest {
  query: string;
  limit?: number;
}

export interface CodeSessionSearchResult {
  session_id: number;
  score: number;
  headline: string;
  summary: string;
  matched_turn_ids: number[];
  matched_artifact_ids: number[];
  matched_event_ids: number[];
}

export interface CodeSessionSearchResponse {
  query: string;
  results: CodeSessionSearchResult[];
}

export interface CodeSkillRevision {
  id: number;
  skill_id: number;
  reflection_run_id: number | null;
  revision_number: number;
  revision_status: string;
  change_summary: string | null;
  content_markdown: string;
  supporting_files: Record<string, unknown>;
  created_at: string | null;
}

export interface CodeSkill {
  id: number;
  tenant_id: number;
  workspace_id: number;
  origin_task_id: number | null;
  created_by_user_id: number | null;
  name: string;
  slug: string;
  description: string | null;
  skill_status: string;
  directory_path: string;
  latest_revision_number: number;
  usage_count: number;
  positive_feedback_count: number;
  negative_feedback_count: number;
  last_used_at: string | null;
  last_feedback_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  latest_revision: CodeSkillRevision | null;
}

export interface CodeSkillCreateRequest {
  name: string;
  slug: string;
  description?: string;
  content_markdown: string;
  supporting_files?: Record<string, string>;
}

export interface CodeSkillUpdateRequest {
  description?: string;
  skill_status?: string;
  change_summary?: string;
  content_markdown?: string;
  supporting_files?: Record<string, string>;
}

export interface CodeSkillFeedbackRequest {
  sentiment: "positive" | "negative";
  note?: string;
}

export interface CodeReflectionRun {
  id: number;
  workspace_id: number;
  session_id: number;
  task_id: number | null;
  skill_id: number | null;
  trigger_source: string;
  reflection_status: string;
  output_kind: string;
  summary: string | null;
  payload: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  skill: CodeSkill | null;
}

export interface CodeReflectionRunRequest {
  session_id: number;
  task_id?: number;
  trigger_source?: string;
}

export interface CodeReleaseArtifact {
  key: string;
  label: string;
  relative_path: string;
  download_url: string;
  content_type: string;
}

export interface CodeReleaseCheck {
  status: string;
  name: string;
  summary: string;
}

export interface CodeReleaseReadiness {
  generated_at: string | null;
  release_state: string;
  backend_version: string;
  frontend_version: string;
  git_branch: string;
  git_commit: string;
  preflight_pass_count: number;
  preflight_warn_count: number;
  preflight_fail_count: number;
  known_warnings: string[];
  known_limitations: string[];
  recommended_next_action: string | null;
  checks: CodeReleaseCheck[];
  report_markdown: string;
  report_path: string;
  code_smoke_path: string | null;
  bos_smoke_path: string | null;
  artifacts: CodeReleaseArtifact[];
}
