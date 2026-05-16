import client from "@/api/client";
import type { VisionDetectionResponse, VisionObservationAttachResponse } from "@/types/vision";

export const visionApi = {
  detect: async (file: File): Promise<VisionDetectionResponse> => {
    const body = new FormData();
    body.append("file", file);
    const { data } = await client.post<VisionDetectionResponse>("/bos/vision/detect", body, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
  listRuns: async (limit = 20): Promise<VisionDetectionResponse[]> => {
    const { data } = await client.get<VisionDetectionResponse[]>("/bos/vision/runs", {
      params: { limit },
    });
    return data;
  },
  attachRunToSignal: async (
    runId: string,
    signalBatchId: number,
  ): Promise<VisionObservationAttachResponse> => {
    const { data } = await client.post<VisionObservationAttachResponse>(
      `/bos/vision/runs/${runId}/attach`,
      { signal_batch_id: signalBatchId },
    );
    return data;
  },
};
