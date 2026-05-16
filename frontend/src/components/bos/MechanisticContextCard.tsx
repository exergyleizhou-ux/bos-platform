import type { ReactNode } from "react";
import { Activity, Gauge, Orbit, Waves } from "lucide-react";

import { MechanisticEnvelopeChart } from "@/components/charts/MechanisticEnvelopeChart";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { translateText } from "@/lib/i18n";
import { formatNumber, formatPercent } from "@/lib/utils";
import type { MechanisticContext } from "@/types/bos";

interface MechanisticContextCardProps {
  context?: MechanisticContext | null;
  title?: string;
  description?: string;
  signalLabel?: string | null;
}

function hasRenderableMechanisticContext(
  context: MechanisticContext | null | undefined,
): context is MechanisticContext {
  return Boolean(
    context &&
      context.c_di_ser &&
      context.handover_envelope &&
      context.inputs,
  );
}

export function MechanisticContextCard({
  context,
  title = "Mechanistic signal snapshot",
  description = "Audit-ready C-DI-SER, handover envelope, and evidence quality from the latest compiled signal.",
  signalLabel,
}: MechanisticContextCardProps) {
  const ready = hasRenderableMechanisticContext(context);

  return (
    <Card className="assistant-aside-card rounded-[28px]">
      <CardHeader title={title} description={description} />
      <CardBody className="space-y-4">
        {ready ? (
          <>
            <div className="assistant-thread-shell rounded-3xl border border-white/8 p-4">
              <div className="flex flex-wrap items-center gap-2">
                {signalLabel ? <Badge variant="info">{signalLabel}</Badge> : null}
                <Badge variant="success">
                  {translateText(`C-DI-SER ${formatNumber(context.c_di_ser.score, 3)}`)}
                </Badge>
                <Badge variant={context.c_di_ser.information_loss < 0.35 ? "success" : "warning"}>
                  {translateText(`Info loss ${formatPercent(context.c_di_ser.information_loss, 0)}`)}
                </Badge>
              </div>
              <p className="mt-3 text-sm leading-6 text-surface-300">
                {translateText(
                  context.c_di_ser.information_loss < 0.35
                    ? "Signal evidence is relatively coherent, so the mechanistic envelope can be trusted more confidently."
                    : "Evidence quality is usable but not pristine. Treat the envelope as directional rather than absolute.",
                )}
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricTile
                icon={<Gauge className="h-4 w-4" />}
                label="SER score"
                value={formatNumber(context.c_di_ser.score, 3)}
              />
              <MetricTile
                icon={<Orbit className="h-4 w-4" />}
                label="Tau star"
                value={`${formatNumber(context.handover_envelope.tau_star_min, 1)} min`}
              />
              <MetricTile
                icon={<Waves className="h-4 w-4" />}
                label="Peak"
                value={formatNumber(context.handover_envelope.c_peak, 3)}
              />
              <MetricTile
                icon={<Activity className="h-4 w-4" />}
                label="Mass balance"
                value={formatPercent(context.inputs.mass_balance_ratio, 0)}
              />
            </div>

            <MechanisticEnvelopeChart context={context} />

            <div className="assistant-aside-card rounded-3xl border border-white/8 p-4">
              <p className="assistant-section-kicker">Expanded parameters</p>
              <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                <MetricRow label="Alpha / beta" value={`${formatNumber(context.c_di_ser.alpha_s, 3)} / ${formatNumber(context.c_di_ser.beta_s, 3)}`} />
                <MetricRow label="Penalty" value={formatNumber(context.c_di_ser.penalty, 3)} />
                <MetricRow label="Evidence balance" value={formatPercent(context.c_di_ser.evidence_balance, 0)} />
                <MetricRow label="Metering completeness" value={formatPercent(context.inputs.metering_completeness, 0)} />
                <MetricRow label="Clock frequency" value={formatNumber(context.handover_envelope.f_clock, 4)} />
                <MetricRow label="Rise / decay" value={`${formatNumber(context.handover_envelope.rise_rate, 4)} / ${formatNumber(context.handover_envelope.decay_rate, 4)}`} />
              </dl>
            </div>
          </>
        ) : (
          <div className="assistant-aside-card rounded-3xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
            {translateText("Compile a signal first to populate the mechanistic snapshot.")}
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
