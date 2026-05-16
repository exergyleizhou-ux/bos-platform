import type { AxiosError } from "axios";

type ErrorDetail =
  | string
  | {
      detail?: unknown;
      message?: unknown;
      details?: unknown;
      errors?: unknown;
    };

interface ApiErrorSummary {
  detail: string;
  method?: string;
  status?: number;
  url?: string;
}

function normalizeDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) return detail.trim();

  if (Array.isArray(detail)) {
    const flattened = detail
      .map((entry) => normalizeDetail(entry))
      .filter((entry): entry is string => Boolean(entry));
    return flattened.length ? flattened.join("; ") : null;
  }

  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    return (
      normalizeDetail(record.detail) ??
      normalizeDetail(record.message) ??
      normalizeDetail(record.details) ??
      normalizeDetail(record.errors) ??
      null
    );
  }

  return null;
}

export function summarizeApiError(error: unknown): ApiErrorSummary {
  const axiosError = error as AxiosError<ErrorDetail> | undefined;
  const status = axiosError?.response?.status;
  const method = axiosError?.config?.method?.toUpperCase();
  const url = axiosError?.config?.url;
  const detail =
    normalizeDetail(axiosError?.response?.data) ??
    (error instanceof Error && error.message.trim() ? error.message.trim() : null) ??
    "Unknown error";

  return {
    detail,
    method,
    status,
    url,
  };
}

export function formatApiErrorDetail(label: string, error: unknown) {
  const summary = summarizeApiError(error);
  const parts = [label];

  if (summary.method && summary.url) {
    parts.push(`${summary.method} ${summary.url}`);
  } else if (summary.url) {
    parts.push(summary.url);
  }

  if (summary.status) {
    parts.push(`status ${summary.status}`);
  }

  parts.push(summary.detail);
  return parts.join(" — ");
}

export function collectApiErrorDetails(
  entries: Array<{ error: unknown; label: string }>,
) {
  return entries
    .filter((entry) => entry.error)
    .map((entry) => formatApiErrorDetail(entry.label, entry.error));
}
