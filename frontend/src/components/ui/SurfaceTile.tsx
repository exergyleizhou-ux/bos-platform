import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

interface SurfaceTileProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  tone?: "default" | "subtle" | "brand" | "info" | "success" | "warning" | "danger";
}

const TONE_MAP: Record<NonNullable<SurfaceTileProps["tone"]>, string> = {
  default: "border border-white/8 bg-white/5 text-surface-300",
  subtle: "border border-white/8 bg-surface-950/55 text-surface-300",
  brand: "border border-brand-400/16 bg-brand-500/10 text-surface-200",
  info: "border border-sky-400/15 bg-sky-500/10 text-surface-200",
  success: "border border-emerald-400/15 bg-emerald-500/10 text-surface-200",
  warning: "border border-amber-400/15 bg-amber-500/10 text-surface-200",
  danger: "border border-red-400/15 bg-red-500/10 text-surface-200",
};

export function surfaceTileClasses(
  tone: NonNullable<SurfaceTileProps["tone"]> = "default",
) {
  return cn("rounded-2xl px-4 py-4", TONE_MAP[tone]);
}

export function surfaceTileButtonClasses(selected = false) {
  return selected
    ? "border-brand-300/30 bg-white/10 shadow-glow"
    : "border-white/8 bg-white/4 hover:-translate-y-0.5 hover:border-white/16 hover:bg-white/7";
}

export function surfaceActionButtonClasses(
  tone: "neutral" | "danger" = "neutral",
) {
  return tone === "danger"
    ? "rounded-2xl border border-transparent px-3 py-3 text-sm font-medium text-surface-400 transition-colors hover:border-red-400/12 hover:bg-red-500/10 hover:text-red-200"
    : "rounded-2xl border border-transparent px-3 py-3 text-sm transition-colors hover:border-white/8 hover:bg-white/6 hover:text-white";
}

export function SurfaceTile({
  children,
  tone = "default",
  className,
  ...props
}: SurfaceTileProps) {
  return (
    <div
      className={cn(surfaceTileClasses(tone), className)}
      {...props}
    >
      {children}
    </div>
  );
}

interface SurfaceTileButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  selected?: boolean;
}

export function SurfaceTileButton({
  children,
  selected = false,
  className,
  type = "button",
  ...props
}: SurfaceTileButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "rounded-2xl border px-4 py-4 text-left transition-all duration-200",
        surfaceTileButtonClasses(selected),
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
