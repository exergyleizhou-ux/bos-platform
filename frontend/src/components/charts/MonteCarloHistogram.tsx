/**
 * BOS Pipeline v9.0 �� Monte Carlo Histogram
 *
 * Bar chart showing the SER distribution from Monte Carlo simulation.
 */

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { formatNumber } from "@/lib/utils";
import type { MonteCarloResponse } from "@/types/simulation";

interface MonteCarloHistogramProps {
  data: MonteCarloResponse;
  height?: number;
}

export function MonteCarloHistogram({
  data,
  height = 260,
}: MonteCarloHistogramProps) {
  // Build chart data from histogram_bins / histogram_counts
  const chartData = data.histogram_bins.map((bin, i) => ({
    bin: bin,
    binLabel: bin.toFixed(3),
    count: data.histogram_counts[i] ?? 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={chartData}
        margin={{ top: 8, right: 16, bottom: 0, left: 0 }}
      >
        <CartesianGrid
          strokeDasharray="3 3"
          vertical={false}
          stroke="var(--color-surface-200)"
        />

        <XAxis
          dataKey="binLabel"
          tick={{ fontSize: 10, fill: "var(--color-surface-400)" }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
          dy={4}
        />

        <YAxis
          tick={{ fontSize: 10, fill: "var(--color-surface-400)" }}
          axisLine={false}
          tickLine={false}
          dx={-4}
          width={40}
        />

        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const item = payload[0].payload as (typeof chartData)[number];
            return (
              <div className="rounded-lg border border-surface-200 bg-white px-3 py-2 shadow-lg text-xs dark:border-surface-700 dark:bg-surface-800">
                <p className="font-medium text-surface-900 dark:text-surface-100">
                  SER: {item.binLabel}
                </p>
                <p className="mt-1 text-surface-500">
                  Count:{" "}
                  <span className="font-bold">{item.count}</span>
                </p>
              </div>
            );
          }}
        />

        {/* Mean reference */}
        <ReferenceLine
          x={data.ser_mean.toFixed(3)}
          stroke="#22c55e"
          strokeDasharray="4 4"
          strokeWidth={1.5}
          label={{
            value: `��=${formatNumber(data.ser_mean, 4)}`,
            position: "top",
            fontSize: 10,
            fill: "#22c55e",
          }}
        />

        {/* Pass threshold */}
        <ReferenceLine
          x={(0.12).toFixed(3)}
          stroke="#f59e0b"
          strokeDasharray="4 4"
          strokeWidth={1}
          label={{
            value: "Pass",
            position: "top",
            fontSize: 10,
            fill: "#f59e0b",
          }}
        />

        <Bar
          dataKey="count"
          fill="var(--color-brand-500)"
          radius={[2, 2, 0, 0]}
          animationDuration={600}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

