"""
BOS Code v9.0 schemas.

Typed API contracts for the embedded BOS Code workspace, sessions,
events, diffs, artifacts, and verification surfaces.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SESSION_STATUS_PATTERN = r"^(created|spawning|trust_required|ready_for_prompt|prompt_accepted|ready|running|blocked|completed|failed|cancelled)$"
VERIFICATION_STATUS_PATTERN = r"^(pending|running|passed|failed|skipped)$"


class CodeWorkspaceInitRequest(BaseModel):
    """Create or reconcile the tenant workspace."""

    repo_root: str | None = Field(
        default=None,
        max_length=500,
        description="Repository-relative or configured repo root hint.",
    )
    base_branch: str | None = Field(default=None, max_length=255)
    default_branch: str | None = Field(default=None, max_length=255)


class CodeWorkspaceLeaseResponse(BaseModel):
    """Backend lease state for a code workspace."""

    id: int
    workspace_id: int
    active_session_id: int | None = None
    lease_owner_user_id: int | None = None
    lease_status: str
    lease_expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeWorkspaceResponse(BaseModel):
    """Tenant workspace summary."""

    id: int
    tenant_id: int
    repo_root: str
    worktree_root: str
    base_branch: str
    default_branch: str
    active_branch: str
    workspace_status: str
    base_commit: str | None = None
    head_commit: str | None = None
    dirty_state: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    lease: CodeWorkspaceLeaseResponse | None = None

    model_config = {"from_attributes": True}


class CodeWorkspaceStatusResponse(BaseModel):
    """Workspace health and occupancy status."""

    workspace: CodeWorkspaceResponse
    lease: CodeWorkspaceLeaseResponse | None = None
    can_write: bool = False
    permission_mode: str
    latest_event_time: datetime | None = None


class CodeWorkspaceTreeItem(BaseModel):
    """File tree node within the tenant worktree."""

    path: str
    name: str
    node_type: str = Field(..., pattern=r"^(file|directory)$")
    has_children: bool = False
    size_bytes: int | None = None


class CodeWorkspaceTreeResponse(BaseModel):
    """Directory listing response."""

    root: str
    items: list[CodeWorkspaceTreeItem] = Field(default_factory=list)


class CodeWorkspaceFileResponse(BaseModel):
    """Current file contents in the tenant worktree."""

    path: str
    content: str
    encoding: str = "utf-8"
    truncated: bool = False
    size_bytes: int | None = None


class CodeBranchStateResponse(BaseModel):
    """Persisted branch posture for a workspace/session branch."""

    id: int
    workspace_id: int
    branch_name: str
    base_branch: str
    head_commit: str | None = None
    base_commit: str | None = None
    merge_base_commit: str | None = None
    is_dirty: bool
    is_stale_against_base: bool
    ahead_count: int | None = None
    behind_count: int | None = None
    branch_status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeReadinessResponse(BaseModel):
    """Readiness posture derived from branch state."""

    session_id: int
    branch_state: CodeBranchStateResponse
    readiness: str
    blocking_reasons: list[str] = Field(default_factory=list)
    failure_class: str | None = None
    headline: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class CodeRecoveryResponse(BaseModel):
    """Recovery guidance surface for BOS Code."""

    session_id: int
    status: str
    failure_class: str | None = None
    headline: str
    recommended_actions: list[str] = Field(default_factory=list)
    next_safe_action: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class CodeMcpServerConnectRequest(BaseModel):
    """Connect or register an MCP server."""

    server_name: str = Field(..., min_length=1, max_length=150)
    transport: str = Field(default="stub", max_length=50)


class CodeMcpServerResponse(BaseModel):
    """MCP server lifecycle state."""

    id: int
    tenant_id: int
    workspace_id: int
    server_name: str
    transport: str
    connection_status: str
    capabilities: dict[str, Any] | None = None
    startup_phase: str | None = None
    discovery_status: str | None = None
    resource_count: int = 0
    tool_count: int = 0
    failure_class: str | None = None
    degraded_scope: str | None = None
    recovery_recommendations: list[str] = Field(default_factory=list)
    error_message: str | None = None
    last_connected_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeMcpResourceResponse(BaseModel):
    """Minimal MCP resource descriptor."""

    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None


class CodeMcpResourceReadResponse(BaseModel):
    """Resource contents read from a minimal MCP server."""

    uri: str
    contents: dict[str, Any]


class CodeLspSessionResponse(BaseModel):
    """LSP lifecycle state for a workspace language session."""

    id: int
    workspace_id: int
    language: str
    server_name: str
    status: str
    root_uri: str | None = None
    error_message: str | None = None
    last_heartbeat_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeLspDiagnosticResponse(BaseModel):
    path: str
    severity: str
    message: str
    line: int
    code: str | None = None


class CodeLspSymbolResponse(BaseModel):
    name: str
    kind: str
    path: str


class CodeLspDiagnosticsPayload(BaseModel):
    session: CodeLspSessionResponse
    diagnostics: list[CodeLspDiagnosticResponse] = Field(default_factory=list)


class CodeLspSymbolsPayload(BaseModel):
    session: CodeLspSessionResponse
    symbols: list[CodeLspSymbolResponse] = Field(default_factory=list)


class CodeTaskPacket(BaseModel):
    objective: str = Field(..., min_length=1, max_length=4000)
    scope: str = Field(..., min_length=1, max_length=4000)
    repo: str = Field(..., min_length=1, max_length=500)
    branch_policy: str = Field(..., min_length=1, max_length=500)
    acceptance_tests: list[str] = Field(default_factory=list)
    commit_policy: str = Field(..., min_length=1, max_length=1000)
    reporting_contract: str = Field(..., min_length=1, max_length=2000)
    escalation_policy: str = Field(..., min_length=1, max_length=2000)


class CodeTaskResponse(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    workspace_id: int
    session_id: int | None = None
    title: str
    objective: str
    scope: str | None = None
    task_packet: CodeTaskPacket | None = None
    task_status: str
    priority: str
    acceptance_criteria: list[Any] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeTaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    objective: str = Field(..., min_length=1, max_length=4000)
    scope: str | None = Field(default=None, max_length=4000)
    session_id: int | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    task_packet: CodeTaskPacket | None = None


class CodeTaskArchitectRouteRequest(BaseModel):
    acceptance_criteria: list[str] = Field(default_factory=list)
    summary: str | None = Field(default=None, max_length=4000)
    route_to: str = Field(default="executor", min_length=1, max_length=150)
    payload: dict[str, Any] = Field(default_factory=dict)


class CodeTaskArchitectPlanRequest(BaseModel):
    regenerate: bool = False
    summary: str | None = Field(default=None, max_length=4000)
    payload: dict[str, Any] = Field(default_factory=dict)


class CodeTaskArchitectPlanResponse(BaseModel):
    task: CodeTaskResponse
    route_to: str
    plan_summary: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class CodeTaskReviewRequest(BaseModel):
    summary: str | None = Field(default=None, max_length=4000)
    payload: dict[str, Any] = Field(default_factory=dict)


class CodeTaskReviewDecisionRequest(BaseModel):
    decision: str = Field(..., pattern=r"^(accept|reject)$")
    summary: str | None = Field(default=None, max_length=4000)
    reason: str | None = Field(default=None, max_length=4000)
    reason_code: str | None = Field(default=None, max_length=100)
    checklist: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class CodeWorkerResponse(BaseModel):
    id: int
    workspace_id: int
    task_id: int | None = None
    worker_name: str
    worker_role: str
    worker_status: str
    allowed_actions: list[str] = Field(default_factory=list)
    allowed_action_policies: dict[str, str] = Field(default_factory=dict)
    last_error: str | None = None
    last_event_summary: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeWorkerAssignRequest(BaseModel):
    task_id: int
    worker_name: str = Field(..., min_length=1, max_length=150)


class CodeWorkerStatusUpdateRequest(BaseModel):
    worker_status: str = Field(..., min_length=1, max_length=50)
    last_error: str | None = Field(default=None, max_length=4000)
    last_event_summary: str | None = Field(default=None, max_length=4000)
    lane: str | None = Field(default=None, min_length=1, max_length=100)
    event_name: str | None = Field(default=None, min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class CodeWorkerEventResponse(BaseModel):
    id: int
    workspace_id: int
    task_id: int | None = None
    worker_id: int | None = None
    lane: str
    event_name: str
    status: str
    summary: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    reflection_id: int | None = None
    subagent_run_id: int | None = None
    skill_id: int | None = None
    event_data_version: int = 1
    phase: str | None = None
    severity: str | None = None
    failure_class: str | None = None
    headline: str | None = None
    recommended_action: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    degraded_scope: str | None = None
    blocking: bool = False
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeWorkerEventListResponse(BaseModel):
    items: list[CodeWorkerEventResponse] = Field(default_factory=list)
    after_id: int | None = None
    next_id: int | None = None


class CodeOrchestrationTotalsResponse(BaseModel):
    tasks: int = 0
    workers: int = 0
    running_tasks: int = 0
    blocked_tasks: int = 0
    completed_tasks: int = 0
    active_lanes: int = 0
    blocked_lanes: int = 0


class CodeOrchestrationLaneResponse(BaseModel):
    lane: str
    worker_name: str | None = None
    worker_role: str | None = None
    worker_status: str | None = None
    task_id: int | None = None
    task_title: str | None = None
    task_status: str | None = None
    latest_event_id: int | None = None
    latest_event_name: str | None = None
    latest_status: str | None = None
    latest_summary: str | None = None
    latest_event_at: datetime | None = None
    event_count: int = 0
    blocked: bool = False
    tone: str = "neutral"
    headline: str
    lane_actions: list[str] = Field(default_factory=list)
    lane_action_policies: dict[str, str] = Field(default_factory=dict)
    automation_actions: list[str] = Field(default_factory=list)
    human_actions: list[str] = Field(default_factory=list)
    review_gated_actions: list[str] = Field(default_factory=list)
    automation_ready: bool = False
    automation_blockers: list[str] = Field(default_factory=list)
    automation_summary: str | None = None
    next_automation_action: str | None = None
    primary_action: str | None = None
    primary_action_policy: str | None = None


class CodeOrchestrationSnapshotResponse(BaseModel):
    workspace_id: int
    latest_event_time: datetime | None = None
    verification_gate: str = "not_required"
    merge_readiness: str = "idle"
    operator_posture: str = "idle"
    operator_actions: list[str] = Field(default_factory=list)
    operator_action_policies: dict[str, str] = Field(default_factory=dict)
    automation_actions: list[str] = Field(default_factory=list)
    human_actions: list[str] = Field(default_factory=list)
    review_gated_actions: list[str] = Field(default_factory=list)
    automation_ready: bool = False
    automation_blockers: list[str] = Field(default_factory=list)
    automation_summary: str | None = None
    next_automation_action: str | None = None
    next_human_action: str | None = None
    operator_action_classes: dict[str, str] = Field(default_factory=dict)
    merge_blockers: list[str] = Field(default_factory=list)
    merge_summary: str = "Merge posture is idle."
    merge_next_action: str | None = None
    merge_evidence: list[str] = Field(default_factory=list)
    heartbeat_status: str = "idle"
    heartbeat_summary: str | None = None
    reflection_posture: str = "idle"
    focus_task_id: int | None = None
    focus_task_title: str | None = None
    focus_task_status: str | None = None
    focus_task_headline: str | None = None
    totals: CodeOrchestrationTotalsResponse
    lanes: list[CodeOrchestrationLaneResponse] = Field(default_factory=list)


class CodeAutomationExecutionResponse(BaseModel):
    workspace_id: int
    session_id: int | None = None
    executed_action: str
    execution_status: str
    summary: str
    executed_at: datetime
    resulting_session_status: str | None = None
    resulting_verification_status: str | None = None
    snapshot: CodeOrchestrationSnapshotResponse


class CodeAutomationJobResponse(BaseModel):
    id: int
    tenant_id: int
    workspace_id: int
    name: str
    job_type: str
    enabled: bool
    schedule_kind: str
    cron_expr: str | None = None
    interval_sec: int | None = None
    timezone: str | None = None
    prompt_template: str | None = None
    target_scope: str | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeAutomationJobCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    job_type: str = Field(default="cron", min_length=1, max_length=50)
    enabled: bool = True
    schedule_kind: str = Field(default="manual", min_length=1, max_length=50)
    cron_expr: str | None = Field(default=None, max_length=120)
    interval_sec: int | None = Field(default=None, ge=1, le=604800)
    timezone: str | None = Field(default=None, max_length=80)
    prompt_template: str | None = Field(default=None, max_length=4000)
    target_scope: str | None = Field(default=None, max_length=100)


class CodeAutomationJobUpdateRequest(BaseModel):
    enabled: bool | None = None
    schedule_kind: str | None = Field(default=None, max_length=50)
    cron_expr: str | None = Field(default=None, max_length=120)
    interval_sec: int | None = Field(default=None, ge=1, le=604800)
    timezone: str | None = Field(default=None, max_length=80)
    prompt_template: str | None = Field(default=None, max_length=4000)
    target_scope: str | None = Field(default=None, max_length=100)
    last_error: str | None = Field(default=None, max_length=4000)


class CodeRunLedgerArtifactSummaryResponse(BaseModel):
    slice: str | None = None
    outcome: str | None = None
    target_surface: str | None = None
    target_id: str | None = None
    target_route: str | None = None
    recorded_at: datetime | None = None


class CodeRuntimeMetricsResponse(BaseModel):
    last_heartbeat_summary: str | None = None
    last_heartbeat_risk_level: str | None = None
    last_heartbeat_planner_recommendation: str | None = None
    last_heartbeat_planner_steps: list[str] = Field(default_factory=list)
    last_heartbeat_critic_notes: list[str] = Field(default_factory=list)
    last_heartbeat_critic_checks: list[str] = Field(default_factory=list)
    last_heartbeat_loop_budget: str | None = None
    last_heartbeat_convergence_signal: str | None = None
    last_heartbeat_difficulty_signals: list[str] = Field(default_factory=list)
    last_heartbeat_policy_learning_snapshot: dict[str, dict[str, int]] = Field(default_factory=dict)
    last_heartbeat_focus_task_id: int | None = None
    last_heartbeat_focus_task_title: str | None = None
    last_heartbeat_next_automation_action: str | None = None
    last_heartbeat_executed_action: str | None = None
    last_heartbeat_execution_status: str | None = None
    last_reflection_verified_signal: bool | None = None
    last_reflection_verification_signals: list[str] = Field(default_factory=list)
    last_automation_execution: dict[str, Any] | None = None
    last_run_ledger_artifact: CodeRunLedgerArtifactSummaryResponse | None = None
    policy_learning: dict[str, dict[str, int]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class CodeAgentRuntimeStateResponse(BaseModel):
    id: int
    workspace_id: int
    heartbeat_enabled: bool
    memory_enabled: bool
    reflections_enabled: bool
    last_heartbeat_decision: str | None = None
    last_heartbeat_at: datetime | None = None
    last_memory_sync_at: datetime | None = None
    last_reflection_at: datetime | None = None
    last_compressed_turn_index: int | None = None
    runtime_metrics: CodeRuntimeMetricsResponse = Field(default_factory=CodeRuntimeMetricsResponse)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeSubagentRunResponse(BaseModel):
    id: int
    workspace_id: int
    session_id: int | None = None
    task_id: int | None = None
    worker_id: int | None = None
    objective: str
    run_status: str
    result_summary: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeRuntimeResponse(BaseModel):
    workspace_id: int
    runtime_state: CodeAgentRuntimeStateResponse
    automation_jobs: list[CodeAutomationJobResponse] = Field(default_factory=list)
    active_subagents: list[CodeSubagentRunResponse] = Field(default_factory=list)
    pending_reflections: int = 0
    available_providers: list["CodeProviderCatalogResponse"] = Field(default_factory=list)
    team_models: list[str] = Field(default_factory=list)


class CodeProviderCatalogResponse(BaseModel):
    name: str
    label: str
    base_url: str
    default_model: str
    is_default: bool = False


class CodeSessionCreateRequest(BaseModel):
    """Create a code session."""

    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=150)
    permission_mode: str | None = Field(default=None, max_length=50)
    resume_session_id: int | None = None
    acquire_write_lease: bool = True


class CodeSessionUpdateRequest(BaseModel):
    """Update mutable session metadata."""

    title: str | None = Field(default=None, max_length=255)


class CodeSessionResponse(BaseModel):
    """Primary session response."""

    id: int
    tenant_id: int
    user_id: int
    workspace_id: int
    provider: str
    model: str
    permission_mode: str
    title: str | None = None
    session_branch: str
    session_status: str = Field(..., pattern=SESSION_STATUS_PATTERN)
    verification_status: str = Field(..., pattern=VERIFICATION_STATUS_PATTERN)
    token_usage: dict[str, Any] | None = None
    estimated_cost: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeTurnResponse(BaseModel):
    """Single turn within a coding session."""

    id: int
    session_id: int
    turn_index: int
    user_message: str
    assistant_summary: str | None = None
    turn_status: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeTurnCreateRequest(BaseModel):
    """Prompt submission for a new turn."""

    user_message: str = Field(..., min_length=1, max_length=20000)
    stream: bool = True
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=150)


class CodeCancelSessionRequest(BaseModel):
    """Session cancellation request."""

    reason: str | None = Field(default=None, max_length=500)


class CodeSafeBashRequest(BaseModel):
    """Safe shell execution request."""

    command: str = Field(..., min_length=1, max_length=1000)


class CodeToolCallResponse(BaseModel):
    """Auditable tool execution record."""

    id: int
    session_id: int
    turn_id: int | None = None
    tool_name: str
    tool_class: str
    input_summary: str | None = None
    result_summary: str | None = None
    duration_ms: float | None = None
    exit_code: int | None = None
    was_denied: bool
    denial_reason: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeEventResponse(BaseModel):
    """Append-only session event."""

    id: int
    session_id: int
    seq_no: int
    event_type: str
    payload: dict[str, Any]
    idempotency_key: str | None = None
    request_id: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeEventListResponse(BaseModel):
    """Replayable event list."""

    items: list[CodeEventResponse] = Field(default_factory=list)
    after_seq: int | None = None
    next_seq: int | None = None


class CodeArtifactResponse(BaseModel):
    """Generated artifact for a session."""

    id: int
    session_id: int
    artifact_type: str
    base_commit: str | None = None
    head_commit: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    diff_summary: str | None = None
    export_path: str | None = None
    verification_summary: dict[str, Any] | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeDiffResponse(BaseModel):
    """Diff surface for a session."""

    session_id: int
    base_commit: str | None = None
    head_commit: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    diff_summary: str | None = None
    patch: str | None = None


class CodeToolExecutionResponse(BaseModel):
    """Result of a directly invoked runtime tool."""

    tool_name: str
    success: bool
    output: str
    exit_code: int | None = None
    denied_reason: str | None = None


class CodeGitStatusResponse(BaseModel):
    """Controlled git surface for a session worktree."""

    session_id: int
    branch: str
    success: bool
    output: str
    diff_summary: str | None = None
    exit_code: int | None = None


class CodeVerificationRunResponse(BaseModel):
    """Single verification stage result."""

    id: int
    session_id: int
    verification_stage: str
    verification_status: str = Field(..., pattern=VERIFICATION_STATUS_PATTERN)
    summary: str | None = None
    log_excerpt: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeVerificationResponse(BaseModel):
    """Verification summary for a session."""

    session_id: int
    overall_status: str = Field(..., pattern=VERIFICATION_STATUS_PATTERN)
    stages: list[CodeVerificationRunResponse] = Field(default_factory=list)


class CodeVerificationRunRequest(BaseModel):
    """Trigger verification execution."""

    stage: str | None = Field(default=None, max_length=50)
    stop_on_failure: bool = True


class CodeSessionDetailResponse(BaseModel):
    """Hydrated session detail used by the cockpit."""

    session: CodeSessionResponse
    workspace: CodeWorkspaceResponse
    lease: CodeWorkspaceLeaseResponse | None = None
    turns: list[CodeTurnResponse] = Field(default_factory=list)
    tool_calls: list[CodeToolCallResponse] = Field(default_factory=list)
    latest_event: CodeEventResponse | None = None
    memory_snapshots: list["CodeMemorySnapshotResponse"] = Field(default_factory=list)
    reflection_runs: list["CodeReflectionRunResponse"] = Field(default_factory=list)
    subagent_runs: list[CodeSubagentRunResponse] = Field(default_factory=list)


class CodeSessionListResponse(BaseModel):
    """List response for sessions."""

    items: list[CodeSessionResponse] = Field(default_factory=list)
    active_session_id: int | None = None


class CodeMemorySnapshotResponse(BaseModel):
    id: int
    workspace_id: int
    session_id: int
    snapshot_kind: str
    source_turn_start: int | None = None
    source_turn_end: int | None = None
    summary_markdown: str
    history_excerpt: str | None = None
    token_estimate: int | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeMemoryRefreshResponse(BaseModel):
    session_id: int
    snapshot: CodeMemorySnapshotResponse


class CodeSessionSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)


class CodeSessionSearchResultResponse(BaseModel):
    session_id: int
    score: float
    headline: str
    summary: str
    matched_turn_ids: list[int] = Field(default_factory=list)
    matched_artifact_ids: list[int] = Field(default_factory=list)
    matched_event_ids: list[int] = Field(default_factory=list)


class CodeSessionSearchResponse(BaseModel):
    query: str
    results: list[CodeSessionSearchResultResponse] = Field(default_factory=list)


class CodeSkillRevisionResponse(BaseModel):
    id: int
    skill_id: int
    reflection_run_id: int | None = None
    revision_number: int
    revision_status: str
    change_summary: str | None = None
    content_markdown: str
    supporting_files: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CodeSkillResponse(BaseModel):
    id: int
    tenant_id: int
    workspace_id: int
    origin_task_id: int | None = None
    created_by_user_id: int | None = None
    name: str
    slug: str
    description: str | None = None
    skill_status: str
    directory_path: str
    latest_revision_number: int
    usage_count: int = 0
    positive_feedback_count: int = 0
    negative_feedback_count: int = 0
    last_used_at: datetime | None = None
    last_feedback_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    latest_revision: CodeSkillRevisionResponse | None = None

    model_config = {"from_attributes": True}


class CodeSkillCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    slug: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    content_markdown: str = Field(..., min_length=1, max_length=50000)
    supporting_files: dict[str, str] = Field(default_factory=dict)


class CodeSkillUpdateRequest(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    skill_status: str | None = Field(default=None, max_length=50)
    change_summary: str | None = Field(default=None, max_length=2000)
    content_markdown: str | None = Field(default=None, max_length=50000)
    supporting_files: dict[str, str] = Field(default_factory=dict)


class CodeSkillFeedbackRequest(BaseModel):
    sentiment: str = Field(..., pattern=r"^(positive|negative)$")
    note: str | None = Field(default=None, max_length=2000)


class CodeReflectionRunResponse(BaseModel):
    id: int
    workspace_id: int
    session_id: int
    task_id: int | None = None
    skill_id: int | None = None
    trigger_source: str
    reflection_status: str
    output_kind: str
    summary: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    skill: CodeSkillResponse | None = None

    model_config = {"from_attributes": True}


class CodeReflectionRunRequest(BaseModel):
    session_id: int = Field(..., ge=1)
    task_id: int | None = Field(default=None, ge=1)
    trigger_source: str = Field(default="manual", min_length=1, max_length=50)


class CodeReleaseArtifactResponse(BaseModel):
    key: str
    label: str
    relative_path: str
    download_url: str
    content_type: str


class CodeReleaseCheckResponse(BaseModel):
    status: str
    name: str
    summary: str


class CodeReleaseReadinessResponse(BaseModel):
    generated_at: datetime | None = None
    release_state: str
    backend_version: str
    frontend_version: str
    git_branch: str
    git_commit: str
    preflight_pass_count: int = 0
    preflight_warn_count: int = 0
    preflight_fail_count: int = 0
    known_warnings: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    recommended_next_action: str | None = None
    checks: list[CodeReleaseCheckResponse] = Field(default_factory=list)
    report_markdown: str = ""
    report_path: str
    code_smoke_path: str | None = None
    bos_smoke_path: str | None = None
    artifacts: list[CodeReleaseArtifactResponse] = Field(default_factory=list)
