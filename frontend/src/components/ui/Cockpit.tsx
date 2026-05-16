import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

interface CockpitPanelProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  tone?: "default" | "hero" | "rail" | "emphasis";
}

const TONE_CLASSNAME: Record<NonNullable<CockpitPanelProps["tone"]>, string> = {
  default: "cockpit-panel",
  hero: "cockpit-panel cockpit-panel-hero",
  rail: "cockpit-panel cockpit-panel-rail",
  emphasis: "cockpit-panel cockpit-panel-emphasis",
};

export function CockpitPanel({
  children,
  tone = "default",
  className,
  ...props
}: CockpitPanelProps) {
  return (
    <section className={cn(TONE_CLASSNAME[tone], className)} {...props}>
      {children}
    </section>
  );
}

export function CockpitSectionLabel({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("cockpit-section-label", className)} {...props}>
      {children}
    </p>
  );
}

interface CockpitMetricProps extends HTMLAttributes<HTMLDivElement> {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  accent?: "cyan" | "violet" | "amber" | "neutral";
}

export function CockpitMetric({
  label,
  value,
  hint,
  accent = "neutral",
  className,
  ...props
}: CockpitMetricProps) {
  return (
    <div
      className={cn("cockpit-metric", `cockpit-metric-${accent}`, className)}
      {...props}
    >
      <p className="cockpit-metric-label">{label}</p>
      <div className="cockpit-metric-value">{value}</div>
      {hint ? <p className="cockpit-metric-hint">{hint}</p> : null}
    </div>
  );
}

export function CockpitGrid({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("cockpit-grid", className)} {...props}>
      {children}
    </div>
  );
}
