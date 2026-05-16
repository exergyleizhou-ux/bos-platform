import client from "@/api/client";
import type {
  RemotionAssistantRunRequest,
  RemotionAssistantRunResponse,
  RemotionHealth,
  RemotionPreset,
  RemotionPresetCreateRequest,
  RemotionPresetUpdateRequest,
  RemotionRenderRequest,
  RemotionRenderResponse,
  RemotionSuggestRequest,
  RemotionSuggestResponse,
  RemotionTemplate,
} from "@/types/media";

export const mediaApi = {
  getHealth: async (): Promise<RemotionHealth> => {
    const { data } = await client.get<RemotionHealth>("/media/remotion/health");
    return data;
  },
  listTemplates: async (): Promise<RemotionTemplate[]> => {
    const { data } = await client.get<RemotionTemplate[]>("/media/remotion/templates");
    return data;
  },
  listPresets: async (): Promise<RemotionPreset[]> => {
    const { data } = await client.get<RemotionPreset[]>("/media/remotion/presets");
    return data;
  },
  listRenders: async (): Promise<RemotionRenderResponse[]> => {
    const { data } = await client.get<RemotionRenderResponse[]>("/media/remotion/renders");
    return data;
  },
  createPreset: async (payload: RemotionPresetCreateRequest): Promise<RemotionPreset> => {
    const { data } = await client.post<RemotionPreset>("/media/remotion/presets", payload);
    return data;
  },
  updatePreset: async (presetId: string, payload: RemotionPresetUpdateRequest): Promise<RemotionPreset> => {
    const { data } = await client.put<RemotionPreset>(`/media/remotion/presets/${encodeURIComponent(presetId)}`, payload);
    return data;
  },
  deletePreset: async (presetId: string): Promise<void> => {
    await client.delete(`/media/remotion/presets/${encodeURIComponent(presetId)}`);
  },
  render: async (payload: RemotionRenderRequest): Promise<RemotionRenderResponse> => {
    const { data } = await client.post<RemotionRenderResponse>("/media/remotion/render", payload);
    return data;
  },
  suggest: async (payload: RemotionSuggestRequest): Promise<RemotionSuggestResponse> => {
    const { data } = await client.post<RemotionSuggestResponse>("/media/remotion/suggest", payload);
    return data;
  },
  assistantRun: async (payload: RemotionAssistantRunRequest): Promise<RemotionAssistantRunResponse> => {
    const { data } = await client.post<RemotionAssistantRunResponse>("/media/remotion/assistant-run", payload);
    return data;
  },
  fetchAssetBlob: async (fileName: string): Promise<Blob> => {
    const { data } = await client.get(`/media/remotion/renders/${encodeURIComponent(fileName)}`, {
      responseType: "blob",
    });
    return data;
  },
  downloadAssetBlob: async (fileName: string): Promise<Blob> => {
    const { data } = await client.get(`/media/remotion/renders/${encodeURIComponent(fileName)}/download`, {
      responseType: "blob",
    });
    return data;
  },
};
