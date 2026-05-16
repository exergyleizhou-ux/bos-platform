import { describe, expect, it } from "vitest";

import { buildCodeOrchestrationReadModel, pickCodeFocusTask } from "@/lib/code-orchestration-read-model";
import type { CodeTask, CodeWorker, CodeWorkerEvent } from "@/types/code";

const tasks: CodeTask[] = [
  {
    id: 11,
    tenant_id: 1,
    user_id: 7,
    workspace_id: 3,
    session_id: 19,
    title: "Stabilize worker event stream",
    objective: "Make worker orchestration observable.",
    scope: "code/orchestration",
    task_status: "running",
    priority: "normal",
    acceptance_criteria: [],
    created_at: "2026-04-10T05:00:00Z",
    updated_at: "2026-04-10T05:02:00Z",
  },
  {
    id: 12,
    tenant_id: 1,
    user_id: 7,
    workspace_id: 3,
    session_id: 19,
    title: "Wire lane panel",
    objective: "Show current lane posture in cockpit.",
    scope: "frontend/cockpit",
    task_status: "blocked",
    priority: "normal",
    acceptance_criteria: [],
    created_at: "2026-04-10T05:03:00Z",
    updated_at: "2026-04-10T05:05:00Z",
  },
];

const workers: CodeWorker[] = [
  {
    id: 101,
    workspace_id: 3,
    task_id: 11,
    worker_name: "executor",
    worker_role: "implementer",
    worker_status: "running",
    allowed_actions: ["mark_blocked", "mark_ready"],
    allowed_action_policies: {
      mark_blocked: "automation_safe",
      mark_ready: "automation_safe",
    },
    last_error: null,
    last_event_summary: "Implementing the read model.",
    created_at: "2026-04-10T05:00:00Z",
    updated_at: "2026-04-10T05:06:00Z",
  },
  {
    id: 102,
    workspace_id: 3,
    task_id: 12,
    worker_name: "reviewer",
    worker_role: "reviewer",
    worker_status: "failed",
    allowed_actions: ["mark_ready"],
    allowed_action_policies: {
      mark_ready: "automation_safe",
    },
    last_error: "Panel contract mismatch.",
    last_event_summary: "Review blocked on missing lane summary.",
    created_at: "2026-04-10T05:00:00Z",
    updated_at: "2026-04-10T05:07:00Z",
  },
];

const workerEvents: CodeWorkerEvent[] = [
  {
    id: 201,
    workspace_id: 3,
    task_id: 11,
    worker_id: null,
    lane: "tasking",
    event_name: "task.created",
    status: "created",
    summary: "Task #11 created: Stabilize worker event stream",
    payload: { task_id: 11 },
    created_at: "2026-04-10T05:00:00Z",
  },
  {
    id: 202,
    workspace_id: 3,
    task_id: 11,
    worker_id: 101,
    lane: "executor",
    event_name: "worker.assigned",
    status: "running",
    summary: "Assigned to task #11",
    payload: { task_id: 11 },
    created_at: "2026-04-10T05:01:00Z",
  },
  {
    id: 203,
    workspace_id: 3,
    task_id: 12,
    worker_id: 102,
    lane: "reviewer",
    event_name: "worker.status_changed",
    status: "failed",
    summary: "Review blocked on missing lane summary.",
    payload: { task_id: 12 },
    created_at: "2026-04-10T05:07:00Z",
  },
];

describe("Code orchestration read model", () => {
  it("derives lane summaries from task, worker, and event state", () => {
    const view = buildCodeOrchestrationReadModel(tasks, workers, workerEvents);

    expect(view.totals.tasks).toBe(2);
    expect(view.totals.runningTasks).toBe(1);
    expect(view.totals.blockedTasks).toBe(1);
    expect(view.totals.blockedLanes).toBe(1);
    expect(view.latestEventAt).toBe("2026-04-10T05:07:00Z");

    const executorLane = view.lanes.find((lane) => lane.lane === "executor");
    expect(executorLane?.taskTitle).toBe("Stabilize worker event stream");
    expect(executorLane?.latestEventName).toBe("worker.assigned");
    expect(executorLane?.tone).toBe("warning");

    const reviewerLane = view.lanes.find((lane) => lane.lane === "reviewer");
    expect(reviewerLane?.blocked).toBe(true);
    expect(reviewerLane?.headline).toContain("Review blocked");

    const taskingLane = view.lanes.find((lane) => lane.lane === "tasking");
    expect(taskingLane?.eventCount).toBe(1);
    expect(taskingLane?.taskTitle).toBe("Stabilize worker event stream");
  });

  it("keeps deterministic lane ordering with tasking first", () => {
    const view = buildCodeOrchestrationReadModel(tasks, workers, workerEvents);
    expect(view.lanes.map((lane) => lane.lane)).toEqual(["tasking", "executor", "reviewer"]);
  });

  it("prefers the most operator-relevant active task as the focus task", () => {
    const focus = pickCodeFocusTask([
      ...tasks,
      {
        id: 14,
        tenant_id: 1,
        user_id: 7,
        workspace_id: 3,
        session_id: 19,
        title: "Verification gate",
        objective: "Wait for verification to complete.",
        scope: "code/orchestration",
        task_status: "verification_pending",
        priority: "normal",
        acceptance_criteria: [],
        created_at: "2026-04-10T05:08:00Z",
        updated_at: "2026-04-10T05:08:00Z",
      },
      {
        id: 15,
        tenant_id: 1,
        user_id: 7,
        workspace_id: 3,
        session_id: 19,
        title: "Reviewer pass",
        objective: "Active review in progress.",
        scope: "code/orchestration",
        task_status: "in_review",
        priority: "normal",
        acceptance_criteria: [],
        created_at: "2026-04-10T05:09:00Z",
        updated_at: "2026-04-10T05:09:00Z",
      },
    ]);

    expect(focus?.id).toBe(15);
  });
});
