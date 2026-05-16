import client from "@/api/client";
import type {
  AssistantConfirmRequest,
  AssistantReviewHumanApprovalItem,
  AssistantReviewWorkbenchResponse,
  AssistantRunCreate,
  AssistantRunResponse,
  AssistantToolCall,
  HumanApprovalResolveRequest,
} from "@/types/assistant";
import type { FinalActionReviewPacketSnapshotResponse } from "@/types/finalActions";

export const assistantApi = {
  createRun: async (payload: AssistantRunCreate): Promise<AssistantRunResponse> => {
    const { data } = await client.post<AssistantRunResponse>("/assistant/runs", payload);
    return data;
  },
  getRun: async (runId: string): Promise<AssistantRunResponse> => {
    const { data } = await client.get<AssistantRunResponse>(`/assistant/runs/${runId}`);
    return data;
  },
  listRuns: async (limit = 10): Promise<AssistantRunResponse[]> => {
    const { data } = await client.get<AssistantRunResponse[]>("/assistant/runs", { params: { limit } });
    return data;
  },
  getReviewWorkbench: async (status = "pending", limit = 50): Promise<AssistantReviewWorkbenchResponse> => {
    const { data } = await client.get<AssistantReviewWorkbenchResponse>("/assistant/review-workbench", {
      params: { status, limit },
    });
    return data;
  },
  exportReviewWorkbenchAuditPacket: async (format: "md" | "json" = "md", limit = 50): Promise<Blob> => {
    const { data } = await client.get("/assistant/review-workbench/audit-packet", {
      params: { format, limit },
      responseType: "blob",
    });
    return data;
  },
  persistReviewWorkbenchAuditPacketSnapshot: async (
    limit = 50,
  ): Promise<FinalActionReviewPacketSnapshotResponse> => {
    const { data } = await client.post<FinalActionReviewPacketSnapshotResponse>(
      "/assistant/review-workbench/audit-packet/snapshot",
      null,
      { params: { limit } },
    );
    return data;
  },
  resolveHumanApprovalRequest: async (
    approvalRequestId: string,
    payload: HumanApprovalResolveRequest,
  ): Promise<AssistantReviewHumanApprovalItem> => {
    const { data } = await client.post<AssistantReviewHumanApprovalItem>(
      `/assistant/review-workbench/human-approval-requests/${approvalRequestId}/resolve`,
      payload,
    );
    return data;
  },
  listToolCalls: async (runId: string): Promise<AssistantToolCall[]> => {
    const { data } = await client.get<AssistantToolCall[]>(`/assistant/runs/${runId}/tool-calls`);
    return data;
  },
  confirm: async (runId: string, payload: AssistantConfirmRequest): Promise<AssistantRunResponse> => {
    const { data } = await client.post<AssistantRunResponse>(`/assistant/runs/${runId}/confirm`, payload);
    return data;
  },
};
