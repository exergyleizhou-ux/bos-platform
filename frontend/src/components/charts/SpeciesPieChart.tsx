import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import type { SpeciesDistributionItem } from "@/types/dashboard";

interface SpeciesPieChartProps {
  data: SpeciesDistributionItem[];
  height?: number;
}

const COLORS = [
  "#25c897",
  "#3b82f6",
  "#f59e0b",
  "#ef4444",
  "#06b6d4",
  "#84cc16",
  "#f97316",
  "#0ea5a4",
];

export function SpeciesPieChart({ data, height = 300 }: SpeciesPieChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          dataKey="count"
          nameKey="species"
          cx="50%"
          cy="50%"
          innerRadius="55%"
          outerRadius="80%"
          paddingAngle={2}
          animationDuration={600}
        >
          {data.map((entry, index) => (
            <Cell key={entry.species} fill={COLORS[index % COLORS.length]} stroke="none" />
          ))}
        </Pie>

        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const item = payload[0].payload as SpeciesDistributionItem;

            return (
              <div className="rounded-2xl border border-white/10 bg-surface-900/95 px-3 py-2 text-xs shadow-card">
                <p className="font-medium text-white">{item.species}</p>
                <p className="mt-1 text-surface-300">
                  Count: <span className="font-bold text-white">{item.count}</span>
                </p>
                <p className="text-surface-500">{item.percentage.toFixed(1)}%</p>
              </div>
            );
          }}
        />

        <Legend
          verticalAlign="bottom"
          height={36}
          iconType="circle"
          iconSize={8}
          formatter={(value: string) => <span className="text-xs text-surface-400">{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
