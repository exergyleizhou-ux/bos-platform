import { RefreshCcw, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { translateText } from "@/lib/i18n";

interface SignalCompilerPanelProps {
  compileStatus: string | null;
  latestSignalStatus: string | null;
  signalFreshness: string;
  hasSignal: boolean;
  onCompile: () => void;
  onRefresh: () => void;
  compileLoading?: boolean;
  refreshLoading?: boolean;
}

export function SignalCompilerPanel({
  compileStatus,
  latestSignalStatus,
  signalFreshness,
  hasSignal,
  onCompile,
  onRefresh,
  compileLoading = false,
  refreshLoading = false,
}: SignalCompilerPanelProps) {
  const freshnessHint = getFreshnessHint(signalFreshness, hasSignal);

  return (
    <Card className="assistant-aside-card rounded-[28px]">
      <CardHeader
        title="Signal Actions"
        description="Compile the signal or refresh its status directly from the batch detail surface."
      />
      <CardBody className="space-y-4">
        <div className="assistant-thread-shell rounded-3xl border border-white/8 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={hasSignal ? "success" : "warning"}>
              {hasSignal ? "Signal ready" : "Signal missing"}
            </Badge>
            <Badge variant={compileStatusVariant(compileStatus)}>
              {formatCompileStatus(compileStatus)}
            </Badge>
            <Badge variant={signalStatusVariant(latestSignalStatus)}>
              {formatSignalStatus(latestSignalStatus)}
            </Badge>
          </div>
          <p className="mt-3 text-sm leading-6 text-surface-300">{translateText(freshnessHint)}</p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Button
            fullWidth
            leftIcon={<Sparkles className="h-4 w-4" />}
            onClick={onCompile}
            loading={compileLoading}
          >
            Compile signal
          </Button>
          <Button
            variant="secondary"
            fullWidth
            leftIcon={<RefreshCcw className="h-4 w-4" />}
            onClick={onRefresh}
            loading={refreshLoading}
            disabled={!hasSignal}
          >
            Refresh signal status
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function getFreshnessHint(signalFreshness: string, hasSignal: boolean) {
  const normalized = signalFreshness.toLowerCase();
  if (!hasSignal) return "Compile a signal first, then continue with release and portability decisions.";
  if (normalized.includes("stale")) return "The signal is outside the recommended freshness window. Refresh it or compile a new one first.";
  if (normalized.includes("stable")) return "The current signal is still usable, but refreshing it before a critical decision is recommended.";
  return "The current signal can still be used. If the batch changed recently, refresh once more to confirm the status.";
}

function formatCompileStatus(value: string | null) {
  if (value === "compiled") return "Compiled";
  if (value === "manual") return "Manual signal";
  if (value === "not_started") return "Not started";
  return "Status pending";
}

function formatSignalStatus(value: string | null) {
  if (value === "valid") return "Signal valid";
  if (value === "review") return "Review advised";
  if (value === "blocked") return "Signal blocked";
  if (value === "missing") return "No signal status";
  return value ?? "Status pending";
}

function compileStatusVariant(value: string | null) {
  if (value === "compiled") return "success" as const;
  if (value === "manual") return "info" as const;
  return "warning" as const;
}

function signalStatusVariant(value: string | null) {
  if (value === "valid") return "success" as const;
  if (value === "review") return "warning" as const;
  if (value === "blocked") return "danger" as const;
  return "neutral" as const;
}
