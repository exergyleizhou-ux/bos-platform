import client from "@/api/client";
import type {
  HumanApprovalRequest,
  HumanApprovalRequestCreate,
  ReleasePacketAttachment,
  SimulationAppendixAttachRequest,
} from "@/types/releasePackets";

export const releasePacketApi = {
  attachSimulationAppendix: async (
    releaseDecisionId: number,
    payload: SimulationAppendixAttachRequest,
  ): Promise<ReleasePacketAttachment> => {
    const { data } = await client.post<ReleasePacketAttachment>(
      `/release-packets/${releaseDecisionId}/appendices/simulation`,
      payload,
    );
    return data;
  },
  listAppendices: async (releaseDecisionId: number): Promise<ReleasePacketAttachment[]> => {
    const { data } = await client.get<ReleasePacketAttachment[]>(
      `/release-packets/${releaseDecisionId}/appendices`,
    );
    return data;
  },
  createApprovalRequest: async (
    releaseDecisionId: number,
    payload: HumanApprovalRequestCreate,
  ): Promise<HumanApprovalRequest> => {
    const { data } = await client.post<HumanApprovalRequest>(
      `/release-packets/${releaseDecisionId}/approval-requests`,
      payload,
    );
    return data;
  },
};
