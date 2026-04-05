/**
 * BOS Pipeline v9.0 �� SER Gauge Chart
 *
 * Circular gauge displaying the SER value with color-coded grade arcs.
 */

import { useMemo } from "react";
import { scoreToGrade, getGradeColor } from "@/types/ser";
import { cn } from "@/lib/utils";

interface SERGaugeProps {
  value: number;
  size?: number;
  maxValue?: number;
  className?: string;
}

export function SERGauge({
  value,
  size = 160,
  maxValue = 0.3,
  className,
}: SERGaugeProps) {
  const grade = scoreToGrade(value);
  const color = getGradeColor(grade);

  // SVG arc calculations
  const {
    cx,
    radius,
    strokeWidth,
    circumference,
    offset,
  } = useMemo(() => {
    const sw = size * 0.08;
    const r = (size - sw) / 2;
    const c = Math.PI * r; // semicircle
    const clampedValue = Math.min(value / maxValue, 1);
    const o = c * (1 - clampedValue);

    return {
      cx: size / 2,
      radius: r,
      strokeWidth: sw,
      circumference: c,
      offset: o,
    };
  }, [value, size, maxValue]);

  return (
    <div
      className={cn("relative inline-flex flex-col items-center", className)}
      style={{ width: size, height: size * 0.65 }}
    >
      <svg
        width={size}
        height={size * 0.55}
        viewBox={`0 0 ${size} ${size * 0.55}`}
        className="overflow-visible"
      >
        {/* Background arc */}
        <path
          d={describeArc(cx, size * 0.52, radius, 180, 360)}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          className="text-surface-100 dark:text-surface-700"
        />

        {/* Value arc */}
        <path
          d={describeArc(cx, size * 0.52, radius, 180, 360)}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700 ease-out"
        />
      </svg>

      {/* Center label */}
      <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
        <p
          className="text-2xl font-bold"
          style={{ color }}
        >
          {value.toFixed(4)}
        </p>
        <p className="text-xs font-semibold text-surface-400 uppercase">
          Grade {grade}
        </p>
      </div>
    </div>
  );
}

// ���� SVG Arc Helper ����

function polarToCartesian(
  cx: number,
  cy: number,
  r: number,
  angleDeg: number,
): { x: number; y: number } {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad),
  };
}

function describeArc(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number,
): string {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";

  return [
    "M",
    start.x,
    start.y,
    "A",
    r,
    r,
    0,
    largeArcFlag,
    0,
    end.x,
    end.y,
  ].join(" ");
}
