/**
 * BOS Pipeline v9.0 -Forecast Chart
 *
 * Line chart showing historical values, forecast, and confidence intervals.
 */

import {
 ResponsiveContainer,
 ComposedChart,
 Line,
 Area,
 XAxis,
 YAxis,
 CartesianGrid,
 Tooltip,
 ReferenceLine,
} from "recharts";
import { translateText } from "@/lib/i18n";
import { formatNumber } from "@/lib/utils";
import type { ForecastResponse } from "@/types/simulation";

interface ForecastChartProps {
 historical: number[];
 forecast: ForecastResponse;
 height?: number;
}

export function ForecastChart({
 historical,
 forecast,
 height = 360,
}: ForecastChartProps) {
 // Build combined dataset
 const chartData = [
 // Historical points
 ...historical.map((val, i) => ({
 index: i,
 label: `H${i + 1}`,
 historical: val,
 forecast: null as number | null,
 ci_lower: null as number | null,
 ci_upper: null as number | null,
 })),
 // Bridge point (last historical = first forecast anchor)
 ...(historical.length > 0
 ? [
 {
 index: historical.length,
 label: `F1`,
 historical: null as number | null,
 forecast: forecast.forecast[0],
 ci_lower: forecast.ci_lower?.[0] ?? null,
 ci_upper: forecast.ci_upper?.[0] ?? null,
 },
 ]
 : []),
 // Forecast points
 ...forecast.forecast.slice(historical.length > 0 ? 1 : 0).map((val, i) => {
 const idx = historical.length + (historical.length > 0 ? 1 : 0) + i;
 const fi = (historical.length > 0 ? 1 : 0) + i;
 return {
 index: idx,
 label: `F${fi + 1}`,
 historical: null as number | null,
 forecast: val,
 ci_lower: forecast.ci_lower?.[fi] ?? null,
 ci_upper: forecast.ci_upper?.[fi] ?? null,
 };
 }),
 ];

 // CI as area band
 const ciData = chartData.map((d) => ({
 ...d,
 ci_band: d.ci_lower !== null && d.ci_upper !== null
 ? [d.ci_lower, d.ci_upper]
 : undefined,
 }));

 return (
 <ResponsiveContainer width="100%" height={height}>
 <ComposedChart
 data={ciData}
 margin={{ top: 8, right: 16, bottom: 0, left: 0 }}
 >
 <CartesianGrid
 strokeDasharray="3 3"
 vertical={false}
 stroke="var(--color-surface-200)"
 />

 <XAxis
 dataKey="label"
 tick={{ fontSize: 10, fill: "var(--color-surface-400)" }}
 axisLine={false}
 tickLine={false}
 dy={4}
 />

 <YAxis
 domain={["auto", "auto"]}
 tickFormatter={(v: number) => v.toFixed(3)}
 tick={{ fontSize: 10, fill: "var(--color-surface-400)" }}
 axisLine={false}
 tickLine={false}
 dx={-4}
 width={52}
 />

 <Tooltip
 content={({ active, payload }) => {
 if (!active || !payload?.length) return null;
 const item = payload[0]?.payload;
 return (
 <div className="rounded-lg border border-surface-200 bg-white px-3 py-2 shadow-lg text-xs dark:border-surface-700 dark:bg-surface-800">
 <p className="font-medium text-surface-900 dark:text-surface-100">
 {item.label}
 </p>
 {item.historical !== null && (
 <p className="text-surface-500">
 {translateText("Historical")}:{" "}
 <span className="font-bold">
 {formatNumber(item.historical, 4)}
 </span>
 </p>
 )}
 {item.forecast !== null && (
 <p className="text-brand-600 dark:text-brand-400">
 {translateText("Forecast")}:{" "}
 <span className="font-bold">
 {formatNumber(item.forecast, 4)}
 </span>
 </p>
 )}
 {item.ci_lower !== null && (
 <p className="text-surface-400">
 {translateText("CI")}: [{formatNumber(item.ci_lower, 4)},{" "}
 {formatNumber(item.ci_upper, 4)}]
 </p>
 )}
 </div>
 );
 }}
 />

 {/* Confidence Interval band */}
 <Area
 dataKey="ci_band"
 fill="var(--color-brand-200)"
 fillOpacity={0.25}
 stroke="none"
 animationDuration={400}
 />

 {/* Divider line between historical and forecast */}
 <ReferenceLine
 x={`H${historical.length}`}
 stroke="var(--color-surface-300)"
 strokeDasharray="4 4"
 strokeWidth={1}
 />

 {/* Historical line */}
 <Line
 type="monotone"
 dataKey="historical"
 stroke="var(--color-surface-500)"
 strokeWidth={2}
 dot={{ r: 3, fill: "var(--color-surface-500)", strokeWidth: 0 }}
 connectNulls={false}
 animationDuration={600}
 />

 {/* Forecast line */}
 <Line
 type="monotone"
 dataKey="forecast"
 stroke="var(--color-brand-500)"
 strokeWidth={2}
 strokeDasharray="6 3"
 dot={{ r: 3, fill: "var(--color-brand-500)", strokeWidth: 0 }}
 connectNulls={false}
 animationDuration={600}
 />
 </ComposedChart>
 </ResponsiveContainer>
 );
}
