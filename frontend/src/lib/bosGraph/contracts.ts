import type { AssistantBosIntent, AssistantStructuredResult } from "@/lib/bosAssistant";
import type { batchApi } from "@/api/batchApi";
import type { bosApi } from "@/api/bosApi";
import type { dashboardApi } from "@/api/dashboardApi";
import type { twinApi } from "@/api/twinApi";
import type { AuditPacket, BrainRuntimeResponse, HandoverRecommendationResponse, ReleaseDecision, SignalBatch, SupervisorObservationRequest, SupervisorStateResponse } from "@/types/bos";
import type { Batch, BatchListResponse } from "@/types/batch";
import type { DashboardSummary } from "@/types/dashboard";

export type BosGraphName =
  | "batch_triage_graph"
  | "release_review_graph"
  | "signal_runtime_graph";

export type BosGraphStatus = "completed" | "blocked";

export interface BosGraphDiagnostic {
  scope: string;
  message: string;
  detail?: string;
}

export interface BosGraphNextAction {
  label: string;
  to?: string;
}

export interface BosGraphNodeOutput {
  status: BosGraphStatus;
  body: string;
  structuredResult: AssistantStructuredResult;
  nextActions?: BosGraphNextAction[];
  diagnostics?: BosGraphDiagnostic[];
}

export interface BosGraphQueryClient {
  invalidateQueries: (filters: { queryKey: readonly unknown[] | unknown[] }) => Promise<unknown>;
}

export interface BosGraphEffects {
  downloadBlob?: (blob: Blob, filename: string) => void;
}

export interface BosGraphApiClients {
  batch: Pick<typeof batchApi, "list" | "get">;
  bos: Pick<
    typeof bosApi,
    | "listSignals"
    | "listAuditPackets"
    | "getBatchGuidance"
    | "compileSignal"
    | "refreshSignal"
    | "evaluateRelease"
    | "exportAuditPacket"
    | "evaluateSupervisor"
    | "getHandoverRecommendation"
    | "listReleaseDecisions"
    | "getBrainRuntime"
  >;
  dashboard: Pick<typeof dashboardApi, "summary">;
  twin: Pick<typeof twinApi, "list">;
}

export interface BosGraphIntermediateData {
  batches?: Batch[];
  batchList?: BatchListResponse;
  batch?: Batch | null;
  comparisonBatches?: Batch[];
  signals?: SignalBatch[];
  signal?: SignalBatch | null;
  audits?: AuditPacket[];
  audit?: AuditPacket | null;
  releaseDecisions?: ReleaseDecision[];
  releaseDecision?: ReleaseDecision | null;
  guidance?: {
    gap_items: Array<{ severity: string; title: string; message: string }>;
    recommended_actions: string[];
  } | null;
  brainRuntime?: BrainRuntimeResponse | null;
  dashboardSummary?: DashboardSummary | null;
  supervisorObservation?: SupervisorObservationRequest | null;
  supervisorResult?: SupervisorStateResponse | null;
  handoverResult?: HandoverRecommendationResponse | null;
  scoredBatches?: Array<{
    batch: Batch;
    signal: SignalBatch | null;
    audit: AuditPacket | null;
    guidance: {
      gap_items: Array<{ severity: string; title: string; message: string }>;
      recommended_actions: string[];
    };
    score: number;
    reasons: string[];
  }>;
}

export interface BosGraphContext {
  graphName: BosGraphName;
  intent: AssistantBosIntent;
  message: string;
  requestedEntityId: number | null;
  requestedEntityIds: number[];
  queryClient: BosGraphQueryClient;
  apiClients: BosGraphApiClients;
  sessionId: number | null;
  userRole: string;
  effects?: BosGraphEffects;
  intermediateData: BosGraphIntermediateData;
}

export interface BosGraphDefinition {
  name: BosGraphName;
  intents: AssistantBosIntent[];
  execute: (context: BosGraphContext) => Promise<BosGraphNodeOutput>;
}
