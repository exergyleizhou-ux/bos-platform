import { useState } from "react";
import { Activity, Cpu, Radar, RefreshCcw } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import { CockpitPanel } from "@/components/ui/Cockpit";
import { Input } from "@/components/ui/Input";
import { SurfaceTile } from "@/components/ui/SurfaceTile";
import {
  useNativeModelDownload,
  useNativeModelDownloadPlan,
  useNativeModelInference,
  useNativeModelRuns,
  useNativeModelRuntimeStatus,
} from "@/hooks/useBos";

interface NativeModelRuntimeCardProps {
  batchId?: number;
}

const STATE_VARIANT = {
  disabled: "neutral",
  missing_dependencies: "danger",
  awaiting_artifact: "warning",
  artifact_detected_contract_only: "info",
  remote_reference_contract_only: "info",
  code_bundle_detected: "warning",
  live_adapter_ready: "success",
} as const;

function getEvidenceBadge(modelKey: string) {
  if (modelKey === "insecta") {
    return { label: "Bootstrap public vision", variant: "info" as const };
  }
  if (modelKey === "yolo11_dsconv") {
    return { label: "Specialized BSF vision", variant: "brand" as const };
  }
  if (modelKey === "chronos_bolt") {
    return { label: "Stabilized live timeseries", variant: "neutral" as const };
  }
  if (modelKey === "timer_s1") {
    return { label: "Gated timeseries fallback", variant: "warning" as const };
  }
  return { label: "Native model evidence", variant: "neutral" as const };
}

export function NativeModelRuntimeCard({ batchId }: NativeModelRuntimeCardProps) {
  const runtime = useNativeModelRuntimeStatus();
  const downloadPlan = useNativeModelDownloadPlan();
  const download = useNativeModelDownload();
  const inference = useNativeModelInference();
  const runs = useNativeModelRuns(undefined, batchId, 8);
  const [visionImagePath, setVisionImagePath] = useState("");
  const [visionImageUrl, setVisionImageUrl] = useState("");

  const latestResult = inference.data;

  return (
    <CockpitPanel className="p-5 lg:p-6">
      <CardHeader
        title="Native runtime"
        description="Check whether each frontier model is actually runnable, and expose honest dry-run, live, or fallback inference paths."
        action={
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<RefreshCcw className="h-4 w-4" />}
            onClick={() => void runtime.refetch()}
          >
            Refresh
          </Button>
        }
      />
      <CardBody className="space-y-4">
        <SurfaceTile className="assistant-thread-shell rounded-3xl p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={runtime.data?.enabled ? "success" : "danger"}>
              {runtime.data?.enabled ? "Runtime enabled" : "Runtime disabled"}
            </Badge>
            <Badge variant="neutral">{String(runtime.data?.summary?.total_models ?? 0)} models</Badge>
          </div>
          <p className="mt-3 text-sm leading-6 text-surface-300">
            Cache dir: {runtime.data?.cache_dir ?? "N/A"}
          </p>
        </SurfaceTile>

        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            leftIcon={<Cpu className="h-4 w-4" />}
            loading={inference.isPending}
            disabled={!visionImagePath.trim() && !visionImageUrl.trim()}
            onClick={() =>
              inference.mutate({
                model_key: "insecta",
                batch_id: batchId,
                dry_run: false,
                payload: visionImagePath.trim()
                  ? { image_path: visionImagePath.trim() }
                  : { image_url: visionImageUrl.trim() },
              })
            }
          >
            Run Insecta bootstrap
          </Button>
          <Button
            variant="secondary"
            leftIcon={<Radar className="h-4 w-4" />}
            loading={inference.isPending}
            onClick={() =>
              inference.mutate({
                model_key: "timer_s1",
                batch_id: batchId,
                dry_run: false,
                payload: {
                  metric_name: "decomposition_rate",
                  horizon: 6,
                  sensor_history: [0.31, 0.35, 0.4, 0.46, 0.5, 0.54],
                },
              })
            }
          >
            Run Timer-S1 fallback
          </Button>
          <Button
            variant="outline"
            leftIcon={<Cpu className="h-4 w-4" />}
            loading={inference.isPending}
            onClick={() =>
              inference.mutate({
                model_key: "chronos_bolt",
                batch_id: batchId,
                dry_run: false,
                payload: {
                  metric_name: "tray_temperature",
                  horizon: 6,
                  sensor_history: [27.1, 27.4, 27.8, 28.0, 28.2, 28.4],
                },
              })
            }
          >
            Run Chronos inference
          </Button>
        </div>

        <Input
          label="Vision image path"
          value={visionImagePath}
          onChange={(event) => setVisionImagePath(event.target.value)}
          placeholder="C:\\data\\insects\\tray-frame.jpg"
          helperText="Use this for public bootstrap vision models such as insecta. YOLO11-DSConv still needs its dedicated best.pt weight."
        />

        <Input
          label="Vision image URL"
          value={visionImageUrl}
          onChange={(event) => setVisionImageUrl(event.target.value)}
          placeholder="https://example.com/insect.jpg"
          helperText="Optional alternative to a local image path. BOS will cache the remote image before inference."
        />

        <div className="grid gap-3 xl:grid-cols-2">
          {(runtime.data?.runtimes ?? []).map((entry) => (
            <SurfaceTile
              key={entry.key}
              className="rounded-[22px] px-4 py-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-white">{entry.key}</p>
                <Badge
                  variant={STATE_VARIANT[entry.runtime_state as keyof typeof STATE_VARIANT] ?? "neutral"}
                >
                  {entry.runtime_state}
                </Badge>
                <Badge variant={entry.modality === "vision" ? "info" : "brand"}>
                  {entry.modality}
                </Badge>
              </div>
              <p className="mt-2 text-xs text-surface-400">{entry.adapter_status}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {entry.dependencies.map((dependency) => (
                  <Badge
                    key={`${entry.key}-${dependency.package}`}
                    variant={dependency.installed ? "success" : "danger"}
                  >
                    {dependency.package}
                  </Badge>
                ))}
              </div>
              <p className="mt-3 text-xs leading-6 text-surface-400">
                {entry.artifact.exists
                  ? `Artifact detected at ${entry.artifact.configured_location ?? entry.artifact.expected_location}`
                  : `Awaiting artifact at ${entry.artifact.expected_location}`}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={download.isPending}
                  onClick={() => download.mutate(entry.key)}
                >
                  Download artifact
                </Button>
              </div>
            </SurfaceTile>
          ))}
        </div>

        {downloadPlan.data?.length ? (
          <SurfaceTile className="rounded-[24px] p-4">
            <p className="assistant-section-kicker">Download plan</p>
            <div className="mt-3 space-y-3">
              {downloadPlan.data.map((item) => (
                <SurfaceTile
                  key={item.model_key}
                  tone="subtle"
                  className="px-4 py-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-white">{item.model_key}</p>
                    <Badge variant={item.supported ? "success" : "warning"}>{item.source_kind}</Badge>
                  </div>
                  <p className="mt-2 text-xs leading-6 text-surface-400">{item.target_path}</p>
                </SurfaceTile>
              ))}
            </div>
          </SurfaceTile>
        ) : null}

        {runs.data?.length ? (
          <SurfaceTile className="rounded-[24px] p-4">
            <p className="assistant-section-kicker">Recent inference runs</p>
            <p className="mt-2 text-xs leading-6 text-surface-400">
              {batchId ? `Filtered to batch ${batchId}` : "Showing all recent runs"}
            </p>
            <div className="mt-3 space-y-3">
              {runs.data.map((run) => {
                const evidence = getEvidenceBadge(run.model_key);
                return (
                  <SurfaceTile
                    key={run.artifact_path}
                    tone="subtle"
                    className="px-4 py-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-white">{run.model_key}</p>
                      <Badge variant={run.execution_mode.includes("live") ? "success" : "warning"}>
                        {run.execution_mode}
                      </Badge>
                      <Badge variant={evidence.variant}>{evidence.label}</Badge>
                    </div>
                    <p className="mt-2 text-xs leading-6 text-surface-400">{run.recorded_at}</p>
                    <p className="mt-1 text-xs leading-6 text-surface-400">{run.artifact_path}</p>
                  </SurfaceTile>
                );
              })}
            </div>
          </SurfaceTile>
        ) : null}

        {latestResult ? (
          <SurfaceTile tone="info" className="rounded-[24px] border-white/8 bg-gradient-to-br from-sky-500/8 via-transparent to-emerald-500/10 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Activity className="h-4 w-4 text-sky-200" />
              <p className="assistant-section-kicker">Latest runtime result</p>
              <Badge variant="info">{latestResult.execution_mode}</Badge>
              <Badge variant={latestResult.execution_mode.includes("live") ? "success" : "warning"}>
                {latestResult.execution_mode.includes("live") ? "live" : "fallback"}
              </Badge>
              <Badge variant={getEvidenceBadge(latestResult.model_key).variant}>
                {getEvidenceBadge(latestResult.model_key).label}
              </Badge>
            </div>
            <p className="mt-3 text-sm leading-6 text-surface-300">
              Model: {latestResult.model_key} · state: {latestResult.runtime_state}
            </p>
            {Array.isArray(latestResult.result?.forecast) ? (
              <p className="mt-2 text-sm leading-6 text-surface-300">
                Forecast: {(latestResult.result.forecast as unknown[]).join(", ")}
              </p>
            ) : null}
            {typeof latestResult.result?.detection_count === "number" ? (
              <p className="mt-2 text-sm leading-6 text-surface-300">
                Detections: {latestResult.result.detection_count as number}
              </p>
            ) : null}
            {Array.isArray(latestResult.result?.detections) && latestResult.result.detections.length ? (
              <div className="mt-4 space-y-3">
                {(latestResult.result.detections as Array<Record<string, unknown>>).map((detection, index) => (
                  <SurfaceTile
                    key={`det-${index}`}
                    tone="subtle"
                    className="px-4 py-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="success">{`Detection ${index + 1}`}</Badge>
                      {typeof detection.top_label === "string" ? (
                        <Badge variant="info">{detection.top_label}</Badge>
                      ) : null}
                      {typeof detection.confidence === "number" ? (
                        <Badge variant="neutral">{`conf ${detection.confidence.toFixed(3)}`}</Badge>
                      ) : null}
                    </div>
                    {Array.isArray(detection.bbox_xyxy) ? (
                      <p className="mt-2 text-xs leading-6 text-surface-400">
                        bbox: {(detection.bbox_xyxy as unknown[]).join(", ")}
                      </p>
                    ) : null}
                    {Array.isArray(detection.species_candidates) ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(detection.species_candidates as Array<Record<string, unknown>>).slice(0, 5).map((candidate, candidateIndex) => (
                          <Badge key={`cand-${index}-${candidateIndex}`} variant="brand">
                            {`${candidateIndex + 1}. ${String(candidate.label ?? "unknown")}`}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                  </SurfaceTile>
                ))}
              </div>
            ) : null}
            {typeof latestResult.result?.artifact_path === "string" ? (
              <p className="mt-2 text-xs leading-6 text-surface-400">
                Artifact log: {latestResult.result.artifact_path as string}
              </p>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              {latestResult.warnings.map((warning) => (
                <Badge key={warning} variant="warning">
                  {warning}
                </Badge>
              ))}
            </div>
          </SurfaceTile>
        ) : null}
      </CardBody>
    </CockpitPanel>
  );
}


