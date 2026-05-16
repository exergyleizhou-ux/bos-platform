/**
 * BOS Pipeline v9.0 digital twin hooks.
 *
 * React Query hooks for twin CRUD, simulation, and cache management.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { twinApi } from "@/api/twinApi";
import { dashboardKeys } from "@/hooks/useDashboard";
import type {
  Twin,
  TwinCreate,
  TwinObservationUpdateRequest,
  TwinPredictRequest,
  TwinUpdate,
} from "@/types/twin";

export const twinKeys = {
  all: ["twins"] as const,
  lists: () => [...twinKeys.all, "list"] as const,
  list: (page: number, size: number, isActive?: boolean) =>
    [...twinKeys.lists(), page, size, isActive ?? "all"] as const,
  details: () => [...twinKeys.all, "detail"] as const,
  detail: (id: number) => [...twinKeys.details(), id] as const,
};

function getErrorMessage(error: unknown, fallback: string): string {
  return (
    (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
    fallback
  );
}

function mergeTwinRuntimeState(
  current: Twin | undefined,
  payload: { state: Twin["state"]; version: number },
): Twin | undefined {
  if (!current) return current;

  return {
    ...current,
    state: payload.state,
    version: payload.version,
  };
}

export function useTwinList(page: number, pageSize: number, isActive?: boolean) {
  return useQuery({
    queryKey: twinKeys.list(page, pageSize, isActive),
    queryFn: () => twinApi.list(page, pageSize, isActive),
    placeholderData: (prev) => prev,
    staleTime: 60_000,
  });
}

export function useTwin(id: number) {
  return useQuery({
    queryKey: twinKeys.detail(id),
    queryFn: () => twinApi.get(id),
    enabled: !!id && id > 0,
    staleTime: 60_000,
  });
}

export function useCreateTwin() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (payload: TwinCreate) => twinApi.create(payload),
    onSuccess: (twin) => {
      toast.success(`Twin "${twin.name}" created`);
      qc.invalidateQueries({ queryKey: twinKeys.lists() });
      qc.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Failed to create twin"));
    },
  });
}

export function useUpdateTwin(id: number) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (payload: TwinUpdate) => twinApi.update(id, payload),
    onSuccess: (twin) => {
      toast.success(`Twin "${twin.name}" updated`);
      qc.setQueryData(twinKeys.detail(id), twin);
      qc.invalidateQueries({ queryKey: twinKeys.lists() });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Failed to update twin"));
    },
  });
}

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
    onError: (error) => {
      toast.error(getErrorMessage(error, "Failed to delete twin"));
    },
  });
}

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
      toast.success(`Simulation complete - SER: ${result.computed_ser.toFixed(4)}`);
      qc.invalidateQueries({ queryKey: dashboardKeys.all });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Twin simulation failed"));
    },
  });
}

export function usePredictTwinStep(id: number) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (payload: TwinPredictRequest) => twinApi.predict(id, payload),
    onSuccess: (result) => {
      toast.success(`Prediction complete - instant SER: ${result.ser_instantaneous.toFixed(4)}`);
      qc.setQueryData(twinKeys.detail(id), (current: Twin | undefined) =>
        mergeTwinRuntimeState(current, { state: result.state, version: result.version }),
      );
      qc.invalidateQueries({ queryKey: twinKeys.lists() });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Twin prediction failed"));
    },
  });
}

export function useUpdateTwinObservations(id: number) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (payload: TwinObservationUpdateRequest) => twinApi.updateObservations(id, payload),
    onSuccess: (result) => {
      toast.success("Twin observations applied");
      qc.setQueryData(twinKeys.detail(id), (current: Twin | undefined) =>
        mergeTwinRuntimeState(current, { state: result.state, version: result.version }),
      );
      qc.invalidateQueries({ queryKey: twinKeys.lists() });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, "Twin observation update failed"));
    },
  });
}
