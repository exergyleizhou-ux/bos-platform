import { type HTMLAttributes, type ReactNode } from "react";
import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react";

import { translateNodeText } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { SortConfig } from "@/types/common";

interface TableProps extends HTMLAttributes<HTMLTableElement> {
  children: ReactNode;
}

export function Table({ children, className, ...props }: TableProps) {
  return (
    <div className="overflow-x-auto rounded-[24px] border border-white/8 bg-white/4">
      <table className={cn("w-full text-sm", className)} {...props}>
        {children}
      </table>
    </div>
  );
}

export function TableHead({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement> & { children: ReactNode }) {
  return (
    <thead className={cn("bg-white/6", className)} {...props}>
      {children}
    </thead>
  );
}

export function TableBody({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement> & { children: ReactNode }) {
  return (
    <tbody className={cn("divide-y divide-white/8", className)} {...props}>
      {children}
    </tbody>
  );
}

interface TableRowProps extends HTMLAttributes<HTMLTableRowElement> {
  children: ReactNode;
}

export function TableRow({ children, className, onClick, ...props }: TableRowProps) {
  return (
    <tr
      className={cn(
        "bg-transparent",
        onClick
          ? "cursor-pointer transition-colors hover:bg-white/6"
          : undefined,
        className,
      )}
      onClick={onClick}
      {...props}
    >
      {children}
    </tr>
  );
}

interface TableHeaderCellProps extends HTMLAttributes<HTMLTableCellElement> {
  children?: ReactNode;
  align?: "left" | "center" | "right";
  sortable?: boolean;
  sortField?: string;
  currentSort?: SortConfig;
  onSort?: (field: string) => void;
}

export function TableHeaderCell({
  children,
  align = "left",
  sortable,
  sortField,
  currentSort,
  onSort,
  className,
  ...props
}: TableHeaderCellProps) {
  const isActive = sortable && currentSort?.field === sortField;
  const direction = isActive ? currentSort?.direction : null;

  return (
    <th
      className={cn(
        "px-4 py-3 text-xs font-semibold uppercase tracking-[0.24em] text-surface-500",
        align === "center" && "text-center",
        align === "right" && "text-right",
        sortable && "cursor-pointer select-none transition-colors hover:text-white",
        className,
      )}
      onClick={() => {
        if (sortable && sortField && onSort) onSort(sortField);
      }}
      {...props}
    >
      <span className="inline-flex items-center gap-1">
        {translateNodeText(children)}
        {sortable ? (
          <span className="flex-shrink-0">
            {direction === "asc" ? (
              <ChevronUp className="h-3 w-3" />
            ) : direction === "desc" ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronsUpDown className="h-3 w-3 opacity-40" />
            )}
          </span>
        ) : null}
      </span>
    </th>
  );
}

interface TableCellProps extends HTMLAttributes<HTMLTableCellElement> {
  children?: ReactNode;
  align?: "left" | "center" | "right";
  mono?: boolean;
}

export function TableCell({
  children,
  align = "left",
  mono,
  className,
  ...props
}: TableCellProps) {
  return (
    <td
      className={cn(
        "px-4 py-3 text-surface-300",
        align === "center" && "text-center",
        align === "right" && "text-right",
        mono && "font-mono text-xs",
        className,
      )}
      {...props}
    >
      {children}
    </td>
  );
}

interface TableSkeletonProps {
  rows?: number;
  cols?: number;
}

export function TableSkeleton({ rows = 5, cols = 5 }: TableSkeletonProps) {
  return (
    <div className="overflow-hidden rounded-[24px] border border-white/8 bg-white/4">
      <table className="w-full">
        <thead>
          <tr className="bg-white/6">
            {Array.from({ length: cols }).map((_, colIndex) => (
              <th key={colIndex} className="px-4 py-3">
                <div className="skeleton h-3 w-16 rounded" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/8">
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <tr key={rowIndex}>
              {Array.from({ length: cols }).map((_, colIndex) => (
                <td key={colIndex} className="px-4 py-3">
                  <div
                    className="skeleton h-3 rounded"
                    style={{ width: `${50 + Math.random() * 40}%` }}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
