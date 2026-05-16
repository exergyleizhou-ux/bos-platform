import type { ReactNode } from "react";
import { Activity, ArrowRightLeft, Clock3 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { translateText } from "@/lib/i18n";
import { formatDateTime, formatNumber, formatPercent } from "@/lib/utils";
import type { SupervisorSnapshot } from "@/types/bos";

interface SupervisorSnapshotCardProps {
  snapshot?: SupervisorSnapshot | null;
  title?: string;
  description?: string;
}

export function SupervisorSnapshotCard({
  snapshot,
  title = "Latest supervisor snapshot",
  description = "Most recent causal observation and decision emitted by the BOS supervisor.",
}: SupervisorSnapshotCardProps) {
  return (
    <Card className="assistant-aside-card rounded-[28px]">
      <CardHeader title={title} description={description} />
      <CardBody className="space-y-4">
        {snapshot ? (
          <>
            <div className="assistant-thread-shell rounded-3xl border border-white/8 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="info">{translateText(`Mode ${snapshot.mode}`)}</Badge>
                <Badge variant={snapshot.decision?.recommended_handover ? "warning" : "success"}>
                  {snapshot.decision?.recommended_handover ? "Handover advised" : "Observe"}
                </Badge>
                <Badge variant="neutral">
                  {translateText(`Recorded ${formatDateTime(snapshot.recorded_at)}`)}
                </Badge>
              </div>
              <p className="mt-3 text-sm leading-6 text-surface-300">
                {translateText(
                  snapshot.decision?.trigger_reason
                    ? `Trigger reason: ${snapshot.decision.trigger_reason}.`
                    : "No explicit trigger fired during the latest observation window.",
                )}
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricTile icon={<Activity className="h-4 w-4" />} label="C-hat" value={formatNumber(snapshot.decision?.c_signal_hat, 3)} />
              <MetricTile icon={<ArrowRightLeft className="h-4 w-4" />} label="dC/dt" value={formatNumber(snapshot.decision?.dc_dt_hat, 3)} />
              <MetricTile icon={<Clock3 className="h-4 w-4" />} label="Confidence" value={formatPercent(snapshot.decision?.confidence, 0)} />
              <MetricTile icon={<Clock3 className="h-4 w-4" />} label="Expected window" value={snapshot.decision?.expected_freshness_window_hours != null ? `${formatNumber(snapshot.decision.expected_freshness_window_hours, 2)} h` : "N/A"} />
            </div>

            <div className="assistant-aside-card rounded-3xl border border-white/8 p-4">
              <p className="assistant-section-kicker">Expanded decision</p>
              <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                <MetricRow label="Trigger" value={String(snapshot.decision?.trigger_reason ?? "none")} />
                <MetricRow label="Negative slope streak" value={String(snapshot.decision?.negative_slope_streak ?? 0)} />
                <MetricRow label="Information loss" value={formatPercent(snapshot.decision?.information_loss, 0)} />
                <MetricRow label="Observability" value={formatPercent(snapshot.decision?.observability_score, 0)} />
              </dl>
              <div className="mt-4 flex flex-wrap gap-2">
                {(snapshot.decision?.channels_used ?? []).map((channel) => (
                  <Badge key={channel} variant="success">{channel}</Badge>
                ))}
                {(snapshot.decision?.missing_channels ?? []).map((channel) => (
                  <Badge key={channel} variant="danger">{channel}</Badge>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="assistant-aside-card rounded-3xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
            {translateText("No supervisor snapshot has been recorded yet.")}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function MetricTile({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="assistant-meta-panel rounded-2xl border border-white/8 bg-surface-900/70 px-4 py-3">
      <div className="flex items-center gap-2 text-brand-200">
        {icon}
        <p className="assistant-section-kicker !text-surface-500">{translateText(label)}</p>
      </div>
      <p className="mt-3 text-sm font-medium text-white">{value}</p>
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <dt className="text-surface-400">{translateText(label)}</dt>
      <dd className="text-right font-medium text-white">{value}</dd>
    </div>
  );
}
