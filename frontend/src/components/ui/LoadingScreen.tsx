/**
 * BOS Pipeline v9.0 �� Loading Screen
 *
 * Full-screen loading overlay used during auth checks and lazy route loading.
 */

import { Spinner } from "@/components/ui/Spinner";
import { Leaf } from "lucide-react";

interface LoadingScreenProps {
  label?: string;
}

export function LoadingScreen({ label = "Loading��" }: LoadingScreenProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-surface-50 dark:bg-surface-950">
      {/* Logo */}
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 shadow-lg">
        <Leaf className="h-8 w-8 text-white animate-pulse" />
      </div>

      {/* Spinner */}
      <Spinner size="lg" />

      {/* Label */}
      <p className="text-sm font-medium text-surface-400 dark:text-surface-500">
        {label}
      </p>
    </div>
  );
}
