import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import type { BatchStatus } from "@/types/batch";

const BADGE_VARIANTS = {
  brand: "border border-brand-400/20 bg-brand-500/15 text-brand-200",
  neutral: "border border-white/10 bg-white/6 text-surface-300",
  success: "border border-emerald-400/20 bg-emerald-500/15 text-emerald-200",
  warning: "border border-amber-400/20 bg-amber-500/15 text-amber-200",
  danger: "border border-red-400/20 bg-red-500/15 text-red-200",
  info: "border border-sky-400/20 bg-sky-500/15 text-sky-200",
} as const;

const BADGE_SIZES = {
  xs: "px-1.5 py-0.5 text-[10px]",
  sm: "px-2 py-0.5 text-xs",
  md: "px-2.5 py-1 text-xs",
} as const;

type BadgeVariant = keyof typeof BADGE_VARIANTS;
type BadgeSize = keyof typeof BADGE_SIZES;

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  className?: string;
}

export function Badge({
  children,
  variant = "neutral",
  size = "sm",
  dot,
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-medium whitespace-nowrap",
        BADGE_VARIANTS[variant],
        BADGE_SIZES[size],
        className,
      )}
    >
      {dot ? (
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            variant === "success" && "bg-emerald-300",
            variant === "warning" && "bg-amber-300",
            variant === "danger" && "bg-red-300",
            variant === "info" && "bg-sky-300",
            variant === "brand" && "bg-brand-300",
            variant === "neutral" && "bg-surface-300",
          )}
        />
      ) : null}
      {children}
    </span>
  );
}

const STATUS_CONFIG: Record<
  BatchStatus,
  { variant: BadgeVariant; label: string }
> = {
  logged: { variant: "neutral", label: "Logged" },
  active: { variant: "info", label: "Active" },
  completed: { variant: "success", label: "Completed" },
  archived: { variant: "neutral", label: "Archived" },
  failed: { variant: "danger", label: "Failed" },
};

interface StatusBadgeProps {
  status: BatchStatus | string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status as BatchStatus] ?? {
    variant: "neutral" as BadgeVariant,
    label: status,
  };

  return (
    <Badge variant={config.variant} size="sm" dot className={className}>
      {config.label}
    </Badge>
  );
}

const GRADE_CONFIG: Record<string, BadgeVariant> = {
  "A+": "success",
  A: "success",
  B: "brand",
  C: "warning",
  D: "warning",
  F: "danger",
};

interface GradeBadgeProps {
  grade: string;
  className?: string;
}

export function GradeBadge({ grade, className }: GradeBadgeProps) {
  const variant = GRADE_CONFIG[grade] ?? "neutral";

  return (
    <Badge variant={variant} size="sm" className={cn("font-bold", className)}>
      {grade}
    </Badge>
  );
}
