import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockClient } = vi.hoisted(() => ({
  mockClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("@/api/client", () => ({
  default: mockClient,
}));

import { bosApi } from "@/api/bosApi";

describe("bosApi adapter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("posts supervisor observations to the supervisor endpoint", async () => {
    mockClient.post.mockResolvedValueOnce({
      data: {
        id: 12,
        signal_batch_id: 12,
        c_signal_hat: 0.61,
        dc_dt_hat: 0.02,
        confidence: 0.88,
        observed_at: "2026-04-15T12:00:00Z",
        missing_channels: [],
        channels_used: ["uv254", "od280", "do", "ph"],
        information_loss: 0.12,
        observability_score: 1,
        negative_slope_streak: 0,
        trigger_reason: null,
        expected_handover: "2026-04-15T14:00:00Z",
        mechanistic_context: null,
      },
    });

    const result = await bosApi.evaluateSupervisor(12, {
      uv254: 2.4,
      od280: 2.0,
      do: 5.1,
      ph: 7.1,
      elapsed_hours: 8,
    });

    expect(mockClient.post).toHaveBeenCalledWith("/signals/12/supervisor", {
      uv254: 2.4,
      od280: 2.0,
      do: 5.1,
      ph: 7.1,
      elapsed_hours: 8,
    });
    expect(result).toMatchObject({
      signal_batch_id: 12,
      c_signal_hat: 0.61,
      channels_used: ["uv254", "od280", "do", "ph"],
    });
  });

  it("posts handover observations to the handover recommendation endpoint", async () => {
    mockClient.post.mockResolvedValueOnce({
      data: {
        signal_batch_id: 15,
        recommended_handover: true,
        trigger_reason: "negative_slope_persistence",
        expected_freshness_window_hours: 1.4,
        c_signal_hat: 0.44,
        dc_dt_hat: -0.07,
        confidence: 0.81,
        expected_handover: "2026-04-15T13:30:00Z",
        confidence_threshold: 0.8,
        negative_slope_persistence: 3,
        observability_required: true,
        missing_channels: [],
        channels_used: ["uv254", "od280", "do", "ph"],
        information_loss: 0.18,
        observability_score: 1,
        mechanistic_context: null,
      },
    });

    const result = await bosApi.getHandoverRecommendation(15, {
      uv254: 1.2,
      od280: 1.0,
      do: 2.5,
      ph: 6.9,
      elapsed_hours: 10,
      previous_c_signal_hat: 0.52,
      previous_elapsed_hours: 9,
      previous_dc_dt_hat: -0.04,
      previous_negative_slope_streak: 2,
    });

    expect(mockClient.post).toHaveBeenCalledWith("/signals/15/handover-recommendation", {
      uv254: 1.2,
      od280: 1.0,
      do: 2.5,
      ph: 6.9,
      elapsed_hours: 10,
      previous_c_signal_hat: 0.52,
      previous_elapsed_hours: 9,
      previous_dc_dt_hat: -0.04,
      previous_negative_slope_streak: 2,
    });
    expect(result).toMatchObject({
      signal_batch_id: 15,
      recommended_handover: true,
      trigger_reason: "negative_slope_persistence",
    });
  });

  it("fetches the native model catalog with an optional batch id", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        version: "BOS-1.0",
        catalog_version: "BOS-NATIVE-2026.04",
        verified_on: "2026-04-15",
        models: [{ key: "yolo11_dsconv" }],
        compositions: [],
        recommendations: [],
        rollout: [],
      },
    });

    const result = await bosApi.listNativeModels(88);

    expect(mockClient.get).toHaveBeenCalledWith("/native-models", {
      params: { batch_id: 88 },
    });
    expect(result.catalog_version).toBe("BOS-NATIVE-2026.04");
    expect(result.models[0]?.key).toBe("yolo11_dsconv");
  });

  it("fetches native runtime status", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        version: "BOS-1.0",
        enabled: true,
        cache_dir: "C:/tmp/native-models",
        summary: { total_models: 5 },
        runtimes: [{ key: "timer_s1", runtime_state: "remote_reference_contract_only" }],
      },
    });

    const result = await bosApi.getNativeModelRuntimeStatus();

    expect(mockClient.get).toHaveBeenCalledWith("/native-models/runtime");
    expect(result.enabled).toBe(true);
    expect(result.runtimes[0]?.key).toBe("timer_s1");
  });

  it("fetches native download plan", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: [
        {
          version: "BOS-1.0",
          model_key: "chronos_bolt",
          supported: true,
          source_kind: "huggingface_snapshot",
          source_reference: "autogluon/chronos-bolt-small",
          target_path: "C:/tmp/native-models/chronos-bolt",
          notes: [],
        },
      ],
    });

    const result = await bosApi.getNativeModelDownloadPlan("chronos_bolt");

    expect(mockClient.get).toHaveBeenCalledWith("/native-models/download-plan", {
      params: { model_key: "chronos_bolt" },
    });
    expect(result[0]?.model_key).toBe("chronos_bolt");
  });

  it("posts a native model download request", async () => {
    mockClient.post.mockResolvedValueOnce({
      data: {
        version: "BOS-1.0",
        model_key: "chronos_bolt",
        downloaded: true,
        runtime_state: "artifact_detected_contract_only",
        target_path: "C:/tmp/native-models/chronos-bolt",
        source_reference: "autogluon/chronos-bolt-small",
        detail: "ok",
        extracted_path: "C:/tmp/native-models/chronos-bolt",
      },
    });

    const result = await bosApi.downloadNativeModel("chronos_bolt");

    expect(mockClient.post).toHaveBeenCalledWith("/native-models/chronos_bolt/download");
    expect(result.downloaded).toBe(true);
  });

  it("posts a native inference request", async () => {
    mockClient.post.mockResolvedValueOnce({
      data: {
        version: "BOS-1.0",
        model_key: "chronos_bolt",
        batch_id: 8,
        ready: false,
        runtime_state: "remote_reference_contract_only",
        execution_mode: "bos_fallback_projection",
        payload_echo: { sensor_history: [1, 2, 3] },
        result: { forecast: [4, 5, 6] },
        warnings: ["fallback"],
        next_steps: [],
      },
    });

    const result = await bosApi.inferNativeModel({
      model_key: "chronos_bolt",
      batch_id: 8,
      dry_run: false,
      payload: { sensor_history: [1, 2, 3] },
    });

    expect(mockClient.post).toHaveBeenCalledWith("/native-models/infer", {
      model_key: "chronos_bolt",
      batch_id: 8,
      dry_run: false,
      payload: { sensor_history: [1, 2, 3] },
    });
    expect(result.execution_mode).toBe("bos_fallback_projection");
  });

  it("fetches native model run artifacts", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: [
        {
          model_key: "chronos_bolt",
          execution_mode: "chronos_bolt_live",
          recorded_at: "2026-04-16T00:00:00Z",
          artifact_path: "C:/tmp/native-models/runs/chronos_bolt/run.json",
          payload_echo: {},
          result: { forecast: [1, 2, 3] },
          warnings: [],
        },
      ],
    });

    const result = await bosApi.listNativeModelRuns("chronos_bolt", undefined, 5);

    expect(mockClient.get).toHaveBeenCalledWith("/native-models/runs", {
      params: { limit: 5, model_key: "chronos_bolt" },
    });
    expect(result[0]?.execution_mode).toBe("chronos_bolt_live");
  });

  it("fetches native model run artifacts filtered by batch", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: [],
    });

    await bosApi.listNativeModelRuns(undefined, 42, 8);

    expect(mockClient.get).toHaveBeenCalledWith("/native-models/runs", {
      params: { limit: 8, batch_id: 42 },
    });
  });

  it("posts reference ingestion parse requests as form data", async () => {
    mockClient.post.mockResolvedValueOnce({
      data: {
        id: "refing_123",
        source_title: "Core relay",
        status: "staged",
      },
    });
    const file = new File(["%PDF-1.4"], "core-relay.pdf", { type: "application/pdf" });

    const result = await bosApi.parseReferenceDocument({
      file,
      source_title: "Core relay",
      source_type: "pdf",
      source_owner: "EPA",
      license_note: "Review before customer-facing use",
      region: "US",
      units: { moisture: "% wet basis", cn_ratio: "dimensionless" },
      ingestion_mode: "manual_review_first",
      human_review_required: true,
    });

    expect(mockClient.post).toHaveBeenCalledWith(
      "/references/ingestion/parse",
      expect.any(FormData),
      {
        headers: { "Content-Type": "multipart/form-data" },
      },
    );
    const formData = mockClient.post.mock.calls[0]?.[1] as FormData;
    expect(formData.get("source_title")).toBe("Core relay");
    expect(formData.get("source_type")).toBe("pdf");
    expect(formData.get("source_owner")).toBe("EPA");
    expect(formData.get("license_note")).toBe("Review before customer-facing use");
    expect(formData.get("region")).toBe("US");
    expect(formData.get("units_json")).toBe(JSON.stringify({ moisture: "% wet basis", cn_ratio: "dimensionless" }));
    expect(formData.get("ingestion_mode")).toBe("manual_review_first");
    expect(formData.get("human_review_required")).toBe("true");
    expect(result.id).toBe("refing_123");
  });

  it("fetches review-gated candidate seed catalogs", async () => {
    mockClient.get
      .mockResolvedValueOnce({
        data: {
          candidates: [
            {
              code: "BSF",
              review_status: "pending_review",
              human_review_required: true,
            },
          ],
          count: 1,
          validated_species_codes: ["BSF", "MW", "PB"],
          candidate_codes: ["BSF"],
        },
      })
      .mockResolvedValueOnce({
        data: {
          candidates: [
            {
              key: "mixed_food_waste",
              review_status: "pending_review",
              human_review_required: true,
            },
          ],
          count: 1,
          validated_feedstock_keys: ["distillers_grains"],
          candidate_keys: ["mixed_food_waste"],
        },
      });

    const bioexecutors = await bosApi.listBioexecutorCandidates();
    const feedstocks = await bosApi.listFeedstockCandidates();

    expect(mockClient.get).toHaveBeenNthCalledWith(1, "/species/candidates");
    expect(mockClient.get).toHaveBeenNthCalledWith(2, "/feedstocks/candidates");
    expect(bioexecutors.candidates[0]?.review_status).toBe("pending_review");
    expect(feedstocks.candidates[0]?.human_review_required).toBe(true);
  });

  it("fetches reviewed external source candidate read models", async () => {
    mockClient.get
      .mockResolvedValueOnce({
        data: {
          items: [{ source_id: "A-BSF-002", evidence_source_kind: "peer_reviewed_literature" }],
          count: 1,
          guardrails: ["no_runtime_activation"],
        },
      })
      .mockResolvedValueOnce({
        data: {
          schema_version: "external_source_procurement_summary_v1",
          source_count: 70,
          source_kind_counts: { peer_reviewed_literature: 8 },
          ingestion_mode_counts: { metadata_only: 62, manual_review_first: 8 },
          bos_module_counts: { reference_atlas: 8 },
          review_required_count: 8,
          metadata_only_count: 62,
          manual_review_first_count: 8,
          other_ingestion_mode_count: 0,
          commercial_or_restricted_count: 0,
          guardrails: ["source_procurement_summary_is_read_only"],
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: [{ card_id: "BSF-CARD-001", review_status: "pending_review" }],
          count: 1,
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: [{ extraction_id: "EXT-BSF-CARD-001", numeric_values_included: false }],
          count: 1,
          guardrails: ["numeric_values_blocked_for_bsf_metadata_lane"],
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              candidate_id: "REC-BSF-CARD-001",
              runtime_activated: false,
              validated_default_write_enabled: false,
              candidate_payload: { payload_version: "bsf-reviewed-metadata-v1" },
            },
          ],
          count: 1,
          guardrails: ["runtime_activated_false"],
        },
      })
      .mockResolvedValueOnce({
        data: {
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
          guardrails: ["summary_is_read_only"],
        },
      });

    const sources = await bosApi.listExternalSources();
    const procurementSummary = await bosApi.getExternalSourceProcurementSummary();
    const cards = await bosApi.listExternalSourceReviewCards();
    const extractions = await bosApi.listExternalSourceExtractions();
    const reviewed = await bosApi.listReviewedExternalCandidates();
    const summary = await bosApi.getReviewedExternalCandidateSummary();

    expect(mockClient.get).toHaveBeenNthCalledWith(1, "/external-sources/catalog");
    expect(mockClient.get).toHaveBeenNthCalledWith(2, "/external-sources/catalog/summary");
    expect(mockClient.get).toHaveBeenNthCalledWith(3, "/external-sources/review-cards");
    expect(mockClient.get).toHaveBeenNthCalledWith(4, "/external-sources/extractions");
    expect(mockClient.get).toHaveBeenNthCalledWith(5, "/external-sources/reviewed-candidates");
    expect(mockClient.get).toHaveBeenNthCalledWith(6, "/external-sources/reviewed-candidates/summary");
    expect(sources.items[0]?.source_id).toBe("A-BSF-002");
    expect(procurementSummary.review_required_count).toBe(8);
    expect(cards.items[0]?.review_status).toBe("pending_review");
    expect(extractions.items[0]?.numeric_values_included).toBe(false);
    expect(reviewed.items[0]?.runtime_activated).toBe(false);
    expect(reviewed.items[0]?.candidate_payload).toMatchObject({ payload_version: "bsf-reviewed-metadata-v1" });
    expect(summary.reviewed_metadata_candidate_count).toBe(1);
    expect(summary.runtime_activated_count).toBe(0);
  });

  it("posts explicit external source review actions through the review workflow endpoint", async () => {
    mockClient.post.mockResolvedValueOnce({
      data: {
        review_card: {
          card_id: "BSF-CARD-004",
          review_action: "approve_metadata",
          review_status: "extracted_metadata",
          runtime_activated: false,
          validated_default_write_enabled: false,
        },
        reviewed_candidate: null,
        created_reviewed_candidate: false,
        guardrails: ["approved_for_candidate_use_is_not_runtime_activation"],
      },
    });

    const payload = {
      review_action: "approve_metadata" as const,
      reviewer: "Dr. Reviewer",
      reviewed_at: "2026-04-27T00:00:00Z",
      license_status: "metadata_only",
      boundary_condition: "Reviewed metadata boundary only.",
      allowed_use: "review workflow metadata only",
      blocked_use: "no validated defaults; no release evidence; no runtime activation",
    };
    const result = await bosApi.resolveExternalSourceReviewCard("BSF-CARD-004", payload);

    expect(mockClient.post).toHaveBeenCalledWith("/external-sources/review-cards/BSF-CARD-004/resolve", payload);
    expect(result.review_card.review_action).toBe("approve_metadata");
    expect(result.created_reviewed_candidate).toBe(false);
    expect(result.reviewed_candidate).toBeNull();
  });

  it("fills Phase 4A reviewed candidates through the gated backend endpoint", async () => {
    mockClient.post.mockResolvedValueOnce({
      data: {
        schema_version: "external_source_phase4a_reviewed_candidate_fill_v1",
        source_count: 24,
        reviewed_candidate_count: 24,
        created_reviewed_candidate_count: 24,
        updated_reviewed_candidate_count: 0,
        reviewed_candidate_ids: ["REC-PHASE4A-C-LCA-010"],
        candidate_types: { lca_factor_candidate: 6 },
        candidate_domains: { lca: 6 },
        runtime_activated_count: 0,
        validated_default_write_enabled_count: 0,
        numeric_value_candidate_count: 0,
        guardrails: ["no_runtime_activation", "no_species_db_writes"],
      },
    });

    const result = await bosApi.fillPhase4AReviewedCandidates();

    expect(mockClient.post).toHaveBeenCalledWith("/external-sources/phase4a/reviewed-candidates/fill");
    expect(result.reviewed_candidate_count).toBe(24);
    expect(result.runtime_activated_count).toBe(0);
    expect(result.guardrails).toContain("no_species_db_writes");
  });

  it("fetches reviewed candidate activation previews as read-only audit contracts", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "reviewed_external_candidate_activation_preview_v1",
        tenant_id: 1,
        candidate: {
          candidate_id: "REC-BSF-CARD-002",
          candidate_type: "lca_factor_candidate",
          runtime_activated: false,
          validated_default_write_enabled: false,
          candidate_payload: { numeric_values_included: false },
        },
        activation_scope: {
          tenant_id: 1,
          tenant_scoped: true,
          candidate_id: "REC-BSF-CARD-002",
          candidate_type: "lca_factor_candidate",
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
      },
    });

    const result = await bosApi.getReviewedExternalCandidateActivationPreview("REC-BSF-CARD-002");

    expect(mockClient.get).toHaveBeenCalledWith(
      "/external-sources/reviewed-candidates/REC-BSF-CARD-002/activation-preview",
    );
    expect(result.can_execute_activation).toBe(false);
    expect(result.runtime_overlay_preview_only).toBe(true);
    expect(result.activation_scope).toMatchObject({
      tenant_scoped: true,
      candidate_key: "lca_factor_candidate:BSF-CARD-002",
      runtime_paths: ["lca.factor_runtime"],
      source_lineage: {
        source_id: "A-BSF-002",
        review_status: "approved_for_candidate_use",
      },
    });
    expect(result.active_overlay_state).toMatchObject({
      event_count: 0,
      activation_required_before_runtime_use: true,
    });
    expect(result.activation_audit_contract).toMatchObject({
      activation_audit_id_required: true,
      activation_execution_endpoint_enabled: false,
    });
    expect(result.side_effects).toMatchObject({
      runtime_activation: false,
      validated_default_write: false,
      final_action_execution: false,
    });
  });

  it("fetches reviewed candidate runtime readiness as a read-only rollback-gated path", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "reviewed_external_candidate_runtime_readiness_v1",
        tenant_id: 1,
        candidate: {
          candidate_id: "REC-BSF-CARD-002",
          candidate_type: "lca_factor_candidate",
          runtime_activated: false,
          validated_default_write_enabled: false,
          candidate_payload: { numeric_values_included: false },
        },
        activation_scope: {
          tenant_id: 1,
          tenant_scoped: true,
          candidate_id: "REC-BSF-CARD-002",
          candidate_type: "lca_factor_candidate",
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
      },
    });

    const result = await bosApi.getReviewedExternalCandidateRuntimeReadiness("REC-BSF-CARD-002");

    expect(mockClient.get).toHaveBeenCalledWith(
      "/external-sources/reviewed-candidates/REC-BSF-CARD-002/runtime-readiness",
    );
    expect(result.runtime_read_path_enabled).toBe(true);
    expect(result.can_read_runtime_payload).toBe(false);
    expect(result.rollback_required).toBe(true);
    expect(result.rollback_contract).toMatchObject({
      rollback_execution_endpoint_enabled: false,
      rollback_target_required: false,
    });
    expect(result.side_effects).toMatchObject({
      runtime_activation: false,
      runtime_rollback: false,
      final_action_execution: false,
    });
  });

  it("fetches reviewed candidate rollback previews without execution", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "reviewed_external_candidate_rollback_preview_v1",
        tenant_id: 1,
        candidate: {
          candidate_id: "REC-BSF-CARD-002",
          candidate_type: "lca_factor_candidate",
          runtime_activated: false,
          validated_default_write_enabled: false,
          candidate_payload: { numeric_values_included: false },
        },
        activation_scope: {
          tenant_id: 1,
          tenant_scoped: true,
          candidate_id: "REC-BSF-CARD-002",
          candidate_type: "lca_factor_candidate",
          candidate_key: "lca_factor_candidate:BSF-CARD-002",
          scope_key: "tenant:1:lca_factor_candidate:lca_factor_candidate:BSF-CARD-002",
          runtime_paths: ["lca.factor_runtime"],
        },
        active_overlay_state: {
          active_activation_id: null,
          active_registry_patch_id: null,
          activation_required_before_runtime_use: true,
        },
        rollback_contract: {
          rollback_required: true,
          rollback_execution_endpoint_enabled: false,
          rollback_target_required: false,
        },
        rollback_audit_packet: {
          rollback_target_available: false,
          rollback_execution_endpoint_enabled: false,
          blocked_until: ["no_active_runtime_activation_to_rollback"],
          required_attestations: ["operator_attestation", "rollback_reason"],
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
      },
    });

    const result = await bosApi.getReviewedExternalCandidateRollbackPreview("REC-BSF-CARD-002");

    expect(mockClient.get).toHaveBeenCalledWith(
      "/external-sources/reviewed-candidates/REC-BSF-CARD-002/rollback-preview",
    );
    expect(result.rollback_target_available).toBe(false);
    expect(result.can_execute_rollback).toBe(false);
    expect(result.rollback_preview_only).toBe(true);
    expect(result.rollback_blockers).toContain("no_active_runtime_activation_to_rollback");
    expect(result.rollback_audit_packet).toMatchObject({
      rollback_execution_endpoint_enabled: false,
      rollback_target_available: false,
    });
    expect(result.side_effects).toMatchObject({
      runtime_rollback: false,
      final_action_execution: false,
    });
  });

  it("fetches feedstock public dataset candidates as metadata-only read models", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            candidate_uid: "FDS-B-FEED-001",
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
            waste_proxy_warning: "Food/feed composition source, not a validated waste-stream default.",
            review_status: "pending_review",
            human_review_required: true,
            numeric_values_included: false,
            runtime_activated: false,
            validated_default_write_enabled: false,
            next_action: "Human reviewer must map source rows to BOS feedstock candidates before extraction.",
          },
        ],
        count: 1,
        guardrails: [
          "feedstock_dataset_candidates_are_metadata_only",
          "no_feedstock_db_writes",
          "runtime_activation_blocked",
        ],
      },
    });

    const result = await bosApi.listFeedstockDatasetCandidates();

    expect(mockClient.get).toHaveBeenCalledWith("/external-sources/feedstock-dataset-candidates");
    expect(result.items[0]).toMatchObject({
      candidate_type: "feedstock_dataset_candidate",
      review_status: "pending_review",
      source_id: "B-FEED-001",
      numeric_values_included: false,
      runtime_activated: false,
      validated_default_write_enabled: false,
    });
    expect(result.guardrails).toContain("no_feedstock_db_writes");
    expect(result.guardrails).toContain("feedstock_dataset_candidates_are_metadata_only");
  });

  it("fetches reviewed candidate knowledge base readiness without release-evidence activation", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "reviewed_external_candidate_knowledge_base_v1",
        tenant_id: 1,
        status: "ready_for_review",
        schema_ready: true,
        source_catalog_ready: true,
        reviewed_metadata_lane_ready: true,
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
          "approved_for_candidate_use_is_not_runtime_activation",
          "feedstock_public_dataset_candidates_do_not_count_as_reviewed_release_evidence",
        ],
      },
    });

    const result = await bosApi.getReviewedExternalCandidateKnowledgeBase();

    expect(mockClient.get).toHaveBeenCalledWith("/external-sources/reviewed-candidates/knowledge-base");
    expect(result.supported_candidate_domains).toEqual(
      expect.arrayContaining(["bsf_metadata", "feedstock_metadata", "lca", "tea", "compliance", "model_provider", "github_reference"]),
    );
    expect(result.runtime_activated_count).toBe(0);
    expect(result.validated_default_write_enabled_count).toBe(0);
    expect(result.guardrails).toContain("feedstock_public_dataset_candidates_do_not_count_as_reviewed_release_evidence");
  });

  it("fetches business knowledge review packet exports as response-only payloads", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "business_knowledge_review_packet_export_v1",
        tenant_id: 1,
        export_format: "json",
        export_filename: "AGR-GERMINATION-RATE-REVIEW-PACKET.json",
        content_hash: "a".repeat(64),
        export_manifest: {
          item_key: "germination_rate",
          group_key: "product_agronomy_outputs",
          review_packet_id: "AGR-GERMINATION-RATE-REVIEW-PACKET",
          review_state: "pending_review",
          export_policy: "response_only_no_file_write",
        },
        review_packet: {
          item: { item_key: "germination_rate" },
          review_workflow: { numeric_values_allowed: false },
          source_trace: { release_evidence_allowed: false },
        },
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
      },
    });

    const result = await bosApi.getBusinessKnowledgeReviewPacketExport("germination_rate");

    expect(mockClient.get).toHaveBeenCalledWith(
      "/external-sources/business-knowledge/germination_rate/review-packet/export",
    );
    expect(result.export_manifest.export_policy).toBe("response_only_no_file_write");
    expect(result.side_effects.file_written).toBe(false);
    expect(result.side_effects.final_action_execution).toBe(false);
  });

  it("fetches literature extraction candidate review packet exports as response-only payloads", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "literature_extraction_candidate_review_packet_export_v1",
        tenant_id: 1,
        export_format: "json",
        export_filename: "LIT-AGR-GI-001-literature-extraction-review-packet.json",
        content_hash: "b".repeat(64),
        export_manifest: {
          export_id: "literature-extraction-review-packet-export:LIT-AGR-GI-001:bbbbbbbbbbbb",
          candidate_id: "LIT-AGR-GI-001",
          export_policy: "response_only_no_file_write",
          release_evidence_allowed: false,
          runtime_activation_enabled: false,
          validated_default_write_enabled: false,
          promotion_enabled: false,
          final_action_execution: false,
        },
        review_packet: {
          raw_value: "85-102",
          unit: "%",
          conditions: { condition_context: "Radish seed germination assay" },
          source_trace: { source_ref: "https://doi.org/10.3390/su151511526" },
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
      },
    });

    const result = await bosApi.getLiteratureExtractionCandidateReviewPacketExport("LIT-AGR-GI-001");

    expect(mockClient.get).toHaveBeenCalledWith(
      "/external-sources/literature-extraction-candidates/LIT-AGR-GI-001/review-packet/export",
    );
    expect(result.export_manifest.export_policy).toBe("response_only_no_file_write");
    expect(result.export_manifest.release_evidence_allowed).toBe(false);
    expect(result.review_packet.raw_value).toBe("85-102");
    expect(result.side_effects.file_written).toBe(false);
    expect(result.side_effects.final_action_execution).toBe(false);
  });

  it("fetches literature extraction bulk review packet exports as response-only payloads", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "literature_extraction_candidate_review_packet_bulk_export_v1",
        tenant_id: 1,
        export_format: "json",
        export_filename: "literature-extraction-review-packets.json",
        content_hash: "c".repeat(64),
        export_manifest: {
          export_id: "literature-extraction-review-packet-bulk-export:1:cccccccccccc",
          candidate_count: 5,
          export_policy: "response_only_no_file_write",
          source_packet_persistence: "persisted_candidate_records_only",
        },
        packet_exports: [],
        count: 5,
        metric_counts: { germination_index: 3, phytotoxicity: 2 },
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
        ],
      },
    });

    const result = await bosApi.getLiteratureExtractionCandidateReviewPacketBulkExport();

    expect(mockClient.get).toHaveBeenCalledWith(
      "/external-sources/literature-extraction-candidates/review-packets/export",
    );
    expect(result.count).toBe(5);
    expect(result.export_manifest.export_policy).toBe("response_only_no_file_write");
    expect(result.export_manifest.source_packet_persistence).toBe("persisted_candidate_records_only");
    expect(result.side_effects.file_written).toBe(false);
    expect(result.side_effects.final_action_execution).toBe(false);
  });

  it("records and lists literature extraction reviewer draft intent without activation side effects", async () => {
    mockClient.post.mockResolvedValueOnce({
      data: {
        schema_version: "literature_extraction_review_draft_v1",
        review_draft_id: "LERD-TEST-001",
        tenant_id: 1,
        candidate_id: "LIT-AGR-GI-001",
        source_id: "A-BSF-007",
        reviewer_user_id: 1,
        review_intent: "approve_candidate_use_intent",
        reviewer_notes: "intent only",
        status: "draft_intent_recorded",
        source_review_packet_export_id: "literature-extraction-review-packet-export:LIT-AGR-GI-001:bbbbbbbbbbbb",
        source_review_packet_hash: "b".repeat(64),
        candidate_snapshot: { review_status: "pending_review" },
        export_manifest: { export_policy: "response_only_no_file_write" },
        release_evidence_allowed: false,
        runtime_activation_enabled: false,
        validated_default_write_enabled: false,
        promotion_enabled: false,
        final_action_execution: false,
        side_effects: {
          candidate_status_update: false,
          runtime_activation: false,
          validated_default_write: false,
          release_evidence_use: false,
          promotion: false,
          final_action_execution: false,
        },
        guardrails: ["candidate_status_remains_pending_review"],
        idempotency_key: "idem-draft",
        created_at: "2026-04-28T07:45:00+00:00",
        updated_at: "2026-04-28T07:45:00+00:00",
      },
    });
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "literature_extraction_review_draft_list_v1",
        tenant_id: 1,
        count: 1,
        drafts: [{ review_draft_id: "LERD-TEST-001" }],
        side_effects: { candidate_status_update: false, final_action_execution: false },
        guardrails: ["literature_extraction_review_draft_list_is_read_only"],
      },
    });
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "literature_extraction_review_draft_comparison_v1",
        tenant_id: 1,
        candidate_id: "LIT-AGR-GI-001",
        current_review_draft_id: "LERD-TEST-001",
        previous_review_draft_id: null,
        current_revision_hash: "c".repeat(64),
        current_candidate_snapshot_hash: "d".repeat(64),
        current_export_manifest_hash: "e".repeat(64),
        source_review_packet_hash: "b".repeat(64),
        current_response_packet_hash: "b".repeat(64),
        changed_field_filter: null,
        comparison_manifest: {
          comparison_policy: "response_only_no_file_write",
          comparison_hash: "f".repeat(64),
          candidate_status: "pending_review",
        },
        report_manifest: {
          report_policy: "response_only_no_file_write",
          report_id: "literature-extraction-review-draft-comparison-report:LIT-AGR-GI-001:ffffffffffff",
          file_written: false,
        },
        report_payload: {
          summary: {
            packet_hash_matches: true,
            changed_fields: [],
          },
        },
        comparison_summary: {
          current_response_packet_hash_matches_draft: true,
          current_candidate_snapshot_matches_draft: true,
        },
        changed_fields: [],
        audit_trail: [{ review_draft_id: "LERD-TEST-001", revision_hash: "c".repeat(64) }],
        side_effects: { file_written: false, release_evidence_use: false, final_action_execution: false },
        guardrails: ["literature_extraction_review_draft_comparison_is_read_only"],
      },
    });

    const draft = await bosApi.createLiteratureExtractionReviewDraft("LIT-AGR-GI-001", {
      review_intent: "approve_candidate_use_intent",
      reviewer_notes: "intent only",
      idempotency_key: "idem-draft",
    });
    const drafts = await bosApi.listLiteratureExtractionReviewDrafts();
    const comparison = await bosApi.getLiteratureExtractionReviewDraftComparison("LIT-AGR-GI-001");

    expect(mockClient.post).toHaveBeenCalledWith(
      "/external-sources/literature-extraction-candidates/LIT-AGR-GI-001/review-drafts",
      {
        review_intent: "approve_candidate_use_intent",
        reviewer_notes: "intent only",
        idempotency_key: "idem-draft",
      },
    );
    expect(mockClient.get).toHaveBeenCalledWith(
      "/external-sources/literature-extraction-candidates/review-drafts",
    );
    expect(mockClient.get).toHaveBeenCalledWith(
      "/external-sources/literature-extraction-candidates/LIT-AGR-GI-001/review-drafts/comparison",
    );
    expect(draft.status).toBe("draft_intent_recorded");
    expect(draft.side_effects.candidate_status_update).toBe(false);
    expect(drafts.count).toBe(1);
    expect(comparison.comparison_manifest.comparison_policy).toBe("response_only_no_file_write");
    expect(comparison.report_manifest.report_policy).toBe("response_only_no_file_write");
    expect(comparison.comparison_summary.current_response_packet_hash_matches_draft).toBe(true);
  });

  it("fetches literature extraction reviewer draft comparison with a changed-field filter", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "literature_extraction_review_draft_comparison_v1",
        tenant_id: 1,
        candidate_id: "LIT-AGR-GI-001",
        current_review_draft_id: "LERD-TEST-001",
        previous_review_draft_id: "LERD-TEST-000",
        current_revision_hash: "c".repeat(64),
        current_candidate_snapshot_hash: "d".repeat(64),
        current_export_manifest_hash: "e".repeat(64),
        source_review_packet_hash: "b".repeat(64),
        current_response_packet_hash: "b".repeat(64),
        changed_field_filter: "review_intent",
        comparison_manifest: {
          comparison_policy: "response_only_no_file_write",
          changed_field_filter: "review_intent",
          candidate_status: "pending_review",
        },
        report_manifest: {
          report_policy: "response_only_no_file_write",
          changed_field_filter: "review_intent",
          file_written: false,
        },
        report_payload: { summary: { changed_fields: ["review_intent"] } },
        comparison_summary: { review_intent_changed_since_previous: true },
        changed_fields: ["review_intent"],
        audit_trail: [],
        side_effects: { file_written: false, final_action_execution: false },
        guardrails: ["literature_extraction_review_draft_comparison_is_read_only"],
      },
    });

    const comparison = await bosApi.getLiteratureExtractionReviewDraftComparison("LIT-AGR-GI-001", "review_intent");

    expect(mockClient.get).toHaveBeenCalledWith(
      "/external-sources/literature-extraction-candidates/LIT-AGR-GI-001/review-drafts/comparison?changed_field=review_intent",
    );
    expect(comparison.changed_field_filter).toBe("review_intent");
    expect(comparison.changed_fields).toEqual(["review_intent"]);
  });

  it("fetches literature extraction evidence chain readiness as a final read-only summary", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "literature_extraction_evidence_chain_readiness_v1",
        tenant_id: 1,
        chain_complete: true,
        candidate_count: 5,
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
        readiness_notes: [
          "literature raw values are persisted only as pending_review candidates",
          "chain completion does not permit release evidence, runtime activation, defaults, promotion, or final actions",
        ],
      },
    });

    const readiness = await bosApi.getLiteratureExtractionEvidenceChainReadiness();

    expect(mockClient.get).toHaveBeenCalledWith(
      "/external-sources/literature-extraction-candidates/evidence-chain/readiness",
    );
    expect(readiness.schema_version).toBe("literature_extraction_evidence_chain_readiness_v1");
    expect(readiness.chain_complete).toBe(true);
    expect(readiness.auto_use_allowed).toBe(false);
    expect(readiness.release_evidence_allowed).toBe(false);
    expect(readiness.final_action_execution).toBe(false);
    expect(readiness.side_effects.final_action_execution).toBe(false);
  });

  it("maps literature value promotion workflow endpoints", async () => {
    mockClient.post
      .mockResolvedValueOnce({ data: { schema_version: "literature_value_promotion_request_v1", promotion_request_id: "LVPR-1" } })
      .mockResolvedValueOnce({ data: { schema_version: "literature_value_promotion_approval_v1", approval_id: "LVPA-1" } })
      .mockResolvedValueOnce({ data: { schema_version: "literature_value_promotion_approval_v1", approval_id: "LVPA-R" } })
      .mockResolvedValueOnce({ data: { schema_version: "literature_value_overlay_v1", overlay_id: "LVO-1" } })
      .mockResolvedValueOnce({ data: { schema_version: "literature_value_runtime_activation_v1", activation_id: "LVRA-1" } })
      .mockResolvedValueOnce({ data: { schema_version: "literature_value_runtime_activation_v1", activation_id: "LVRA-1", activation_status: "deactivated" } })
      .mockResolvedValueOnce({ data: { schema_version: "literature_value_rollback_v1", rollback_id: "LVRB-1" } })
      .mockResolvedValueOnce({ data: { schema_version: "literature_value_release_evidence_link_v1", link_id: "LVREL-1" } });
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "literature_value_runtime_activation_preview_v1",
        overlay_id: "LVO-1",
        can_activate_scoped_runtime: true,
      },
    });

    await bosApi.createLiteratureValuePromotionRequest("LIT-AGR-GI-001", {
      target_use: "candidate_overlay_review",
      target_scope: { campaign_key: "literature-promotion:LIT-AGR-GI-001" },
      idempotency_key: "idem-request",
    });
    await bosApi.approveLiteratureValuePromotionRequest("LVPR-1", {
      approval_action: "approve",
      approver_notes: "approved",
      idempotency_key: "idem-approve",
    });
    await bosApi.rejectLiteratureValuePromotionRequest("LVPR-1", {
      rejector_notes: "reject",
      idempotency_key: "idem-reject",
    });
    await bosApi.promoteLiteratureValueRequestToOverlay("LVPR-1", {
      overlay_notes: "inactive overlay",
      idempotency_key: "idem-overlay",
    });
    await bosApi.getLiteratureValueRuntimeActivationPreview("LVO-1");
    await bosApi.createLiteratureValueRuntimeActivation("LVO-1", {
      activation_scope: { campaign_key: "literature-promotion:LIT-AGR-GI-001" },
      operator_attestation: "scoped only",
      idempotency_key: "idem-activate",
    });
    await bosApi.deactivateLiteratureValueRuntimeActivation("LVRA-1", {
      deactivation_reason: "pause",
      operator_attestation: "scoped only",
      idempotency_key: "idem-deactivate",
    });
    await bosApi.rollbackLiteratureValueRuntimeActivation("LVRA-1", {
      rollback_reason: "rollback",
      operator_attestation: "preserve review_required",
      idempotency_key: "idem-rollback",
    });
    await bosApi.createLiteratureValueReleaseEvidenceLink(42, {
      activation_id: "LVRA-1",
      link_notes: "review evidence only",
      idempotency_key: "idem-link",
    });

    expect(mockClient.post).toHaveBeenNthCalledWith(
      1,
      "/external-sources/literature-extraction-candidates/LIT-AGR-GI-001/promotion-requests",
      {
        target_use: "candidate_overlay_review",
        target_scope: { campaign_key: "literature-promotion:LIT-AGR-GI-001" },
        idempotency_key: "idem-request",
      },
    );
    expect(mockClient.post).toHaveBeenNthCalledWith(
      2,
      "/external-sources/promotion-requests/LVPR-1/approvals",
      { approval_action: "approve", approver_notes: "approved", idempotency_key: "idem-approve" },
    );
    expect(mockClient.post).toHaveBeenNthCalledWith(
      3,
      "/external-sources/promotion-requests/LVPR-1/reject",
      { rejector_notes: "reject", idempotency_key: "idem-reject" },
    );
    expect(mockClient.post).toHaveBeenNthCalledWith(
      4,
      "/external-sources/promotion-requests/LVPR-1/promote-overlay",
      { overlay_notes: "inactive overlay", idempotency_key: "idem-overlay" },
    );
    expect(mockClient.get).toHaveBeenCalledWith("/external-sources/overlays/LVO-1/activation-preview");
    expect(mockClient.post).toHaveBeenNthCalledWith(
      5,
      "/external-sources/overlays/LVO-1/runtime-activations",
      {
        activation_scope: { campaign_key: "literature-promotion:LIT-AGR-GI-001" },
        operator_attestation: "scoped only",
        idempotency_key: "idem-activate",
      },
    );
    expect(mockClient.post).toHaveBeenNthCalledWith(
      6,
      "/external-sources/runtime-activations/LVRA-1/deactivate",
      { deactivation_reason: "pause", operator_attestation: "scoped only", idempotency_key: "idem-deactivate" },
    );
    expect(mockClient.post).toHaveBeenNthCalledWith(
      7,
      "/external-sources/runtime-activations/LVRA-1/rollback",
      { rollback_reason: "rollback", operator_attestation: "preserve review_required", idempotency_key: "idem-rollback" },
    );
    expect(mockClient.post).toHaveBeenNthCalledWith(
      8,
      "/external-sources/release-decisions/42/literature-value-release-evidence-links",
      { activation_id: "LVRA-1", link_notes: "review evidence only", idempotency_key: "idem-link" },
    );
  });

  it("fetches external source schema readiness as read-only diagnostics", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        schema_version: "external_source_schema_readiness_v1",
        status: "ready",
        schema_ready: true,
        source_catalog_ready: true,
        feedstock_dataset_candidate_count: 9,
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
      },
    });

    const result = await bosApi.getExternalSourceSchemaReadiness();

    expect(mockClient.get).toHaveBeenCalledWith("/external-sources/schema-readiness");
    expect(result.status).toBe("ready");
    expect(result.feedstock_dataset_candidate_count).toBe(9);
    expect(result.guardrails).toContain("no_table_creation");
    expect(result.guardrails).toContain("no_validated_default_writes");
  });

  it("fetches reference ingestion health and staged items", async () => {
    mockClient.get
      .mockResolvedValueOnce({
        data: {
          parser_name: "mineru",
          parser_command: "mineru",
          parser_extra_args: "-b pipeline -m txt",
          parser_available: false,
          promotion_enabled: true,
          storage_root: "C:/tmp/reference-ingestion",
          staged_count: 2,
          promoted_count: 1,
          rollback_mode: "promotion_explicit",
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: [{ id: "refing_123" }],
          count: 1,
        },
      });

    const health = await bosApi.getReferenceIngestionHealth();
    const staged = await bosApi.listReferenceIngestionItems();

    expect(mockClient.get).toHaveBeenNthCalledWith(1, "/references/ingestion/health");
    expect(mockClient.get).toHaveBeenNthCalledWith(2, "/references/ingestion/staged");
    expect(health.rollback_mode).toBe("promotion_explicit");
    expect(staged.count).toBe(1);
  });

  it("promotes staged reference ingestion items explicitly", async () => {
    mockClient.post.mockResolvedValueOnce({
      data: {
        staged_item: { id: "refing_123", status: "promoted" },
        campaign: { key: "staged_core_relay", species_chain: ["MW", "PB"] },
      },
    });

    const result = await bosApi.promoteReferenceIngestionItem("refing_123", {
      target_type: "campaign",
      notes: "approved",
    });

    expect(mockClient.post).toHaveBeenCalledWith(
      "/references/ingestion/staged/refing_123/promote",
      { target_type: "campaign", notes: "approved" },
    );
    expect(result.campaign.key).toBe("staged_core_relay");
  });
});
