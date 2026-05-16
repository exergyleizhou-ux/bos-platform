/**
 * BOS Pipeline v9.0 SER API client.
 *
 * HTTP helpers for SER computation and history.
 */

import client from "@/api/client";
import type {
  SERComputeRequest,
  SERComputeResponse,
  SERHistoryResponse,
} from "@/types/ser";

export const serApi = {
  // Compute from direct inputs
  compute: async (payload: SERComputeRequest): Promise<SERComputeResponse> => {
    const { data } = await client.post<SERComputeResponse>("/ser/compute", payload);
    return data;
  },

  // Compute from an existing batch
  computeFromBatch: async (batchId: number): Promise<SERComputeResponse> => {
    const { data } = await client.post<SERComputeResponse>(
      `/ser/compute/batch/${batchId}`,
    );
    return data;
  },

  // History
  history: async (page: number, pageSize: number): Promise<SERHistoryResponse> => {
    const { data } = await client.get<SERHistoryResponse>("/ser/history", {
      params: { page, page_size: pageSize },
    });
    return data;
  },
};
