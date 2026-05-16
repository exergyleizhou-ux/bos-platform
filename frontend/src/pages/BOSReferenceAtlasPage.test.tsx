import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const hookMocks = vi.hoisted(() => ({
  useBioexecutorCandidates: vi.fn(),
  useBusinessKnowledgeReviewPacketExport: vi.fn(),
  useExternalSourceProcurementSummary: vi.fn(),
  useExternalSourceExtractions: vi.fn(),
  useExternalSourceReviewCards: vi.fn(),
  useExternalSourceSchemaReadiness: vi.fn(),
  useExternalSources: vi.fn(),
  useFeedstockCandidates: vi.fn(),
  useFeedstockDatasetCandidates: vi.fn(),
  useFeedstocksCatalog: vi.fn(),
  useLiteratureExtractionCandidateReviewPacketBulkExport: vi.fn(),
  useLiteratureExtractionCandidateReviewPacketExport: vi.fn(),
  useLiteratureExtractionCandidates: vi.fn(),
  useLiteratureExtractionEvidenceChainReadiness: vi.fn(),
  useLiteratureValuePromotionReadiness: vi.fn(),
  useLiteratureValuePromotionLifecycle: vi.fn(),
  useLiteratureValuePromotionAuditExport: vi.fn(),
  useLiteratureValueRuntimeActivationPreview: vi.fn(),
  useCreateLiteratureValuePromotionRequest: vi.fn(),
  useApproveLiteratureValuePromotionRequest: vi.fn(),
  useRejectLiteratureValuePromotionRequest: vi.fn(),
  usePromoteLiteratureValueRequestToOverlay: vi.fn(),
  useCreateLiteratureValueRuntimeActivation: vi.fn(),
  useRollbackLiteratureValueRuntimeActivation: vi.fn(),
  useCreateLiteratureExtractionReviewDraft: vi.fn(),
  useLiteratureExtractionReviewDraftComparison: vi.fn(),
  useLiteratureExtractionReviewDrafts: vi.fn(),
  useManuscriptCampaigns: vi.fn(),
  useParseReferenceDocument: vi.fn(),
  usePromoteReferenceIngestionItem: vi.fn(),
  useReferenceIngestionHealth: vi.fn(),
  useReferenceIngestionItems: vi.fn(),
  useResolveExternalSourceReviewCard: vi.fn(),
  useReviewedExternalCandidateKnowledgeBase: vi.fn(),
  useReviewedExternalCandidateActivationPreview: vi.fn(),
  useReviewedExternalCandidateRollbackPreview: vi.fn(),
  useReviewedExternalCandidateRuntimeReadiness: vi.fn(),
  useReviewedExternalCandidateSummary: vi.fn(),
  useReviewedExternalCandidates: vi.fn(),
  useSpeciesCatalog: vi.fn(),
}));

vi.mock("@/hooks/useBos", () => hookMocks);

import BOSReferenceAtlasPage, {
  DomainCandidateGroups,
  ExternalReviewCardQueueItem,
  ExternalSourceSchemaReadinessStrip,
  FeedstockDatasetCandidateCard,
  ReviewedExternalCandidateCard,
} from "@/pages/BOSReferenceAtlasPage";
import type { BusinessKnowledgeCoverageGroup } from "@/types/bos";

function queryResult(data: unknown) {
  return {
    data,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  };
}

function mutationResult() {
  return {
    mutate: vi.fn(),
    isPending: false,
  };
}

const feedstockDatasetCandidate = {
  candidate_uid: "feedstock_dataset_candidate:B-FEED-001",
  candidate_type: "feedstock_dataset_candidate",
  source_id: "B-FEED-001",
  source_name: "USDA FoodData Central",
  source_owner: "USDA",
  source_kind: "public_dataset",
  source_ref: "https://fdc.nal.usda.gov/",
  license_note: "public domain",
  ingestion_mode: "metadata_only",
  geography: "US",
  units: "source-defined",
  source_version_required: true,
  checked_at_required: true,
  mapping_confidence: "unmapped",
  waste_proxy_warning: "Public food/feed composition datasets are staged as feedstock proxy metadata only.",
  review_status: "pending_review",
  human_review_required: true,
  numeric_values_included: false,
  runtime_activated: false,
  validated_default_write_enabled: false,
  next_action: "Review mapping before extraction.",
} as const;

const literatureExtractionCandidate = {
  candidate_uid: "literature_extraction_candidate:LIT-AGR-GI-001",
  candidate_id: "LIT-AGR-GI-001",
  candidate_type: "literature_extraction_candidate",
  source_id: "A-BSF-007",
  doi: "10.3390/su151511526",
  source_ref: "https://doi.org/10.3390/su151511526",
  title: "Agronomic evaluation of black soldier fly frass",
  species: "radish",
  feedstock: "biosolids",
  treatment: "BSF frass-amended growing media",
  metric_key: "germination_index",
  metric_label: "Germination index",
  raw_value: "85-102",
  unit: "%",
  condition_context: "Radish seed germination assay",
  experiment_context: "Frass treatment compared with control media.",
  table_or_section_ref: "Results section 3.2",
  extraction_note: "Candidate raw value range only; reviewer must verify boundary and license before use.",
  license_note: "Open-access publisher page; reuse and extracted-value policy must be checked before release evidence.",
  source_kind: "peer_reviewed_literature",
  review_status: "pending_review",
  human_review_required: true,
  numeric_values_included: true,
  release_evidence_allowed: false,
  runtime_activation_enabled: false,
  validated_default_write_enabled: false,
  promotion_enabled: false,
  guardrails: [
    "literature_values_are_pending_review_candidates",
    "numeric_values_included_but_not_validated_defaults",
    "release_evidence_allowed_false",
  ],
} as const;

const reviewedExternalCandidate = {
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
} as const;

const businessKnowledgeCoverageGroups: BusinessKnowledgeCoverageGroup[] = [
  {
    group_key: "bioexecutor_species",
    label: "Bioexecutor species",
    expected_item_count: 3,
    covered_item_count: 3,
    coverage_percent: 100,
    status: "covered",
    review_gated: true,
    runtime_activation_enabled: false,
    validated_default_write_enabled: false,
    numeric_values_included: false,
    items: [
      {
        item_key: "mw",
        label: "MW / 黄粉虫 / Tenebrio molitor",
        status: "validated_read_model",
        coverage_basis: "validated_read_model",
        evidence_refs: ["SPECIES_DB.MW"],
        notes: "Species coverage is counted separately from source metadata families.",
        review_gated: true,
        runtime_activation_enabled: false,
        validated_default_write_enabled: false,
        numeric_values_included: false,
        review_workflow: {
          review_packet_id: "AGR-GERMINATION-INDEX-REVIEW-PACKET",
          review_state: "pending_review",
          source_packet_persistence: "read_model_only",
          reviewer_notes_required: true,
          reviewer_notes: "",
          allowed_review_actions: ["approve_metadata", "request_license_clearance", "reject"],
          approval_enabled: false,
          rejection_enabled: true,
          release_evidence_allowed: false,
          runtime_activation_enabled: false,
          validated_default_write_enabled: false,
          numeric_values_allowed: false,
          guardrails: [
            "review_workflow_is_read_only",
            "numeric_values_blocked",
            "release_evidence_allowed_false",
          ],
        },
      },
    ],
  },
  {
    group_key: "product_agronomy_outputs",
    label: "Product and agronomy outputs",
    expected_item_count: 5,
    covered_item_count: 5,
    coverage_percent: 70,
    status: "partial",
    review_gated: true,
    runtime_activation_enabled: false,
    validated_default_write_enabled: false,
    numeric_values_included: false,
    items: [
      {
        item_key: "germination_index",
        label: "Germination index / GI",
        status: "candidate_read_model",
        coverage_basis: "candidate_read_model",
        evidence_refs: ["external_knowledge_candidates.germination_index"],
        notes: "Review-gated GI metadata candidate exists; no GI values or formal thresholds are promoted.",
        review_gated: true,
        runtime_activation_enabled: false,
        validated_default_write_enabled: false,
        numeric_values_included: false,
      },
    ],
  },
];

describe("BOSReferenceAtlasPage", () => {
  beforeEach(() => {
    hookMocks.useSpeciesCatalog.mockReturnValue(queryResult({ species: [], count: 0 }));
    hookMocks.useBioexecutorCandidates.mockReturnValue(queryResult({ candidates: [], count: 0 }));
    hookMocks.useBusinessKnowledgeReviewPacketExport.mockImplementation((itemKey?: string) =>
      queryResult(
        itemKey === "germination_index"
          ? {
              schema_version: "business_knowledge_review_packet_export_v1",
              tenant_id: 1,
              export_format: "json",
              export_filename: "AGR-GERMINATION-INDEX-REVIEW-PACKET.json",
              content_hash: "abc123456789abc123456789abc123456789abc123456789abc123456789abcd",
              export_manifest: {
                item_key: "germination_index",
                group_key: "product_agronomy_outputs",
                review_packet_id: "AGR-GERMINATION-INDEX-REVIEW-PACKET",
                review_state: "pending_review",
                source_packet_persistence: "read_model_only",
                export_policy: "response_only_no_file_write",
              },
              review_packet: {},
              side_effects: {
                file_written: false,
                runtime_activation: false,
                validated_default_write: false,
                species_db_write: false,
                feedstock_db_write: false,
                numeric_value_extraction: false,
                final_action_execution: false,
              },
              guardrails: [
                "business_knowledge_review_packet_export_is_read_only",
                "export_response_only_no_file_write",
              ],
            }
          : undefined,
      ),
    );
    hookMocks.useLiteratureExtractionCandidateReviewPacketExport.mockImplementation((candidateId?: string) =>
      queryResult(
        candidateId === "LIT-AGR-GI-001"
          ? {
              schema_version: "literature_extraction_candidate_review_packet_export_v1",
              tenant_id: 1,
              export_format: "json",
              export_filename: "LIT-AGR-GI-001-literature-extraction-review-packet.json",
              content_hash: "def123456789def123456789def123456789def123456789def123456789def1",
              export_manifest: {
                export_id: "literature-extraction-review-packet-export:LIT-AGR-GI-001:def123456789",
                candidate_id: "LIT-AGR-GI-001",
                candidate_type: "literature_extraction_candidate",
                source_id: "A-BSF-007",
                metric_key: "germination_index",
                review_status: "pending_review",
                release_evidence_allowed: false,
                runtime_activation_enabled: false,
                validated_default_write_enabled: false,
                promotion_enabled: false,
                final_action_execution: false,
                export_policy: "response_only_no_file_write",
              },
              review_packet: {
                candidate: literatureExtractionCandidate,
                candidate_payload: literatureExtractionCandidate,
                raw_value: literatureExtractionCandidate.raw_value,
                unit: literatureExtractionCandidate.unit,
                conditions: {
                  condition_context: literatureExtractionCandidate.condition_context,
                },
                license_note: literatureExtractionCandidate.license_note,
                source_trace: {
                  source_ref: literatureExtractionCandidate.source_ref,
                },
                release_evidence_allowed: false,
                runtime_activation_enabled: false,
                validated_default_write_enabled: false,
                promotion_enabled: false,
                final_action_execution: false,
              },
              side_effects: {
                file_written: false,
                runtime_activation: false,
                validated_default_write: false,
                species_db_write: false,
                feedstock_db_write: false,
                release_evidence_use: false,
                promotion: false,
                final_action_execution: false,
              },
              guardrails: [
                "literature_extraction_review_packet_export_is_read_only",
                "export_response_only_no_file_write",
              ],
            }
          : undefined,
      ),
    );
    hookMocks.useLiteratureExtractionCandidateReviewPacketBulkExport.mockReturnValue(
      queryResult({
        schema_version: "literature_extraction_candidate_review_packet_bulk_export_v1",
        tenant_id: 1,
        export_format: "json",
        export_filename: "literature-extraction-review-packets.json",
        content_hash: "fed123456789fed123456789fed123456789fed123456789fed123456789fed1",
        export_manifest: {
          export_id: "literature-extraction-review-packet-bulk-export:1:fed123456789",
          tenant_id: 1,
          candidate_count: 1,
          candidate_ids: ["LIT-AGR-GI-001"],
          metric_counts: { germination_index: 1 },
          export_policy: "response_only_no_file_write",
          source_packet_persistence: "persisted_candidate_records_only",
          release_evidence_allowed: false,
          runtime_activation_enabled: false,
          validated_default_write_enabled: false,
          promotion_enabled: false,
          final_action_execution: false,
        },
        packet_exports: [],
        count: 1,
        metric_counts: { germination_index: 1 },
        side_effects: {
          file_written: false,
          runtime_activation: false,
          validated_default_write: false,
          species_db_write: false,
          feedstock_db_write: false,
          release_evidence_use: false,
          promotion: false,
          final_action_execution: false,
        },
        guardrails: [
          "literature_extraction_bulk_export_is_read_only",
          "export_response_only_no_file_write",
          "tenant_scoped_persisted_candidates_only",
        ],
      }),
    );
    hookMocks.useLiteratureExtractionEvidenceChainReadiness.mockReturnValue(
      queryResult({
        schema_version: "literature_extraction_evidence_chain_readiness_v1",
        tenant_id: 1,
        chain_complete: true,
        candidate_count: 1,
        packet_export_ready: true,
        bulk_export_ready: true,
        review_draft_count: 1,
        comparison_ready: true,
        report_ready: true,
        auto_use_allowed: false,
        release_evidence_allowed: false,
        runtime_activation_enabled: false,
        validated_default_write_enabled: false,
        promotion_enabled: false,
        final_action_execution: false,
        side_effects: {
          candidate_status_update: false,
          file_written: false,
          runtime_activation: false,
          validated_default_write: false,
          species_db_write: false,
          feedstock_db_write: false,
          release_evidence_use: false,
          promotion: false,
          final_action_execution: false,
        },
        guardrails: [
          "literature_evidence_chain_readiness_is_read_only",
          "chain_complete_does_not_allow_auto_use",
        ],
        blocking_reason: null,
        readiness_notes: [
          "literature raw values are persisted only as pending_review candidates",
          "chain completion does not permit release evidence, runtime activation, defaults, promotion, or final actions",
        ],
      }),
    );
    hookMocks.useLiteratureValuePromotionReadiness.mockReturnValue(
      queryResult({
        schema_version: "literature_value_promotion_readiness_v1",
        tenant_id: 1,
        candidate_id: "LIT-AGR-GI-001",
        source_review_packet_hash: "def123456789def123456789def123456789def123456789def123456789def1",
        comparison_hash: "cmp123456789cmp123456789cmp123456789cmp123456789cmp123456789cm",
        raw_value: "85-102",
        unit: "%",
        conditions: { source_ref: "https://doi.org/10.3390/su151511526" },
        request_status: "requested",
        existing_promotion_request_id: "LVPR-TEST-001",
        target_use_options: ["candidate_overlay_review"],
        auto_use_allowed: false,
        release_evidence_allowed: false,
        runtime_activation_enabled: false,
        validated_default_write_enabled: false,
        promotion_enabled: false,
        final_action_execution: false,
        side_effects: {
          overlay_write: false,
          runtime_activation: false,
          validated_default_write: false,
          species_db_write: false,
          feedstock_db_write: false,
          release_evidence_use: false,
          promotion: false,
          final_action_execution: false,
        },
        guardrails: ["literature_value_promotion_requires_dual_approval"],
        blocking_reason: "release_manager_approval_required",
      }),
    );
    hookMocks.useLiteratureValuePromotionLifecycle.mockReturnValue(
      queryResult({
        schema_version: "literature_value_promotion_lifecycle_v1",
        tenant_id: 1,
        candidate_id: "LIT-AGR-GI-001",
        promotion_request_count: 1,
        approval_count: 1,
        overlay_count: 0,
        runtime_activation_count: 0,
        release_evidence_link_count: 0,
        rollback_count: 0,
        promotion_request_ids: ["LVPR-TEST-001"],
        approval_ids: ["LVPA-TEST-SCI"],
        overlay_ids: [],
        activation_ids: [],
        release_evidence_link_ids: [],
        rollback_ids: [],
        request_statuses: ["requested"],
        approval_actions: ["approve"],
        overlay_statuses: [],
        activation_statuses: [],
        release_evidence_link_statuses: [],
        rollback_statuses: [],
        release_decision_states: [],
        lifecycle_read_only: true,
        release_decision_unchanged: true,
        human_review_required: true,
        final_action_execution: false,
        side_effects: {
          overlay_write: false,
          runtime_activation: false,
          release_evidence_use: false,
          rollback: false,
          validated_default_write: false,
          species_db_write: false,
          feedstock_db_write: false,
          final_action_execution: false,
        },
        guardrails: ["release_decision_remains_review_required"],
      }),
    );
    hookMocks.useLiteratureValuePromotionAuditExport.mockReturnValue(
      queryResult({
        schema_version: "literature_value_promotion_audit_export_v1",
        tenant_id: 1,
        candidate_id: "LIT-AGR-GI-001",
        export_format: "json",
        export_policy: "response_only_no_file_write",
        content_hash: "aaabbbcccdddeeefff111222333444555666777888999000aaabbbcccdddeee1",
        export_manifest: {
          export_policy: "response_only_no_file_write",
          file_written: false,
        },
        request: { request_status: "requested" },
        approvals: [{ approval_id: "LVPA-TEST-SCI" }],
        overlay: {
          source_ref: "https://doi.org/10.3390/su151511526",
          normalized_value: "85-102 %",
          overlay_hash: "overlayhash",
        },
        runtime_activation: null,
        release_evidence_link: null,
        rollback: null,
        db_pollution_proof: {
          validated_default_write: false,
          species_db_write: false,
          feedstock_db_write: false,
        },
        final_action_non_execution_proof: {
          final_action_execution: false,
          release_decisions_all_review_required: true,
          release_decision_states: [],
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
        guardrails: ["export_response_only_no_file_write", "release_decision_remains_review_required"],
      }),
    );
    hookMocks.useLiteratureExtractionReviewDrafts.mockReturnValue(
      queryResult({
        schema_version: "literature_extraction_review_draft_list_v1",
        tenant_id: 1,
        count: 1,
        drafts: [
          {
            schema_version: "literature_extraction_review_draft_v1",
            review_draft_id: "LERD-TEST-001",
            tenant_id: 1,
            candidate_id: "LIT-AGR-GI-001",
            source_id: "A-BSF-007",
            reviewer_user_id: 1,
            review_intent: "approve_candidate_use_intent",
            reviewer_notes: "Reference Atlas reviewer draft intent only.",
            status: "draft_intent_recorded",
            source_review_packet_export_id: "literature-extraction-review-packet-export:LIT-AGR-GI-001:def123456789",
            source_review_packet_hash: "def123456789def123456789def123456789def123456789def123456789def1",
            candidate_snapshot: { review_status: "pending_review" },
            export_manifest: {
              candidate_id: "LIT-AGR-GI-001",
              export_policy: "response_only_no_file_write",
            },
            release_evidence_allowed: false,
            runtime_activation_enabled: false,
            validated_default_write_enabled: false,
            promotion_enabled: false,
            final_action_execution: false,
            side_effects: {
              candidate_status_update: false,
              file_written: false,
              runtime_activation: false,
              validated_default_write: false,
              species_db_write: false,
              feedstock_db_write: false,
              release_evidence_use: false,
              promotion: false,
              final_action_execution: false,
            },
            guardrails: ["candidate_status_remains_pending_review"],
            idempotency_key: "reference-atlas:LIT-AGR-GI-001:approve_candidate_use_intent",
            created_at: "2026-04-28T07:45:00+00:00",
            updated_at: "2026-04-28T07:45:00+00:00",
          },
        ],
        side_effects: {
          candidate_status_update: false,
          runtime_activation: false,
          validated_default_write: false,
          species_db_write: false,
          feedstock_db_write: false,
          release_evidence_use: false,
          promotion: false,
          final_action_execution: false,
        },
        guardrails: ["literature_extraction_review_draft_list_is_read_only"],
      }),
    );
    hookMocks.useLiteratureExtractionReviewDraftComparison.mockReturnValue(
      queryResult({
        schema_version: "literature_extraction_review_draft_comparison_v1",
        tenant_id: 1,
        candidate_id: "LIT-AGR-GI-001",
        current_review_draft_id: "LERD-TEST-001",
        previous_review_draft_id: null,
        current_revision_hash: "abc123456789abc123456789abc123456789abc123456789abc123456789abc1",
        current_candidate_snapshot_hash: "snap123456789snap123456789snap123456789snap123456789snap123456789s",
        current_export_manifest_hash: "man123456789man123456789man123456789man123456789man123456789ma",
        source_review_packet_hash: "def123456789def123456789def123456789def123456789def123456789def1",
        current_response_packet_hash: "def123456789def123456789def123456789def123456789def123456789def1",
        changed_field_filter: null,
        comparison_manifest: {
          comparison_id: "literature-extraction-review-draft-comparison:LIT-AGR-GI-001:abc123456789",
          comparison_hash: "cmp123456789cmp123456789cmp123456789cmp123456789cmp123456789cm",
          comparison_policy: "response_only_no_file_write",
          revision_count: 1,
          candidate_status: "pending_review",
          release_evidence_allowed: false,
          runtime_activation_enabled: false,
          validated_default_write_enabled: false,
          promotion_enabled: false,
          final_action_execution: false,
        },
        report_manifest: {
          report_id: "literature-extraction-review-draft-comparison-report:LIT-AGR-GI-001:abc123456789",
          report_policy: "response_only_no_file_write",
          report_format: "json_response",
          changed_field_filter: null,
          changed_field_count: 0,
          file_written: false,
        },
        report_payload: {
          summary: {
            changed_fields: [],
            packet_hash_matches: true,
            candidate_snapshot_matches: true,
          },
          guardrails: ["report_is_response_only"],
        },
        comparison_summary: {
          candidate_snapshot_changed_since_previous: false,
          packet_hash_changed_since_previous: false,
          review_intent_changed_since_previous: false,
          side_effect_flags_changed_since_previous: false,
          export_manifest_changed_since_previous: false,
          current_response_packet_hash_matches_draft: true,
          current_candidate_snapshot_matches_draft: true,
        },
        changed_fields: [],
        audit_trail: [
          {
            review_draft_id: "LERD-TEST-001",
            revision_index: 1,
            revision_hash: "abc123456789abc123456789abc123456789abc123456789abc123456789abc1",
            candidate_snapshot_hash: "snap123456789snap123456789snap123456789snap123456789snap123456789s",
            export_manifest_hash: "man123456789man123456789man123456789man123456789man123456789ma",
            source_review_packet_hash: "def123456789def123456789def123456789def123456789def123456789def1",
            review_intent: "approve_candidate_use_intent",
            changed_fields: [],
            side_effects: {
              file_written: false,
              release_evidence_use: false,
              final_action_execution: false,
            },
            created_at: "2026-04-28T07:45:00+00:00",
          },
        ],
        side_effects: {
          candidate_status_update: false,
          file_written: false,
          runtime_activation: false,
          validated_default_write: false,
          species_db_write: false,
          feedstock_db_write: false,
          release_evidence_use: false,
          promotion: false,
          final_action_execution: false,
        },
        guardrails: ["literature_extraction_review_draft_comparison_is_read_only"],
      }),
    );
    hookMocks.useCreateLiteratureExtractionReviewDraft.mockReturnValue(mutationResult());
    hookMocks.useFeedstocksCatalog.mockReturnValue(queryResult({ feedstocks: [], count: 0 }));
    hookMocks.useFeedstockCandidates.mockReturnValue(queryResult({ candidates: [], count: 0 }));
    hookMocks.useFeedstockDatasetCandidates.mockReturnValue(
      queryResult({
        items: [
          feedstockDatasetCandidate,
        ],
        count: 1,
        guardrails: [
          "feedstock_dataset_candidates_are_metadata_only",
          "no_feedstock_db_writes",
          "runtime_activation_blocked",
        ],
      }),
    );
    hookMocks.useLiteratureExtractionCandidates.mockReturnValue(
      queryResult({
        schema_version: "literature_extraction_candidate_list_v1",
        items: [literatureExtractionCandidate],
        count: 1,
        metric_counts: { germination_index: 1 },
        side_effects: {
          file_written: false,
          runtime_activation: false,
          validated_default_write: false,
          species_db_write: false,
          feedstock_db_write: false,
          release_evidence_use: false,
          final_action_execution: false,
        },
        guardrails: [
          "literature_extraction_candidates_are_review_gated",
          "numeric_values_are_candidate_raw_values_only",
          "release_evidence_allowed_false",
        ],
      }),
    );
    hookMocks.useExternalSources.mockReturnValue(queryResult({ items: [], count: 0, guardrails: [] }));
    hookMocks.useExternalSourceProcurementSummary.mockReturnValue(
      queryResult({
        schema_version: "external_source_procurement_summary_v1",
        source_count: 0,
        source_kind_counts: {},
        ingestion_mode_counts: {},
        bos_module_counts: {},
        review_required_count: 0,
        metadata_only_count: 0,
        manual_review_first_count: 0,
        other_ingestion_mode_count: 0,
        commercial_or_restricted_count: 0,
        guardrails: [],
      }),
    );
    hookMocks.useExternalSourceSchemaReadiness.mockReturnValue(
      queryResult({
        schema_version: "external_source_schema_readiness_v1",
        status: "ready",
        schema_ready: true,
        source_catalog_ready: true,
        knowledge_coverage_ready: true,
        knowledge_coverage_percent: 100,
        source_metadata_coverage_percent: 100,
        business_knowledge_coverage_percent: 84.17,
        business_knowledge_coverage_groups: businessKnowledgeCoverageGroups,
        knowledge_coverage_domains: [
          {
            domain_key: "bsf_metadata",
            label: "BSF literature and extraction metadata",
            coverage_basis: "source_metadata",
            expected_source_count: 9,
            covered_source_count: 9,
            coverage_percent: 100,
            status: "covered",
            review_gated: true,
            runtime_activation_enabled: false,
            validated_default_write_enabled: false,
            numeric_values_included: false,
          },
          {
            domain_key: "feedstock_metadata",
            label: "Feedstock public dataset metadata",
            coverage_basis: "source_metadata",
            expected_source_count: 9,
            covered_source_count: 9,
            coverage_percent: 100,
            status: "covered",
            review_gated: true,
            runtime_activation_enabled: false,
            validated_default_write_enabled: false,
            numeric_values_included: false,
          },
          {
            domain_key: "lca",
            label: "LCA source metadata",
            coverage_basis: "source_metadata",
            expected_source_count: 15,
            covered_source_count: 15,
            coverage_percent: 100,
            status: "covered",
            review_gated: true,
            runtime_activation_enabled: false,
            validated_default_write_enabled: false,
            numeric_values_included: false,
          },
        ],
        feedstock_dataset_candidate_count: 9,
        literature_extraction_candidate_count: 1,
        phase4a_domain_metadata_ready: true,
        phase4a_domain_candidate_counts: {
          lca: 6,
          tea: 6,
          compliance: 5,
          model_provider: 4,
          github_reference: 3,
        },
        phase4a_domain_expected_counts: {
          lca: 6,
          tea: 6,
          compliance: 5,
          model_provider: 4,
          github_reference: 3,
        },
        phase4a_domain_missing_counts: {
          lca: 0,
          tea: 0,
          compliance: 0,
          model_provider: 0,
          github_reference: 0,
        },
        reviewed_metadata_lane_ready: true,
        required_tables: [
          { table_name: "external_source_records", present: true, row_count: 70 },
          { table_name: "external_source_review_cards", present: true, row_count: 8 },
          { table_name: "external_source_extraction_records", present: true, row_count: 8 },
          { table_name: "reviewed_external_candidate_records", present: true, row_count: 0 },
        ],
        missing_required_tables: [],
        blockers: [],
        guardrails: [
          "schema_readiness_only",
          "no_table_creation",
          "no_seed_mutation",
          "no_validated_default_writes",
        ],
      }),
    );
    hookMocks.useExternalSourceReviewCards.mockReturnValue(queryResult({ items: [], count: 0 }));
    hookMocks.useExternalSourceExtractions.mockReturnValue(queryResult({ items: [], count: 0, guardrails: [] }));
    hookMocks.useReviewedExternalCandidates.mockReturnValue(queryResult({ items: [], count: 0, guardrails: [] }));
    hookMocks.useReviewedExternalCandidateSummary.mockReturnValue(
      queryResult({
        schema_version: "reviewed_external_candidate_lane_summary_v1",
        tenant_id: 1,
        reviewed_candidate_count: 0,
        reviewed_metadata_candidate_count: 0,
        pending_runtime_activation_count: 0,
        runtime_activated_count: 0,
        validated_default_write_enabled_count: 0,
        numeric_value_candidate_count: 0,
        release_evidence_blocked_count: 0,
        statuses: {},
        candidate_types: {},
        candidate_domains: {},
        latest_reviewed_at: null,
        guardrails: [],
      }),
    );
    hookMocks.useReviewedExternalCandidateKnowledgeBase.mockReturnValue(
      queryResult({
        schema_version: "reviewed_external_candidate_knowledge_base_v1",
        tenant_id: 1,
        status: "ready_for_review",
        schema_ready: true,
        source_catalog_ready: true,
        reviewed_metadata_lane_ready: true,
        knowledge_coverage_ready: true,
        knowledge_coverage_percent: 100,
        source_metadata_coverage_percent: 100,
        business_knowledge_coverage_percent: 84.17,
        business_knowledge_coverage_groups: businessKnowledgeCoverageGroups,
        knowledge_coverage_domains: [
          {
            domain_key: "bsf_metadata",
            label: "BSF literature and extraction metadata",
            coverage_basis: "source_metadata",
            expected_source_count: 9,
            covered_source_count: 9,
            coverage_percent: 100,
            status: "covered",
            review_gated: true,
            runtime_activation_enabled: false,
            validated_default_write_enabled: false,
            numeric_values_included: false,
          },
          {
            domain_key: "feedstock_metadata",
            label: "Feedstock public dataset metadata",
            coverage_basis: "source_metadata",
            expected_source_count: 9,
            covered_source_count: 9,
            coverage_percent: 100,
            status: "covered",
            review_gated: true,
            runtime_activation_enabled: false,
            validated_default_write_enabled: false,
            numeric_values_included: false,
          },
          {
            domain_key: "lca",
            label: "LCA source metadata",
            coverage_basis: "source_metadata",
            expected_source_count: 15,
            covered_source_count: 15,
            coverage_percent: 100,
            status: "covered",
            review_gated: true,
            runtime_activation_enabled: false,
            validated_default_write_enabled: false,
            numeric_values_included: false,
          },
        ],
        supported_candidate_types: [
          "bsf_reviewed_metadata_candidate",
          "feedstock_metadata_candidate",
          "lca_boundary_metadata_candidate",
          "tea_factor_candidate",
          "compliance_rule_candidate",
          "model_provider_capability_candidate",
          "github_reference_candidate",
        ],
        supported_candidate_domains: [
          "bsf_metadata",
          "feedstock_metadata",
          "lca",
          "tea",
          "compliance",
          "model_provider",
          "github_reference",
        ],
        phase4a_domain_metadata_ready: true,
        phase4a_domain_candidate_counts: {
          lca: 6,
          tea: 6,
          compliance: 5,
          model_provider: 4,
          github_reference: 3,
        },
        phase4a_domain_expected_counts: {
          lca: 6,
          tea: 6,
          compliance: 5,
          model_provider: 4,
          github_reference: 3,
        },
        phase4a_domain_missing_counts: {
          lca: 0,
          tea: 0,
          compliance: 0,
          model_provider: 0,
          github_reference: 0,
        },
        reviewed_candidate_count: 0,
        reviewed_metadata_candidate_count: 0,
        pending_runtime_activation_count: 0,
        runtime_activated_count: 0,
        validated_default_write_enabled_count: 0,
        numeric_value_candidate_count: 0,
        candidate_types: {},
        candidate_domains: {},
        blockers: [],
        guardrails: [
          "knowledge_base_summary_is_read_only",
          "reviewed_candidates_do_not_count_as_release_evidence",
        ],
      }),
    );
    hookMocks.useManuscriptCampaigns.mockReturnValue(queryResult({ campaigns: [], count: 0 }));
    hookMocks.useReferenceIngestionItems.mockReturnValue(queryResult({ items: [], count: 0 }));
    hookMocks.useReferenceIngestionHealth.mockReturnValue(
      queryResult({
        parser_name: "mineru",
        parser_available: false,
        parser_command: "mineru",
        parser_extra_args: "-b pipeline -m txt",
        rollback_mode: "staging_only",
        promotion_enabled: false,
        guardrails: [],
      }),
    );
    hookMocks.useParseReferenceDocument.mockReturnValue(mutationResult());
    hookMocks.usePromoteReferenceIngestionItem.mockReturnValue(mutationResult());
    hookMocks.useResolveExternalSourceReviewCard.mockReturnValue(mutationResult());
    hookMocks.useLiteratureValueRuntimeActivationPreview.mockReturnValue(queryResult(undefined));
    hookMocks.useCreateLiteratureValuePromotionRequest.mockReturnValue(mutationResult());
    hookMocks.useApproveLiteratureValuePromotionRequest.mockReturnValue(mutationResult());
    hookMocks.useRejectLiteratureValuePromotionRequest.mockReturnValue(mutationResult());
    hookMocks.usePromoteLiteratureValueRequestToOverlay.mockReturnValue(mutationResult());
    hookMocks.useCreateLiteratureValueRuntimeActivation.mockReturnValue(mutationResult());
    hookMocks.useRollbackLiteratureValueRuntimeActivation.mockReturnValue(mutationResult());
    hookMocks.useReviewedExternalCandidateActivationPreview.mockReturnValue(queryResult(undefined));
    hookMocks.useReviewedExternalCandidateRuntimeReadiness.mockReturnValue(queryResult(undefined));
    hookMocks.useReviewedExternalCandidateRollbackPreview.mockReturnValue(queryResult(undefined));
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("surfaces feedstock public dataset candidates in the Reference Atlas counts", () => {
    const html = renderToStaticMarkup(<BOSReferenceAtlasPage />);

    expect(html).toContain("1 public dataset candidates");
    expect(html).toContain("1 literature value candidates");
  });

  it("renders feedstock public dataset candidate cards as metadata-only staged records", () => {
    const html = renderToStaticMarkup(
      <FeedstockDatasetCandidateCard candidate={feedstockDatasetCandidate} />,
    );

    expect(html).toContain("B-FEED-001");
    expect(html).toContain("USDA FoodData Central");
    expect(html).toContain("candidate_type: feedstock_dataset_candidate");
    expect(html).toContain("public_dataset");
    expect(html).toContain("metadata_only");
    expect(html).toContain("license_status: pending_review");
    expect(html).toContain("human_review_required: true");
    expect(html).toContain("numeric_values_included: false");
    expect(html).toContain("promotion_enabled: false");
    expect(html).toContain("runtime_activated: false");
    expect(html).toContain("validated_default_write_enabled: false");
    expect(html).toContain("blocked_use: no composition defaults; no release evidence; no runtime activation");
    expect(html).toContain("feedstock proxy metadata only");
  });

  it("renders reviewed candidate domain grouping with visible guardrails", () => {
    const html = renderToStaticMarkup(
      <DomainCandidateGroups
        cards={[
          {
            id: "bsf-1",
            domain: "bsf",
            title: "REC-BSF-CARD-001",
            subtitle: "bsf_reviewed_metadata_candidate:BSF-CARD-001",
            lane: "Reviewed external",
            candidateType: "bsf_reviewed_metadata_candidate",
            reviewStatus: "approved_for_candidate_use",
            licenseStatus: "metadata_only",
            allowedUse: "candidate metadata only",
            blockedUse: "no validated defaults; no release evidence",
            humanReviewRequired: true,
            promotionEnabled: false,
            runtimeActivated: false,
            validatedDefaultWriteEnabled: false,
            sourceKind: "peer_reviewed_literature",
            sourceRef: "10.1016/j.wasman.2020.07.050",
          },
          {
            id: "feedstock-1",
            domain: "feedstock",
            title: "B-FEED-001",
            subtitle: "USDA FoodData Central",
            lane: "Feedstock public dataset candidates",
            candidateType: "feedstock_dataset_candidate",
            reviewStatus: "pending_review",
            licenseStatus: "pending_review",
            allowedUse: "source metadata and mapping review only",
            blockedUse: "no composition defaults; no release evidence; no runtime activation",
            humanReviewRequired: true,
            promotionEnabled: false,
            runtimeActivated: false,
            validatedDefaultWriteEnabled: false,
            sourceKind: "public_dataset",
            sourceRef: "https://fdc.nal.usda.gov/",
          },
          {
            id: "lca-1",
            domain: "lca",
            title: "C-LCA-010",
            subtitle: "Grid emission metadata",
            lane: "Reviewed metadata source catalog",
            candidateType: "lca_boundary_metadata_candidate",
            reviewStatus: "pending_review",
            licenseStatus: "pending_review",
            allowedUse: "metadata discovery and reviewer triage only",
            blockedUse: "no runtime activation; no release evidence; no validated defaults",
            humanReviewRequired: true,
            promotionEnabled: false,
            runtimeActivated: false,
            validatedDefaultWriteEnabled: false,
            sourceKind: "public_dataset",
            sourceRef: "candidate:IEA-grid-emissions-factor",
          },
          {
            id: "agronomy-germination-index",
            domain: "agronomy",
            title: "Germination index / GI",
            subtitle: "candidate_read_model",
            lane: "Agronomy output candidates",
            candidateType: "release_gate_candidate",
            reviewStatus: "candidate_read_model",
            licenseStatus: "metadata_only",
            allowedUse: "Reference Atlas read-only agronomy output metadata",
            blockedUse: "no validated defaults; no release evidence; no runtime activation; no numeric thresholds",
            humanReviewRequired: true,
            promotionEnabled: false,
            runtimeActivated: false,
            validatedDefaultWriteEnabled: false,
            sourceKind: "candidate_read_model",
            sourceRef: "external_knowledge_candidates.germination_index",
            reviewPacketExportItemKey: "germination_index",
            reviewWorkflow: {
              review_packet_id: "AGR-GERMINATION-INDEX-REVIEW-PACKET",
              review_state: "pending_review",
              source_packet_persistence: "read_model_only",
              reviewer_notes_required: true,
              reviewer_notes: "",
              allowed_review_actions: ["approve_metadata", "request_license_clearance", "reject"],
              approval_enabled: false,
              rejection_enabled: true,
              release_evidence_allowed: false,
              runtime_activation_enabled: false,
              validated_default_write_enabled: false,
              numeric_values_allowed: false,
              guardrails: [
                "review_workflow_is_read_only",
                "numeric_values_blocked",
                "release_evidence_allowed_false",
              ],
            },
          },
          {
            id: literatureExtractionCandidate.candidate_uid,
            domain: "agronomy",
            title: `${literatureExtractionCandidate.metric_label}: ${literatureExtractionCandidate.raw_value} ${literatureExtractionCandidate.unit}`,
            subtitle: literatureExtractionCandidate.title,
            lane: "Literature extraction candidates",
            candidateType: literatureExtractionCandidate.candidate_type,
            reviewStatus: literatureExtractionCandidate.review_status,
            licenseStatus: "pending_review",
            allowedUse: "raw literature extraction candidate for human review only",
            blockedUse: "no validated defaults; no release evidence; no runtime activation; no promotion",
            humanReviewRequired: literatureExtractionCandidate.human_review_required,
            promotionEnabled: literatureExtractionCandidate.promotion_enabled,
            runtimeActivated: literatureExtractionCandidate.runtime_activation_enabled,
            validatedDefaultWriteEnabled: literatureExtractionCandidate.validated_default_write_enabled,
            sourceKind: literatureExtractionCandidate.source_kind,
            sourceRef: literatureExtractionCandidate.source_ref,
            note: `numeric candidate only; ${literatureExtractionCandidate.feedstock} / ${literatureExtractionCandidate.treatment} / ${literatureExtractionCandidate.condition_context}`,
            reviewPacketExportCandidateId: literatureExtractionCandidate.candidate_id,
            reviewDraft: {
              schema_version: "literature_extraction_review_draft_v1",
              review_draft_id: "LERD-TEST-001",
              tenant_id: 1,
              candidate_id: "LIT-AGR-GI-001",
              source_id: "A-BSF-007",
              reviewer_user_id: 1,
              review_intent: "approve_candidate_use_intent",
              reviewer_notes: "Reference Atlas reviewer draft intent only.",
              status: "draft_intent_recorded",
              source_review_packet_export_id: "literature-extraction-review-packet-export:LIT-AGR-GI-001:def123456789",
              source_review_packet_hash: "def123456789def123456789def123456789def123456789def123456789def1",
              candidate_snapshot: { review_status: "pending_review" },
              export_manifest: {
                candidate_id: "LIT-AGR-GI-001",
                export_policy: "response_only_no_file_write",
              },
              release_evidence_allowed: false,
              runtime_activation_enabled: false,
              validated_default_write_enabled: false,
              promotion_enabled: false,
              final_action_execution: false,
              side_effects: {
                candidate_status_update: false,
                file_written: false,
                runtime_activation: false,
                validated_default_write: false,
                species_db_write: false,
                feedstock_db_write: false,
                release_evidence_use: false,
                promotion: false,
                final_action_execution: false,
              },
              guardrails: ["candidate_status_remains_pending_review"],
              idempotency_key: "reference-atlas:LIT-AGR-GI-001:approve_candidate_use_intent",
              created_at: "2026-04-28T07:45:00+00:00",
              updated_at: "2026-04-28T07:45:00+00:00",
            },
          },
        ]}
        readiness={{
          schema_version: "external_source_schema_readiness_v1",
          status: "ready",
          schema_ready: true,
          source_catalog_ready: true,
          knowledge_coverage_ready: true,
          knowledge_coverage_percent: 100,
          source_metadata_coverage_percent: 100,
          business_knowledge_coverage_percent: 84.17,
          business_knowledge_coverage_groups: businessKnowledgeCoverageGroups,
          knowledge_coverage_domains: [],
          feedstock_dataset_candidate_count: 9,
          phase4a_domain_metadata_ready: true,
          phase4a_domain_candidate_counts: { lca: 6, tea: 6, compliance: 5, model_provider: 4, github_reference: 3 },
          phase4a_domain_expected_counts: { lca: 6, tea: 6, compliance: 5, model_provider: 4, github_reference: 3 },
          phase4a_domain_missing_counts: { lca: 0, tea: 0, compliance: 0, model_provider: 0, github_reference: 0 },
          reviewed_metadata_lane_ready: true,
          required_tables: [],
          missing_required_tables: [],
          blockers: [],
          guardrails: [],
        }}
        knowledgeBase={{
          schema_version: "reviewed_external_candidate_knowledge_base_v1",
          tenant_id: 1,
          status: "ready_for_review",
          schema_ready: true,
          source_catalog_ready: true,
          reviewed_metadata_lane_ready: true,
          knowledge_coverage_ready: true,
          knowledge_coverage_percent: 100,
          source_metadata_coverage_percent: 100,
          business_knowledge_coverage_percent: 84.17,
          business_knowledge_coverage_groups: businessKnowledgeCoverageGroups,
          knowledge_coverage_domains: [],
          supported_candidate_types: [],
          supported_candidate_domains: [],
          phase4a_domain_metadata_ready: true,
          phase4a_domain_candidate_counts: { lca: 6, tea: 6, compliance: 5, model_provider: 4, github_reference: 3 },
          phase4a_domain_expected_counts: { lca: 6, tea: 6, compliance: 5, model_provider: 4, github_reference: 3 },
          phase4a_domain_missing_counts: { lca: 0, tea: 0, compliance: 0, model_provider: 0, github_reference: 0 },
          reviewed_candidate_count: 1,
          reviewed_metadata_candidate_count: 1,
          pending_runtime_activation_count: 1,
          runtime_activated_count: 0,
          validated_default_write_enabled_count: 0,
          numeric_value_candidate_count: 0,
          candidate_types: { bsf_reviewed_metadata_candidate: 1 },
          candidate_domains: { bsf_metadata: 1 },
          blockers: [],
          guardrails: [
            "knowledge_base_summary_is_read_only",
            "reviewed_candidates_do_not_count_as_release_evidence",
          ],
        }}
        feedstockGuardrails={[
          "feedstock_dataset_candidates_are_metadata_only",
          "no_feedstock_db_writes",
        ]}
        literatureBulkExport={{
          schema_version: "literature_extraction_candidate_review_packet_bulk_export_v1",
          tenant_id: 1,
          export_format: "json",
          export_filename: "literature-extraction-review-packets.json",
          content_hash: "fed123456789fed123456789fed123456789fed123456789fed123456789fed1",
          export_manifest: {
            candidate_count: 1,
            export_policy: "response_only_no_file_write",
            source_packet_persistence: "persisted_candidate_records_only",
          },
          packet_exports: [],
          count: 1,
          metric_counts: { germination_index: 1 },
          side_effects: {
            file_written: false,
            runtime_activation: false,
            validated_default_write: false,
            species_db_write: false,
            feedstock_db_write: false,
            release_evidence_use: false,
            promotion: false,
            final_action_execution: false,
          },
          guardrails: ["literature_extraction_bulk_export_is_read_only"],
        }}
        literatureEvidenceChainReadiness={{
          schema_version: "literature_extraction_evidence_chain_readiness_v1",
          tenant_id: 1,
          chain_complete: true,
          candidate_count: 1,
          packet_export_ready: true,
          bulk_export_ready: true,
          review_draft_count: 1,
          comparison_ready: true,
          report_ready: true,
          auto_use_allowed: false,
          release_evidence_allowed: false,
          runtime_activation_enabled: false,
          validated_default_write_enabled: false,
          promotion_enabled: false,
          final_action_execution: false,
          side_effects: {
            candidate_status_update: false,
            file_written: false,
            runtime_activation: false,
            validated_default_write: false,
            species_db_write: false,
            feedstock_db_write: false,
            release_evidence_use: false,
            promotion: false,
            final_action_execution: false,
          },
          guardrails: ["literature_evidence_chain_readiness_is_read_only"],
          blocking_reason: null,
          readiness_notes: [],
        }}
      />,
    );

    expect(html).toContain("BSF domain candidates");
    expect(html).toContain("Feedstock domain candidates");
    expect(html).toContain("LCA domain candidates");
    expect(html).toContain("TEA domain candidates");
    expect(html).toContain("Compliance domain candidates");
    expect(html).toContain("Agronomy domain candidates");
    expect(html).toContain("Model domain candidates");
    expect(html).toContain("OSS domain candidates");
    expect(html).toContain("candidate_type: bsf_reviewed_metadata_candidate");
    expect(html).toContain("license_status: metadata_only");
    expect(html).toContain("allowed_use: candidate metadata only");
    expect(html).toContain("blocked_use: no validated defaults; no release evidence");
    expect(html).toContain("human_review_required: true");
    expect(html).toContain("promotion_enabled: false");
    expect(html).toContain("runtime_activated: false");
    expect(html).toContain("validated_default_write_enabled: false");
    expect(html).toContain("runtime inactive / defaults disabled");
    expect(html).toContain("Agronomy output candidates");
    expect(html).toContain("Literature extraction candidates");
    expect(html).toContain("Literature reviewer packet bulk export");
    expect(html).toContain("Literature evidence chain readiness");
    expect(html).toContain("chain_complete: true");
    expect(html).toContain("auto_use_allowed: false");
    expect(html).toContain("release/runtime/default/promotion/final-action: false");
    expect(html).toContain("export_filename: literature-extraction-review-packets.json");
    expect(html).toContain("candidate_count: 1");
    expect(html).toContain("source_packet_persistence: persisted_candidate_records_only");
    expect(html).toContain("Germination index: 85-102 %");
    expect(html).toContain("candidate_type: release_gate_candidate");
    expect(html).toContain("candidate_type: literature_extraction_candidate");
    expect(html).toContain("numeric candidate only");
    expect(html).toContain("source_ref: external_knowledge_candidates.germination_index");
    expect(html).toContain("source_ref: https://doi.org/10.3390/su151511526");
    expect(html).toContain("Reviewer workflow");
    expect(html).toContain("review_packet_id: AGR-GERMINATION-INDEX-REVIEW-PACKET");
    expect(html).toContain("review_state: pending_review");
    expect(html).toContain("source_packet_persistence: read_model_only");
    expect(html).toContain("Response-only reviewer packet export");
    expect(html).toContain("export_filename: AGR-GERMINATION-INDEX-REVIEW-PACKET.json");
    expect(html).toContain("export_filename: LIT-AGR-GI-001-literature-extraction-review-packet.json");
    expect(html).toContain("export_policy: response_only_no_file_write");
    expect(html).toContain("candidate_id: LIT-AGR-GI-001");
    expect(html).toContain("Reviewer draft intent");
    expect(html).toContain("review_draft_id: LERD-TEST-001");
    expect(html).toContain("Reviewer draft revision comparison");
    expect(html).toContain("comparison_policy: response_only_no_file_write");
    expect(html).toContain("report_policy: response_only_no_file_write");
    expect(html).toContain("revision_hash: abc123456789");
    expect(html).toContain("changed_field_filter: none");
    expect(html).toContain("changed_fields: none");
    expect(html).toContain("packet_hash_matches: true");
    expect(html).toContain("candidate_status_update: false");
    expect(html).toContain("release_evidence_use: false");
    expect(html).toContain("promotion: false");
    expect(html).toContain("file_written: false");
    expect(html).toContain("numeric_value_extraction: false");
    expect(html).toContain("final_action_execution: false");
    expect(html).toContain("allowed_review_actions: approve_metadata, request_license_clearance, reject");
    expect(html).toContain("release_evidence_allowed: false");
    expect(html).toContain("numeric_values_allowed: false");
    expect(html).toContain("feedstock_dataset_candidates_are_metadata_only");
    expect(html).toContain("reviewed_candidates_do_not_count_as_release_evidence");
  });

  it("renders reviewed candidate activation previews as read-only audit scope", () => {
    hookMocks.useReviewedExternalCandidateActivationPreview.mockReturnValue(
      queryResult({
        schema_version: "reviewed_external_candidate_activation_preview_v1",
        tenant_id: 1,
        candidate: reviewedExternalCandidate,
        activation_scope: {
          tenant_id: 1,
          tenant_scoped: true,
          candidate_id: "REC-BSF-CARD-002",
          candidate_type: "lca_factor_candidate",
          candidate_domain: "lca",
          candidate_key: "lca_factor_candidate:BSF-CARD-002",
          scope_key: "tenant:1:lca_factor_candidate:lca_factor_candidate:BSF-CARD-002",
          runtime_paths: ["lca.factor_runtime"],
          source_lineage: {
            source_id: "A-BSF-002",
            source_kind: "peer_reviewed_literature",
            source_ref: "10.1016/j.wasman.2020.07.050",
            reviewer: "Dr. Reviewer",
            reviewed_at: "2026-04-27T00:00:00Z",
            review_status: "approved_for_candidate_use",
          },
        },
        active_overlay_state: {
          scope_key: "tenant:1:lca_factor_candidate:lca_factor_candidate:BSF-CARD-002",
          active_registry_patch_id: null,
          active_activation_id: null,
          active_registry_version: null,
          event_count: 0,
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
          final_action_execution: false,
        },
        guardrails: ["activation_preview_is_read_only"],
      }),
    );
    hookMocks.useReviewedExternalCandidateRuntimeReadiness.mockReturnValue(
      queryResult({
        schema_version: "reviewed_external_candidate_runtime_readiness_v1",
        tenant_id: 1,
        candidate: reviewedExternalCandidate,
        activation_scope: {
          tenant_id: 1,
          tenant_scoped: true,
          candidate_id: "REC-BSF-CARD-002",
          candidate_type: "lca_factor_candidate",
          candidate_domain: "lca",
          candidate_key: "lca_factor_candidate:BSF-CARD-002",
          scope_key: "tenant:1:lca_factor_candidate:lca_factor_candidate:BSF-CARD-002",
          runtime_paths: ["lca.factor_runtime"],
        },
        active_overlay_state: {
          scope_key: "tenant:1:lca_factor_candidate:lca_factor_candidate:BSF-CARD-002",
          active_registry_patch_id: null,
          active_activation_id: null,
          active_registry_version: null,
          event_count: 0,
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
          active_activation_id: null,
          active_registry_patch_id: null,
        },
        side_effects: {
          runtime_activation: false,
          runtime_rollback: false,
          validated_default_write: false,
          species_db_write: false,
          feedstock_db_write: false,
          final_action_execution: false,
        },
        guardrails: ["runtime_readiness_is_read_only", "rollback_required"],
      }),
    );
    hookMocks.useReviewedExternalCandidateRollbackPreview.mockReturnValue(
      queryResult({
        schema_version: "reviewed_external_candidate_rollback_preview_v1",
        tenant_id: 1,
        candidate: reviewedExternalCandidate,
        activation_scope: {
          tenant_id: 1,
          tenant_scoped: true,
          candidate_id: "REC-BSF-CARD-002",
          candidate_type: "lca_factor_candidate",
          candidate_domain: "lca",
          candidate_key: "lca_factor_candidate:BSF-CARD-002",
          scope_key: "tenant:1:lca_factor_candidate:lca_factor_candidate:BSF-CARD-002",
          runtime_paths: ["lca.factor_runtime"],
        },
        active_overlay_state: {
          active_registry_patch_id: null,
          active_activation_id: null,
          active_registry_version: null,
          activation_required_before_runtime_use: true,
        },
        rollback_contract: {
          rollback_required: true,
          rollback_execution_endpoint_enabled: false,
          rollback_target_required: false,
          active_activation_id: null,
          active_registry_patch_id: null,
        },
        rollback_audit_packet: {
          tenant_id: 1,
          candidate_id: "REC-BSF-CARD-002",
          candidate_type: "lca_factor_candidate",
          candidate_key: "lca_factor_candidate:BSF-CARD-002",
          scope_key: "tenant:1:lca_factor_candidate:lca_factor_candidate:BSF-CARD-002",
          rollback_target_available: false,
          rollback_execution_endpoint_enabled: false,
          required_attestations: ["operator_attestation", "rollback_reason", "idempotency_key"],
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
          species_db_write: false,
          feedstock_db_write: false,
          final_action_execution: false,
        },
        guardrails: ["rollback_preview_is_read_only", "rollback_requires_separate_audit_execution"],
      }),
    );

    const html = renderToStaticMarkup(
      <ReviewedExternalCandidateCard candidate={reviewedExternalCandidate} />,
    );

    expect(hookMocks.useReviewedExternalCandidateActivationPreview).toHaveBeenCalledWith("REC-BSF-CARD-002");
    expect(hookMocks.useReviewedExternalCandidateRuntimeReadiness).toHaveBeenCalledWith("REC-BSF-CARD-002");
    expect(hookMocks.useReviewedExternalCandidateRollbackPreview).toHaveBeenCalledWith("REC-BSF-CARD-002");
    expect(html).toContain("Operator evidence summary");
    expect(html).toContain("operator evidence ready / execution blocked");
    expect(html).toContain("activation_execution");
    expect(html).toContain("blocked");
    expect(html).toContain("runtime_read_path");
    expect(html).toContain("enabled");
    expect(html).toContain("runtime_payload_readable");
    expect(html).toContain("rollback_execution");
    expect(html).toContain("rollback_target_available");
    expect(html).toContain("release_decision");
    expect(html).toContain("review_required");
    expect(html).toContain("release_evidence_allowed: false");
    expect(html).toContain("side_effects_blocked: true");
    expect(html).toContain("Activation preview (read only)");
    expect(html).toContain("tenant_scoped");
    expect(html).toContain("candidate_type");
    expect(html).toContain("lca_factor_candidate");
    expect(html).toContain("candidate_key");
    expect(html).toContain("lca_factor_candidate:BSF-CARD-002");
    expect(html).toContain("scope_key");
    expect(html).toContain("tenant:1:lca_factor_candidate:lca_factor_candidate:BSF-CARD-002");
    expect(html).toContain("runtime_paths");
    expect(html).toContain("lca.factor_runtime");
    expect(html).toContain("runtime inactive / defaults disabled");
    expect(html).toContain("can_execute_activation: false");
    expect(html).toContain("runtime_overlay_preview_only");
    expect(html).toContain("activation_audit_required");
    expect(html).toContain("activation_execution_endpoint_enabled");
    expect(html).toContain("rollback_required: true");
    expect(html).toContain("validated_default_write_enabled");
    expect(html).toContain("activation_required_before_runtime_use: true");
    expect(html).toContain("source_id: A-BSF-002");
    expect(html).toContain("runtime_activation: false");
    expect(html).toContain("final_action_execution: false");
    expect(html).toContain("activation_preview_is_read_only");
    expect(html).toContain("Runtime readiness (read only)");
    expect(html).toContain("runtime payload blocked");
    expect(html).toContain("runtime_read_path_enabled");
    expect(html).toContain("can_read_runtime_payload");
    expect(html).toContain("rollback_endpoint_enabled: false");
    expect(html).toContain("rollback_target_required");
    expect(html).toContain("runtime_rollback: false");
    expect(html).toContain("runtime_readiness_is_read_only");
    expect(html).toContain("Rollback preview (read only)");
    expect(html).toContain("rollback target unavailable");
    expect(html).toContain("can_execute_rollback: false");
    expect(html).toContain("rollback_preview_only: true");
    expect(html).toContain("rollback_execution_endpoint_enabled");
    expect(html).toContain("no_active_runtime_activation_to_rollback");
    expect(html).toContain("operator_attestation");
    expect(html).toContain("rollback_preview_is_read_only");
    expect(html).toContain("rollback_requires_separate_audit_execution");
    expect(html).not.toContain("Execute activation");
    expect(html).not.toContain("Execute rollback");
  });

  it("keeps operator evidence pending while runtime readiness has not returned", () => {
    hookMocks.useReviewedExternalCandidateActivationPreview.mockReturnValue(
      queryResult({
        schema_version: "reviewed_external_candidate_activation_preview_v1",
        tenant_id: 1,
        candidate: reviewedExternalCandidate,
        activation_scope: {
          tenant_id: 1,
          tenant_scoped: true,
          candidate_type: "lca_factor_candidate",
          candidate_key: "lca_factor_candidate:BSF-CARD-002",
          runtime_paths: ["lca.factor_runtime"],
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
      }),
    );
    hookMocks.useReviewedExternalCandidateRuntimeReadiness.mockReturnValue(queryResult(undefined));
    hookMocks.useReviewedExternalCandidateRollbackPreview.mockReturnValue(
      queryResult({
        schema_version: "reviewed_external_candidate_rollback_preview_v1",
        tenant_id: 1,
        candidate: reviewedExternalCandidate,
        activation_scope: {
          tenant_id: 1,
          tenant_scoped: true,
          candidate_type: "lca_factor_candidate",
          candidate_key: "lca_factor_candidate:BSF-CARD-002",
          runtime_paths: ["lca.factor_runtime"],
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
          candidate_id: "REC-BSF-CARD-002",
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
      }),
    );

    const html = renderToStaticMarkup(
      <ReviewedExternalCandidateCard candidate={reviewedExternalCandidate} />,
    );

    expect(html).toContain("Operator evidence summary");
    expect(html).toContain("operator evidence pending");
    expect(html).toContain("runtime_read_path");
    expect(html).toContain("pending");
    expect(html).toContain("Runtime readiness pending");
    expect(html).not.toContain("operator evidence ready / execution blocked");
    expect(html).not.toContain("Execute activation");
    expect(html).not.toContain("Execute rollback");
  });

  it("renders review-card queue actions as a read-only approval summary", () => {
    const html = renderToStaticMarkup(
      <ExternalReviewCardQueueItem
        candidateGenerated={false}
        onResolve={vi.fn()}
        card={{
          tenant_id: 1,
          card_id: "BSF-CARD-004",
          shortlist_id: "BSF-LIT-004",
          source_id: "A-BSF-004",
          doi: "10.1016/j.wasman.2020.07.050",
          source_url: "https://example.test/source",
          title: "Metadata-only source review",
          review_status: "extracted_metadata",
          review_action: "approve_metadata",
          reviewer: "Dr. Reviewer",
          reviewer_user_id: 7,
          reviewed_at: "2026-04-27T00:00:00Z",
          license_status: "metadata_only",
          evidence_source_kind: "peer_reviewed_literature",
          ingestion_mode: "manual_review_first",
          human_review_required: true,
          extracted_numeric_values_allowed: false,
          boundary_condition_required: true,
          allowed_use: "review workflow metadata only",
          blocked_use: "no validated defaults; no release evidence; no runtime activation",
          next_action: "Review action persisted without candidate creation.",
          boundary_metadata: {},
          raw_payload: {},
          created_at: "2026-04-27T00:00:00Z",
          updated_at: "2026-04-27T00:00:00Z",
          promotion_enabled: false,
          runtime_activated: false,
          validated_default_write_enabled: false,
        }}
      />,
    );

    expect(html).toContain("approve_metadata");
    expect(html).toContain("extracted_metadata");
    expect(html).toContain("reviewer: Dr. Reviewer");
    expect(html).toContain("license_status");
    expect(html).toContain("allowed_use: review workflow metadata only");
    expect(html).toContain("blocked_use: no validated defaults; no release evidence; no runtime activation");
    expect(html).toContain("candidate_generated: false");
    expect(html).toContain("runtime_active: false");
    expect(html).toContain("Approve metadata");
    expect(html).toContain("Request license clearance");
    expect(html).toContain("Reject");
    expect(html).toContain("Approve for candidate use");
    expect(html).toContain("These actions only resolve review cards");
  });

  it("renders external source schema readiness as a read-only diagnostic", () => {
    const html = renderToStaticMarkup(
      <ExternalSourceSchemaReadinessStrip
        readiness={{
          schema_version: "external_source_schema_readiness_v1",
          status: "ready",
          schema_ready: true,
          source_catalog_ready: true,
          feedstock_dataset_candidate_count: 9,
          phase4a_domain_metadata_ready: true,
          phase4a_domain_candidate_counts: { lca: 6, tea: 6, compliance: 5, model_provider: 4, github_reference: 3 },
          phase4a_domain_expected_counts: { lca: 6, tea: 6, compliance: 5, model_provider: 4, github_reference: 3 },
          phase4a_domain_missing_counts: { lca: 0, tea: 0, compliance: 0, model_provider: 0, github_reference: 0 },
          reviewed_metadata_lane_ready: true,
          required_tables: [
            { table_name: "external_source_records", present: true, row_count: 70 },
            { table_name: "external_source_review_cards", present: true, row_count: 8 },
          ],
          missing_required_tables: [],
          blockers: [],
          guardrails: [
            "schema_readiness_only",
            "no_table_creation",
            "no_seed_mutation",
            "no_validated_default_writes",
          ],
        }}
        isLoading={false}
        isError={false}
      />,
    );

    expect(html).toContain("External source schema readiness");
    expect(html).toContain("9 feedstock dataset candidates");
    expect(html).toContain("phase4a_domain_metadata_ready: true");
    expect(html).toContain("lca: 6/6");
    expect(html).toContain("external_source_records: 70");
    expect(html).toContain("no_table_creation");
    expect(html).toContain("no_validated_default_writes");
  });
});
