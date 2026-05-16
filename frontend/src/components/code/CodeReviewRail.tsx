import { CheckCircle2, CornerDownLeft, GitPullRequestArrow, MessageSquareWarning } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { CardBody, CardHeader } from "@/components/ui/Card";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { translateText } from "@/lib/i18n";
import { CODE_LANE_EVENTS } from "@/lib/codeProtocol";
import { formatDateTime, formatRelativeTime } from "@/lib/utils";
import type { CodeOrchestrationSnapshot, CodeTask, CodeWorkerEvent } from "@/types/code";

interface CodeReviewRailProps {
  tasks?: CodeTask[];
  workerEvents?: CodeWorkerEvent[];
  orchestration?: CodeOrchestrationSnapshot;
}

function iconForEvent(eventName: string) {
  switch (eventName) {
    case CODE_LANE_EVENTS.reviewAccepted:
      return <CheckCircle2 className="h-4 w-4 text-emerald-300" />;
    case CODE_LANE_EVENTS.reviewRejected:
      return <MessageSquareWarning className="h-4 w-4 text-amber-300" />;
    case CODE_LANE_EVENTS.reviewRequested:
      return <GitPullRequestArrow className="h-4 w-4 text-sky-300" />;
    default:
      return <CornerDownLeft className="h-4 w-4 text-surface-400" />;
  }
}

function badgeVariantForEvent(event: CodeWorkerEvent) {
  if (event.severity === "error") return "danger";
  if (event.severity === "warning") return "warning";
  if (event.severity === "success") return "success";
  if (event.event_name === CODE_LANE_EVENTS.reviewPacketReady) return "brand";
  return "info";
}

export function CodeReviewRail({ tasks, workerEvents, orchestration }: CodeReviewRailProps) {
  const taskById = new Map((tasks ?? []).map((task) => [task.id, task]));
  const focusTaskId = orchestration?.focus_task_id ?? null;
  const reviewEventNames = new Set<string>([
    CODE_LANE_EVENTS.reviewRequested,
    CODE_LANE_EVENTS.reviewPacketReady,
    CODE_LANE_EVENTS.reviewAccepted,
    CODE_LANE_EVENTS.reviewRejected,
  ]);
  const reviewEvents = (workerEvents ?? [])
    .filter((event) => reviewEventNames.has(event.event_name))
    .sort((a, b) => {
      const aFocus = a.task_id === focusTaskId ? 1 : 0;
      const bFocus = b.task_id === focusTaskId ? 1 : 0;
      if (aFocus !== bFocus) return bFocus - aFocus;
      return b.id - a.id;
    })
    .slice(0, 8);

  function buildReviewCopy(event: CodeWorkerEvent): string {
    if (event.headline && event.summary && event.headline.trim() !== event.summary.trim()) {
      return event.summary;
    }
    if (event.headline) {
      return event.headline;
    }
    switch (event.event_name) {
      case CODE_LANE_EVENTS.reviewRequested:
        return translateText("Review requested and waiting for reviewer pickup.");
      case CODE_LANE_EVENTS.reviewPacketReady:
        return translateText("Executor prepared a structured reviewer-ready handoff packet.");
      case CODE_LANE_EVENTS.reviewAccepted:
        return translateText("Reviewer accepted the handoff; verification is next.");
      case CODE_LANE_EVENTS.reviewRejected:
        return translateText("Reviewer asked for changes before verification.");
      default:
        return event.summary ?? event.event_name;
    }
  }

  return (
    <CockpitPanel className="p-5 lg:p-6">
      <CardHeader
        title={translateText("Review Rail")}
        description={translateText("Reviewer decisions stay visible here as a calm margin note, so the thread can stay central while critique remains traceable.")}
        action={<Badge variant="info">{reviewEvents.length} {translateText("events")}</Badge>}
      />
      <CardBody className="space-y-3">
        {reviewEvents.length ? (
          reviewEvents.map((event) => {
            const task = event.task_id ? taskById.get(event.task_id) : undefined;
            const isFocus = focusTaskId !== null && event.task_id === focusTaskId;
            return (
              <div key={event.id} className="assistant-thread-shell rounded-2xl border border-white/8 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    {iconForEvent(event.event_name)}
                    <div>
                      <p className="text-sm font-medium text-white">
                        {task?.title ?? `${translateText("Task")} #${event.task_id ?? "?"}`}
                      </p>
                      <p className="mt-1 text-xs text-surface-500">
                        {buildReviewCopy(event)}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap justify-end gap-2">
                    {isFocus ? <Badge variant="brand">{translateText("focus")}</Badge> : <Badge variant="neutral">{translateText("history")}</Badge>}
                    <Badge variant={badgeVariantForEvent(event)}>
                      {event.event_name.replace("review.", "")}
                    </Badge>
                    {event.phase ? <Badge variant="neutral">{event.phase}</Badge> : null}
                    {event.failure_class ? <Badge variant="warning">{event.failure_class}</Badge> : null}
                  </div>
                </div>
                {event.event_name === CODE_LANE_EVENTS.reviewRejected ? (
                  <div className="mt-3 rounded-xl border border-amber-400/10 bg-amber-500/10 px-3 py-3 text-xs text-amber-100">
                    <p>{translateText("Reason code")}: {String(event.payload.reason_code ?? "n/a")}</p>
                    <p className="mt-1">{translateText("Reason")}: {String(event.payload.reason ?? "n/a")}</p>
                    {event.recommended_actions?.length ? (
                      <div className="mt-2 space-y-1">
                        <p className="font-medium">{translateText("Next actions")}</p>
                        {event.recommended_actions.map((item, index) => (
                          <p key={`${event.id}-next-${index}`}>- {item}</p>
                        ))}
                      </div>
                    ) : null}
                    {Array.isArray(event.payload.checklist) && event.payload.checklist.length ? (
                      <div className="mt-2 space-y-1">
                        {(event.payload.checklist as string[]).map((item, index) => (
                          <p key={`${event.id}-review-check-${index}`}>- {item}</p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {event.event_name === CODE_LANE_EVENTS.reviewPacketReady ? (
                  <div className="mt-3 rounded-xl border border-sky-400/10 bg-sky-500/10 px-3 py-3 text-xs text-sky-100">
                    <p>{translateText("Completed slices")}: {String(event.payload.completed_runs ?? 0)}</p>
                    <p className="mt-1">{translateText("Failed slices")}: {String(event.payload.failed_runs ?? 0)}</p>
                    <p className="mt-1">{translateText("Recommendation")}: {String(event.payload.review_recommendation ?? "n/a")}</p>
                    {event.recommended_actions?.length ? (
                      <div className="mt-2 space-y-1">
                        <p className="font-medium">{translateText("Operator actions")}</p>
                        {event.recommended_actions.map((item, index) => (
                          <p key={`${event.id}-operator-${index}`}>- {item}</p>
                        ))}
                      </div>
                    ) : null}
                    {Array.isArray(event.payload.slice_summaries) && event.payload.slice_summaries.length ? (
                      <div className="mt-2 space-y-1">
                        {(event.payload.slice_summaries as Array<Record<string, unknown>>).map((item, index) => (
                          <p key={`${event.id}-packet-${index}`}>
                            - {String(item.criterion ?? "slice")} / {String(item.status ?? "unknown")} / {String(item.summary ?? "")}
                          </p>
                        ))}
                      </div>
                    ) : null}
                    {Array.isArray(event.payload.review_checklist) && event.payload.review_checklist.length ? (
                      <div className="mt-2 space-y-1">
                        <p className="font-medium">{translateText("Checklist")}</p>
                        {(event.payload.review_checklist as string[]).map((item, index) => (
                          <p key={`${event.id}-review-check-${index}`}>- {item}</p>
                        ))}
                      </div>
                    ) : null}
                    {Array.isArray(event.payload.recovery_checklist) && event.payload.recovery_checklist.length ? (
                      <div className="mt-2 space-y-1">
                        <p className="font-medium">{translateText("Recovery")}</p>
                        {(event.payload.recovery_checklist as string[]).map((item, index) => (
                          <p key={`${event.id}-recovery-check-${index}`}>- {item}</p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                <p className="mt-3 text-[11px] uppercase tracking-[0.18em] text-surface-500">
                  {formatRelativeTime(event.created_at ?? "")} / {formatDateTime(event.created_at)}
                </p>
              </div>
            );
          })
        ) : (
          <div className="rounded-2xl border border-white/8 bg-surface-950/50 px-4 py-4 text-sm leading-6 text-surface-400">
            {translateText("No review rounds yet. The first reviewer note will appear here as soon as the thread leaves execution.")}
          </div>
        )}
      </CardBody>
    </CockpitPanel>
  );
}
