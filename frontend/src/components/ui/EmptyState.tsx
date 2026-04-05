/**
 * BOS Pipeline v9.0 �� Empty State Components
 *
 * EmptyState (no data), NoResults (search), and ErrorState (error fallback).
 */

import { Inbox, SearchX, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

// �T�T�T�T�T�T�T�T�T�T�T EmptyState �T�T�T�T�T�T�T�T�T�T�T

interface EmptyStateProps {
  icon?: ReactNode;
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export function EmptyState({
  icon,
  title = "No data",
  description = "There's nothing here yet.",
  actionLabel,
  onAction,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 text-center",
        className,
      )}
    >
      <div className="mb-4 text-surface-300 dark:text-surface-600">
        {icon ?? <Inbox className="h-12 w-12" />}
      </div>
      <h3 className="text-sm font-semibold text-surface-600 dark:text-surface-400">
        {title}
      </h3>
      <p className="mt-1 max-w-xs text-xs text-surface-400 dark:text-surface-500">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button size="sm" className="mt-4" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

// �T�T�T�T�T�T�T�T�T�T�T NoResults �T�T�T�T�T�T�T�T�T�T�T

interface NoResultsProps {
  query?: string;
  onClear?: () => void;
  className?: string;
}

export function NoResults({ query, onClear, className }: NoResultsProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 text-center",
        className,
      )}
    >
      <SearchX className="mb-4 h-12 w-12 text-surface-300 dark:text-surface-600" />
      <h3 className="text-sm font-semibold text-surface-600 dark:text-surface-400">
        No results found
      </h3>
      <p className="mt-1 max-w-xs text-xs text-surface-400 dark:text-surface-500">
        {query
          ? `No items match "${query}". Try a different search or filter.`
          : "Try adjusting your filters."}
      </p>
      {onClear && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={onClear}>
          Clear Filters
        </Button>
      )}
    </div>
  );
}

// �T�T�T�T�T�T�T�T�T�T�T ErrorState �T�T�T�T�T�T�T�T�T�T�T

interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = "Something went wrong",
  description = "An error occurred while loading data. Please try again.",
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 text-center",
        className,
      )}
    >
      <AlertCircle className="mb-4 h-12 w-12 text-red-400 dark:text-red-500" />
      <h3 className="text-sm font-semibold text-surface-600 dark:text-surface-400">
        {title}
      </h3>
      <p className="mt-1 max-w-xs text-xs text-surface-400 dark:text-surface-500">
        {description}
      </p>
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

