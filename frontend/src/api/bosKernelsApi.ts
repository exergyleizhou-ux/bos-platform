import client from "@/api/client";
import type {
  BenchmarkCase,
  BenchmarkRun,
  ExternalKnowledgeCandidateMatrix,
  ExternalKnowledgePromotionResponse,
  ExternalKnowledgeRuntimeActivationDraft,
  ExternalKnowledgeRuntimeActivationExecutionReadiness,
  ExternalKnowledgeRuntimeActivationReadiness,
  ExternalKnowledgeRuntimeActivationRecord,
  ExternalKnowledgeRuntimeActivationState,
  ExternalKnowledgeRegistryPatchResponse,
  ExternalKnowledgeValidatedRegistry,
  KnowledgeRelation,
  ModelGovernanceResponse,
  ModelProviderCapabilityMatrix,
  ModelRegistrationResponse,
  ModelRegistryItem,
} from "@/types/bosKernels";

export const bosKernelsApi = {
  listBenchmarkCases: async (): Promise<BenchmarkCase[]> => {
    const { data } = await client.get<BenchmarkCase[]>("/benchmarks/cases");
    return data;
  },
  createBenchmarkRun: async (): Promise<BenchmarkRun> => {
    const { data } = await client.post<BenchmarkRun>("/benchmarks/runs", {
      suite_name: "simulation_lab_regression",
    });
    return data;
  },
  listBenchmarkRuns: async (): Promise<BenchmarkRun[]> => {
    const { data } = await client.get<BenchmarkRun[]>("/benchmarks/runs");
    return data;
  },
  listModels: async (): Promise<ModelRegistryItem[]> => {
    const { data } = await client.get<ModelRegistryItem[]>("/models");
    return data;
  },
  listModelProviderCapabilities: async (): Promise<ModelProviderCapabilityMatrix> => {
    const { data } = await client.get<ModelProviderCapabilityMatrix>("/model-providers/capabilities");
    return data;
  },
  listExternalKnowledgeCandidates: async (): Promise<ExternalKnowledgeCandidateMatrix> => {
    const { data } = await client.get<ExternalKnowledgeCandidateMatrix>("/external-knowledge/candidates");
    return data;
  },
  requestExternalKnowledgePromotion: async (
    candidateType: string,
    candidateKey: string,
  ): Promise<ExternalKnowledgePromotionResponse> => {
    const { data } = await client.post<ExternalKnowledgePromotionResponse>("/external-knowledge/promotion-requests", {
      candidate_type: candidateType,
      candidate_key: candidateKey,
      reason: "Request explicit human review before any manual validated-default patch.",
    });
    return data;
  },
  resolveExternalKnowledgePromotion: async (
    approvalRequestId: string,
    approved: boolean,
  ): Promise<ExternalKnowledgePromotionResponse> => {
    const { data } = await client.post<ExternalKnowledgePromotionResponse>(
      `/external-knowledge/promotion-requests/${encodeURIComponent(approvalRequestId)}/resolve`,
      {
        approved,
        reason: approved
          ? "Approved for manual registry patch only; no defaults are mutated by this endpoint."
          : "Rejected; candidate remains metadata-only.",
      },
    );
    return data;
  },
  applyExternalKnowledgeRegistryPatch: async (
    approvalRequestId: string,
  ): Promise<ExternalKnowledgeRegistryPatchResponse> => {
    const { data } = await client.post<ExternalKnowledgeRegistryPatchResponse>(
      "/external-knowledge/manual-registry-patches",
      {
        approval_request_id: approvalRequestId,
        reason: "Apply approved candidate to the validated external knowledge registry without mutating runtime defaults.",
      },
    );
    return data;
  },
  listExternalKnowledgeValidatedRegistry: async (): Promise<ExternalKnowledgeValidatedRegistry> => {
    const { data } = await client.get<ExternalKnowledgeValidatedRegistry>("/external-knowledge/validated-defaults");
    return data;
  },
  getExternalKnowledgeRuntimeActivationReadiness: async (
    registryPatchId?: string,
  ): Promise<ExternalKnowledgeRuntimeActivationReadiness> => {
    const { data } = await client.get<ExternalKnowledgeRuntimeActivationReadiness>(
      "/external-knowledge/runtime-activation/readiness",
      { params: registryPatchId ? { registry_patch_id: registryPatchId } : undefined },
    );
    return data;
  },
  listExternalKnowledgeRuntimeActivationState: async (): Promise<ExternalKnowledgeRuntimeActivationState> => {
    const { data } = await client.get<ExternalKnowledgeRuntimeActivationState>("/external-knowledge/runtime-activation/state");
    return data;
  },
  createExternalKnowledgeRuntimeActivationDraft: async (
    registryPatchId: string,
  ): Promise<ExternalKnowledgeRuntimeActivationDraft> => {
    const { data } = await client.post<ExternalKnowledgeRuntimeActivationDraft>(
      "/external-knowledge/runtime-activation/drafts",
      {
        registry_patch_id: registryPatchId,
        operator_attestation: "I reviewed the validated external registry patch and request scoped runtime activation.",
        idempotency_key: `runtime-activation-draft-${registryPatchId}`,
      },
    );
    return data;
  },
  resolveExternalKnowledgeRuntimeActivationDraft: async (
    activationRequestId: string,
    approved: boolean,
  ): Promise<ExternalKnowledgeRuntimeActivationDraft> => {
    const { data } = await client.post<ExternalKnowledgeRuntimeActivationDraft>(
      `/external-knowledge/runtime-activation/drafts/${encodeURIComponent(activationRequestId)}/resolve`,
      {
        approved,
        reason: approved
          ? "Approved for separate audited runtime activation only."
          : "Rejected before runtime activation.",
      },
    );
    return data;
  },
  getExternalKnowledgeRuntimeActivationExecutionReadiness: async (
    activationRequestId: string,
  ): Promise<ExternalKnowledgeRuntimeActivationExecutionReadiness> => {
    const { data } = await client.get<ExternalKnowledgeRuntimeActivationExecutionReadiness>(
      `/external-knowledge/runtime-activation/drafts/${encodeURIComponent(activationRequestId)}/execution-readiness`,
    );
    return data;
  },
  executeExternalKnowledgeRuntimeActivation: async (
    activationRequestId: string,
    expectedPreviousActiveRegistryPatchId: string | null,
  ): Promise<ExternalKnowledgeRuntimeActivationRecord> => {
    const { data } = await client.post<ExternalKnowledgeRuntimeActivationRecord>(
      "/external-knowledge/runtime-activation/executions",
      {
        activation_request_id: activationRequestId,
        expected_previous_active_registry_patch_id: expectedPreviousActiveRegistryPatchId,
        operator_attestation: "Activate only the scoped runtime read path for this reviewed registry patch.",
        idempotency_key: `runtime-activation-execute-${activationRequestId}`,
      },
    );
    return data;
  },
  rollbackExternalKnowledgeRuntimeActivation: async (
    activationId: string,
  ): Promise<ExternalKnowledgeRuntimeActivationRecord> => {
    const { data } = await client.post<ExternalKnowledgeRuntimeActivationRecord>(
      "/external-knowledge/runtime-activation/rollbacks",
      {
        activation_id: activationId,
        operator_attestation: "Rollback this scoped runtime activation to its previous active version.",
        idempotency_key: `runtime-activation-rollback-${activationId}`,
      },
    );
    return data;
  },
  registerModelCandidate: async (benchmarkRunId: string): Promise<ModelRegistrationResponse> => {
    const { data } = await client.post<ModelRegistrationResponse>("/models", {
      name: "chronos-risk-candidate",
      task_type: "risk_forecast",
      version: "review-candidate",
      benchmark_run_id: benchmarkRunId,
      metadata_payload: {
        source: "release_center",
      },
    });
    return data;
  },
  requestModelGovernanceReview: async (
    modelId: string,
    modelVersionId: string,
    benchmarkRunId: string,
  ): Promise<ModelGovernanceResponse> => {
    const { data } = await client.post<ModelGovernanceResponse>(
      `/models/${modelId}/versions/${modelVersionId}/governance`,
      {
        benchmark_run_id: benchmarkRunId,
        decision: "request_review",
        reason: "Benchmark evidence is ready for human review.",
      },
    );
    return data;
  },
  listKnowledgeRelations: async (): Promise<KnowledgeRelation[]> => {
    const { data } = await client.get<KnowledgeRelation[]>("/knowledge/relations");
    return data;
  },
};
