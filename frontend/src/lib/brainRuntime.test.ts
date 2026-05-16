import { describe, expect, it } from "vitest";

import {
  auditBrainRuntimeDocument,
  auditLatestRunDetail,
  buildStructuredRuntimeDocument,
  derivePriorityAction,
  inferBrainRouteFromTarget,
  inferBrainRouteFromText,
  parseBrainDocument,
  parseRecentRunEntry,
  parseLatestRun,
  suggestBrainRoutes,
  summarizeBrainRuntimeDocuments,
} from "@/lib/brainRuntime";

describe("brainRuntime helpers", () => {
  it("parses sections and extracts summary lists", () => {
    const documents = [
      {
        key: "project_brain",
        title: "Project Brain",
        relative_path: ".agents/runtime/project-brain.md",
        updated_at: null,
        line_count: 12,
        is_missing: false,
        content: `# Project Brain

## Current Focus
- Finish the signal lab
- Tighten release posture

## Next Slices
- Build the brain dashboard

## Stable Facts
- Use the reconciled repo

## Repeated Pitfalls
- Do not trust stale packets`,
      },
      {
        key: "decision_journal",
        title: "Decision Journal",
        relative_path: ".agents/runtime/decision-journal.md",
        updated_at: null,
        line_count: 6,
        is_missing: false,
        content: `# Decision Journal

## Recent Decisions
- Picked Signal Lab as the next operator surface
- Added deep links before widening scope`,
      },
      {
        key: "evolution_log",
        title: "Evolution Log",
        relative_path: ".agents/runtime/evolution-log.md",
        updated_at: null,
        line_count: 6,
        is_missing: false,
        content: `# Evolution Log

## Active Heuristics
- Verify before broadening scope

## Recent Learnings
- Default selection must work without useEffect`,
      },
      {
        key: "run_ledger",
        title: "Autonomy Run Ledger",
        relative_path: ".agents/runtime/run-ledger.md",
        updated_at: null,
        line_count: 7,
        is_missing: false,
        content: `# Autonomy Run Ledger

## Latest Run
- Slice: Brain dashboard
- Outcome: Verified
- Verification: frontend tests
- Remaining Risk: release mapping still pending
- Next Step: connect release center
- Target Surface: brain
- Target Route: /bos/brain

## Recent Runs
- 2026-04-16 12:00 | Brain dashboard | Verified | Added editor controls | brain |  | /bos/brain
- 2026-04-16 13:30 | Operator context card | Verified | Mapped brain into dashboard | signal_lab | 101 | /bos/signal-lab?batchId=101`,
      },
    ];

    const parsed = parseBrainDocument(documents[0].content);
    expect(parsed.sections.map((item) => item.title)).toContain("Current Focus");

    const summary = summarizeBrainRuntimeDocuments(documents);
    expect(summary.currentFocus[0]).toBe("Finish the signal lab");
    expect(summary.recentDecisions[0]).toContain("Signal Lab");
    expect(summary.activeHeuristics[0]).toContain("Verify before broadening scope");
    expect(summary.latestRun[0]).toContain("Slice: Brain dashboard");
    expect(summary.latestRunDetail.slice).toBe("Brain dashboard");
    expect(summary.latestRunDetail.outcome).toBe("Verified");
    expect(summary.recentRunDetails[0]?.slice).toBe("Brain dashboard");
  });

  it("audits runtime documents against the required heading contract", () => {
    const audit = auditBrainRuntimeDocument({
      key: "project_brain",
      title: "Project Brain",
      relative_path: ".agents/runtime/project-brain.md",
      updated_at: null,
      line_count: 6,
      is_missing: false,
      content: `# Project Brain

## Mission
- Keep the runtime brain valid.

## Surprise
- This should be flagged.`,
    });

    expect(audit.expectedTitle).toBe("Project Brain");
    expect(audit.isStructured).toBe(false);
    expect(audit.unexpectedHeadings).toEqual(["Surprise"]);
    expect(audit.missingHeadings).toContain("Current Focus");
  });

  it("parses a latest run block into structured fields", () => {
    const detail = parseLatestRun([
      "Slice: Signal Lab",
      "Outcome: Verified",
      "Verification: type-check and vitest",
      "Remaining Risk: release bridge not yet mapped",
      "Next Step: connect run outputs to release center",
      "Target Surface: release",
      "Target Route: /release",
    ]);

    expect(detail.slice).toBe("Signal Lab");
    expect(detail.outcome).toBe("Verified");
    expect(detail.nextStep).toContain("release center");
    expect(detail.targetSurface).toBe("release");
    expect(detail.targetRoute).toBe("/release");
  });

  it("parses recent run entries into timeline fields", () => {
    const entry = parseRecentRunEntry("2026-04-16 13:30 | Operator context card | Verified | Mapped brain into dashboard | signal_lab | 101 | /bos/signal-lab?batchId=101");

    expect(entry.when).toBe("2026-04-16 13:30");
    expect(entry.slice).toBe("Operator context card");
    expect(entry.outcome).toBe("Verified");
    expect(entry.note).toContain("Mapped brain");
    expect(entry.targetSurface).toBe("signal_lab");
    expect(entry.targetId).toBe("101");
    expect(entry.targetRoute).toBe("/bos/signal-lab?batchId=101");
  });

  it("infers concrete and broad routes from brain text", () => {
    const concrete = inferBrainRouteFromText("Batch 101 signal review");
    expect(concrete?.to).toBe("/bos/signal-lab?batchId=101");

    const broader = suggestBrainRoutes(["release dossier trust gate"]);
    expect(broader[0]?.to).toBe("/release");
  });

  it("prefers explicit target metadata when present", () => {
    const explicit = inferBrainRouteFromTarget("audit_packet", "900", null);
    expect(explicit?.to).toBe("/bos/console?auditPacketId=900");
  });

  it("derives a priority action from mode and latest run context", () => {
    const documents = [
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
        content: "# Autonomy Run Ledger\n\n## Latest Run\n- Slice: Batch 101 signal review\n- Outcome: Verified\n- Verification: tests\n- Remaining Risk: release mapping still pending\n- Next Step: connect audit packet 900 to release center\n- Target Surface: audit_packet\n- Target ID: 900\n",
      },
    ];

    const summary = summarizeBrainRuntimeDocuments(documents);
    const releaseAction = derivePriorityAction(summary, "release");
    const signalAction = derivePriorityAction(summary, "signal");

    expect(releaseAction?.to).toBe("/bos/console?auditPacketId=900");
    expect(signalAction?.to).toBe("/bos/signal-lab?batchId=101");
  });

  it("audits latest run completeness", () => {
    const incomplete = auditLatestRunDetail({
      slice: "Signal Lab",
      outcome: "Verified",
      verification: null,
      remainingRisk: null,
      nextStep: "Open release center",
      targetSurface: null,
      targetId: null,
      targetRoute: null,
    });

    expect(incomplete.isComplete).toBe(false);
    expect(incomplete.missingFields).toEqual(["verification", "remaining risk", "target surface", "target id/route"]);
  });

  it("repairs runtime documents into the required structure", () => {
    const repaired = buildStructuredRuntimeDocument(
      "run_ledger",
      `# Autonomy Run Ledger

## Latest Run
- Slice: Signal Lab`,
    );

    expect(repaired).toContain("## Latest Run");
    expect(repaired).toContain("- Slice: Signal Lab");
    expect(repaired).toContain("- Outcome:");
    expect(repaired).toContain("- Target Surface:");
    expect(repaired).toContain("- Target ID:");
    expect(repaired).toContain("- Target Route:");
    expect(repaired).toContain("## Recent Runs");
    expect(repaired).toContain("| targetSurface | targetId | targetRoute");
  });
});
