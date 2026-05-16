import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  useBatchMock,
  useDeleteBatchMock,
  useBatchGuidanceMock,
  useCompileSignalMock,
  useEvaluateReleaseMock,
  useExportAuditPacketMock,
  useNativeModelRunsMock,
  useRefreshSignalMock,
  useComputeSERFromBatchMock,
  useSERResultMock,
  navigateMock,
  paramsMock,
} = vi.hoisted(() => ({
  useBatchMock: vi.fn(),
  useDeleteBatchMock: vi.fn(),
  useBatchGuidanceMock: vi.fn(),
  useCompileSignalMock: vi.fn(),
  useEvaluateReleaseMock: vi.fn(),
  useExportAuditPacketMock: vi.fn(),
  useNativeModelRunsMock: vi.fn(),
  useRefreshSignalMock: vi.fn(),
  useComputeSERFromBatchMock: vi.fn(),
  useSERResultMock: vi.fn(),
  navigateMock: vi.fn(),
  paramsMock: { id: "42" },
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
  useParams: () => paramsMock,
}));

vi.mock("@/hooks/useBatches", () => ({
  useBatch: useBatchMock,
  useDeleteBatch: useDeleteBatchMock,
}));

vi.mock("@/hooks/useBos", () => ({
  useBatchGuidance: useBatchGuidanceMock,
  useCompileSignal: useCompileSignalMock,
  useEvaluateRelease: useEvaluateReleaseMock,
  useExportAuditPacket: useExportAuditPacketMock,
  useNativeModelRuns: useNativeModelRunsMock,
  useRefreshSignal: useRefreshSignalMock,
}));

vi.mock("@/hooks/useSER", () => ({
  useComputeSERFromBatch: useComputeSERFromBatchMock,
  useSERResult: useSERResultMock,
}));

vi.mock("@/components/bos/AuditExportCard", () => ({
  AuditExportCard: () => <div>Audit export card</div>,
}));
vi.mock("@/components/bos/MechanisticContextCard", () => ({
  MechanisticContextCard: () => <div>Mechanistic context card</div>,
}));
vi.mock("@/components/bos/NativeModelRunsCard", () => ({
  NativeModelRunsCard: () => <div>Native model runs card</div>,
}));
vi.mock("@/components/bos/NextBestActionsCard", () => ({
  NextBestActionsCard: () => <div>Next best actions card</div>,
}));
vi.mock("@/components/bos/SignalCompilerPanel", () => ({
  SignalCompilerPanel: () => <div>Signal compiler panel</div>,
}));
vi.mock("@/components/bos/SignalSupervisorPanel", () => ({
  SignalSupervisorPanel: () => <div>Signal supervisor panel</div>,
}));
vi.mock("@/components/bos/SupervisorHistoryCard", () => ({
  SupervisorHistoryCard: () => <div>Supervisor history card</div>,
}));
vi.mock("@/components/bos/SupervisorSnapshotCard", () => ({
  SupervisorSnapshotCard: () => <div>Supervisor snapshot card</div>,
}));
vi.mock("@/components/ui/Modal", () => ({
  Modal: () => null,
}));

import BatchDetailPage from "@/pages/BatchDetailPage";

function mutationStub() {
  return {
    isPending: false,
    mutate: vi.fn(),
  };
}

describe("BatchDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    useBatchGuidanceMock.mockReturnValue({ data: null, isLoading: false });
    useDeleteBatchMock.mockReturnValue(mutationStub());
    useCompileSignalMock.mockReturnValue(mutationStub());
    useEvaluateReleaseMock.mockReturnValue(mutationStub());
    useExportAuditPacketMock.mockReturnValue(mutationStub());
    useNativeModelRunsMock.mockReturnValue({ data: [], isLoading: false });
    useRefreshSignalMock.mockReturnValue(mutationStub());
    useComputeSERFromBatchMock.mockReturnValue(mutationStub());
    useSERResultMock.mockReturnValue({ data: null });

    useBatchMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        id: 42,
        batch_id: "BOS-DEMO-042",
        species: "BSF",
        status: "completed",
        dm_in: 10,
        dm_out: 4,
        n_in: 1,
        n_larvae: 0.5,
        n_frass: 0.3,
        ash_in: null,
        ash_out: null,
        fat_in: null,
        fat_out: null,
        temperature: 28,
        moisture: 66,
        feed_rate: 1.2,
        density: 4.1,
        score: null,
        operator: null,
        notes: null,
        batch_date: null,
        created_at: "2026-04-16T00:00:00Z",
        updated_at: "2026-04-16T00:00:00Z",
        bos: {
          signal_batch: null,
          control_profile: null,
          boundary_ledger: null,
          release_decision: null,
          audit_packet: {
            id: 1,
            batch_id: 42,
            release_decision_id: null,
            user_id: 1,
            tenant_id: 1,
            packet_version: "AUD-1.0",
            evidence_level: "Validated",
            contract_evaluation: null,
            signal_validity: null,
            retuning_axes: null,
            generated_at: "2026-04-16T01:00:00Z",
            created_at: "2026-04-16T01:00:00Z",
            packet: {
              batch: { id: 42, batch_id: "BOS-DEMO-042", species: "BSF", status: "completed" },
              signal_batch: null,
              control_profile: null,
              boundary_ledger: null,
              release_decision: null,
              portability_audits: [
                {
                  id: 51,
                  executor_profile_id: 9,
                  locality_profile_id: null,
                  executor_name: "Executor 9",
                  locality_name: null,
                  outcome: "FAIL",
                  retuning_required: true,
                  recommended_outcome: "FAIL",
                  rationale: "The current signal and portability context remain outside the safe transfer envelope.",
                  recommended_action: "Requalify the signal under a different executor or locality before release.",
                  requires_requalification: true,
                  retuning_axes: ["executor_hal"],
                  retuning_magnitude: 0.33,
                  portability_score: 0.22,
                  trigger_metrics: { hal_margin: 0.28 },
                },
              ],
              native_model_stack: null,
              native_forecast_evidence: {
                model_key: "insecta",
                modality: "vision",
                evidence_tier: "bootstrap_public_vision",
                evidence_label: "Bootstrap public vision",
                evidence_summary: "3 detections · top label 鞘翅目_步甲科,Carabidae",
                execution_mode: "insecta_bootstrap_live",
                recorded_at: "2026-04-16T01:00:00Z",
                artifact_path: "C:/tmp/runs/insecta.json",
                top_label: "鞘翅目_步甲科,Carabidae",
                top_candidates: [
                  "鞘翅目_步甲科,Carabidae",
                  "鞘翅目_步甲科_麻步甲,Carabus brandti",
                ],
                bbox_summary: "544, 289, 546, 303",
                is_live: true,
              },
              generation_context: {
                schema_version: "BOS-1.0",
                compiled_at: "2026-04-16T01:00:00Z",
                compiled_by_user_id: 1,
                source_ids: {
                  signal_batch_id: null,
                  control_profile_id: null,
                  boundary_ledger_id: null,
                  release_decision_id: null,
                  portability_audit_ids: [],
                },
                hash: "hash",
              },
            },
          },
          portability_audits: [
            {
              id: 51,
              signal_batch_id: 11,
              executor_profile_id: 9,
              locality_profile_id: null,
              user_id: 1,
              tenant_id: 1,
              outcome: "FAIL",
              retuning_required: true,
              override_outcome: null,
              notes: "Locality drift exceeded the current release envelope.",
              trigger_metrics: { hal_margin: 0.28 },
              created_at: "2026-04-16T01:00:00Z",
              recommended_outcome: "FAIL",
              rationale: "The current signal and portability context remain outside the safe transfer envelope.",
              recommended_action: "Requalify the signal under a different executor or locality before release.",
              requires_requalification: true,
              retuning_axes: ["executor_hal"],
              retuning_magnitude: 0.33,
              portability_score: 0.22,
            },
          ],
          compile_status: "not_started",
          latest_signal_status: "missing",
          latest_native_run: {
            modelKey: "insecta",
            modality: "vision",
            evidenceTier: "bootstrap_public_vision",
            evidenceLabel: "Bootstrap public vision",
            evidenceSummary: "3 detections · top label 鞘翅目_步甲科,Carabidae",
            executionMode: "insecta_bootstrap_live",
            recordedAt: "2026-04-16T01:00:00Z",
            artifactPath: "C:/tmp/runs/insecta.json",
            metricName: null,
            predictionHorizon: null,
            forecastPreview: [],
            detectionCount: 3,
            topLabel: "鞘翅目_步甲科,Carabidae",
            topCandidates: [
              "鞘翅目_步甲科,Carabidae",
              "鞘翅目_步甲科_麻步甲,Carabus brandti",
            ],
            bboxSummary: "544, 289, 546, 303",
            isLive: true,
          },
        },
      },
      refetch: vi.fn(),
    });
  });

  it("renders native visual evidence in the batch command rail", () => {
    const html = renderToStaticMarkup(<BatchDetailPage />);

    expect(html).toContain("Latest native evidence");
    expect(html).toContain("Bootstrap public vision");
    expect(html).toContain("鞘翅目_步甲科,Carabidae");
    expect(html).toContain("544, 289, 546, 303");
    expect(html).toContain("Native model runs card");
  });

  it("renders explicit portability requalification guidance from the packet", () => {
    const html = renderToStaticMarkup(<BatchDetailPage />);

    expect(html).toContain("Requalification required");
    expect(html).toContain("outside the safe transfer envelope");
    expect(html).toContain("Requalify the signal under a different executor or locality before release.");
  });

  it("renders next-best-action CTA labels for the operator", () => {
    const html = renderToStaticMarkup(<BatchDetailPage />);

    expect(html).toContain("Open signal lab");
  });

  it("renders the operator decision panel with primary actions", () => {
    const html = renderToStaticMarkup(<BatchDetailPage />);

    expect(html).toContain("Operator decision panel");
    expect(html).toContain("Primary actions");
    expect(html).toContain("Evaluate release");
    expect(html).toContain("Signal");
    expect(html).toContain("Control");
    expect(html).toContain("Portability");
    expect(html).toContain("Audit packet");
    expect(html).toContain("Export audit packet");
    expect(html).toContain("Edit batch");
    expect(html).toContain("Suggested action queue");
    expect(html).toContain("Signal evidence");
    expect(html).toContain("Decision confidence");
    expect(html).toContain("Portability score");
    expect(html).toContain("Packet version");
    expect(html).toContain("Evidence rail");
    expect(html).toContain("Deep evidence rail");
    expect(html).toContain("Packet and signal footing");
    expect(html).toContain("Operating context");
    expect(html).toContain("Packet decision and portability");
    expect(html).toContain("Do not release");
  });
});
