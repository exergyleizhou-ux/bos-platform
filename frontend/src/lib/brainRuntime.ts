import type { BrainRuntimeDocument } from "@/types/bos";

export interface ParsedBrainDocument {
  intro: string[];
  sections: Array<{
    title: string;
    lines: string[];
  }>;
}

export interface ParsedLatestRun {
  slice: string | null;
  outcome: string | null;
  verification: string | null;
  remainingRisk: string | null;
  nextStep: string | null;
  targetSurface: string | null;
  targetId: string | null;
  targetRoute: string | null;
}

export interface ParsedRecentRunEntry {
  when: string | null;
  slice: string | null;
  outcome: string | null;
  note: string | null;
  targetSurface: string | null;
  targetId: string | null;
  targetRoute: string | null;
}

export interface LatestRunAudit {
  missingFields: string[];
  isComplete: boolean;
}

export interface BrainRouteSuggestion {
  to: string;
  label: string;
}

export interface BrainPriorityAction {
  label: string;
  to: string;
  reason: string;
}

export const runtimeDocumentSpecs = {
  project_brain: {
    title: "Project Brain",
    requiredHeadings: [
      "Mission",
      "Current Focus",
      "Next Slices",
      "Stable Facts",
      "Constraints",
      "Known Good Commands",
      "Repeated Pitfalls",
    ],
  },
  decision_journal: {
    title: "Decision Journal",
    requiredHeadings: ["Recent Decisions", "Plan Changes"],
  },
  evolution_log: {
    title: "Evolution Log",
    requiredHeadings: ["Active Heuristics", "Recent Learnings"],
  },
  run_ledger: {
    title: "Autonomy Run Ledger",
    requiredHeadings: ["Latest Run", "Recent Runs"],
  },
} as const;

export interface BrainRuntimeDocumentAudit {
  expectedTitle: string;
  requiredHeadings: string[];
  presentHeadings: string[];
  missingHeadings: string[];
  unexpectedHeadings: string[];
  invalidLines: string[];
  isStructured: boolean;
}

const runtimeDocumentDefaults: Record<string, Record<string, string[]>> = {
  project_brain: {
    Mission: ["- Record the durable mission of the project here."],
    "Current Focus": ["- Record the current highest-priority slice here."],
    "Next Slices": ["- Record the next 1-3 highest-value slices here."],
    "Stable Facts": ["- Record stable architecture and product truths here."],
    Constraints: ["- Record hard limits, dependencies, and non-negotiables here."],
    "Known Good Commands": ["- Record the most reliable verification or run commands here."],
    "Repeated Pitfalls": ["- Record recurring traps or regressions here."],
  },
  decision_journal: {
    "Recent Decisions": ["- Record important planning and implementation decisions here."],
    "Plan Changes": ["- Record when the plan changed and why."],
  },
  evolution_log: {
    "Active Heuristics": ["- Record verified heuristics and routine improvements here."],
    "Recent Learnings": ["- Record short evidence-backed lessons from recent runs here."],
  },
  run_ledger: {
    "Latest Run": [
      "- Slice: Record the current slice here.",
      "- Outcome: Record the result here.",
      "- Verification: Record how it was verified here.",
      "- Remaining Risk: Record the remaining risk here.",
      "- Next Step: Record the next step here.",
      "- Target Surface: Record the destination surface key here.",
      "- Target ID: Record the destination entity id here when one exists.",
      "- Target Route: Record the deep-link route here.",
    ],
    "Recent Runs": ["- YYYY-MM-DD HH:MM | Slice | Outcome | Short note | targetSurface | targetId | targetRoute"],
  },
};

export function parseBrainDocument(content: string): ParsedBrainDocument {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const intro: string[] = [];
  const sections: ParsedBrainDocument["sections"] = [];
  let currentSection: ParsedBrainDocument["sections"][number] | null = null;

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const headingMatch = /^##\s+(.*)$/.exec(line.trim());
    if (headingMatch) {
      currentSection = {
        title: headingMatch[1].trim(),
        lines: [],
      };
      sections.push(currentSection);
      continue;
    }

    if (currentSection) {
      if (line.trim()) currentSection.lines.push(line.trim());
    } else if (line.trim() && !line.trim().startsWith("#")) {
      intro.push(line.trim());
    }
  }

  return { intro, sections };
}

export function getSectionLines(parsed: ParsedBrainDocument, title: string) {
  return parsed.sections.find((section) => section.title.toLowerCase() === title.toLowerCase())?.lines ?? [];
}

export function extractBullets(lines: string[]) {
  return lines
    .filter((line) => line.startsWith("- "))
    .map((line) => line.replace(/^- /, "").trim())
    .filter(Boolean);
}

export function summarizeBrainRuntimeDocuments(documents: BrainRuntimeDocument[]) {
  const documentMap = new Map(documents.map((item) => [item.key, item]));
  const projectBrain = documentMap.get("project_brain");
  const decisionJournal = documentMap.get("decision_journal");
  const evolutionLog = documentMap.get("evolution_log");
  const runLedger = documentMap.get("run_ledger");

  const parsedProjectBrain = parseBrainDocument(projectBrain?.content ?? "");
  const parsedDecisionJournal = parseBrainDocument(decisionJournal?.content ?? "");
  const parsedEvolutionLog = parseBrainDocument(evolutionLog?.content ?? "");
  const parsedRunLedger = parseBrainDocument(runLedger?.content ?? "");

  const currentFocus =
    extractBullets(getSectionLines(parsedProjectBrain, "Current Focus")).slice(0, 4);
  const nextSlices =
    extractBullets(getSectionLines(parsedProjectBrain, "Next Slices")).slice(0, 4);
  const stableFacts =
    extractBullets(getSectionLines(parsedProjectBrain, "Stable Facts")).slice(0, 4);
  const repeatedPitfalls =
    extractBullets(getSectionLines(parsedProjectBrain, "Repeated Pitfalls")).slice(0, 4);

  const recentDecisions = [
    ...extractBullets(getSectionLines(parsedDecisionJournal, "Recent Decisions")),
    ...extractBullets(parsedDecisionJournal.intro),
  ].slice(0, 5);

  const activeHeuristics =
    extractBullets(getSectionLines(parsedEvolutionLog, "Active Heuristics")).slice(0, 5);
  const recentLearnings =
    extractBullets(getSectionLines(parsedEvolutionLog, "Recent Learnings")).slice(0, 5);
  const latestRun =
    extractBullets(getSectionLines(parsedRunLedger, "Latest Run"));
  const recentRuns =
    extractBullets(getSectionLines(parsedRunLedger, "Recent Runs")).slice(0, 5);
  const latestRunDetail = parseLatestRun(latestRun);
  const recentRunDetails = recentRuns.map(parseRecentRunEntry);
  const latestRunAudit = auditLatestRunDetail(latestRunDetail);

  return {
    currentFocus,
    nextSlices,
    stableFacts,
    repeatedPitfalls,
    recentDecisions,
    activeHeuristics,
    recentLearnings,
    latestRun,
    recentRuns,
    latestRunDetail,
    recentRunDetails,
    latestRunAudit,
  };
}

export function parseLatestRun(lines: string[]): ParsedLatestRun {
  const detail: ParsedLatestRun = {
    slice: null,
    outcome: null,
    verification: null,
    remainingRisk: null,
    nextStep: null,
    targetSurface: null,
    targetId: null,
    targetRoute: null,
  };

  for (const line of lines) {
    const [rawKey, ...rest] = line.split(":");
    if (!rawKey || rest.length === 0) continue;
    const value = rest.join(":").trim();
    const key = rawKey.trim().toLowerCase();

    if (key === "slice") detail.slice = value;
    else if (key === "outcome") detail.outcome = value;
    else if (key === "verification") detail.verification = value;
    else if (key === "remaining risk") detail.remainingRisk = value;
    else if (key === "next step") detail.nextStep = value;
    else if (key === "target surface") detail.targetSurface = value;
    else if (key === "target id") detail.targetId = value;
    else if (key === "target route") detail.targetRoute = value;
  }

  return detail;
}

export function parseRecentRunEntry(line: string): ParsedRecentRunEntry {
  const parts = line.split("|").map((item) => item.trim());
  return {
    when: parts[0] ?? null,
    slice: parts[1] ?? null,
    outcome: parts[2] ?? null,
    note: parts.slice(3).join(" | ") || null,
    targetSurface: parts[4] ?? null,
    targetId: parts[5] ?? null,
    targetRoute: parts[6] ?? null,
  };
}

export function auditLatestRunDetail(detail: ParsedLatestRun): LatestRunAudit {
  const missingFields: string[] = [];
  if (!detail.slice) missingFields.push("slice");
  if (!detail.outcome) missingFields.push("outcome");
  if (!detail.verification) missingFields.push("verification");
  if (!detail.remainingRisk) missingFields.push("remaining risk");
  if (!detail.nextStep) missingFields.push("next step");
  if (!detail.targetSurface) missingFields.push("target surface");
  if (!detail.targetId && !detail.targetRoute) missingFields.push("target id/route");

  return {
    missingFields,
    isComplete: missingFields.length === 0,
  };
}

export function suggestBrainRoutes(items: string[]) {
  const rules = [
    { when: /(signal|handover|mtt|hal|portability|executor|locality)/, to: "/bos/signal-lab", label: "Signal Lab" },
    { when: /(release|verification|dossier|trust|gate)/, to: "/release", label: "Release Center" },
    { when: /(brain|memory|evolution|heuristic)/, to: "/bos/brain", label: "Brain Dashboard" },
    { when: /(batch|feedstock|operator surface|command center)/, to: "/batches", label: "Batch Command" },
    { when: /(forecast|trend|drift)/, to: "/forecast", label: "Forecast" },
    { when: /(twin|scenario)/, to: "/twins", label: "Digital Twins" },
    { when: /(dashboard|overview|executive)/, to: "/dashboard", label: "Executive Overview" },
  ];

  const haystack = items.join(" ").toLowerCase();
  return rules.filter((rule) => rule.when.test(haystack)).slice(0, 4);
}

export function inferBrainRouteFromText(text: string): BrainRouteSuggestion | null {
  const signalLabContextMatch = /\bbatch\s+(\d+)\b.*\bsignal\b/i.exec(text);
  if (signalLabContextMatch) {
    const batchId = signalLabContextMatch[1];
    return {
      to: `/bos/signal-lab?batchId=${batchId}`,
      label: `Signal Lab for Batch ${batchId}`,
    };
  }

  const batchMatch = /\bbatch\s+(\d+)\b/i.exec(text);
  if (batchMatch) {
    return {
      to: `/batches/${batchMatch[1]}`,
      label: `Batch ${batchMatch[1]}`,
    };
  }

  const auditPacketMatch = /\baudit\s+packet\s+(\d+)\b/i.exec(text);
  if (auditPacketMatch) {
    return {
      to: `/bos/console?auditPacketId=${auditPacketMatch[1]}`,
      label: `Audit Packet ${auditPacketMatch[1]}`,
    };
  }

  const releaseSignalMatch = /\brelease\b.*\bsignal\b/i.exec(text);
  if (releaseSignalMatch) {
    return {
      to: "/bos/signal-lab",
      label: "Signal Lab",
    };
  }

  return suggestBrainRoutes([text])[0] ?? null;
}

export function inferBrainRouteFromTarget(
  targetSurface: string | null | undefined,
  targetId: string | null | undefined,
  targetRoute: string | null | undefined,
): BrainRouteSuggestion | null {
  if (targetRoute) {
    return {
      to: targetRoute,
      label: humanizeRouteLabel(targetSurface, targetId, targetRoute),
    };
  }

  if (!targetSurface) return null;
  const surface = targetSurface.toLowerCase();

  if (surface === "signal_lab" && targetId) {
    return {
      to: `/bos/signal-lab?batchId=${targetId}`,
      label: `Signal Lab for Batch ${targetId}`,
    };
  }
  if (surface === "batch" && targetId) {
    return {
      to: `/batches/${targetId}`,
      label: `Batch ${targetId}`,
    };
  }
  if (surface === "audit_packet" && targetId) {
    return {
      to: `/bos/console?auditPacketId=${targetId}`,
      label: `Audit Packet ${targetId}`,
    };
  }
  if (surface === "release") {
    return { to: "/release", label: "Release Center" };
  }
  if (surface === "brain") {
    return { to: "/bos/brain", label: "Brain Dashboard" };
  }
  if (surface === "orchestrator") {
    return { to: "/bos/orchestrator", label: "BOS Orchestrator" };
  }

  return null;
}

function humanizeRouteLabel(
  targetSurface: string | null | undefined,
  targetId: string | null | undefined,
  targetRoute: string,
) {
  const surface = targetSurface?.toLowerCase();
  if (surface === "signal_lab" && targetId) return `Signal Lab for Batch ${targetId}`;
  if (surface === "batch" && targetId) return `Batch ${targetId}`;
  if (surface === "audit_packet" && targetId) return `Audit Packet ${targetId}`;
  if (surface === "release") return "Release Center";
  if (surface === "brain") return "Brain Dashboard";
  if (surface === "orchestrator") return "BOS Orchestrator";
  return targetRoute;
}

export function derivePriorityAction(
  summary: ReturnType<typeof summarizeBrainRuntimeDocuments>,
  mode: "default" | "dashboard" | "release" | "signal" | "assistant" | "orchestrator",
): BrainPriorityAction | null {
  const join = (...items: Array<string | null | undefined>) => items.filter(Boolean).join(" ");
  const explicitRoute = inferBrainRouteFromTarget(
    summary.latestRunDetail.targetSurface,
    summary.latestRunDetail.targetId,
    summary.latestRunDetail.targetRoute,
  );

  if (mode === "release") {
    const releaseExplicitRoute =
      summary.latestRunDetail.targetSurface &&
      ["release", "audit_packet"].includes(summary.latestRunDetail.targetSurface.toLowerCase())
        ? explicitRoute
        : null;
    const route = releaseExplicitRoute ?? inferBrainRouteFromText(
      join(summary.latestRunDetail.nextStep, summary.latestRunDetail.remainingRisk, ...summary.recentDecisions),
    );
    return route
      ? {
          label: `Priority: ${route.label}`,
          to: route.to,
          reason: summary.latestRunDetail.remainingRisk ?? "Latest release-adjacent run still carries follow-up risk.",
        }
      : {
          label: "Priority: Release Center",
          to: "/release",
          reason: "Release posture is the main decision surface for this context.",
        };
  }

  if (mode === "signal") {
    const signalExplicitRoute =
      summary.latestRunDetail.targetSurface &&
      ["signal_lab", "batch"].includes(summary.latestRunDetail.targetSurface.toLowerCase())
        ? explicitRoute
        : null;
    const route = signalExplicitRoute ?? inferBrainRouteFromText(
      join(summary.latestRunDetail.slice, summary.latestRunDetail.nextStep, ...summary.currentFocus, ...summary.nextSlices),
    );
    return route
      ? {
          label: `Priority: ${route.label}`,
          to: route.to,
          reason: summary.latestRunDetail.nextStep ?? "Signal-adjacent work is the clearest next move.",
        }
      : {
          label: "Priority: Signal Lab",
          to: "/bos/signal-lab",
          reason: "Signal qualification remains the highest-leverage next action.",
        };
  }

  if (mode === "assistant") {
    return {
      label: "Priority: Assistant Thread",
      to: "/bos",
      reason: "Use the thread to refine the next move before opening a narrower surface.",
    };
  }

  if (mode === "orchestrator") {
    return {
      label: "Priority: Orchestrator",
      to: "/bos/orchestrator",
      reason: "Coordinate the next native or embedded workflow from the orchestration surface.",
    };
  }

  const route = explicitRoute ?? inferBrainRouteFromText(
    join(summary.latestRunDetail.nextStep, summary.latestRunDetail.slice, ...summary.currentFocus, ...summary.nextSlices),
  );
  return route
    ? {
        label: `Priority: ${route.label}`,
        to: route.to,
        reason: summary.latestRunDetail.nextStep ?? "The project brain points here as the next highest-value move.",
      }
    : null;
}

export function auditBrainRuntimeDocument(document: BrainRuntimeDocument): BrainRuntimeDocumentAudit {
  const spec = runtimeDocumentSpecs[document.key as keyof typeof runtimeDocumentSpecs];
  if (!spec) {
    return {
      expectedTitle: document.title,
      requiredHeadings: [],
      presentHeadings: [],
      missingHeadings: [],
      unexpectedHeadings: [],
      invalidLines: [],
      isStructured: true,
    };
  }

  const parsed = parseBrainDocument(document.content);
  const presentHeadings = parsed.sections.map((section) => section.title);
  const requiredHeadings: string[] = [...spec.requiredHeadings];
  const missingHeadings = requiredHeadings.filter((heading) => !presentHeadings.includes(heading));
  const unexpectedHeadings = presentHeadings.filter((heading) => !requiredHeadings.includes(heading));
  const invalidLines: string[] = [];
  const titleLine = document.content.replace(/\r\n/g, "\n").split("\n")[0]?.trim();

  if (titleLine !== `# ${spec.title}`) {
    invalidLines.push(`Title must be '# ${spec.title}'.`);
  }
  if (parsed.intro.length) {
    invalidLines.push("Intro content must move under a required heading.");
  }
  for (const section of parsed.sections) {
    for (const line of section.lines) {
      if (!line.startsWith("- ")) {
        invalidLines.push(`${section.title}: ${line}`);
      }
    }
  }

  return {
    expectedTitle: spec.title,
    requiredHeadings,
    presentHeadings,
    missingHeadings,
    unexpectedHeadings,
    invalidLines,
    isStructured: missingHeadings.length === 0 && unexpectedHeadings.length === 0 && invalidLines.length === 0,
  };
}

export function buildStructuredRuntimeDocument(
  documentKey: string,
  content: string,
) {
  const spec = runtimeDocumentSpecs[documentKey as keyof typeof runtimeDocumentSpecs];
  if (!spec) return content;

  const parsed = parseBrainDocument(content);
  const sectionMap = new Map(parsed.sections.map((section) => [section.title, extractBullets(section.lines)]));
  const defaults = runtimeDocumentDefaults[documentKey] ?? {};

  const lines: string[] = [`# ${spec.title}`, ""];
  for (const heading of spec.requiredHeadings) {
    lines.push(`## ${heading}`, "");
    const existing = sectionMap.get(heading)?.filter(Boolean) ?? [];
    const defaultLines = defaults[heading] ?? ["- Fill this section."];
    const normalizedExisting = existing.map((line) => `- ${line}`);
    const existingKeys = new Set(
      existing.map((line) => {
        const [key] = line.split(":");
        return key.trim().toLowerCase();
      }),
    );
    const missingDefaults = defaultLines.filter((line) => {
      const body = line.replace(/^- /, "");
      const [key] = body.split(":");
      return !existingKeys.has(key.trim().toLowerCase());
    });
    const payload =
      normalizedExisting.length > 0
        ? [...normalizedExisting, ...missingDefaults]
        : defaultLines;
    lines.push(...payload, "");
  }

  return `${lines.join("\n").trim()}\n`;
}
