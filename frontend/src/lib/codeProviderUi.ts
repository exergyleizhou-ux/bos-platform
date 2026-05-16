import type { CodeEvent, CodeSessionDetail } from "@/types/code";

export type CodeProviderIssueKind = "provider_cooldown" | "provider_error" | "trust_required";

export interface CodeProviderIssue {
  kind: CodeProviderIssueKind;
  title: string;
  message: string;
  retryAfterSeconds: number | null;
  recommendedActions: string[];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function formatRetryAfter(seconds: number | null): string | null {
  if (seconds === null || seconds <= 0) return null;

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (hours > 0 && minutes > 0) {
    return `about ${hours}h ${minutes}m`;
  }
  if (hours > 0) {
    return `about ${hours}h`;
  }
  if (minutes > 0) {
    return `about ${minutes}m`;
  }
  return "under 1 minute";
}

export function getLatestProviderIssue(sessionDetail?: CodeSessionDetail, events: CodeEvent[] = []): CodeProviderIssue | null {
  const latestStatusEvent = [...events]
    .reverse()
    .find((event) => event.event_type === "code.session.status");
  const latestFailedEvent = [...events]
    .reverse()
    .find((event) => event.event_type === "code.session.failed");

  const statusPayload = asRecord(latestStatusEvent?.payload);
  const payload = asRecord(latestFailedEvent?.payload);
  const reason = typeof payload?.reason === "string" ? payload.reason : null;
  const userMessage = typeof payload?.user_message === "string" ? payload.user_message : null;
  const retryAfterSeconds =
    typeof payload?.retry_after_seconds === "number" ? payload.retry_after_seconds : null;
  const recommendedActions = Array.isArray(payload?.recommended_actions)
    ? payload?.recommended_actions.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
  const statusRecommendedActions = Array.isArray(statusPayload?.recommended_actions)
    ? statusPayload?.recommended_actions.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
  const statusHeadline = typeof statusPayload?.headline === "string" ? statusPayload.headline : null;
  const statusValue = typeof statusPayload?.session_status === "string" ? statusPayload.session_status : null;
  const failureClass = typeof payload?.failure_class === "string" ? payload.failure_class : null;

  const latestFailedTurn = [...(sessionDetail?.turns ?? [])]
    .reverse()
    .find((turn) => turn.turn_status === "failed" && turn.assistant_summary);

  if (statusValue === "trust_required") {
    return {
      kind: "trust_required" as const,
      title: "Trust Required",
      message: statusHeadline ?? "A trust gate must be cleared before the session can continue.",
      retryAfterSeconds: null,
      recommendedActions: statusRecommendedActions,
    };
  }

  if (reason === "provider_cooldown") {
    const retryAfterLabel = formatRetryAfter(retryAfterSeconds);
    return {
      kind: "provider_cooldown" as const,
      title: retryAfterLabel ? `Model Cooldown · ${retryAfterLabel}` : "Model Cooldown",
      message: retryAfterLabel
        ? `${userMessage ?? "The model pool is cooling down right now."} Estimated recovery: ${retryAfterLabel}.`
        : userMessage ?? "The model pool is cooling down right now. Try again a little later.",
      retryAfterSeconds,
      recommendedActions,
    };
  }

  if (failureClass || payload) {
    return {
      kind: "provider_error" as const,
      title: failureClass === "prompt_delivery" ? "Prompt Interrupted" : "Provider Error",
      message:
        (typeof payload?.headline === "string" ? payload.headline : null) ??
        userMessage ??
        "The session hit a provider-side failure.",
      retryAfterSeconds,
      recommendedActions,
    };
  }

  if (latestFailedTurn?.assistant_summary) {
    return {
      kind: "provider_error" as const,
      title: "Provider Error",
      message: latestFailedTurn.assistant_summary,
      retryAfterSeconds: null,
      recommendedActions: [],
    };
  }

  return null;
}
