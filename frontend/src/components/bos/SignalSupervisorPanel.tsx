import type { Dispatch, SetStateAction } from "react";
import { useMemo, useState } from "react";
import { Radar, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { translateText } from "@/lib/i18n";
import { formatDateTime, formatNumber, formatPercent } from "@/lib/utils";
import type { SignalBatch, SupervisorObservationRequest } from "@/types/bos";
import { useHandoverRecommendation, useSupervisorState } from "@/hooks/useBos";

interface SignalSupervisorPanelProps {
  signal?: SignalBatch | null;
}

export function SignalSupervisorPanel({ signal }: SignalSupervisorPanelProps) {
  const supervisor = useSupervisorState(signal?.id);
  const handover = useHandoverRecommendation(signal?.id);
  const [form, setForm] = useState<SupervisorObservationRequest>({
    uv254: 2.4,
    od280: 2.0,
    do: 5.1,
    ph: 7.1,
    elapsed_hours: 8,
    previous_c_signal_hat: 0.58,
    previous_elapsed_hours: 7,
    previous_dc_dt_hat: 0.03,
    previous_negative_slope_streak: 0,
    confidence_threshold: 0.8,
    negative_slope_persistence: 3,
    observability_required: true,
  });

  const canRun = Boolean(signal?.id);
  const signalLabel = signal?.compiled_signal_id ?? (signal ? `Signal ${signal.id}` : null);
  const latestResult = handover.data ?? supervisor.data ?? null;
  const negativeSlopeStreak = supervisor.data?.negative_slope_streak ?? 0;
  const recommendationTone = useMemo(() => {
    if (!handover.data) return "neutral" as const;
    if (handover.data.recommended_handover) return "warning" as const;
    return "success" as const;
  }, [handover.data]);

  return (
    <Card className="assistant-aside-card rounded-[28px]">
      <CardHeader
        title="Supervisor preview"
        description="Run the BOS supervisor against proxy observations and see whether handover is currently advised."
      />
      <CardBody className="space-y-4">
        {canRun ? (
          <>
            <div className="assistant-thread-shell rounded-3xl border border-white/8 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="info">{signalLabel}</Badge>
                <Badge variant="neutral">
                  {translateText(`Freshness ${signal?.freshness_state ?? "Unknown"}`)}
                </Badge>
              </div>
              <p className="mt-3 text-sm leading-6 text-surface-300">
                {translateText(
                  "Use a plausible proxy snapshot to evaluate the latent signal state and see whether the handover trigger should fire.",
                )}
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Input
                label="UV254"
                type="number"
                step="0.01"
                value={String(form.uv254)}
                onChange={(event) => updateNumber("uv254", event.target.value, setForm)}
              />
              <Input
                label="OD280"
                type="number"
                step="0.01"
                value={String(form.od280)}
                onChange={(event) => updateNumber("od280", event.target.value, setForm)}
              />
              <Input
                label="DO"
                type="number"
                step="0.01"
                value={String(form.do)}
                onChange={(event) => updateNumber("do", event.target.value, setForm)}
              />
              <Input
                label="pH"
                type="number"
                step="0.01"
                value={String(form.ph)}
                onChange={(event) => updateNumber("ph", event.target.value, setForm)}
              />
              <Input
                label="Elapsed (h)"
                type="number"
                step="0.1"
                value={String(form.elapsed_hours)}
                onChange={(event) => updateNumber("elapsed_hours", event.target.value, setForm)}
              />
              <Input
                label="Prev C-hat"
                type="number"
                step="0.01"
                value={String(form.previous_c_signal_hat ?? "")}
                onChange={(event) => updateOptionalNumber("previous_c_signal_hat", event.target.value, setForm)}
              />
              <Input
                label="Prev elapsed (h)"
                type="number"
                step="0.1"
                value={String(form.previous_elapsed_hours ?? "")}
                onChange={(event) => updateOptionalNumber("previous_elapsed_hours", event.target.value, setForm)}
              />
              <Input
                label="Prev dC/dt"
                type="number"
                step="0.01"
                value={String(form.previous_dc_dt_hat ?? "")}
                onChange={(event) => updateOptionalNumber("previous_dc_dt_hat", event.target.value, setForm)}
              />
            </div>

            <div className="flex flex-wrap gap-3">
              <Button
                leftIcon={<Radar className="h-4 w-4" />}
                loading={supervisor.isPending}
                onClick={() => supervisor.mutate(form)}
              >
                Evaluate supervisor
              </Button>
              <Button
                variant="secondary"
                leftIcon={<Sparkles className="h-4 w-4" />}
                loading={handover.isPending}
                onClick={() => handover.mutate(form)}
              >
                Evaluate handover
              </Button>
            </div>

            {latestResult ? (
              <>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <MetricTile label="C-hat" value={formatNumber(latestResult.c_signal_hat, 3)} />
                  <MetricTile label="dC/dt" value={formatNumber(latestResult.dc_dt_hat, 3)} />
                  <MetricTile label="Confidence" value={formatPercent(latestResult.confidence, 0)} />
                  <MetricTile label="Observability" value={formatPercent(latestResult.observability_score, 0)} />
                </div>

                <div className="assistant-aside-card rounded-3xl border border-white/8 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    {"recommended_handover" in latestResult ? (
                      <Badge variant={recommendationTone}>
                        {latestResult.recommended_handover ? "Handover advised" : "Keep observing"}
                      </Badge>
                    ) : null}
                    {latestResult.trigger_reason ? (
                      <Badge variant="warning">{latestResult.trigger_reason}</Badge>
                    ) : (
                      <Badge variant="success">No trigger fired</Badge>
                    )}
                    <Badge variant="info">
                      {translateText(`Slope streak ${negativeSlopeStreak}`)}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-surface-300">
                    {latestResult.expected_handover
                      ? translateText(`Expected handover window around ${formatDateTime(latestResult.expected_handover)}.`)
                      : translateText("No handover timestamp is available yet.")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(latestResult.channels_used ?? []).map((channel) => (
                      <Badge key={channel} variant="success">{channel}</Badge>
                    ))}
                    {(latestResult.missing_channels ?? []).map((channel) => (
                      <Badge key={channel} variant="danger">{channel}</Badge>
                    ))}
                  </div>
                </div>
              </>
            ) : null}
          </>
        ) : (
          <div className="assistant-aside-card rounded-3xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
            {translateText("Compile a signal first, then evaluate supervisor and handover recommendations here.")}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="assistant-meta-panel rounded-2xl border border-white/8 bg-surface-900/70 px-4 py-3">
      <p className="assistant-section-kicker !text-surface-500">{translateText(label)}</p>
      <p className="mt-2 text-sm font-medium text-white">{value}</p>
    </div>
  );
}

function updateNumber(
  key: keyof SupervisorObservationRequest,
  value: string,
  setForm: Dispatch<SetStateAction<SupervisorObservationRequest>>,
) {
  const parsed = Number(value);
  setForm((current) => ({
    ...current,
    [key]: Number.isFinite(parsed) ? parsed : 0,
  }));
}

function updateOptionalNumber(
  key: keyof SupervisorObservationRequest,
  value: string,
  setForm: Dispatch<SetStateAction<SupervisorObservationRequest>>,
) {
  const trimmed = value.trim();
  setForm((current) => ({
    ...current,
    [key]: trimmed ? Number(trimmed) : undefined,
  }));
}
