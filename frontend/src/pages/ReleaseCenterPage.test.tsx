/**
 * @vitest-environment jsdom
 */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const {
  useCodeReleaseReadinessMock,
  useBrainRuntimeMock,
  useRecentTimeseriesRisksMock,
  navigateMock,
  assistantApiMock,
  bosApiMock,
  finalActionsApiMock,
  governanceApiMock,
  simulationLabApiMock,
  releasePacketApiMock,
  bosKernelsApiMock,
} = vi.hoisted(() => ({
  useCodeReleaseReadinessMock: vi.fn(),
  useBrainRuntimeMock: vi.fn(),
  useRecentTimeseriesRisksMock: vi.fn(),
  navigateMock: vi.fn(),
    assistantApiMock: {
      listRuns: vi.fn(),
      getReviewWorkbench: vi.fn(),
      exportReviewWorkbenchAuditPacket: vi.fn(),
      persistReviewWorkbenchAuditPacketSnapshot: vi.fn(),
      confirm: vi.fn(),
      resolveHumanApprovalRequest: vi.fn(),
    },
  bosApiMock: {
    listLiteratureExtractionCandidates: vi.fn(),
    getLiteratureValuePromotionAuditExport: vi.fn(),
    createLiteratureValueReleaseEvidenceLink: vi.fn(),
    listReviewedExternalCandidates: vi.fn(),
    getReviewedExternalCandidateSummary: vi.fn(),
    getReviewedExternalCandidateActivationPreview: vi.fn(),
    getReviewedExternalCandidateRuntimeReadiness: vi.fn(),
    getReviewedExternalCandidateRollbackPreview: vi.fn(),
  },
  finalActionsApiMock: {
    getReadiness: vi.fn(),
    getAuditRecords: vi.fn(),
    getRequestDrafts: vi.fn(),
    createRequestDraft: vi.fn(),
    resolveRequestDraft: vi.fn(),
    getRequestDraftExecutionReadiness: vi.fn(),
    executeFinalReleaseApproval: vi.fn(),
    executeFinalModelActivation: vi.fn(),
    executeFinalExternalReleaseShare: vi.fn(),
    getSourceReviewPacket: vi.fn(),
    getLatestSourceReviewPacket: vi.fn(),
  },
  governanceApiMock: {
    getRCManifest: vi.fn(),
  },
  simulationLabApiMock: {
    listScenarios: vi.fn(),
    getReleaseAppendix: vi.fn(),
    exportReleaseAppendix: vi.fn(),
  },
  releasePacketApiMock: {
    attachSimulationAppendix: vi.fn(),
    listAppendices: vi.fn(),
    createApprovalRequest: vi.fn(),
  },
  bosKernelsApiMock: {
    listBenchmarkCases: vi.fn(),
    createBenchmarkRun: vi.fn(),
    listBenchmarkRuns: vi.fn(),
    listModels: vi.fn(),
    listModelProviderCapabilities: vi.fn(),
    listExternalKnowledgeCandidates: vi.fn(),
    requestExternalKnowledgePromotion: vi.fn(),
    resolveExternalKnowledgePromotion: vi.fn(),
    applyExternalKnowledgeRegistryPatch: vi.fn(),
    listExternalKnowledgeValidatedRegistry: vi.fn(),
    getExternalKnowledgeRuntimeActivationReadiness: vi.fn(),
    listExternalKnowledgeRuntimeActivationState: vi.fn(),
    createExternalKnowledgeRuntimeActivationDraft: vi.fn(),
    resolveExternalKnowledgeRuntimeActivationDraft: vi.fn(),
    getExternalKnowledgeRuntimeActivationExecutionReadiness: vi.fn(),
    executeExternalKnowledgeRuntimeActivation: vi.fn(),
    rollbackExternalKnowledgeRuntimeActivation: vi.fn(),
    registerModelCandidate: vi.fn(),
    requestModelGovernanceReview: vi.fn(),
    listKnowledgeRelations: vi.fn(),
  },
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
}));

vi.mock("@/hooks/code/useCode", () => ({
  useCodeReleaseReadiness: useCodeReleaseReadinessMock,
}));
vi.mock("@/hooks/useBos", () => ({
  useBrainRuntime: useBrainRuntimeMock,
  useRecentTimeseriesRisks: useRecentTimeseriesRisksMock,
}));
vi.mock("react-hot-toast", () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));
vi.mock("@/api/simulationLabApi", () => ({
  simulationLabApi: simulationLabApiMock,
}));
vi.mock("@/api/assistantApi", () => ({
  assistantApi: assistantApiMock,
}));
vi.mock("@/api/bosApi", () => ({
  bosApi: bosApiMock,
}));
vi.mock("@/api/finalActionsApi", () => ({
  finalActionsApi: finalActionsApiMock,
}));
vi.mock("@/api/governanceApi", () => ({
  governanceApi: governanceApiMock,
}));
vi.mock("@/api/releasePacketApi", () => ({
  releasePacketApi: releasePacketApiMock,
}));
vi.mock("@/api/bosKernelsApi", () => ({
  bosKernelsApi: bosKernelsApiMock,
}));

vi.mock("@/components/code/ReleaseReadinessCard", () => ({
  ReleaseReadinessCard: ({ readiness }: { readiness: { release_state: string } }) => (
    <div>Release readiness card: {readiness.release_state}</div>
  ),
}));
vi.mock("@/components/bos/BrainOperatorContextCard", () => ({
  BrainOperatorContextCard: () => <div>Brain operator context card</div>,
}));

import ReleaseCenterPage, { buildReleaseProofCardsFromAssistantRun } from "@/pages/ReleaseCenterPage";

const appendixFixture = {
  simulation_id: "SIM-RC",
  generated_at: "2026-04-24T00:00:00Z",
  scenario: {
    simulation_id: "SIM-RC",
    batch_id: "VIRTUAL-BSF-RC",
    tenant_id: 1,
    species: "BSF",
    feedstock: "mixed_food_waste",
    scenario: "moisture_drift",
    initial_state: {
      biomass: 0.5,
      substrate: 10,
      temperature: 28,
      moisture: 70,
      nitrogen: 50,
    },
    cycles: 8,
    seed: 17,
    policy: "rule_based",
    status: "created",
    created_at: "2026-04-24T00:00:00Z",
    evidence_sources: [],
  },
  selected_run: {
    run_id: "RUN-RC",
    tenant_id: 1,
    status: "completed",
    engine_version: "simulation_lab_v2_8",
    model_version: null,
    input_snapshot_id: "INP-RC",
    input_snapshot_hash: "hash",
    replay_of_run_id: null,
    evidence_pack_id: "EVP-RC",
    started_at: "2026-04-24T00:00:00Z",
    completed_at: "2026-04-24T00:01:00Z",
    created_at: "2026-04-24T00:00:00Z",
    simulation_id: "SIM-RC",
    cycle_count: 8,
    scenario: "moisture_drift",
    policy: "rule_based",
    starting_risk: 0.6,
    ending_risk: 0.35,
    risk_delta: -0.25,
    action_count: 2,
    audit_event_count: 8,
    final_state: {},
  },
  comparison_runs: [],
  audit_trace_hashes: [],
  evidence_pack_id: "EVP-RC",
  input_snapshot_id: "INP-RC",
  disclaimer: "review only",
};

function renderInteractive() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => {
    root.render(<ReleaseCenterPage />);
  });
  return { container, root };
}

async function flushAsyncWork() {
  await act(async () => {
    await Promise.resolve();
  });
}

function buttonByText(container: HTMLElement, text: string): HTMLButtonElement {
  const button = Array.from(container.querySelectorAll("button")).find((item) =>
    item.textContent?.includes(text),
  );
  if (!button) throw new Error(`Button not found: ${text}`);
  return button as HTMLButtonElement;
}

const emptyReviewWorkbench = {
  assistant_confirmations: [],
  human_approval_requests: [],
  guardrails: [
    "tenant_scoped_read_model",
    "queue_only_confirmation_management",
    "release_decision_remains_review_required",
    "no_auto_model_activation",
    "no_external_sharing",
  ],
};

const rcManifestFixture = {
  generated_at: "2026-04-28T10:33:40Z",
  release_state: "review_required",
  candidate_evidence_state: "ready_for_review",
  preflight_pass_count: 21,
  preflight_warn_count: 0,
  preflight_fail_count: 0,
  review_required_items: [],
  local_validation_notes: [],
  recommended_next_action: "Move this candidate to human approval required review and circulate the dossier.",
  bos_v9_target_progress_percent: 91,
  bos_v9_target_scorecard: [
    {
      dimension: "reproducible_p0_baseline",
      score: 9,
      target: 9,
      evidence: "P0 has zero failures and zero warnings with the default stack online.",
    },
    {
      dimension: "release_reference_evidence",
      score: 8,
      target: 9,
      evidence: "Release+Reference joint smoke passed.",
    },
  ],
  safety_boundary: {
    release_decision: "review_required",
    model_version: "ready_for_review",
    final_action_draft_count: 0,
    final_action_audit_record_count: 0,
    external_share_record_created: false,
    final_action_execute_call_count: 0,
    validated_default_write_enabled: false,
    runtime_activation_enabled: false,
    hardware_execution_enabled: false,
    final_action_execution_enabled: false,
  },
  release_reference_smoke_passed: true,
  checks: [
    { status: "ready_for_review", raw_status: "PASS", name: "backend integration", summary: "completed" },
  ],
  artifacts: {
    bos_v9_rc_manifest: "reports/stabilize-v9/BOS_V9_RC_MANIFEST.json",
  },
} as const;

const finalActionReadinessFixture = {
  schema_version: "final_action_readiness_v1",
  generated_at: "2026-04-25T00:04:00Z",
  tenant_id: 1,
  review_only: true,
  audit_schema_available: true,
  request_draft_schema_available: true,
  source_review_packet_required: true,
  source_review_packet_id: "FARP-RC",
  current_state: {
    latest_release_decision_id: 1,
    latest_release_decision: "review_required",
    latest_model_version_id: "MV-RC",
    latest_model_version_status: "ready_for_review",
    pending_review_items: 2,
    resolved_review_items: 2,
    evidence_pack_ids: ["EVP-ASSISTANT", "EVP-BMR"],
    external_share_record_created: false,
    final_action_request_drafts_created: false,
  },
  actions: [
    {
      action: "final_release_approval",
      status: "blocked",
      executable: false,
      blockers: ["request_draft_required", "approved_request_draft_required", "specific_final_action_approver_role_required"],
      required_roles: ["final_release_approver"],
      required_evidence_ids: ["EVP-ASSISTANT", "EVP-BMR"],
      missing_evidence_ids: [],
      source_review_packet_required: true,
      source_review_packet_id: "FARP-RC",
      side_effects_if_executed: {
        release_decision: "not_executed",
        model_activation: false,
        external_share: false,
        hardware_execution: false,
      },
    },
    {
      action: "model_activation",
      status: "locked",
      executable: false,
      blockers: ["request_draft_required", "approved_request_draft_required", "specific_final_action_approver_role_required"],
      required_roles: ["model_governance_approver"],
      required_evidence_ids: ["EVP-BMR"],
      missing_evidence_ids: [],
      source_review_packet_required: true,
      source_review_packet_id: "FARP-RC",
      side_effects_if_executed: {
        release_decision: "not_executed",
        model_activation: false,
        external_share: false,
        hardware_execution: false,
      },
    },
    {
      action: "external_release_share",
      status: "locked",
      executable: false,
      blockers: [
        "request_draft_required",
        "approved_request_draft_required",
        "specific_final_action_approver_role_required",
        "release_packet_attachment_required",
      ],
      required_roles: ["external_release_share_approver"],
      required_evidence_ids: ["EVP-ASSISTANT", "EVP-BMR"],
      missing_evidence_ids: ["redacted_release_packet_evidence"],
      source_review_packet_required: true,
      source_review_packet_id: "FARP-RC",
      side_effects_if_executed: {
        release_decision: "not_executed",
        model_activation: false,
        external_share: false,
        hardware_execution: false,
      },
    },
  ],
  guardrails: [
    "readiness_only",
    "readiness_query_does_not_execute_final_actions",
    "no_assistant_confirmation_authority",
    "no_human_approval_disposition_authority",
    "tenant_scoped_read_model",
    "final_action_routes_require_approved_request_draft",
    "external_network_send_requires_separate_gate",
    "no_hardware_execution",
  ],
} as const;

const finalActionSourcePacketFixture = {
  schema_version: "final_action_review_packet_snapshot_v1",
  tenant_id: 1,
  review_only: true,
  source_review_packet_id: "FARP-RC",
  packet_type: "assistant_review_workbench_audit_packet",
  packet_hash: "abcdef1234567890abcdef1234567890",
  evidence_pack_ids: ["EVP-ASSISTANT", "EVP-BMR"],
  generated_by_user_id: 1,
  created_at: "2026-04-25T00:04:00Z",
  packet_payload: {
    final_actions: {
      release_approval: "not_executed",
      model_activation: "not_executed",
      external_share: "not_executed",
    },
  },
  guardrails: [
    "read_only_source_review_packet",
    "immutable_packet_snapshot",
    "tenant_scoped_read_model",
    "final_actions_not_executed",
  ],
} as const;

const finalActionAuditRecordsFixture = {
  schema_version: "final_action_audit_records_read_model_v1",
  tenant_id: 1,
  review_only: true,
  count: 0,
  records: [],
  guardrails: [
    "read_only_final_action_audit_records",
    "final_actions_not_executed",
    "tenant_scoped_read_model",
  ],
} as const;

const finalActionRequestDraftsFixture = {
  schema_version: "final_action_request_drafts_read_model_v1",
  tenant_id: 1,
  review_only: true,
  count: 0,
  drafts: [],
  guardrails: [
    "read_only_final_action_request_drafts",
    "final_action_drafts_not_created_by_assistant",
    "final_actions_not_executed",
  ],
} as const;

const literaturePromotionAuditExportFixture = {
  schema_version: "literature_value_promotion_audit_export_v1",
  tenant_id: 1,
  candidate_id: "LIT-CAND-001",
  export_format: "json",
  export_policy: "response_only_no_file_write",
  content_hash: "a".repeat(64),
  export_manifest: {
    export_id: "literature-value-promotion-audit-export:LIT-CAND-001:aaaaaaaaaaaa",
    candidate_id: "LIT-CAND-001",
    content_hash_algorithm: "sha256",
    content_hash: "a".repeat(64),
    export_policy: "response_only_no_file_write",
    file_written: false,
    promotion_request_count: 1,
    approval_count: 2,
    overlay_count: 1,
    runtime_activation_count: 1,
    release_evidence_link_count: 1,
    rollback_count: 1,
  },
  request: {
    promotion_request_id: "LVPR-001",
    request_status: "approved_for_promotion",
    raw_value: "72",
    unit: "g/kg",
    conditions: { feedstock: "wheat bran", source_ref: "10.1016/j.wasman.2020.01.001" },
  },
  approvals: [
    { approval_id: "LVPA-SCI-001", approver_role: "scientist", approval_action: "approve" },
    { approval_id: "LVPA-RM-001", approver_role: "release_manager", approval_action: "approve" },
  ],
  overlay: {
    overlay_id: "LVO-001",
    overlay_status: "promoted_inactive",
    normalized_value: "72 g/kg",
    source_ref: "10.1016/j.wasman.2020.01.001",
    overlay_hash: "overlayhash1234567890",
    approval_hash: "approvalhash1234567890",
    validity_scope: { feedstock: "wheat bran", treatment: "drying" },
    rollback_pointer: { rollback_required_before_use_change: true },
  },
  runtime_activation: {
    activation_id: "LVA-001",
    activation_status: "active",
    activation_scope: { candidate_type: "literature_value", feedstock: "wheat bran" },
  },
  release_evidence_link: {
    link_id: "LVREL-001",
    link_status: "active",
    rollback_status: "rolled_back",
  },
  rollback: {
    rollback_id: "LVRB-001",
    rollback_status: "completed",
  },
  db_pollution_proof: {
    validated_default_write: false,
    species_db_write: false,
    feedstock_db_write: false,
  },
  final_action_non_execution_proof: {
    final_action_execution: false,
    release_auto_approval: false,
    release_decision_update: false,
    release_decisions_all_review_required: true,
    release_decision_states: [
      {
        release_decision_id: 1,
        release_decision_before: "review_required",
        release_decision_after: "review_required",
      },
    ],
  },
  side_effects: {
    file_written: false,
    runtime_activation: false,
    runtime_deactivation: false,
    release_decision_update: false,
    release_auto_approval: false,
    validated_default_write: false,
    species_db_write: false,
    feedstock_db_write: false,
    final_action_execution: false,
  },
  guardrails: [
    "promotion_audit_export_is_response_only",
    "export_response_only_no_file_write",
    "release_decision_remains_review_required",
    "no_final_action_execution",
  ],
} as const;

const reviewedMetadataLaneFixture = {
  items: [
    {
      tenant_id: 1,
      candidate_id: "REC-BSF-CARD-001",
      candidate_type: "bsf_reviewed_metadata_candidate",
      candidate_key: "bsf_reviewed_metadata_candidate:BSF-CARD-001",
      card_id: "BSF-CARD-001",
      source_id: "A-BSF-001",
      source_kind: "peer_reviewed_literature",
      source_ref: "10.1016/j.wasman.2020.01.001",
      license_status: "metadata_only",
      license_note: "Metadata-only review cleared; no copied numeric tables.",
      ingestion_mode: "metadata_only",
      review_status: "approved_for_candidate_use",
      reviewer: "Dr. Reviewer",
      reviewed_at: "2026-04-26T00:00:00Z",
      boundary_condition: "Use citation and method boundary metadata only.",
      allowed_use: "reviewed candidate metadata for later activation review",
      blocked_use: "no validated defaults; no release evidence; no runtime activation",
      candidate_payload: {
        payload_version: "bsf-reviewed-metadata-v1",
        candidate_family: "bsf_reviewed_metadata",
        card_id: "BSF-CARD-001",
        shortlist_id: "BSF-LIT-001",
        source_catalog_id: "A-BSF-001",
        doi: "10.1016/j.wasman.2020.01.001",
        source_url: "https://doi.org/10.1016/j.wasman.2020.01.001",
        title: "BSF substrate conversion review",
        article_type: "review",
        target_boundary_fields: "method boundary, substrate class, lifecycle stage",
        boundary_condition: "Use citation and method boundary metadata only.",
        allowed_use: "reviewed candidate metadata for later activation review",
        blocked_use: "no validated defaults; no release evidence; no runtime activation",
        evidence_source_kind: "peer_reviewed_literature",
        ingestion_mode: "metadata_only",
        license_status: "metadata_only",
        source_kind: "peer_reviewed_literature",
        source_ref: "10.1016/j.wasman.2020.01.001",
        numeric_values_included: false,
        extracted_numeric_values: {},
        promotion_enabled: false,
        runtime_activated: false,
        validated_default_write_enabled: false,
        runtime_activation_required_before_use: true,
        reviewer_annotations: {},
      },
      human_review_required: true,
      promotion_enabled: false,
      runtime_activated: false,
      validated_default_write_enabled: false,
      activation_relation_id: null,
      audit_payload: {},
      created_at: "2026-04-26T00:00:00Z",
      updated_at: "2026-04-26T00:00:00Z",
    },
  ],
  count: 1,
  guardrails: [
    "approved_for_candidate_use_is_not_runtime_activation",
    "runtime_activated_false_until_overlay_activation",
    "validated_default_write_enabled_false",
  ],
} as const;

const reviewedMetadataSummaryFixture = {
  schema_version: "reviewed_external_candidate_lane_summary_v1",
  tenant_id: 1,
  reviewed_candidate_count: 1,
  reviewed_metadata_candidate_count: 1,
  pending_runtime_activation_count: 1,
  runtime_activated_count: 0,
  validated_default_write_enabled_count: 0,
  numeric_value_candidate_count: 0,
  release_evidence_blocked_count: 1,
  statuses: { approved_for_candidate_use: 1 },
  candidate_types: { bsf_reviewed_metadata_candidate: 1 },
  latest_reviewed_at: "2026-04-26T00:00:00Z",
  guardrails: [
    "summary_is_read_only",
    "approved_for_candidate_use_is_not_runtime_activation",
    "numeric_values_remain_blocked_for_bsf_metadata_lane",
    "validated_default_write_enabled_false",
  ],
} as const;

const reviewedMetadataActivationPreviewFixture = {
  schema_version: "reviewed_external_candidate_activation_preview_v1",
  tenant_id: 1,
  candidate: reviewedMetadataLaneFixture.items[0],
  activation_scope: {
    tenant_id: 1,
    tenant_scoped: true,
    candidate_type: "bsf_reviewed_metadata_candidate",
    candidate_key: "bsf_reviewed_metadata_candidate:BSF-CARD-001",
    runtime_paths: ["external_knowledge.runtime"],
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
    final_action_execution: false,
  },
  guardrails: ["activation_preview_is_read_only"],
} as const;

const reviewedMetadataRuntimeReadinessFixture = {
  schema_version: "reviewed_external_candidate_runtime_readiness_v1",
  tenant_id: 1,
  candidate: reviewedMetadataLaneFixture.items[0],
  activation_scope: {
    tenant_id: 1,
    tenant_scoped: true,
    candidate_type: "bsf_reviewed_metadata_candidate",
    candidate_key: "bsf_reviewed_metadata_candidate:BSF-CARD-001",
    runtime_paths: ["external_knowledge.runtime"],
  },
  active_overlay_state: {
    active_activation_id: null,
    activation_required_before_runtime_use: true,
  },
  active_candidate_payload: null,
  can_read_runtime_payload: false,
  runtime_read_path_enabled: true,
  rollback_required: true,
  rollback_contract: {
    rollback_required: true,
    rollback_execution_endpoint_enabled: false,
    rollback_target_required: false,
  },
  side_effects: {
    runtime_activation: false,
    runtime_rollback: false,
    validated_default_write: false,
    final_action_execution: false,
  },
  guardrails: ["runtime_readiness_is_read_only"],
} as const;

const reviewedMetadataRollbackPreviewFixture = {
  schema_version: "reviewed_external_candidate_rollback_preview_v1",
  tenant_id: 1,
  candidate: reviewedMetadataLaneFixture.items[0],
  activation_scope: {
    tenant_id: 1,
    tenant_scoped: true,
    candidate_type: "bsf_reviewed_metadata_candidate",
    candidate_key: "bsf_reviewed_metadata_candidate:BSF-CARD-001",
    runtime_paths: ["external_knowledge.runtime"],
  },
  active_overlay_state: {
    active_activation_id: null,
    activation_required_before_runtime_use: true,
  },
  rollback_contract: {
    rollback_required: true,
    rollback_execution_endpoint_enabled: false,
    rollback_target_required: false,
  },
  rollback_audit_packet: {
    tenant_id: 1,
    candidate_id: "REC-BSF-CARD-001",
    rollback_target_available: false,
    rollback_execution_endpoint_enabled: false,
    blocked_until: ["no_active_runtime_activation_to_rollback"],
  },
  rollback_target_available: false,
  can_execute_rollback: false,
  rollback_preview_only: true,
  rollback_required: true,
  rollback_blockers: ["no_active_runtime_activation_to_rollback"],
  side_effects: {
    runtime_activation: false,
    runtime_rollback: false,
    validated_default_write: false,
    final_action_execution: false,
  },
  guardrails: ["rollback_preview_is_read_only"],
} as const;

describe("ReleaseCenterPage", () => {
  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    vi.clearAllMocks();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:release-center-audit"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
    Object.defineProperty(HTMLAnchorElement.prototype, "click", {
      configurable: true,
      value: vi.fn(),
    });
    simulationLabApiMock.listScenarios.mockResolvedValue([{ simulation_id: "SIM-RC" }]);
    simulationLabApiMock.getReleaseAppendix.mockResolvedValue(appendixFixture);
    simulationLabApiMock.exportReleaseAppendix.mockResolvedValue(new Blob(["appendix"]));
    assistantApiMock.listRuns.mockResolvedValue([]);
    assistantApiMock.getReviewWorkbench.mockResolvedValue(emptyReviewWorkbench);
    assistantApiMock.exportReviewWorkbenchAuditPacket.mockResolvedValue(new Blob(["audit packet"]));
    assistantApiMock.confirm.mockResolvedValue(makeAssistantRunWithReleaseProofs());
    bosApiMock.listReviewedExternalCandidates.mockResolvedValue(reviewedMetadataLaneFixture);
    bosApiMock.getReviewedExternalCandidateSummary.mockResolvedValue(reviewedMetadataSummaryFixture);
    bosApiMock.getReviewedExternalCandidateActivationPreview.mockResolvedValue(reviewedMetadataActivationPreviewFixture);
    bosApiMock.getReviewedExternalCandidateRuntimeReadiness.mockResolvedValue(reviewedMetadataRuntimeReadinessFixture);
    bosApiMock.getReviewedExternalCandidateRollbackPreview.mockResolvedValue(reviewedMetadataRollbackPreviewFixture);
    assistantApiMock.resolveHumanApprovalRequest.mockResolvedValue({
      approval_request_id: "HAR-MODEL",
      release_decision_id: null,
      subject_type: "model_version",
      subject_id: "MV-RC",
      status: "approved",
      reason: "Release Center workbench resolved this review request only; release/model/share state remains unchanged.",
      payload: {
        benchmark_run_id: "BMR-RC",
        evidence_pack_id: "EVP-BMR",
        workbench_resolution: {
          scope: "human_approval_request_only",
          side_effects: {
            release_decision: "unchanged",
            model_activation: false,
            external_share: false,
          },
        },
      },
      source_assistant_run_id: "ARUN-RC-PROOFS",
      source_evidence_pack_id: "EVP-ASSISTANT",
      evidence_pack_ids: ["EVP-BMR"],
      risk_guardrails: ["resolved_review_request_only", "no_auto_model_activation", "no_external_sharing"],
      created_at: "2026-04-25T00:00:00Z",
      resolved_at: "2026-04-25T00:02:00Z",
    });
    finalActionsApiMock.getReadiness.mockResolvedValue(finalActionReadinessFixture);
    finalActionsApiMock.getAuditRecords.mockResolvedValue(finalActionAuditRecordsFixture);
    finalActionsApiMock.getRequestDrafts.mockResolvedValue(finalActionRequestDraftsFixture);
    finalActionsApiMock.getSourceReviewPacket.mockResolvedValue(finalActionSourcePacketFixture);
    finalActionsApiMock.getLatestSourceReviewPacket.mockResolvedValue(finalActionSourcePacketFixture);
    governanceApiMock.getRCManifest.mockResolvedValue(rcManifestFixture);
    assistantApiMock.persistReviewWorkbenchAuditPacketSnapshot.mockResolvedValue(finalActionSourcePacketFixture);
    bosApiMock.listLiteratureExtractionCandidates.mockResolvedValue({
      schema_version: "literature_extraction_candidate_list_v1",
      tenant_id: 1,
      count: 1,
      items: [
        {
          candidate_id: "LIT-CAND-001",
          candidate_uid: "literature_value:LIT-CAND-001",
          candidate_type: "literature_value_candidate",
          review_status: "pending_review",
          source_ref: "10.1016/j.wasman.2020.01.001",
          source_kind: "peer_reviewed_literature",
          feedstock: "wheat bran",
          treatment: "drying",
          condition_context: "lab scale",
          raw_value: "72",
          unit: "g/kg",
          human_review_required: true,
          runtime_activated: false,
          validated_default_write_enabled: false,
        },
      ],
      guardrails: ["human_review_required"],
    });
    bosApiMock.getLiteratureValuePromotionAuditExport.mockResolvedValue(literaturePromotionAuditExportFixture);
    bosApiMock.createLiteratureValueReleaseEvidenceLink.mockResolvedValue({
      link_id: "LVREL-NEW",
      release_decision_before: "review_required",
      release_decision_after: "review_required",
      release_decision_unchanged: true,
      final_action_execution: false,
      side_effects: {
        release_decision_update: false,
        release_auto_approval: false,
        final_action_execution: false,
        validated_default_write: false,
        species_db_write: false,
        feedstock_db_write: false,
      },
    });
    releasePacketApiMock.listAppendices.mockResolvedValue([]);
    releasePacketApiMock.attachSimulationAppendix.mockResolvedValue({
      attachment_id: "RPA-RC",
      release_decision_id: 1,
      tenant_id: 1,
      user_id: 1,
      attachment_type: "simulation_appendix",
      simulation_id: "SIM-RC",
      run_id: "RUN-RC",
      evidence_pack_id: "EVP-RC",
      appendix_hash: "hash",
      payload: {},
      created_at: "2026-04-24T00:00:00Z",
    });
    releasePacketApiMock.createApprovalRequest.mockResolvedValue({
      approval_request_id: "HAR-RC",
      release_decision_id: 1,
      tenant_id: 1,
      user_id: 1,
      subject_type: "release_decision",
      subject_id: "1",
      status: "pending",
      reason: "Review simulation appendix evidence before release decision",
      payload: {},
      created_at: "2026-04-24T00:00:00Z",
      resolved_at: null,
    });
    bosKernelsApiMock.listBenchmarkCases.mockResolvedValue([
      {
        case_id: "CASE-moisture_drift",
        name: "moisture_drift",
        scenario_payload: { scenario: "moisture_drift" },
        expected_metrics: { max_ending_risk: 0.55 },
      },
    ]);
    bosKernelsApiMock.createBenchmarkRun.mockResolvedValue({
      benchmark_run_id: "BMR-RC",
      suite_name: "simulation_lab_regression",
      scorecard: {
        status: "ready_for_review",
        suite_gate: "human_review_required",
        case_count: 1,
        passed_count: 1,
        failed_count: 0,
        cases: [
          {
            case_id: "CASE-moisture_drift",
            name: "moisture_drift",
            status: "passed",
            simulation_id: "SIM-BMR-RC",
            run_id: "RUN-BMR-RC",
            evidence_pack_id: "EVP-BMR-CASE",
            metrics: {
              ending_risk: 0.35,
              audit_event_count: 8,
              cycle_count: 8,
            },
            assertions: [{ metric: "ending_risk", passed: true }],
            expected_metrics: { max_ending_risk: 0.55 },
          },
        ],
      },
      evidence_pack_id: "EVP-BMR",
      created_at: "2026-04-24T00:00:00Z",
    });
    bosKernelsApiMock.listBenchmarkRuns.mockResolvedValue([]);
    bosKernelsApiMock.listModels.mockResolvedValue([]);
    bosKernelsApiMock.listModelProviderCapabilities.mockResolvedValue({
      providers: [
        {
          model_id: "gpt-5.4",
          provider: "OpenAI",
          context_window: null,
          tool_calling: null,
          json_schema_output: null,
          vision: null,
          embedding: null,
          pricing_input: null,
          pricing_output: null,
          rate_limit: null,
          data_retention_policy: null,
          deployment_region: "global",
          fallback_candidate: true,
          source_ref: "https://platform.openai.com/docs",
          checked_date: "2026-04-26",
          review_status: "pending_review",
          human_review_required: true,
          source_kind: "model_provider_docs",
          license_note: "Provider metadata requires review.",
        },
      ],
      count: 1,
      review_gate: "metadata_only_until_human_review",
      human_review_required: true,
      checked_date_policy: "Provider metadata remains review-gated.",
    });
    bosKernelsApiMock.listExternalKnowledgeCandidates.mockResolvedValue({
      candidates: [
        {
          candidate_uid: "lca_factor_candidate:electricity_kgco2e_per_kwh",
          candidate_type: "lca_factor_candidate",
          key: "electricity_kgco2e_per_kwh",
          source_kind: "public_dataset",
          source_ref: "candidate:IEA-grid-emissions-factor",
          license_note: "Review required.",
          ingestion_mode: "metadata_only",
          review_status: "pending_review",
          human_review_required: true,
          approved_for_kernel_use: false,
          checked_date: "2026-04-26",
          payload: {},
        },
      ],
      count: 1,
      review_gate: "explicit_human_review_required_before_manual_promotion",
      human_review_required: true,
      promotion_policy: {
        request_only: true,
        auto_promote: false,
        validated_defaults_mutated: false,
        manual_default_patch_required_after_approval: true,
      },
    });
    bosKernelsApiMock.requestExternalKnowledgePromotion.mockResolvedValue({
      approval_request_id: "HAR-EK-RC",
      status: "pending",
      subject_type: "external_knowledge_candidate",
      subject_id: "lca_factor_candidate:electricity_kgco2e_per_kwh",
      candidate_type: "lca_factor_candidate",
      candidate_key: "electricity_kgco2e_per_kwh",
      candidate_uid: "lca_factor_candidate:electricity_kgco2e_per_kwh",
      reason: "Request explicit human review before any manual validated-default patch.",
      evidence_pack_id: "EVP-EK-RC",
      knowledge_relation_id: null,
      review_gate: "explicit_human_review_required",
      human_review_required: true,
      promoted_to_validated_defaults: false,
      manual_default_patch_required: true,
      side_effects: {
        kernel_defaults_mutated: false,
        provider_defaults_mutated: false,
      },
      created_at: "2026-04-26T00:00:00Z",
      resolved_at: null,
    });
    bosKernelsApiMock.resolveExternalKnowledgePromotion.mockResolvedValue({
      approval_request_id: "HAR-EK-RC",
      status: "approved",
      subject_type: "external_knowledge_candidate",
      subject_id: "lca_factor_candidate:electricity_kgco2e_per_kwh",
      candidate_type: "lca_factor_candidate",
      candidate_key: "electricity_kgco2e_per_kwh",
      candidate_uid: "lca_factor_candidate:electricity_kgco2e_per_kwh",
      reason: "Approved for manual registry patch only.",
      evidence_pack_id: "EVP-EK-RC",
      knowledge_relation_id: "KREL-EK-RC",
      review_gate: "explicit_human_review_required",
      human_review_required: false,
      promoted_to_validated_defaults: false,
      manual_default_patch_required: true,
      side_effects: {
        kernel_defaults_mutated: false,
        provider_defaults_mutated: false,
      },
      created_at: "2026-04-26T00:00:00Z",
      resolved_at: "2026-04-26T00:01:00Z",
    });
    bosKernelsApiMock.applyExternalKnowledgeRegistryPatch.mockResolvedValue({
      registry_patch_id: "KREL-REG-RC",
      status: "applied_to_validated_external_registry",
      candidate_uid: "lca_factor_candidate:electricity_kgco2e_per_kwh",
      registry_key: "lca_factor_candidate:electricity_kgco2e_per_kwh:external-knowledge-registry-20260426",
      registry_version: "external-knowledge-registry-20260426",
      approval_request_id: "HAR-EK-RC",
      evidence_pack_id: "EVP-REG-RC",
      validated_external_registry_updated: true,
      runtime_defaults_mutated: false,
      side_effects: {
        runtime_defaults_mutated: false,
        kernel_defaults_mutated: false,
      },
      created_at: "2026-04-26T00:02:00Z",
    });
    bosKernelsApiMock.listExternalKnowledgeValidatedRegistry.mockResolvedValue({
      registry: [],
      count: 0,
      registry_type: "validated_external_knowledge_registry",
      runtime_defaults_mutated: false,
      requires_separate_runtime_activation: true,
    });
    bosKernelsApiMock.getExternalKnowledgeRuntimeActivationReadiness.mockResolvedValue({
      schema_version: "external_knowledge_runtime_activation_readiness_v1",
      tenant_id: 1,
      activation_ready: false,
      executable: false,
      target_found: true,
      registry_patch_id: "KREL-REG-RC",
      activation_scope: {
        scope_key: "tenant:1:lca_factor_candidate:electricity_kgco2e_per_kwh",
      },
      current_active_state: {},
      blockers: ["approved_activation_draft_required"],
      required_roles: ["external_runtime_activation_approver"],
      side_effects_if_executed: {
        runtime_defaults_mutated: false,
        model_activation: false,
        external_share: false,
      },
      guardrails: ["readiness_only"],
    });
    bosKernelsApiMock.listExternalKnowledgeRuntimeActivationState.mockResolvedValue({
      schema_version: "external_knowledge_runtime_activation_state_v1",
      tenant_id: 1,
      runtime_defaults_mutated: false,
      active_scopes: [],
      activation_event_count: 0,
      guardrails: ["fallback_defaults_when_no_active_version"],
    });
    bosKernelsApiMock.createExternalKnowledgeRuntimeActivationDraft.mockResolvedValue({
      activation_request_id: "EKRA-RC",
      status: "pending",
      registry_patch_id: "KREL-REG-RC",
      candidate_type: "lca_factor_candidate",
      candidate_key: "electricity_kgco2e_per_kwh",
      registry_version: "external-knowledge-registry-20260426",
      activation_scope: {
        scope_key: "tenant:1:lca_factor_candidate:electricity_kgco2e_per_kwh",
      },
      previous_active_registry_patch_id: null,
      previous_active_registry_version: null,
      rollback_target_registry_patch_id: null,
      rollback_target_activation_id: null,
      operator_attestation: "reviewed",
      review_evidence_ids: ["EVP-REG-RC"],
      evidence_pack_id: "EVP-ACT-RC",
      review_gate: "explicit_human_review_required_before_runtime_activation",
      human_review_required: true,
      runtime_activation_executed: false,
      side_effects: { runtime_defaults_mutated: false },
      created_at: "2026-04-26T00:03:00Z",
      resolved_at: null,
    });
    bosKernelsApiMock.resolveExternalKnowledgeRuntimeActivationDraft.mockResolvedValue({
      activation_request_id: "EKRA-RC",
      status: "approved",
      registry_patch_id: "KREL-REG-RC",
      candidate_type: "lca_factor_candidate",
      candidate_key: "electricity_kgco2e_per_kwh",
      registry_version: "external-knowledge-registry-20260426",
      activation_scope: {
        scope_key: "tenant:1:lca_factor_candidate:electricity_kgco2e_per_kwh",
      },
      previous_active_registry_patch_id: null,
      previous_active_registry_version: null,
      rollback_target_registry_patch_id: null,
      rollback_target_activation_id: null,
      operator_attestation: "reviewed",
      review_evidence_ids: ["EVP-REG-RC"],
      evidence_pack_id: "EVP-ACT-RC",
      review_gate: "explicit_human_review_required_before_runtime_activation",
      human_review_required: false,
      runtime_activation_executed: false,
      side_effects: { runtime_defaults_mutated: false },
      created_at: "2026-04-26T00:03:00Z",
      resolved_at: "2026-04-26T00:04:00Z",
    });
    bosKernelsApiMock.getExternalKnowledgeRuntimeActivationExecutionReadiness.mockResolvedValue({
      activation_request_id: "EKRA-RC",
      registry_patch_id: "KREL-REG-RC",
      status: "approved",
      activation_ready: true,
      executable_now: true,
      blockers: [],
      target_found: true,
      activation_scope: {
        scope_key: "tenant:1:lca_factor_candidate:electricity_kgco2e_per_kwh",
      },
      previous_active_registry_patch_id: null,
      previous_active_registry_version: null,
      rollback_target_registry_patch_id: null,
      rollback_target_activation_id: null,
      source_evidence_pack_ids: ["EVP-REG-RC", "EVP-ACT-RC"],
      required_roles: ["external_runtime_activation_approver"],
      would_write_activation_record_now: true,
      side_effects_if_executed: {
        scoped_runtime_read_path_changed: true,
        runtime_defaults_mutated: false,
      },
      guardrails: ["approved_activation_draft_required"],
    });
    bosKernelsApiMock.executeExternalKnowledgeRuntimeActivation.mockResolvedValue({
      activation_id: "EKRACT-RC",
      registry_patch_id: "KREL-REG-RC",
      predicate: "runtime_activation_executed",
      activation_scope: {
        scope_key: "tenant:1:lca_factor_candidate:electricity_kgco2e_per_kwh",
      },
      registry_version: "external-knowledge-registry-20260426",
      previous_active_registry_patch_id: null,
      previous_active_registry_version: null,
      rollback_target_registry_patch_id: null,
      rollback_target_activation_id: null,
      idempotency_key: "runtime-activation-execute-EKRA-RC",
      status: "active",
      side_effects: {
        scoped_runtime_read_path_changed: true,
        runtime_defaults_mutated: false,
      },
      evidence_pack_id: "EVP-ACT-RC",
      created_at: "2026-04-26T00:05:00Z",
    });
    bosKernelsApiMock.rollbackExternalKnowledgeRuntimeActivation.mockResolvedValue({
      activation_id: "EKRROLL-RC",
      registry_patch_id: "EKRACT-RC",
      predicate: "runtime_activation_rolled_back",
      activation_scope: {
        scope_key: "tenant:1:lca_factor_candidate:electricity_kgco2e_per_kwh",
      },
      registry_version: "external-knowledge-registry-20260426",
      previous_active_registry_patch_id: null,
      previous_active_registry_version: null,
      rollback_target_registry_patch_id: null,
      rollback_target_activation_id: null,
      idempotency_key: "runtime-activation-rollback-EKRACT-RC",
      status: "rolled_back",
      side_effects: {
        rollback_event_written: true,
        runtime_defaults_mutated: false,
      },
      evidence_pack_id: "EVP-ACT-RC",
      created_at: "2026-04-26T00:06:00Z",
    });
    bosKernelsApiMock.registerModelCandidate.mockResolvedValue({
      model_id: "MOD-RC",
      model_version_id: "MVN-RC",
      status: "candidate",
      version_status: "candidate",
      metadata_payload: { evidence_pack_id: "EVP-BMR" },
    });
    bosKernelsApiMock.requestModelGovernanceReview.mockResolvedValue({
      model_id: "MOD-RC",
      model_version_id: "MVN-RC",
      model_status: "review_required",
      version_status: "ready_for_review",
      knowledge_relation_id: "KREL-RC",
      evidence_pack_id: "EVP-BMR",
      approval_request_id: "HAR-MODEL",
    });
    bosKernelsApiMock.listKnowledgeRelations.mockResolvedValue([]);
    useBrainRuntimeMock.mockReturnValue({
      data: {
        documents: [
          {
            key: "project_brain",
            title: "Project Brain",
            relative_path: ".agents/runtime/project-brain.md",
            content: "# Project Brain\n\n## Current Focus\n- Tighten release loop\n",
            updated_at: null,
            line_count: 3,
            is_missing: false,
          },
          {
            key: "decision_journal",
            title: "Decision Journal",
            relative_path: ".agents/runtime/decision-journal.md",
            content: "# Decision Journal\n\n## Recent Decisions\n- Prioritize release confidence\n",
            updated_at: null,
            line_count: 3,
            is_missing: false,
          },
          {
            key: "evolution_log",
            title: "Evolution Log",
            relative_path: ".agents/runtime/evolution-log.md",
            content: "# Evolution Log\n\n## Active Heuristics\n- Verify before widening scope\n",
            updated_at: null,
            line_count: 3,
            is_missing: false,
          },
          {
            key: "run_ledger",
            title: "Autonomy Run Ledger",
            relative_path: ".agents/runtime/run-ledger.md",
            content: "# Autonomy Run Ledger\n\n## Latest Run\n- Slice: Batch 101 signal review\n- Outcome: Verified\n- Verification: type-check and vitest\n- Remaining Risk: release mapping still pending\n- Next Step: connect audit packet 900 to release center\n",
            updated_at: null,
            line_count: 8,
            is_missing: false,
          },
        ],
      },
    });
    useCodeReleaseReadinessMock.mockReturnValue({
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
      data: {
        generated_at: "2026-04-16T00:00:00Z",
        release_state: "review_required",
        backend_version: "9.0.0",
        frontend_version: "9.0.0",
        git_branch: "main",
        git_commit: "abc123",
        preflight_pass_count: 10,
        preflight_warn_count: 1,
        preflight_fail_count: 0,
        known_warnings: ["port 5173 occupied"],
        known_limitations: ["Live smoke artifacts should be regenerated."],
        recommended_next_action: "Regenerate live smoke artifacts before demo.",
        checks: [
          { name: "backend tests", status: "PASS", summary: "369 passed" },
          { name: "frontend build", status: "PASS", summary: "vite build completed" },
        ],
        report_markdown: "# Dossier",
        report_path: "reports/release-readiness-summary.md",
        code_smoke_path: null,
        bos_smoke_path: null,
        artifacts: [
          {
            key: "release_dossier",
            label: "Release dossier",
            relative_path: "reports/release-readiness-summary.md",
            download_url: "/api/v1/code/release-artifacts/release_dossier",
            content_type: "text/markdown",
          },
          {
            key: "bos_v9_rc_manifest",
            label: "BOS v9 RC manifest",
            relative_path: "reports/stabilize-v9/BOS_V9_RC_MANIFEST.json",
            download_url: "/api/v1/code/release-artifacts/bos_v9_rc_manifest",
            content_type: "application/json",
          },
        ],
      },
    });
    useRecentTimeseriesRisksMock.mockReturnValue({
      isLoading: false,
      data: {
        items: [],
      },
    });
  });

  it("renders the release center shell, checks, and limitations", () => {
    const html = renderToStaticMarkup(<ReleaseCenterPage />);

    expect(html).toContain("BOS Code release center");
    expect(html).toContain("review_required");
    expect(html).toContain("Verification-first");
    expect(html).toContain("Release dossier preview");
    expect(html).toContain("Simulation appendix");
    expect(html).toContain("Checking appendix");
    expect(html).toContain("Release decision ID");
    expect(html).toContain("Attached appendices");
    expect(html).toContain("No appendices are attached");
    expect(html).toContain("without changing release decisions");
    expect(html).toContain("Governance kernel");
    expect(html).toContain("Review-gated");
    expect(html).toContain("Run benchmark suite");
    expect(html).toContain("Request model review");
    expect(html).toContain("No promotion pending");
    expect(html).toContain("Known limitations");
    expect(html).toContain("Live smoke artifacts should be regenerated.");
    expect(html).toContain("Release checks");
    expect(html).toContain("backend tests");
    expect(html).toContain("Quick interpretation");
    expect(html).toContain("Release readiness card: review_required");
    expect(html).toContain("Brain operator context card");
  });

  it("renders RC manifest candidate evidence separately from release state", async () => {
    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    expect(governanceApiMock.getRCManifest).toHaveBeenCalledTimes(1);
    const panel = container.querySelector('[data-testid="rc-manifest-state-panel"]');
    expect(panel?.textContent).toContain("candidate_evidence_state: ready_for_review");
    expect(panel?.textContent).toContain("release_state: review_required");
    expect(panel?.textContent).toContain("preflight: 21 pass / 0 warn / 0 fail");
    expect(panel?.textContent).toContain("final_action_execute_call_count: 0");
    expect(panel?.textContent).toContain("Six 9/10 target scorecard");
    expect(panel?.textContent).toContain("reproducible_p0_baseline");
    expect(panel?.textContent).toContain("Review packet entry");
    expect(panel?.textContent).toContain("reports/stabilize-v9/BOS_V9_RC_MANIFEST.json");
    expect(panel?.textContent).toContain("Immutable source review packet");
    expect(panel?.textContent).toContain("source_review_packet_id: FARP-RC");
    expect(panel?.textContent).toContain("packet_hash: abcdef1234567890");
    expect(panel?.textContent).toContain("read_only_source_review_packet");
    expect(panel?.textContent).toContain("final_actions_not_executed");
    expect(panel?.textContent).toContain("release_state remains review_required");
    expect(panel?.querySelector('a[href="/api/v1/code/release-artifacts/bos_v9_rc_manifest"]')).not.toBeNull();
    expect(panel?.querySelector('a[href="/api/v1/final-actions/source-review-packets/FARP-RC"]')).not.toBeNull();
    expect(panel?.textContent).not.toContain("release_state: ready_for_review");
    expect(panel?.textContent?.toLowerCase()).not.toContain("approved");
    act(() => root.unmount());
  });

  it("renders reviewed metadata candidates as read-only release review context", async () => {
    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    expect(bosApiMock.listReviewedExternalCandidates).toHaveBeenCalledTimes(1);
    expect(bosApiMock.getReviewedExternalCandidateSummary).toHaveBeenCalledTimes(1);
    expect(bosApiMock.getReviewedExternalCandidateActivationPreview).toHaveBeenCalledWith("REC-BSF-CARD-001");
    expect(bosApiMock.getReviewedExternalCandidateRuntimeReadiness).toHaveBeenCalledWith("REC-BSF-CARD-001");
    expect(bosApiMock.getReviewedExternalCandidateRollbackPreview).toHaveBeenCalledWith("REC-BSF-CARD-001");
    expect(container.textContent).toContain("Reviewed metadata lane");
    expect(container.textContent).toContain("REC-BSF-CARD-001");
    expect(container.textContent).toContain("BSF substrate conversion review");
    expect(container.textContent).toContain("pending_runtime_activation: 1");
    expect(container.textContent).toContain("runtime_activated: false");
    expect(container.textContent).toContain("numeric_values_included: false");
    expect(container.textContent).toContain("numeric_value_candidates: 0");
    expect(container.textContent).toContain("no validated defaults; no release evidence; no runtime activation");
    expect(container.textContent).toContain("summary_is_read_only");
    expect(container.textContent).toContain("approved_for_candidate_use_is_not_runtime_activation");
    expect(container.textContent).toContain("metadata_candidates_excluded_from_final_action_evidence");
    expect(container.textContent).toContain("Operator evidence summary");
    expect(container.textContent).toContain("operator evidence ready / execution blocked");
    expect(container.textContent).toContain("release_decision: review_required");
    expect(container.textContent).toContain("release_evidence_allowed: false");
    expect(container.textContent).toContain("Runtime read path enabled only");
    expect(container.textContent).toContain("Rollback execution blocked");
    expect(container.textContent).not.toContain("Activate reviewed metadata");
    act(() => root.unmount());
  });

  it("renders literature promotion audit exports without exposing release execution", async () => {
    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    expect(bosApiMock.listLiteratureExtractionCandidates).toHaveBeenCalledTimes(1);
    expect(bosApiMock.getLiteratureValuePromotionAuditExport).toHaveBeenCalledWith("LIT-CAND-001");
    expect(container.textContent).toContain("Literature promotion audit export");
    expect(container.textContent).toContain("response_only_no_file_write");
    expect(container.textContent).toContain("72 g/kg");
    expect(container.textContent).toContain("10.1016/j.wasman.2020.01.001");
    expect(container.textContent).toContain("approval: LVPA-SCI-001, LVPA-RM-001");
    expect(container.textContent).toContain("release_decision: review_required");
    expect(container.textContent).toContain("species_db_write: false");
    expect(container.textContent).toContain("feedstock_db_write: false");
    expect(container.textContent).toContain("validated_default_write: false");
    expect(container.textContent).toContain("final_action_execution: false");
    expect(container.textContent).toContain("file_written: false");
    expect(container.textContent).toContain("side_effects: false");
    expect(container.textContent).not.toContain("Execute literature promotion");
    act(() => root.unmount());
  });

  it("links an active scoped literature activation as review-only release evidence", async () => {
    bosApiMock.getLiteratureValuePromotionAuditExport.mockResolvedValueOnce({
      ...literaturePromotionAuditExportFixture,
      release_evidence_link: null,
      export_manifest: {
        ...literaturePromotionAuditExportFixture.export_manifest,
        release_evidence_link_count: 0,
      },
    });

    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    expect(container.textContent).toContain("active_activation_id: LVA-001");
    expect(container.textContent).toContain("release_decision_before: review_required");
    expect(container.textContent).toContain("final_action_execution: false");

    await act(async () => {
      buttonByText(container, "Link active scoped value as release evidence").click();
    });
    await flushAsyncWork();

    expect(bosApiMock.createLiteratureValueReleaseEvidenceLink).toHaveBeenCalledWith(1, {
      activation_id: "LVA-001",
      link_notes: "Link active scoped literature overlay as release evidence only; release decision remains review_required.",
      idempotency_key: expect.stringContaining("release-center-literature-release-evidence-link-"),
    });
    expect(container.textContent).toContain("link_id: LVREL-NEW");
    act(() => root.unmount());
  });

  it("keeps release reviewed metadata evidence pending when preview reads fail", async () => {
    bosApiMock.getReviewedExternalCandidateRuntimeReadiness.mockRejectedValueOnce(new Error("runtime preview unavailable"));

    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    expect(container.textContent).toContain("Reviewed metadata lane");
    expect(container.textContent).toContain("Operator evidence summary");
    expect(container.textContent).toContain("operator evidence pending");
    expect(container.textContent).toContain("runtime_read_path: pending");
    expect(container.textContent).toContain("release_decision: review_required");
    expect(container.textContent).not.toContain("operator evidence ready / execution blocked");
    expect(container.textContent).not.toContain("Activate reviewed metadata");
    act(() => root.unmount());
  });

  it("excludes feedstock public dataset candidates from the release reviewed metadata lane", async () => {
    bosApiMock.listReviewedExternalCandidates.mockResolvedValueOnce({
      ...reviewedMetadataLaneFixture,
      items: [
        reviewedMetadataLaneFixture.items[0],
        {
          tenant_id: 1,
          candidate_id: "FDS-B-FEED-001",
          candidate_type: "feedstock_dataset_candidate",
          candidate_key: "feedstock_dataset_candidate:B-FEED-001",
          card_id: "B-FEED-001",
          source_id: "B-FEED-001",
          source_kind: "public_dataset",
          source_ref: "https://fdc.nal.usda.gov/",
          title: "USDA FoodData Central",
          review_status: "pending_review",
          reviewer_user_id: null,
          reviewer: "unassigned",
          reviewed_at: null,
          license_status: "metadata_only",
          boundary_condition: "Food/feed dataset staged as proxy metadata only.",
          allowed_use: "Reference Atlas review queue only",
          blocked_use: "no validated defaults; no release evidence; no runtime activation",
          candidate_payload: {
            candidate_family: "feedstock_dataset_candidate",
            numeric_values_included: false,
          },
          human_review_required: true,
          promotion_enabled: false,
          runtime_activated: false,
          validated_default_write_enabled: false,
          activation_relation_id: null,
          audit_payload: {},
          created_at: "2026-04-26T00:00:00Z",
          updated_at: "2026-04-26T00:00:00Z",
        },
      ],
      count: 2,
    });

    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    expect(container.textContent).toContain("Reviewed metadata lane");
    expect(container.textContent).toContain("REC-BSF-CARD-001");
    expect(container.textContent).not.toContain("FDS-B-FEED-001");
    expect(container.textContent).not.toContain("USDA FoodData Central");
    expect(container.textContent).toContain("no validated defaults; no release evidence; no runtime activation");
    act(() => root.unmount());
  });

  it("attaches the latest simulation appendix and requests human approval", async () => {
    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    await act(async () => {
      buttonByText(container, "Attach appendix").click();
    });
    await flushAsyncWork();

    expect(releasePacketApiMock.attachSimulationAppendix).toHaveBeenCalledWith(1, {
      simulation_id: "SIM-RC",
      run_id: "RUN-RC",
    });
    expect(container.textContent).toContain("RPA-RC");

    await act(async () => {
      buttonByText(container, "Request human approval").click();
    });
    await flushAsyncWork();

    expect(releasePacketApiMock.createApprovalRequest).toHaveBeenCalledWith(1, {
      subject_type: "release_decision",
      subject_id: "1",
      reason: "Review simulation appendix evidence before release decision",
      payload: {
        simulation_id: "SIM-RC",
        evidence_pack_id: "EVP-RC",
        input_snapshot_id: "INP-RC",
      },
    });
    expect(container.textContent).toContain("HAR-RC");
    act(() => root.unmount());
  });

  it("creates benchmark evidence and requests model governance review", async () => {
    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    await act(async () => {
      buttonByText(container, "Run benchmark suite").click();
    });
    await flushAsyncWork();

    expect(bosKernelsApiMock.createBenchmarkRun).toHaveBeenCalled();
    expect(bosKernelsApiMock.listBenchmarkRuns).toHaveBeenCalled();
    expect(container.textContent).toContain("BMR-RC");
    expect(container.textContent).toContain("1/1 passed");
    expect(container.textContent).toContain("moisture_drift");
    expect(container.textContent).toContain("EVP-BMR-CASE");

    bosKernelsApiMock.listModels.mockResolvedValue([
      {
        model_id: "MOD-RC",
        name: "chronos-risk-candidate",
        task_type: "risk_forecast",
        status: "review_required",
      },
    ]);
    bosKernelsApiMock.listKnowledgeRelations.mockResolvedValue([
      {
        relation_id: "KREL-RC",
        subject_type: "model_version",
        subject_id: "MVN-RC",
        predicate: "evaluated_by",
        object_type: "benchmark_run",
        object_id: "BMR-RC",
        evidence_pack_id: "EVP-BMR",
        payload: {},
        created_at: "2026-04-24T00:00:00Z",
      },
    ]);

    await act(async () => {
      buttonByText(container, "Request model review").click();
    });
    await flushAsyncWork();

    expect(bosKernelsApiMock.registerModelCandidate).toHaveBeenCalledWith("BMR-RC");
    expect(bosKernelsApiMock.requestModelGovernanceReview).toHaveBeenCalledWith("MOD-RC", "MVN-RC", "BMR-RC");
    expect(container.textContent).toContain("MOD-RC");
    expect(container.textContent).toContain("KREL-RC");
    expect(container.textContent).toContain("HAR-MODEL");
    expect(container.textContent).toContain("model_version -> benchmark_run -> evidence_pack");
    expect(container.textContent).toContain("ready_for_review");
    act(() => root.unmount());
  });

  it("requests external knowledge promotion review and applies manual registry patch without runtime default mutation", async () => {
    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    expect(container.textContent).toContain("External knowledge promotion workflow");
    expect(container.textContent).toContain("electricity_kgco2e_per_kwh");
    expect(container.textContent).toContain("pending_review");

    await act(async () => {
      buttonByText(container, "Request promotion review").click();
    });
    await flushAsyncWork();

    expect(bosKernelsApiMock.requestExternalKnowledgePromotion).toHaveBeenCalledWith(
      "lca_factor_candidate",
      "electricity_kgco2e_per_kwh",
    );
    expect(container.textContent).toContain("HAR-EK-RC");
    expect(container.textContent).toContain("validated defaults unchanged");

    await act(async () => {
      buttonByText(container, "Approve promotion review").click();
    });
    await flushAsyncWork();

    expect(bosKernelsApiMock.resolveExternalKnowledgePromotion).toHaveBeenCalledWith("HAR-EK-RC", true);
    expect(container.textContent).toContain("approved");

    bosKernelsApiMock.listExternalKnowledgeValidatedRegistry.mockResolvedValue({
      registry: [
        {
          registry_patch_id: "KREL-REG-RC",
          status: "applied_to_validated_external_registry",
          candidate_uid: "lca_factor_candidate:electricity_kgco2e_per_kwh",
          registry_key: "lca_factor_candidate:electricity_kgco2e_per_kwh:external-knowledge-registry-20260426",
          registry_version: "external-knowledge-registry-20260426",
          approval_request_id: "HAR-EK-RC",
          evidence_pack_id: "EVP-REG-RC",
          validated_external_registry_updated: true,
          runtime_defaults_mutated: false,
          side_effects: { runtime_defaults_mutated: false },
          created_at: "2026-04-26T00:02:00Z",
        },
      ],
      count: 1,
      registry_type: "validated_external_knowledge_registry",
      runtime_defaults_mutated: false,
      requires_separate_runtime_activation: true,
    });

    await act(async () => {
      buttonByText(container, "Apply manual registry patch").click();
    });
    await flushAsyncWork();

    expect(bosKernelsApiMock.applyExternalKnowledgeRegistryPatch).toHaveBeenCalledWith("HAR-EK-RC");
    expect(container.textContent).toContain("KREL-REG-RC");
    expect(container.textContent).toContain("runtime defaults unchanged");
    expect(container.textContent).toContain("Validated external registry");

    await act(async () => {
      buttonByText(container, "Create activation draft").click();
    });
    await flushAsyncWork();

    expect(bosKernelsApiMock.createExternalKnowledgeRuntimeActivationDraft).toHaveBeenCalledWith("KREL-REG-RC");
    expect(container.textContent).toContain("EKRA-RC");
    expect(container.textContent).toContain("pending");

    await act(async () => {
      buttonByText(container, "Approve activation draft").click();
    });
    await flushAsyncWork();

    expect(bosKernelsApiMock.resolveExternalKnowledgeRuntimeActivationDraft).toHaveBeenCalledWith("EKRA-RC", true);
    expect(container.textContent).toContain("approved");

    await act(async () => {
      buttonByText(container, "Check activation readiness").click();
    });
    await flushAsyncWork();

    expect(bosKernelsApiMock.getExternalKnowledgeRuntimeActivationExecutionReadiness).toHaveBeenCalledWith("EKRA-RC");
    expect(container.textContent).toContain("activation_ready");

    await act(async () => {
      buttonByText(container, "Execute scoped activation").click();
    });
    await flushAsyncWork();

    expect(bosKernelsApiMock.executeExternalKnowledgeRuntimeActivation).toHaveBeenCalledWith("EKRA-RC", null);
    expect(container.textContent).toContain("EKRACT-RC");
    expect(container.textContent).toContain("runtime_activation_executed");

    await act(async () => {
      buttonByText(container, "Rollback activation").click();
    });
    await flushAsyncWork();

    expect(bosKernelsApiMock.rollbackExternalKnowledgeRuntimeActivation).toHaveBeenCalledWith("EKRACT-RC");
    expect(container.textContent).toContain("runtime_activation_rolled_back");
    act(() => root.unmount());
  });

  it("renders latest benchmark case details and keeps failed cases review-blocked", async () => {
    bosKernelsApiMock.listBenchmarkRuns.mockResolvedValue([
      {
        benchmark_run_id: "BMR-FAILED",
        suite_name: "simulation_lab_regression",
        scorecard: {
          status: "blocked",
          suite_gate: "human_review_required",
          case_count: 1,
          passed_count: 0,
          failed_count: 1,
          cases: [
            {
              case_id: "CASE-moisture_drift",
              name: "moisture_drift",
              status: "failed",
              simulation_id: "SIM-FAILED",
              run_id: "RUN-FAILED",
              evidence_pack_id: "EVP-FAILED-CASE",
              metrics: {
                ending_risk: 0.42,
                audit_event_count: 8,
                cycle_count: 8,
              },
              assertions: [{ metric: "ending_risk", passed: false }],
              expected_metrics: { max_ending_risk: 0.01 },
            },
          ],
        },
        evidence_pack_id: "EVP-FAILED",
        created_at: "2026-04-24T00:00:00Z",
      },
    ]);

    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    expect(container.textContent).toContain("BMR-FAILED");
    expect(container.textContent).toContain("0/1 passed / 1 failed");
    expect(container.textContent).toContain("Blocked / review required");
    expect(container.textContent).toContain("moisture_drift");
    expect(container.textContent).toContain("CASE-moisture_drift");
    expect(container.textContent).toContain("EVP-FAILED-CASE");
    expect(container.textContent).not.toContain("Approved");
    act(() => root.unmount());
  });

  it("builds assistant proof cards from compliance, LCA, and TEA summary evidence", () => {
    const cards = buildReleaseProofCardsFromAssistantRun(makeAssistantRunWithReleaseProofs());

    expect(cards.map((card) => card.title)).toEqual([
      "Compliance gate",
      "LCA value proof",
      "TEA value proof",
      "Uncertainty warnings",
    ]);
    expect(cards[0].status).toBe("blocked");
    expect(cards[0].evidencePackId).toBe("EVP-COMPLIANCE");
    expect(cards[1].lines).toContain("CO2e abatement: 431.60 kg");
    expect(cards[2].lines).toContain("Gross margin: $105.40");
    expect(cards[3].status).toBe("human_review_required");
  });

  it("renders assistant compliance and value proof cards as review-only release evidence", async () => {
    assistantApiMock.listRuns.mockResolvedValue([makeAssistantRunWithReleaseProofs()]);

    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    expect(assistantApiMock.listRuns).toHaveBeenCalledWith(5);
    expect(container.textContent).toContain("Assistant proof appendix");
    expect(container.textContent).toContain("Compliance gate");
    expect(container.textContent).toContain("blocked");
    expect(container.textContent).toContain("Missing assays: moisture, protein");
    expect(container.textContent).toContain("LCA value proof");
    expect(container.textContent).toContain("CO2e abatement: 431.60 kg");
    expect(container.textContent).toContain("TEA value proof");
    expect(container.textContent).toContain("Gross margin: $105.40");
    expect(container.textContent).toContain("Uncertainty warnings");
    expect(container.textContent).toContain("EVP-COMPLIANCE");
    expect(container.textContent).toContain("EVP-LCA");
    expect(container.textContent).toContain("EVP-TEA");
    expect(container.textContent).toContain("Release decision remains unchanged");
    expect(container.textContent).not.toContain("Approved");
    act(() => root.unmount());
  });

  it("renders the review workbench and resolves Assistant confirmations as queue-only actions", async () => {
    assistantApiMock.getReviewWorkbench
      .mockResolvedValueOnce({
        assistant_confirmations: [
          {
            confirmation_id: "ACONF-RC-RELEASE",
            action_name: "release.request_human_approval",
            action_payload: { execution: "queue_only_no_auto_approval" },
            status: "pending",
            reason: null,
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-ASSISTANT", "EVP-COMPLIANCE"],
            risk_guardrails: [
              "queue_only_no_auto_approval",
              "release_decision_remains_review_required",
              "separate_human_release_workflow_required",
            ],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
          {
            confirmation_id: "ACONF-RC-SHARE",
            action_name: "external.share_release_packet",
            action_payload: { execution: "forbidden_until_explicit_external_share_workflow" },
            status: "pending",
            reason: null,
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-ASSISTANT"],
            risk_guardrails: ["queue_only_no_external_sharing", "tenant_boundary_required"],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
          {
            confirmation_id: "ACONF-RC-MODEL",
            action_name: "model.complete_review",
            action_payload: { approval_request_id: "HAR-MODEL", execution: "queue_only_no_model_activation" },
            status: "pending",
            reason: null,
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-ASSISTANT", "EVP-BMR"],
            risk_guardrails: ["queue_only_no_model_activation", "human_approval_request_remains_pending"],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
        ],
        human_approval_requests: [
          {
            approval_request_id: "HAR-MODEL",
            release_decision_id: null,
            subject_type: "model_version",
            subject_id: "MV-RC",
            status: "pending",
            reason: "Assistant requested model governance review from benchmark evidence.",
            payload: { benchmark_run_id: "BMR-RC", evidence_pack_id: "EVP-BMR" },
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-BMR"],
            risk_guardrails: [
              "pending_review_request_only",
              "no_auto_release_approval",
              "no_auto_model_activation",
              "no_external_sharing",
            ],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
        ],
        guardrails: [
          "tenant_scoped_read_model",
          "queue_only_confirmation_management",
          "release_decision_remains_review_required",
          "no_auto_model_activation",
          "no_external_sharing",
        ],
      })
      .mockResolvedValueOnce({
        assistant_confirmations: [
          {
            confirmation_id: "ACONF-RC-SHARE",
            action_name: "external.share_release_packet",
            action_payload: { execution: "forbidden_until_explicit_external_share_workflow" },
            status: "pending",
            reason: null,
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-ASSISTANT"],
            risk_guardrails: ["queue_only_no_external_sharing", "tenant_boundary_required"],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
        ],
        human_approval_requests: [
          {
            approval_request_id: "HAR-MODEL",
            release_decision_id: null,
            subject_type: "model_version",
            subject_id: "MV-RC",
            status: "pending",
            reason: "Assistant requested model governance review from benchmark evidence.",
            payload: { benchmark_run_id: "BMR-RC", evidence_pack_id: "EVP-BMR" },
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-BMR"],
            risk_guardrails: ["pending_review_request_only", "no_auto_model_activation"],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
        ],
        guardrails: ["queue_only_confirmation_management", "no_external_sharing"],
      })
      .mockResolvedValueOnce({
        assistant_confirmations: [
          {
            confirmation_id: "ACONF-RC-SHARE",
            action_name: "external.share_release_packet",
            action_payload: { execution: "forbidden_until_explicit_external_share_workflow" },
            status: "pending",
            reason: null,
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-ASSISTANT"],
            risk_guardrails: ["queue_only_no_external_sharing", "tenant_boundary_required"],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
        ],
        human_approval_requests: [],
        guardrails: ["queue_only_confirmation_management", "no_external_sharing"],
      });

    const pendingStates = [
      {
        assistant_confirmations: [
          {
            confirmation_id: "ACONF-RC-RELEASE",
            action_name: "release.request_human_approval",
            action_payload: { execution: "queue_only_no_auto_approval" },
            status: "pending",
            reason: null,
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-ASSISTANT", "EVP-COMPLIANCE"],
            risk_guardrails: [
              "queue_only_no_auto_approval",
              "release_decision_remains_review_required",
              "separate_human_release_workflow_required",
            ],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
          {
            confirmation_id: "ACONF-RC-SHARE",
            action_name: "external.share_release_packet",
            action_payload: { execution: "forbidden_until_explicit_external_share_workflow" },
            status: "pending",
            reason: null,
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-ASSISTANT"],
            risk_guardrails: ["queue_only_no_external_sharing", "tenant_boundary_required"],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
          {
            confirmation_id: "ACONF-RC-MODEL",
            action_name: "model.complete_review",
            action_payload: { approval_request_id: "HAR-MODEL", execution: "queue_only_no_model_activation" },
            status: "pending",
            reason: null,
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-ASSISTANT", "EVP-BMR"],
            risk_guardrails: ["queue_only_no_model_activation", "human_approval_request_remains_pending"],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
        ],
        human_approval_requests: [
          {
            approval_request_id: "HAR-MODEL",
            release_decision_id: null,
            subject_type: "model_version",
            subject_id: "MV-RC",
            status: "pending",
            reason: "Assistant requested model governance review from benchmark evidence.",
            payload: { benchmark_run_id: "BMR-RC", evidence_pack_id: "EVP-BMR" },
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-BMR"],
            risk_guardrails: [
              "pending_review_request_only",
              "no_auto_release_approval",
              "no_auto_model_activation",
              "no_external_sharing",
            ],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
        ],
        guardrails: [
          "tenant_scoped_read_model",
          "queue_only_confirmation_management",
          "release_decision_remains_review_required",
          "no_auto_model_activation",
          "no_external_sharing",
        ],
      },
      {
        assistant_confirmations: [
          {
            confirmation_id: "ACONF-RC-SHARE",
            action_name: "external.share_release_packet",
            action_payload: { execution: "forbidden_until_explicit_external_share_workflow" },
            status: "pending",
            reason: null,
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-ASSISTANT"],
            risk_guardrails: ["queue_only_no_external_sharing", "tenant_boundary_required"],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
        ],
        human_approval_requests: [
          {
            approval_request_id: "HAR-MODEL",
            release_decision_id: null,
            subject_type: "model_version",
            subject_id: "MV-RC",
            status: "pending",
            reason: "Assistant requested model governance review from benchmark evidence.",
            payload: { benchmark_run_id: "BMR-RC", evidence_pack_id: "EVP-BMR" },
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-BMR"],
            risk_guardrails: ["pending_review_request_only", "no_auto_model_activation"],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
        ],
        guardrails: ["queue_only_confirmation_management", "no_external_sharing"],
      },
      {
        assistant_confirmations: [
          {
            confirmation_id: "ACONF-RC-SHARE",
            action_name: "external.share_release_packet",
            action_payload: { execution: "forbidden_until_explicit_external_share_workflow" },
            status: "pending",
            reason: null,
            source_assistant_run_id: "ARUN-RC-PROOFS",
            source_evidence_pack_id: "EVP-ASSISTANT",
            evidence_pack_ids: ["EVP-ASSISTANT"],
            risk_guardrails: ["queue_only_no_external_sharing", "tenant_boundary_required"],
            created_at: "2026-04-25T00:00:00Z",
            resolved_at: null,
          },
        ],
        human_approval_requests: [],
        guardrails: ["queue_only_confirmation_management", "no_external_sharing"],
      },
    ];
    let pendingLoadCount = 0;
    assistantApiMock.getReviewWorkbench.mockReset();
    assistantApiMock.getReviewWorkbench.mockImplementation((status = "pending") => {
      if (status === "pending") {
        const nextState = pendingStates[Math.min(pendingLoadCount, pendingStates.length - 1)];
        pendingLoadCount += 1;
        return Promise.resolve(nextState);
      }
      return Promise.resolve(emptyReviewWorkbench);
    });

    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    expect(assistantApiMock.getReviewWorkbench).toHaveBeenCalledWith("pending", 50);
    expect(container.textContent).toContain("Human review workbench");
    expect(container.textContent).toContain("Review-gated, queue-only operator surface");
    expect(container.textContent).toContain("release.request_human_approval");
    expect(container.textContent).toContain("external.share_release_packet");
    expect(container.textContent).toContain("model.complete_review");
    expect(container.textContent).toContain("HAR-MODEL");
    expect(container.textContent).toContain("queue_only_no_auto_approval");
    expect(container.textContent).toContain("no_auto_model_activation");
    expect(container.textContent).toContain("no_external_sharing");
    expect(container.textContent).not.toContain("Final approval");

    await act(async () => {
      buttonByText(container, "Mark reviewed").click();
    });
    await flushAsyncWork();
    await flushAsyncWork();

    expect(assistantApiMock.confirm).toHaveBeenCalledWith("ARUN-RC-PROOFS", {
      confirmation_id: "ACONF-RC-RELEASE",
      approved: true,
      reason: "Release Center workbench marked this queue item reviewed; no final release/model/share action executed.",
    });
    expect(container.textContent).toContain("external.share_release_packet");
    expect(container.textContent).toContain("HAR-MODEL");

    await act(async () => {
      buttonByText(container, "Resolve request only").click();
    });
    await flushAsyncWork();
    await flushAsyncWork();

    expect(assistantApiMock.resolveHumanApprovalRequest).toHaveBeenCalledWith("HAR-MODEL", {
      approved: true,
      reason: "Release Center workbench resolved this review request only; release/model/share state remains unchanged.",
    });
    expect(container.textContent).toContain("external.share_release_packet");
    expect(container.textContent).toContain("No pending HumanApprovalRequest records are visible for this tenant.");
    act(() => root.unmount());
  });

  it("renders resolved review history as read-only release evidence", async () => {
    assistantApiMock.getReviewWorkbench.mockImplementation((status = "pending") => {
      if (status === "approved") {
        return Promise.resolve({
          assistant_confirmations: [],
          human_approval_requests: [
            {
              approval_request_id: "HAR-APPROVED-HISTORY",
              release_decision_id: null,
              subject_type: "model_version",
              subject_id: "MV-RC",
              status: "approved",
              reason: "review request disposition only; no model activation",
              payload: {
                evidence_pack_id: "EVP-BMR",
                workbench_resolution: {
                  scope: "human_approval_request_only",
                  side_effects: {
                    release_decision: "unchanged",
                    model_activation: false,
                    external_share: false,
                  },
                },
              },
              source_assistant_run_id: "ARUN-RC-PROOFS",
              source_evidence_pack_id: "EVP-ASSISTANT",
              evidence_pack_ids: ["EVP-BMR"],
              risk_guardrails: ["resolved_review_request_only", "no_auto_model_activation"],
              created_at: "2026-04-25T00:00:00Z",
              resolved_at: "2026-04-25T00:02:00Z",
            },
          ],
          guardrails: ["tenant_scoped_read_model", "no_auto_model_activation"],
        });
      }
      if (status === "rejected") {
        return Promise.resolve({
          assistant_confirmations: [
            {
              confirmation_id: "ACONF-REJECTED-HISTORY",
              action_name: "model.complete_review",
              action_payload: { execution: "queue_only_no_model_activation" },
              status: "rejected",
              reason: "queue-only rejection for workbench test",
              source_assistant_run_id: "ARUN-RC-PROOFS",
              source_evidence_pack_id: "EVP-ASSISTANT",
              evidence_pack_ids: ["EVP-ASSISTANT", "EVP-BMR"],
              risk_guardrails: ["queue_only_no_model_activation", "separate_model_governance_workflow_required"],
              created_at: "2026-04-25T00:00:00Z",
              resolved_at: "2026-04-25T00:03:00Z",
            },
          ],
          human_approval_requests: [],
          guardrails: ["queue_only_confirmation_management"],
        });
      }
      return Promise.resolve(emptyReviewWorkbench);
    });

    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    expect(assistantApiMock.getReviewWorkbench).toHaveBeenCalledWith("pending", 50);
    expect(assistantApiMock.getReviewWorkbench).toHaveBeenCalledWith("approved", 25);
    expect(assistantApiMock.getReviewWorkbench).toHaveBeenCalledWith("rejected", 25);
    expect(finalActionsApiMock.getReadiness).toHaveBeenCalledWith(50);
    expect(finalActionsApiMock.getAuditRecords).toHaveBeenCalledWith(25);
    expect(finalActionsApiMock.getRequestDrafts).toHaveBeenCalledWith(25);
    expect(finalActionsApiMock.getSourceReviewPacket).toHaveBeenCalledWith("FARP-RC");
    expect(container.textContent).toContain("Resolved review history");
    expect(container.textContent).toContain("Pending queue");
    expect(container.textContent).toContain("Resolved approvals");
    expect(container.textContent).toContain("Resolved rejections");
    expect(container.textContent).toContain("Final actions");
    expect(container.textContent).toContain("not executed");
    expect(container.textContent).toContain("Latest resolved 2026-04-25T00:03:00Z");
    expect(container.textContent).toContain("Operator audit packet");
    expect(container.textContent).toContain("Read-only export of pending queue, resolved dispositions, evidence IDs, and side-effect guardrails.");
    expect(container.textContent).toContain("Persist source packet");
    expect(container.textContent).toContain("final_actions_not_executed");
    expect(container.textContent).toContain("Final actions readiness");
    expect(container.textContent).toContain("Audited workflow for request drafts");
    expect(container.textContent).toContain("Final release approval");
    expect(container.textContent).toContain("Model activation");
    expect(container.textContent).toContain("External release share");
    expect(container.textContent).toContain("audited final-action workflow");
    expect(container.textContent).toContain("Create request draft");
    expect(container.textContent).toContain("Final execution attestation");
    expect(container.textContent).toContain("executable: false");
    expect(container.textContent).toContain("draft_gate: ready_for_request_draft");
    expect(container.textContent).toContain("required_roles: final_release_approver");
    expect(container.textContent).toContain("required_evidence_ids: EVP-ASSISTANT, EVP-BMR");
    expect(container.textContent).toContain("missing_evidence_ids: redacted_release_packet_evidence");
    expect(container.textContent).toContain("release_decision: review_required");
    expect(container.textContent).toContain("model_version: ready_for_review");
    expect(container.textContent).toContain("external_share_record_created: false");
    expect(container.textContent).toContain("audit_schema_available: true");
    expect(container.textContent).toContain("request_draft_schema_available: true");
    expect(container.textContent).toContain("final_action_request_drafts_created: false");
    expect(container.textContent).toContain("final_action_request_drafts: 0");
    expect(container.textContent).toContain("source_review_packet_id: FARP-RC");
    expect(container.textContent).toContain("final_action_audit_records: 0");
    expect(container.textContent).toContain("Source review packet snapshot");
    expect(container.textContent).toContain("packet_hash: abcdef1234567890");
    expect(container.textContent).toContain("evidence_packs: 2");
    expect(container.textContent).toContain("Final action audit records");
    expect(container.textContent).toContain("records: 0");
    expect(container.textContent).toContain("read_only_final_action_audit_records");
    expect(container.textContent).toContain("Final action request drafts");
    expect(container.textContent).toContain("drafts: 0");
    expect(container.textContent).toContain("read_only_final_action_request_drafts");
    expect(container.textContent).toContain("no_assistant_confirmation_authority");
    expect(container.textContent).not.toContain("Execute final release approval");
    expect(container.textContent).not.toContain("Activate model version");
    expect(container.textContent).not.toContain("Prepare external share approval");
    expect(container.textContent).toContain("ACONF-REJECTED-HISTORY");
    expect(container.textContent).toContain("HAR-APPROVED-HISTORY");
    expect(container.textContent).toContain("queue-only rejection for workbench test");
    expect(container.textContent).toContain("workbench_resolution.side_effects");
    expect(container.textContent).toContain("release_decision: unchanged");
    expect(container.textContent).toContain("model_activation: false");
    expect(container.textContent).toContain("external_share: false");
    expect(container.textContent).not.toContain("Mark reviewed");
    expect(container.textContent).not.toContain("Resolve request only");
    expect(container.textContent).not.toContain("Reject request only");
    expect((container.querySelector('[data-testid="final-action-create-draft-final_release_approval"]') as HTMLButtonElement).disabled).toBe(false);
    expect((container.querySelector('[data-testid="final-action-create-draft-model_activation"]') as HTMLButtonElement).disabled).toBe(false);
    expect((container.querySelector('[data-testid="final-action-create-draft-external_release_share"]') as HTMLButtonElement).disabled).toBe(true);

    await act(async () => {
      buttonByText(container, "Download audit packet").click();
    });
    await flushAsyncWork();
    expect(assistantApiMock.exportReviewWorkbenchAuditPacket).toHaveBeenCalledWith("md", 50);

    await act(async () => {
      buttonByText(container, "JSON packet").click();
    });
    await flushAsyncWork();
    expect(assistantApiMock.exportReviewWorkbenchAuditPacket).toHaveBeenCalledWith("json", 50);

    await act(async () => {
      buttonByText(container, "Persist source packet").click();
    });
    await flushAsyncWork();
    expect(assistantApiMock.persistReviewWorkbenchAuditPacketSnapshot).toHaveBeenCalledWith(50);
    expect(finalActionsApiMock.getReadiness).toHaveBeenCalledTimes(2);
    act(() => root.unmount());
  });

  it("disables final release draft entry when readiness is blocked by a non-review-required decision", async () => {
    finalActionsApiMock.getReadiness.mockResolvedValue({
      ...finalActionReadinessFixture,
      current_state: {
        ...finalActionReadinessFixture.current_state,
        latest_release_decision: "PASS",
      },
      actions: finalActionReadinessFixture.actions.map((action) =>
        action.action === "final_release_approval"
          ? {
              ...action,
              blockers: [...action.blockers, "release_decision_not_review_required:PASS"],
            }
          : action,
      ),
    });

    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    const releaseDraftButton = container.querySelector(
      '[data-testid="final-action-create-draft-final_release_approval"]',
    ) as HTMLButtonElement;
    expect(container.textContent).toContain("release_decision: PASS");
    expect(container.textContent).toContain("release_decision_not_review_required:PASS");
    expect(container.textContent).toContain("draft_gate: release_decision_not_review_required:PASS");
    expect(releaseDraftButton.disabled).toBe(true);

    await act(async () => {
      releaseDraftButton.click();
    });
    expect(finalActionsApiMock.createRequestDraft).not.toHaveBeenCalled();
    act(() => root.unmount());
  });

  it("reloads assistant-generated appendix, benchmark, and governance relation after refresh", async () => {
    releasePacketApiMock.listAppendices.mockResolvedValue([
      {
        attachment_id: "RPA-REFRESH",
        release_decision_id: 1,
        tenant_id: 1,
        user_id: 1,
        attachment_type: "simulation_appendix",
        simulation_id: "SIM-RC",
        run_id: "RUN-RC",
        evidence_pack_id: "EVP-RC",
        appendix_hash: "refresh-hash",
        payload: {},
        created_at: "2026-04-24T00:00:00Z",
      },
    ]);
    bosKernelsApiMock.listBenchmarkRuns.mockResolvedValue([
      {
        benchmark_run_id: "BMR-REFRESH",
        suite_name: "simulation_lab_regression",
        scorecard: {
          status: "ready_for_review",
          suite_gate: "human_review_required",
          case_count: 1,
          passed_count: 1,
          failed_count: 0,
          cases: [
            {
              case_id: "CASE-refresh",
              name: "refresh_case",
              status: "passed",
              simulation_id: "SIM-REFRESH",
              run_id: "RUN-REFRESH",
              evidence_pack_id: "EVP-REFRESH-CASE",
              metrics: {
                ending_risk: 0.2,
                audit_event_count: 8,
                cycle_count: 8,
              },
              assertions: [{ metric: "ending_risk", passed: true }],
              expected_metrics: { max_ending_risk: 0.55 },
            },
          ],
        },
        evidence_pack_id: "EVP-REFRESH",
        created_at: "2026-04-24T00:00:00Z",
      },
    ]);
    bosKernelsApiMock.listModels.mockResolvedValue([
      {
        model_id: "MOD-REFRESH",
        name: "chronos-risk-candidate",
        task_type: "risk_forecast",
        status: "review_required",
      },
    ]);
    bosKernelsApiMock.listKnowledgeRelations.mockResolvedValue([
      {
        relation_id: "KREL-OLD",
        subject_type: "model_version",
        subject_id: "MVN-OLD",
        predicate: "evaluated_by",
        object_type: "benchmark_run",
        object_id: "BMR-OLD",
        evidence_pack_id: "EVP-OLD",
        payload: {},
        created_at: "2026-04-23T00:00:00Z",
      },
      {
        relation_id: "KREL-REFRESH",
        subject_type: "model_version",
        subject_id: "MVN-REFRESH",
        predicate: "evaluated_by",
        object_type: "benchmark_run",
        object_id: "BMR-REFRESH",
        evidence_pack_id: "EVP-REFRESH",
        payload: { decision: "request_review" },
        created_at: "2026-04-24T00:00:00Z",
      },
    ]);

    const { container, root } = renderInteractive();
    await flushAsyncWork();
    await flushAsyncWork();

    expect(container.textContent).toContain("SIM-RC");
    expect(container.textContent).toContain("RPA-REFRESH");
    expect(container.textContent).toContain("refresh-hash");
    expect(container.textContent).toContain("BMR-REFRESH");
    expect(container.textContent).toContain("EVP-REFRESH-CASE");
    expect(container.textContent).toContain("MOD-REFRESH");
    expect(container.textContent).toContain("KREL-REFRESH");
    expect(container.textContent).toContain("model_version -> benchmark_run -> evidence_pack");
    expect(container.textContent).not.toContain("Approved");
    act(() => root.unmount());
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });
});

function makeAssistantRunWithReleaseProofs() {
  return {
    run_id: "ARUN-RC-PROOFS",
    tenant_id: 1,
    user_id: 1,
    user_message: "run compliance lca tea",
    parsed_intent: {},
    status: "completed",
    evidence_pack_id: "EVP-ASSISTANT",
    tool_registry: { version: "assistant-tool-registry-v1" },
    created_at: "2026-04-25T00:00:00Z",
    completed_at: "2026-04-25T00:01:00Z",
    tool_calls: [],
    confirmation_requests: [],
    result_summary: {
      result_ids: {
        evidence_pack_id: "EVP-ASSISTANT",
        compliance_gate_id: "GATE-RC",
        compliance_evidence_pack_id: "EVP-COMPLIANCE",
        lca_result_id: "SUS-LCA-RC",
        lca_evidence_pack_id: "EVP-LCA",
        tea_result_id: "SUS-TEA-RC",
        tea_evidence_pack_id: "EVP-TEA",
      },
      compliance_gate: {
        gate_id: "GATE-RC",
        status: "blocked",
        missing_assays: ["moisture", "protein"],
        blocked_reasons: ["missing_assay:moisture", "missing_assay:protein"],
        evidence_pack_id: "EVP-COMPLIANCE",
      },
      lca_value_proof: {
        result_id: "SUS-LCA-RC",
        result: {
          co2e_abatement_kg: 431.6,
          energy_kwh: 20,
        },
      },
      tea_value_proof: {
        result_id: "SUS-TEA-RC",
        result: {
          gross_margin_usd: 105.4,
          operating_cost_usd: 19.6,
        },
      },
      uncertainty_warnings: [
        "emission_factor.electricity_kgco2e_per_kwh defaulted",
        "cost_factor.energy_usd_per_kwh defaulted",
      ],
    },
  };
}
