import { ShieldAlert, Wrench } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { translateText } from "@/lib/i18n";
import type { CodeAutomationExecutionResponse, CodeRecoveryResponse } from "@/types/code";

interface CodeRecoveryPanelProps {
  recovery?: CodeRecoveryResponse;
  result?: CodeAutomationExecutionResponse | null;
  resultSummary?: string | null;
  actionLabel?: string;
  actionLoading?: boolean;
  actionDisabled?: boolean;
  onAction?: () => void;
}

function variant(status?: string): "success" | "warning" | "danger" | "info" | "neutral" {
  switch (status) {
    case "merge_ready":
    case "ready":
      return "success";
    case "needs_recovery":
      return "warning";
    case "blocked":
      return "danger";
    case "degraded":
      return "info";
    default:
      return "neutral";
  }
}

export function CodeRecoveryPanel({
  recovery,
  result,
  resultSummary,
  actionLabel,
  actionLoading = false,
  actionDisabled = false,
  onAction,
}: CodeRecoveryPanelProps) {
  return (
    <Card className="border-amber-400/15 bg-amber-500/5">
      <CardHeader
        title={translateText("Recovery Advisor")}
        description={translateText("Structured next-step guidance for blocked, degraded, or recovery-required states.")}
        action={
          <Badge variant={variant(recovery?.status)} dot>
            {translateText(recovery?.status ?? "unknown")}
          </Badge>
        }
      />
      <CardBody className="space-y-4">
        <div className="rounded-2xl border border-white/8 bg-surface-950/60 p-4">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-amber-300" />
            <p className="text-sm font-medium text-white">
              {translateText(recovery?.headline ?? "No recovery guidance available.")}
            </p>
          </div>
          {recovery?.failure_class ? (
            <p className="mt-2 text-xs text-surface-400">{translateText("Failure class")}: {translateText(recovery.failure_class)}</p>
          ) : null}
          {recovery?.next_safe_action ? (
            <p className="mt-2 text-xs text-surface-400">
              {translateText("Next safe action")}: {translateText(recovery.next_safe_action)}
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          {recovery?.recommended_actions.length ? (
            recovery.recommended_actions.map((action) => (
              <div key={action} className="rounded-xl border border-white/8 bg-white/4 p-3">
                <div className="flex items-start gap-2">
                  <Wrench className="mt-0.5 h-4 w-4 text-amber-300" />
                  <p className="text-sm text-white">{action}</p>
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm text-surface-400">{translateText("No recommended actions at the moment.")}</p>
          )}
        </div>

        {recovery?.blocking_reasons.length ? (
          <div className="rounded-2xl border border-white/8 bg-white/4 p-4">
            <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">{translateText("Blocking Reasons")}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {recovery.blocking_reasons.map((reason) => (
                <Badge key={reason} variant="warning">
                  {reason}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
        {actionLabel && onAction ? (
          <div className="flex justify-end">
            <Button
              size="sm"
              variant="secondary"
              loading={actionLoading}
              disabled={actionDisabled}
              data-testid="run-next-automation-button"
              onClick={onAction}
            >
              {translateText(actionLabel)}
            </Button>
          </div>
        ) : null}
        {result ? (
          <div className="rounded-2xl border border-white/8 bg-surface-950/40 p-4">
            <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">{translateText("Last recovery result")}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge variant="info">{translateText(result.executed_action)}</Badge>
              <Badge variant="neutral">{translateText(result.execution_status)}</Badge>
              {result.resulting_session_status ? (
                <Badge variant="neutral">
                  {translateText("session")} {translateText(result.resulting_session_status)}
                </Badge>
              ) : null}
              {result.resulting_verification_status ? (
                <Badge variant="neutral">
                  {translateText("verification")} {translateText(result.resulting_verification_status)}
                </Badge>
              ) : null}
            </div>
            <p className="mt-3 text-sm leading-6 text-surface-200">{translateText(result.summary)}</p>
            <p className="mt-2 text-xs text-surface-400">
              {translateText("Executed at")}: {result.executed_at}
            </p>
          </div>
        ) : resultSummary ? (
          <div className="rounded-2xl border border-white/8 bg-surface-950/40 p-4">
            <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">{translateText("Last recovery result")}</p>
            <p className="mt-3 text-sm leading-6 text-surface-200">{translateText(resultSummary)}</p>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
