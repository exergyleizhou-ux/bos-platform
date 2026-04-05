/**
 * BOS Pipeline v9.0 �� Tooltip Component
 *
 * Simple hover tooltip using CSS-only approach with data attributes.
 * No external library required.
 */

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type TooltipPosition = "top" | "bottom" | "left" | "right";

interface TooltipProps {
  content: string;
  children: ReactNode;
  position?: TooltipPosition;
  className?: string;
}

const positionStyles: Record<TooltipPosition, string> = {
  top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
  bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
  left: "right-full top-1/2 -translate-y-1/2 mr-2",
  right: "left-full top-1/2 -translate-y-1/2 ml-2",
};

const arrowStyles: Record<TooltipPosition, string> = {
  top: "top-full left-1/2 -translate-x-1/2 border-t-surface-800 dark:border-t-surface-200 border-x-transparent border-b-transparent",
  bottom:
    "bottom-full left-1/2 -translate-x-1/2 border-b-surface-800 dark:border-b-surface-200 border-x-transparent border-t-transparent",
  left: "left-full top-1/2 -translate-y-1/2 border-l-surface-800 dark:border-l-surface-200 border-y-transparent border-r-transparent",
  right:
    "right-full top-1/2 -translate-y-1/2 border-r-surface-800 dark:border-r-surface-200 border-y-transparent border-l-transparent",
};

export function Tooltip({
  content,
  children,
  position = "top",
  className,
}: TooltipProps) {
  if (!content) return <>{children}</>;

  return (
    <div className={cn("group relative inline-flex", className)}>
      {children}

      {/* Tooltip bubble */}
      <div
        role="tooltip"
        className={cn(
          "pointer-events-none absolute z-50 whitespace-nowrap rounded-lg bg-surface-800 px-2.5 py-1.5 text-xs font-medium text-white shadow-lg",
          "dark:bg-surface-200 dark:text-surface-900",
          "opacity-0 transition-opacity duration-150 group-hover:opacity-100",
          positionStyles[position],
        )}
      >
        {content}

        {/* Arrow */}
        <span
          className={cn(
            "absolute h-0 w-0 border-4",
            arrowStyles[position],
          )}
        />
      </div>
    </div>
  );
}
