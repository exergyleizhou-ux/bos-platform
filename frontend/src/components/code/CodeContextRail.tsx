import { CheckCircle2, FlaskConical, GitBranch, ShieldAlert, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { translateText } from "@/lib/i18n";
import {
  codeActionPolicyBadgeVariant,
  formatCodeAction,
  formatCodeActionPolicy,
  resolveCodeActionPolicy,
} from "@/lib/codeActionPolicy";
import type {
  CodeBranchState,
  CodeOrchestrationSnapshot,
  CodeReadinessResponse,
  CodeRecoveryResponse,
  CodeRuntimeResponse,
  CodeSession,
  CodeVerificationResponse,
} from "@/types/code";

interface CodeContextRailProps {
  activeSession?: CodeSession | null;
  orchestration?: CodeOrchestrationSnapshot;
  runtime?: CodeRuntimeResponse;
  branchState?: CodeBranchState;
  readiness?: CodeReadinessResponse;
  recovery?: CodeRecoveryResponse;
  verification?: CodeVerificationResponse;
  mcpSummary?: string;
  runningVerification: boolean;
  refreshingBranch: boolean;
  runningAutomation: boolean;
  onRunVerification: () => void;
  onRefreshBranch: () => void;
  onRunAutomation: () => void;
}

export function CodeContextRail({
  activeSession,
  orchestration,
  runtime,
  branchState,
  readiness,
  recovery,
  verification,
  mcpSummary,
  runningVerification,
  refreshingBranch,
  runningAutomation,
  onRunVerification,
  onRefreshBranch,
  onRunAutomation,
}: CodeContextRailProps) {
  const runtimeMetrics = runtime?.runtime_state.runtime_metrics;
  const recoveryTaskId = runtimeMetrics?.last_recovery_task_id as number | undefined;
  const recoveryFailureClass = runtimeMetrics?.last_recovery_failure_class as string | undefined;
  const recoveryTaskAt = runtimeMetrics?.last_recovery_task_at as string | undefined;
  return (
    <div className="space-y-3">
      <CockpitPanel className="p-5 lg:p-6">
        <CardHeader
          title={translateText("Context Rail")}
          description={translateText("Keep the thread central. Pull the critical scientific posture into view here only when it helps you decide.")}
        />
        <CardBody className="space-y-3">
          <RailTile
            icon={<Sparkles className="h-4 w-4 text-brand-300" />}
            label={translateText("Session")}
            value={activeSession ? `#${activeSession.id} / ${translateText(activeSession.session_status)}` : translateText("No active session")}
            hint={activeSession ? `${activeSession.provider} / ${activeSession.model}` : translateText("Start a session when you want BOS Code to act.")}
          />
          <RailTile
            icon={<CheckCircle2 className="h-4 w-4 text-emerald-300" />}
            label={translateText("Review + Merge")}
            value={orchestration ? `${translateText(orchestration.verification_gate)} / ${translateText(orchestration.merge_readiness)}` : translateText("Awaiting orchestration snapshot")}
            hint={orchestration?.merge_summary ?? translateText("No active blockers")}
          />
          <RailTile
            icon={<GitBranch className="h-4 w-4 text-sky-300" />}
            label={translateText("Branch")}
            value={translateText(branchState?.branch_status ?? "unknown")}
            hint={readiness?.readiness ?? translateText("Awaiting branch posture")}
            action={
              <Button size="sm" variant="ghost" loading={refreshingBranch} onClick={onRefreshBranch}>
                {translateText("Refresh")}
              </Button>
            }
          />
          <RailTile
            icon={<FlaskConical className="h-4 w-4 text-fuchsia-300" />}
            label={translateText("Verification")}
            value={translateText(verification?.overall_status ?? "pending")}
            hint={orchestration?.merge_next_action ?? recovery?.headline ?? translateText("Run verification when the thread is ready for a gate decision.")}
            action={
              <Button size="sm" variant="secondary" loading={runningVerification} onClick={onRunVerification}>
                {translateText("Run pipeline")}
              </Button>
            }
          />
          {mcpSummary ? (
            <RailTile
              icon={<ShieldAlert className="h-4 w-4 text-violet-300" />}
              label={translateText("Connectors")}
              value={translateText("MCP posture")}
              hint={mcpSummary}
            />
          ) : null}
          {recovery?.blocking_reasons.length ? (
            <div className="rounded-2xl border border-amber-400/10 bg-amber-500/10 px-4 py-4">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-amber-300" />
                <p className="text-sm font-medium text-amber-100">{translateText("Recovery notes")}</p>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {recovery.blocking_reasons.map((reason) => (
                  <Badge key={reason} variant="warning">
                    {reason}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}
          {recoveryTaskId ? (
            <div className="rounded-2xl border border-rose-400/12 bg-rose-500/10 px-4 py-4">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-rose-300" />
                <p className="text-sm font-medium text-rose-100">{translateText("Recovery loop active")}</p>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge variant="warning">{translateText("task")} #{String(recoveryTaskId)}</Badge>
                {recoveryFailureClass ? <Badge variant="warning">{recoveryFailureClass}</Badge> : null}
              </div>
              {recoveryTaskAt ? (
                <p className="mt-3 text-sm leading-6 text-surface-300">
                  {translateText("Last recovery handoff")}: {recoveryTaskAt}
                </p>
              ) : null}
            </div>
          ) : null}
          {(orchestration?.merge_evidence?.length ?? 0) > 0 ? (
            <div className="rounded-2xl border border-white/8 bg-surface-950/55 px-4 py-4">
              <p className="text-sm font-medium text-white">{translateText("Merge evidence")}</p>
              <div className="mt-3 space-y-2">
                {(orchestration?.merge_evidence ?? []).map((item) => (
                  <p key={item} className="text-sm leading-6 text-surface-400">
                    {item}
                  </p>
                ))}
              </div>
              {orchestration?.merge_next_action ? (
                <p className="mt-3 text-sm font-medium text-surface-200">{translateText("Next action")}: {orchestration.merge_next_action}</p>
              ) : null}
            </div>
          ) : null}
          {orchestration?.operator_actions?.length ? (
            <div className="rounded-2xl border border-white/8 bg-white/4 px-4 py-4">
              <p className="text-sm font-medium text-white">{translateText("Operator actions")}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {orchestration.operator_actions.map((action) => {
                  const actionPolicy = resolveCodeActionPolicy(
                    action,
                    orchestration.operator_action_policies ?? orchestration.operator_action_classes,
                  );
                  return (
                    <div
                      key={action}
                      className="flex items-center gap-2"
                      data-testid="operator-action-chip"
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
            </div>
          ) : null}
          {orchestration?.next_automation_action ? (
            <div
              className={`rounded-2xl px-4 py-4 ${
                orchestration.automation_ready
                  ? "border border-sky-400/12 bg-sky-500/10"
                  : "border border-amber-400/12 bg-amber-500/10"
              }`}
              data-testid="automation-decision-card"
              data-next-automation-action={orchestration.next_automation_action}
              data-automation-ready={orchestration.automation_ready ? "true" : "false"}
            >
              <p className="text-sm font-medium text-white">{translateText("Automation next move")}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Badge variant={orchestration.automation_ready ? "info" : "warning"}>
                  {formatCodeAction(orchestration.next_automation_action)}
                </Badge>
                <Badge variant={orchestration.automation_ready ? "info" : "warning"}>
                  {translateText(orchestration.automation_ready ? "automation ready" : "automation gated")}
                </Badge>
              </div>
              <p className="mt-3 text-sm leading-6 text-surface-300">
                {translateText("Automation-safe actions available now")}: {(orchestration.automation_actions ?? []).length}
              </p>
              {orchestration.automation_summary ? (
                <p className="mt-2 text-sm leading-6 text-surface-300">{orchestration.automation_summary}</p>
              ) : null}
              {(orchestration.automation_blockers?.length ?? 0) > 0 ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {(orchestration.automation_blockers ?? []).map((blocker) => (
                    <Badge key={blocker} variant="warning">
                      {blocker}
                    </Badge>
                  ))}
                </div>
              ) : null}
              {orchestration.next_human_action ? (
                <p className="mt-2 text-sm leading-6 text-surface-400">
                  {translateText("Human gate after that")}: {formatCodeAction(orchestration.next_human_action)}
                </p>
              ) : null}
              <div className="mt-3 flex justify-end">
                <Button
                  size="sm"
                  variant={orchestration.automation_ready ? "secondary" : "ghost"}
                  loading={runningAutomation}
                  disabled={!orchestration.automation_ready}
                  data-testid="run-next-automation-button"
                  onClick={onRunAutomation}
                >
                  {translateText("Run next automation")}
                </Button>
              </div>
            </div>
          ) : null}
        </CardBody>
      </CockpitPanel>
    </div>
  );
}

function RailTile({
  icon,
  label,
  value,
  hint,
  action,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[0.68rem] uppercase tracking-[0.22em] text-surface-500">
            {icon}
            <span>{label}</span>
          </div>
          <p className="mt-3 text-sm font-semibold text-white">{value}</p>
          {hint ? <p className="mt-2 text-sm leading-6 text-surface-400">{hint}</p> : null}
        </div>
        {action ? <div className="flex-shrink-0">{action}</div> : null}
      </div>
    </div>
  );
}
