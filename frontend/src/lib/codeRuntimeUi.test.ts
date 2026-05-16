import { describe, expect, it } from "vitest";

import { formatCodeActionCallToAction } from "@/lib/codeActionPolicy";
import {
  scopedAutomationAction,
  runtimeBody,
  runtimeIssueVariant,
  runtimeNextAction,
  runtimeStatusLabel,
  runtimeStatusVariant,
  scopedRecoveryResultSummary,
} from "@/lib/codeRuntimeUi";

describe("codeRuntimeUi", () => {
  it("maps handshake statuses into stable badge variants and labels", () => {
    expect(runtimeStatusVariant("ready_for_prompt")).toBe("success");
    expect(runtimeStatusVariant("trust_required")).toBe("warning");
    expect(runtimeStatusVariant("running")).toBe("brand");
    expect(runtimeStatusLabel("prompt_accepted")).toBe("prompt accepted");
    expect(runtimeStatusLabel("blocked")).toBe("attention");
  });

  it("prefers provider issue messaging over generic runtime body", () => {
    expect(
      runtimeBody("blocked", {
        kind: "provider_error",
        title: "Provider Error",
        message: "The upstream provider returned an unexpected response.",
        retryAfterSeconds: null,
        recommendedActions: ["Inspect provider health."],
      }),
    ).toContain("upstream provider");
  });

  it("derives next actions and issue variants for runtime recovery", () => {
    expect(runtimeNextAction("ready_for_prompt", null)).toContain("Send the next prompt");
    expect(
      runtimeNextAction("blocked", {
        kind: "trust_required",
        title: "Trust Required",
        message: "A trust gate must be cleared.",
        retryAfterSeconds: null,
        recommendedActions: ["Resolve the trust gate before sending more work."],
      }),
    ).toContain("trust gate");
    expect(
      runtimeIssueVariant({
        kind: "provider_cooldown",
        title: "Cooldown",
        message: "Cooling down.",
        retryAfterSeconds: 30,
        recommendedActions: [],
      }),
    ).toBe("warning");
  });

  it("formats friendly CTA labels for automation-safe runtime actions", () => {
    expect(formatCodeActionCallToAction("reset_session_ready")).toBe("Reset runtime");
    expect(formatCodeActionCallToAction("run_verification")).toBe("Run verification");
  });

  it("scopes recovery result summaries to the active session", () => {
    expect(
      scopedRecoveryResultSummary(
        {
          workspace_id: 1,
          session_id: 7,
          executed_action: "reset_session_ready",
          execution_status: "completed",
          summary: "Automation reset the session back to ready-for-prompt.",
          executed_at: "2026-04-17T00:00:00Z",
          snapshot: {} as never,
        },
        7,
      ),
    ).toContain("ready-for-prompt");
    expect(
      scopedRecoveryResultSummary(
        {
          workspace_id: 1,
          session_id: 7,
          executed_action: "reset_session_ready",
          execution_status: "completed",
          summary: "Automation reset the session back to ready-for-prompt.",
          executed_at: "2026-04-17T00:00:00Z",
          snapshot: {} as never,
        },
        8,
      ),
    ).toBeNull();
  });

  it("only exposes automation actions for the targeted session", () => {
    expect(scopedAutomationAction(true, "reset_session_ready", 7, 7)).toBe("reset_session_ready");
    expect(scopedAutomationAction(true, "reset_session_ready", 7, 8)).toBeNull();
    expect(scopedAutomationAction(false, "reset_session_ready", 7, 7)).toBeNull();
  });
});
