import type { AssistantBosIntent } from "@/lib/bosAssistant";
import type { BosGraphApiClients, BosGraphContext, BosGraphEffects, BosGraphName, BosGraphQueryClient } from "@/lib/bosGraph/contracts";
import type { SupervisorObservationRequest } from "@/types/bos";

export interface CreateBosGraphContextOptions {
  graphName: BosGraphName;
  intent: AssistantBosIntent;
  message: string;
  queryClient: BosGraphQueryClient;
  apiClients: BosGraphApiClients;
  sessionId: number | null;
  userRole: string;
  effects?: BosGraphEffects;
}

export function extractRequestedEntityId(message: string) {
  const match = message.match(/\b(\d{1,6})\b/);
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isInteger(value) && value > 0 ? value : null;
}

export function extractRequestedEntityIds(message: string) {
  const matches = message.match(/\b(\d{1,6})\b/g) ?? [];
  return Array.from(
    new Set(
      matches
        .map((item) => Number(item))
        .filter((value) => Number.isInteger(value) && value > 0),
    ),
  );
}

export function buildDefaultSupervisorObservation(): SupervisorObservationRequest {
  return {
    uv254: 2.4,
    od280: 2.0,
    do: 5.1,
    ph: 7.1,
    elapsed_hours: 8,
    previous_c_signal_hat: 0.58,
    previous_elapsed_hours: 7,
    previous_dc_dt_hat: 0.03,
    previous_negative_slope_streak: 0,
    confidence_threshold: 0.8,
    negative_slope_persistence: 3,
    observability_required: true,
  };
}

export function createBosGraphContext(options: CreateBosGraphContextOptions): BosGraphContext {
  return {
    graphName: options.graphName,
    intent: options.intent,
    message: options.message,
    requestedEntityId: extractRequestedEntityId(options.message),
    requestedEntityIds: extractRequestedEntityIds(options.message),
    queryClient: options.queryClient,
    apiClients: options.apiClients,
    sessionId: options.sessionId,
    userRole: options.userRole,
    effects: options.effects,
    intermediateData: {},
  };
}
