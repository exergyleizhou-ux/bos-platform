import type { ReactNode } from "react";
import { motion } from "framer-motion";

import { Badge } from "@/components/ui/Badge";
import { translateNodeText, translateText } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { panelReveal } from "@/lib/motion";

interface HeroStat {
  label: string;
  value: ReactNode;
  hint?: string;
}

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  badges?: Array<{
    label: string;
    variant?: "brand" | "neutral" | "success" | "warning" | "danger" | "info";
  }>;
  stats?: HeroStat[];
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  badges,
  stats,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <motion.section
      {...panelReveal}
      className={cn("premium-hero overflow-hidden rounded-[28px] p-6 lg:p-8", className)}
    >
      <div className="relative z-[1] flex flex-col gap-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl space-y-3">
            {eyebrow ? (
              <p className="text-[0.7rem] font-semibold uppercase tracking-[0.32em] text-brand-300/90">
                {translateText(eyebrow)}
              </p>
            ) : null}
            <div className="space-y-3">
              <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                {translateText(title)}
              </h1>
              {description ? (
                <p className="max-w-2xl text-sm leading-6 text-surface-300">
                  {translateText(description)}
                </p>
              ) : null}
            </div>

            {badges?.length ? (
              <div className="flex flex-wrap gap-2">
                {badges.map((badge) => (
                  <Badge
                    key={`${badge.label}-${badge.variant ?? "neutral"}`}
                    variant={badge.variant ?? "neutral"}
                    className="border border-white/10 bg-white/5 text-white"
                  >
                    {translateText(badge.label)}
                  </Badge>
                ))}
              </div>
            ) : null}
          </div>

          {actions ? (
            <div className="flex flex-wrap items-center gap-3">{actions}</div>
          ) : null}
        </div>

        {stats?.length ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {stats.map((stat) => (
              <div
                key={stat.label}
                className="rounded-2xl border border-white/10 bg-white/6 px-4 py-4 backdrop-blur-sm"
              >
                <p className="text-[0.68rem] uppercase tracking-[0.24em] text-surface-400">
                  {translateText(stat.label)}
                </p>
                <div className="mt-3 text-2xl font-semibold text-white">
                  {translateNodeText(stat.value)}
                </div>
                {stat.hint ? (
                  <p className="mt-2 text-xs text-surface-400">{translateText(stat.hint)}</p>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </motion.section>
  );
}
