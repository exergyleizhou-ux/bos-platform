import { describe, expect, it } from "vitest";

import {
  deriveBosNextBestActions,
  getBosActionIntent,
  getBosActionLabel,
  mapBosGuidanceItem,
} from "@/lib/bosGuidance";

describe("bosGuidance", () => {
  it("maps backend guidance items into operator-facing copy", () => {
    const action = mapBosGuidanceItem({
      code: "missing_signal_batch",
      severity: "critical",
      title: "Signal not compiled",
      message: "This batch does not have a compiled BOS signal yet.",
      recommended_action: "Compile the signal first.",
      blocking: true,
    });

    expect(action.title).toBe("Compile the signal first");
    expect(action.recommendedAction).toBe("Compile the signal first");
    expect(action.blocking).toBe(true);
    expect(action.actionIntent).toBe("compile_signal");
  });

  it("derives release-blocked fallback actions when guidance is unavailable", () => {
    const actions = deriveBosNextBestActions({
      signal: {
        id: 11,
        batch_id: 101,
        user_id: 1,
        tenant_id: 1,
        signal_api_version: "SIG-1.0",
        compiled_signal_id: "SIG-READY-001",
        potency: 0.45,
        potency_unit: "SER-equivalent",
        potency_basis: "matched_boundary",
        dose_window_min: 0.1,
        dose_window_max: 0.3,
        stability_window_hours: 8,
        kernel_residence_time_hours: null,
        handover_time: null,
        freshness_state: "Fresh",
        qc_markers: null,
        notes: null,
        released_at: null,
        expires_at: null,
        created_at: "2026-04-16T00:00:00Z",
        updated_at: "2026-04-16T00:10:00Z",
      },
      releaseDecision: {
        id: 33,
        batch_id: 101,
        signal_batch_id: 11,
        boundary_ledger_id: null,
        control_profile_id: 5,
        user_id: 1,
        tenant_id: 1,
        decision: "FAIL",
        reason_codes: ["potency_out_of_contract"],
        blocking_factors: ["Signal potency is outside the current contract window."],
        warning_factors: [],
        passed_checks: [],
        trigger_metrics: null,
        approver: null,
        rationale: "Release blocked pending contract retuning.",
        decision_time: "2026-04-16T00:12:00Z",
        created_at: "2026-04-16T00:12:00Z",
      },
      portabilityAudits: [],
      hasControlProfile: true,
      hasLocalityProfile: true,
    });

    expect(actions[0]).toMatchObject({
      code: "fallback_release_blocked",
      title: "Release is currently blocked",
      recommendedAction: "Retune the control profile or compile a signal that fits the dose window.",
      blocking: true,
    });
    expect(actions[1]).toMatchObject({
      code: "fallback_no_portability_check",
      title: "Run the portability check first",
    });
  });

  it("derives stable action intents and surface labels", () => {
    expect(
      getBosActionIntent({
        code: "release_not_evaluated",
        recommendedAction: "Continue with the release evaluation",
      }),
    ).toBe("evaluate_release");

    expect(
      getBosActionLabel("evaluate_release", "batch"),
    ).toBe("Evaluate release");
    expect(
      getBosActionLabel("open_signal_lab", "signal_lab"),
    ).toBe("Open decision console");
  });
});
