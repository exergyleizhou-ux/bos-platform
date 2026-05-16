import type {
  ReviewedExternalCandidateActivationPreviewResponse,
  ReviewedExternalCandidateRollbackPreviewResponse,
  ReviewedExternalCandidateRuntimeReadinessResponse,
} from "@/types/bos";

export type OperatorEvidenceStatus =
  | "operator evidence ready / execution blocked"
  | "operator evidence pending";

export type ExecutionSummary = "blocked" | "enabled";
export type RuntimeReadPathSummary = "enabled" | "pending";

export interface ReviewedCandidateEvidenceInput {
  activationPreview?: ReviewedExternalCandidateActivationPreviewResponse;
  runtimeReadiness?: ReviewedExternalCandidateRuntimeReadinessResponse;
  rollbackPreview?: ReviewedExternalCandidateRollbackPreviewResponse;
}

export interface ReviewedCandidateEvidenceSummary {
  operatorEvidenceStatus: OperatorEvidenceStatus;
  activationExecution: ExecutionSummary;
  runtimeReadPath: RuntimeReadPathSummary;
  runtimePayloadReadable: boolean;
  rollbackExecution: ExecutionSummary;
  rollbackTargetAvailable: boolean;
  releaseDecision: "review_required";
  releaseEvidenceAllowed: boolean;
  sideEffectsBlocked: boolean;
  guardrailSummary: string[];
}

export function buildReviewedCandidateEvidenceSummary({
  activationPreview,
  runtimeReadiness,
  rollbackPreview,
}: ReviewedCandidateEvidenceInput): ReviewedCandidateEvidenceSummary {
  const activationExecution = activationPreview?.can_execute_activation ? "enabled" : "blocked";
  const rollbackExecution = rollbackPreview?.can_execute_rollback ? "enabled" : "blocked";
  const runtimeReadPath = runtimeReadiness?.runtime_read_path_enabled ? "enabled" : "pending";
  const runtimePayloadReadable = runtimeReadiness?.can_read_runtime_payload === true;
  const rollbackTargetAvailable = rollbackPreview?.rollback_target_available === true;
  const releaseEvidenceAllowed =
    readRecord(activationPreview?.activation_audit_contract).release_evidence_allowed === true;
  const sideEffectValues = collectSideEffectValues(
    activationPreview,
    runtimeReadiness,
    rollbackPreview,
  );
  const sideEffectsBlocked = sideEffectValues.every((value) => value === false);
  const hasSideEffectEvidence = sideEffectValues.length > 0;
  const allReadModelsReady = Boolean(activationPreview && runtimeReadiness && rollbackPreview);
  const operatorEvidenceReady =
    allReadModelsReady &&
    activationExecution === "blocked" &&
    rollbackExecution === "blocked" &&
    runtimeReadPath === "enabled" &&
    !releaseEvidenceAllowed &&
    hasSideEffectEvidence &&
    sideEffectsBlocked;

  return {
    operatorEvidenceStatus: operatorEvidenceReady
      ? "operator evidence ready / execution blocked"
      : "operator evidence pending",
    activationExecution,
    runtimeReadPath,
    runtimePayloadReadable,
    rollbackExecution,
    rollbackTargetAvailable,
    releaseDecision: "review_required",
    releaseEvidenceAllowed,
    sideEffectsBlocked: hasSideEffectEvidence && sideEffectsBlocked,
    guardrailSummary: buildGuardrailSummary({
      activationPreview,
      runtimeReadiness,
      rollbackPreview,
      activationExecution,
      runtimeReadPath,
      rollbackExecution,
      releaseEvidenceAllowed,
      sideEffectsBlocked: hasSideEffectEvidence && sideEffectsBlocked,
    }),
  };
}

export function formatReviewedCandidateGuardrail(guardrail: string): string {
  const labels: Record<string, string> = {
    activation_execution_blocked: "Activation execution blocked",
    activation_execution_enabled: "Activation execution enabled",
    runtime_read_path_enabled: "Runtime read path enabled only",
    runtime_read_path_pending: "Runtime readiness pending",
    rollback_execution_blocked: "Rollback execution blocked",
    rollback_execution_enabled: "Rollback execution enabled",
    release_decision_review_required: "Release decision: review_required",
    release_evidence_allowed: "Release evidence allowed",
    release_evidence_blocked: "Release evidence blocked",
    side_effects_blocked: "Side effects blocked",
    side_effects_pending_or_detected: "Side effects pending or detected",
  };

  return labels[guardrail] ?? guardrail.split("_").join(" ");
}

function collectSideEffectValues(
  activationPreview?: ReviewedExternalCandidateActivationPreviewResponse,
  runtimeReadiness?: ReviewedExternalCandidateRuntimeReadinessResponse,
  rollbackPreview?: ReviewedExternalCandidateRollbackPreviewResponse,
): boolean[] {
  return [
    ...Object.values(activationPreview?.side_effects ?? {}),
    ...Object.values(runtimeReadiness?.side_effects ?? {}),
    ...Object.values(rollbackPreview?.side_effects ?? {}),
  ];
}

function buildGuardrailSummary({
  activationPreview,
  runtimeReadiness,
  rollbackPreview,
  activationExecution,
  runtimeReadPath,
  rollbackExecution,
  releaseEvidenceAllowed,
  sideEffectsBlocked,
}: ReviewedCandidateEvidenceInput & {
  activationExecution: ExecutionSummary;
  runtimeReadPath: RuntimeReadPathSummary;
  rollbackExecution: ExecutionSummary;
  releaseEvidenceAllowed: boolean;
  sideEffectsBlocked: boolean;
}): string[] {
  const guardrails = new Set<string>([
    `activation_execution_${activationExecution}`,
    `runtime_read_path_${runtimeReadPath}`,
    `rollback_execution_${rollbackExecution}`,
    "release_decision_review_required",
    releaseEvidenceAllowed ? "release_evidence_allowed" : "release_evidence_blocked",
    sideEffectsBlocked ? "side_effects_blocked" : "side_effects_pending_or_detected",
    ...(activationPreview?.guardrails ?? []),
    ...(runtimeReadiness?.guardrails ?? []),
    ...(rollbackPreview?.guardrails ?? []),
  ]);

  return Array.from(guardrails);
}

function readRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
