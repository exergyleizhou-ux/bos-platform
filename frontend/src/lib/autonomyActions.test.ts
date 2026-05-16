import { describe, expect, it } from "vitest";

import { deriveAutonomyPriority } from "@/lib/autonomyActions";

describe("autonomyActions", () => {
  it("derives mode-specific priority actions from runtime docs", () => {
    const docs = [
      {
        key: "project_brain",
        title: "Project Brain",
        relative_path: ".agents/runtime/project-brain.md",
        updated_at: null,
        line_count: 10,
        is_missing: false,
        content: "# Project Brain\n\n## Current Focus\n- Tighten release posture\n\n## Next Slices\n- Batch 101 signal review\n",
      },
      {
        key: "decision_journal",
        title: "Decision Journal",
        relative_path: ".agents/runtime/decision-journal.md",
        updated_at: null,
        line_count: 4,
        is_missing: false,
        content: "# Decision Journal\n\n## Recent Decisions\n- Prioritize release confidence\n",
      },
      {
        key: "evolution_log",
        title: "Evolution Log",
        relative_path: ".agents/runtime/evolution-log.md",
        updated_at: null,
        line_count: 4,
        is_missing: false,
        content: "# Evolution Log\n\n## Active Heuristics\n- Verify before widening scope\n",
      },
      {
        key: "run_ledger",
        title: "Autonomy Run Ledger",
        relative_path: ".agents/runtime/run-ledger.md",
        updated_at: null,
        line_count: 8,
        is_missing: false,
        content: "# Autonomy Run Ledger\n\n## Latest Run\n- Slice: Batch 101 signal review\n- Outcome: Verified\n- Verification: tests\n- Remaining Risk: release mapping still pending\n- Next Step: connect audit packet 900 to release center\n",
      },
    ];

    expect(deriveAutonomyPriority(docs, "signal")?.to).toBe("/bos/signal-lab?batchId=101");
    expect(deriveAutonomyPriority(docs, "release")?.to).toBe("/bos/console?auditPacketId=900");
  });
});
