/**
 * BOS Pipeline v9.0 �� Twin API Client
 *
 * HTTP functions for digital twin CRUD and simulation.
 */

import client from "@/api/client";
import type {
  Twin,
  TwinCreate,
  TwinUpdate,
  TwinListResponse,
  TwinSimulateRequest,
  TwinSimulateResponse,
} from "@/types/twin";

export const twinApi = {
  // ���� List ����
  list: async (page: number, pageSize: number): Promise<TwinListResponse> => {
    const { data } = await client.get<TwinListResponse>("/twins", {
      params: { page, page_size: pageSize },
    });
    return data;
  },

  // ���� Detail ����
  get: async (id: number): Promise<Twin> => {
    const { data } = await client.get<Twin>(`/twins/${id}`);
    return data;
  },

  // ���� Create ����
  create: async (payload: TwinCreate): Promise<Twin> => {
    const { data } = await client.post<Twin>("/twins", payload);
    return data;
  },

  // ���� Update ����
  update: async (id: number, payload: TwinUpdate): Promise<Twin> => {
    const { data } = await client.patch<Twin>(`/twins/${id}`, payload);
    return data;
  },

  // ���� Delete ����
  delete: async (id: number): Promise<void> => {
    await client.delete(`/twins/${id}`);
  },

  // ���� Simulate ����
  simulate: async (
    id: number,
    payload: TwinSimulateRequest,
  ): Promise<TwinSimulateResponse> => {
    const { data } = await client.post<TwinSimulateResponse>(
      `/twins/${id}/simulate`,
      payload,
    );
    return data;
  },
};
