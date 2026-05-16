import { describe, expect, it } from "vitest";

import {
  buildReviewedCandidateEvidenceSummary,
  formatReviewedCandidateGuardrail,
} from "@/lib/reviewedCandidateEvidence";
import type {
  ReviewedExternalCandidate,
  ReviewedExternalCandidateActivationPreviewResponse,
  ReviewedExternalCandidateRollbackPreviewResponse,
  ReviewedExternalCandidateRuntimeReadinessResponse,
} from "@/types/bos";

const candidate: ReviewedExternalCandidate = {
  tenant_id: 1,
  candidate_id: "REC-BSF-CARD-002",
  candidate_type: "lca_factor_candidate",
  candidate_type_group: "lca",
  candidate_domain: "lca",
  candidate_key: "lca_factor_candidate:BSF-CARD-002",
  card_id: "BSF-CARD-002",
  source_id: "A-BSF-002",
  source_kind: "peer_reviewed_literature",
  source_ref: "10.1016/j.wasman.2020.07.050",
  license_status: "metadata_only",
  license_note: null,
  ingestion_mode: "manual_review_first",
  review_status: "approved_for_candidate_use",
  reviewer: "Dr. Reviewer",
  reviewed_at: "2026-04-27T00:00:00Z",
  boundary_condition: "Reviewed metadata boundary only.",
  allowed_use: "candidate metadata only",
  blocked_use: "no validated defaults; no release evidence; no runtime activation",
  candidate_payload: {
    payload_version: "bsf-reviewed-metadata-v1",
    title: "Metadata-only source review",
    doi: "10.1016/j.wasman.2020.07.050",
    article_type: "review",
    numeric_values_included: false,
  },
  human_review_required: true,
  promotion_enabled: false,
  runtime_activated: false,
  validated_default_write_enabled: false,
  activation_relation_id: null,
  audit_payload: {},
  created_at: "2026-04-27T00:00:00Z",
  updated_at: "2026-04-27T00:00:00Z",
};

const activationPreview: ReviewedExternalCandidateActivationPreviewResponse = {
  schema_version: "reviewed_external_candidate_activation_preview_v1",
  tenant_id: 1,
  candidate,
  activation_scope: {
    tenant_id: 1,
    tenant_scoped: true,
    candidate_type: "lca_factor_candidate",
    candidate_key: "lca_factor_candidate:BSF-CARD-002",
  },
  active_overlay_state: {
    active_activation_id: null,
    activation_required_before_runtime_use: true,
  },
  activation_audit_contract: {
    activation_audit_id_required: true,
    activation_execution_endpoint_enabled: false,
    release_evidence_allowed: false,
  },
  can_execute_activation: false,
  runtime_overlay_preview_only: true,
  rollback_required: true,
  side_effects: {
    runtime_activation: false,
    validated_default_write: false,
    species_db_write: false,
    feedstock_db_write: false,
  },
  guardrails: ["activation_requires_audit_packet"],
};

const runtimeReadiness: ReviewedExternalCandidateRuntimeReadinessResponse = {
  schema_version: "reviewed_external_candidate_runtime_readiness_v1",
  tenant_id: 1,
  candidate,
  activation_scope: {
    tenant_id: 1,
    tenant_scoped: true,
    candidate_type: "lca_factor_candidate",
    candidate_key: "lca_factor_candidate:BSF-CARD-002",
  },
  active_overlay_state: {
    active_activation_id: "RUNTIME-ACTIVATION-READONLY-001",
    active_registry_version: 1,
  },
  active_candidate_payload: {
    title: "Metadata-only source review",
  },
  can_read_runtime_payload: true,
  runtime_read_path_enabled: true,
  rollback_required: true,
  rollback_contract: {
    rollback_execution_endpoint_enabled: false,
    rollback_target_required: true,
  },
  side_effects: {
    runtime_activation: false,
    runtime_rollback: false,
    validated_default_write: false,
    final_action_execution: false,
  },
  guardrails: ["runtime_read_path_only"],
};

const rollbackPreview: ReviewedExternalCandidateRollbackPreviewResponse = {
  schema_version: "reviewed_external_candidate_rollback_preview_v1",
  tenant_id: 1,
  candidate,
  activation_scope: {
    tenant_id: 1,
    tenant_scoped: true,
    candidate_type: "lca_factor_candidate",
    candidate_key: "lca_factor_candidate:BSF-CARD-002",
  },
  active_overlay_state: {
    active_activation_id: "RUNTIME-ACTIVATION-READONLY-001",
    active_registry_version: 1,
  },
  rollback_contract: {
    rollback_execution_endpoint_enabled: false,
    rollback_target_required: true,
  },
  rollback_audit_packet: {
    active_activation_id: "RUNTIME-ACTIVATION-READONLY-001",
    rollback_target_available: true,
  },
  rollback_target_available: true,
  can_execute_rollback: false,
  rollback_preview_only: true,
  rollback_required: true,
  rollback_blockers: [],
  side_effects: {
    runtime_activation: false,
    runtime_rollback: false,
    validated_default_write: false,
    final_action_execution: false,
  },
  guardrails: ["rollback_requires_audit_packet"],
};

describe("reviewed candidate operator evidence read model", () => {
  it("marks evidence ready when all read models are present and execution remains blocked", () => {
    const summary = buildReviewedCandidateEvidenceSummary({
      activationPreview,
      runtimeReadiness,
      rollbackPreview,
    });

    expect(summary).toMatchObject({
      operatorEvidenceStatus: "operator evidence ready / execution blocked",
      activationExecution: "blocked",
      runtimeReadPath: "enabled",
      runtimePayloadReadable: true,
      rollbackExecution: "blocked",
      rollbackTargetAvailable: true,
      releaseDecision: "review_required",
      releaseEvidenceAllowed: false,
      sideEffectsBlocked: true,
    });
    expect(summary.guardrailSummary).toContain("release_decision_review_required");
    expect(summary.guardrailSummary).toContain("side_effects_blocked");
  });

  it("keeps status pending while runtime readiness is still unavailable", () => {
    const summary = buildReviewedCandidateEvidenceSummary({
      activationPreview,
      rollbackPreview,
    });

    expect(summary.operatorEvidenceStatus).toBe("operator evidence pending");
    expect(summary.runtimeReadPath).toBe("pending");
    expect(summary.activationExecution).toBe("blocked");
    expect(summary.rollbackExecution).toBe("blocked");
  });

  it("does not mark evidence ready when any side effect is true", () => {
    const summary = buildReviewedCandidateEvidenceSummary({
      activationPreview,
      runtimeReadiness: {
        ...runtimeReadiness,
        side_effects: {
          ...runtimeReadiness.side_effects,
          runtime_activation: true,
        },
      },
      rollbackPreview,
    });

    expect(summary.operatorEvidenceStatus).toBe("operator evidence pending");
    expect(summary.sideEffectsBlocked).toBe(false);
    expect(summary.guardrailSummary).toContain("side_effects_pending_or_detected");
  });

  it("does not mark evidence ready when release evidence is allowed", () => {
    const summary = buildReviewedCandidateEvidenceSummary({
      activationPreview: {
        ...activationPreview,
        activation_audit_contract: {
          ...activationPreview.activation_audit_contract,
          release_evidence_allowed: true,
        },
      },
      runtimeReadiness,
      rollbackPreview,
    });

    expect(summary.operatorEvidenceStatus).toBe("operator evidence pending");
    expect(summary.releaseDecision).toBe("review_required");
    expect(summary.releaseEvidenceAllowed).toBe(true);
    expect(summary.guardrailSummary).toContain("release_evidence_allowed");
  });

  it("formats guardrail keys without changing stable summary fields", () => {
    expect(formatReviewedCandidateGuardrail("runtime_read_path_enabled")).toBe(
      "Runtime read path enabled only",
    );
    expect(formatReviewedCandidateGuardrail("release_decision_review_required")).toBe(
      "Release decision: review_required",
    );
    expect(formatReviewedCandidateGuardrail("custom_backend_guardrail")).toBe(
      "custom backend guardrail",
    );
  });
});
