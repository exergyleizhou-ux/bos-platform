import client from "@/api/client";
import type {
  EvidenceItemResponse,
  EvidencePackCreate,
  EvidencePackResponse,
  InputSnapshotResponse,
} from "@/types/evidence";

export const evidenceApi = {
  createPack: async (payload: EvidencePackCreate): Promise<EvidencePackResponse> => {
    const { data } = await client.post<EvidencePackResponse>("/evidence-packs", payload);
    return data;
  },
  getPack: async (evidencePackId: string): Promise<EvidencePackResponse> => {
    const { data } = await client.get<EvidencePackResponse>(`/evidence-packs/${evidencePackId}`);
    return data;
  },
  listItems: async (evidencePackId: string): Promise<EvidenceItemResponse[]> => {
    const { data } = await client.get<EvidenceItemResponse[]>(`/evidence-packs/${evidencePackId}/items`);
    return data;
  },
  getInputSnapshot: async (inputSnapshotId: string): Promise<InputSnapshotResponse> => {
    const { data } = await client.get<InputSnapshotResponse>(`/input-snapshots/${inputSnapshotId}`);
    return data;
  },
};
