import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { translateText } from "@/lib/i18n";
import type { MechanisticContext } from "@/types/bos";

interface MechanisticEnvelopeChartProps {
  context: MechanisticContext;
  height?: number;
}

export function MechanisticEnvelopeChart({
  context,
  height = 260,
}: MechanisticEnvelopeChartProps) {
  const radarData = [
    { metric: "SER", value: clamp(context.c_di_ser.score) },
    { metric: translateText("Peak"), value: clamp(context.handover_envelope.c_peak) },
    { metric: translateText("Metering"), value: clamp(context.inputs.metering_completeness) },
    { metric: translateText("Balance"), value: clamp(context.inputs.mass_balance_ratio) },
    { metric: translateText("Evidence"), value: clamp(context.c_di_ser.evidence_balance) },
    { metric: translateText("Low loss"), value: clamp(1 - context.c_di_ser.information_loss) },
  ];

  const barData = [
    { label: translateText("Tau*"), value: clamp(context.handover_envelope.tau_star_min / 240), color: "#f6c85f" },
    { label: translateText("Peak"), value: clamp(context.handover_envelope.c_peak), color: "#7dd3fc" },
    { label: translateText("Penalty"), value: clamp(context.c_di_ser.penalty), color: "#86efac" },
    { label: translateText("Loss"), value: clamp(context.c_di_ser.information_loss), color: "#fda4af" },
  ];

  return (
    <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
      <div className="assistant-meta-panel rounded-3xl border border-white/8 bg-surface-900/70 px-3 py-4">
        <p className="assistant-section-kicker !text-surface-500">{translateText("Signal geometry")}</p>
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart outerRadius="72%" data={radarData}>
              <PolarGrid stroke="rgba(255,255,255,0.12)" />
              <PolarAngleAxis
                dataKey="metric"
                tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
              />
              <Radar
                name={translateText("Mechanistic profile")}
                dataKey="value"
                stroke="#7dd3fc"
                fill="#38bdf8"
                fillOpacity={0.35}
                strokeWidth={2}
              />
              <Tooltip
                formatter={(value: number) => value.toFixed(3)}
                contentStyle={{
                  backgroundColor: "rgba(15, 23, 42, 0.95)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: 14,
                  color: "#fff",
                }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="assistant-meta-panel rounded-3xl border border-white/8 bg-surface-900/70 px-3 py-4">
        <p className="assistant-section-kicker !text-surface-500">{translateText("Handover envelope")}</p>
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} margin={{ top: 16, right: 12, left: -18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis
                dataKey="label"
                tick={{ fill: "rgba(255,255,255,0.75)", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 1]}
                tickFormatter={(value) => `${Math.round(value * 100)}%`}
                tick={{ fill: "rgba(255,255,255,0.55)", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                formatter={(value: number, _name, item) => {
                  if (item?.payload?.label === translateText("Tau*")) {
                    return `${context.handover_envelope.tau_star_min.toFixed(1)} min`;
                  }
                  return `${(value * 100).toFixed(1)}%`;
                }}
                contentStyle={{
                  backgroundColor: "rgba(15, 23, 42, 0.95)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: 14,
                  color: "#fff",
                }}
              />
              <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                {barData.map((entry) => (
                  <Cell key={entry.label} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function clamp(value: number, lower = 0, upper = 1) {
  return Math.max(lower, Math.min(upper, value));
}
