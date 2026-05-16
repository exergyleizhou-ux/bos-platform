import type { CodeProviderIssue } from "@/lib/codeProviderUi";
import type { CodeAutomationExecutionResponse } from "@/types/code";

export function runtimeStatusVariant(status?: string | null): "brand" | "info" | "warning" | "success" | "danger" | "neutral" {
  switch (status) {
    case "ready_for_prompt":
    case "ready":
    case "completed":
      return "success";
    case "prompt_accepted":
    case "running":
    case "created":
      return "brand";
    case "spawning":
      return "info";
    case "trust_required":
    case "blocked":
      return "warning";
    case "failed":
    case "cancelled":
      return "danger";
    default:
      return "neutral";
  }
}

export function runtimeStatusLabel(status?: string | null) {
  switch (status) {
    case "created":
      return "new";
    case "spawning":
      return "spawning";
    case "ready_for_prompt":
      return "ready for prompt";
    case "prompt_accepted":
      return "prompt accepted";
    case "trust_required":
      return "trust gate";
    case "running":
      return "live";
    case "ready":
      return "ready";
    case "blocked":
      return "attention";
    case "completed":
      return "settled";
    default:
      return status ?? "idle";
  }
}

export function runtimeBody(status?: string | null, providerIssue?: CodeProviderIssue | null) {
  if (providerIssue?.message) return providerIssue.message;
  switch (status) {
    case "spawning":
      return "The runtime is still booting and preparing the first usable session surface.";
    case "ready_for_prompt":
      return "The runtime handshake is complete and the session is ready for the next prompt.";
    case "prompt_accepted":
      return "The prompt has been accepted and queued for provider dispatch.";
    case "running":
      return "The provider is actively working through the current turn.";
    case "trust_required":
      return "A trust gate still needs resolution before the session can safely accept prompts.";
    case "blocked":
      return "The session is blocked. Clear the latest runtime issue before assuming the thread can continue.";
    default:
      return "The deeper evidence trail stays available below whenever you want to inspect it.";
  }
}

export function runtimeNextAction(status?: string | null, providerIssue?: CodeProviderIssue | null) {
  if (providerIssue?.recommendedActions?.[0]) return providerIssue.recommendedActions[0];
  switch (status) {
    case "ready_for_prompt":
      return "Send the next prompt whenever you want BOS Code to move.";
    case "prompt_accepted":
    case "running":
      return "Let the current turn settle before redirecting the thread.";
    case "spawning":
      return "Wait for the runtime handshake before treating the thread as ready.";
    case "trust_required":
      return "Resolve the trust gate before sending more work.";
    case "blocked":
      return "Inspect the latest runtime issue before retrying.";
    default:
      return null;
  }
}

export function runtimeIssueVariant(issue?: CodeProviderIssue | null): "warning" | "danger" | "neutral" {
  if (!issue) return "neutral";
  return issue.kind === "provider_cooldown" || issue.kind === "trust_required" ? "warning" : "danger";
}

export function scopedRecoveryResultSummary(
  execution: CodeAutomationExecutionResponse | undefined,
  sessionId: number | null,
) {
  if (!execution) return null;
  if (execution.session_id !== sessionId) return null;
  return execution.summary;
}

export function scopedAutomationAction(
  automationReady: boolean | undefined,
  nextAutomationAction: string | null | undefined,
  currentSessionId: number | null,
  targetSessionId: number | null,
) {
  if (!automationReady) return null;
  if (!nextAutomationAction) return null;
  if (currentSessionId === null || targetSessionId === null) return null;
  if (currentSessionId !== targetSessionId) return null;
  return nextAutomationAction;
}
