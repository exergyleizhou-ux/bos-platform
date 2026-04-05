import { type HTMLAttributes, type ReactNode } from "react";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";
import { panelReveal } from "@/lib/motion";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  noPadding?: boolean;
  hover?: boolean;
  tone?: "default" | "strong" | "hero";
}

export function Card({
  children,
  noPadding,
  hover,
  tone = "default",
  className,
  ...props
}: CardProps) {
  const toneClasses = {
    default: "premium-panel",
    strong: "premium-panel-strong",
    hero: "premium-hero shadow-glow",
  };

  return (
    <motion.div
      {...panelReveal}
      className={cn(hover && "transition-all hover:-translate-y-0.5")}
    >
      <div
        className={cn(
          toneClasses[tone],
          !noPadding && "p-5",
          hover && "cursor-pointer hover:shadow-card-hover",
          className,
        )}
        {...props}
      >
        {children}
      </div>
    </motion.div>
  );
}

interface CardHeaderProps {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function CardHeader({
  title,
  description,
  action,
  className,
}: CardHeaderProps) {
  return (
    <div className={cn("flex items-start justify-between gap-4", className)}>
      <div>
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        {description ? (
          <p className="mt-0.5 text-xs text-surface-400">{description}</p>
        ) : null}
      </div>
      {action ? <div className="flex-shrink-0">{action}</div> : null}
    </div>
  );
}

interface CardBodyProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function CardBody({ children, className, ...props }: CardBodyProps) {
  return (
    <div className={cn("mt-4", className)} {...props}>
      {children}
    </div>
  );
}

interface CardFooterProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function CardFooter({
  children,
  className,
  ...props
}: CardFooterProps) {
  return (
    <div
      className={cn(
        "mt-5 flex items-center justify-end gap-3 border-t border-white/8 pt-4",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: ReactNode;
  unit?: string;
  icon?: ReactNode;
  color?: "blue" | "green" | "amber" | "red" | "neutral";
  className?: string;
}

const STAT_COLORS = {
  blue: "bg-sky-500/12 text-sky-200",
  green: "bg-emerald-500/12 text-emerald-200",
  amber: "bg-amber-500/12 text-amber-200",
  red: "bg-red-500/12 text-red-200",
  neutral: "bg-white/8 text-surface-200",
} as const;

export function StatCard({
  label,
  value,
  unit,
  icon,
  color = "neutral",
  className,
}: StatCardProps) {
  return (
    <Card className={cn("flex items-center gap-4", className)}>
      {icon ? (
        <div
          className={cn(
            "flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10",
            STAT_COLORS[color],
          )}
        >
          {icon}
        </div>
      ) : null}
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-surface-400">
          {label}
        </p>
        <p className="mt-1 text-2xl font-semibold tracking-tight text-white">
          {value}
          {unit ? (
            <span className="ml-1 text-xs font-normal text-surface-400">
              {unit}
            </span>
          ) : null}
        </p>
      </div>
    </Card>
  );
}
