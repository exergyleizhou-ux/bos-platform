/**
 * BOS Pipeline v9.0 �� Common Types
 *
 * Shared type definitions used across the frontend.
 */

// ���� Sort Config ����
export interface SortConfig {
  field: string;
  direction: "asc" | "desc";
}

// ���� Paginated Response (generic) ����
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ���� API Error ����
export interface APIError {
  detail: string;
  status_code: number;
  errors?: Record<string, string[]>;
}

// ���� Select Option ����
export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

// ���� Key-Value Pair ����
export interface KeyValue<V = string> {
  key: string;
  value: V;
}

// ���� Date Range ����
export interface DateRange {
  start: string;
  end: string;
}

// ���� Generic ID Reference ����
export interface IdRef {
  id: number;
  label: string;
}

// ���� Export Format ����
export type ExportFormat = "csv" | "json" | "parquet";
