import type { CodeTask, CodeWorker, CodeWorkerEvent } from "@/types/code";

export type CodeLaneTone = "success" | "warning" | "danger" | "neutral" | "info" | "brand";

export interface CodeLaneReadModel {
  lane: string;
  workerName: string | null;
  workerRole: string | null;
  workerStatus: string | null;
  taskId: number | null;
  taskTitle: string | null;
  taskStatus: string | null;
  latestEventId: number | null;
  latestEventName: string | null;
  latestStatus: string | null;
  latestSummary: string | null;
  latestEventAt: string | null;
  eventCount: number;
  blocked: boolean;
  tone: CodeLaneTone;
  headline: string;
  lane_actions: string[];
  lane_action_policies: Record<string, string>;
  automation_actions: string[];
  human_actions: string[];
  review_gated_actions: string[];
  automation_ready: boolean;
  automation_blockers: string[];
  automation_summary: string | null;
  next_automation_action: string | null;
  primary_action: string | null;
  primary_action_policy: string | null;
  recentEvents: CodeWorkerEvent[];
}

export interface CodeOrchestrationReadModel {
  totals: {
    tasks: number;
    workers: number;
    runningTasks: number;
    blockedTasks: number;
    completedTasks: number;
    activeLanes: number;
    blockedLanes: number;
  };
  latestEventAt: string | null;
  lanes: CodeLaneReadModel[];
}

const LANE_ORDER = ["tasking", "architect", "executor", "reviewer"];
const TASK_PRIORITY = ["in_review", "review_pending", "verification_pending", "running", "created", "blocked", "completed", "failed"];

function orderLane(a: string, b: string): number {
  const aIndex = LANE_ORDER.indexOf(a);
  const bIndex = LANE_ORDER.indexOf(b);
  if (aIndex !== -1 || bIndex !== -1) {
    if (aIndex === -1) return 1;
    if (bIndex === -1) return -1;
    return aIndex - bIndex;
  }
  return a.localeCompare(b);
}

function toTone(status?: string | null): CodeLaneTone {
  switch (status) {
    case "ready_for_prompt":
    case "ready":
    case "completed":
    case "merge_ready":
      return "success";
    case "spawning":
      return "info";
    case "in_review":
    case "review_pending":
    case "waiting_review":
    case "prompt_accepted":
      return "info";
    case "running":
    case "assigned":
    case "blocked":
    case "trust_required":
    case "pending":
    case "needs_recovery":
      return "warning";
    case "failed":
      return "danger";
    case "created":
      return "brand";
    default:
      return "neutral";
  }
}

function isBlockedStatus(status?: string | null): boolean {
  return status === "failed" || status === "blocked";
}

function taskPriority(task?: CodeTask | null): number {
  if (!task?.task_status) return TASK_PRIORITY.length;
  const index = TASK_PRIORITY.indexOf(task.task_status);
  return index === -1 ? TASK_PRIORITY.length : index;
}

export function pickCodeFocusTask(tasks: CodeTask[] = []): CodeTask | null {
  if (!tasks.length) return null;
  return tasks
    .slice()
    .sort((a, b) => {
      const priorityDelta = taskPriority(a) - taskPriority(b);
      if (priorityDelta !== 0) return priorityDelta;
      return b.id - a.id;
    })[0] ?? null;
}

function buildHeadline(args: {
  lane: string;
  latestEventName: string | null;
  latestSummary: string | null;
  taskTitle: string | null;
  workerStatus: string | null;
  taskStatus: string | null;
}): string {
  if (args.latestSummary) return args.latestSummary;
  if (args.taskTitle && args.workerStatus) {
    return `${args.taskTitle} / ${args.workerStatus}`;
  }
  if (args.taskTitle && args.taskStatus) {
    return `${args.taskTitle} / ${args.taskStatus}`;
  }
  if (args.latestEventName) return args.latestEventName;
  return `${args.lane} lane awaiting activity`;
}

export function buildCodeOrchestrationReadModel(
  tasks: CodeTask[] = [],
  workers: CodeWorker[] = [],
  workerEvents: CodeWorkerEvent[] = [],
): CodeOrchestrationReadModel {
  const taskById = new Map(tasks.map((task) => [task.id, task]));
  const workerById = new Map(workers.map((worker) => [worker.id, worker]));
  const focusTask = pickCodeFocusTask(tasks);
  const lanes = new Set<string>();

  workers.forEach((worker) => lanes.add(worker.worker_name));
  workerEvents.forEach((event) => lanes.add(event.lane));
  tasks.forEach(() => lanes.add("tasking"));

  const laneModels = [...lanes]
    .sort(orderLane)
    .map((lane) => {
      const laneEvents = workerEvents
        .filter((event) => event.lane === lane)
        .sort((a, b) => b.id - a.id);
      const latestEvent = laneEvents[0] ?? null;

      const worker =
        workers.find((item) => item.worker_name === lane) ??
        (latestEvent?.worker_id ? workerById.get(latestEvent.worker_id) ?? null : null);

      const task =
        (worker?.task_id ? taskById.get(worker.task_id) ?? null : null) ??
        (latestEvent?.task_id ? taskById.get(latestEvent.task_id) ?? null : null) ??
        (lane === "tasking" ? focusTask : null);

      const latestStatus =
        latestEvent?.status ??
        worker?.worker_status ??
        (lane === "tasking" ? task?.task_status : null) ??
        null;

      const blocked =
        isBlockedStatus(latestStatus) ||
        isBlockedStatus(worker?.worker_status) ||
        isBlockedStatus(task?.task_status);

      return {
        lane,
        workerName: worker?.worker_name ?? null,
        workerRole: worker?.worker_role ?? null,
        workerStatus: worker?.worker_status ?? null,
        taskId: task?.id ?? latestEvent?.task_id ?? null,
        taskTitle: task?.title ?? null,
        taskStatus: task?.task_status ?? null,
        latestEventId: latestEvent?.id ?? null,
        latestEventName: latestEvent?.event_name ?? null,
        latestStatus,
        latestSummary: latestEvent?.summary ?? null,
        latestEventAt: latestEvent?.created_at ?? null,
        eventCount: laneEvents.length,
        blocked,
        tone: blocked ? "danger" : toTone(latestStatus),
        headline: buildHeadline({
          lane,
          latestEventName: latestEvent?.event_name ?? null,
          latestSummary: latestEvent?.summary ?? null,
          taskTitle: task?.title ?? null,
          workerStatus: worker?.worker_status ?? null,
          taskStatus: task?.task_status ?? null,
        }),
        lane_actions: [],
        lane_action_policies: {},
        automation_actions: [],
        human_actions: [],
        review_gated_actions: [],
        automation_ready: false,
        automation_blockers: [],
        automation_summary: null,
        next_automation_action: null,
        primary_action: null,
        primary_action_policy: null,
        recentEvents: laneEvents.slice(0, 4),
      } satisfies CodeLaneReadModel;
    });

  return {
    totals: {
      tasks: tasks.length,
      workers: workers.length,
      runningTasks: tasks.filter((task) => task.task_status === "running").length,
      blockedTasks: tasks.filter((task) => task.task_status === "blocked").length,
      completedTasks: tasks.filter((task) => task.task_status === "completed").length,
      activeLanes: laneModels.filter((lane) => lane.latestStatus === "running").length,
      blockedLanes: laneModels.filter((lane) => lane.blocked).length,
    },
    latestEventAt:
      workerEvents.slice().sort((a, b) => b.id - a.id)[0]?.created_at ?? null,
    lanes: laneModels,
  };
}
