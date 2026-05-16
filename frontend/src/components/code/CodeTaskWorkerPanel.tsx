import { ClipboardList, GitMerge, Users2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { translateText } from "@/lib/i18n";
import {
  codeActionPolicyBadgeVariant,
  formatCodeAction,
  formatCodeActionPolicy,
  resolveCodeActionPolicy,
} from "@/lib/codeActionPolicy";
import { buildCodeOrchestrationReadModel } from "@/lib/code-orchestration-read-model";
import { CODE_LANES, CODE_LANE_EVENTS, CODE_TASK_STATUSES, CODE_WORKER_STATUSES } from "@/lib/codeProtocol";
import { formatDateTime, formatRelativeTime } from "@/lib/utils";
import type { CodeOrchestrationSnapshot, CodeTask, CodeTaskArchitectPlanResponse, CodeTaskPacket, CodeWorker, CodeWorkerEvent } from "@/types/code";

interface CodeTaskWorkerPanelProps {
  tasks?: CodeTask[];
  workers?: CodeWorker[];
  workerEvents?: CodeWorkerEvent[];
  orchestration?: CodeOrchestrationSnapshot;
  streamConnected: boolean;
  creating: boolean;
  onCreateTask: (title: string, objective: string, acceptanceCriteria: string[], taskPacket: CodeTaskPacket) => void;
  assigning: boolean;
  updating: boolean;
  plannerDrafts?: Record<number, CodeTaskArchitectPlanResponse>;
  onArchitectPlan: (taskId: number) => void;
  onArchitectRoute: (taskId: number, acceptanceCriteria: string[]) => void;
  onRequestReview: (taskId: number) => void;
  onBeginReview: (taskId: number) => void;
  onAcceptReview: (taskId: number) => void;
  onRejectReview: (taskId: number, reason: string, reasonCode: string, checklist: string[]) => void;
  onMarkWorkerReady: (workerName: string) => void;
  onMarkWorkerBlocked: (workerName: string) => void;
}

function workerVariant(status?: string): "success" | "warning" | "danger" | "neutral" | "info" {
  switch (status) {
    case CODE_WORKER_STATUSES.readyForPrompt:
    case CODE_WORKER_STATUSES.ready:
    case CODE_WORKER_STATUSES.completed:
      return "success";
    case CODE_WORKER_STATUSES.spawning:
      return "info";
    case CODE_WORKER_STATUSES.assigned:
    case CODE_WORKER_STATUSES.promptAccepted:
    case CODE_WORKER_STATUSES.waitingReview:
    case CODE_TASK_STATUSES.reviewPending:
    case CODE_TASK_STATUSES.inReview:
      return "info";
    case CODE_WORKER_STATUSES.running:
    case CODE_WORKER_STATUSES.blocked:
    case CODE_WORKER_STATUSES.trustRequired:
      return "warning";
    case CODE_WORKER_STATUSES.failed:
      return "danger";
    default:
      return "neutral";
  }
}

function laneVariant(lane: string): "brand" | "info" | "warning" | "neutral" {
  switch (lane) {
    case CODE_LANES.tasking:
      return "brand";
    case CODE_LANES.architect:
      return "info";
    case CODE_LANES.executor:
      return "warning";
    case CODE_LANES.reviewer:
      return "neutral";
    default:
      return "neutral";
  }
}

export function CodeTaskWorkerPanel({
  tasks,
  workers,
  workerEvents,
  orchestration,
  streamConnected,
  creating,
  onCreateTask,
  assigning,
  updating,
  plannerDrafts,
  onArchitectPlan,
  onArchitectRoute,
  onRequestReview,
  onBeginReview,
  onAcceptReview,
  onRejectReview,
  onMarkWorkerReady,
  onMarkWorkerBlocked,
}: CodeTaskWorkerPanelProps) {
  const [title, setTitle] = useState(translateText("Prepare next engineering slice"));
  const [objective, setObjective] = useState(translateText("Coordinate the next BOS Code implementation objective."));
  const [acceptanceCriteria, setAcceptanceCriteria] = useState(
    translateText("- Route through architect before implementation") +
      "\n" +
      translateText("- Reviewer accepts implementation") +
      "\n" +
      translateText("- Verification gate passes"),
  );
  const defaultTaskPacket: CodeTaskPacket = {
    objective,
    scope: "code/orchestration",
    repo: "canonical BOS repository worktree",
    branch_policy: "Use the active session branch and refresh branch posture before merge decisions.",
    acceptance_tests: acceptanceCriteria
      .split("\n")
      .map((item) => item.replace(/^-\s*/, "").trim())
      .filter(Boolean),
    commit_policy: "Keep changes scoped and reviewer-friendly before handoff.",
    reporting_contract: "Return a concise implementation summary, changed surfaces, verification posture, and next review action.",
    escalation_policy: "Escalate only when scope, access, or safety becomes ambiguous.",
  };
  const [rejectReasonByTask, setRejectReasonByTask] = useState<Record<number, string>>({});
  const [rejectReasonCodeByTask, setRejectReasonCodeByTask] = useState<Record<number, string>>({});
  const [rejectChecklistByTask, setRejectChecklistByTask] = useState<Record<number, string>>({});

  const derivedOrchestration = useMemo(
    () => buildCodeOrchestrationReadModel(tasks ?? [], workers ?? [], workerEvents ?? []),
    [tasks, workers, workerEvents],
  );
  const snapshot = orchestration ?? derivedOrchestration;
  const recentEventsByLane = useMemo(() => {
    const grouped = new Map<string, CodeWorkerEvent[]>();
    (workerEvents ?? []).forEach((event) => {
      const current = grouped.get(event.lane) ?? [];
      current.push(event);
      grouped.set(
        event.lane,
        current.sort((a, b) => b.id - a.id).slice(0, 4),
      );
    });
    return grouped;
  }, [workerEvents]);

  const taskById = useMemo(
    () => new Map((tasks ?? []).map((task) => [task.id, task])),
    [tasks],
  );

  return (
    <Card className="border-rose-400/15 bg-rose-500/5">
      <CardHeader
        title={translateText("Task / Worker Lanes")}
        description={translateText("Lane-aware orchestration state with replayable worker events.")}
        action={
          <Badge variant={streamConnected ? "success" : "warning"} dot>
            {translateText(streamConnected ? "lane stream live" : "lane stream polling")}
          </Badge>
        }
      />
      <CardBody className="space-y-4">
        <div className="rounded-2xl border border-white/8 bg-surface-950/60 p-4">
          <Input
            label="Task title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
          <div className="mt-3">
            <Textarea
              label="Objective"
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
              autoResize
            />
          </div>
          <div className="mt-3">
            <Textarea
              label="Acceptance Criteria"
              value={acceptanceCriteria}
              onChange={(event) => setAcceptanceCriteria(event.target.value)}
              autoResize
            />
          </div>
          <div className="mt-3 flex justify-end">
            <Button
              size="sm"
              loading={creating}
              onClick={() =>
                onCreateTask(
                  title,
                  objective,
                  acceptanceCriteria
                    .split("\n")
                    .map((item) => item.replace(/^-\s*/, "").trim())
                    .filter(Boolean),
                  defaultTaskPacket,
                )
              }
            >
              {translateText("Create Task")}
            </Button>
          </div>
        </div>

        <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
          <div className="flex items-center gap-2">
            <ClipboardList className="h-4 w-4 text-rose-300" />
            <p className="text-sm font-medium text-white">{translateText("Tasks")} ({tasks?.length ?? 0})</p>
          </div>
          <div className="mt-3 space-y-2">
            {tasks?.length ? (
              tasks.map((task) => (
                <div key={task.id} className="rounded-xl border border-white/8 bg-white/4 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-white">{task.title}</p>
                    <Badge variant="brand">{translateText(task.task_status)}</Badge>
                  </div>
                  <p className="mt-2 text-xs text-surface-400">{task.objective}</p>
                  {task.acceptance_criteria?.length ? (
                    <div className="mt-3 rounded-xl border border-white/6 bg-surface-950/45 p-3">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">{translateText("Acceptance Criteria")}</p>
                      <div className="mt-2 space-y-1">
                        {(task.acceptance_criteria as string[]).map((criterion, index) => (
                          <p key={`${task.id}-criterion-${index}`} className="text-xs text-surface-300">
                            - {criterion}
                          </p>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {plannerDrafts?.[task.id] ? (
                    <div className="mt-3 rounded-xl border border-sky-400/10 bg-sky-500/10 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-sky-100">{translateText("Architect Draft")}</p>
                        <Badge variant="info">{plannerDrafts[task.id].route_to}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-sky-50/90">{plannerDrafts[task.id].plan_summary}</p>
                    </div>
                  ) : null}
                  <div className="mt-3 flex flex-wrap justify-end gap-2">
                    {task.task_status === CODE_TASK_STATUSES.created ? (
                      <>
                        <Button
                          size="sm"
                          variant="ghost"
                          loading={assigning}
                          onClick={() => onArchitectPlan(task.id)}
                        >
                          {translateText("Draft with architect")}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          loading={assigning}
                          onClick={() => onArchitectRoute(task.id, (task.acceptance_criteria as string[]) ?? [])}
                        >
                          {translateText("Route with architect")}
                        </Button>
                      </>
                    ) : null}
                    {task.task_status === CODE_TASK_STATUSES.running ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={updating}
                        onClick={() => onRequestReview(task.id)}
                      >
                        {translateText("Send to review")}
                      </Button>
                    ) : null}
                    {task.task_status === CODE_TASK_STATUSES.reviewPending ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={updating}
                        onClick={() => onBeginReview(task.id)}
                      >
                        {translateText("Begin review")}
                      </Button>
                    ) : null}
                    {task.task_status === CODE_TASK_STATUSES.inReview ? (
                      <>
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={updating}
                          onClick={() => onAcceptReview(task.id)}
                        >
                          {translateText("Record review acceptance")}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          loading={updating}
                          onClick={() =>
                            onRejectReview(
                              task.id,
                              rejectReasonByTask[task.id] ?? "",
                              rejectReasonCodeByTask[task.id] ?? "",
                              (rejectChecklistByTask[task.id] ?? "")
                                .split("\n")
                                .map((item) => item.replace(/^-\s*/, "").trim())
                                .filter(Boolean),
                            )
                          }
                        >
                          {translateText("Record changes requested")}
                        </Button>
                        <div className="w-full space-y-2 rounded-xl border border-white/8 bg-surface-950/45 p-3">
                          <Input
                            label="Reject Code"
                            value={rejectReasonCodeByTask[task.id] ?? ""}
                            onChange={(event) =>
                              setRejectReasonCodeByTask((current) => ({
                                ...current,
                                [task.id]: event.target.value,
                              }))
                            }
                            placeholder={translateText("missing-verification")}
                          />
                          <Textarea
                            label="Reject Reason"
                            value={rejectReasonByTask[task.id] ?? ""}
                            onChange={(event) =>
                              setRejectReasonByTask((current) => ({
                                ...current,
                                [task.id]: event.target.value,
                              }))
                            }
                            autoResize
                          />
                          <Textarea
                            label="Checklist"
                            value={rejectChecklistByTask[task.id] ?? ""}
                            onChange={(event) =>
                              setRejectChecklistByTask((current) => ({
                                ...current,
                                [task.id]: event.target.value,
                              }))
                            }
                            placeholder={`${translateText("- Re-run verification")}\n${translateText("- Update lane schema")}`}
                            autoResize
                          />
                        </div>
                      </>
                    ) : null}
                  </div>
                  <div className="mt-3 rounded-xl border border-white/6 bg-surface-950/45 p-3">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">{translateText("Task Audit Trail")}</p>
                    <div className="mt-2 space-y-2">
                      {(workerEvents ?? [])
                        .filter((event) => event.task_id === task.id)
                        .slice(0, 4)
                        .map((event) => (
                          <div key={event.id} className="rounded-lg border border-white/6 bg-white/4 px-3 py-2">
                            <div className="flex items-center justify-between gap-3">
                              <div className="flex items-center gap-2">
                                <Badge variant={laneVariant(event.lane)}>{event.lane}</Badge>
                                <p className="text-xs font-medium text-white">{event.event_name}</p>
                              </div>
                              <p className="text-[11px] text-surface-500">{formatDateTime(event.created_at)}</p>
                            </div>
                            {event.summary ? (
                              <p className="mt-1 text-xs text-surface-300">{event.summary}</p>
                            ) : null}
                            {event.event_name === CODE_LANE_EVENTS.reviewRejected ? (
                              <div className="mt-2 rounded-md border border-amber-400/10 bg-amber-500/10 px-2 py-2 text-xs text-amber-100">
                                <p>{translateText("Code")}: {String(event.payload.reason_code ?? "n/a")}</p>
                                <p className="mt-1">{translateText("Reason")}: {String(event.payload.reason ?? "n/a")}</p>
                                {Array.isArray(event.payload.checklist) && event.payload.checklist.length ? (
                                  <div className="mt-1 space-y-1">
                                    {(event.payload.checklist as string[]).map((item, index) => (
                                      <p key={`${event.id}-check-${index}`}>- {item}</p>
                                    ))}
                                  </div>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                        ))}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-surface-400">{translateText("No tasks yet.")}</p>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
          <div className="flex items-center gap-2">
            <Users2 className="h-4 w-4 text-rose-300" />
            <p className="text-sm font-medium text-white">{translateText("Workers")} ({workers?.length ?? 0})</p>
          </div>
          <div className="mt-3 space-y-2">
            {workers?.length ? (
              workers.map((worker) => {
                const beginReviewAction = worker.allowed_actions?.find((action) => action === "begin_review") ?? null;
                const markBlockedAction = worker.allowed_actions?.find((action) => action.endsWith("_blocked")) ?? null;
                const markReadyAction = worker.allowed_actions?.find((action) => action.endsWith("_ready")) ?? null;
                const workerTask = worker.task_id ? taskById.get(worker.task_id) ?? null : null;

                return (
                  <div key={worker.id} className="rounded-xl border border-white/8 bg-white/4 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium capitalize text-white">{worker.worker_name}</p>
                      <Badge variant={workerVariant(worker.worker_status)} dot>
                        {translateText(worker.worker_status)}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-surface-400">
                      {worker.worker_role}
                      {worker.last_event_summary ? ` / ${worker.last_event_summary}` : ""}
                    </p>
                    {(worker.allowed_actions?.length ?? 0) > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {worker.allowed_actions.map((action) => {
                          const actionPolicy = resolveCodeActionPolicy(action, worker.allowed_action_policies);
                          return (
                            <div
                              key={`${worker.worker_name}-${action}`}
                              className="flex items-center gap-2"
                              data-testid="worker-action-chip"
                              data-worker-name={worker.worker_name}
                              data-action-name={action}
                              data-action-policy={actionPolicy}
                            >
                              <Badge variant="neutral">{formatCodeAction(action)}</Badge>
                              <Badge variant={codeActionPolicyBadgeVariant(actionPolicy)}>
                                {formatCodeActionPolicy(actionPolicy)}
                              </Badge>
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                    <div className="mt-3 flex justify-end">
                      <div className="flex flex-wrap gap-2">
                        {beginReviewAction && worker.task_id ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            loading={updating}
                            data-testid={`worker-action-button-${worker.worker_name}-begin_review`}
                            data-action-name={beginReviewAction}
                            data-action-policy={resolveCodeActionPolicy(beginReviewAction, worker.allowed_action_policies)}
                            onClick={() => onBeginReview(worker.task_id!)}
                          >
                            {translateText("Begin review")}
                          </Button>
                        ) : null}
                        {markBlockedAction ? (
                          <Button
                            size="sm"
                            variant="outline"
                            loading={updating}
                            data-testid={`worker-action-button-${worker.worker_name}-mark_blocked`}
                            data-action-name={markBlockedAction}
                            data-action-policy={resolveCodeActionPolicy(
                              markBlockedAction,
                              worker.allowed_action_policies,
                            )}
                            onClick={() => onMarkWorkerBlocked(worker.worker_name)}
                          >
                            {translateText("Mark blocked")}
                          </Button>
                        ) : null}
                        {markReadyAction ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            loading={updating}
                            data-testid={`worker-action-button-${worker.worker_name}-mark_ready`}
                            data-action-name={markReadyAction}
                            data-action-policy={resolveCodeActionPolicy(
                              markReadyAction,
                              worker.allowed_action_policies,
                            )}
                            onClick={() => onMarkWorkerReady(worker.worker_name)}
                          >
                            {translateText("Mark ready")}
                          </Button>
                        ) : null}
                      </div>
                    </div>
                    {workerTask ? (
                      <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-surface-500">
                        {translateText("task")} #{workerTask.id}: {translateText(workerTask.task_status)}
                      </p>
                    ) : null}
                  </div>
                );
              })
            ) : (
              <p className="text-sm text-surface-400">{translateText("No workers yet.")}</p>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
          <div className="flex items-center gap-2">
            <GitMerge className="h-4 w-4 text-rose-300" />
            <p className="text-sm font-medium text-white">
              {translateText("Lane Timeline")} ({workerEvents?.length ?? 0})
            </p>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl border border-white/8 bg-surface-950/55 p-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">{translateText("Running Tasks")}</p>
              <p className="mt-2 text-lg font-semibold text-white">
                {"running_tasks" in snapshot.totals ? snapshot.totals.running_tasks : snapshot.totals.runningTasks}
              </p>
            </div>
            <div className="rounded-xl border border-white/8 bg-surface-950/55 p-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">{translateText("Blocked Tasks")}</p>
              <p className="mt-2 text-lg font-semibold text-white">
                {"blocked_tasks" in snapshot.totals ? snapshot.totals.blocked_tasks : snapshot.totals.blockedTasks}
              </p>
            </div>
            <div className="rounded-xl border border-white/8 bg-surface-950/55 p-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">{translateText("Active Lanes")}</p>
              <p className="mt-2 text-lg font-semibold text-white">
                {"active_lanes" in snapshot.totals ? snapshot.totals.active_lanes : snapshot.totals.activeLanes}
              </p>
            </div>
            <div className="rounded-xl border border-white/8 bg-surface-950/55 p-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">{translateText("Latest Lane Event")}</p>
              <p className="mt-2 text-sm font-semibold text-white">
                {("latest_event_time" in snapshot ? snapshot.latest_event_time : snapshot.latestEventAt)
                  ? formatRelativeTime(("latest_event_time" in snapshot ? snapshot.latest_event_time : snapshot.latestEventAt) ?? "")
                  : translateText("No events")}
              </p>
            </div>
          </div>
          <div className="mt-3 space-y-3">
            {snapshot.lanes.length ? (
              snapshot.lanes.map((lane) => {
                return (
                  <div key={lane.lane} className="rounded-xl border border-white/8 bg-surface-950/55 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Badge variant={laneVariant(lane.lane)}>{lane.lane}</Badge>
                        <p className="text-sm font-medium text-white">
                          {("latest_event_name" in lane ? lane.latest_event_name : lane.latestEventName) ?? lane.headline}
                        </p>
                      </div>
                      <Badge variant={lane.tone === "brand" ? "brand" : (lane.tone as "success" | "warning" | "danger" | "neutral" | "info" | "brand")} dot>
                        {translateText(("latest_status" in lane ? lane.latest_status : lane.latestStatus) ?? "idle")}
                      </Badge>
                    </div>
                    <p className="mt-2 text-xs text-surface-300">{lane.headline}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {("task_title" in lane ? lane.task_title : lane.taskTitle) ? (
                        <Badge variant="info">{"task_title" in lane ? lane.task_title : lane.taskTitle}</Badge>
                      ) : null}
                      {("worker_role" in lane ? lane.worker_role : lane.workerRole) ? (
                        <Badge variant="neutral">{"worker_role" in lane ? lane.worker_role : lane.workerRole}</Badge>
                      ) : null}
                      <Badge variant="neutral">{"event_count" in lane ? lane.event_count : lane.eventCount} {translateText("events")}</Badge>
                      {lane.primary_action ? (
                        <div
                          className="flex items-center gap-2"
                          data-testid={`lane-primary-action-${lane.lane}`}
                          data-lane-name={lane.lane}
                          data-action-name={lane.primary_action}
                          data-action-policy={
                            "primary_action_policy" in lane && lane.primary_action_policy
                              ? lane.primary_action_policy
                              : "human_only"
                          }
                        >
                          <Badge variant="brand">{translateText("primary")}: {formatCodeAction(lane.primary_action)}</Badge>
                          <Badge
                            variant={codeActionPolicyBadgeVariant(
                              "primary_action_policy" in lane
                                ? lane.primary_action_policy
                                : null,
                            )}
                          >
                            {formatCodeActionPolicy(
                              "primary_action_policy" in lane
                                ? lane.primary_action_policy
                                : null,
                            )}
                          </Badge>
                        </div>
                      ) : null}
                      {("next_automation_action" in lane ? lane.next_automation_action : null) ? (
                        <div
                          className="flex items-center gap-2"
                          data-testid={`lane-automation-next-${lane.lane}`}
                          data-lane-name={lane.lane}
                          data-next-automation-action={lane.next_automation_action}
                          data-automation-ready={
                            "automation_ready" in lane && lane.automation_ready ? "true" : "false"
                          }
                        >
                          <Badge variant={"automation_ready" in lane && lane.automation_ready ? "info" : "warning"}>
                            {translateText("auto next")}: {formatCodeAction(lane.next_automation_action as string)}
                          </Badge>
                        </div>
                      ) : null}
                    </div>
                    {(lane.lane_actions?.length ?? 0) > 0 ? (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {lane.lane_actions.map((action) => {
                          const actionPolicy = resolveCodeActionPolicy(
                            action,
                            "lane_action_policies" in lane ? lane.lane_action_policies : null,
                          );
                          return (
                            <div
                              key={`${lane.lane}-${action}`}
                              className="flex items-center gap-2"
                              data-testid="lane-action-chip"
                              data-lane-name={lane.lane}
                              data-action-name={action}
                              data-action-policy={actionPolicy}
                            >
                              <Badge variant="neutral">{formatCodeAction(action)}</Badge>
                              <Badge variant={codeActionPolicyBadgeVariant(actionPolicy)}>
                                {formatCodeActionPolicy(actionPolicy)}
                              </Badge>
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                    {(("automation_actions" in lane ? lane.automation_actions.length : 0) > 0 ||
                      ("review_gated_actions" in lane ? lane.review_gated_actions.length : 0) > 0 ||
                      ("human_actions" in lane ? lane.human_actions.length : 0) > 0) ? (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {("automation_actions" in lane ? lane.automation_actions.length : 0) > 0 ? (
                          <Badge variant="info">
                            {translateText("auto")}: {"automation_actions" in lane ? lane.automation_actions.length : 0}
                          </Badge>
                        ) : null}
                        {("human_actions" in lane ? lane.human_actions.length : 0) > 0 ? (
                          <Badge variant="neutral">
                            {translateText("human")}: {"human_actions" in lane ? lane.human_actions.length : 0}
                          </Badge>
                        ) : null}
                        {("review_gated_actions" in lane ? lane.review_gated_actions.length : 0) > 0 ? (
                          <Badge variant="warning">
                            {translateText("review gated")}: {"review_gated_actions" in lane ? lane.review_gated_actions.length : 0}
                          </Badge>
                        ) : null}
                      </div>
                    ) : null}
                    {("automation_summary" in lane ? lane.automation_summary : null) ? (
                      <p className="mt-2 text-xs text-surface-400">
                        {"automation_summary" in lane ? lane.automation_summary : null}
                      </p>
                    ) : null}
                    {(("automation_blockers" in lane ? lane.automation_blockers.length : 0) > 0) ? (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {("automation_blockers" in lane ? lane.automation_blockers : []).map((blocker) => (
                          <Badge key={`${lane.lane}-${blocker}`} variant="warning">
                            {blocker}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                    <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-surface-500">
                      {("latest_event_at" in lane ? lane.latest_event_at : lane.latestEventAt)
                        ? formatRelativeTime(("latest_event_at" in lane ? lane.latest_event_at : lane.latestEventAt) ?? "")
                        : translateText("Awaiting events")}
                    </p>

                    {(recentEventsByLane.get(lane.lane)?.length ?? 0) > 0 ? (
                      <div className="mt-3 space-y-2 border-t border-white/8 pt-3">
                        {(recentEventsByLane.get(lane.lane) ?? []).map((event) => (
                          <div key={event.id} className="rounded-lg border border-white/6 bg-white/4 px-3 py-2">
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-xs font-medium text-white">{event.event_name}</p>
                              <p className="text-[11px] text-surface-500">{formatDateTime(event.created_at)}</p>
                            </div>
                            {event.summary ? (
                              <p className="mt-1 text-xs text-surface-400">{event.summary}</p>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                );
              })
            ) : (
              <p className="text-sm text-surface-400">{translateText("No lane events yet.")}</p>
            )}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
