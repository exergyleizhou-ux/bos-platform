import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  useCodeSessionsMock,
  useCreateCodeSessionMock,
  useCodeOrchestrationMock,
  useCodeRuntimeMock,
  useExecuteNextAutomationActionMock,
  useCodeSessionMock,
  useCodeSessionEventsMock,
  useUpdateCodeSessionMock,
  useLocalStorageMock,
  navigateMock,
  invalidateQueriesMock,
} = vi.hoisted(() => ({
  useCodeSessionsMock: vi.fn(),
  useCreateCodeSessionMock: vi.fn(),
  useCodeOrchestrationMock: vi.fn(),
  useCodeRuntimeMock: vi.fn(),
  useExecuteNextAutomationActionMock: vi.fn(),
  useCodeSessionMock: vi.fn(),
  useCodeSessionEventsMock: vi.fn(),
  useUpdateCodeSessionMock: vi.fn(),
  useLocalStorageMock: vi.fn(),
  navigateMock: vi.fn(),
  invalidateQueriesMock: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
  useSearchParams: () => [new URLSearchParams(), vi.fn()],
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    invalidateQueries: invalidateQueriesMock,
  }),
}));

vi.mock("@/hooks/code/useCode", () => ({
  codeKeys: {
    sessions: () => ["code", "sessions"],
    session: (id: number) => ["code", "session", id],
    events: (id: number) => ["code", "events", id],
  },
  useCodeSessions: useCodeSessionsMock,
  useCreateCodeSession: useCreateCodeSessionMock,
  useCodeOrchestration: useCodeOrchestrationMock,
  useCodeRuntime: useCodeRuntimeMock,
  useExecuteNextAutomationAction: useExecuteNextAutomationActionMock,
  useCodeSession: useCodeSessionMock,
  useCodeSessionEvents: useCodeSessionEventsMock,
  useUpdateCodeSession: useUpdateCodeSessionMock,
}));

vi.mock("@/hooks/useLocalStorage", () => ({
  useLocalStorage: useLocalStorageMock,
}));

vi.mock("@/store/authStore", () => ({
  useAuthStore: (selector: (state: { user: { role: string } | null; accessToken: string | null }) => unknown) =>
    selector({
      user: {
        role: "operator",
      },
      accessToken: "token",
    }),
}));

import BOSAssistantV1Page from "@/pages/BOSAssistantV1Page";

function mutationStub() {
  return {
    isPending: false,
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    data: null,
    error: null,
  };
}

describe("BOSAssistantV1Page render", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    useCodeSessionsMock.mockReturnValue({
      data: {
        active_session_id: null,
        items: [],
      },
      error: null,
    });
    useCreateCodeSessionMock.mockReturnValue(mutationStub());
    useCodeOrchestrationMock.mockReturnValue({
      data: {
        automation_ready: false,
        next_automation_action: null,
      },
    });
    useCodeRuntimeMock.mockReturnValue({
      data: {
        workspace_id: 1,
        runtime_state: {
          id: 1,
          workspace_id: 1,
          heartbeat_enabled: true,
          memory_enabled: true,
          reflections_enabled: true,
          last_heartbeat_decision: "run",
          last_heartbeat_at: null,
          last_memory_sync_at: null,
          last_reflection_at: null,
          last_compressed_turn_index: null,
          runtime_metrics: {
            workflow_mode: "recovery",
            workflow_skills: ["bos-systematic-debugging"],
            workflow_rationale: ["Recovery evidence is active, so debugging and verification gating should lead."],
            next_autonomy_objective: "Continue recovery task #11.",
            last_recovery_task_id: 11,
            last_recovery_failure_class: "verification_failed",
            provider_pause_until: "2026-04-17T08:30:00+08:00",
            experience_quality: {
              posture: "emerging",
              score: 3,
              notes: ["Project brain contains durable context beyond the default scaffold."],
            },
          },
          created_at: null,
          updated_at: null,
        },
        automation_jobs: [],
        active_subagents: [],
        pending_reflections: 0,
      },
    });
    useExecuteNextAutomationActionMock.mockReturnValue(mutationStub());
    useCodeSessionMock.mockReturnValue({
      data: null,
    });
    useCodeSessionEventsMock.mockReturnValue({
      data: {
        items: [],
      },
    });
    useUpdateCodeSessionMock.mockReturnValue(mutationStub());
    useLocalStorageMock.mockImplementation((_key: string, initialValue: unknown) => [
      initialValue,
      vi.fn(),
      vi.fn(),
    ]);
  });

  it("renders the assistant empty-state surface with key operator copy", () => {
    const html = renderToStaticMarkup(<BOSAssistantV1Page />);

    expect(html).toContain("BOS Assistant");
    expect(html).toContain("BOS is here.");
    expect(html).toContain("Threads");
    expect(html).toContain("Ask BOS for the next move");
    expect(html).toContain("Use this page for conversation only.");
    expect(html).toContain("Message BOS");
    expect(html).toContain("Ask BOS what matters, what changed, or what should happen next.");
    expect(html).toContain("Runtime");
    expect(html).toContain("New chat");
  });

  it("renders the visible recovery action label when assistant automation is safe", () => {
    useCodeSessionsMock.mockReturnValue({
      data: {
        active_session_id: 11,
        items: [
          {
            id: 11,
            tenant_id: 1,
            user_id: 1,
            workspace_id: 1,
            provider: "openai",
            model: "gpt-5.4-mini",
            permission_mode: "workspace-write",
            title: "Recovery thread",
            session_branch: "boscode/tenant-1/session-11",
            session_status: "blocked",
            verification_status: "failed",
            token_usage: null,
            estimated_cost: null,
            created_at: null,
            updated_at: null,
          },
        ],
      },
      error: null,
    });
    useCodeSessionMock.mockReturnValue({
      data: {
        session: {
          id: 11,
          tenant_id: 1,
          user_id: 1,
          workspace_id: 1,
          provider: "openai",
          model: "gpt-5.4-mini",
          permission_mode: "workspace-write",
          title: "Recovery thread",
          session_branch: "boscode/tenant-1/session-11",
          session_status: "blocked",
          verification_status: "failed",
          token_usage: null,
          estimated_cost: null,
          created_at: null,
          updated_at: null,
        },
        workspace: {} as never,
        lease: null,
        turns: [],
        tool_calls: [],
        latest_event: null,
        memory_snapshots: [],
        reflection_runs: [],
        subagent_runs: [],
      },
    });
    useCodeOrchestrationMock.mockReturnValue({
      data: {
        automation_ready: true,
        next_automation_action: "reset_session_ready",
      },
    });

    const html = renderToStaticMarkup(<BOSAssistantV1Page />);

    expect(html).toContain("Reset runtime");
  });
});
