import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CodeContextRail } from "@/components/code/CodeContextRail";
import { CodeAlwaysOnPanel } from "@/components/code/CodeAlwaysOnPanel";
import { CodeRecoveryPanel } from "@/components/code/CodeRecoveryPanel";
import { CodeRuntimeHud } from "@/components/code/CodeRuntimeHud";
import { CodeStatusBand } from "@/components/code/CodeStatusBand";

describe("Code runtime components", () => {
  it("renders runtime HUD with provider issue and explicit action", () => {
    const html = renderToStaticMarkup(
      <CodeRuntimeHud
        status="blocked"
        providerIssue={{
          kind: "provider_error",
          title: "Prompt Interrupted",
          message: "The prompt may have landed in the wrong runtime surface.",
          retryAfterSeconds: null,
          recommendedActions: ["Reset the session back to ready-for-prompt."],
        }}
        actionLabel="Reset runtime"
        onAction={() => undefined}
      />,
    );

    expect(html).toContain("Prompt Interrupted");
    expect(html).toContain("Reset runtime");
    expect(html).toContain("ready-for-prompt");
  });

  it("renders recovery panel with recovery action button", () => {
    const html = renderToStaticMarkup(
      <CodeRecoveryPanel
        recovery={{
          session_id: 1,
          status: "needs_recovery",
          failure_class: "prompt_delivery",
          headline: "The session appears recoverable without changing code.",
          recommended_actions: [
            "Reset the session back to ready-for-prompt.",
            "Resend the intended prompt after the runtime posture stabilizes.",
          ],
          next_safe_action: "reset_session_ready",
          blocking_reasons: ["prompt_delivery"],
          evidence: { recovery_mode: "soft_reset_available" },
        }}
        actionLabel="Reset runtime"
        onAction={() => undefined}
      />,
    );

    expect(html).toContain("The session appears recoverable without changing code.");
    expect(html).toContain("Reset runtime");
    expect(html).toContain("prompt_delivery");
    expect(html).toContain("reset_session_ready");
  });

  it("renders full recovery provenance after an automation action runs", () => {
    const html = renderToStaticMarkup(
      <CodeRecoveryPanel
        recovery={{
          session_id: 1,
          status: "needs_recovery",
          failure_class: "verification_failed",
          headline: "Verification failed and requires a targeted follow-up.",
          recommended_actions: ["Inspect the failing verification stage and its log excerpt."],
          next_safe_action: "run_verification",
          blocking_reasons: ["verification_failed"],
          evidence: { failed_verification_stage: "lint" },
        }}
        result={{
          workspace_id: 1,
          session_id: 1,
          executed_action: "run_verification",
          execution_status: "completed",
          summary: "Automation executed the verification pipeline.",
          executed_at: "2026-04-17T18:10:00+08:00",
          resulting_session_status: "blocked",
          resulting_verification_status: "failed",
          snapshot: {} as never,
        }}
        actionLabel="Run verification"
        onAction={() => undefined}
      />,
    );

    expect(html).toContain("Last recovery result");
    expect(html).toContain("run_verification");
    expect(html).toContain("completed");
    expect(html).toContain("session blocked");
    expect(html).toContain("verification failed");
    expect(html).toContain("Automation executed the verification pipeline.");
  });

  it("renders the latest run artifact from runtime metrics", () => {
    const html = renderToStaticMarkup(
      <CodeAlwaysOnPanel
        runtime={{
          workspace_id: 7,
          runtime_state: {
            id: 1,
            workspace_id: 7,
            heartbeat_enabled: true,
            memory_enabled: true,
            reflections_enabled: true,
            last_heartbeat_decision: "run",
            last_heartbeat_at: "2026-04-16T17:20:00+08:00",
            last_memory_sync_at: null,
            last_reflection_at: null,
            last_compressed_turn_index: null,
            runtime_metrics: {
              last_run_ledger_artifact: {
                slice: "Task #12: Batch 101 signal review",
                outcome: "Verification passed and the task is now complete.",
                target_surface: "signal_lab",
                target_id: "101",
                target_route: "/bos/signal-lab?batchId=101",
                recorded_at: "2026-04-16T17:20:00+08:00",
              },
            },
            created_at: null,
            updated_at: null,
          },
          automation_jobs: [],
          active_subagents: [],
          pending_reflections: 0,
        }}
        reflections={[]}
        skills={[]}
      />,
    );

    expect(html).toContain("Latest run artifact");
    expect(html).toContain("Task #12: Batch 101 signal review");
    expect(html).toContain("Verification passed and the task is now complete.");
    expect(html).toContain("surface signal_lab");
    expect(html).toContain("target 101");
    expect(html).toContain("/bos/signal-lab?batchId=101");
  });

  it("renders maintenance summary from runtime metrics", () => {
    const html = renderToStaticMarkup(
      <CodeAlwaysOnPanel
        runtime={{
          workspace_id: 7,
          runtime_state: {
            id: 1,
            workspace_id: 7,
            heartbeat_enabled: true,
            memory_enabled: true,
            reflections_enabled: true,
            last_heartbeat_decision: "run",
            last_heartbeat_at: "2026-04-16T17:20:00+08:00",
            last_memory_sync_at: null,
            last_reflection_at: null,
            last_compressed_turn_index: null,
            runtime_metrics: {
              last_maintenance_summary: "Maintenance refreshed project memory and staged autonomy reports.",
              last_maintenance_generated_at: "2026-04-16T18:00:00+08:00",
              last_maintenance_report_markdown_path: "reports/runtime-staging/autonomy-maintenance-latest.md",
              last_maintenance_project_brain_path: "reports/runtime-staging/project-brain.md",
              last_maintenance_decision_journal_path: "reports/runtime-staging/decision-journal.md",
              last_maintenance_evolution_log_path: "reports/runtime-staging/evolution-log.md",
              next_autonomy_mode: "idle_maintenance",
              next_autonomy_objective: "Run idle BOS maintenance and inspect the highest-value optimization.",
              last_seeded_autonomy_task_id: 42,
              last_seeded_autonomy_at: "2026-04-16T18:05:00+08:00",
              last_reflection_verified_signal: false,
              last_reflection_verification_signals: ["recent_verification_failed", "task_blocked"],
            },
            created_at: null,
            updated_at: null,
          },
          automation_jobs: [],
          active_subagents: [],
          pending_reflections: 0,
        }}
        reflections={[]}
        skills={[]}
      />,
    );

    expect(html).toContain("Maintenance");
    expect(html).toContain("Maintenance refreshed project memory and staged autonomy reports.");
    expect(html).toContain("reports/runtime-staging/project-brain.md");
    expect(html).toContain("reports/runtime-staging/autonomy-maintenance-latest.md");
    expect(html).toContain("next autonomy");
    expect(html).toContain("idle_maintenance");
    expect(html).toContain("Run idle BOS maintenance and inspect the highest-value optimization.");
    expect(html).toContain("seeded task");
    expect(html).toContain("#42");
    expect(html).toContain("memory only");
    expect(html).toContain("recent_verification_failed");
  });

  it("renders heartbeat loop posture and reflection verification signals", () => {
    const html = renderToStaticMarkup(
      <CodeAlwaysOnPanel
        runtime={{
          workspace_id: 7,
          runtime_state: {
            id: 1,
            workspace_id: 7,
            heartbeat_enabled: true,
            memory_enabled: true,
            reflections_enabled: true,
            last_heartbeat_decision: "run",
            last_heartbeat_at: "2026-04-16T17:20:00+08:00",
            last_memory_sync_at: null,
            last_reflection_at: "2026-04-16T18:00:00+08:00",
            last_compressed_turn_index: null,
            runtime_metrics: {
              last_heartbeat_focus_task_title: "Verification-sensitive task",
              last_heartbeat_planner_recommendation: "run_verification",
              last_heartbeat_risk_level: "high",
              last_heartbeat_loop_budget: "deep",
              last_heartbeat_convergence_signal: "needs_more_evidence",
              last_heartbeat_difficulty_signals: ["verification_history_negative", "review_history_negative"],
            },
            created_at: null,
            updated_at: null,
          },
          automation_jobs: [],
          active_subagents: [],
          pending_reflections: 0,
        }}
        reflections={[
          {
            id: 5,
            workspace_id: 7,
            session_id: 9,
            task_id: 11,
            skill_id: null,
            trigger_source: "manual",
            reflection_status: "completed",
            output_kind: "memory_update",
            summary: "Stored a BOS Code memory snapshot only; recent work is not verified enough to promote into a skill yet.",
            payload: {
              verified_signal: false,
              verification_signals: ["recent_verification_failed", "task_blocked"],
            },
            created_at: null,
            updated_at: null,
            skill: null,
          },
        ]}
        skills={[]}
      />,
    );

    expect(html).toContain("loop deep");
    expect(html).toContain("convergence needs_more_evidence");
    expect(html).toContain("Difficulty signals");
    expect(html).toContain("verification_history_negative");
    expect(html).toContain("memory only");
    expect(html).toContain("task_blocked");
  });

  it("renders recovery state in the status band", () => {
    const html = renderToStaticMarkup(
      <CodeStatusBand
        workspaceStatus={{
          workspace: {
            id: 1,
            tenant_id: 1,
            repo_root: "repo",
            worktree_root: "worktree",
            base_branch: "main",
            default_branch: "main",
            active_branch: "boscode/tenant-1/session-1",
            workspace_status: "ready",
            base_commit: null,
            head_commit: null,
            dirty_state: false,
            created_at: null,
            updated_at: null,
            lease: null,
          },
          lease: null,
          can_write: true,
          permission_mode: "workspace-write",
          latest_event_time: null,
        }}
        activeSession={{
          id: 7,
          tenant_id: 1,
          user_id: 1,
          workspace_id: 1,
          provider: "openai",
          model: "gpt-5.4-mini",
          permission_mode: "workspace-write",
          title: null,
          session_branch: "boscode/tenant-1/session-7",
          session_status: "running",
          verification_status: "failed",
          token_usage: null,
          estimated_cost: null,
          created_at: null,
          updated_at: null,
        }}
        orchestration={{
          workspace_id: 1,
          latest_event_time: null,
          verification_gate: "failed",
          merge_readiness: "blocked",
          operator_posture: "recovery_required",
          operator_actions: [],
          operator_action_policies: {},
          automation_actions: [],
          human_actions: [],
          review_gated_actions: [],
          automation_ready: false,
          automation_blockers: [],
          automation_summary: null,
          next_automation_action: null,
          next_human_action: null,
          operator_action_classes: {},
          merge_blockers: ["verification_failed"],
          merge_summary: "Merge is blocked because verification failed.",
          merge_next_action: "run_verification",
          merge_evidence: [],
          heartbeat_status: "run",
          heartbeat_summary: null,
          reflection_posture: "active",
          focus_task_id: 11,
          focus_task_title: "Verification recovery task",
          focus_task_status: "running",
          focus_task_headline: "Recovery task 11 is running in autonomy mode.",
          totals: {
            tasks: 3,
            workers: 3,
            running_tasks: 1,
            blocked_tasks: 1,
            completed_tasks: 0,
            active_lanes: 1,
            blocked_lanes: 1,
          },
          lanes: [],
        }}
        runtime={{
          workspace_id: 1,
          runtime_state: {
            id: 1,
            workspace_id: 1,
            heartbeat_enabled: true,
            memory_enabled: true,
            reflections_enabled: true,
            last_heartbeat_decision: "run",
            last_heartbeat_at: null,
            last_memory_sync_at: null,
            last_reflection_at: null,
            last_compressed_turn_index: null,
            runtime_metrics: {
              last_recovery_task_id: 11,
              last_recovery_failure_class: "verification_failed",
            },
            created_at: null,
            updated_at: null,
          },
          automation_jobs: [],
          active_subagents: [],
          pending_reflections: 0,
        }}
        sessionDetail={undefined}
        events={[]}
      />,
    );

    expect(html).toContain("recovery");
    expect(html).toContain("Recovery task #11 / verification_failed");
  });

  it("renders recovery loop activity in the context rail", () => {
    const html = renderToStaticMarkup(
      <CodeContextRail
        activeSession={null}
        orchestration={undefined}
        runtime={{
          workspace_id: 1,
          runtime_state: {
            id: 1,
            workspace_id: 1,
            heartbeat_enabled: true,
            memory_enabled: true,
            reflections_enabled: true,
            last_heartbeat_decision: "run",
            last_heartbeat_at: null,
            last_memory_sync_at: null,
            last_reflection_at: null,
            last_compressed_turn_index: null,
            runtime_metrics: {
              last_recovery_task_id: 21,
              last_recovery_failure_class: "subagent_recovery",
              last_recovery_task_at: "2026-04-17T08:00:00+08:00",
            },
            created_at: null,
            updated_at: null,
          },
          automation_jobs: [],
          active_subagents: [],
          pending_reflections: 0,
        }}
        branchState={undefined}
        readiness={undefined}
        recovery={undefined}
        verification={undefined}
        mcpSummary={undefined}
        runningVerification={false}
        refreshingBranch={false}
        runningAutomation={false}
        onRunVerification={() => undefined}
        onRefreshBranch={() => undefined}
        onRunAutomation={() => undefined}
      />,
    );

    expect(html).toContain("Recovery loop active");
    expect(html).toContain("subagent_recovery");
    expect(html).toContain("#21");
  });

  it("renders provider backpressure in the always-on panel", () => {
    const html = renderToStaticMarkup(
      <CodeAlwaysOnPanel
        runtime={{
          workspace_id: 9,
          runtime_state: {
            id: 1,
            workspace_id: 9,
            heartbeat_enabled: true,
            memory_enabled: true,
            reflections_enabled: true,
            last_heartbeat_decision: "run",
            last_heartbeat_at: null,
            last_memory_sync_at: null,
            last_reflection_at: null,
            last_compressed_turn_index: null,
            runtime_metrics: {
              provider_pause_until: "2026-04-17T08:30:00+08:00",
              last_provider_failure_class: "provider_cooldown",
              provider_backpressure_count: 3,
            },
            created_at: null,
            updated_at: null,
          },
          automation_jobs: [],
          active_subagents: [],
          pending_reflections: 0,
        }}
        reflections={[]}
        skills={[]}
      />,
    );

    expect(html).toContain("Provider backpressure");
    expect(html).toContain("provider_cooldown");
    expect(html).toContain("count 3");
  });

  it("renders workflow orchestration and experience quality", () => {
    const html = renderToStaticMarkup(
      <CodeAlwaysOnPanel
        runtime={{
          workspace_id: 12,
          runtime_state: {
            id: 1,
            workspace_id: 12,
            heartbeat_enabled: true,
            memory_enabled: true,
            reflections_enabled: true,
            last_heartbeat_decision: "run",
            last_heartbeat_at: null,
            last_memory_sync_at: null,
            last_reflection_at: null,
            last_compressed_turn_index: null,
            runtime_metrics: {
              workflow_mode: "recovery",
              workflow_skills: ["gstack-bos-director", "tbc-autonomy-loop", "bos-systematic-debugging"],
              workflow_rationale: ["Recovery evidence is active, so debugging and verification gating should lead."],
              experience_quality: {
                posture: "emerging",
                score: 3,
                notes: ["Project brain contains durable context beyond the default scaffold."],
              },
            },
            created_at: null,
            updated_at: null,
          },
          automation_jobs: [],
          active_subagents: [],
          pending_reflections: 0,
        }}
        reflections={[]}
        skills={[]}
      />,
    );

    expect(html).toContain("Workflow orchestrator");
    expect(html).toContain("recovery");
    expect(html).toContain("bos-systematic-debugging");
    expect(html).toContain("Experience quality");
    expect(html).toContain("emerging");
    expect(html).toContain("score 3");
  });
});
