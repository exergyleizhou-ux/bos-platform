import { AlertTriangle, CheckCircle2, CircleDashed, Info, Lock, Wrench } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { translateText } from "@/lib/i18n";
import { getLatestProviderIssue } from "@/lib/codeProviderUi";
import { formatDateTime } from "@/lib/utils";
import type { CodeEvent, CodeSessionDetail } from "@/types/code";

interface CodeSessionTimelineProps {
  sessionDetail?: CodeSessionDetail;
  events: CodeEvent[];
  streamConnected: boolean;
}

const EVENT_CONTRACT_KEYS = new Set([
  "blocking",
  "degraded_scope",
  "event_data_version",
  "failure_class",
  "headline",
  "phase",
  "recommended_action",
  "recommended_actions",
  "severity",
]);

function workerEventHeadline(event: CodeEvent) {
  if (typeof event.payload.headline === "string" && event.payload.headline.trim()) {
    return event.payload.headline.trim();
  }
  return event.event_type.replace(/[._]/g, " ").trim();
}

function workerEventSeverity(event: CodeEvent) {
  const severity = event.payload.severity;
  if (severity === "warning" || severity === "error" || severity === "success" || severity === "info") {
    return severity;
  }
  if (event.event_type.includes("failed")) return "error";
  if (event.event_type.includes("completed")) return "success";
  return "info";
}

function workerEventIcon(event: CodeEvent) {
  if (event.event_type.includes("denied")) {
    return <Lock className="h-4 w-4 text-amber-300" />;
  }

  switch (workerEventSeverity(event)) {
    case "error":
      return <AlertTriangle className="h-4 w-4 text-red-300" />;
    case "warning":
      return <AlertTriangle className="h-4 w-4 text-amber-300" />;
    case "success":
      return <CheckCircle2 className="h-4 w-4 text-emerald-300" />;
    default:
      return event.event_type.includes("tool") ? (
        <Wrench className="h-4 w-4 text-sky-300" />
      ) : event.event_type.includes("completed") ? (
        <CheckCircle2 className="h-4 w-4 text-emerald-300" />
      ) : event.event_type.includes("failed") ? (
        <AlertTriangle className="h-4 w-4 text-red-300" />
      ) : event.event_type.includes("progress") ? (
        <CircleDashed className="h-4 w-4 text-sky-300" />
      ) : (
        <Info className="h-4 w-4 text-surface-400" />
      );
  }
}

function workerEventTone(event: CodeEvent) {
  switch (workerEventSeverity(event)) {
    case "error":
      return "border-red-400/12 bg-red-500/10";
    case "warning":
      return "border-amber-400/12 bg-amber-500/10";
    case "success":
      return "border-emerald-400/12 bg-emerald-500/10";
    default:
      return "border-white/8 bg-white/4";
  }
}

function workerEventRecommendedActions(event: CodeEvent) {
  const recommended = event.payload.recommended_actions;
  if (Array.isArray(recommended)) {
    return recommended.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
  }
  return [];
}

function workerEventDetailPayload(event: CodeEvent) {
  return Object.fromEntries(Object.entries(event.payload).filter(([key]) => !EVENT_CONTRACT_KEYS.has(key)));
}

function sessionEventSummary(event: CodeEvent) {
  const payloadSummary = event.payload.summary;
  if (typeof payloadSummary === "string" && payloadSummary.trim()) {
    return payloadSummary.trim();
  }
  return translateText("Structured session event recorded.");
}

export function CodeSessionTimeline({
  sessionDetail,
  events,
  streamConnected,
}: CodeSessionTimelineProps) {
  const providerIssue = getLatestProviderIssue(sessionDetail, events);
  return (
    <Card className="h-full min-h-[36rem]">
      <CardHeader
        title={translateText("Session Timeline")}
        description={translateText(streamConnected ? "Replay-aware stream attached." : "Polling timeline state.")}
        action={<Badge variant={streamConnected ? "success" : "warning"} dot>{translateText(streamConnected ? "streaming" : "degraded")}</Badge>}
      />
      <CardBody className="space-y-3">
        {providerIssue ? (
          <div className="rounded-2xl border border-amber-400/12 bg-amber-500/10 p-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-300" />
              <p className="text-sm font-medium text-amber-100">{providerIssue.title}</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-amber-50/90">{providerIssue.message}</p>
          </div>
        ) : null}
        {sessionDetail?.turns.map((turn) => (
          <div key={turn.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <p className="text-[11px] uppercase tracking-[0.22em] text-surface-500">{translateText("Prompt")} {turn.turn_index}</p>
            <p className="mt-2 text-sm text-white">{turn.user_message}</p>
            {turn.assistant_summary ? (
              <p className="mt-3 text-sm text-surface-300">{turn.assistant_summary}</p>
            ) : null}
          </div>
        ))}

        {sessionDetail?.tool_calls.map((toolCall) => (
          <div key={toolCall.id} className="rounded-2xl border border-white/8 bg-surface-950/55 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Wrench className="h-4 w-4 text-sky-300" />
                <p className="text-sm font-medium text-white">{toolCall.tool_name}</p>
                <Badge variant="info">{toolCall.tool_class}</Badge>
              </div>
              <Badge
                variant={
                  toolCall.was_denied ? "warning" : toolCall.exit_code && toolCall.exit_code !== 0 ? "danger" : "success"
                }
                dot
              >
                {translateText(toolCall.was_denied ? "denied" : toolCall.exit_code && toolCall.exit_code !== 0 ? "failed" : "finished")}
              </Badge>
            </div>
            {toolCall.input_summary ? (
              <p className="mt-2 text-xs text-surface-400">{toolCall.input_summary}</p>
            ) : null}
            {toolCall.result_summary ? (
              <p className="mt-2 text-sm text-surface-300">{toolCall.result_summary}</p>
            ) : null}
          </div>
        ))}

        {events.map((event) => (
          <div key={event.id} className={`flex gap-3 rounded-2xl border p-3 ${workerEventTone(event)}`}>
            <div className="mt-0.5">
              {workerEventIcon(event)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="neutral">#{event.seq_no}</Badge>
                <p className="truncate text-sm font-medium text-white">{workerEventHeadline(event)}</p>
                {"phase" in event.payload && typeof event.payload.phase === "string" ? (
                  <Badge variant="info">{String(event.payload.phase)}</Badge>
                ) : null}
                {"failure_class" in event.payload && typeof event.payload.failure_class === "string" ? (
                  <Badge variant="warning">{String(event.payload.failure_class)}</Badge>
                ) : null}
                {"degraded_scope" in event.payload && typeof event.payload.degraded_scope === "string" ? (
                  <Badge variant="neutral">{String(event.payload.degraded_scope)}</Badge>
                ) : null}
                {event.payload.blocking ? <Badge variant="danger">{translateText("blocking")}</Badge> : null}
              </div>
              <p className="mt-2 text-sm leading-6 text-surface-100">
                {sessionEventSummary(event)}
              </p>
              {workerEventRecommendedActions(event).length ? (
                <div className="mt-3 space-y-2">
                  {workerEventRecommendedActions(event).slice(0, 2).map((action, index) => (
                    <div
                      key={`${event.id}-action-${index}`}
                      className="rounded-2xl border border-white/8 bg-surface-950/40 px-3 py-2 text-xs text-surface-200"
                    >
                      {action}
                    </div>
                  ))}
                </div>
              ) : null}
              {Object.keys(workerEventDetailPayload(event)).length ? (
                <details className="mt-3">
                  <summary className="cursor-pointer text-[11px] uppercase tracking-[0.18em] text-surface-500">
                    {translateText("Event payload")}
                  </summary>
                  <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs text-surface-400">
                    {JSON.stringify(workerEventDetailPayload(event), null, 2)}
                  </pre>
                </details>
              ) : null}
              <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-surface-500">
                {event.event_type} / {formatDateTime(event.created_at)}
              </p>
            </div>
          </div>
        ))}
      </CardBody>
    </Card>
  );
}
