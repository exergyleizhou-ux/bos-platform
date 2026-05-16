/**
 * BOS Pipeline v9.0 -Grade Bar Chart
 *
 * Horizontal bar chart showing SER grade distribution.
 */

import {
 ResponsiveContainer,
 BarChart,
 Bar,
 XAxis,
 YAxis,
 CartesianGrid,
 Tooltip,
 Cell,
} from "recharts";
import { getGradeColor } from "@/types/ser";
import type { GradeDistributionItem } from "@/types/dashboard";

interface GradeBarChartProps {
 data: GradeDistributionItem[];
 height?: number;
}

export function GradeBarChart({
 data,
 height = 260,
}: GradeBarChartProps) {
 // Ensure consistent grade order
 const GRADE_ORDER = ["A+", "A", "B", "C", "D", "F"];
 const ordered = GRADE_ORDER.map((g) => {
 const found = data.find((d) => d.grade === g);
 return found ?? { grade: g, count: 0, percentage: 0 };
 }).filter((d) => d.count > 0 || data.length === 0);

 return (
 <ResponsiveContainer width="100%" height={height}>
 <BarChart
 data={ordered}
 layout="vertical"
 margin={{ top: 4, right: 24, bottom: 4, left: 8 }}
 >
 <CartesianGrid
 strokeDasharray="3 3"
 horizontal={false}
 stroke="var(--color-surface-200)"
 />

 <XAxis
 type="number"
 tick={{ fontSize: 11, fill: "var(--color-surface-400)" }}
 axisLine={false}
 tickLine={false}
 />

 <YAxis
 type="category"
 dataKey="grade"
 tick={{ fontSize: 12, fontWeight: 600, fill: "var(--color-surface-500)" }}
 axisLine={false}
 tickLine={false}
 width={32}
 />

 <Tooltip
 content={({ active, payload }) => {
 if (!active || !payload?.length) return null;
 const item = payload[0].payload as GradeDistributionItem;
 return (
 <div className="rounded-2xl border border-white/10 bg-surface-900/95 px-3 py-2 text-xs shadow-card">
 <p className="font-bold text-white">
 Grade {item.grade}
 </p>
 <p className="mt-1 text-surface-300">
 Count:{" "}
 <span className="font-bold text-white">{item.count}</span>
 </p>
 <p className="text-surface-500">
 {item.percentage.toFixed(1)}%
 </p>
 </div>
 );
 }}
 />

 <Bar
 dataKey="count"
 radius={[0, 4, 4, 0]}
 animationDuration={600}
 barSize={20}
 >
 {ordered.map((entry) => (
 <Cell
 key={entry.grade}
 fill={getGradeColor(entry.grade)}
 />
 ))}
 </Bar>
 </BarChart>
 </ResponsiveContainer>
 );
}
