import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatNumber } from "@/lib/utils";
import type { SupervisorSnapshot } from "@/types/bos";

interface SupervisorHistoryChartProps {
  history: SupervisorSnapshot[];
  height?: number;
}

export function SupervisorHistoryChart({
  history,
  height = 260,
}: SupervisorHistoryChartProps) {
  const data = history.map((snapshot, index) => ({
    step: index + 1,
    recorded_at: snapshot.recorded_at,
    c_signal_hat: snapshot.decision?.c_signal_hat ?? null,
    confidence: snapshot.decision?.confidence ?? null,
    dc_dt_hat: snapshot.decision?.dc_dt_hat ?? null,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 18, bottom: 0, left: 0 }}>
        <CartesianGrid
          strokeDasharray="3 3"
          vertical={false}
          stroke="rgb(143 159 179 / 0.18)"
        />

        <XAxis
          dataKey="step"
          tickFormatter={(value) => `#${value}`}
          tick={{ fontSize: 11, fill: "var(--color-surface-400)" }}
          axisLine={false}
          tickLine={false}
          dy={8}
        />

        <YAxis
          yAxisId="primary"
          domain={[0, 1]}
          tickFormatter={(value: number) => `${Math.round(value * 100)}%`}
          tick={{ fontSize: 11, fill: "var(--color-surface-400)" }}
          axisLine={false}
          tickLine={false}
          width={52}
        />

        <YAxis
          yAxisId="secondary"
          orientation="right"
          tickFormatter={(value: number) => value.toFixed(2)}
          tick={{ fontSize: 11, fill: "var(--color-surface-500)" }}
          axisLine={false}
          tickLine={false}
          width={48}
        />

        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const item = payload[0].payload as (typeof data)[number];

            return (
              <div className="rounded-2xl border border-white/10 bg-surface-900/95 px-3 py-2 text-xs shadow-card">
                <p className="font-medium text-white">{`Observation #${item.step}`}</p>
                <p className="mt-1 text-surface-300">
                  C-hat: <span className="font-bold text-sky-300">{formatNumber(item.c_signal_hat, 3)}</span>
                </p>
                <p className="text-surface-300">
                  Confidence: <span className="font-bold text-emerald-300">{formatNumber(item.confidence, 3)}</span>
                </p>
                <p className="text-surface-400">
                  dC/dt: <span className="font-bold text-amber-300">{formatNumber(item.dc_dt_hat, 3)}</span>
                </p>
              </div>
            );
          }}
        />

        <Line
          yAxisId="primary"
          type="monotone"
          dataKey="c_signal_hat"
          stroke="#7dd3fc"
          strokeWidth={2.5}
          dot={{ r: 3, fill: "#7dd3fc", strokeWidth: 0 }}
          connectNulls={false}
        />
        <Line
          yAxisId="primary"
          type="monotone"
          dataKey="confidence"
          stroke="#86efac"
          strokeWidth={2.5}
          dot={{ r: 3, fill: "#86efac", strokeWidth: 0 }}
          connectNulls={false}
        />
        <Line
          yAxisId="secondary"
          type="monotone"
          dataKey="dc_dt_hat"
          stroke="#f6c85f"
          strokeWidth={2}
          dot={{ r: 2.5, fill: "#f6c85f", strokeWidth: 0 }}
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
