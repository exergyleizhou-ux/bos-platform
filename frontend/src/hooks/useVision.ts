import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { visionApi } from "@/api/visionApi";
import { bosKeys } from "@/hooks/useBos";
import type { VisionDetectionResponse, VisionObservationAttachResponse } from "@/types/vision";

export const visionKeys = {
  all: ["vision"] as const,
  runs: (limit = 20) => [...visionKeys.all, "runs", limit] as const,
};

export function useVisionDetection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File): Promise<VisionDetectionResponse> => visionApi.detect(file),
    onSuccess: () => {
      toast.success("Vision observation prepared for review");
      qc.invalidateQueries({ queryKey: visionKeys.all });
    },
    onError: () => {
      toast.error("Vision detection failed");
    },
  });
}

export function useVisionRuns(limit = 20) {
  return useQuery({
    queryKey: visionKeys.runs(limit),
    queryFn: () => visionApi.listRuns(limit),
    staleTime: 30_000,
  });
}

export function useAttachVisionObservation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      runId,
      signalBatchId,
    }: {
      runId: string;
      signalBatchId: number;
    }): Promise<VisionObservationAttachResponse> =>
      visionApi.attachRunToSignal(runId, signalBatchId),
    onSuccess: () => {
      toast.success("Vision observation attached to selected signal");
      qc.invalidateQueries({ queryKey: bosKeys.signals() });
      qc.invalidateQueries({ queryKey: bosKeys.auditPackets() });
      qc.invalidateQueries({ queryKey: bosKeys.releaseDecisions() });
      qc.invalidateQueries({ queryKey: bosKeys.batchGuidanceAll() });
    },
    onError: () => {
      toast.error("Failed to attach vision observation");
    },
  });
}
