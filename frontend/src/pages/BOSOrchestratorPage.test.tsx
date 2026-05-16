import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  useQueryMock,
  useMutationMock,
  useLocalStorageMock,
  navigateMock,
} = vi.hoisted(() => ({
  useQueryMock: vi.fn(),
  useMutationMock: vi.fn(),
  useLocalStorageMock: vi.fn(),
  navigateMock: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
  useMutation: useMutationMock,
  useQueryClient: () => ({
    invalidateQueries: vi.fn(),
  }),
}));

vi.mock("@/hooks/useLocalStorage", () => ({
  useLocalStorage: useLocalStorageMock,
}));

vi.mock("@/components/bos/BrainOperatorContextCard", () => ({
  BrainOperatorContextCard: () => <div>Brain operator context card</div>,
}));

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
  },
}));

vi.mock("@/api/assistantApi", () => ({
  assistantApi: {
    listRuns: vi.fn(),
  },
}));

vi.mock("@/api/batchApi", () => ({
  batchApi: {
    stats: vi.fn(),
    list: vi.fn(),
    create: vi.fn(),
  },
}));

vi.mock("@/api/bosApi", () => ({
  bosApi: {
    listSignals: vi.fn(),
    listAuditPackets: vi.fn(),
    getBatchGuidance: vi.fn(),
    evaluateRelease: vi.fn(),
    compileSignal: vi.fn(),
    exportAuditPacket: vi.fn(),
  },
}));

import BOSOrchestratorPage from "@/pages/BOSOrchestratorPage";

function queryStub(data: unknown) {
  return {
    data,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  };
}

function mutationStub() {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    data: null,
  };
}

describe("BOSOrchestratorPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    useLocalStorageMock.mockImplementation((_key: string, initialValue: unknown) => [
      initialValue,
      vi.fn(),
    ]);

    useMutationMock.mockImplementation(() => mutationStub());

    useQueryMock
      .mockReturnValueOnce(queryStub({ status: "ok", environment: "test" }))
      .mockReturnValueOnce(queryStub({ total: 12, by_status: { active: 5, completed: 4 } }))
      .mockReturnValueOnce(
        queryStub({
          items: [{ id: 101, batch_id: "BOS-101", status: "active", created_at: "2026-04-16T00:00:00Z" }],
        }),
      )
      .mockReturnValueOnce(
        queryStub([
          { id: 11, batch_id: 101, signal_api_version: "SIG-1.0", updated_at: "2026-04-16T00:10:00Z" },
        ]),
      )
      .mockReturnValueOnce(
        queryStub([
          { id: 900, batch_id: 101, evidence_level: "Validated", generated_at: "2026-04-16T00:20:00Z" },
        ]),
      )
      .mockReturnValueOnce(
        queryStub([
          {
            run_id: "ARUN-RESEARCH-001",
            parsed_intent: { mode: "research_review" },
            result_summary: {
              final_synthesis: {
                approval_state: "review_required",
                review_packet_snapshot_id: "FARP-RESEARCH-001",
              },
              result_ids: {
                evidence_pack_id: "EVP-RESEARCH-001",
                review_packet_snapshot_id: "FARP-RESEARCH-001",
              },
            },
            evidence_pack_id: "EVP-RESEARCH-001",
            final_synthesis: {
              approval_state: "review_required",
              review_packet_snapshot_id: "FARP-RESEARCH-001",
              debate_turns: [
                {
                  speaker: "Protocol Designer",
                  stance: "Prioritize the controlled small pilot.",
                  challenges: "Keep evidence review-gated.",
                  reply: "Chief Scientist converges on a review-gated pilot.",
                },
              ],
              reasoning_stages: [
                {
                  stage: "Question reframing",
                  status: "complete",
                  readout: "Treat the prompt as a review-gated research prioritization problem.",
                },
                {
                  stage: "Gate posture",
                  status: "review_required",
                  readout: "No external share or validated-default promotion.",
                },
              ],
              evidence_status: [
                {
                  claim: "Preferred pilot lane",
                  status: "candidate_evidence",
                  basis: "Mechanism fit requires source review.",
                  gate: "review_required",
                },
              ],
              experiment_plan: [
                {
                  step: "P1 controlled pilot",
                  design: "Run a small replicated pilot.",
                  gate: "review_required",
                  stop_rule: "Stop on mortality threshold breach.",
                },
              ],
            },
            team_plan: [
              { stage: 1, title: "Chief Scientist", specialist_id: "chief_scientist", lane: "intake" },
              { stage: 2, title: "Protocol Designer", specialist_id: "protocol_designer", lane: "protocol" },
            ],
            handoff_records: [
              {
                handoff_id: "RHAND-001",
                source_specialist: "chief_scientist",
                target_specialist: "protocol_designer",
                status: "recorded",
              },
            ],
            review_verdicts: [{ gate: "scientific_rigor", verdict: "review_required" }],
            action_ledger: [{ action_name: "external.share", status: "requires_confirmation" }],
            created_at: "2026-04-28T00:00:00Z",
          },
        ]),
      );
  });

  it("renders the orchestrator shell with autonomy context and native control room", () => {
    const html = renderToStaticMarkup(<BOSOrchestratorPage />);

    expect(html).toContain("Brain operator context card");
    expect(html).toContain("BOS Orchestrator");
    expect(html).toContain("Native Control Room");
    expect(html).toContain("Native control");
    expect(html).toContain("Embedded workspace");
    expect(html).toContain("Research Review Audit Console");
    expect(html).toContain("Packet / gate register");
    expect(html).toContain("Source review packet: FARP-RESEARCH-001");
    expect(html).toContain("Evidence pack: EVP-RESEARCH-001");
    expect(html).toContain("Research Review DAG");
    expect(html).toContain("Expert debate synthesis");
    expect(html).toContain("Research reasoning timeline");
    expect(html).toContain("Evidence status matrix");
    expect(html).toContain("Controlled pilot plan");
    expect(html).toContain("Question reframing");
    expect(html).toContain("candidate_evidence");
    expect(html).toContain("P1 controlled pilot");
    expect(html).toContain("intake");
    expect(html).toContain("scientific gate");
    expect(html).toContain("evidence audit");
    expect(html).toContain("Handoff Ledger");
    expect(html).toContain("chief_scientist");
    expect(html).toContain("protocol_designer");
    expect(html).toContain("scientific_rigor");
    expect(html).toContain("Recent batches");
    expect(html).toContain("Saved native recipes");
  });
});
