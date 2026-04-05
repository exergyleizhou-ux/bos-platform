/**
 * BOS Pipeline v9.0 �� Batch API Client
 *
 * HTTP functions for batch CRUD, export, and aggregation.
 */

import client from "@/api/client";
import type {
  Batch,
  BatchCreate,
  BatchUpdate,
  BatchListResponse,
  BatchFilters,
  BatchStatsResponse,
} from "@/types/batch";

export const batchApi = {
  // ���� List ����
  list: async (
    page: number,
    pageSize: number,
    filters?: BatchFilters,
  ): Promise<BatchListResponse> => {
    const { data } = await client.get<BatchListResponse>("/batches", {
      params: {
        page,
        page_size: pageSize,
        search: filters?.search,
        status: filters?.status,
        species: filters?.species,
        sort_by: filters?.sort_by,
        sort_order: filters?.sort_order,
      },
    });
    return data;
  },

  // ���� Detail ����
  get: async (id: number): Promise<Batch> => {
    const { data } = await client.get<Batch>(`/batches/${id}`);
    return data;
  },

  // ���� Create ����
  create: async (payload: BatchCreate): Promise<Batch> => {
    const { data } = await client.post<Batch>("/batches", payload);
    return data;
  },

  // ���� Update ����
  update: async (id: number, payload: BatchUpdate): Promise<Batch> => {
    const { data } = await client.patch<Batch>(`/batches/${id}`, payload);
    return data;
  },

  // ���� Delete ����
  delete: async (id: number): Promise<void> => {
    await client.delete(`/batches/${id}`);
  },

  // ���� Export ����
  export: async (params: {
    format: "csv" | "json" | "parquet";
    filters?: BatchFilters;
  }): Promise<Blob> => {
    const { data } = await client.get("/batches/export", {
      params: {
        format: params.format,
        search: params.filters?.search,
        status: params.filters?.status,
        species: params.filters?.species,
      },
      responseType: "blob",
    });
    return data;
  },

  // ���� Stats ����
  stats: async (): Promise<BatchStatsResponse> => {
    const { data } = await client.get<BatchStatsResponse>("/batches/stats");
    return data;
  },
};
