import { memo } from "react";

import { cn } from "@/lib/utils";

type PlasmaBarProps = {
  label: string;
  value: number;
  className?: string;
};

export function glowForValue(value: number) {
  if (value > 84) return "#80FFF5";
  if (value > 56) return "#1AFFE4";
  return "#00C8D4";
}

export const PlasmaBar = memo(function PlasmaBar({ label, value, className }: PlasmaBarProps) {
  const safeValue = Math.max(0, Math.min(100, Math.round(value)));
  const glow = glowForValue(safeValue);

  return (
    <div className={cn("plasma-bar", className)}>
      <div className="plasma-bar__label">
        <span>{label}</span>
        <span className="plasma-bar__value" style={{ color: glow }}>
          {safeValue}%
        </span>
      </div>
      <div className="plasma-bar__track">
        <div
          className="plasma-bar__fill"
          style={{
            width: `${safeValue}%`,
            background:
              "linear-gradient(90deg, rgba(0,132,140,0.84) 0%, rgba(0,200,212,0.92) 70%, rgba(128,255,245,0.98) 100%)",
            boxShadow: `0 0 12px ${glow}, 0 0 4px rgba(128,255,245,0.55)`,
          }}
        >
          <div className="plasma-bar__flow" />
        </div>
      </div>
    </div>
  );
});
