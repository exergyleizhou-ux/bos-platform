import { useQuery } from "@tanstack/react-query";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { bosApi } from "@/api/bosApi";
import { batchKeys } from "@/hooks/useBatches";
import { downloadBlob } from "@/lib/utils";
import type {
  BatchGuidanceResponse,
  BioexecutorCandidateCatalogResponse,
  BrainRuntimeDocument,
  BrainRuntimeResponse,
  BrainRuntimeUpdateRequest,
  BusinessKnowledgeReviewPacketExportResponse,
  ControlAPIProfileCreate,
  ExecutorProfileCreate,
  ExternalSourceCatalogResponse,
  ExternalSourceExtractionListResponse,
  ExternalSourceProcurementSummary,
  ExternalSourceReviewCardListResponse,
  ExternalSourceReviewCardResolveRequest,
  ExternalSourceReviewCardResolveResponse,
  ExternalSourceSchemaReadinessResponse,
  FeedstockCatalogResponse,
  FeedstockCandidateCatalogResponse,
  FeedstockDatasetCandidateListResponse,
  LiteratureExtractionCandidateListResponse,
  LiteratureExtractionCandidateReviewPacketBulkExportResponse,
  LiteratureExtractionCandidateReviewPacketExportResponse,
  LiteratureExtractionEvidenceChainReadinessResponse,
  LiteratureExtractionReviewDraftCreateRequest,
  LiteratureExtractionReviewDraftComparisonResponse,
  LiteratureExtractionReviewDraftListResponse,
  LiteratureExtractionReviewDraftResponse,
  LiteratureValueOverlayCreateRequest,
  LiteratureValueOverlayResponse,
  LiteratureValuePromotionApprovalCreateRequest,
  LiteratureValuePromotionApprovalResponse,
  LiteratureValuePromotionAuditExportResponse,
  LiteratureValuePromotionLifecycleResponse,
  LiteratureValuePromotionReadinessResponse,
  LiteratureValuePromotionRejectRequest,
  LiteratureValuePromotionRequestCreateRequest,
  LiteratureValuePromotionRequestResponse,
  LiteratureValueReleaseEvidenceLinkCreateRequest,
  LiteratureValueReleaseEvidenceLinkResponse,
  LiteratureValueRollbackCreateRequest,
  LiteratureValueRollbackResponse,
  LiteratureValueRuntimeActivationCreateRequest,
  LiteratureValueRuntimeActivationDeactivateRequest,
  LiteratureValueRuntimeActivationPreviewResponse,
  LiteratureValueRuntimeActivationResponse,
  HandoverRecommendationResponse,
  LocalityProfileCreate,
  ManuscriptCampaignCatalogResponse,
  NativeModelInferenceRequest,
  NativeModelInferenceResponse,
  PortabilityAuditCreate,
  PortabilityRecommendationResponse,
  RecentTimeseriesRiskResponse,
  ReferenceIngestionHealthResponse,
  ReferenceIngestionListResponse,
  ReferenceIngestionParseRequest,
  ReferenceIngestionPromoteRequest,
  ReferenceIngestionPromoteResponse,
  ReferenceIngestionStagedItem,
  ReleaseEvaluationRequest,
  ReviewedExternalCandidateRuntimeReadinessResponse,
  ReviewedExternalCandidateLaneSummary,
  ReviewedExternalCandidateKnowledgeBaseResponse,
  ReviewedExternalCandidateListResponse,
  ReviewedExternalCandidateRollbackPreviewResponse,
  SignalCompileRequest,
  SignalBatchCreate,
  SpeciesCatalogResponse,
  SupervisorObservationRequest,
  SupervisorStateResponse,
  TimeseriesRiskResponse,
} from "@/types/bos";

export const bosKeys = {
  all: ["bos"] as const,
  signals: () => [...bosKeys.all, "signals"] as const,
  speciesCatalog: () => [...bosKeys.all, "species-catalog"] as const,
  bioexecutorCandidates: () => [...bosKeys.all, "bioexecutor-candidates"] as const,
  feedstocksCatalog: () => [...bosKeys.all, "feedstocks-catalog"] as const,
  feedstockCandidates: () => [...bosKeys.all, "feedstock-candidates"] as const,
  feedstockDatasetCandidates: () => [...bosKeys.all, "feedstock-dataset-candidates"] as const,
  literatureExtractionCandidates: () => [...bosKeys.all, "literature-extraction-candidates"] as const,
  literatureExtractionCandidateReviewPacketBulkExport: () =>
    [...bosKeys.all, "literature-extraction-candidate-review-packet-bulk-export"] as const,
  literatureExtractionCandidateReviewPacketExport: (candidateId: string) =>
    [...bosKeys.all, "literature-extraction-candidate-review-packet-export", candidateId] as const,
  literatureExtractionEvidenceChainReadiness: () =>
    [...bosKeys.all, "literature-extraction-evidence-chain-readiness"] as const,
  literatureValuePromotionReadiness: (candidateId: string) =>
    [...bosKeys.all, "literature-value-promotion-readiness", candidateId] as const,
  literatureValuePromotionLifecycle: (candidateId: string) =>
    [...bosKeys.all, "literature-value-promotion-lifecycle", candidateId] as const,
  literatureValuePromotionAuditExport: (candidateId: string) =>
    [...bosKeys.all, "literature-value-promotion-audit-export", candidateId] as const,
  literatureValueRuntimeActivationPreview: (overlayId: string) =>
    [...bosKeys.all, "literature-value-runtime-activation-preview", overlayId] as const,
  literatureExtractionReviewDrafts: () => [...bosKeys.all, "literature-extraction-review-drafts"] as const,
  literatureExtractionReviewDraftComparison: (candidateId: string, changedField?: string) =>
    [...bosKeys.all, "literature-extraction-review-draft-comparison", candidateId, changedField ?? "all"] as const,
  externalSources: () => [...bosKeys.all, "external-sources"] as const,
  externalSourceProcurementSummary: () => [...bosKeys.all, "external-source-procurement-summary"] as const,
  externalSourceSchemaReadiness: () => [...bosKeys.all, "external-source-schema-readiness"] as const,
  externalSourceReviewCards: () => [...bosKeys.all, "external-source-review-cards"] as const,
  externalSourceExtractions: () => [...bosKeys.all, "external-source-extractions"] as const,
  reviewedExternalCandidates: () => [...bosKeys.all, "reviewed-external-candidates"] as const,
  reviewedExternalCandidateSummary: () => [...bosKeys.all, "reviewed-external-candidate-summary"] as const,
  reviewedExternalCandidateKnowledgeBase: () => [...bosKeys.all, "reviewed-external-candidate-knowledge-base"] as const,
  businessKnowledgeReviewPacketExport: (itemKey: string) =>
    [...bosKeys.all, "business-knowledge-review-packet-export", itemKey] as const,
  reviewedExternalCandidateActivationPreview: (candidateId: string) =>
    [...bosKeys.all, "reviewed-external-candidate-activation-preview", candidateId] as const,
  reviewedExternalCandidateRuntimeReadiness: (candidateId: string) =>
    [...bosKeys.all, "reviewed-external-candidate-runtime-readiness", candidateId] as const,
  reviewedExternalCandidateRollbackPreview: (candidateId: string) =>
    [...bosKeys.all, "reviewed-external-candidate-rollback-preview", candidateId] as const,
  manuscriptCampaigns: () => [...bosKeys.all, "manuscript-campaigns"] as const,
  referenceIngestionHealth: () => [...bosKeys.all, "reference-ingestion-health"] as const,
  referenceIngestion: () => [...bosKeys.all, "reference-ingestion"] as const,
  referenceIngestionDetail: (itemId: string) =>
    [...bosKeys.all, "reference-ingestion", itemId] as const,
  speciesDetail: (speciesCode: string) => [...bosKeys.all, "species-detail", speciesCode] as const,
  feedstockDetail: (feedstockKey: string) => [...bosKeys.all, "feedstock-detail", feedstockKey] as const,
  manuscriptCampaign: (campaignKey: string) => [...bosKeys.all, "manuscript-campaign", campaignKey] as const,
  supervisor: (signalId: number) => [...bosKeys.all, "supervisor", signalId] as const,
  handoverRecommendation: (signalId: number) =>
    [...bosKeys.all, "handover-recommendation", signalId] as const,
  controlProfiles: () => [...bosKeys.all, "control-profiles"] as const,
  localityProfiles: () => [...bosKeys.all, "locality-profiles"] as const,
  executorProfiles: () => [...bosKeys.all, "executor-profiles"] as const,
  releaseDecisions: () => [...bosKeys.all, "release-decisions"] as const,
  portabilityAudits: () => [...bosKeys.all, "portability-audits"] as const,
  nativeModels: (batchId?: number) => [...bosKeys.all, "native-models", batchId ?? "global"] as const,
  nativeModelRuntime: () => [...bosKeys.all, "native-model-runtime"] as const,
  nativeModelDownloadPlan: (modelKey?: string) =>
    [...bosKeys.all, "native-model-download-plan", modelKey ?? "all"] as const,
  nativeModelRuns: (modelKey?: string, batchId?: number, limit = 20) =>
    [...bosKeys.all, "native-model-runs", modelKey ?? "all", batchId ?? "all", limit] as const,
  portabilityRecommendation: (
    signalBatchId: number,
    executorProfileId: number,
    localityProfileId?: number,
  ) =>
    [
      ...bosKeys.all,
      "portability-recommendation",
      signalBatchId,
      executorProfileId,
      localityProfileId ?? "default",
    ] as const,
  auditPackets: () => [...bosKeys.all, "audit-packets"] as const,
  brainRuntime: () => [...bosKeys.all, "brain-runtime"] as const,
  batchGuidance: (batchId: number) => [...bosKeys.all, "guidance", batchId] as const,
  batchGuidanceAll: () => [...bosKeys.all, "guidance"] as const,
  batchRisk: (batchId: number, horizon = 6) => [...bosKeys.all, "risk", "batch", batchId, horizon] as const,
  recentRisks: (limit = 5, horizon = 6) => [...bosKeys.all, "risk", "recent", limit, horizon] as const,
};

function retryReadOnlyReviewQuery(failureCount: number, error: unknown) {
  const status = (error as { response?: { status?: number } })?.response?.status;
  return status === 429 && failureCount < 4;
}

function reviewRetryDelay(attemptIndex: number) {
  return Math.min(2000 * (attemptIndex + 1), 8000);
}

export function useSignalBatches() {
  return useQuery({
    queryKey: bosKeys.signals(),
    queryFn: bosApi.listSignals,
    staleTime: 60_000,
  });
}

export function useSpeciesCatalog() {
  return useQuery({
    queryKey: bosKeys.speciesCatalog(),
    queryFn: (): Promise<SpeciesCatalogResponse> => bosApi.listSpecies(),
    staleTime: 5 * 60_000,
  });
}

export function useBioexecutorCandidates() {
  return useQuery({
    queryKey: bosKeys.bioexecutorCandidates(),
    queryFn: (): Promise<BioexecutorCandidateCatalogResponse> => bosApi.listBioexecutorCandidates(),
    staleTime: 5 * 60_000,
  });
}

export function useFeedstocksCatalog() {
  return useQuery({
    queryKey: bosKeys.feedstocksCatalog(),
    queryFn: (): Promise<FeedstockCatalogResponse> => bosApi.listFeedstocks(),
    staleTime: 5 * 60_000,
  });
}

export function useFeedstockCandidates() {
  return useQuery({
    queryKey: bosKeys.feedstockCandidates(),
    queryFn: (): Promise<FeedstockCandidateCatalogResponse> => bosApi.listFeedstockCandidates(),
    staleTime: 5 * 60_000,
  });
}

export function useFeedstockDatasetCandidates() {
  return useQuery({
    queryKey: bosKeys.feedstockDatasetCandidates(),
    queryFn: (): Promise<FeedstockDatasetCandidateListResponse> => bosApi.listFeedstockDatasetCandidates(),
    staleTime: 60_000,
  });
}

export function useLiteratureExtractionCandidates() {
  return useQuery({
    queryKey: bosKeys.literatureExtractionCandidates(),
    queryFn: (): Promise<LiteratureExtractionCandidateListResponse> => bosApi.listLiteratureExtractionCandidates(),
    staleTime: 60_000,
  });
}

export function useLiteratureExtractionCandidateReviewPacketExport(candidateId?: string) {
  return useQuery({
    queryKey: bosKeys.literatureExtractionCandidateReviewPacketExport(candidateId ?? ""),
    queryFn: (): Promise<LiteratureExtractionCandidateReviewPacketExportResponse> =>
      bosApi.getLiteratureExtractionCandidateReviewPacketExport(candidateId as string),
    enabled: Boolean(candidateId),
    retry: retryReadOnlyReviewQuery,
    retryDelay: reviewRetryDelay,
    staleTime: 60_000,
  });
}

export function useLiteratureExtractionCandidateReviewPacketBulkExport(enabled = true) {
  return useQuery({
    queryKey: bosKeys.literatureExtractionCandidateReviewPacketBulkExport(),
    queryFn: (): Promise<LiteratureExtractionCandidateReviewPacketBulkExportResponse> =>
      bosApi.getLiteratureExtractionCandidateReviewPacketBulkExport(),
    enabled,
    retry: retryReadOnlyReviewQuery,
    retryDelay: reviewRetryDelay,
    staleTime: 60_000,
  });
}

export function useLiteratureExtractionEvidenceChainReadiness(enabled = true) {
  return useQuery({
    queryKey: bosKeys.literatureExtractionEvidenceChainReadiness(),
    queryFn: (): Promise<LiteratureExtractionEvidenceChainReadinessResponse> =>
      bosApi.getLiteratureExtractionEvidenceChainReadiness(),
    enabled,
    retry: retryReadOnlyReviewQuery,
    retryDelay: reviewRetryDelay,
    staleTime: 30_000,
  });
}

export function useLiteratureValuePromotionReadiness(candidateId?: string) {
  return useQuery({
    queryKey: bosKeys.literatureValuePromotionReadiness(candidateId ?? ""),
    queryFn: (): Promise<LiteratureValuePromotionReadinessResponse> =>
      bosApi.getLiteratureValuePromotionReadiness(candidateId as string),
    enabled: Boolean(candidateId),
    retry: retryReadOnlyReviewQuery,
    retryDelay: reviewRetryDelay,
    staleTime: 30_000,
  });
}

export function useLiteratureValuePromotionLifecycle(candidateId?: string) {
  return useQuery({
    queryKey: bosKeys.literatureValuePromotionLifecycle(candidateId ?? ""),
    queryFn: (): Promise<LiteratureValuePromotionLifecycleResponse> =>
      bosApi.getLiteratureValuePromotionLifecycle(candidateId as string),
    enabled: Boolean(candidateId),
    retry: retryReadOnlyReviewQuery,
    retryDelay: reviewRetryDelay,
    staleTime: 30_000,
  });
}

export function useLiteratureValuePromotionAuditExport(candidateId?: string) {
  return useQuery({
    queryKey: bosKeys.literatureValuePromotionAuditExport(candidateId ?? ""),
    queryFn: (): Promise<LiteratureValuePromotionAuditExportResponse> =>
      bosApi.getLiteratureValuePromotionAuditExport(candidateId as string),
    enabled: Boolean(candidateId),
    retry: retryReadOnlyReviewQuery,
    retryDelay: reviewRetryDelay,
    staleTime: 30_000,
  });
}

export function useLiteratureValueRuntimeActivationPreview(overlayId?: string) {
  return useQuery({
    queryKey: bosKeys.literatureValueRuntimeActivationPreview(overlayId ?? ""),
    queryFn: (): Promise<LiteratureValueRuntimeActivationPreviewResponse> =>
      bosApi.getLiteratureValueRuntimeActivationPreview(overlayId as string),
    enabled: Boolean(overlayId),
    retry: retryReadOnlyReviewQuery,
    retryDelay: reviewRetryDelay,
    staleTime: 15_000,
  });
}

export function useLiteratureExtractionReviewDrafts() {
  return useQuery({
    queryKey: bosKeys.literatureExtractionReviewDrafts(),
    queryFn: (): Promise<LiteratureExtractionReviewDraftListResponse> => bosApi.listLiteratureExtractionReviewDrafts(),
    retry: false,
    staleTime: 30_000,
  });
}

export function useLiteratureExtractionReviewDraftComparison(candidateId?: string, changedField?: string) {
  return useQuery({
    queryKey: bosKeys.literatureExtractionReviewDraftComparison(candidateId ?? "", changedField),
    queryFn: (): Promise<LiteratureExtractionReviewDraftComparisonResponse> =>
      bosApi.getLiteratureExtractionReviewDraftComparison(candidateId as string, changedField),
    enabled: Boolean(candidateId),
    retry: retryReadOnlyReviewQuery,
    retryDelay: reviewRetryDelay,
    staleTime: 30_000,
  });
}

function invalidateLiteratureValuePromotionQueries(
  qc: ReturnType<typeof useQueryClient>,
  candidateId?: string,
  overlayId?: string,
) {
  qc.invalidateQueries({ queryKey: bosKeys.literatureExtractionCandidates() });
  qc.invalidateQueries({ queryKey: bosKeys.releaseDecisions() });
  if (candidateId) {
    qc.invalidateQueries({ queryKey: bosKeys.literatureValuePromotionReadiness(candidateId) });
    qc.invalidateQueries({ queryKey: bosKeys.literatureValuePromotionLifecycle(candidateId) });
    qc.invalidateQueries({ queryKey: bosKeys.literatureValuePromotionAuditExport(candidateId) });
  }
  if (overlayId) {
    qc.invalidateQueries({ queryKey: bosKeys.literatureValueRuntimeActivationPreview(overlayId) });
  }
}

export function useCreateLiteratureValuePromotionRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      candidateId,
      payload,
    }: {
      candidateId: string;
      payload: LiteratureValuePromotionRequestCreateRequest;
    }): Promise<LiteratureValuePromotionRequestResponse> =>
      bosApi.createLiteratureValuePromotionRequest(candidateId, payload),
    onSuccess: (_data, variables) => {
      toast.success("Promotion review requested");
      invalidateLiteratureValuePromotionQueries(qc, variables.candidateId);
    },
    onError: () => {
      toast.error("Failed to request promotion review");
    },
  });
}

export function useApproveLiteratureValuePromotionRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      promotionRequestId,
      payload,
    }: {
      promotionRequestId: string;
      candidateId?: string;
      payload: LiteratureValuePromotionApprovalCreateRequest;
    }): Promise<LiteratureValuePromotionApprovalResponse> =>
      bosApi.approveLiteratureValuePromotionRequest(promotionRequestId, payload),
    onSuccess: (data, variables) => {
      toast.success("Promotion review approval recorded");
      invalidateLiteratureValuePromotionQueries(qc, variables.candidateId ?? data.candidate_id);
    },
    onError: () => {
      toast.error("Failed to approve promotion review");
    },
  });
}

export function useRejectLiteratureValuePromotionRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      promotionRequestId,
      payload,
    }: {
      promotionRequestId: string;
      candidateId?: string;
      payload: LiteratureValuePromotionRejectRequest;
    }): Promise<LiteratureValuePromotionApprovalResponse> =>
      bosApi.rejectLiteratureValuePromotionRequest(promotionRequestId, payload),
    onSuccess: (data, variables) => {
      toast.success("Promotion review rejected");
      invalidateLiteratureValuePromotionQueries(qc, variables.candidateId ?? data.candidate_id);
    },
    onError: () => {
      toast.error("Failed to reject promotion review");
    },
  });
}

export function usePromoteLiteratureValueRequestToOverlay() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      promotionRequestId,
      payload,
    }: {
      promotionRequestId: string;
      candidateId?: string;
      payload: LiteratureValueOverlayCreateRequest;
    }): Promise<LiteratureValueOverlayResponse> =>
      bosApi.promoteLiteratureValueRequestToOverlay(promotionRequestId, payload),
    onSuccess: (data, variables) => {
      toast.success("Inactive literature overlay created");
      invalidateLiteratureValuePromotionQueries(qc, variables.candidateId ?? data.candidate_id, data.overlay_id);
    },
    onError: () => {
      toast.error("Failed to create inactive overlay");
    },
  });
}

export function useCreateLiteratureValueRuntimeActivation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      overlayId,
      payload,
    }: {
      overlayId: string;
      candidateId?: string;
      payload: LiteratureValueRuntimeActivationCreateRequest;
    }): Promise<LiteratureValueRuntimeActivationResponse> =>
      bosApi.createLiteratureValueRuntimeActivation(overlayId, payload),
    onSuccess: (data, variables) => {
      toast.success("Scoped literature runtime overlay activated");
      invalidateLiteratureValuePromotionQueries(qc, variables.candidateId ?? data.candidate_id, variables.overlayId);
    },
    onError: () => {
      toast.error("Failed to activate scoped literature overlay");
    },
  });
}

export function useDeactivateLiteratureValueRuntimeActivation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      activationId,
      payload,
    }: {
      activationId: string;
      candidateId?: string;
      overlayId?: string;
      payload: LiteratureValueRuntimeActivationDeactivateRequest;
    }): Promise<LiteratureValueRuntimeActivationResponse> =>
      bosApi.deactivateLiteratureValueRuntimeActivation(activationId, payload),
    onSuccess: (data, variables) => {
      toast.success("Literature runtime activation deactivated");
      invalidateLiteratureValuePromotionQueries(qc, variables.candidateId ?? data.candidate_id, variables.overlayId ?? data.overlay_id);
    },
    onError: () => {
      toast.error("Failed to deactivate literature runtime activation");
    },
  });
}

export function useRollbackLiteratureValueRuntimeActivation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      activationId,
      payload,
    }: {
      activationId: string;
      candidateId?: string;
      overlayId?: string;
      payload: LiteratureValueRollbackCreateRequest;
    }): Promise<LiteratureValueRollbackResponse> =>
      bosApi.rollbackLiteratureValueRuntimeActivation(activationId, payload),
    onSuccess: (data, variables) => {
      toast.success("Literature runtime activation rolled back");
      invalidateLiteratureValuePromotionQueries(qc, variables.candidateId ?? data.candidate_id, variables.overlayId ?? data.overlay_id);
    },
    onError: () => {
      toast.error("Failed to roll back literature runtime activation");
    },
  });
}

export function useCreateLiteratureValueReleaseEvidenceLink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      releaseDecisionId,
      payload,
    }: {
      releaseDecisionId: number;
      candidateId?: string;
      overlayId?: string;
      payload: LiteratureValueReleaseEvidenceLinkCreateRequest;
    }): Promise<LiteratureValueReleaseEvidenceLinkResponse> =>
      bosApi.createLiteratureValueReleaseEvidenceLink(releaseDecisionId, payload),
    onSuccess: (data, variables) => {
      toast.success("Literature release evidence linked for review");
      invalidateLiteratureValuePromotionQueries(qc, variables.candidateId ?? data.candidate_id, variables.overlayId ?? data.overlay_id);
    },
    onError: () => {
      toast.error("Failed to link literature release evidence");
    },
  });
}

export function useCreateLiteratureExtractionReviewDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      candidateId,
      payload,
    }: {
      candidateId: string;
      payload: LiteratureExtractionReviewDraftCreateRequest;
    }): Promise<LiteratureExtractionReviewDraftResponse> =>
      bosApi.createLiteratureExtractionReviewDraft(candidateId, payload),
    onSuccess: (_data, variables) => {
      toast.success("Review draft intent recorded");
      qc.invalidateQueries({ queryKey: bosKeys.literatureExtractionReviewDrafts() });
      qc.invalidateQueries({ queryKey: bosKeys.literatureExtractionReviewDraftComparison(variables.candidateId) });
      qc.invalidateQueries({ queryKey: bosKeys.literatureExtractionCandidates() });
    },
    onError: () => {
      toast.error("Failed to record review draft intent");
    },
  });
}

export function useExternalSources() {
  return useQuery({
    queryKey: bosKeys.externalSources(),
    queryFn: (): Promise<ExternalSourceCatalogResponse> => bosApi.listExternalSources(),
    staleTime: 60_000,
  });
}

export function useExternalSourceProcurementSummary() {
  return useQuery({
    queryKey: bosKeys.externalSourceProcurementSummary(),
    queryFn: (): Promise<ExternalSourceProcurementSummary> => bosApi.getExternalSourceProcurementSummary(),
    staleTime: 60_000,
  });
}

export function useExternalSourceSchemaReadiness() {
  return useQuery({
    queryKey: bosKeys.externalSourceSchemaReadiness(),
    queryFn: (): Promise<ExternalSourceSchemaReadinessResponse> => bosApi.getExternalSourceSchemaReadiness(),
    staleTime: 60_000,
  });
}

export function useExternalSourceReviewCards() {
  return useQuery({
    queryKey: bosKeys.externalSourceReviewCards(),
    queryFn: (): Promise<ExternalSourceReviewCardListResponse> => bosApi.listExternalSourceReviewCards(),
    staleTime: 60_000,
  });
}

export function useExternalSourceExtractions() {
  return useQuery({
    queryKey: bosKeys.externalSourceExtractions(),
    queryFn: (): Promise<ExternalSourceExtractionListResponse> => bosApi.listExternalSourceExtractions(),
    staleTime: 60_000,
  });
}

export function useResolveExternalSourceReviewCard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      cardId,
      payload,
    }: {
      cardId: string;
      payload: ExternalSourceReviewCardResolveRequest;
    }): Promise<ExternalSourceReviewCardResolveResponse> =>
      bosApi.resolveExternalSourceReviewCard(cardId, payload),
    onSuccess: () => {
      toast.success("Review action saved");
      qc.invalidateQueries({ queryKey: bosKeys.externalSourceReviewCards() });
      qc.invalidateQueries({ queryKey: bosKeys.externalSourceExtractions() });
      qc.invalidateQueries({ queryKey: bosKeys.reviewedExternalCandidates() });
      qc.invalidateQueries({ queryKey: bosKeys.reviewedExternalCandidateSummary() });
      qc.invalidateQueries({ queryKey: bosKeys.reviewedExternalCandidateKnowledgeBase() });
      qc.invalidateQueries({ queryKey: bosKeys.externalSourceSchemaReadiness() });
    },
    onError: () => {
      toast.error("Failed to save review action");
    },
  });
}

export function useReviewedExternalCandidates() {
  return useQuery({
    queryKey: bosKeys.reviewedExternalCandidates(),
    queryFn: (): Promise<ReviewedExternalCandidateListResponse> => bosApi.listReviewedExternalCandidates(),
    staleTime: 60_000,
  });
}

export function useReviewedExternalCandidateSummary() {
  return useQuery({
    queryKey: bosKeys.reviewedExternalCandidateSummary(),
    queryFn: (): Promise<ReviewedExternalCandidateLaneSummary> => bosApi.getReviewedExternalCandidateSummary(),
    staleTime: 60_000,
  });
}

export function useReviewedExternalCandidateKnowledgeBase() {
  return useQuery({
    queryKey: bosKeys.reviewedExternalCandidateKnowledgeBase(),
    queryFn: (): Promise<ReviewedExternalCandidateKnowledgeBaseResponse> =>
      bosApi.getReviewedExternalCandidateKnowledgeBase(),
    staleTime: 60_000,
  });
}

export function useBusinessKnowledgeReviewPacketExport(itemKey?: string) {
  return useQuery({
    queryKey: bosKeys.businessKnowledgeReviewPacketExport(itemKey ?? ""),
    queryFn: (): Promise<BusinessKnowledgeReviewPacketExportResponse> =>
      bosApi.getBusinessKnowledgeReviewPacketExport(itemKey as string),
    enabled: Boolean(itemKey),
    retry: retryReadOnlyReviewQuery,
    retryDelay: reviewRetryDelay,
    staleTime: 60_000,
  });
}

export function useReviewedExternalCandidateActivationPreview(candidateId?: string) {
  return useQuery({
    queryKey: bosKeys.reviewedExternalCandidateActivationPreview(candidateId ?? ""),
    queryFn: () => bosApi.getReviewedExternalCandidateActivationPreview(candidateId as string),
    enabled: Boolean(candidateId),
    retry: false,
    staleTime: 60_000,
  });
}

export function useReviewedExternalCandidateRuntimeReadiness(candidateId?: string) {
  return useQuery({
    queryKey: bosKeys.reviewedExternalCandidateRuntimeReadiness(candidateId ?? ""),
    queryFn: (): Promise<ReviewedExternalCandidateRuntimeReadinessResponse> =>
      bosApi.getReviewedExternalCandidateRuntimeReadiness(candidateId as string),
    enabled: Boolean(candidateId),
    retry: false,
    staleTime: 60_000,
  });
}

export function useReviewedExternalCandidateRollbackPreview(candidateId?: string) {
  return useQuery({
    queryKey: bosKeys.reviewedExternalCandidateRollbackPreview(candidateId ?? ""),
    queryFn: (): Promise<ReviewedExternalCandidateRollbackPreviewResponse> =>
      bosApi.getReviewedExternalCandidateRollbackPreview(candidateId as string),
    enabled: Boolean(candidateId),
    retry: false,
    staleTime: 60_000,
  });
}

export function useManuscriptCampaigns() {
  return useQuery({
    queryKey: bosKeys.manuscriptCampaigns(),
    queryFn: (): Promise<ManuscriptCampaignCatalogResponse> => bosApi.listManuscriptCampaigns(),
    staleTime: 5 * 60_000,
  });
}

export function useReferenceIngestionItems() {
  return useQuery({
    queryKey: bosKeys.referenceIngestion(),
    queryFn: (): Promise<ReferenceIngestionListResponse> => bosApi.listReferenceIngestionItems(),
    staleTime: 30_000,
  });
}

export function useReferenceIngestionHealth() {
  return useQuery({
    queryKey: bosKeys.referenceIngestionHealth(),
    queryFn: (): Promise<ReferenceIngestionHealthResponse> => bosApi.getReferenceIngestionHealth(),
    staleTime: 30_000,
  });
}

export function useReferenceIngestionItem(itemId?: string) {
  return useQuery({
    queryKey: bosKeys.referenceIngestionDetail(itemId ?? ""),
    queryFn: (): Promise<ReferenceIngestionStagedItem> => bosApi.getReferenceIngestionItem(itemId as string),
    enabled: Boolean(itemId),
    staleTime: 30_000,
  });
}

export function useParseReferenceDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReferenceIngestionParseRequest): Promise<ReferenceIngestionStagedItem> =>
      bosApi.parseReferenceDocument(payload),
    onSuccess: () => {
      toast.success("Reference document staged");
      qc.invalidateQueries({ queryKey: bosKeys.referenceIngestion() });
      qc.invalidateQueries({ queryKey: bosKeys.referenceIngestionHealth() });
    },
    onError: () => {
      toast.error("Failed to stage reference document");
    },
  });
}

export function usePromoteReferenceIngestionItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      itemId,
      payload,
    }: {
      itemId: string;
      payload?: ReferenceIngestionPromoteRequest;
    }): Promise<ReferenceIngestionPromoteResponse> =>
      bosApi.promoteReferenceIngestionItem(itemId, payload ?? { target_type: "campaign" }),
    onSuccess: () => {
      toast.success("Staged reference promoted");
      qc.invalidateQueries({ queryKey: bosKeys.referenceIngestion() });
      qc.invalidateQueries({ queryKey: bosKeys.referenceIngestionHealth() });
      qc.invalidateQueries({ queryKey: bosKeys.manuscriptCampaigns() });
    },
    onError: () => {
      toast.error("Failed to promote staged reference");
    },
  });
}

export function useSpeciesDetail(speciesCode?: string) {
  return useQuery({
    queryKey: bosKeys.speciesDetail(speciesCode ?? ""),
    queryFn: () => bosApi.getSpeciesDetail(speciesCode as string),
    enabled: Boolean(speciesCode),
    staleTime: 5 * 60_000,
  });
}

export function useFeedstockDetail(feedstockKey?: string) {
  return useQuery({
    queryKey: bosKeys.feedstockDetail(feedstockKey ?? ""),
    queryFn: () => bosApi.getFeedstockDetail(feedstockKey as string),
    enabled: Boolean(feedstockKey),
    staleTime: 5 * 60_000,
  });
}

export function useManuscriptCampaignDetail(campaignKey?: string) {
  return useQuery({
    queryKey: bosKeys.manuscriptCampaign(campaignKey ?? ""),
    queryFn: () => bosApi.getManuscriptCampaign(campaignKey as string),
    enabled: Boolean(campaignKey),
    staleTime: 5 * 60_000,
  });
}

export function useBrainRuntime() {
  return useQuery({
    queryKey: bosKeys.brainRuntime(),
    queryFn: (): Promise<BrainRuntimeResponse> => bosApi.getBrainRuntime(),
    staleTime: 30_000,
  });
}

export function useUpdateBrainRuntimeDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      documentKey,
      payload,
    }: {
      documentKey: string;
      payload: BrainRuntimeUpdateRequest;
    }): Promise<BrainRuntimeDocument> => bosApi.updateBrainRuntimeDocument(documentKey, payload),
    onSuccess: () => {
      toast.success("Brain document saved");
      qc.invalidateQueries({ queryKey: bosKeys.brainRuntime() });
    },
    onError: () => {
      toast.error("Failed to save brain document");
    },
  });
}

export function useCreateSignalBatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SignalBatchCreate) => bosApi.createSignal(payload),
    onSuccess: () => {
      toast.success("Signal batch created");
      qc.invalidateQueries({ queryKey: bosKeys.signals() });
    },
    onError: () => {
      toast.error("Failed to create signal batch");
    },
  });
}

export function useCompileSignal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SignalCompileRequest) => bosApi.compileSignal(payload),
    onSuccess: (_data, variables) => {
      toast.success("Signal compiled");
      qc.invalidateQueries({ queryKey: bosKeys.signals() });
      qc.invalidateQueries({ queryKey: bosKeys.releaseDecisions() });
      qc.invalidateQueries({ queryKey: bosKeys.portabilityAudits() });
      qc.invalidateQueries({ queryKey: bosKeys.auditPackets() });
      qc.invalidateQueries({ queryKey: bosKeys.batchGuidanceAll() });
      qc.invalidateQueries({ queryKey: batchKeys.detail(variables.batch_id) });
    },
    onError: () => {
      toast.error("Failed to compile signal");
    },
  });
}

export function useRefreshSignal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (signalId: number) => bosApi.refreshSignal(signalId),
    onSuccess: (data) => {
      toast.success("Signal state refreshed");
      qc.invalidateQueries({ queryKey: bosKeys.signals() });
      qc.invalidateQueries({ queryKey: bosKeys.releaseDecisions() });
      qc.invalidateQueries({ queryKey: bosKeys.portabilityAudits() });
      qc.invalidateQueries({ queryKey: bosKeys.auditPackets() });
      qc.invalidateQueries({ queryKey: bosKeys.batchGuidanceAll() });
      qc.invalidateQueries({ queryKey: batchKeys.detail(data.signal_batch.batch_id) });
    },
    onError: () => {
      toast.error("Failed to refresh signal state");
    },
  });
}

export function useSupervisorState(signalId?: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SupervisorObservationRequest): Promise<SupervisorStateResponse> => {
      if (!signalId) throw new Error("signalId is required for supervisor evaluation");
      return bosApi.evaluateSupervisor(signalId, payload);
    },
    onSuccess: (_data) => {
      if (signalId) {
        qc.invalidateQueries({ queryKey: bosKeys.supervisor(signalId) });
        qc.invalidateQueries({ queryKey: bosKeys.handoverRecommendation(signalId) });
      }
      qc.invalidateQueries({ queryKey: bosKeys.signals() });
      qc.invalidateQueries({ queryKey: bosKeys.auditPackets() });
      qc.invalidateQueries({ queryKey: bosKeys.releaseDecisions() });
      qc.invalidateQueries({ queryKey: bosKeys.batchGuidanceAll() });
      qc.invalidateQueries({ queryKey: batchKeys.details() });
    },
    onError: () => {
      toast.error("Failed to evaluate supervisor state");
    },
  });
}

export function useHandoverRecommendation(signalId?: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SupervisorObservationRequest): Promise<HandoverRecommendationResponse> => {
      if (!signalId) throw new Error("signalId is required for handover evaluation");
      return bosApi.getHandoverRecommendation(signalId, payload);
    },
    onSuccess: (_data) => {
      if (signalId) {
        qc.invalidateQueries({ queryKey: bosKeys.handoverRecommendation(signalId) });
        qc.invalidateQueries({ queryKey: bosKeys.supervisor(signalId) });
      }
      qc.invalidateQueries({ queryKey: bosKeys.signals() });
      qc.invalidateQueries({ queryKey: bosKeys.auditPackets() });
      qc.invalidateQueries({ queryKey: bosKeys.releaseDecisions() });
      qc.invalidateQueries({ queryKey: bosKeys.batchGuidanceAll() });
      qc.invalidateQueries({ queryKey: batchKeys.details() });
    },
    onError: () => {
      toast.error("Failed to evaluate handover recommendation");
    },
  });
}

export function useControlProfiles() {
  return useQuery({
    queryKey: bosKeys.controlProfiles(),
    queryFn: bosApi.listControlProfiles,
    staleTime: 60_000,
  });
}

export function useCreateControlProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ControlAPIProfileCreate) => bosApi.createControlProfile(payload),
    onSuccess: () => {
      toast.success("Control profile created");
      qc.invalidateQueries({ queryKey: bosKeys.controlProfiles() });
    },
    onError: () => {
      toast.error("Failed to create control profile");
    },
  });
}

export function useLocalityProfiles() {
  return useQuery({
    queryKey: bosKeys.localityProfiles(),
    queryFn: bosApi.listLocalityProfiles,
    staleTime: 60_000,
  });
}

export function useCreateLocalityProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: LocalityProfileCreate) => bosApi.createLocalityProfile(payload),
    onSuccess: () => {
      toast.success("Locality profile created");
      qc.invalidateQueries({ queryKey: bosKeys.localityProfiles() });
    },
    onError: () => {
      toast.error("Failed to create locality profile");
    },
  });
}

export function useExecutorProfiles() {
  return useQuery({
    queryKey: bosKeys.executorProfiles(),
    queryFn: bosApi.listExecutorProfiles,
    staleTime: 60_000,
  });
}

export function useCreateExecutorProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ExecutorProfileCreate) => bosApi.createExecutorProfile(payload),
    onSuccess: () => {
      toast.success("Executor profile created");
      qc.invalidateQueries({ queryKey: bosKeys.executorProfiles() });
    },
    onError: () => {
      toast.error("Failed to create executor profile");
    },
  });
}

export function useReleaseDecisions() {
  return useQuery({
    queryKey: bosKeys.releaseDecisions(),
    queryFn: bosApi.listReleaseDecisions,
    staleTime: 60_000,
  });
}

export function useEvaluateRelease() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReleaseEvaluationRequest) => bosApi.evaluateRelease(payload),
    onSuccess: () => {
      toast.success("Release decision evaluated");
      qc.invalidateQueries({ queryKey: bosKeys.releaseDecisions() });
      qc.invalidateQueries({ queryKey: bosKeys.auditPackets() });
    },
    onError: () => {
      toast.error("Failed to evaluate release");
    },
  });
}

export function usePortabilityAudits() {
  return useQuery({
    queryKey: bosKeys.portabilityAudits(),
    queryFn: bosApi.listPortabilityAudits,
    staleTime: 60_000,
  });
}

export function useNativeModels(batchId?: number) {
  return useQuery({
    queryKey: bosKeys.nativeModels(batchId),
    queryFn: () => bosApi.listNativeModels(batchId),
    staleTime: 5 * 60_000,
  });
}

export function useNativeModelRuntimeStatus() {
  return useQuery({
    queryKey: bosKeys.nativeModelRuntime(),
    queryFn: bosApi.getNativeModelRuntimeStatus,
    staleTime: 60_000,
  });
}

export function useNativeModelDownloadPlan(modelKey?: string) {
  return useQuery({
    queryKey: bosKeys.nativeModelDownloadPlan(modelKey),
    queryFn: () => bosApi.getNativeModelDownloadPlan(modelKey),
    staleTime: 60_000,
  });
}

export function useNativeModelInference() {
  return useMutation({
    mutationFn: (payload: NativeModelInferenceRequest): Promise<NativeModelInferenceResponse> =>
      bosApi.inferNativeModel(payload),
    onError: () => {
      toast.error("Failed to run native model inference");
    },
  });
}

export function useBatchTimeseriesRisk(batchId?: number, horizon = 6) {
  return useQuery({
    queryKey: bosKeys.batchRisk(batchId ?? 0, horizon),
    queryFn: (): Promise<TimeseriesRiskResponse> => bosApi.getBatchRisk(batchId as number, horizon),
    enabled: Boolean(batchId && batchId > 0),
    staleTime: 30_000,
  });
}

export function useRecentTimeseriesRisks(limit = 5, horizon = 6) {
  return useQuery({
    queryKey: bosKeys.recentRisks(limit, horizon),
    queryFn: (): Promise<RecentTimeseriesRiskResponse> => bosApi.getRecentRisks(limit, horizon),
    staleTime: 30_000,
  });
}

export function useNativeModelDownload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (modelKey: string) => bosApi.downloadNativeModel(modelKey),
    onSuccess: () => {
      toast.success("Native model artifact downloaded");
      qc.invalidateQueries({ queryKey: bosKeys.nativeModelRuntime() });
      qc.invalidateQueries({ queryKey: bosKeys.nativeModelDownloadPlan() });
    },
    onError: () => {
      toast.error("Failed to download native model artifact");
    },
  });
}

export function useNativeModelRuns(modelKey?: string, batchId?: number, limit = 20) {
  return useQuery({
    queryKey: bosKeys.nativeModelRuns(modelKey, batchId, limit),
    queryFn: () => bosApi.listNativeModelRuns(modelKey, batchId, limit),
    staleTime: 30_000,
  });
}

export function usePortabilityRecommendation(
  signalBatchId?: number,
  executorProfileId?: number,
  localityProfileId?: number,
) {
  return useQuery({
    queryKey: bosKeys.portabilityRecommendation(
      signalBatchId ?? 0,
      executorProfileId ?? 0,
      localityProfileId,
    ),
    queryFn: (): Promise<PortabilityRecommendationResponse> =>
      bosApi.getPortabilityRecommendation({
        signal_batch_id: signalBatchId as number,
        executor_profile_id: executorProfileId as number,
        locality_profile_id: localityProfileId,
      }),
    enabled: Boolean(signalBatchId && executorProfileId),
    staleTime: 30_000,
  });
}

export function useCreatePortabilityAudit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: PortabilityAuditCreate) => bosApi.createPortabilityAudit(payload),
    onSuccess: () => {
      toast.success("Portability audit created");
      qc.invalidateQueries({ queryKey: bosKeys.portabilityAudits() });
      qc.invalidateQueries({ queryKey: bosKeys.auditPackets() });
    },
    onError: () => {
      toast.error("Failed to create portability audit");
    },
  });
}

export function useAuditPackets() {
  return useQuery({
    queryKey: bosKeys.auditPackets(),
    queryFn: bosApi.listAuditPackets,
    staleTime: 60_000,
  });
}

export function useBatchGuidance(batchId: number) {
  return useQuery({
    queryKey: bosKeys.batchGuidance(batchId),
    queryFn: (): Promise<BatchGuidanceResponse> => bosApi.getBatchGuidance(batchId),
    enabled: !!batchId && batchId > 0,
    staleTime: 30_000,
  });
}

export function useExportAuditPacket() {
  return useMutation({
    mutationFn: async (variables: { batchId: number; format: "md" | "json" }) => ({
      blob: await bosApi.exportAuditPacket(variables.batchId, variables.format),
      ...variables,
    }),
    onSuccess: ({ blob, batchId, format }) => {
      downloadBlob(blob, `audit-packet-${batchId}.${format}`);
      toast.success(format === "md" ? "Technical audit report exported" : "Structured audit data exported");
    },
    onError: () => {
      toast.error("Failed to export audit packet");
    },
  });
}
