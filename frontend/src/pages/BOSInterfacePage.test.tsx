import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  useSignalBatchesMock,
  useControlProfilesMock,
  useLocalityProfilesMock,
  useExecutorProfilesMock,
  usePortabilityAuditsMock,
  useAuditPacketsMock,
  useReleaseDecisionsMock,
  useNativeModelsMock,
  usePortabilityRecommendationMock,
  useSpeciesCatalogMock,
  useFeedstocksCatalogMock,
  useManuscriptCampaignsMock,
  useCreateSignalBatchMock,
  useCreateControlProfileMock,
  useCreateLocalityProfileMock,
  useCreateExecutorProfileMock,
  useCreatePortabilityAuditMock,
  useEvaluateReleaseMock,
  useExportAuditPacketMock,
  useCompileSignalMock,
  useRefreshSignalMock,
  useBatchListMock,
  navigateMock,
} = vi.hoisted(() => ({
  useSignalBatchesMock: vi.fn(),
  useControlProfilesMock: vi.fn(),
  useLocalityProfilesMock: vi.fn(),
  useExecutorProfilesMock: vi.fn(),
  usePortabilityAuditsMock: vi.fn(),
  useAuditPacketsMock: vi.fn(),
  useReleaseDecisionsMock: vi.fn(),
  useNativeModelsMock: vi.fn(),
  usePortabilityRecommendationMock: vi.fn(),
  useSpeciesCatalogMock: vi.fn(),
  useFeedstocksCatalogMock: vi.fn(),
  useManuscriptCampaignsMock: vi.fn(),
  useCreateSignalBatchMock: vi.fn(),
  useCreateControlProfileMock: vi.fn(),
  useCreateLocalityProfileMock: vi.fn(),
  useCreateExecutorProfileMock: vi.fn(),
  useCreatePortabilityAuditMock: vi.fn(),
  useEvaluateReleaseMock: vi.fn(),
  useExportAuditPacketMock: vi.fn(),
  useCompileSignalMock: vi.fn(),
  useRefreshSignalMock: vi.fn(),
  useBatchListMock: vi.fn(),
  navigateMock: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
  useSearchParams: () => [new URLSearchParams()],
}));

vi.mock("@/hooks/useBos", () => ({
  useSignalBatches: useSignalBatchesMock,
  useControlProfiles: useControlProfilesMock,
  useLocalityProfiles: useLocalityProfilesMock,
  useExecutorProfiles: useExecutorProfilesMock,
  usePortabilityAudits: usePortabilityAuditsMock,
  useAuditPackets: useAuditPacketsMock,
  useReleaseDecisions: useReleaseDecisionsMock,
  useNativeModels: useNativeModelsMock,
  usePortabilityRecommendation: usePortabilityRecommendationMock,
  useSpeciesCatalog: useSpeciesCatalogMock,
  useFeedstocksCatalog: useFeedstocksCatalogMock,
  useManuscriptCampaigns: useManuscriptCampaignsMock,
  useCreateSignalBatch: useCreateSignalBatchMock,
  useCreateControlProfile: useCreateControlProfileMock,
  useCreateLocalityProfile: useCreateLocalityProfileMock,
  useCreateExecutorProfile: useCreateExecutorProfileMock,
  useCreatePortabilityAudit: useCreatePortabilityAuditMock,
  useEvaluateRelease: useEvaluateReleaseMock,
  useExportAuditPacket: useExportAuditPacketMock,
  useCompileSignal: useCompileSignalMock,
  useRefreshSignal: useRefreshSignalMock,
}));

vi.mock("@/hooks/useBatches", () => ({
  useBatchList: useBatchListMock,
}));

vi.mock("@/providers/I18nProvider", () => ({
  useI18n: () => ({
    t: (value: string) => value,
  }),
}));

vi.mock("@/components/ui/Modal", () => ({
  Modal: ({
    open,
    title,
    children,
  }: {
    open: boolean;
    title: string;
    children: ReactNode;
  }) => (open ? <section>{title}{children}</section> : null),
}));

vi.mock("@/components/bos/MechanisticContextCard", () => ({
  MechanisticContextCard: () => <div>Mechanistic context card</div>,
}));
vi.mock("@/components/bos/NativeModelRuntimeCard", () => ({
  NativeModelRuntimeCard: () => <div>Native model runtime card</div>,
}));
vi.mock("@/components/bos/NativeModelStackCard", () => ({
  NativeModelStackCard: () => <div>Native model stack card</div>,
}));
vi.mock("@/components/bos/PortabilityRecommendationCard", () => ({
  PortabilityRecommendationCard: () => <div>Portability recommendation card</div>,
}));
vi.mock("@/components/bos/AuditExportCard", () => ({
  AuditExportCard: ({ hasAuditPacket }: { hasAuditPacket: boolean }) => (
    <div>Audit export card {String(hasAuditPacket)}</div>
  ),
}));
vi.mock("@/components/bos/SupervisorHistoryCard", () => ({
  SupervisorHistoryCard: () => <div>Supervisor history card</div>,
}));
vi.mock("@/components/bos/SignalSupervisorPanel", () => ({
  SignalSupervisorPanel: () => <div>Signal supervisor panel</div>,
}));
vi.mock("@/components/bos/SupervisorSnapshotCard", () => ({
  SupervisorSnapshotCard: () => <div>Supervisor snapshot card</div>,
}));

import BOSInterfacePage from "@/pages/BOSInterfacePage";

function mutationStub() {
  return {
    isPending: false,
    mutateAsync: vi.fn(),
    mutate: vi.fn(),
  };
}

describe("BOSInterfacePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

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
          qc_markers: null,
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
    useControlProfilesMock.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() });
    useLocalityProfilesMock.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() });
    useExecutorProfilesMock.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() });
    usePortabilityAuditsMock.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() });
    useReleaseDecisionsMock.mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() });
    useBatchListMock.mockReturnValue({
      data: {
        items: [{ id: 101 }],
      },
    });
    useNativeModelsMock.mockReturnValue({
      data: {
        version: "1",
        catalog_version: "native-1",
        verified_on: "2026-04-16",
        models: [],
        compositions: [],
        recommendations: [],
        rollout: [],
      },
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
          retuning_axes: {
            recommended_by_portability: [
              {
                recommended_outcome: "PASS_WITH_RETUNING",
                rationale: "The signal can transfer, but portability risk remains elevated around HAL.",
                recommended_action: "Retune HAL before formal release.",
                requires_requalification: false,
                retuning_axes: ["HAL"],
              },
            ],
          },
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
            control_profile: null,
            boundary_ledger: null,
            release_decision: {
              decision: "PASS",
              reason_codes: [],
              blocking_factors: [],
              warning_factors: ["thermal_drift_watch"],
              passed_checks: ["signal_valid"],
              trigger_metrics: {},
              decision_confidence: 0.91,
              rationale: "Release is supported under the current contract and signal state.",
            },
            portability_audits: [],
            native_model_stack: null,
            generation_context: {
              schema_version: "BOS-1.0",
              compiled_at: "2026-04-16T00:10:00Z",
              compiled_by_user_id: 1,
              source_ids: {
                signal_batch_id: 11,
                control_profile_id: null,
                boundary_ledger_id: null,
                release_decision_id: 33,
                portability_audit_ids: [],
              },
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
    usePortabilityRecommendationMock.mockReturnValue({
      data: null,
      isLoading: false,
    });
    useSpeciesCatalogMock.mockReturnValue({
      data: {
        species: [
          {
            code: "BSF",
            scientific_name: "Hermetia illucens",
            common_name: "Black Soldier Fly",
            aliases: ["BSFL"],
            source_basis: "literature+bos_default",
            notes: "Reference executor",
            references: ["ref-1"],
            ser_typical: 0.22,
            development_days: 14,
            protein_content: 42,
            fat_content: 35,
          },
          {
            code: "MW",
            scientific_name: "Tenebrio molitor",
            common_name: "Yellow Mealworm",
            aliases: ["YMW"],
            source_basis: "literature+manuscript",
            notes: "Upstream compiler",
            references: ["ref-2"],
            ser_typical: 0.18,
            development_days: 60,
            protein_content: 52,
            fat_content: 28,
          },
        ],
        count: 2,
      },
      isLoading: false,
    });
    useFeedstocksCatalogMock.mockReturnValue({
      data: {
        feedstocks: [
          {
            key: "distillers_grains",
            display_name: "Distillers grains",
            category: "agro-industrial residue",
            typical_cn_min: 10,
            typical_cn_max: 20,
            moisture_risk: "medium",
            contamination_risk: "low",
            lignocellulose_severity: "medium",
            suitability_notes: "Core manuscript feedstock",
            evidence_basis: "manuscript+public benchmark literature",
            references: ["ref-3"],
          },
          {
            key: "sewage_sludge",
            display_name: "Sewage sludge",
            category: "sludge",
            typical_cn_min: 5,
            typical_cn_max: 10,
            moisture_risk: "high",
            contamination_risk: "critical",
            lignocellulose_severity: "low",
            suitability_notes: "High contamination risk",
            evidence_basis: "manuscript campaign+public risk literature",
            references: ["ref-4"],
          },
        ],
        count: 2,
      },
      isLoading: false,
    });
    useManuscriptCampaignsMock.mockReturnValue({
      data: {
        campaigns: [
          {
            key: "core_tm_pb_distillers_grains",
            title: "Core TM→PB relay on distillers grains",
            species_chain: ["MW", "PB"],
            feedstocks: ["distillers_grains"],
            campaign_type: "core_validation",
            evidence_level: "manuscript_core",
            summary: "Primary relay validation",
            key_parameters: { ser: 0.68 },
            observed_outputs: {},
            source_anchor: "Abstract + Methods",
            references: ["ref-5"],
          },
        ],
        count: 1,
      },
      isLoading: false,
    });

    useCreateSignalBatchMock.mockReturnValue(mutationStub());
    useCreateControlProfileMock.mockReturnValue(mutationStub());
    useCreateLocalityProfileMock.mockReturnValue(mutationStub());
    useCreateExecutorProfileMock.mockReturnValue(mutationStub());
    useCreatePortabilityAuditMock.mockReturnValue(mutationStub());
    useEvaluateReleaseMock.mockReturnValue(mutationStub());
    useExportAuditPacketMock.mockReturnValue({
      ...mutationStub(),
      variables: undefined,
    });
    useCompileSignalMock.mockReturnValue(mutationStub());
    useRefreshSignalMock.mockReturnValue(mutationStub());
  });

  it("renders the BOS decision center shell and latest decision rail", () => {
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
          contract_evaluation: { status: "review", threshold_breaches: ["dose_window"] },
          signal_validity: { status: "valid" },
          retuning_axes: {
            recommended_by_portability: [
              {
                recommended_outcome: "PASS_WITH_RETUNING",
                retuning_axes: ["HAL"],
              },
            ],
          },
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
            control_profile: null,
            boundary_ledger: null,
            release_decision: {
              decision: "PASS",
              reason_codes: [],
              blocking_factors: [],
              warning_factors: ["thermal_drift_watch"],
              passed_checks: ["signal_valid"],
              trigger_metrics: {},
              decision_confidence: 0.91,
              rationale: "Release is supported under the current contract and signal state.",
            },
            portability_audits: [
              {
                id: 51,
                executor_profile_id: 7,
                locality_profile_id: 8,
                executor_name: "Shanghai Executor",
                locality_name: "Shanghai Site A",
                outcome: "PASS_WITH_RETUNING",
                retuning_required: true,
                recommended_outcome: "PASS_WITH_RETUNING",
                rationale: "The signal can transfer, but portability risk remains elevated around HAL.",
                recommended_action: "Retune HAL before formal release.",
                requires_requalification: false,
                retuning_axes: ["HAL"],
                portability_score: 0.82,
                trigger_metrics: { hal_margin: 0.08 },
              },
            ],
            native_model_stack: null,
            generation_context: {
              schema_version: "BOS-1.0",
              compiled_at: "2026-04-16T00:10:00Z",
              compiled_by_user_id: 1,
              source_mode: "refresh",
              source_ids: {
                signal_batch_id: 11,
                control_profile_id: null,
                boundary_ledger_id: null,
                release_decision_id: 33,
                portability_audit_ids: [51],
              },
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

    const html = renderToStaticMarkup(<BOSInterfacePage />);

    expect(html).toContain("BOS Code Decision Center");
    expect(html).toContain("Signal, contract, release, portability, and audit");
    expect(html).toContain("Decision summary rail");
    expect(html).toContain("Release");
    expect(html).toContain("Release ready");
    expect(html).toContain("Decision confidence");
    expect(html).toContain("Contract status");
    expect(html).toContain("Needs review");
    expect(html).toContain("Signal validity");
    expect(html).toContain("Ready");
    expect(html).toContain("Current portability posture");
    expect(html).toContain("Native model stack card");
    expect(html).toContain("Native model runtime card");
    expect(html).toContain("Mechanistic context card");
    expect(html).toContain("Release with retuning");
    expect(html).toContain("82%");
    expect(html).toContain("Release is possible, but address 1 retuning direction before formal execution.");
    expect(html).toContain("Retune HAL before formal release.");
    expect(html).toContain("Audit export card true");
    expect(html).toContain("Latest packet provenance");
    expect(html).toContain("Threshold breaches");
    expect(html).toContain("dose_window");
    expect(html).toContain("Source refresh");
    expect(html).toContain("Signal batch");
    expect(html).toContain("abc");
    expect(html).toContain("Reference species and feedstocks");
    expect(html).toContain("Black Soldier Fly");
    expect(html).toContain("Distillers grains");
    expect(html).toContain("Manuscript evidence campaigns");
    expect(html).toContain("Primary relay validation");
  });
});
