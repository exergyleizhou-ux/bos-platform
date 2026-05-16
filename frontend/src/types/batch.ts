/**
 * BOS Pipeline v9.0 batch types.
 *
 * Type definitions for batch records, filters, and responses.
 */

import type { BatchBosOverview } from "@/types/bos";

// Status
export type BatchStatus = "logged" | "active" | "completed" | "archived" | "failed";

// Batch record
export interface Batch {
  id: number;
  batch_id: string;
  species: string;
  substrate?: string | null;
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
  bos?: BatchBosOverview | null;
}

// Create / update
export interface BatchCreate {
  batch_id: string;
  species: string;
  substrate?: string;
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

// Filters
export interface BatchFilters {
  search?: string;
  status?: BatchStatus;
  species?: string;
  substrate?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

// Paginated response
export interface BatchListResponse {
  items: Batch[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Stats
export interface BatchStatsResponse {
  total: number;
  by_status: Record<BatchStatus, number>;
  by_species: Record<string, number>;
  avg_ser: number | null;
}
