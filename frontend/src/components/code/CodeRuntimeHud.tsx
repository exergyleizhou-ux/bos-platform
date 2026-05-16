import { Activity, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { SurfaceTile } from "@/components/ui/SurfaceTile";
import { translateText } from "@/lib/i18n";
import type { CodeProviderIssue } from "@/lib/codeProviderUi";
import {
  runtimeBody,
  runtimeIssueVariant,
  runtimeNextAction,
  runtimeStatusLabel,
  runtimeStatusVariant,
} from "@/lib/codeRuntimeUi";

interface CodeRuntimeHudProps {
  status?: string | null;
  providerIssue?: CodeProviderIssue | null;
  className?: string;
  label?: string;
  resultSummary?: string | null;
  actionLabel?: string;
  onAction?: () => void;
  actionLoading?: boolean;
  actionDisabled?: boolean;
}

export function CodeRuntimeHud({
  status,
  providerIssue,
  className,
  label = "Runtime posture",
  resultSummary,
  actionLabel,
  onAction,
  actionLoading = false,
  actionDisabled = false,
}: CodeRuntimeHudProps) {
  const nextAction = runtimeNextAction(status, providerIssue);
  return (
    <SurfaceTile className={className}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={runtimeStatusVariant(status)} size="xs">
          {translateText(label)} {translateText(runtimeStatusLabel(status))}
        </Badge>
        {providerIssue ? (
          <Badge variant={runtimeIssueVariant(providerIssue)} size="xs">
            {translateText(providerIssue.title)}
          </Badge>
        ) : null}
      </div>
      <div className="mt-3 flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-2xl border border-white/8 bg-surface-950/50">
          {providerIssue ? <ShieldAlert className="h-4 w-4 text-amber-300" /> : <Activity className="h-4 w-4 text-brand-300" />}
        </div>
        <div className="min-w-0">
          <p className="text-sm leading-6 text-surface-200">{translateText(runtimeBody(status, providerIssue))}</p>
          {nextAction ? (
            <p className="mt-2 text-sm leading-6 text-surface-400">
              {translateText("Next")}: {translateText(nextAction)}
            </p>
          ) : null}
          {actionLabel && onAction ? (
            <div className="mt-3">
              <Button
                size="sm"
                variant="secondary"
                loading={actionLoading}
                disabled={actionDisabled}
                onClick={onAction}
              >
                {translateText(actionLabel)}
              </Button>
            </div>
          ) : null}
          {resultSummary ? (
            <p className="mt-3 rounded-xl border border-white/8 bg-surface-950/40 px-3 py-3 text-sm leading-6 text-surface-300">
              {translateText(resultSummary)}
            </p>
          ) : null}
        </div>
      </div>
    </SurfaceTile>
  );
}
