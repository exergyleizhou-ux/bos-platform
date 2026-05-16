import { describe, expect, it } from "vitest";

import {
  buildBatchAnalysisResult,
  buildResearchReviewAssistantResult,
  buildSimulationLabAssistantResult,
  buildSafeStillCopy,
  clampText,
  computeBatchRiskScore,
  normalizePromptSubject,
  resolveResearchReviewContinuationParentRunId,
  splitChineseHeadline,
} from "@/pages/BOSAssistantV1Page";
import type { Batch } from "@/types/batch";
import type { SignalBatch } from "@/types/bos";
import type { AssistantRunResponse } from "@/types/assistant";
import type { VisionObservation } from "@/types/vision";

describe("BOSAssistantV1Page helpers", () => {
  it("extracts a Chinese topic marker before building copy", () => {
    expect(normalizePromptSubject("\u4e3b\u9898\u662f \u751f\u6210\u53d1\u5e03\u6d77\u62a5")).toBe(
      "\u751f\u6210\u53d1\u5e03\u6d77\u62a5",
    );
    expect(normalizePromptSubject("\u4e3b\u9898\uff1a\u8fd0\u8425\u4fe1\u53f7\u5361\u7247")).toBe(
      "\u8fd0\u8425\u4fe1\u53f7\u5361\u7247",
    );
  });

  it("splits Chinese headlines into compact two-line titles when needed", () => {
    expect(splitChineseHeadline("\u53d1\u5e03\u6d77\u62a5\u5c01\u9762")).toBe(
      "\u53d1\u5e03\u6d77\u62a5\u5c01\u9762",
    );
    expect(splitChineseHeadline("\u8fd0\u8425")).toBe("\u8fd0\u8425");
    expect(splitChineseHeadline("\u56fd\u9645\u5316\u5de5\u4f5c\u53f0\u5347\u7ea7\u8ba1\u5212")).toBe(
      "\u56fd\u9645\u5316\u5de5\u4f5c\u53f0\n\u5347\u7ea7\u8ba1\u5212",
    );
  });

  it("builds readable Chinese release-oriented still copy", () => {
    const copy = buildSafeStillCopy("\u4e3b\u9898\u662f \u751f\u6210\u53d1\u5e03\u6d77\u62a5");
    expect(copy.metricLabel).toBe("\u7528\u9014");
    expect(copy.metricValue).toBe("\u53d1\u5e03");
    expect(copy.caption).toBe("\u53d1\u5e03\u6d77\u62a5");
    expect(copy.subtitle).toContain("\u5b89\u5168\u9759\u6001\u56fe");
  });

  it("builds readable Chinese operations-oriented still copy when release keywords are absent", () => {
    const copy = buildSafeStillCopy("\u8fd0\u8425\u4fe1\u53f7\u5361\u7247");
    expect(copy.metricLabel).toBe("\u7528\u9014");
    expect(copy.metricValue).toBe("\u8fd0\u8425");
    expect(copy.caption).toBe("\u8fd0\u8425\u4fe1\u53f7");
  });

  it("uses an ellipsis when truncating long copy", () => {
    expect(clampText("0123456789", 5)).toBe("0123\u2026");
  });

  it("adds vision observation notes to batch analysis", () => {
    const result = buildBatchAnalysisResult({
      batch: makeBatch(),
      guidance: { gap_items: [], recommended_actions: [] },
      signal: makeSignal({
        anomaly_flag: false,
        confidence_mean: 0.82,
        observation_summary: "2 detections; dominant label larvae_cluster; mean confidence 0.82.",
      }),
      audit: null,
    });

    expect(result.notes?.some((note) => note.includes("Vision observation: 2 detections"))).toBe(true);
    expect(result.notes?.some((note) => note.includes("dominant larvae_cluster"))).toBe(true);
  });

  it("adds review-only vision risk without overriding core BOS posture", () => {
    const highRisk = computeBatchRiskScore({
      batch: makeBatch(),
      signal: makeSignal({
        anomaly_flag: true,
        confidence_mean: 0.9,
        observation_summary: "1 detection; dominant label foreign_object; mean confidence 0.90.",
        dominant_label: "foreign_object",
        detected_classes: ["foreign_object"],
      }),
      audit: null,
      guidance: { gap_items: [] },
    });
    const lowConfidence = computeBatchRiskScore({
      batch: makeBatch(),
      signal: makeSignal({
        anomaly_flag: false,
        confidence_mean: 0.31,
        observation_summary: "1 detection; dominant label larvae_cluster; mean confidence 0.31.",
      }),
      audit: null,
      guidance: { gap_items: [] },
    });

    expect(highRisk.score).toBe(2);
    expect(highRisk.reasons).toContain("Vision observation flagged an anomaly for operator review");
    expect(lowConfidence.score).toBe(1);
    expect(lowConfidence.reasons).toContain("Vision observation confidence is below the preferred review band");
  });

  it("surfaces assistant compliance, LCA, and TEA evidence in the structured result", () => {
    const result = buildSimulationLabAssistantResult(makeAssistantRunWithValueProofs());

    expect(result.metrics?.some((item) => item.label === "Compliance" && item.value === "blocked")).toBe(true);
    expect(result.metrics?.some((item) => item.label === "LCA proof" && item.value.includes("431.6"))).toBe(true);
    expect(result.metrics?.some((item) => item.label === "TEA proof" && item.value.includes("105.4"))).toBe(true);
    expect(result.sections?.some((section) => section.title === "Compliance gate result")).toBe(true);
    expect(result.sections?.some((section) => section.title === "LCA value proof")).toBe(true);
    expect(result.sections?.some((section) => section.title === "TEA value proof")).toBe(true);
    expect(result.sections?.some((section) => section.title === "Uncertainty warnings")).toBe(true);
    expect(result.metrics?.some((item) => item.label === "Confirmations" && item.value === "3")).toBe(true);
    const confirmationSection = result.sections?.find((section) => section.title === "Human confirmation queue");
    expect(confirmationSection?.items).toContain("release.request_human_approval: pending / queue_only_no_auto_approval");
    expect(confirmationSection?.items).toContain(
      "external.share_release_packet: pending / forbidden_until_explicit_external_share_workflow",
    );
    expect(confirmationSection?.items).toContain("model.complete_review: pending / queue_only_no_model_activation");
    expect(result.notes).toContain("Compliance gate: GATE-20260425-ABCDEF01");
    expect(result.notes).toContain("LCA result: SUS-20260425-LCA00001");
    expect(result.notes).toContain("TEA result: SUS-20260425-TEA00001");
  });

  it("surfaces a research partner readout while keeping trace sections in the background", () => {
    const result = buildResearchReviewAssistantResult(makeResearchReviewRun());

    expect(result.title).toBe("Research partner readout");
    expect(result.summary).toContain("research partner review");
    expect(result.metrics?.some((item) => item.label === "Decision posture" && item.value === "review_required")).toBe(true);
    expect(result.metrics?.some((item) => item.label === "Research team" && item.value === "9 specialists")).toBe(true);
    expect(result.metrics?.some((item) => item.label === "Audit trail" && item.value === "Captured")).toBe(true);
    expect(result.metrics?.some((item) => item.label === "Continuity" && item.value === "Recalled")).toBe(true);
    expect(result.sections?.some((section) => section.title === "My read on the proposal")).toBe(true);
    expect(result.sections?.some((section) => section.title === "Reasoning in progress")).toBe(true);
    expect(result.sections?.some((section) => section.title === "Evidence status")).toBe(true);
    expect(result.sections?.some((section) => section.title === "Controlled pilot plan")).toBe(true);
    expect(result.sections?.some((section) => section.title === "What I would challenge first")).toBe(true);
    expect(result.sections?.some((section) => section.title === "Next research moves")).toBe(true);
    expect(result.sections?.some((section) => section.title === "Trace: team plan")).toBe(true);
    expect(result.sections?.some((section) => section.title === "Trace: specialist cards")).toBe(true);
    expect(result.sections?.some((section) => section.title === "Trace: action ledger")).toBe(true);
    expect(result.notes?.some((note) => note.includes("review_required"))).toBe(true);
    expect(result.notes?.some((note) => note.includes("Trace and evidence are captured in the background"))).toBe(true);
    expect(result.notes).toContain("Continuation parent: ARUN-PARENT-REVIEW");
  });

  it("surfaces Chinese research review judgment and expert debate without weakening review gates", () => {
    const result = buildResearchReviewAssistantResult(makeChineseResearchReviewRun());
    const sectionTitles = result.sections?.map((section) => section.title) ?? [];
    const renderedText = JSON.stringify(result);

    expect(result.title).toBe("\u79d1\u7814\u4f19\u4f34\u8bc4\u5ba1");
    expect(sectionTitles).toContain("\u4e13\u5bb6\u7ec4\u5df2\u542f\u52a8");
    expect(sectionTitles).toContain("\u63a8\u6f14\u8fdb\u5ea6");
    expect(sectionTitles).toContain("\u4e13\u5bb6\u4ea4\u950b\u7eaa\u8981");
    expect(sectionTitles).toContain("\u8bc1\u636e\u72b6\u6001");
    expect(sectionTitles).toContain("\u53d7\u63a7\u5c0f\u8bd5\u8ba1\u5212");
    expect(renderedText).toContain("\u9ec4\u7c89\u866b");
    expect(renderedText).toContain("\u86f4\u87ac");
    expect(renderedText).toContain("review_required");
    expect(renderedText).toContain("\u95ee\u9898\u91cd\u6784");
    expect(renderedText).toContain("candidate_evidence");
    expect(renderedText).toContain("P1 \u9ec4\u7c89\u866b\u53d7\u63a7\u5c0f\u8bd5");
  });

  it("attaches a persisted session research review parent only for continuation prompts", () => {
    const latestRunId = "ARUN-SESSION-PARENT";

    expect(
      resolveResearchReviewContinuationParentRunId(
        "让机制分析师继续深挖反证和失效模式，focus on counterexample and failure mode",
        latestRunId,
      ),
    ).toBe(latestRunId);
    expect(
      resolveResearchReviewContinuationParentRunId(
        "请做课题方案评审，并让专家团队审查这个实验设计",
        latestRunId,
      ),
    ).toBeNull();
    expect(
      resolveResearchReviewContinuationParentRunId(
        "让机制分析师继续深挖反证和失效模式，focus on counterexample and failure mode",
        null,
      ),
    ).toBeNull();
  });
});

function makeBatch(): Batch {
  return {
    id: 42,
    batch_id: "VISION-BATCH-001",
    species: "BSF",
    status: "completed",
    dm_in: 10,
    dm_out: 4,
    n_in: null,
    n_larvae: null,
    n_frass: null,
    ash_in: null,
    ash_out: null,
    fat_in: null,
    fat_out: null,
    temperature: 28,
    moisture: 66,
    feed_rate: null,
    density: null,
    score: 0.01,
    operator: null,
    notes: null,
    batch_date: null,
    created_at: "2026-04-23T00:00:00Z",
    updated_at: "2026-04-23T00:00:00Z",
    bos: null,
  };
}

function makeAssistantRunWithValueProofs(): AssistantRunResponse {
  return {
    run_id: "ARUN-20260425-ABCDEF01",
    tenant_id: 1,
    user_id: 1,
    user_message: "run compliance lca tea",
    parsed_intent: {
      scenario: "moisture_drift",
      cycles: 6,
      policy: "rule_based",
    },
    status: "completed",
    evidence_pack_id: "EVP-ASSISTANT",
    tool_registry: { version: "assistant-tool-registry-v1" },
    team_plan: [],
    specialist_cards: [],
    handoff_records: [],
    review_verdicts: [],
    action_ledger: [],
    memory_tags: [],
    final_synthesis: null,
    created_at: "2026-04-25T00:00:00Z",
    completed_at: "2026-04-25T00:01:00Z",
    tool_calls: [],
    confirmation_requests: [
      {
        confirmation_id: "ACONF-RELEASE",
        action_name: "release.request_human_approval",
        action_payload: {
          release_attachment_id: "RPA-20260425-ABCDEF01",
          execution: "queue_only_no_auto_approval",
        },
        status: "pending",
        reason: null,
        created_at: "2026-04-25T00:00:30Z",
        resolved_at: null,
      },
      {
        confirmation_id: "ACONF-SHARE",
        action_name: "external.share_release_packet",
        action_payload: {
          release_attachment_id: "RPA-20260425-ABCDEF01",
          execution: "forbidden_until_explicit_external_share_workflow",
        },
        status: "pending",
        reason: null,
        created_at: "2026-04-25T00:00:31Z",
        resolved_at: null,
      },
      {
        confirmation_id: "ACONF-MODEL",
        action_name: "model.complete_review",
        action_payload: {
          approval_request_id: "HAR-20260425-ABCDEF01",
          execution: "queue_only_no_model_activation",
        },
        status: "pending",
        reason: null,
        created_at: "2026-04-25T00:00:32Z",
        resolved_at: null,
      },
    ],
    result_summary: {
      simulation_id: "SIM-20260425-ABCDEF01",
      run_id: "RUN-SIM-20260425-ABCDEF01-1",
      export_ready: true,
      tool_registry_version: "assistant-tool-registry-v1",
      result_ids: {
        evidence_pack_id: "EVP-ASSISTANT",
        release_attachment_id: "RPA-20260425-ABCDEF01",
        model_approval_request_id: "HAR-20260425-ABCDEF01",
        compliance_gate_id: "GATE-20260425-ABCDEF01",
        compliance_evidence_pack_id: "EVP-COMPLIANCE",
        lca_result_id: "SUS-20260425-LCA00001",
        lca_evidence_pack_id: "EVP-LCA",
        tea_result_id: "SUS-20260425-TEA00001",
        tea_evidence_pack_id: "EVP-TEA",
      },
      human_review_requirement: {
        state: "review_required",
        required_for: ["release approval before external use", "compliance blocker resolution", "LCA/TEA uncertainty review"],
      },
      risk_value_drivers: {
        risk_drivers: ["Release decision remains unchanged until human review."],
        value_drivers: ["LCA abatement proof: 431.6 kg CO2e.", "TEA gross margin proof: 105.4 USD."],
      },
      compliance_gate: {
        gate_id: "GATE-20260425-ABCDEF01",
        status: "blocked",
        missing_assays: ["moisture", "protein"],
        blocked_reasons: ["missing_assay:moisture", "missing_assay:protein"],
        evidence_pack_id: "EVP-COMPLIANCE",
      },
      lca_value_proof: {
        result_id: "SUS-20260425-LCA00001",
        result: {
          baseline_co2e_kg: 450,
          alternative_co2e_kg: 18.4,
          co2e_abatement_kg: 431.6,
        },
      },
      tea_value_proof: {
        result_id: "SUS-20260425-TEA00001",
        result: {
          revenue_usd: 125,
          operating_cost_usd: 19.6,
          gross_margin_usd: 105.4,
        },
      },
      uncertainty_warnings: [
        "emission_factor.electricity_kgco2e_per_kwh defaulted",
        "cost_factor.energy_usd_per_kwh defaulted",
      ],
      next_safe_actions: [],
    },
  };
}

function makeResearchReviewRun(): AssistantRunResponse {
  const teamPlan = [
    "Chief Scientist",
    "Protocol Designer",
    "Mechanistic Analyst",
    "Reference Evidence Curator",
    "Digital Twin Analyst",
    "Data Integrity Reviewer",
    "Scientific Reviewer",
    "Evidence Auditor",
    "Chief Scientist",
  ].map((title, index) => ({
    stage: index + 1,
    specialist_id: `${title.toLowerCase().replace(/\s+/g, "_")}_${index + 1}`,
    title,
    objective: `Review objective ${index + 1}`,
  }));
  const specialistCards = teamPlan.map((step) => ({
    specialist_id: step.specialist_id,
    title: step.title,
    objective: step.objective,
    inputs_used: ["operator_prompt"],
    reasoning_summary: "Reasoning stays review-gated.",
    deliverable: `${step.title} deliverable`,
    uncertainties: ["Requires human review"],
    handoff_to: [],
    review_required: true,
    evidence_refs: ["EVP-RESEARCH"],
  }));
  const reviewVerdicts = [
    { gate: "scientific_rigor", verdict: "review_required" },
    { gate: "evidence_traceability", verdict: "review_required" },
  ];
  const actionLedger = [
    {
      action_name: "evidence_pack.create_or_update",
      action_policy: "auto_allowed",
      requires_confirmation: false,
      status: "completed",
    },
    {
      action_name: "external.share",
      action_policy: "requires_confirmation",
      requires_confirmation: true,
      status: "requires_confirmation",
    },
    {
      action_name: "hardware.run",
      action_policy: "forbidden",
      requires_confirmation: true,
      status: "forbidden",
    },
  ];
  const finalSynthesis = {
    approval_state: "review_required",
    unified_answer: "BOS formed a fixed expert review team and returned a review-gated protocol critique.",
    evidence_pack_id: "EVP-RESEARCH",
    review_packet_snapshot_id: "FARP-ABCDEF0123456789",
    reasoning_stages: [
      {
        stage: "Question reframing",
        status: "complete",
        readout: "Treat the prompt as review-gated research prioritization.",
      },
    ],
    evidence_status: [
      {
        claim: "Preferred pilot lane",
        status: "candidate_evidence",
        basis: "Mechanism fit needs review.",
        gate: "review_required",
        source_ref: "EVP-RESEARCH",
      },
    ],
    experiment_plan: [
      {
        step: "P1 controlled pilot",
        design: "Run a small replicated pilot.",
        controls: ["blank substrate", "batch replicate"],
        stop_rule: "Stop on mortality threshold breach.",
        gate: "review_required",
      },
    ],
    continuity: {
      parent_run_id: "ARUN-PARENT-REVIEW",
      requested_specialist: "mechanistic_analyst",
      team_context_reused: true,
    },
  };

  return {
    run_id: "ARUN-20260428-REVIEW01",
    tenant_id: 1,
    user_id: 1,
    user_message: "research review",
    parsed_intent: { mode: "research_review" },
    status: "completed",
    result_summary: {
      team_plan: teamPlan,
      specialist_cards: specialistCards,
      review_verdicts: reviewVerdicts,
      action_ledger: actionLedger,
      final_synthesis: finalSynthesis,
    },
    evidence_pack_id: "EVP-RESEARCH",
    tool_registry: { version: "assistant-tool-registry-v1" },
    team_plan: teamPlan,
    specialist_cards: specialistCards,
    handoff_records: [],
    review_verdicts: reviewVerdicts,
    action_ledger: actionLedger,
    memory_tags: ["research_review"],
    final_synthesis: finalSynthesis,
    created_at: "2026-04-28T00:00:00Z",
    completed_at: "2026-04-28T00:01:00Z",
    tool_calls: [],
    confirmation_requests: [],
  };
}

function makeChineseResearchReviewRun(): AssistantRunResponse {
  const base = makeResearchReviewRun();
  const prompt = "\u4f60\u89c9\u5f97\u9ec4\u7c89\u866b\u548c\u86f4\u87ac \u54ea\u4e2a\u66f4\u9002\u5408\u5904\u7406\u9152\u7cdf";
  const finalSynthesis = {
    approval_state: "review_required",
    language: "zh-CN",
    unified_answer:
      "\u5728 review_required \u524d\u63d0\u4e0b\uff0c\u9ed8\u8ba4\u66f4\u5efa\u8bae\u628a\u9ec4\u7c89\u866b\u4f5c\u4e3a\u9152\u7cdf\u5904\u7406\u7684\u9996\u9009\u5c0f\u8bd5\u5bf9\u8c61\uff1b\u86f4\u87ac\u4fdd\u7559\u4e3a\u53cd\u4e8b\u5b9e\u6216\u63a2\u7d22\u8def\u7ebf\u3002",
    evidence_pack_id: "EVP-RESEARCH",
    review_packet_snapshot_id: "FARP-ABCDEF0123456789",
    debate_turns: [
      {
        speaker: "\u65b9\u6848\u8bbe\u8ba1\u4e13\u5bb6",
        stance: "\u652f\u6301\u9ec4\u7c89\u866b\u4f18\u5148\u505a\u53d7\u63a7\u5c0f\u8bd5\uff0c\u86f4\u87ac\u53ea\u4f5c\u4e3a\u53cd\u4e8b\u5b9e\u6216\u63a2\u7d22\u7ec4\u3002",
        challenges: "\u6240\u6709\u8def\u7ebf\u4fdd\u6301 review_required\u3002",
        reply: "\u9996\u5e2d\u79d1\u5b66\u5bb6\u6536\u655b\u4e3a\u9ec4\u7c89\u866b\u4f18\u5148\u5c0f\u8bd5\u3002",
      },
    ],
    reasoning_stages: [
      {
        stage: "\u95ee\u9898\u91cd\u6784",
        status: "complete",
        readout: "\u6bd4\u8f83\u9ec4\u7c89\u866b\u4e0e\u86f4\u87ac\u5904\u7406\u9152\u7cdf\u7684\u53d7\u63a7\u5c0f\u8bd5\u4f18\u5148\u7ea7\u3002",
      },
      {
        stage: "\u5ba1\u67e5\u95e8",
        status: "review_required",
        readout: "\u4e0d\u81ea\u52a8\u6279\u51c6\u3001\u4e0d\u5916\u53d1\u3001\u4e0d\u5199\u5165 validated defaults\u3002",
      },
    ],
    evidence_status: [
      {
        claim: "\u9ec4\u7c89\u866b\u66f4\u9002\u5408\u4f5c\u4e3a\u9996\u8f6e\u53d7\u63a7\u5c0f\u8bd5\u5bf9\u8c61",
        status: "candidate_evidence",
        basis: "\u9700\u8981\u6587\u732e\u4e0e\u5185\u90e8\u6570\u636e\u5ba1\u67e5\u3002",
        gate: "review_required",
        source_ref: "EVP-RESEARCH",
      },
    ],
    experiment_plan: [
      {
        step: "P1 \u9ec4\u7c89\u866b\u53d7\u63a7\u5c0f\u8bd5",
        design: "\u5c0f\u6279\u91cf\u91cd\u590d\u7ec4\u8bb0\u5f55\u542b\u6c34\u7387\u3001pH\u3001\u6b7b\u4ea1\u7387\u548c\u6b8b\u6e23\u6307\u6807\u3002",
        controls: ["\u7a7a\u767d\u57fa\u8d28", "\u9884\u5e72\u71e5\u9152\u7cdf"],
        stop_rule: "\u9709\u83cc\u3001\u6b8b\u9152\u7cbe\u6216\u6b7b\u4ea1\u7387\u8d85\u9608\u503c\u5373\u505c\u6b62\u3002",
        gate: "review_required",
      },
    ],
  };

  return {
    ...base,
    user_message: prompt,
    parsed_intent: { ...base.parsed_intent, language: "zh-CN" },
    result_summary: {
      ...base.result_summary,
      language: "zh-CN",
      final_synthesis: finalSynthesis,
    },
    final_synthesis: finalSynthesis,
  };
}

function makeSignal(overrides: Partial<VisionObservation> = {}): SignalBatch {
  return {
    id: 7,
    batch_id: 42,
    user_id: 1,
    tenant_id: 1,
    signal_api_version: "SIG-1.0",
    compiled_signal_id: "SIG-VISION-BATCH-001",
    potency: 0.2,
    potency_unit: "SER-equivalent",
    potency_basis: "matched_boundary",
    dose_window_min: null,
    dose_window_max: null,
    stability_window_hours: 8,
    kernel_residence_time_hours: null,
    handover_time: null,
    freshness_state: "Fresh",
    qc_markers: {
      vision_observation: {
        image_id: "vision-assistant-001",
        detected_classes: ["larvae_cluster"],
        detections: [
          {
            label: "larvae_cluster",
            confidence: 0.82,
            bbox: [10, 20, 120, 160],
          },
        ],
        dominant_label: "larvae_cluster",
        confidence_mean: 0.82,
        anomaly_flag: false,
        observation_summary: "2 detections; dominant label larvae_cluster; mean confidence 0.82.",
        bbox_coverage_ratio: 0.24,
        ...overrides,
      },
    },
    notes: null,
    released_at: null,
    expires_at: null,
    created_at: "2026-04-23T00:00:00Z",
    updated_at: "2026-04-23T00:00:00Z",
  };
}
