/**
 * BOS Pipeline v9.0 SER hooks.
 *
 * React Query hooks for SER computation, batch-level results, and history.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { serApi } from "@/api/serApi";
import { batchKeys } from "@/hooks/useBatches";
import { dashboardKeys } from "@/hooks/useDashboard";
import type { SERComputeRequest } from "@/types/ser";

// Query keys
export const serKeys = {
  all: ["ser"] as const,
  result: (batchId: number) => [...serKeys.all, "result", batchId] as const,
  history: (page: number, size: number) => [...serKeys.all, "history", page, size] as const,
};

// Compute from direct input
export function useComputeSER() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (payload: SERComputeRequest) => serApi.compute(payload),
    onSuccess: () => {
      toast.success("SER computed successfully");
      qc.invalidateQueries({ queryKey: serKeys.all });
      qc.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: () => {
      toast.error("SER computation failed");
    },
  });
}

// Compute from batch
export function useComputeSERFromBatch() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (batchId: number) => serApi.computeFromBatch(batchId),
    onSuccess: (result) => {
      toast.success(`SER: ${result.ser_value.toFixed(4)} (${result.grade})`);
      if (result.batch_id) {
        qc.setQueryData(serKeys.result(result.batch_id), result);
        qc.invalidateQueries({ queryKey: batchKeys.detail(result.batch_id) });
      }
      qc.invalidateQueries({ queryKey: serKeys.all });
      qc.invalidateQueries({ queryKey: batchKeys.lists() });
      qc.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: () => {
      toast.error("SER computation failed");
    },
  });
}

// Get SER result for a batch
export function useSERResult(batchId: number) {
  return useQuery({
    queryKey: serKeys.result(batchId),
    queryFn: async () => {
      const { data } = await (await import("@/api/client")).default.get(
        `/ser/result/batch/${batchId}`,
      );
      return data;
    },
    enabled: !!batchId && batchId > 0,
    staleTime: 2 * 60_000,
    retry: false,
  });
}

// History
export function useSERHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: serKeys.history(page, pageSize),
    queryFn: () => serApi.history(page, pageSize),
    placeholderData: (prev) => prev,
    staleTime: 30_000,
  });
}
