/**
 * BOS Pipeline v9.0 batch hooks.
 *
 * React Query hooks for batch CRUD, export, and cache management.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { batchApi } from "@/api/batchApi";
import { dashboardKeys } from "@/hooks/useDashboard";
import { downloadBlob } from "@/lib/utils";
import type { BatchFilters, BatchUpdate } from "@/types/batch";

// Query keys
export const batchKeys = {
  all: ["batches"] as const,
  lists: () => [...batchKeys.all, "list"] as const,
  list: (page: number, size: number, filters?: BatchFilters) =>
    [...batchKeys.lists(), page, size, filters] as const,
  details: () => [...batchKeys.all, "detail"] as const,
  detail: (id: number) => [...batchKeys.details(), id] as const,
  stats: () => [...batchKeys.all, "stats"] as const,
};

// List
export function useBatchList(page: number, pageSize: number, filters?: BatchFilters) {
  return useQuery({
    queryKey: batchKeys.list(page, pageSize, filters),
    queryFn: () => batchApi.list(page, pageSize, filters),
    placeholderData: (prev) => prev,
    staleTime: 30_000,
  });
}

// Detail
export function useBatch(id: number) {
  return useQuery({
    queryKey: batchKeys.detail(id),
    queryFn: () => batchApi.get(id),
    enabled: !!id && id > 0,
    staleTime: 60_000,
  });
}

// Create
export function useCreateBatch() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: batchApi.create,
    onSuccess: (batch) => {
      toast.success(`Batch "${batch.batch_id}" created`);
      qc.invalidateQueries({ queryKey: batchKeys.lists() });
      qc.invalidateQueries({ queryKey: batchKeys.stats() });
      qc.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: () => {
      toast.error("Failed to create batch");
    },
  });
}

// Update
export function useUpdateBatch(id: number) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (payload: BatchUpdate) => batchApi.update(id, payload),
    onSuccess: (batch) => {
      toast.success(`Batch "${batch.batch_id}" updated`);
      qc.setQueryData(batchKeys.detail(id), batch);
      qc.invalidateQueries({ queryKey: batchKeys.lists() });
      qc.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: () => {
      toast.error("Failed to update batch");
    },
  });
}

// Delete
export function useDeleteBatch() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: batchApi.delete,
    onSuccess: (_data, deletedId) => {
      toast.success("Batch deleted");
      qc.removeQueries({ queryKey: batchKeys.detail(deletedId) });
      qc.invalidateQueries({ queryKey: batchKeys.lists() });
      qc.invalidateQueries({ queryKey: batchKeys.stats() });
      qc.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: () => {
      toast.error("Failed to delete batch");
    },
  });
}

// Export
export function useExportBatches() {
  return useMutation({
    mutationFn: batchApi.export,
    onSuccess: (blob, variables) => {
      const ext = variables.format;
      const filename = `batches-export-${Date.now()}.${ext}`;
      downloadBlob(blob, filename);
      toast.success(`Exported as ${ext.toUpperCase()}`);
    },
    onError: () => {
      toast.error("Export failed");
    },
  });
}

// Stats
export function useBatchStats() {
  return useQuery({
    queryKey: batchKeys.stats(),
    queryFn: batchApi.stats,
    staleTime: 2 * 60_000,
  });
}
