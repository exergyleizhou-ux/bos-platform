import client from "@/api/client";
import type {
  SimulationLabAuditTraceResponse,
  SimulationLabCycleListResponse,
  SimulationLabRunHistoryItem,
  SimulationLabRunResponse,
  SimulationEvidenceSourcesResponse,
  SimulationPolicyCompareRequest,
  SimulationPolicyComparisonResponse,
  SimulationReleaseAppendixResponse,
  SimulationReplayResponse,
  SimulationRunDiffResponse,
  SimulationScenarioCreate,
  SimulationScenarioImportRequest,
  SimulationScenarioImportResponse,
  SimulationScenarioResponse,
} from "@/types/simulationLab";

export const simulationLabApi = {
  createScenario: async (payload: SimulationScenarioCreate): Promise<SimulationScenarioResponse> => {
    const { data } = await client.post<SimulationScenarioResponse>("/bos/simulation-lab/scenarios", payload);
    return data;
  },
  importScenarioFromReference: async (
    payload: SimulationScenarioImportRequest,
  ): Promise<SimulationScenarioImportResponse> => {
    const { data } = await client.post<SimulationScenarioImportResponse>(
      "/bos/simulation-lab/scenarios/import-reference",
      payload,
    );
    return data;
  },
  listScenarios: async (params?: {
    batch_id?: string;
    species?: string;
    feedstock?: string;
    limit?: number;
  }): Promise<SimulationScenarioResponse[]> => {
    const { data } = await client.get<SimulationScenarioResponse[]>("/bos/simulation-lab/scenarios", { params });
    return data;
  },
  runScenario: async (simulationId: string): Promise<SimulationLabRunResponse> => {
    const { data } = await client.post<SimulationLabRunResponse>(`/bos/simulation-lab/scenarios/${simulationId}/run`);
    return data;
  },
  comparePolicies: async (
    simulationId: string,
    payload: SimulationPolicyCompareRequest,
  ): Promise<SimulationPolicyComparisonResponse> => {
    const { data } = await client.post<SimulationPolicyComparisonResponse>(
      `/bos/simulation-lab/scenarios/${simulationId}/compare`,
      payload,
    );
    return data;
  },
  listRuns: async (simulationId: string): Promise<SimulationLabRunHistoryItem[]> => {
    const { data } = await client.get<SimulationLabRunHistoryItem[]>(
      `/bos/simulation-lab/scenarios/${simulationId}/runs`,
    );
    return data;
  },
  getCycles: async (simulationId: string): Promise<SimulationLabCycleListResponse> => {
    const { data } = await client.get<SimulationLabCycleListResponse>(
      `/bos/simulation-lab/scenarios/${simulationId}/cycles`,
    );
    return data;
  },
  getAuditTrace: async (simulationId: string): Promise<SimulationLabAuditTraceResponse> => {
    const { data } = await client.get<SimulationLabAuditTraceResponse>(
      `/bos/simulation-lab/scenarios/${simulationId}/audit-trace`,
    );
    return data;
  },
  getEvidenceSources: async (simulationId: string): Promise<SimulationEvidenceSourcesResponse> => {
    const { data } = await client.get<SimulationEvidenceSourcesResponse>(
      `/bos/simulation-lab/scenarios/${simulationId}/evidence-sources`,
    );
    return data;
  },
  exportRun: async (simulationId: string): Promise<Blob> => {
    const { data } = await client.get(`/bos/simulation-lab/scenarios/${simulationId}/export`, {
      responseType: "blob",
    });
    return data;
  },
  getReleaseAppendix: async (simulationId: string): Promise<SimulationReleaseAppendixResponse> => {
    const { data } = await client.get<SimulationReleaseAppendixResponse>(
      `/bos/simulation-lab/scenarios/${simulationId}/release-appendix`,
    );
    return data;
  },
  exportReleaseAppendix: async (simulationId: string, format: "json" | "md" = "md"): Promise<Blob> => {
    const { data } = await client.get(`/bos/simulation-lab/scenarios/${simulationId}/release-appendix`, {
      params: { format },
      responseType: "blob",
    });
    return data;
  },
  replayRun: async (runId: string): Promise<SimulationReplayResponse> => {
    const { data } = await client.post<SimulationReplayResponse>(`/bos/simulation-lab/runs/${runId}/replay`);
    return data;
  },
  diffRuns: async (runId: string, againstRunId: string): Promise<SimulationRunDiffResponse> => {
    const { data } = await client.get<SimulationRunDiffResponse>(`/bos/simulation-lab/runs/${runId}/diff`, {
      params: { against_run_id: againstRunId },
    });
    return data;
  },
};
