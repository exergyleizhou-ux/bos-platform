import type { CodeActionPolicy } from "@/types/code";

export function formatCodeAction(action: string): string {
  return action.replace(/_/g, " ");
}

export function formatCodeActionCallToAction(action: string): string {
  switch (action) {
    case "reset_session_ready":
      return "Reset runtime";
    case "refresh_branch":
      return "Refresh branch";
    case "run_verification":
      return "Run verification";
    case "inspect_context":
      return "Inspect context";
    case "inspect_diff":
      return "Inspect diff";
    default:
      return `Run ${formatCodeAction(action)}`;
  }
}

export function resolveCodeActionPolicy(
  action: string,
  policies?: Record<string, CodeActionPolicy | string> | null,
): CodeActionPolicy {
  const policy = policies?.[action];
  if (
    policy === "automation_safe" ||
    policy === "human_only" ||
    policy === "review_gated"
  ) {
    return policy;
  }
  return "human_only";
}

export function formatCodeActionPolicy(policy?: string | null): string {
  switch (policy) {
    case "automation_safe":
      return "automation safe";
    case "review_gated":
      return "review gated";
    case "human_only":
    default:
      return "human only";
  }
}

export function codeActionPolicyBadgeVariant(
  policy?: string | null,
): "neutral" | "info" | "warning" {
  switch (policy) {
    case "automation_safe":
      return "info";
    case "review_gated":
      return "warning";
    default:
      return "neutral";
  }
}
