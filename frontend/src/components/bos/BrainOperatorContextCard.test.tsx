import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { useBrainRuntimeMock, navigateMock } = vi.hoisted(() => ({
  useBrainRuntimeMock: vi.fn(),
  navigateMock: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
}));

vi.mock("@/hooks/useBos", () => ({
  useBrainRuntime: useBrainRuntimeMock,
}));

import { BrainOperatorContextCard } from "@/components/bos/BrainOperatorContextCard";

describe("BrainOperatorContextCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useBrainRuntimeMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        root_path: ".agents/runtime",
        total_line_count: 20,
        last_updated_at: "2026-04-16T12:00:00Z",
        documents: [
          {
            key: "project_brain",
            title: "Project Brain",
            relative_path: ".agents/runtime/project-brain.md",
            content: "# Project Brain\n\n## Current Focus\n- Tighten release loop\n- Qualify the signal handover\n\n## Next Slices\n- Improve brain memory inspector\n- Build release trust summary\n",
            updated_at: "2026-04-16T12:00:00Z",
            line_count: 6,
            is_missing: false,
          },
          {
            key: "decision_journal",
            title: "Decision Journal",
            relative_path: ".agents/runtime/decision-journal.md",
            content: "# Decision Journal\n\n## Recent Decisions\n- Prioritize visible closed loops\n",
            updated_at: "2026-04-16T11:00:00Z",
            line_count: 4,
            is_missing: false,
          },
          {
            key: "evolution_log",
            title: "Evolution Log",
            relative_path: ".agents/runtime/evolution-log.md",
            content: "# Evolution Log\n\n## Active Heuristics\n- Verify before widening scope\n",
            updated_at: "2026-04-16T10:00:00Z",
            line_count: 4,
            is_missing: false,
          },
          {
            key: "run_ledger",
            title: "Autonomy Run Ledger",
            relative_path: ".agents/runtime/run-ledger.md",
            content: "# Autonomy Run Ledger\n\n## Latest Run\n- Slice: Batch 101 signal review\n- Outcome: Verified\n- Verification: type-check and vitest\n- Remaining Risk: release mapping still pending\n- Next Step: connect audit packet 900 to release center\n- Target Surface: signal_lab\n- Target ID: 101\n- Target Route: /bos/signal-lab?batchId=101\n",
            updated_at: "2026-04-16T12:30:00Z",
            line_count: 11,
            is_missing: false,
          },
        ],
      },
    });
  });

  it("renders current focus, next slices, and heuristics", () => {
    const html = renderToStaticMarkup(<BrainOperatorContextCard />);

    expect(html).toContain("Autonomy context");
    expect(html).toContain("Tighten release loop");
    expect(html).toContain("Improve brain memory inspector");
    expect(html).toContain("Suggested surfaces");
    expect(html).toContain("Signal Lab");
    expect(html).toContain("Release Center");
    expect(html).toContain("Verify before widening scope");
    expect(html).toContain("Latest autonomous run");
    expect(html).toContain("Run inspector");
    expect(html).toContain("Run artifact complete");
    expect(html).toContain("type-check and vitest");
    expect(html).toContain("connect audit packet 900");
    expect(html).toContain("Priority action");
    expect(html).toContain("Open Signal Lab for Batch 101");
    expect(html).toContain("Open brain dashboard");
  });

  it("specializes focus blocks for release mode", () => {
    const html = renderToStaticMarkup(<BrainOperatorContextCard mode="release" />);

    expect(html).toContain("Release-adjacent focus");
    expect(html).toContain("Tighten release loop");
    expect(html).toContain("Recent decisions");
    expect(html).toContain("Priority: Audit Packet 900");
    expect(html).toContain("Open release center");
  });

  it("specializes focus blocks for signal mode", () => {
    const html = renderToStaticMarkup(<BrainOperatorContextCard mode="signal" />);

    expect(html).toContain("Signal-adjacent focus");
    expect(html).toContain("Qualify the signal handover");
    expect(html).toContain("Next lab slices");
    expect(html).toContain("Priority: Signal Lab for Batch 101");
    expect(html).toContain("Open signal lab");
  });

  it("specializes focus blocks for assistant and orchestrator modes", () => {
    const assistantHtml = renderToStaticMarkup(<BrainOperatorContextCard mode="assistant" />);
    const orchestratorHtml = renderToStaticMarkup(<BrainOperatorContextCard mode="orchestrator" />);

    expect(assistantHtml).toContain("Thread focus");
    expect(assistantHtml).toContain("Open assistant thread");
    expect(orchestratorHtml).toContain("Orchestration focus");
    expect(orchestratorHtml).toContain("Open orchestrator");
  });
});
