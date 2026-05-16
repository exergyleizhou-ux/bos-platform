/**
 * BOS Pipeline v9.0 -Empty State Components
 *
 * EmptyState (no data), NoResults (search), and ErrorState (error fallback).
 */

import { Inbox, SearchX, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { translateText } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

// EmptyState 

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
 "flex flex-col items-center justify-center rounded-[28px] border border-white/8 bg-white/4 px-6 py-16 text-center",
 className,
 )}
 >
 <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/6 text-surface-300">
 {icon ?? <Inbox className="h-12 w-12" />}
 </div>
 <h3 className="text-base font-semibold text-white">
 {translateText(title)}
 </h3>
 <p className="mt-2 max-w-md text-sm leading-6 text-surface-400">
 {translateText(description)}
 </p>
 {actionLabel && onAction && (
 <Button size="sm" className="mt-5" onClick={onAction}>
 {translateText(actionLabel)}
 </Button>
 )}
 </div>
 );
}

// NoResults 

interface NoResultsProps {
 query?: string;
 onClear?: () => void;
 className?: string;
}

export function NoResults({ query, onClear, className }: NoResultsProps) {
 return (
 <div
 className={cn(
 "flex flex-col items-center justify-center rounded-[28px] border border-white/8 bg-white/4 px-6 py-16 text-center",
 className,
 )}
 >
 <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/6 text-surface-300">
 <SearchX className="h-12 w-12" />
 </div>
 <h3 className="text-base font-semibold text-white">
 {translateText("No results found")}
 </h3>
 <p className="mt-2 max-w-md text-sm leading-6 text-surface-400">
 {query
 ? `${translateText("No items match")} "${query}". ${translateText("Try a different search or filter.")}`
 : translateText("Try adjusting your filters.")}
 </p>
 {onClear && (
 <Button variant="secondary" size="sm" className="mt-5" onClick={onClear}>
 {translateText("Clear Filters")}
 </Button>
 )}
 </div>
 );
}

// ErrorState 

interface ErrorStateProps {
 title?: string;
 description?: string;
 details?: string[];
 onRetry?: () => void;
 className?: string;
}

export function ErrorState({
 title = "Something went wrong",
 description = "An error occurred while loading data. Please try again.",
 details,
 onRetry,
 className,
}: ErrorStateProps) {
 return (
 <div
 className={cn(
 "flex flex-col items-center justify-center rounded-[28px] border border-red-400/15 bg-red-500/8 px-6 py-16 text-center",
 className,
 )}
 >
 <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-red-400/18 bg-red-500/12 text-red-200">
 <AlertCircle className="h-12 w-12" />
 </div>
 <h3 className="text-base font-semibold text-white">
 {translateText(title)}
 </h3>
 <p className="mt-2 max-w-md text-sm leading-6 text-surface-300">
 {translateText(description)}
 </p>
 {details?.length ? (
 <div className="mt-5 w-full max-w-2xl rounded-2xl border border-white/8 bg-surface-950/45 px-4 py-3 text-left text-xs text-surface-300">
 <p className="font-semibold uppercase tracking-[0.18em] text-surface-500">
 {translateText("Diagnostic details")}
 </p>
 <ul className="mt-3 space-y-2">
 {details.map((detail) => (
 <li key={detail} className="break-words font-mono leading-5">
 {detail}
 </li>
 ))}
 </ul>
 </div>
 ) : null}
 {onRetry && (
 <Button variant="secondary" size="sm" className="mt-5" onClick={onRetry}>
 {translateText("Retry")}
 </Button>
 )}
 </div>
 );
}

