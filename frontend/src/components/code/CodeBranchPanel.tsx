import { GitBranch, RefreshCcw, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { SurfaceTile } from "@/components/ui/SurfaceTile";
import { translateText } from "@/lib/i18n";
import type { CodeBranchState, CodeReadinessResponse } from "@/types/code";

interface CodeBranchPanelProps {
  branchState?: CodeBranchState;
  readiness?: CodeReadinessResponse;
  refreshing: boolean;
  onRefresh: () => void;
}

function statusVariant(status?: string): "success" | "warning" | "danger" | "info" | "neutral" {
  switch (status) {
    case "clean":
    case "merge_ready":
      return "success";
    case "stale":
    case "needs_recovery":
      return "warning";
    case "dirty":
    case "blocked":
      return "danger";
    case "degraded":
      return "info";
    default:
      return "neutral";
  }
}

export function CodeBranchPanel({
  branchState,
  readiness,
  refreshing,
  onRefresh,
}: CodeBranchPanelProps) {
  return (
    <CockpitPanel className="border-emerald-400/15 bg-emerald-500/5 p-5 lg:p-6">
      <CardHeader
        title={translateText("Branch Posture")}
        description={translateText("Freshness, divergence, and merge readiness for the active session branch.")}
        action={
          <Button
            variant="secondary"
            size="sm"
            leftIcon={<RefreshCcw className="h-4 w-4" />}
            loading={refreshing}
            onClick={onRefresh}
          >
            {translateText("Refresh")}
          </Button>
        }
      />
      <CardBody className="space-y-4">
        <SurfaceTile tone="subtle">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-emerald-300" />
            <p className="truncate text-sm font-semibold text-white">
              {branchState?.branch_name ?? translateText("No branch state")}
            </p>
          </div>
          <p className="mt-2 text-xs text-surface-400">
            {translateText("Base branch")}: {branchState?.base_branch ?? translateText("unknown")}
          </p>
        </SurfaceTile>

        <div className="grid gap-3 sm:grid-cols-2">
          <Metric label={translateText("Branch Status")} value={translateText(branchState?.branch_status ?? "unknown")} />
          <Metric label={translateText("Readiness")} value={translateText(readiness?.readiness ?? "unknown")} />
          <Metric label={translateText("Ahead")} value={String(branchState?.ahead_count ?? 0)} />
          <Metric label={translateText("Behind")} value={String(branchState?.behind_count ?? 0)} />
        </div>

        <div className="flex flex-wrap gap-2">
          <Badge variant={statusVariant(branchState?.branch_status)} dot>
            {translateText(branchState?.branch_status ?? "unknown")}
          </Badge>
          <Badge variant={branchState?.is_dirty ? "danger" : "success"} dot>
            {translateText(branchState?.is_dirty ? "dirty" : "clean")}
          </Badge>
          <Badge variant={branchState?.is_stale_against_base ? "warning" : "success"} dot>
            {translateText(branchState?.is_stale_against_base ? "stale" : "fresh")}
          </Badge>
        </div>

        {readiness?.blocking_reasons.length ? (
          <SurfaceTile tone="warning">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-amber-300" />
              <p className="text-sm font-medium text-amber-100">{translateText("Recovery required")}</p>
            </div>
            <ul className="mt-2 space-y-1 text-xs text-amber-200/80">
              {readiness.blocking_reasons.map((reason) => (
                <li key={reason}>- {reason}</li>
              ))}
            </ul>
          </SurfaceTile>
        ) : null}
      </CardBody>
    </CockpitPanel>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <SurfaceTile className="px-3 py-3">
      <p className="text-[11px] uppercase tracking-[0.18em] text-surface-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-white">{value}</p>
    </SurfaceTile>
  );
}
