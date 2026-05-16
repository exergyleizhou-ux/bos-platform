import type { ReactNode } from "react";
import { Cpu, GitBranch, ShieldCheck, Sparkles } from "lucide-react";

import { CodeRuntimeHud } from "@/components/code/CodeRuntimeHud";
import { Badge } from "@/components/ui/Badge";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { translateText } from "@/lib/i18n";
import { getLatestProviderIssue } from "@/lib/codeProviderUi";
import { runtimeIssueVariant } from "@/lib/codeRuntimeUi";
import type { CodeEvent, CodeOrchestrationSnapshot, CodeRuntimeResponse, CodeWorkspaceStatus, CodeSession, CodeSessionDetail } from "@/types/code";

interface CodeStatusBandProps {
  workspaceStatus?: CodeWorkspaceStatus;
  activeSession?: CodeSession | null;
  orchestration?: CodeOrchestrationSnapshot;
  runtime?: CodeRuntimeResponse;
  sessionDetail?: CodeSessionDetail;
  events?: CodeEvent[];
}

function buildMergeSummary(orchestration?: CodeOrchestrationSnapshot): string {
  if (!orchestration) return translateText("Waiting for orchestration snapshot.");
  return orchestration.merge_summary;
}

export function CodeStatusBand({ workspaceStatus, activeSession, orchestration, runtime, sessionDetail, events }: CodeStatusBandProps) {
  const focusTaskSummary = orchestration?.focus_task_title
    ? `${orchestration.focus_task_title} / ${orchestration.focus_task_status ?? "unknown"}`
    : translateText("No active focus task");
  const providerIssue = getLatestProviderIssue(sessionDetail, events);
  const runtimeMetrics = runtime?.runtime_state.runtime_metrics;
  const recoveryTaskId = runtimeMetrics?.last_recovery_task_id as number | undefined;
  const recoveryFailureClass = runtimeMetrics?.last_recovery_failure_class as string | undefined;
  const recoveryCopy = recoveryTaskId
    ? `${translateText("Recovery task")} #${recoveryTaskId}${recoveryFailureClass ? ` / ${recoveryFailureClass}` : ""}`
    : null;

  return (
    <CockpitPanel className="space-y-4 p-6 lg:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="brand">{translateText(workspaceStatus?.workspace.workspace_status ?? "workspace idle")}</Badge>
        <Badge variant="info">{activeSession?.provider ?? "openai"}</Badge>
        <Badge variant="neutral">{activeSession?.model ?? "gpt-5.4-mini"}</Badge>
        {providerIssue ? (
          <Badge variant={runtimeIssueVariant(providerIssue)}>
            {translateText(
              providerIssue.kind === "provider_cooldown"
                ? "provider cooldown"
                : providerIssue.kind === "trust_required"
                  ? "trust required"
                  : "provider error",
            )}
          </Badge>
        ) : null}
        <Badge variant={orchestration?.verification_gate === "passed" ? "success" : "warning"}>
          {translateText("verification")} {translateText(orchestration?.verification_gate ?? activeSession?.verification_status ?? "pending")}
        </Badge>
        <Badge
          variant={
            orchestration?.merge_readiness === "merge_ready"
              ? "success"
              : orchestration?.merge_readiness === "blocked"
                ? "danger"
                : "warning"
          }
        >
          {translateText("merge")} {translateText(orchestration?.merge_readiness ?? "idle")}
        </Badge>
        {recoveryTaskId ? (
          <Badge variant="warning">
            {translateText("recovery")} #{recoveryTaskId}
          </Badge>
        ) : null}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr_0.8fr]">
        <NarrativeTile
          icon={<Cpu className="h-4 w-4" />}
          label={translateText("Workspace")}
          title={workspaceStatus?.workspace.active_branch ?? translateText("No active branch")}
          body={
            workspaceStatus?.lease?.lease_status === "active"
              ? translateText("A write lease is active, so this workspace is already in motion with a live engineering session.")
              : translateText("The workspace is open and ready for the next move.")
          }
        />
        <NarrativeTile
          icon={<ShieldCheck className="h-4 w-4" />}
          label={translateText("Progress")}
          title={
            orchestration
              ? focusTaskSummary
              : translateText("Awaiting snapshot")
          }
          body={recoveryCopy ? `${recoveryCopy}. ${orchestration?.focus_task_headline ?? buildMergeSummary(orchestration)}` : orchestration?.focus_task_headline ?? buildMergeSummary(orchestration)}
        />
        <NarrativeTile
          icon={<GitBranch className="h-4 w-4" />}
          label={translateText("Session")}
          title={activeSession ? `${translateText("Session")} #${activeSession.id}` : translateText("No active session")}
          body={
            activeSession
              ? orchestration?.focus_task_title
                ? `${translateText("Operator focus is currently")} ${orchestration.focus_task_title}. ${buildMergeSummary(orchestration)}`
                : translateText("The runtime posture stays visible below whenever you need to inspect it.")
              : translateText("Start a session whenever you want BOS Code to pick up the next orchestration cycle.")
          }
        />
      </div>

      {activeSession ? (
        <CodeRuntimeHud
          status={activeSession.session_status}
          providerIssue={providerIssue}
          label="Runtime"
        />
      ) : null}

      <div className="flex flex-wrap items-center gap-3 text-xs text-surface-400">
        <span className="inline-flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-brand-300" />
          {translateText("Conversation-first workspace, scientific control core intact")}
        </span>
        <span>{translateText("Tasks")}: {orchestration?.totals.tasks ?? 0}</span>
        <span>{translateText("Lanes")}: {orchestration?.totals.active_lanes ?? 0} {translateText("active")}</span>
        <span>{translateText("Lease")}: {translateText(workspaceStatus?.lease?.lease_status ?? "available")}</span>
        {orchestration?.merge_next_action ? <span>{translateText("Next")}: {translateText(orchestration.merge_next_action)}</span> : null}
        {recoveryCopy ? <span>{translateText("Recovery")}: {recoveryCopy}</span> : null}
      </div>
    </CockpitPanel>
  );
}

function NarrativeTile({
  icon,
  label,
  title,
  body,
}: {
  icon: ReactNode;
  label: string;
  title: string;
  body: string;
}) {
  return (
    <div className="assistant-thread-shell rounded-[22px] border border-white/8 px-4 py-4">
      <div className="flex items-center gap-2 text-[0.68rem] uppercase tracking-[0.24em] text-surface-400">
        {icon}
        <span>{label}</span>
      </div>
      <p className="mt-3 text-base font-semibold text-white">{title}</p>
      <p className="mt-2 text-sm leading-6 text-surface-300">{body}</p>
    </div>
  );
}
