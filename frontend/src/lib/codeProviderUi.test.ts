import { describe, expect, it } from "vitest";

import { getLatestProviderIssue } from "@/lib/codeProviderUi";
import type { CodeEvent, CodeSessionDetail } from "@/types/code";

function makeSessionDetail(): CodeSessionDetail {
  return {
    session: {
      id: 1,
      tenant_id: 1,
      user_id: 1,
      workspace_id: 1,
      provider: "openai",
      model: "gpt-5.4-mini",
      permission_mode: "read-only",
      title: "Runtime thread",
      session_branch: "boscode/tenant-1/session-1",
      session_status: "blocked",
      verification_status: "pending",
      token_usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2 },
      estimated_cost: 0,
      created_at: "2026-04-15T00:00:00Z",
      updated_at: "2026-04-15T00:00:00Z",
    },
    workspace: {
      id: 1,
      tenant_id: 1,
      repo_root: ".",
      worktree_root: ".",
      base_branch: "main",
      default_branch: "main",
      active_branch: "main",
      workspace_status: "ready",
      base_commit: null,
      head_commit: null,
      dirty_state: false,
      created_at: "2026-04-15T00:00:00Z",
      updated_at: "2026-04-15T00:00:00Z",
      lease: null,
    },
    lease: null,
    turns: [],
    tool_calls: [],
    latest_event: null,
    memory_snapshots: [],
    reflection_runs: [],
    subagent_runs: [],
  };
}

function makeEvent(payload: Record<string, unknown>, event_type = "code.session.failed"): CodeEvent {
  return {
    id: 1,
    session_id: 1,
    seq_no: 1,
    event_type,
    payload,
    idempotency_key: null,
    request_id: null,
    created_at: "2026-04-15T00:00:01Z",
  };
}

describe("codeProviderUi", () => {
  it("surfaces trust required from the latest session status event", () => {
    const issue = getLatestProviderIssue(makeSessionDetail(), [
      makeEvent(
        {
          session_status: "trust_required",
          headline: "A trust gate must be cleared before the session can continue.",
          recommended_actions: ["Resolve the trust gate before sending more work."],
        },
        "code.session.status",
      ),
    ]);

    expect(issue?.kind).toBe("trust_required");
    expect(issue?.recommendedActions?.[0]).toContain("trust gate");
  });

  it("surfaces prompt delivery failures from structured session failure payloads", () => {
    const issue = getLatestProviderIssue(makeSessionDetail(), [
      makeEvent({
        failure_class: "prompt_delivery",
        headline: "The prompt may have landed in the wrong runtime surface.",
        recommended_actions: ["Reset the session back to ready-for-prompt."],
        reason: "prompt_misdelivery",
      }),
    ]);

    expect(issue?.kind).toBe("provider_error");
    expect(issue?.title).toBe("Prompt Interrupted");
    expect(issue?.recommendedActions?.[0]).toContain("ready-for-prompt");
  });

  it("preserves cooldown semantics including retry delay", () => {
    const issue = getLatestProviderIssue(makeSessionDetail(), [
      makeEvent({
        reason: "provider_cooldown",
        user_message: "The model pool is cooling down right now.",
        retry_after_seconds: 3600,
        recommended_actions: ["Wait for the cooldown window, then retry the prompt."],
      }),
    ]);

    expect(issue?.kind).toBe("provider_cooldown");
    expect(issue?.retryAfterSeconds).toBe(3600);
  });
});
