import type { Batch } from "@/types/batch";
import type {
  AuditPacket,
  MechanisticContext,
  NativeModelRunArtifact,
  NativeRunSummary,
  SupervisorSnapshot,
} from "@/types/bos";
import type { VisionObservation } from "@/types/vision";
import type { SERResult } from "@/types/ser";

export type ReadinessTone = "success" | "warning" | "danger" | "neutral";

export interface AuditPacketReadModel {
  id: number;
  batchId: number;
  batchLabel: string;
  packetVersion: string;
  schemaVersion: string;
  evidenceLevel: string;
  compiledAt: string;
  compiledByUserId: number;
  integrityHash: string;
  signalLabel: string;
  signalFreshness: string;
  controlLabel: string;
  releaseDecision: string;
  decisionConfidence: number | null;
  readinessLabel: string;
  readinessTone: ReadinessTone;
  contractStatus: string;
  signalStatus: string;
  rationale: string;
  blockingFactors: string[];
  warningFactors: string[];
  passedChecks: string[];
  reasonCodes: string[];
  triggerMetrics: Record<string, unknown>;
  visionObservation: (VisionObservation & Record<string, unknown>) | null;
  portabilityAudits: Array<{
    id: number;
    executorLabel: string;
    localityLabel: string;
    outcome: string;
    retuningRequired: boolean;
    recommendedOutcome?: string | null;
    rationale?: string | null;
    recommendedAction?: string | null;
    requiresRequalification?: boolean;
    retuningAxes?: string[] | null;
    retuningMagnitude?: number | null;
    portabilityScore?: number | null;
    triggerMetrics: Record<string, unknown> | null;
  }>;
  metrics: {
    serValue: number | null;
    dPrime: number | null;
    gPrime: number | null;
    closureResidual: number | null;
    meteringCompleteness: number | null;
    potency: number | null;
    mtt: number | null;
  };
  mechanisticContext: MechanisticContext | null;
  supervisorSnapshot: SupervisorSnapshot | null;
  supervisorHistory: SupervisorSnapshot[];
}

export interface BatchBosReadModel {
  packet: AuditPacketReadModel | null;
  evidenceLevel: string;
  signalFreshness: string;
  controlVersion: string;
  releaseLabel: string;
  releaseTone: ReadinessTone;
  rationale: string;
  blockingFactors: string[];
  warningFactors: string[];
  passedChecks: string[];
  reasonCodes: string[];
  metrics: AuditPacketReadModel["metrics"];
  portabilityAudits: AuditPacketReadModel["portabilityAudits"];
  serValue: number | null;
  grade: string | null;
  latestNativeRun: NativeRunSummary | null;
  visionObservation: AuditPacketReadModel["visionObservation"];
}

function mapDecision(decision: string): { label: string; tone: ReadinessTone } {
  switch (decision) {
    case "PASS":
      return { label: "Ready", tone: "success" };
    case "PASS_WITH_RETUNING":
      return { label: "Retune", tone: "warning" };
    case "FAIL":
      return { label: "Blocked", tone: "danger" };
    default:
      return { label: "Evidence gap", tone: "warning" };
  }
}

export function getAuditPacketReadModel(packet: AuditPacket): AuditPacketReadModel {
  const payload = packet.packet;
  const decision = payload?.release_decision;
  const decisionView = mapDecision(decision?.decision ?? "INSUFFICIENT_EVIDENCE");
  const mechanisticContext = extractMechanisticContext(packet);
  const supervisorSnapshot = extractSupervisorSnapshot(packet);
  const supervisorHistory = extractSupervisorHistory(packet);
  const visionObservation = extractVisionObservation(packet);
  const portabilityRecommendations = new Map<
    number,
    {
      recommended_outcome?: string | null;
      rationale?: string | null;
      recommended_action?: string | null;
      requires_requalification?: boolean;
      retuning_axes?: string[] | null;
      retuning_magnitude?: number | null;
      portability_score?: number | null;
    }
  >(
    Array.isArray((packet.retuning_axes as { recommended_by_portability?: unknown } | null)?.recommended_by_portability)
      ? (
          (
            packet.retuning_axes as {
              recommended_by_portability?: Array<{
                audit_id?: number;
                recommended_outcome?: string | null;
                rationale?: string | null;
                recommended_action?: string | null;
                requires_requalification?: boolean;
                retuning_axes?: string[] | null;
                retuning_magnitude?: number | null;
                portability_score?: number | null;
              }>;
            }
          ).recommended_by_portability ?? []
        )
          .filter((item) => typeof item?.audit_id === "number")
          .map((item) => [
            item.audit_id as number,
            {
              recommended_outcome: item.recommended_outcome ?? null,
              rationale: item.rationale ?? null,
              recommended_action: item.recommended_action ?? null,
              requires_requalification: item.requires_requalification ?? false,
              retuning_axes: Array.isArray(item.retuning_axes) ? item.retuning_axes.filter(Boolean) : null,
              retuning_magnitude:
                typeof item.retuning_magnitude === "number" ? item.retuning_magnitude : null,
              portability_score:
                typeof item.portability_score === "number" ? item.portability_score : null,
            },
          ])
      : [],
  );

  return {
    id: packet.id,
    batchId: packet.batch_id,
    batchLabel: payload?.batch.batch_id ?? `Batch ${packet.batch_id}`,
    packetVersion: packet.packet_version,
    schemaVersion: payload?.generation_context.schema_version ?? packet.packet_version,
    evidenceLevel: payload?.boundary_ledger?.evidence_level ?? packet.evidence_level ?? "Unknown",
    compiledAt: payload?.generation_context.compiled_at ?? packet.generated_at,
    compiledByUserId: payload?.generation_context.compiled_by_user_id ?? packet.user_id,
    integrityHash: payload?.generation_context.hash ?? "",
    signalLabel:
      payload?.signal_batch?.compiled_signal_id ??
      (payload?.signal_batch ? `Signal ${payload.signal_batch.id}` : "No signal packet"),
    signalFreshness: payload?.signal_batch?.freshness_state ?? "Unknown",
    controlLabel: payload?.control_profile
      ? `${payload.control_profile.name} / ${payload.control_profile.version}`
      : "No control contract",
    releaseDecision: decision?.decision ?? "INSUFFICIENT_EVIDENCE",
    decisionConfidence: getDecisionConfidence(decision),
    readinessLabel: decisionView.label,
    readinessTone: decisionView.tone,
    contractStatus:
      typeof packet.contract_evaluation?.status === "string" ? packet.contract_evaluation.status : "unknown",
    signalStatus:
      typeof packet.signal_validity?.status === "string" ? packet.signal_validity.status : "unknown",
    rationale: decision?.rationale ?? "Audit packet has not compiled a release rationale yet.",
    blockingFactors: decision?.blocking_factors ?? [],
    warningFactors: decision?.warning_factors ?? [],
    passedChecks: decision?.passed_checks ?? [],
    reasonCodes: decision?.reason_codes ?? [],
    triggerMetrics: decision?.trigger_metrics ?? {},
    visionObservation,
    portabilityAudits: (payload?.portability_audits ?? []).map((audit) => ({
      ...(portabilityRecommendations.get(audit.id) ?? {}),
      id: audit.id,
      executorLabel: audit.executor_name ?? `Executor ${audit.executor_profile_id}`,
      localityLabel:
        audit.locality_name ??
        (audit.locality_profile_id != null ? `Locality ${audit.locality_profile_id}` : "No locality override"),
      outcome: audit.outcome,
      retuningRequired: audit.retuning_required,
      recommendedOutcome:
        typeof (audit as { recommended_outcome?: unknown }).recommended_outcome === "string"
          ? ((audit as { recommended_outcome?: string }).recommended_outcome ?? null)
          : (portabilityRecommendations.get(audit.id)?.recommended_outcome ?? null),
      rationale:
        typeof (audit as { rationale?: unknown }).rationale === "string"
          ? ((audit as { rationale?: string }).rationale ?? null)
          : (portabilityRecommendations.get(audit.id)?.rationale ?? null),
      recommendedAction:
        typeof (audit as { recommended_action?: unknown }).recommended_action === "string"
          ? ((audit as { recommended_action?: string }).recommended_action ?? null)
          : (portabilityRecommendations.get(audit.id)?.recommended_action ?? null),
      requiresRequalification:
        typeof (audit as { requires_requalification?: unknown }).requires_requalification === "boolean"
          ? ((audit as { requires_requalification?: boolean }).requires_requalification ?? false)
          : Boolean(portabilityRecommendations.get(audit.id)?.requires_requalification),
      retuningAxes: Array.isArray((audit as { retuning_axes?: unknown }).retuning_axes)
        ? (((audit as { retuning_axes?: string[] }).retuning_axes ?? []).filter(Boolean))
        : (portabilityRecommendations.get(audit.id)?.retuning_axes ?? null),
      retuningMagnitude:
        typeof (audit as { retuning_magnitude?: unknown }).retuning_magnitude === "number"
          ? ((audit as { retuning_magnitude?: number }).retuning_magnitude ?? null)
          : (portabilityRecommendations.get(audit.id)?.retuning_magnitude ?? null),
      portabilityScore:
        typeof (audit as { portability_score?: unknown }).portability_score === "number"
          ? ((audit as { portability_score?: number }).portability_score ?? null)
          : (portabilityRecommendations.get(audit.id)?.portability_score ?? null),
      triggerMetrics: audit.trigger_metrics,
    })),
    metrics: {
      serValue: payload?.boundary_ledger?.ser_value ?? null,
      dPrime: payload?.boundary_ledger?.d_prime ?? null,
      gPrime: payload?.boundary_ledger?.g_prime ?? null,
      closureResidual: payload?.boundary_ledger?.closure_residual ?? null,
      meteringCompleteness: payload?.boundary_ledger?.metering_completeness ?? null,
      potency: payload?.signal_batch?.potency ?? null,
      mtt: payload?.control_profile?.mtt ?? null,
    },
    mechanisticContext,
    supervisorSnapshot,
    supervisorHistory,
  };
}

function getDecisionConfidence(
  decision:
    | {
        decision_confidence?: number | null;
        trigger_metrics?: Record<string, unknown>;
      }
    | null
    | undefined,
) {
  if (typeof decision?.decision_confidence === "number") {
    return decision.decision_confidence;
  }
  return typeof decision?.trigger_metrics?.decision_confidence === "number"
    ? decision.trigger_metrics.decision_confidence
    : null;
}

export function getBatchBosReadModel(
  batch: Batch,
  serResult?: SERResult | null,
  nativeRuns: NativeModelRunArtifact[] = [],
): BatchBosReadModel {
  const packet = batch.bos?.audit_packet ? getAuditPacketReadModel(batch.bos.audit_packet) : null;
  const latestNativeRun = batch.bos?.latest_native_run ?? summarizeLatestNativeRun(nativeRuns);
  const visionObservation =
    packet?.visionObservation ??
    batch.bos?.signal_batch?.qc_markers?.vision_observation ??
    null;

  return {
    packet,
    evidenceLevel: packet?.evidenceLevel ?? "Awaiting packet",
    signalFreshness: packet?.signalFreshness ?? "Awaiting packet",
    controlVersion: packet?.controlLabel ?? "Awaiting packet",
    releaseLabel: packet?.readinessLabel ?? "Awaiting packet",
    releaseTone: packet?.readinessTone ?? "neutral",
    rationale: packet?.rationale ?? "BOS read model is waiting for an audit packet.",
    blockingFactors: packet?.blockingFactors ?? [],
    warningFactors: packet?.warningFactors ?? [],
    passedChecks: packet?.passedChecks ?? [],
    reasonCodes: packet?.reasonCodes ?? [],
    metrics: packet?.metrics ?? {
      serValue: null,
      dPrime: null,
      gPrime: null,
      closureResidual: null,
      meteringCompleteness: null,
      potency: null,
      mtt: null,
    },
    portabilityAudits: packet?.portabilityAudits ?? [],
    serValue: packet?.metrics.serValue ?? serResult?.ser_value ?? null,
    grade: serResult?.grade ?? null,
    latestNativeRun,
    visionObservation,
  };
}

function isVisionObservation(value: unknown): value is VisionObservation & Record<string, unknown> {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<VisionObservation>;
  return typeof candidate.image_id === "string" && Array.isArray(candidate.detections);
}

function extractVisionObservation(packet: AuditPacket): (VisionObservation & Record<string, unknown>) | null {
  const validityObservation = packet.signal_validity?.vision_observation;
  if (isVisionObservation(validityObservation)) return validityObservation;

  const triggerObservation = packet.packet?.release_decision?.trigger_metrics?.vision_observation;
  if (isVisionObservation(triggerObservation)) return triggerObservation;

  return null;
}

function extractMechanisticContext(packet: AuditPacket): MechanisticContext | null {
  const packetContext = packet.packet as (typeof packet.packet & {
    mechanistic_context?: MechanisticContext | null;
  }) | null;
  if (packetContext?.mechanistic_context) return packetContext.mechanistic_context;

  if (packet.signal_validity?.mechanistic_context) {
    return packet.signal_validity.mechanistic_context as MechanisticContext;
  }

  const triggerContext = packet.packet?.release_decision?.trigger_metrics?.mechanistic_context;
  if (isMechanisticContext(triggerContext)) return triggerContext;

  return null;
}

function extractSupervisorSnapshot(packet: AuditPacket): SupervisorSnapshot | null {
  const validitySnapshot = packet.signal_validity?.supervisor_snapshot;
  if (validitySnapshot && typeof validitySnapshot === "object") {
    return validitySnapshot as SupervisorSnapshot;
  }

  const packetContext = packet.packet as (typeof packet.packet & {
    mechanistic_context?: { supervisor_snapshot?: SupervisorSnapshot | null } | null;
  }) | null;
  if (packetContext?.mechanistic_context?.supervisor_snapshot) {
    return packetContext.mechanistic_context.supervisor_snapshot;
  }

  const triggerContext = packet.packet?.release_decision?.trigger_metrics?.mechanistic_context;
  if (
    triggerContext &&
    typeof triggerContext === "object" &&
    "supervisor_snapshot" in triggerContext &&
    triggerContext.supervisor_snapshot &&
    typeof triggerContext.supervisor_snapshot === "object"
  ) {
    return triggerContext.supervisor_snapshot as SupervisorSnapshot;
  }

  return null;
}

function extractSupervisorHistory(packet: AuditPacket): SupervisorSnapshot[] {
  const validityHistory = packet.signal_validity?.supervisor_history;
  if (Array.isArray(validityHistory)) {
    return validityHistory.filter((item) => item && typeof item === "object") as SupervisorSnapshot[];
  }
  return [];
}

function isMechanisticContext(value: unknown): value is MechanisticContext {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<MechanisticContext>;
  return Boolean(candidate.c_di_ser && candidate.handover_envelope && candidate.inputs);
}

function summarizeLatestNativeRun(nativeRuns: NativeModelRunArtifact[]): NativeRunSummary | null {
  if (!nativeRuns.length) return null;

  const sorted = [...nativeRuns].sort((a, b) => {
    const aTime = new Date(a.recorded_at).getTime();
    const bTime = new Date(b.recorded_at).getTime();
    return bTime - aTime;
  });
  const latest = sorted[0];
  const result = latest.result ?? {};
  const rawPreview = Array.isArray(result.forecast_preview)
    ? result.forecast_preview
    : Array.isArray(result.forecast)
      ? (result.forecast as unknown[]).slice(0, 4)
      : [];
  const modelKey = latest.model_key;
  const modality = modelKey === "chronos_bolt" || modelKey === "timer_s1" ? "time-series" : "vision";
  const evidenceTier =
    modelKey === "chronos_bolt"
      ? "stabilized_live_timeseries"
      : modelKey === "timer_s1"
        ? "gated_timeseries_fallback"
        : modelKey === "insecta"
          ? "bootstrap_public_vision"
          : modelKey === "yolo11_dsconv"
            ? "specialized_bsf_vision"
            : "native_model_evidence";
  const evidenceLabel =
    modelKey === "chronos_bolt"
      ? "Stabilized live timeseries"
      : modelKey === "timer_s1"
        ? "Gated timeseries fallback"
        : modelKey === "insecta"
          ? "Bootstrap public vision"
          : modelKey === "yolo11_dsconv"
            ? "Specialized BSF vision"
            : "Native model evidence";
  const predictionHorizon =
    typeof result.prediction_horizon === "number"
      ? result.prediction_horizon
      : Array.isArray(result.forecast)
        ? result.forecast.length
        : null;
  const evidenceSummary =
    modality === "time-series"
      ? `${typeof result.metric_name === "string" ? result.metric_name : "sensor_metric"} · horizon ${predictionHorizon ?? "N/A"} · ${
          rawPreview.map((item) => String(item)).slice(0, 3).join(", ") || "no preview"
        }`
      : `${typeof result.detection_count === "number" ? result.detection_count : 0} detections${
          Array.isArray(result.detections) &&
          result.detections[0] &&
          typeof result.detections[0] === "object" &&
          "top_label" in result.detections[0] &&
          result.detections[0].top_label
            ? ` · top label ${String(result.detections[0].top_label)}`
            : ""
        }`;

  return {
    modelKey,
    modality,
    evidenceTier,
    evidenceLabel,
    evidenceSummary,
    executionMode: latest.execution_mode,
    recordedAt: latest.recorded_at,
    artifactPath: latest.artifact_path,
    metricName: typeof result.metric_name === "string" ? result.metric_name : null,
    predictionHorizon:
      typeof result.prediction_horizon === "number"
        ? result.prediction_horizon
        : Array.isArray(result.forecast)
          ? result.forecast.length
          : null,
    forecastPreview: rawPreview.map((item) => String(item)),
    detectionCount: typeof result.detection_count === "number" ? result.detection_count : null,
    topLabel: typeof result.top_label === "string" ? result.top_label : null,
    topCandidates: Array.isArray(result.top_candidates)
      ? result.top_candidates
          .map((item) =>
            item && typeof item === "object" && "label" in item
              ? String((item as { label?: unknown }).label ?? "")
              : String(item),
          )
          .filter(Boolean)
      : [],
    bboxSummary: typeof result.bbox_summary === "string" ? result.bbox_summary : null,
    isLive: latest.execution_mode.includes("live"),
  };
}

export function summarizeAuditPackets(packets: AuditPacket[]) {
  const views = packets.map(getAuditPacketReadModel);
  const passLikeCount = views.filter(
    (packet) => packet.releaseDecision === "PASS" || packet.releaseDecision === "PASS_WITH_RETUNING",
  ).length;
  const freshSignals = views.filter((packet) => packet.signalFreshness.toLowerCase().includes("fresh")).length;
  const portabilityAudits = views.flatMap((packet) =>
    packet.portabilityAudits.map((audit) => ({
      ...audit,
      packetId: packet.id,
      batchLabel: packet.batchLabel,
      signalLabel: packet.signalLabel,
      compiledAt: packet.compiledAt,
    })),
  );

  return {
    views,
    summary: {
      packets: views.length,
      freshSignals,
      passRate: views.length > 0 ? passLikeCount / views.length : null,
      portabilityAudits: portabilityAudits.length,
    },
    portabilityAudits,
  };
}


