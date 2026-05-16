import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  useBatchListMock,
  useBatchGuidanceMock,
  useSignalBatchesMock,
  useControlProfilesMock,
  useLocalityProfilesMock,
  useExecutorProfilesMock,
  useReleaseDecisionsMock,
  useAuditPacketsMock,
  usePortabilityAuditsMock,
  useCompileSignalMock,
  useRefreshSignalMock,
  useEvaluateReleaseMock,
  useExportAuditPacketMock,
  usePortabilityRecommendationMock,
  useBrainRuntimeMock,
  useVisionDetectionMock,
  useVisionRunsMock,
  useAttachVisionObservationMock,
  navigateMock,
} = vi.hoisted(() => ({
  useBatchListMock: vi.fn(),
  useBatchGuidanceMock: vi.fn(),
  useSignalBatchesMock: vi.fn(),
  useControlProfilesMock: vi.fn(),
  useLocalityProfilesMock: vi.fn(),
  useExecutorProfilesMock: vi.fn(),
  useReleaseDecisionsMock: vi.fn(),
  useAuditPacketsMock: vi.fn(),
  usePortabilityAuditsMock: vi.fn(),
  useCompileSignalMock: vi.fn(),
  useRefreshSignalMock: vi.fn(),
  useEvaluateReleaseMock: vi.fn(),
  useExportAuditPacketMock: vi.fn(),
  usePortabilityRecommendationMock: vi.fn(),
  useBrainRuntimeMock: vi.fn(),
  useVisionDetectionMock: vi.fn(),
  useVisionRunsMock: vi.fn(),
  useAttachVisionObservationMock: vi.fn(),
  navigateMock: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
  useSearchParams: () => [new URLSearchParams()],
}));

vi.mock("@/hooks/useBatches", () => ({
  useBatchList: useBatchListMock,
}));

vi.mock("@/hooks/useBos", () => ({
  useBatchGuidance: useBatchGuidanceMock,
  useSignalBatches: useSignalBatchesMock,
  useControlProfiles: useControlProfilesMock,
  useLocalityProfiles: useLocalityProfilesMock,
  useExecutorProfiles: useExecutorProfilesMock,
  useReleaseDecisions: useReleaseDecisionsMock,
  useAuditPackets: useAuditPacketsMock,
  usePortabilityAudits: usePortabilityAuditsMock,
  useCompileSignal: useCompileSignalMock,
  useRefreshSignal: useRefreshSignalMock,
  useEvaluateRelease: useEvaluateReleaseMock,
  useExportAuditPacket: useExportAuditPacketMock,
  usePortabilityRecommendation: usePortabilityRecommendationMock,
  useBrainRuntime: useBrainRuntimeMock,
}));

vi.mock("@/hooks/useVision", () => ({
  useVisionDetection: useVisionDetectionMock,
  useVisionRuns: useVisionRunsMock,
  useAttachVisionObservation: useAttachVisionObservationMock,
}));

vi.mock("@/components/bos/MechanisticContextCard", () => ({
  MechanisticContextCard: () => <div>Mechanistic context card</div>,
}));
vi.mock("@/components/bos/BrainOperatorContextCard", () => ({
  BrainOperatorContextCard: () => <div>Brain operator context card</div>,
}));
vi.mock("@/components/bos/NextBestActionsCard", () => ({
  NextBestActionsCard: ({
    items,
    onAction,
  }: {
    items: Array<{ title: string; recommendedAction: string }>;
    onAction?: unknown;
  }) => (
    <div>
      Next best actions card {items.map((item) => item.title).join(" | ")} ::{" "}
      {items.map((item) => item.recommendedAction).join(" | ")}
      {items.map((item) => ("actionLabel" in item ? ` :: ${String((item as { actionLabel?: string }).actionLabel ?? "")}` : "")).join("")}
      {String(Boolean(onAction))}
    </div>
  ),
}));
vi.mock("@/components/bos/SignalSupervisorPanel", () => ({
  SignalSupervisorPanel: ({ signal }: { signal?: { compiled_signal_id?: string | null } | null }) => (
    <div>Signal supervisor panel {signal?.compiled_signal_id ?? "none"}</div>
  ),
}));
vi.mock("@/components/bos/SupervisorSnapshotCard", () => ({
  SupervisorSnapshotCard: () => <div>Supervisor snapshot card</div>,
}));
vi.mock("@/components/bos/SupervisorHistoryCard", () => ({
  SupervisorHistoryCard: () => <div>Supervisor history card</div>,
}));
vi.mock("@/components/bos/PortabilityRecommendationCard", () => ({
  PortabilityRecommendationCard: () => <div>Portability recommendation card</div>,
}));
vi.mock("@/components/bos/AuditExportCard", () => ({
  AuditExportCard: ({ hasAuditPacket }: { hasAuditPacket: boolean }) => (
    <div>Audit export card {String(hasAuditPacket)}</div>
  ),
}));
vi.mock("@/components/ui/Select", () => ({
  Select: ({
    label,
    value,
    children,
  }: {
    label: string;
    value?: string;
    children?: ReactNode;
  }) => (
    <div>
      {label}:{value}
      {children}
    </div>
  ),
}));

import SignalLabPage from "@/pages/SignalLabPage";

function mutationStub() {
  return {
    isPending: false,
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    variables: undefined,
  };
}

describe("SignalLabPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    useBatchListMock.mockReturnValue({
      data: {
        items: [{ id: 101, batch_id: "BOS-101", status: "active" }],
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    useBrainRuntimeMock.mockReturnValue({
      data: {
        documents: [
          {
            key: "project_brain",
            title: "Project Brain",
            relative_path: ".agents/runtime/project-brain.md",
            content: "# Project Brain\n\n## Current Focus\n- Qualify the signal handover\n",
            updated_at: null,
            line_count: 3,
            is_missing: false,
          },
          {
            key: "decision_journal",
            title: "Decision Journal",
            relative_path: ".agents/runtime/decision-journal.md",
            content: "# Decision Journal\n\n## Recent Decisions\n- Prioritize signal review\n",
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
    useBatchGuidanceMock.mockReturnValue({
      data: {
        batch_id: 101,
        gap_items: [
          {
            code: "release_blocked",
            severity: "critical",
            title: "Release is currently blocked",
            message: "Signal potency is outside the current contract window.",
            recommended_action: "Retune the control profile or compile a signal that fits the dose window.",
            blocking: true,
          },
          {
            code: "portability_retuning_required",
            severity: "warning",
            title: "Portability retuning is still required",
            message: "Executor pairing is viable only with retuning.",
            recommended_action: "Retune the executor or locality settings before release.",
            blocking: false,
          },
        ],
      },
      isLoading: false,
      isError: false,
    });
    useSignalBatchesMock.mockReturnValue({
      data: [
        {
          id: 11,
          batch_id: 101,
          user_id: 1,
          tenant_id: 1,
          signal_api_version: "SIG-1.0",
          compiled_signal_id: "SIG-READY-001",
          potency: 0.22,
          potency_unit: "SER-equivalent",
          potency_basis: "matched_boundary",
          dose_window_min: 0.1,
          dose_window_max: 0.3,
          stability_window_hours: 8,
          kernel_residence_time_hours: null,
          handover_time: null,
          freshness_state: "Fresh",
          qc_markers: {
            compile_context: {
              mechanistic_context: {
                c_di_ser: { score: 0.8, alpha_s: 0.5, beta_s: 0.4, penalty: 0.1, information_loss: 0.2, evidence_balance: 0.8 },
                handover_envelope: { tau_star_min: 30, c_peak: 0.6, f_clock: 0.1, rise_rate: 0.2, decay_rate: 0.1 },
                inputs: { mass_balance_ratio: 0.9, metering_completeness: 0.8, locality_shift_pct: 0 },
              },
            },
          },
          notes: null,
          released_at: null,
          expires_at: null,
          created_at: "2026-04-16T00:00:00Z",
          updated_at: "2026-04-16T00:05:00Z",
        },
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    useControlProfilesMock.mockReturnValue({
      data: [
        {
          id: 5,
          user_id: 1,
          tenant_id: 1,
          name: "CTRL Main",
          version: "CTRL-1.0",
          hal_min: 1,
          hal_max: 2,
          mtt: 4,
          dose_window_min: 0.1,
          dose_window_max: 0.3,
          stability_window_hours: 8,
          dwell_time_min_hours: null,
          dwell_time_max_hours: null,
          qc_thresholds: null,
          release_rules: null,
          active: true,
          notes: null,
          created_at: "2026-04-16T00:00:00Z",
          updated_at: "2026-04-16T00:00:00Z",
        },
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    useLocalityProfilesMock.mockReturnValue({
      data: [{ id: 8, name: "Shanghai", dose_window_shift_pct: 5, mtt_shift_pct: -3 }],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    useExecutorProfilesMock.mockReturnValue({
      data: [
        {
          id: 7,
          locality_profile_id: 8,
          user_id: 1,
          tenant_id: 1,
          executor_code: "exec-a",
          name: "Executor A",
          executor_type: "larval",
          hal_min: 1,
          hal_max: 2,
          mtt_nominal: 4,
          plugin_mode: "baseline",
          notes: null,
          active: true,
          created_at: "2026-04-16T00:00:00Z",
          updated_at: "2026-04-16T00:00:00Z",
        },
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    useReleaseDecisionsMock.mockReturnValue({
      data: [
        {
          id: 33,
          batch_id: 101,
          signal_batch_id: 11,
          boundary_ledger_id: null,
          control_profile_id: 5,
          user_id: 1,
          tenant_id: 1,
          decision: "PASS",
          reason_codes: [],
          blocking_factors: [],
          warning_factors: ["thermal_drift_watch"],
          passed_checks: ["signal_valid"],
          trigger_metrics: { decision_confidence: 0.91 },
          approver: null,
          rationale: "Release is supported.",
          decision_time: "2026-04-16T00:10:00Z",
          created_at: "2026-04-16T00:10:00Z",
        },
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    useAuditPacketsMock.mockReturnValue({
      data: [
        {
          id: 900,
          batch_id: 101,
          release_decision_id: 33,
          user_id: 1,
          tenant_id: 1,
          packet_version: "AUD-1.0",
          evidence_level: "Validated",
          contract_evaluation: { status: "within_window" },
          signal_validity: { status: "valid" },
          retuning_axes: { recommended_by_portability: [] },
          packet: {
            batch: { id: 101, batch_id: "BOS-101", species: "BSF", status: "active" },
            signal_batch: {
              id: 11,
              signal_api_version: "SIG-1.0",
              compiled_signal_id: "SIG-READY-001",
              potency: 0.22,
              potency_unit: "SER-equivalent",
              freshness_state: "Fresh",
            },
            control_profile: {
              id: 5,
              name: "CTRL Main",
              version: "CTRL-1.0",
              hal_min: 1,
              hal_max: 2,
              mtt: 4,
            },
            boundary_ledger: null,
            release_decision: {
              decision: "PASS",
              reason_codes: [],
              blocking_factors: [],
              warning_factors: ["thermal_drift_watch"],
              passed_checks: ["signal_valid"],
              trigger_metrics: { decision_confidence: 0.91 },
              rationale: "Release is supported.",
            },
            portability_audits: [],
            generation_context: {
              schema_version: "BOS-1.0",
              compiled_at: "2026-04-16T00:10:00Z",
              compiled_by_user_id: 1,
              hash: "abc",
            },
          },
          generated_at: "2026-04-16T00:10:00Z",
          created_at: "2026-04-16T00:10:00Z",
        },
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    usePortabilityAuditsMock.mockReturnValue({
      data: [
        {
          id: 51,
          signal_batch_id: 11,
          executor_profile_id: 7,
          locality_profile_id: 8,
          user_id: 1,
          tenant_id: 1,
          outcome: "PASS_WITH_RETUNING",
          retuning_required: true,
          override_outcome: null,
          notes: "Tighten HAL before the next run.",
          trigger_metrics: { hal_margin: 0.12 },
          created_at: "2026-04-16T00:12:00Z",
          recommended_outcome: "PASS_WITH_RETUNING",
          rationale: "The signal can transfer, but portability risk remains elevated around HAL.",
          recommended_action: "Retune HAL before formal release.",
          requires_requalification: false,
          retuning_axes: ["HAL"],
          retuning_magnitude: 0.12,
          portability_score: 0.82,
        },
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    usePortabilityRecommendationMock.mockReturnValue({
      data: {
        signal_batch_id: 11,
        executor_profile_id: 7,
        locality_profile_id: 8,
        recommended_outcome: "PASS_WITH_RETUNING",
        rationale: "The signal can transfer, but portability risk remains elevated around HAL.",
        recommended_action: "Retune HAL before formal release.",
        requires_requalification: false,
        retuning_axes: ["HAL"],
        retuning_magnitude: 0.12,
        override_outcome: null,
        portability_score: 0.82,
      },
      isLoading: false,
    });
    useVisionDetectionMock.mockReturnValue({
      data: null,
      isPending: false,
      mutate: vi.fn(),
    });
    useVisionRunsMock.mockReturnValue({
      data: [],
      isLoading: false,
    });
    useAttachVisionObservationMock.mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    });

    useCompileSignalMock.mockReturnValue(mutationStub());
    useRefreshSignalMock.mockReturnValue(mutationStub());
    useEvaluateReleaseMock.mockReturnValue(mutationStub());
    useExportAuditPacketMock.mockReturnValue(mutationStub());
  });

  it("renders the signal lab shell and focused operator controls", () => {
    const html = renderToStaticMarkup(<SignalLabPage />);

    expect(html).toContain("Compile, inspect, and qualify the handover signal");
    expect(html).toContain("Lab controls");
    expect(html).toContain("Selected batch");
    expect(html).toContain("BOS-101");
    expect(html).toContain("Operator decision panel");
    expect(html).toContain("Vision observation review");
    expect(html).toContain("Operator review only");
    expect(html).toContain("Current release posture");
    expect(html).toContain("Next best actions card Release is currently blocked | Retune portability before release");
    expect(html).toContain("Retune the control profile or compile a signal that fits the dose window.");
    expect(html).toContain("Contract and executor");
    expect(html).toContain("Portability recommendation card");
    expect(html).toContain("The signal can transfer, but portability risk remains elevated around HAL.");
    expect(html).toContain("Retune HAL before formal release.");
    expect(html).toContain("Current decision posture");
    expect(html).toContain("Compile signal");
    expect(html).toContain("Evaluate release");
    expect(html).toContain("Open decision console");
    expect(html).toContain("Portability evidence rail");
    expect(html).toContain("Audit export card true");
    expect(html).toContain("Signal supervisor panel SIG-READY-001");
    expect(html).toContain("Tighten HAL before the next run.");
    expect(html).toContain("Brain operator context card");
  });
});
