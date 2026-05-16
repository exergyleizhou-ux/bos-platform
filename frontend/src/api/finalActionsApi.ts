import client from "@/api/client";
import type {
  FinalActionAuditRecordItem,
  FinalActionAuditRecordListResponse,
  FinalActionExecutionReadinessResponse,
  FinalActionReadinessResponse,
  FinalActionRequestDraftCreateRequest,
  FinalActionRequestDraftItem,
  FinalActionRequestDraftListResponse,
  FinalActionRequestDraftResolveRequest,
  FinalExternalReleaseDeliveryRequest,
  FinalExternalReleaseShareRequest,
  FinalModelActivationRequest,
  FinalActionReviewPacketSnapshotResponse,
  FinalReleaseApprovalRequest,
} from "@/types/finalActions";

export const finalActionsApi = {
  getReadiness: async (limit = 50): Promise<FinalActionReadinessResponse> => {
    const { data } = await client.get<FinalActionReadinessResponse>("/final-actions/readiness", {
      params: { limit },
    });
    return data;
  },
  getAuditRecords: async (limit = 50): Promise<FinalActionAuditRecordListResponse> => {
    const { data } = await client.get<FinalActionAuditRecordListResponse>("/final-actions/audit-records", {
      params: { limit },
    });
    return data;
  },
  executeFinalReleaseApproval: async (payload: FinalReleaseApprovalRequest): Promise<FinalActionAuditRecordItem> => {
    const { data } = await client.post<FinalActionAuditRecordItem>("/final-actions/release-approvals", payload);
    return data;
  },
  executeFinalModelActivation: async (payload: FinalModelActivationRequest): Promise<FinalActionAuditRecordItem> => {
    const { data } = await client.post<FinalActionAuditRecordItem>("/final-actions/model-activations", payload);
    return data;
  },
  executeFinalExternalReleaseShare: async (
    payload: FinalExternalReleaseShareRequest,
  ): Promise<FinalActionAuditRecordItem> => {
    const { data } = await client.post<FinalActionAuditRecordItem>("/final-actions/external-release-shares", payload);
    return data;
  },
  executeFinalExternalReleaseDelivery: async (
    payload: FinalExternalReleaseDeliveryRequest,
  ): Promise<FinalActionAuditRecordItem> => {
    const { data } = await client.post<FinalActionAuditRecordItem>("/final-actions/external-release-deliveries", payload);
    return data;
  },
  getRequestDrafts: async (limit = 50): Promise<FinalActionRequestDraftListResponse> => {
    const { data } = await client.get<FinalActionRequestDraftListResponse>("/final-actions/request-drafts", {
      params: { limit },
    });
    return data;
  },
  createRequestDraft: async (payload: FinalActionRequestDraftCreateRequest): Promise<FinalActionRequestDraftItem> => {
    const { data } = await client.post<FinalActionRequestDraftItem>("/final-actions/request-drafts", payload);
    return data;
  },
  resolveRequestDraft: async (
    finalActionRequestId: string,
    payload: FinalActionRequestDraftResolveRequest,
  ): Promise<FinalActionRequestDraftItem> => {
    const { data } = await client.post<FinalActionRequestDraftItem>(
      `/final-actions/request-drafts/${encodeURIComponent(finalActionRequestId)}/resolve`,
      payload,
    );
    return data;
  },
  getRequestDraftExecutionReadiness: async (
    finalActionRequestId: string,
  ): Promise<FinalActionExecutionReadinessResponse> => {
    const { data } = await client.get<FinalActionExecutionReadinessResponse>(
      `/final-actions/request-drafts/${encodeURIComponent(finalActionRequestId)}/execution-readiness`,
    );
    return data;
  },
  getSourceReviewPacket: async (sourceReviewPacketId: string): Promise<FinalActionReviewPacketSnapshotResponse> => {
    const { data } = await client.get<FinalActionReviewPacketSnapshotResponse>(
      `/final-actions/source-review-packets/${encodeURIComponent(sourceReviewPacketId)}`,
    );
    return data;
  },
  getLatestSourceReviewPacket: async (): Promise<FinalActionReviewPacketSnapshotResponse> => {
    const { data } = await client.get<FinalActionReviewPacketSnapshotResponse>(
      "/final-actions/source-review-packets/latest",
    );
    return data;
  },
};
