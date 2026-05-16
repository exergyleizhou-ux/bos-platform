/**
 * BOS Pipeline v9.0 pagination component.
 *
 * Page navigation with first/prev/next/last buttons and page info.
 */

import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

import { translateText } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface PaginationProps {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
  className,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className={cn("flex flex-col items-center justify-between gap-3 sm:flex-row", className)}>
      <p className="text-xs text-surface-400 dark:text-surface-500">
        {translateText("Showing")}{" "}
        <span className="font-medium text-surface-600 dark:text-surface-300">
          {start}-{end}
        </span>{" "}
        {translateText("of")}{" "}
        <span className="font-medium text-surface-600 dark:text-surface-300">{total}</span>{" "}
        {translateText("results")}
      </p>

      <div className="flex items-center gap-1">
        <PageButton onClick={() => onPageChange(1)} disabled={page <= 1} aria-label={translateText("First page")}>
          <ChevronsLeft className="h-3.5 w-3.5" />
        </PageButton>

        <PageButton
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label={translateText("Previous page")}
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </PageButton>

        {getPageNumbers(page, totalPages).map((p, i) =>
          p === "..." ? (
            <span
              key={`ellipsis-${i}`}
              className="flex h-8 w-8 items-center justify-center text-xs text-surface-400"
            >
              ...
            </span>
          ) : (
            <PageButton
              key={p}
              active={p === page}
              onClick={() => onPageChange(p as number)}
            >
              {p}
            </PageButton>
          ),
        )}

        <PageButton
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          aria-label={translateText("Next page")}
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </PageButton>

        <PageButton
          onClick={() => onPageChange(totalPages)}
          disabled={page >= totalPages}
          aria-label={translateText("Last page")}
        >
          <ChevronsRight className="h-3.5 w-3.5" />
        </PageButton>
      </div>
    </div>
  );
}

// Page button
interface PageButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

function PageButton({
  active,
  disabled,
  className,
  children,
  ...props
}: PageButtonProps) {
  return (
    <button
      disabled={disabled}
      className={cn(
        "flex h-8 min-w-[2rem] items-center justify-center rounded-lg px-2 text-xs font-medium transition-colors",
        "disabled:pointer-events-none disabled:opacity-40",
        active
          ? "bg-brand-600 text-white dark:bg-brand-500"
          : "text-surface-600 hover:bg-surface-100 dark:text-surface-400 dark:hover:bg-surface-700",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

// Page number generator
function getPageNumbers(current: number, total: number): (number | "...")[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | "...")[] = [1];

  if (current > 3) pages.push("...");

  const rangeStart = Math.max(2, current - 1);
  const rangeEnd = Math.min(total - 1, current + 1);

  for (let i = rangeStart; i <= rangeEnd; i++) {
    pages.push(i);
  }

  if (current < total - 2) pages.push("...");

  pages.push(total);
  return pages;
}
