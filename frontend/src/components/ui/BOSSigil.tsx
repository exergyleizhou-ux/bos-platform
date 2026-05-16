import { Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

interface BOSSigilProps {
  className?: string;
  size?: "sm" | "md" | "lg";
  showGlyph?: boolean;
  showSignals?: boolean;
}

export function BOSSigil({
  className,
  size = "lg",
  showGlyph = false,
  showSignals = true,
}: BOSSigilProps) {
  return (
    <div className={cn("bos-sigil", `bos-sigil-${size}`, className)} aria-hidden="true">
      <div className="loading-orb-shell">
        <div className="loading-orb-image" />
        {showSignals ? (
          <>
            <div className="loading-signal loading-signal-left" />
            <div className="loading-signal loading-signal-right" />
          </>
        ) : null}
        <div className="loading-core-glow" />
        <div className="loading-core-pulse" />
        <div className="loading-ring loading-ring-outer" />
        <div className="loading-ring loading-ring-mid" />
        <div className="loading-ring loading-ring-inner" />
        {showGlyph ? (
          <div className="loading-glyph">
            <Sparkles className="h-5 w-5 text-brand-100" />
          </div>
        ) : null}
      </div>
    </div>
  );
}
