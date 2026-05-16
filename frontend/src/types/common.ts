/**
 * BOS Pipeline v9.0 common types.
 *
 * Shared type definitions used across the frontend.
 */

// Sort config
export interface SortConfig {
  field: string;
  direction: "asc" | "desc";
}

// Paginated response
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// API error
export interface APIError {
  detail: string;
  status_code: number;
  errors?: Record<string, string[]>;
}

// Select option
export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

// Key-value pair
export interface KeyValue<V = string> {
  key: string;
  value: V;
}

// Date range
export interface DateRange {
  start: string;
  end: string;
}

// Generic ID reference
export interface IdRef {
  id: number;
  label: string;
}

// Export format
export type ExportFormat = "csv" | "json" | "parquet";
