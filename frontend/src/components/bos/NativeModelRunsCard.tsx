import type { NativeModelRunArtifact } from "@/types/bos";
import { ActivitySquare, FileJson } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { useNativeModelRuns } from "@/hooks/useBos";
import { formatDateTime } from "@/lib/utils";

interface NativeModelRunsCardProps {
  batchId: number;
  limit?: number;
  runs?: NativeModelRunArtifact[] | null;
  isLoading?: boolean;
}

export function NativeModelRunsCard({
  batchId,
  limit = 8,
  runs: providedRuns,
  isLoading: providedLoading,
}: NativeModelRunsCardProps) {
  const runsQuery = useNativeModelRuns(undefined, batchId, limit);
  const runItems = providedRuns ?? runsQuery.data ?? [];
  const isLoading = providedLoading ?? runsQuery.isLoading;

  return (
    <Card className="assistant-aside-card rounded-[28px]">
      <CardHeader
        title="Native inference history"
        description="Recent frontier-model runs linked to this batch, including live Chronos and any fallback projections."
      />
      <CardBody className="space-y-4">
        <div className="assistant-aside-card rounded-3xl border border-white/8 px-4 py-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">batch {batchId}</Badge>
            <Badge variant="neutral">{runItems.length} runs</Badge>
          </div>
          <p className="mt-3 text-sm leading-6 text-surface-300">
            BOS filters native-model run artifacts by batch context so operators can inspect the exact predictions and execution modes tied to this record.
          </p>
        </div>

        {isLoading ? (
          <div className="rounded-2xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
            Loading native inference history...
          </div>
        ) : runItems.length ? (
          <div className="space-y-3">
            {runItems.map((run) => {
              const forecast = Array.isArray(run.result?.forecast)
                ? (run.result.forecast as unknown[]).slice(0, 4).join(", ")
                : null;
              const live = run.execution_mode.includes("live");

              return (
                <div
                  key={run.artifact_path}
                  className="rounded-2xl border border-white/8 bg-surface-900/80 px-4 py-4"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium text-white">{run.model_key}</p>
                    <Badge variant={live ? "success" : "warning"}>{run.execution_mode}</Badge>
                    <Badge variant={run.model_key === "insecta" ? "info" : run.model_key === "yolo11_dsconv" ? "brand" : "neutral"}>
                      {run.model_key === "insecta"
                        ? "Bootstrap public vision"
                        : run.model_key === "yolo11_dsconv"
                          ? "Specialized BSF vision"
                          : "Time-series evidence"}
                    </Badge>
                  </div>
                  <p className="mt-2 text-xs text-surface-400">{formatDateTime(run.recorded_at)}</p>

                  {forecast ? (
                    <div className="mt-3 rounded-2xl border border-sky-400/15 bg-sky-500/10 px-3 py-2 text-sm text-sky-100">
                      Forecast preview: {forecast}
                    </div>
                  ) : null}

                  <div className="mt-3 flex flex-wrap gap-2">
                    {run.warnings.map((warning) => (
                      <Badge key={warning} variant="warning">
                        {warning}
                      </Badge>
                    ))}
                  </div>

                  <div className="mt-3 flex items-start gap-2 text-xs text-surface-400">
                    <FileJson className="mt-0.5 h-4 w-4 flex-shrink-0" />
                    <span className="break-all">{run.artifact_path}</span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
            <div className="flex items-center justify-center gap-2 text-surface-300">
              <ActivitySquare className="h-4 w-4" />
              <span>No native inference artifacts are attached to this batch yet.</span>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
