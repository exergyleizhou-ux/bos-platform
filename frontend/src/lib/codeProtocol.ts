export const CODE_LANES = {
  tasking: "tasking",
  architect: "architect",
  executor: "executor",
  reviewer: "reviewer",
} as const;

export const CODE_TASK_STATUSES = {
  created: "created",
  running: "running",
  reviewPending: "review_pending",
  inReview: "in_review",
  verificationPending: "verification_pending",
  completed: "completed",
  blocked: "blocked",
  failed: "failed",
} as const;

export const CODE_WORKER_STATUSES = {
  idle: "idle",
  spawning: "spawning",
  trustRequired: "trust_required",
  readyForPrompt: "ready_for_prompt",
  promptAccepted: "prompt_accepted",
  ready: "ready",
  assigned: "assigned",
  running: "running",
  waitingReview: "waiting_review",
  blocked: "blocked",
  failed: "failed",
  completed: "completed",
} as const;

export const CODE_REVIEW_DECISIONS = {
  accept: "accept",
  reject: "reject",
} as const;

export const CODE_OPERATOR_POSTURES = {
  idle: "idle",
  pending: "pending",
  planningRequired: "planning_required",
  executionActive: "execution_active",
  reviewQueue: "review_queue",
  reviewActive: "review_active",
  verificationGate: "verification_gate",
  blocked: "blocked",
  recoveryRequired: "recovery_required",
  degraded: "degraded",
  completed: "completed",
  mergeReady: "merge_ready",
} as const;

export const CODE_CONTROL_ACTIONS = {
  architectPlan: "architect_plan",
  architectRoute: "architect_route",
  requestReview: "request_review",
  beginReview: "begin_review",
  acceptReview: "accept_review",
  rejectReview: "reject_review",
  markReviewerReady: "mark_reviewer_ready",
  markReviewerBlocked: "mark_reviewer_blocked",
  markExecutorBlocked: "mark_executor_blocked",
  markExecutorReady: "mark_executor_ready",
  markArchitectReady: "mark_architect_ready",
  markArchitectBlocked: "mark_architect_blocked",
  runVerification: "run_verification",
  refreshBranch: "refresh_branch",
  resetSessionReady: "reset_session_ready",
  inspectDiff: "inspect_diff",
  reviewDiff: "review_diff",
  prepareMerge: "prepare_merge",
  inspectContext: "inspect_context",
} as const;

export const CODE_LANE_EVENTS = {
  taskCreated: "task.created",
  taskRouted: "task.routed",
  laneStarted: "lane.started",
  laneProgressed: "lane.progressed",
  laneBlocked: "lane.blocked",
  laneCompleted: "lane.completed",
  reviewRequested: "review.requested",
  reviewPacketReady: "review.packet.ready",
  reviewAccepted: "review.accepted",
  reviewRejected: "review.rejected",
  taskCompleted: "task.completed",
  taskFailed: "task.failed",
  mergeReadinessUpdated: "merge.readiness.updated",
} as const;
