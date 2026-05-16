import client from "@/api/client";
import type {
  AuditPacket,
  BatchGuidanceResponse,
  BioexecutorCandidateCatalogResponse,
  BrainRuntimeResponse,
  BrainRuntimeDocument,
  BrainRuntimeUpdateRequest,
  BusinessKnowledgeReviewPacketExportResponse,
  ControlAPIProfileCreate,
  ControlAPIProfile,
  ExternalSourceCatalogResponse,
  ExternalSourceExtractionListResponse,
  ExternalSourcePhase4AReviewedCandidateFillResponse,
  ExternalSourceProcurementSummary,
  ExternalSourceReviewCardListResponse,
  ExternalSourceReviewCardResolveRequest,
  ExternalSourceReviewCardResolveResponse,
  ExternalSourceSchemaReadinessResponse,
  ExecutorProfile,
  ExecutorProfileCreate,
  HandoverRecommendationResponse,
  LocalityProfile,
  LocalityProfileCreate,
  NativeModelCatalog,
  NativeModelDownloadPlan,
  NativeModelDownloadResponse,
  NativeModelInferenceRequest,
  NativeModelInferenceResponse,
  NativeModelRunArtifact,
  NativeModelRuntimeStatus,
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
  ManuscriptCampaignCatalogResponse,
  PortabilityAudit,
  PortabilityAuditCreate,
  PortabilityRecommendationRequest,
  PortabilityRecommendationResponse,
  RecentTimeseriesRiskResponse,
  ReferenceIngestionHealthResponse,
  ReferenceIngestionListResponse,
  ReferenceIngestionParseRequest,
  ReferenceIngestionPromoteRequest,
  ReferenceIngestionPromoteResponse,
  ReferenceIngestionStagedItem,
  ReleaseDecision,
  ReleaseEvaluationRequest,
  ReviewedExternalCandidateActivationPreviewResponse,
  ReviewedExternalCandidateLaneSummary,
  ReviewedExternalCandidateKnowledgeBaseResponse,
  ReviewedExternalCandidateListResponse,
  ReviewedExternalCandidateRollbackPreviewResponse,
  ReviewedExternalCandidateRuntimeReadinessResponse,
  SignalCompileRequest,
  SignalCompileResponse,
  SignalRefreshResponse,
  SignalBatchCreate,
  SignalBatch,
  SpeciesCatalogResponse,
  SupervisorObservationRequest,
  SupervisorStateResponse,
  TimeseriesRiskResponse,
} from "@/types/bos";

export const bosApi = {
  listSignals: async (): Promise<SignalBatch[]> => {
    const { data } = await client.get<SignalBatch[]>("/signals");
    return data;
  },
  listSpecies: async (): Promise<SpeciesCatalogResponse> => {
    const { data } = await client.get<SpeciesCatalogResponse>("/species");
    return data;
  },
  listBioexecutorCandidates: async (): Promise<BioexecutorCandidateCatalogResponse> => {
    const { data } = await client.get<BioexecutorCandidateCatalogResponse>("/species/candidates");
    return data;
  },
  getSpeciesDetail: async (speciesCode: string) => {
    const { data } = await client.get(`/species/${speciesCode}`);
    return data;
  },
  listFeedstocks: async (): Promise<FeedstockCatalogResponse> => {
    const { data } = await client.get<FeedstockCatalogResponse>("/feedstocks");
    return data;
  },
  listFeedstockCandidates: async (): Promise<FeedstockCandidateCatalogResponse> => {
    const { data } = await client.get<FeedstockCandidateCatalogResponse>("/feedstocks/candidates");
    return data;
  },
  listFeedstockDatasetCandidates: async (): Promise<FeedstockDatasetCandidateListResponse> => {
    const { data } = await client.get<FeedstockDatasetCandidateListResponse>("/external-sources/feedstock-dataset-candidates");
    return data;
  },
  listLiteratureExtractionCandidates: async (): Promise<LiteratureExtractionCandidateListResponse> => {
    const { data } = await client.get<LiteratureExtractionCandidateListResponse>("/external-sources/literature-extraction-candidates");
    return data;
  },
  getLiteratureExtractionCandidateReviewPacketExport: async (
    candidateId: string,
  ): Promise<LiteratureExtractionCandidateReviewPacketExportResponse> => {
    const { data } = await client.get<LiteratureExtractionCandidateReviewPacketExportResponse>(
      `/external-sources/literature-extraction-candidates/${candidateId}/review-packet/export`,
    );
    return data;
  },
  getLiteratureExtractionCandidateReviewPacketBulkExport: async (): Promise<LiteratureExtractionCandidateReviewPacketBulkExportResponse> => {
    const { data } = await client.get<LiteratureExtractionCandidateReviewPacketBulkExportResponse>(
      "/external-sources/literature-extraction-candidates/review-packets/export",
    );
    return data;
  },
  getLiteratureExtractionEvidenceChainReadiness: async (): Promise<LiteratureExtractionEvidenceChainReadinessResponse> => {
    const { data } = await client.get<LiteratureExtractionEvidenceChainReadinessResponse>(
      "/external-sources/literature-extraction-candidates/evidence-chain/readiness",
    );
    return data;
  },
  getLiteratureValuePromotionReadiness: async (
    candidateId: string,
  ): Promise<LiteratureValuePromotionReadinessResponse> => {
    const { data } = await client.get<LiteratureValuePromotionReadinessResponse>(
      `/external-sources/literature-extraction-candidates/${candidateId}/promotion-readiness`,
    );
    return data;
  },
  getLiteratureValuePromotionLifecycle: async (
    candidateId: string,
  ): Promise<LiteratureValuePromotionLifecycleResponse> => {
    const { data } = await client.get<LiteratureValuePromotionLifecycleResponse>(
      `/external-sources/literature-extraction-candidates/${candidateId}/promotion-lifecycle`,
    );
    return data;
  },
  getLiteratureValuePromotionAuditExport: async (
    candidateId: string,
  ): Promise<LiteratureValuePromotionAuditExportResponse> => {
    const { data } = await client.get<LiteratureValuePromotionAuditExportResponse>(
      `/external-sources/literature-extraction-candidates/${candidateId}/promotion-audit/export`,
    );
    return data;
  },
  createLiteratureValuePromotionRequest: async (
    candidateId: string,
    payload: LiteratureValuePromotionRequestCreateRequest,
  ): Promise<LiteratureValuePromotionRequestResponse> => {
    const { data } = await client.post<LiteratureValuePromotionRequestResponse>(
      `/external-sources/literature-extraction-candidates/${candidateId}/promotion-requests`,
      payload,
    );
    return data;
  },
  approveLiteratureValuePromotionRequest: async (
    promotionRequestId: string,
    payload: LiteratureValuePromotionApprovalCreateRequest,
  ): Promise<LiteratureValuePromotionApprovalResponse> => {
    const { data } = await client.post<LiteratureValuePromotionApprovalResponse>(
      `/external-sources/promotion-requests/${promotionRequestId}/approvals`,
      payload,
    );
    return data;
  },
  rejectLiteratureValuePromotionRequest: async (
    promotionRequestId: string,
    payload: LiteratureValuePromotionRejectRequest,
  ): Promise<LiteratureValuePromotionApprovalResponse> => {
    const { data } = await client.post<LiteratureValuePromotionApprovalResponse>(
      `/external-sources/promotion-requests/${promotionRequestId}/reject`,
      payload,
    );
    return data;
  },
  promoteLiteratureValueRequestToOverlay: async (
    promotionRequestId: string,
    payload: LiteratureValueOverlayCreateRequest,
  ): Promise<LiteratureValueOverlayResponse> => {
    const { data } = await client.post<LiteratureValueOverlayResponse>(
      `/external-sources/promotion-requests/${promotionRequestId}/promote-overlay`,
      payload,
    );
    return data;
  },
  getLiteratureValueRuntimeActivationPreview: async (
    overlayId: string,
  ): Promise<LiteratureValueRuntimeActivationPreviewResponse> => {
    const { data } = await client.get<LiteratureValueRuntimeActivationPreviewResponse>(
      `/external-sources/overlays/${overlayId}/activation-preview`,
    );
    return data;
  },
  createLiteratureValueRuntimeActivation: async (
    overlayId: string,
    payload: LiteratureValueRuntimeActivationCreateRequest,
  ): Promise<LiteratureValueRuntimeActivationResponse> => {
    const { data } = await client.post<LiteratureValueRuntimeActivationResponse>(
      `/external-sources/overlays/${overlayId}/runtime-activations`,
      payload,
    );
    return data;
  },
  deactivateLiteratureValueRuntimeActivation: async (
    activationId: string,
    payload: LiteratureValueRuntimeActivationDeactivateRequest,
  ): Promise<LiteratureValueRuntimeActivationResponse> => {
    const { data } = await client.post<LiteratureValueRuntimeActivationResponse>(
      `/external-sources/runtime-activations/${activationId}/deactivate`,
      payload,
    );
    return data;
  },
  rollbackLiteratureValueRuntimeActivation: async (
    activationId: string,
    payload: LiteratureValueRollbackCreateRequest,
  ): Promise<LiteratureValueRollbackResponse> => {
    const { data } = await client.post<LiteratureValueRollbackResponse>(
      `/external-sources/runtime-activations/${activationId}/rollback`,
      payload,
    );
    return data;
  },
  createLiteratureValueReleaseEvidenceLink: async (
    releaseDecisionId: number,
    payload: LiteratureValueReleaseEvidenceLinkCreateRequest,
  ): Promise<LiteratureValueReleaseEvidenceLinkResponse> => {
    const { data } = await client.post<LiteratureValueReleaseEvidenceLinkResponse>(
      `/external-sources/release-decisions/${releaseDecisionId}/literature-value-release-evidence-links`,
      payload,
    );
    return data;
  },
  listLiteratureExtractionReviewDrafts: async (): Promise<LiteratureExtractionReviewDraftListResponse> => {
    const { data } = await client.get<LiteratureExtractionReviewDraftListResponse>(
      "/external-sources/literature-extraction-candidates/review-drafts",
    );
    return data;
  },
  getLiteratureExtractionReviewDraftComparison: async (
    candidateId: string,
    changedField?: string,
  ): Promise<LiteratureExtractionReviewDraftComparisonResponse> => {
    const suffix = changedField ? `?changed_field=${encodeURIComponent(changedField)}` : "";
    const { data } = await client.get<LiteratureExtractionReviewDraftComparisonResponse>(
      `/external-sources/literature-extraction-candidates/${candidateId}/review-drafts/comparison${suffix}`,
    );
    return data;
  },
  createLiteratureExtractionReviewDraft: async (
    candidateId: string,
    payload: LiteratureExtractionReviewDraftCreateRequest,
  ): Promise<LiteratureExtractionReviewDraftResponse> => {
    const { data } = await client.post<LiteratureExtractionReviewDraftResponse>(
      `/external-sources/literature-extraction-candidates/${candidateId}/review-drafts`,
      payload,
    );
    return data;
  },
  listExternalSources: async (): Promise<ExternalSourceCatalogResponse> => {
    const { data } = await client.get<ExternalSourceCatalogResponse>("/external-sources/catalog");
    return data;
  },
  getExternalSourceProcurementSummary: async (): Promise<ExternalSourceProcurementSummary> => {
    const { data } = await client.get<ExternalSourceProcurementSummary>("/external-sources/catalog/summary");
    return data;
  },
  getExternalSourceSchemaReadiness: async (): Promise<ExternalSourceSchemaReadinessResponse> => {
    const { data } = await client.get<ExternalSourceSchemaReadinessResponse>("/external-sources/schema-readiness");
    return data;
  },
  listExternalSourceReviewCards: async (): Promise<ExternalSourceReviewCardListResponse> => {
    const { data } = await client.get<ExternalSourceReviewCardListResponse>("/external-sources/review-cards");
    return data;
  },
  resolveExternalSourceReviewCard: async (
    cardId: string,
    payload: ExternalSourceReviewCardResolveRequest,
  ): Promise<ExternalSourceReviewCardResolveResponse> => {
    const { data } = await client.post<ExternalSourceReviewCardResolveResponse>(
      `/external-sources/review-cards/${cardId}/resolve`,
      payload,
    );
    return data;
  },
  fillPhase4AReviewedCandidates: async (): Promise<ExternalSourcePhase4AReviewedCandidateFillResponse> => {
    const { data } = await client.post<ExternalSourcePhase4AReviewedCandidateFillResponse>(
      "/external-sources/phase4a/reviewed-candidates/fill",
    );
    return data;
  },
  listExternalSourceExtractions: async (): Promise<ExternalSourceExtractionListResponse> => {
    const { data } = await client.get<ExternalSourceExtractionListResponse>("/external-sources/extractions");
    return data;
  },
  listReviewedExternalCandidates: async (): Promise<ReviewedExternalCandidateListResponse> => {
    const { data } = await client.get<ReviewedExternalCandidateListResponse>("/external-sources/reviewed-candidates");
    return data;
  },
  getReviewedExternalCandidateSummary: async (): Promise<ReviewedExternalCandidateLaneSummary> => {
    const { data } = await client.get<ReviewedExternalCandidateLaneSummary>("/external-sources/reviewed-candidates/summary");
    return data;
  },
  getReviewedExternalCandidateKnowledgeBase: async (): Promise<ReviewedExternalCandidateKnowledgeBaseResponse> => {
    const { data } = await client.get<ReviewedExternalCandidateKnowledgeBaseResponse>(
      "/external-sources/reviewed-candidates/knowledge-base",
    );
    return data;
  },
  getBusinessKnowledgeReviewPacketExport: async (
    itemKey: string,
  ): Promise<BusinessKnowledgeReviewPacketExportResponse> => {
    const { data } = await client.get<BusinessKnowledgeReviewPacketExportResponse>(
      `/external-sources/business-knowledge/${itemKey}/review-packet/export`,
    );
    return data;
  },
  getReviewedExternalCandidateActivationPreview: async (
    candidateId: string,
  ): Promise<ReviewedExternalCandidateActivationPreviewResponse> => {
    const { data } = await client.get<ReviewedExternalCandidateActivationPreviewResponse>(
      `/external-sources/reviewed-candidates/${candidateId}/activation-preview`,
    );
    return data;
  },
  getReviewedExternalCandidateRuntimeReadiness: async (
    candidateId: string,
  ): Promise<ReviewedExternalCandidateRuntimeReadinessResponse> => {
    const { data } = await client.get<ReviewedExternalCandidateRuntimeReadinessResponse>(
      `/external-sources/reviewed-candidates/${candidateId}/runtime-readiness`,
    );
    return data;
  },
  getReviewedExternalCandidateRollbackPreview: async (
    candidateId: string,
  ): Promise<ReviewedExternalCandidateRollbackPreviewResponse> => {
    const { data } = await client.get<ReviewedExternalCandidateRollbackPreviewResponse>(
      `/external-sources/reviewed-candidates/${candidateId}/rollback-preview`,
    );
    return data;
  },
  getFeedstockDetail: async (feedstockKey: string) => {
    const { data } = await client.get(`/feedstocks/${feedstockKey}`);
    return data;
  },
  listManuscriptCampaigns: async (): Promise<ManuscriptCampaignCatalogResponse> => {
    const { data } = await client.get<ManuscriptCampaignCatalogResponse>("/references/campaigns");
    return data;
  },
  getManuscriptCampaign: async (campaignKey: string) => {
    const { data } = await client.get(`/references/campaigns/${campaignKey}`);
    return data;
  },
  parseReferenceDocument: async (
    payload: ReferenceIngestionParseRequest,
  ): Promise<ReferenceIngestionStagedItem> => {
    const formData = new FormData();
    formData.append("file", payload.file);
    if (payload.source_title) formData.append("source_title", payload.source_title);
    formData.append("source_type", payload.source_type ?? "pdf");
    if (payload.source_owner) formData.append("source_owner", payload.source_owner);
    if (payload.license_note) formData.append("license_note", payload.license_note);
    if (payload.region) formData.append("region", payload.region);
    if (payload.units) formData.append("units_json", JSON.stringify(payload.units));
    if (payload.ingestion_mode) formData.append("ingestion_mode", payload.ingestion_mode);
    if (payload.human_review_required !== undefined) {
      formData.append("human_review_required", String(payload.human_review_required));
    }
    const { data } = await client.post<ReferenceIngestionStagedItem>(
      "/references/ingestion/parse",
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      },
    );
    return data;
  },
  listReferenceIngestionItems: async (): Promise<ReferenceIngestionListResponse> => {
    const { data } = await client.get<ReferenceIngestionListResponse>("/references/ingestion/staged");
    return data;
  },
  getReferenceIngestionItem: async (itemId: string): Promise<ReferenceIngestionStagedItem> => {
    const { data } = await client.get<ReferenceIngestionStagedItem>(`/references/ingestion/staged/${itemId}`);
    return data;
  },
  getReferenceIngestionHealth: async (): Promise<ReferenceIngestionHealthResponse> => {
    const { data } = await client.get<ReferenceIngestionHealthResponse>("/references/ingestion/health");
    return data;
  },
  promoteReferenceIngestionItem: async (
    itemId: string,
    payload: ReferenceIngestionPromoteRequest = { target_type: "campaign" },
  ): Promise<ReferenceIngestionPromoteResponse> => {
    const { data } = await client.post<ReferenceIngestionPromoteResponse>(
      `/references/ingestion/staged/${itemId}/promote`,
      payload,
    );
    return data;
  },
  createSignal: async (payload: SignalBatchCreate): Promise<SignalBatch> => {
    const { data } = await client.post<SignalBatch>("/signals", payload);
    return data;
  },
  compileSignal: async (payload: SignalCompileRequest): Promise<SignalCompileResponse> => {
    const { data } = await client.post<SignalCompileResponse>("/signals/compile", payload);
    return data;
  },
  refreshSignal: async (signalId: number): Promise<SignalRefreshResponse> => {
    const { data } = await client.post<SignalRefreshResponse>(`/signals/${signalId}/refresh`);
    return data;
  },
  evaluateSupervisor: async (
    signalId: number,
    payload: SupervisorObservationRequest,
  ): Promise<SupervisorStateResponse> => {
    const { data } = await client.post<SupervisorStateResponse>(`/signals/${signalId}/supervisor`, payload);
    return data;
  },
  getHandoverRecommendation: async (
    signalId: number,
    payload: SupervisorObservationRequest,
  ): Promise<HandoverRecommendationResponse> => {
    const { data } = await client.post<HandoverRecommendationResponse>(
      `/signals/${signalId}/handover-recommendation`,
      payload,
    );
    return data;
  },
  listControlProfiles: async (): Promise<ControlAPIProfile[]> => {
    const { data } = await client.get<ControlAPIProfile[]>("/control-profiles");
    return data;
  },
  createControlProfile: async (
    payload: ControlAPIProfileCreate,
  ): Promise<ControlAPIProfile> => {
    const { data } = await client.post<ControlAPIProfile>("/control-profiles", payload);
    return data;
  },
  listLocalityProfiles: async (): Promise<LocalityProfile[]> => {
    const { data } = await client.get<LocalityProfile[]>("/locality-profiles");
    return data;
  },
  createLocalityProfile: async (
    payload: LocalityProfileCreate,
  ): Promise<LocalityProfile> => {
    const { data } = await client.post<LocalityProfile>("/locality-profiles", payload);
    return data;
  },
  listExecutorProfiles: async (): Promise<ExecutorProfile[]> => {
    const { data } = await client.get<ExecutorProfile[]>("/executor-profiles");
    return data;
  },
  createExecutorProfile: async (
    payload: ExecutorProfileCreate,
  ): Promise<ExecutorProfile> => {
    const { data } = await client.post<ExecutorProfile>("/executor-profiles", payload);
    return data;
  },
  listReleaseDecisions: async (): Promise<ReleaseDecision[]> => {
    const { data } = await client.get<ReleaseDecision[]>("/release-decisions");
    return data;
  },
  evaluateRelease: async (
    payload: ReleaseEvaluationRequest,
  ): Promise<ReleaseDecision> => {
    const { data } = await client.post<ReleaseDecision>("/release-decisions/evaluate", payload);
    return data;
  },
  listPortabilityAudits: async (): Promise<PortabilityAudit[]> => {
    const { data } = await client.get<PortabilityAudit[]>("/portability-audits");
    return data;
  },
  createPortabilityAudit: async (
    payload: PortabilityAuditCreate,
  ): Promise<PortabilityAudit> => {
    const { data } = await client.post<PortabilityAudit>("/portability-audits", payload);
    return data;
  },
  getPortabilityRecommendation: async (
    payload: PortabilityRecommendationRequest,
  ): Promise<PortabilityRecommendationResponse> => {
    const { data } = await client.post<PortabilityRecommendationResponse>(
      "/portability-audits/recommendation",
      payload,
    );
    return data;
  },
  listAuditPackets: async (): Promise<AuditPacket[]> => {
    const { data } = await client.get<AuditPacket[]>("/audit-packets");
    return data;
  },
  listNativeModels: async (batchId?: number): Promise<NativeModelCatalog> => {
    const { data } = await client.get<NativeModelCatalog>("/native-models", {
      params: batchId ? { batch_id: batchId } : undefined,
    });
    return data;
  },
  getNativeModelRuntimeStatus: async (): Promise<NativeModelRuntimeStatus> => {
    const { data } = await client.get<NativeModelRuntimeStatus>("/native-models/runtime");
    return data;
  },
  getNativeModelDownloadPlan: async (modelKey?: string): Promise<NativeModelDownloadPlan[]> => {
    const { data } = await client.get<NativeModelDownloadPlan[]>("/native-models/download-plan", {
      params: modelKey ? { model_key: modelKey } : undefined,
    });
    return data;
  },
  downloadNativeModel: async (modelKey: string): Promise<NativeModelDownloadResponse> => {
    const { data } = await client.post<NativeModelDownloadResponse>(`/native-models/${modelKey}/download`);
    return data;
  },
  listNativeModelRuns: async (
    modelKey?: string,
    batchId?: number,
    limit = 20,
  ): Promise<NativeModelRunArtifact[]> => {
    const { data } = await client.get<NativeModelRunArtifact[]>("/native-models/runs", {
      params: {
        limit,
        ...(modelKey ? { model_key: modelKey } : {}),
        ...(batchId ? { batch_id: batchId } : {}),
      },
    });
    return data;
  },
  inferNativeModel: async (
    payload: NativeModelInferenceRequest,
  ): Promise<NativeModelInferenceResponse> => {
    const { data } = await client.post<NativeModelInferenceResponse>("/native-models/infer", payload);
    return data;
  },
  getBatchRisk: async (batchId: number, horizon = 6): Promise<TimeseriesRiskResponse> => {
    const { data } = await client.get<TimeseriesRiskResponse>(`/bos/risk/batch/${batchId}`, {
      params: { horizon },
    });
    return data;
  },
  getRecentRisks: async (limit = 5, horizon = 6): Promise<RecentTimeseriesRiskResponse> => {
    const { data } = await client.get<RecentTimeseriesRiskResponse>("/bos/risk/recent", {
      params: { limit, horizon },
    });
    return data;
  },
  getBatchGuidance: async (batchId: number): Promise<BatchGuidanceResponse> => {
    const { data } = await client.get<BatchGuidanceResponse>(`/guidance/batch/${batchId}`);
    return data;
  },
  getBrainRuntime: async (): Promise<BrainRuntimeResponse> => {
    const { data } = await client.get<BrainRuntimeResponse>("/brain/runtime");
    return data;
  },
  updateBrainRuntimeDocument: async (
    documentKey: string,
    payload: BrainRuntimeUpdateRequest,
  ): Promise<BrainRuntimeDocument> => {
    const { data } = await client.put<BrainRuntimeDocument>(`/brain/runtime/${documentKey}`, payload);
    return data;
  },
  exportAuditPacket: async (batchId: number, format: "md" | "json"): Promise<Blob> => {
    const { data } = await client.get(`/audit-packets/batch/${batchId}/export`, {
      params: { format },
      responseType: "blob",
    });
    return data;
  },
};
