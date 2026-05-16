/**
 * BOS Pipeline v9.0 -Twin Trajectory Chart
 *
 * Multi-line chart showing biomass, substrate, and growth rate over time.
 */

import {
 ResponsiveContainer,
 ComposedChart,
 Line,
 XAxis,
 YAxis,
 CartesianGrid,
 Tooltip,
 Legend,
} from "recharts";
import { translateText } from "@/lib/i18n";
import { formatNumber } from "@/lib/utils";
import type { TwinTrajectoryPoint } from "@/types/twin";

interface TwinTrajectoryChartProps {
 data: TwinTrajectoryPoint[];
 height?: number;
}

export function TwinTrajectoryChart({
 data,
 height = 320,
}: TwinTrajectoryChartProps) {
 return (
 <ResponsiveContainer width="100%" height={height}>
 <ComposedChart
 data={data}
 margin={{ top: 8, right: 16, bottom: 0, left: 0 }}
 >
 <CartesianGrid
 strokeDasharray="3 3"
 vertical={false}
 stroke="var(--color-surface-200)"
 />

 <XAxis
 dataKey="time"
 tickFormatter={(v: number) => `${v}h`}
 tick={{ fontSize: 10, fill: "var(--color-surface-400)" }}
 axisLine={false}
 tickLine={false}
 dy={4}
 />

 {/* Left Y axis: mass (kg) */}
 <YAxis
 yAxisId="mass"
 orientation="left"
 tickFormatter={(v: number) => v.toFixed(1)}
 tick={{ fontSize: 10, fill: "var(--color-surface-400)" }}
 axisLine={false}
 tickLine={false}
 dx={-4}
 width={44}
 label={{
 value: "kg",
 angle: -90,
 position: "insideLeft",
 fontSize: 10,
 fill: "var(--color-surface-400)",
 offset: 10,
 }}
 />

 {/* Right Y axis: growth rate (1/h) */}
 <YAxis
 yAxisId="rate"
 orientation="right"
 tickFormatter={(v: number) => v.toFixed(3)}
 tick={{ fontSize: 10, fill: "var(--color-surface-400)" }}
 axisLine={false}
 tickLine={false}
 dx={4}
 width={52}
 label={{
 value: "1/h",
 angle: 90,
 position: "insideRight",
 fontSize: 10,
 fill: "var(--color-surface-400)",
 offset: 10,
 }}
 />

 <Tooltip
 content={({ active, payload }) => {
 if (!active || !payload?.length) return null;
 const item = payload[0].payload as TwinTrajectoryPoint;
 return (
 <div className="rounded-lg border border-surface-200 bg-white px-3 py-2 shadow-lg text-xs dark:border-surface-700 dark:bg-surface-800">
 <p className="font-medium text-surface-900 dark:text-surface-100">
 t = {item.time} h
 </p>
 <div className="mt-1 space-y-0.5">
 <p>
 <span className="inline-block w-2 h-2 rounded-full bg-green-500 mr-1.5" />
 {translateText("Biomass")}: <span className="font-bold">{formatNumber(item.biomass, 3)}</span> kg
 </p>
 <p>
 <span className="inline-block w-2 h-2 rounded-full bg-amber-500 mr-1.5" />
 {translateText("Substrate")}: <span className="font-bold">{formatNumber(item.substrate, 3)}</span> kg
 </p>
 <p>
 <span className="inline-block w-2 h-2 rounded-full bg-purple-500 mr-1.5" />
 {translateText("Growth")}: <span className="font-bold">{formatNumber(item.growth_rate, 5)}</span> 1/h
 </p>
 <p className="text-surface-400">
 T: {formatNumber(item.temperature, 1)}degC- M: {formatNumber(item.moisture, 1)}%
 </p>
 </div>
 </div>
 );
 }}
 />

 <Legend
 verticalAlign="top"
 height={28}
 iconType="line"
 iconSize={14}
 formatter={(value: string) => (
 <span className="text-xs text-surface-600 dark:text-surface-400">
 {value}
 </span>
 )}
 />

 {/* Biomass */}
 <Line
 yAxisId="mass"
 type="monotone"
 dataKey="biomass"
 name={translateText("Biomass (kg)")}
 stroke="#22c55e"
 strokeWidth={2}
 dot={false}
 animationDuration={800}
 />

 {/* Substrate */}
 <Line
 yAxisId="mass"
 type="monotone"
 dataKey="substrate"
 name={translateText("Substrate (kg)")}
 stroke="#f59e0b"
 strokeWidth={2}
 dot={false}
 animationDuration={800}
 />

 {/* Growth Rate */}
 <Line
 yAxisId="rate"
 type="monotone"
 dataKey="growth_rate"
 name={translateText("Growth Rate (1/h)")}
 stroke="#8b5cf6"
 strokeWidth={1.5}
 strokeDasharray="4 2"
 dot={false}
 animationDuration={800}
 />
 </ComposedChart>
 </ResponsiveContainer>
 );
}
