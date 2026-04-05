import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatNumber, formatShortDate } from "@/lib/utils";
import type { SERTrendPoint } from "@/types/dashboard";

interface SERTrendChartProps {
  data: SERTrendPoint[];
  height?: number;
}

export function SERTrendChart({ data, height = 300 }: SERTrendChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid
          strokeDasharray="3 3"
          vertical={false}
          stroke="rgb(143 159 179 / 0.18)"
        />

        <XAxis
          dataKey="date"
          tickFormatter={formatShortDate}
          tick={{ fontSize: 11, fill: "var(--color-surface-400)" }}
          axisLine={false}
          tickLine={false}
          dy={8}
        />

        <YAxis
          domain={["auto", "auto"]}
          tickFormatter={(value: number) => value.toFixed(3)}
          tick={{ fontSize: 11, fill: "var(--color-surface-400)" }}
          axisLine={false}
          tickLine={false}
          dx={-8}
          width={56}
        />

        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const item = payload[0].payload as SERTrendPoint;

            return (
              <div className="rounded-2xl border border-white/10 bg-surface-900/95 px-3 py-2 text-xs shadow-card">
                <p className="font-medium text-white">{formatShortDate(item.date)}</p>
                <p className="mt-1 text-surface-300">
                  SER: <span className="font-bold text-brand-300">{formatNumber(item.ser_value, 4)}</span>
                </p>
                <p className="text-surface-500">Batches: {item.batch_count}</p>
              </div>
            );
          }}
        />

        <ReferenceLine
          y={0.12}
          stroke="#f59e0b"
          strokeDasharray="4 4"
          strokeWidth={1}
          label={{ value: "Pass <= 0.12", position: "right", fontSize: 10, fill: "#f59e0b" }}
        />

        <Line
          type="monotone"
          dataKey="ser_value"
          stroke="#25c897"
          strokeWidth={2.5}
          dot={{ r: 3, fill: "#25c897", strokeWidth: 0 }}
          activeDot={{ r: 5, fill: "#11ad82", strokeWidth: 2, stroke: "#fff" }}
          animationDuration={800}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
