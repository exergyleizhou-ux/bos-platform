/**
 * BOS Pipeline v9.0 �� Batch Types
 *
 * Type definitions for batch records, filters, and responses.
 */

// ���� Status ����
export type BatchStatus =
  | "logged"
  | "active"
  | "completed"
  | "archived"
  | "failed";

// ���� Batch Record ����
export interface Batch {
  id: number;
  batch_id: string;
  species: string;
  status: BatchStatus;
  dm_in: number;
  dm_out: number;
  n_in: number | null;
  n_larvae: number | null;
  n_frass: number | null;
  ash_in: number | null;
  ash_out: number | null;
  fat_in: number | null;
  fat_out: number | null;
  temperature: number | null;
  moisture: number | null;
  feed_rate: number | null;
  density: number | null;
  score: number | null;
  operator: string | null;
  notes: string | null;
  batch_date: string | null;
  created_at: string;
  updated_at: string;
  ser_value?: number | null;
  grade?: string | null;
}

// ���� Create / Update ����
export interface BatchCreate {
  batch_id: string;
  species: string;
  dm_in: number;
  dm_out: number;
  n_in?: number;
  n_larvae?: number;
  n_frass?: number;
  ash_in?: number;
  ash_out?: number;
  fat_in?: number;
  fat_out?: number;
  temperature?: number;
  moisture?: number;
  feed_rate?: number;
  density?: number;
  operator?: string;
  notes?: string;
  batch_date?: string;
}

export interface BatchUpdate extends Partial<BatchCreate> {
  status?: BatchStatus;
}

// ���� Filters ����
export interface BatchFilters {
  search?: string;
  status?: BatchStatus;
  species?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

// ���� Paginated Response ����
export interface BatchListResponse {
  items: Batch[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ���� Stats ����
export interface BatchStatsResponse {
  total: number;
  by_status: Record<BatchStatus, number>;
  by_species: Record<string, number>;
  avg_ser: number | null;
}
