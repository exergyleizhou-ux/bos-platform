import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { useBrainRuntimeMock, useUpdateBrainRuntimeDocumentMock, navigateMock } = vi.hoisted(() => ({
  useBrainRuntimeMock: vi.fn(),
  useUpdateBrainRuntimeDocumentMock: vi.fn(),
  navigateMock: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
}));

vi.mock("@/hooks/useBos", () => ({
  useBrainRuntime: useBrainRuntimeMock,
  useUpdateBrainRuntimeDocument: useUpdateBrainRuntimeDocumentMock,
}));

import BrainDashboardPage from "@/pages/BrainDashboardPage";

describe("BrainDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useUpdateBrainRuntimeDocumentMock.mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    });
    useBrainRuntimeMock.mockReturnValue({
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
      data: {
        root_path: ".agents/runtime",
        total_line_count: 18,
        last_updated_at: "2026-04-16T12:00:00Z",
        documents: [
          {
            key: "project_brain",
            title: "Project Brain",
            relative_path: ".agents/runtime/project-brain.md",
            content: "# Project Brain\n\n## Mission\n- Keep the runtime schema explicit.\n\n## Current Focus\n- Harden the project brain.\n\n## Next Slices\n- Surface structure drift.\n\n## Stable Facts\n- Use the reconciled repo.\n\n## Constraints\n- Preserve required headings.\n\n## Known Good Commands\n- npm run test -- BrainDashboardPage\n\n## Repeated Pitfalls\n- Free-form notes break summaries.",
            updated_at: "2026-04-16T12:00:00Z",
            line_count: 20,
            is_missing: false,
          },
          {
            key: "decision_journal",
            title: "Decision Journal",
            relative_path: ".agents/runtime/decision-journal.md",
            content: "# Decision Journal\n\n## Recent Decisions\n- Chose the next slice.\n\n## Plan Changes\n- Shifted toward schema validation.",
            updated_at: "2026-04-16T11:50:00Z",
            line_count: 6,
            is_missing: false,
          },
          {
            key: "evolution_log",
            title: "Evolution Log",
            relative_path: ".agents/runtime/evolution-log.md",
            content: "# Evolution Log\n\n## Active Heuristics\n- Verify before widening scope.\n\n## Recent Learnings\n- Runtime memory needs a contract.",
            updated_at: "2026-04-16T11:40:00Z",
            line_count: 6,
            is_missing: false,
          },
          {
            key: "run_ledger",
            title: "Autonomy Run Ledger",
            relative_path: ".agents/runtime/run-ledger.md",
            content: "# Autonomy Run Ledger\n\n## Latest Run\n- Slice: Brain dashboard\n- Outcome: Verified\n- Verification: frontend checks\n- Remaining Risk: release mapping still pending\n- Next Step: connect release center\n- Target Surface: release\n- Target ID: 900\n- Target Route: /bos/console?auditPacketId=900\n\n## Recent Runs\n- 2026-04-16 12:00 | Batch 101 signal review | Verified | Added editor controls | signal_lab | 101 | /bos/signal-lab?batchId=101\n- 2026-04-16 13:30 | Operator context card | Verified | Mapped brain into dashboard | brain |  | /bos/brain",
            updated_at: "2026-04-16T12:10:00Z",
            line_count: 13,
            is_missing: false,
          },
        ],
      },
    });
  });

  it("renders the brain dashboard shell and runtime documents", () => {
    const html = renderToStaticMarkup(<BrainDashboardPage />);

    expect(html).toContain("Brain Dashboard / Evolution Inspector");
    expect(html).toContain("Runtime memory surfaces");
    expect(html).toContain("Project Brain");
    expect(html).toContain("Decision Journal");
    expect(html).toContain("Evolution Log");
    expect(html).toContain("Autonomy Run Ledger");
    expect(html).toContain(".agents/runtime");
    expect(html).toContain("Persistent memory");
    expect(html).toContain("Open orchestrator");
    expect(html).toContain("Save changes");
    expect(html).toContain("Repair structure");
    expect(html).toContain("Latest autonomous run");
    expect(html).toContain("Run artifact quality");
    expect(html).toContain("Complete");
    expect(html).toContain("Recent autonomous runs");
    expect(html).toContain("Operator context card");
    expect(html).toContain("Open Signal Lab for Batch 101");
    expect(html).toContain("Open Brain Dashboard");
  });
});
