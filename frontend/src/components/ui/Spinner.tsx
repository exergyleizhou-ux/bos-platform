/**
 * BOS Pipeline v9.0 �� Spinner & SpinnerOverlay
 *
 * Loading spinner with optional label and overlay mode.
 */

import { cn } from "@/lib/utils";

// ���� Size Map ����
const SIZES = {
  xs: "h-3 w-3 border",
  sm: "h-5 w-5 border-2",
  md: "h-8 w-8 border-2",
  lg: "h-12 w-12 border-[3px]",
} as const;

type SpinnerSize = keyof typeof SIZES;

interface SpinnerProps {
  size?: SpinnerSize;
  className?: string;
}

export function Spinner({ size = "md", className }: SpinnerProps) {
  return (
    <div
      className={cn(
        "animate-spin rounded-full border-surface-300 border-t-brand-500 dark:border-surface-600 dark:border-t-brand-400",
        SIZES[size],
        className,
      )}
      role="status"
      aria-label="Loading"
    />
  );
}

// ���� Overlay ����
interface SpinnerOverlayProps {
  label?: string;
  size?: SpinnerSize;
  className?: string;
}

export function SpinnerOverlay({
  label,
  size = "md",
  className,
}: SpinnerOverlayProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 py-12",
        className,
      )}
    >
      <Spinner size={size} />
      {label && (
        <p className="text-sm text-surface-400 dark:text-surface-500">
          {label}
        </p>
      )}
    </div>
  );
}
