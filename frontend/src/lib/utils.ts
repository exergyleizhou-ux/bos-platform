import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import { getLocale, translateText } from "@/lib/i18n";

const EMPTY_VALUE = "N/A";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatNumber(
  value: number | null | undefined,
  decimals: number = 2,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY_VALUE;
  return value.toFixed(decimals);
}

export function formatPercent(
  value: number | null | undefined,
  decimals: number = 1,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY_VALUE;
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatCompact(value: number): string {
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toString();
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return EMPTY_VALUE;
  try {
    return new Date(dateStr).toLocaleDateString(getLocale(), {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return EMPTY_VALUE;
  try {
    return new Date(dateStr).toLocaleString(getLocale(), {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export function formatShortDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString(getLocale(), {
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function formatRelativeTime(dateStr: string): string {
  try {
    const now = Date.now();
    const then = new Date(dateStr).getTime();
    const diffSec = Math.floor((now - then) / 1000);
    const formatter = new Intl.RelativeTimeFormat(getLocale(), { numeric: "auto" });

    if (diffSec < 60) return translateText("just now");
    if (diffSec < 3600) {
      const mins = Math.floor(diffSec / 60);
      return formatter.format(-mins, "minute");
    }
    if (diffSec < 86400) {
      const hours = Math.floor(diffSec / 3600);
      return formatter.format(-hours, "hour");
    }
    if (diffSec < 604800) {
      const days = Math.floor(diffSec / 86400);
      return formatter.format(-days, "day");
    }
    return formatDate(dateStr);
  } catch {
    return dateStr;
  }
}

export function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return `${str.slice(0, maxLen - 1)}...`;
}

export function capitalize(str: string): string {
  if (!str) return str;
  return str.charAt(0).toUpperCase() + str.slice(1);
}

export function slugify(str: string): string {
  return str
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_]+/g, "-")
    .replace(/--+/g, "-")
    .trim();
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function uid(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}
