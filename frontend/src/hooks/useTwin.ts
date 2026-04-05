/**
 * BOS Pipeline v9.0 �� Digital Twin Hooks
 *
 * React Query hooks for twin CRUD, simulation, and cache management.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { twinApi } from "@/api/twinApi";
import { dashboardKeys } from "@/hooks/useDashboard";
import type { TwinCreate, TwinUpdate } from "@/types/twin";

// ���� Query Keys ����
export const twinKeys = {
  all: ["twins"] as const,
  lists: () => [...twinKeys.all, "list"] as const,
  list: (page: number, size: number) =>
    [...twinKeys.lists(), page, size] as const,
  details: () => [...twinKeys.all, "detail"] as const,
  detail: (id: number) => [...twinKeys.details(), id] as const,
};

// ���� List ����
export function useTwinList(page: number, pageSize: number) {
  return useQuery({
    queryKey: twinKeys.list(page, pageSize),
    queryFn: () => twinApi.list(page, pageSize),
    placeholderData: (prev) => prev,
    staleTime: 60_000,
  });
}

// ���� Detail ����
export function useTwin(id: number) {
  return useQuery({
    queryKey: twinKeys.detail(id),
    queryFn: () => twinApi.get(id),
    enabled: !!id && id > 0,
    staleTime: 60_000,
  });
}

// ���� Create ����
export function useCreateTwin() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (payload: TwinCreate) => twinApi.create(payload),
    onSuccess: (twin) => {
      toast.success(`Twin "${twin.name}" created`);
      qc.invalidateQueries({ queryKey: twinKeys.lists() });
      qc.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: () => {
      toast.error("Failed to create twin");
    },
  });
}

// ���� Update ����
export function useUpdateTwin(id: number) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (payload: TwinUpdate) => twinApi.update(id, payload),
    onSuccess: (twin) => {
      toast.success(`Twin "${twin.name}" updated`);
      qc.setQueryData(twinKeys.detail(id), twin);
      qc.invalidateQueries({ queryKey: twinKeys.lists() });
    },
    onError: () => {
      toast.error("Failed to update twin");
    },
  });
}

// ���� Delete ����
export function useDeleteTwin() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: twinApi.delete,
    onSuccess: (_data, deletedId) => {
      toast.success("Twin deleted");
      qc.removeQueries({ queryKey: twinKeys.detail(deletedId) });
      qc.invalidateQueries({ queryKey: twinKeys.lists() });
      qc.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: () => {
      toast.error("Failed to delete twin");
    },
  });
}

// ���� Simulate ����
export function useSimulateTwin() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: Parameters<typeof twinApi.simulate>[1];
    }) => twinApi.simulate(id, payload),
    onSuccess: (result) => {
      toast.success(
        `Simulation complete �� SER: ${result.computed_ser.toFixed(4)}`,
      );
      qc.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: () => {
      toast.error("Twin simulation failed");
    },
  });
}
