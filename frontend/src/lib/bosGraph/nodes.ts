import type { AssistantStructuredResult } from "@/lib/bosAssistant";
import type { BosGraphContext, BosGraphNodeOutput } from "@/lib/bosGraph/contracts";
import { buildDefaultSupervisorObservation } from "@/lib/bosGraph/context";
import { getAuditPacketReadModel } from "@/lib/bos-read-model";
import { formatDateTime, formatNumber, formatPercent } from "@/lib/utils";
import type {
  AuditPacket,
  BrainRuntimeResponse,
  HandoverRecommendationResponse,
  ReleaseDecision,
  SignalBatch,
  SupervisorStateResponse,
} from "@/types/bos";
import type { Batch } from "@/types/batch";
import type { DashboardSummary } from "@/types/dashboard";

type GuidanceShape = {
  gap_items: Array<{ severity: string; title: string; message: string }>;
  recommended_actions: string[];
};

function summarizeReleaseDecisions(decisions: ReleaseDecision[]) {
  return decisions.reduce<Record<string, number>>((accumulator, item) => {
    const key = item.decision || "UNKNOWN";
    accumulator[key] = (accumulator[key] ?? 0) + 1;
    return accumulator;
  }, {});
}

function resolveLatestSignalForBatch(signals: SignalBatch[], batchId: number) {
  return (
    signals
      .filter((item) => item.batch_id === batchId)
      .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null
  );
}

function resolveAuditForBatch(audits: AuditPacket[], batchId: number, signal: SignalBatch | null) {
  return (
    audits.find((item) => item.batch_id === batchId && (!signal || item.packet?.signal_batch?.id === signal.id)) ??
    audits.find((item) => item.batch_id === batchId) ??
    null
  );
}

async function resolveLatestBatchId(context: BosGraphContext) {
  if (context.requestedEntityId) return context.requestedEntityId;
  const batchList = await context.apiClients.batch.list(1, 1);
  context.intermediateData.batchList = batchList;
  return batchList.items[0]?.id ?? null;
}

async function ensureBatchList(context: BosGraphContext, limit: number) {
  if (!context.intermediateData.batchList || context.intermediateData.batchList.items.length < limit) {
    context.intermediateData.batchList = await context.apiClients.batch.list(1, limit);
  }
  context.intermediateData.batches = context.intermediateData.batchList.items;
  return context.intermediateData.batchList;
}

async function ensureSignals(context: BosGraphContext) {
  if (!context.intermediateData.signals) {
    context.intermediateData.signals = await context.apiClients.bos.listSignals();
  }
  return context.intermediateData.signals;
}

async function ensureAudits(context: BosGraphContext) {
  if (!context.intermediateData.audits) {
    context.intermediateData.audits = await context.apiClients.bos.listAuditPackets();
  }
  return context.intermediateData.audits;
}

async function ensureReleaseDecisions(context: BosGraphContext) {
  if (!context.intermediateData.releaseDecisions) {
    context.intermediateData.releaseDecisions = await context.apiClients.bos.listReleaseDecisions();
  }
  return context.intermediateData.releaseDecisions;
}

async function loadGuidance(context: BosGraphContext, batchId: number): Promise<GuidanceShape> {
  try {
    return await context.apiClients.bos.getBatchGuidance(batchId);
  } catch {
    return { gap_items: [], recommended_actions: [] };
  }
}

function buildCatalogEmptyResult(title: string, summary: string, to: string): AssistantStructuredResult {
  return {
    title,
    summary,
    actions: [{ label: "Open batch command", to }],
  };
}

function buildBatchGuidanceResult(args: {
  batch: Batch;
  guidance: GuidanceShape;
}): AssistantStructuredResult {
  return {
    title: `Batch guidance / ${args.batch.batch_id}`,
    summary:
      "Current BOS gap items and next-best actions for this batch, pulled directly from the guidance service.",
    metrics: [
      { label: "Batch", value: args.batch.batch_id, hint: args.batch.species },
      { label: "Status", value: args.batch.status, hint: "Current batch workflow state" },
      { label: "Guidance gaps", value: String(args.guidance.gap_items.length), hint: "Open guidance items" },
      { label: "Recommended actions", value: String(args.guidance.recommended_actions.length), hint: "Action candidates" },
    ],
    notes: [
      ...(args.guidance.gap_items.length
        ? args.guidance.gap_items.slice(0, 5).map((item) => `[${item.severity}] ${item.title}: ${item.message}`)
        : ["No guidance gaps are currently open for this batch."]),
      ...(args.guidance.recommended_actions.length
        ? args.guidance.recommended_actions.slice(0, 5).map((item) => `Recommended: ${item}`)
        : []),
    ],
    actions: [
      { label: "Open batch detail", to: `/batches/${args.batch.id}` },
      { label: "Open signal lab", to: `/bos/signal-lab?batchId=${args.batch.id}` },
    ],
  };
}

function buildBatchAnalysisResult(args: {
  batch: Batch;
  guidance: GuidanceShape;
  signal: SignalBatch | null;
  audit: AuditPacket | null;
}): AssistantStructuredResult {
  const readModel = args.audit ? getAuditPacketReadModel(args.audit) : null;
  return {
    title: `Batch analysis / ${args.batch.batch_id}`,
    summary:
      "Focused batch health summary with current process state, BOS signal posture, and the next guidance items already generated by the system.",
    metrics: [
      { label: "Status", value: args.batch.status, hint: args.batch.species },
      { label: "SER", value: formatNumber(args.batch.ser_value ?? args.batch.score, 4), hint: "Observed batch performance" },
      {
        label: "Signal",
        value: args.signal?.freshness_state || "No signal",
        hint: args.signal?.compiled_signal_id || "Compile signal to unlock richer BOS guidance",
      },
      {
        label: "Release posture",
        value: readModel?.readinessLabel || "Awaiting packet",
        hint: readModel?.releaseDecision || "No release decision yet",
      },
      {
        label: "Moisture",
        value: formatNumber(args.batch.moisture, 2),
        hint: "Current measured moisture",
      },
      {
        label: "Temperature",
        value: formatNumber(args.batch.temperature, 2),
        hint: "Current measured temperature",
      },
    ],
    notes: [
      ...(args.guidance.gap_items.length
        ? args.guidance.gap_items.slice(0, 4).map((item) => `[${item.severity}] ${item.title}: ${item.message}`)
        : ["No BOS guidance gaps are currently flagged for this batch."]),
      ...(args.guidance.recommended_actions.length
        ? args.guidance.recommended_actions.slice(0, 4).map((item) => `Recommended: ${item}`)
        : []),
    ],
    actions: [
      { label: "Open batch detail", to: `/batches/${args.batch.id}` },
      { label: "Open signal lab", to: `/bos/signal-lab?batchId=${args.batch.id}` },
    ],
  };
}

function buildBatchCompareResult(args: {
  batches: Batch[];
  signals: SignalBatch[];
  audits: AuditPacket[];
}): AssistantStructuredResult {
  const rows = args.batches.slice(0, 2).map((batch) => {
    const signal = resolveLatestSignalForBatch(args.signals, batch.id);
    const audit = resolveAuditForBatch(args.audits, batch.id, signal);
    const readModel = audit ? getAuditPacketReadModel(audit) : null;
    return [
      batch.batch_id,
      batch.status,
      formatNumber(batch.ser_value ?? batch.score, 4),
      signal?.freshness_state || "No signal",
      readModel?.releaseDecision || "No decision",
      formatDateTime(batch.updated_at),
    ];
  });

  return {
    title: "Latest batch comparison",
    summary:
      "Side-by-side comparison of the newest batch records, including SER posture, signal freshness, and release decision availability.",
    table: {
      columns: ["Batch", "Status", "SER", "Signal", "Release", "Updated"],
      rows,
    },
    notes:
      args.batches.length >= 2
        ? [
            `Newest batch: ${args.batches[0].batch_id}`,
            `Previous batch: ${args.batches[1].batch_id}`,
          ]
        : ["Only one batch is available right now, so comparison depth is limited."],
    actions: [{ label: "Open batch command", to: "/batches" }],
  };
}

function computeBatchRiskScore(args: {
  batch: Batch;
  signal: SignalBatch | null;
  audit: AuditPacket | null;
  guidance?: GuidanceShape | null;
}) {
  let score = 0;
  const reasons: string[] = [];
  const readModel = args.audit ? getAuditPacketReadModel(args.audit) : null;

  if (readModel?.releaseDecision === "FAIL") {
    score += 5;
    reasons.push("Release decision is FAIL");
  } else if (readModel?.releaseDecision === "PASS_WITH_RETUNING") {
    score += 3;
    reasons.push("Release decision requires retuning");
  }

  if (args.signal?.freshness_state === "Stale") {
    score += 4;
    reasons.push("Signal freshness is stale");
  } else if (args.signal?.freshness_state === "Stable") {
    score += 2;
    reasons.push("Signal freshness is only stable");
  }

  const ser = args.batch.ser_value ?? args.batch.score;
  if (typeof ser === "number") {
    if (ser >= 0.12) {
      score += 3;
      reasons.push("SER is outside preferred pass band");
    } else if (ser >= 0.08) {
      score += 1;
      reasons.push("SER is drifting toward the upper band");
    }
  }

  if (args.batch.status === "failed") {
    score += 4;
    reasons.push("Batch workflow status is failed");
  } else if (args.batch.status === "active") {
    score += 1;
    reasons.push("Batch is still active and unresolved");
  }

  const criticalGaps = args.guidance?.gap_items.filter((item) => item.severity === "critical").length ?? 0;
  const warningGaps = args.guidance?.gap_items.filter((item) => item.severity === "warning").length ?? 0;
  score += criticalGaps * 2 + warningGaps;
  if (criticalGaps > 0) reasons.push(`${criticalGaps} critical guidance gaps`);
  if (warningGaps > 0) reasons.push(`${warningGaps} warning guidance gaps`);

  return { score, reasons, readModel };
}

function buildRiskiestBatchResult(args: {
  batch: Batch;
  signal: SignalBatch | null;
  audit: AuditPacket | null;
  guidance: GuidanceShape;
  score: number;
  reasons: string[];
}): AssistantStructuredResult {
  const readModel = args.audit ? getAuditPacketReadModel(args.audit) : null;
  return {
    title: `Highest-risk batch / ${args.batch.batch_id}`,
    summary:
      "BOS ranked current batch posture across release evidence, signal freshness, SER, and open guidance gaps, then surfaced the heaviest-risk batch.",
    metrics: [
      { label: "Risk score", value: String(args.score), hint: "Composite BOS risk posture" },
      { label: "Status", value: args.batch.status, hint: args.batch.species },
      { label: "SER", value: formatNumber(args.batch.ser_value ?? args.batch.score, 4), hint: "Observed batch performance" },
      { label: "Signal", value: args.signal?.freshness_state || "No signal", hint: args.signal?.compiled_signal_id || "No compiled signal" },
      { label: "Release", value: readModel?.releaseDecision || "No decision", hint: readModel?.readinessLabel || "Awaiting packet" },
      { label: "Guidance gaps", value: String(args.guidance.gap_items.length), hint: "Open BOS guidance items" },
    ],
    notes: [
      ...(args.reasons.length
        ? args.reasons.slice(0, 5).map((item) => `Why it ranked high: ${item}`)
        : ["No strong risk factor was detected; this is simply the highest among the current set."]),
      ...(args.guidance.recommended_actions.length
        ? args.guidance.recommended_actions.slice(0, 4).map((item) => `Recommended: ${item}`)
        : []),
    ],
    actions: [
      { label: "Open batch detail", to: `/batches/${args.batch.id}` },
      { label: "Open signal lab", to: `/bos/signal-lab?batchId=${args.batch.id}` },
      { label: "Open release center", to: "/release" },
    ],
  };
}

function buildReleaseSummaryResult(args: {
  decisions: ReleaseDecision[];
  audits: AuditPacket[];
}): AssistantStructuredResult {
  const releaseCounts = summarizeReleaseDecisions(args.decisions);
  const latestAudit = args.audits[0] ? getAuditPacketReadModel(args.audits[0]) : null;

  return {
    title: "Release summary",
    summary: "Release posture based on current decisions and audit packets already compiled in BOS.",
    metrics: [
      { label: "Release decisions", value: String(args.decisions.length), hint: "Persisted decision records" },
      { label: "Audit packets", value: String(args.audits.length), hint: "Evidence packets available" },
      { label: "PASS", value: String(releaseCounts.PASS ?? 0), hint: "Ready candidates" },
      { label: "FAIL", value: String(releaseCounts.FAIL ?? 0), hint: "Blocked candidates" },
    ],
    notes: latestAudit
      ? [
          `Latest packet: ${latestAudit.batchLabel}`,
          `Latest decision: ${latestAudit.releaseDecision}`,
          `Latest rationale: ${latestAudit.rationale}`,
        ]
      : ["No audit packet has been compiled yet, so release posture is still thin."],
    actions: [{ label: "Open release center", to: "/release" }],
  };
}

function buildReleaseRiskResult(decisions: ReleaseDecision[], audits: AuditPacket[]): AssistantStructuredResult {
  const riskRows = audits
    .slice(0, 8)
    .map((item) => getAuditPacketReadModel(item))
    .flatMap((item) => [
      ...item.blockingFactors.map((factor) => [item.batchLabel, "Blocking", factor, item.releaseDecision]),
      ...item.warningFactors.map((factor) => [item.batchLabel, "Warning", factor, item.releaseDecision]),
    ]);

  const releaseCounts = summarizeReleaseDecisions(decisions);

  return {
    title: "Release risks",
    summary:
      "Blocking and warning factors extracted from current audit packets and release decisions, ranked in the order they appear in packet evidence.",
    metrics: [
      { label: "Release decisions", value: String(decisions.length), hint: "Persisted decisions in scope" },
      { label: "PASS", value: String(releaseCounts.PASS ?? 0), hint: "Ready candidates" },
      { label: "Retune", value: String(releaseCounts.PASS_WITH_RETUNING ?? 0), hint: "Candidates needing changes" },
      { label: "Fail", value: String(releaseCounts.FAIL ?? 0), hint: "Blocked candidates" },
    ],
    table: {
      columns: ["Batch", "Severity", "Factor", "Decision"],
      rows: riskRows.length ? riskRows : [["N/A", "Info", "No blocking or warning factors are currently present.", "N/A"]],
    },
    actions: [{ label: "Open release center", to: "/release" }],
  };
}

function buildReleaseEvaluationResult(decision: ReleaseDecision, signal: SignalBatch | null): AssistantStructuredResult {
  return {
    title: "Release evaluation completed",
    summary: "BOS evaluated the current release posture and persisted the decision for this batch.",
    metrics: [
      { label: "Batch", value: String(decision.batch_id), hint: signal?.compiled_signal_id || "Latest batch signal" },
      { label: "Decision", value: decision.decision, hint: decision.approver || "BOS policy engine" },
      { label: "Confidence", value: formatNumber(decision.decision_confidence, 4), hint: "Decision confidence" },
      { label: "Time", value: formatDateTime(decision.decision_time), hint: "Persisted release timestamp" },
    ],
    notes: [
      ...(decision.blocking_factors ?? []).map((item) => `Blocking: ${item}`),
      ...(decision.warning_factors ?? []).map((item) => `Warning: ${item}`),
      ...(decision.passed_checks ?? []).slice(0, 4).map((item) => `Passed: ${item}`),
    ],
    actions: [{ label: "Open release center", to: "/release" }],
  };
}

function buildSupervisorResult(result: SupervisorStateResponse): AssistantStructuredResult {
  return {
    title: "Supervisor evaluation",
    summary:
      "BOS evaluated the latent signal state from the current proxy observation snapshot and returned the live supervisor posture.",
    metrics: [
      { label: "Signal batch", value: String(result.signal_batch_id), hint: "Target signal packet" },
      { label: "C-hat", value: formatNumber(result.c_signal_hat, 3), hint: "Estimated latent signal" },
      { label: "dC/dt", value: formatNumber(result.dc_dt_hat, 3), hint: "Estimated slope" },
      { label: "Confidence", value: formatPercent(result.confidence, 0), hint: "Supervisor confidence" },
      { label: "Observability", value: formatPercent(result.observability_score, 0), hint: "Signal observability score" },
      { label: "Slope streak", value: String(result.negative_slope_streak ?? 0), hint: "Negative slope persistence" },
    ],
    notes: [
      result.trigger_reason ? `Trigger reason: ${result.trigger_reason}` : "No trigger reason is currently active.",
      result.expected_handover
        ? `Expected handover: ${formatDateTime(result.expected_handover)}`
        : "No handover timestamp is available yet.",
      `Channels used: ${(result.channels_used ?? []).join(", ") || "N/A"}`,
      `Missing channels: ${(result.missing_channels ?? []).join(", ") || "None"}`,
    ],
    actions: [{ label: "Open signal lab", to: "/bos/signal-lab" }],
  };
}

function buildHandoverRecommendationResult(result: HandoverRecommendationResponse): AssistantStructuredResult {
  return {
    title: "Handover recommendation",
    summary:
      "BOS evaluated whether handover should fire for the current signal packet and returned the recommendation with confidence context.",
    metrics: [
      { label: "Signal batch", value: String(result.signal_batch_id), hint: "Target signal packet" },
      { label: "Recommended", value: result.recommended_handover ? "Yes" : "No", hint: result.trigger_reason },
      { label: "Confidence", value: formatPercent(result.confidence, 0), hint: "Recommendation confidence" },
      {
        label: "Freshness window(h)",
        value: formatNumber(result.expected_freshness_window_hours, 2),
        hint: "Expected freshness window",
      },
      { label: "Threshold", value: formatNumber(result.confidence_threshold, 2), hint: "Confidence threshold" },
      {
        label: "Observability",
        value: formatPercent(result.observability_score, 0),
        hint: result.observability_required ? "Observability required" : "Observability optional",
      },
    ],
    notes: [
      `Channels used: ${(result.channels_used ?? []).join(", ") || "N/A"}`,
      `Missing channels: ${(result.missing_channels ?? []).join(", ") || "None"}`,
      result.expected_handover
        ? `Expected handover: ${formatDateTime(result.expected_handover)}`
        : "No handover timestamp is available yet.",
    ],
    actions: [{ label: "Open signal lab", to: "/bos/signal-lab" }],
  };
}

function buildExecutiveSummaryResult(args: {
  summary: DashboardSummary;
  decisions: ReleaseDecision[];
  audits: AuditPacket[];
  runtime: BrainRuntimeResponse;
}): AssistantStructuredResult {
  const releaseCounts = summarizeReleaseDecisions(args.decisions);
  const latestAudit = args.audits[0] ? getAuditPacketReadModel(args.audits[0]) : null;
  const posture =
    args.summary.avg_pass_rate >= 0.85
      ? "Healthy"
      : args.summary.avg_pass_rate >= 0.65
        ? "Watch closely"
        : "Constrained";

  return {
    title: "Executive BOS summary",
    summary:
      "Management-ready snapshot of current operating posture, release quality, and runtime memory health.",
    metrics: [
      { label: "Posture", value: posture, hint: "Derived from pass-rate and release posture" },
      { label: "Pass rate", value: formatPercent(args.summary.avg_pass_rate), hint: "Qualified output share" },
      { label: "Average SER", value: formatNumber(args.summary.avg_ser, 4), hint: "Current quality envelope" },
      { label: "Batches", value: String(args.summary.total_batches), hint: `${args.summary.active_batches} active` },
      { label: "Twins", value: String(args.summary.total_twins), hint: "Scenario surfaces online" },
      { label: "Brain docs", value: String(args.runtime.documents.length), hint: "Persistent memory surfaces" },
    ],
    notes: [
      `Release decisions: PASS ${releaseCounts.PASS ?? 0}, PASS_WITH_RETUNING ${releaseCounts.PASS_WITH_RETUNING ?? 0}, FAIL ${releaseCounts.FAIL ?? 0}`,
      latestAudit
        ? `Latest release rationale: ${latestAudit.rationale}`
        : "No audit packet rationale is available yet.",
      `Brain runtime last updated: ${formatDateTime(args.runtime.last_updated_at)}`,
    ],
    actions: [
      { label: "Open dashboard", to: "/dashboard" },
      { label: "Open release center", to: "/release" },
      { label: "Open brain dashboard", to: "/bos/brain" },
    ],
  };
}

export async function runBatchTriageIntent(context: BosGraphContext): Promise<BosGraphNodeOutput> {
  switch (context.intent) {
    case "riskiest_batch": {
      const [batchList, signals, audits] = await Promise.all([
        ensureBatchList(context, 8),
        ensureSignals(context),
        ensureAudits(context),
      ]);

      if (!batchList.items.length) {
        return {
          status: "blocked",
          body: "BOS could not find any batch records to rank yet.",
          structuredResult: buildCatalogEmptyResult(
            "No batches are available",
            "BOS could not find any batch records to rank for risk yet.",
            "/batches",
          ),
          diagnostics: [{ scope: "batch_triage_graph", message: "No batch records available for risk ranking." }],
        };
      }

      const scored = await Promise.all(
        batchList.items.map(async (batch) => {
          const signal = resolveLatestSignalForBatch(signals, batch.id);
          const audit = resolveAuditForBatch(audits, batch.id, signal);
          const guidance = await loadGuidance(context, batch.id);
          const risk = computeBatchRiskScore({ batch, signal, audit, guidance });
          return { batch, signal, audit, guidance, score: risk.score, reasons: risk.reasons };
        }),
      );

      context.intermediateData.scoredBatches = scored;
      const highest = [...scored].sort((left, right) => right.score - left.score)[0];
      return {
        status: "completed",
        body: `BOS ranked the recent batches and surfaced ${highest.batch.batch_id} as the heaviest current risk.`,
        structuredResult: buildRiskiestBatchResult(highest),
        nextActions: [{ label: "Open signal lab", to: `/bos/signal-lab?batchId=${highest.batch.id}` }],
      };
    }
    case "batch_analysis": {
      const batchId = await resolveLatestBatchId(context);
      if (!batchId) {
        return {
          status: "blocked",
          body: "BOS could not find a batch to analyze yet.",
          structuredResult: buildCatalogEmptyResult(
            "No batch is available to analyze",
            "BOS could not find any batch records yet, so there is nothing to run a focused batch analysis on.",
            "/batches",
          ),
        };
      }

      const [batch, guidance, signals, audits] = await Promise.all([
        context.apiClients.batch.get(batchId),
        context.apiClients.bos.getBatchGuidance(batchId),
        ensureSignals(context),
        ensureAudits(context),
      ]);
      const signal = resolveLatestSignalForBatch(signals, batch.id);
      const audit = resolveAuditForBatch(audits, batch.id, signal);
      return {
        status: "completed",
        body: `BOS analyzed batch ${batch.batch_id} and pulled its latest guidance into this thread.`,
        structuredResult: buildBatchAnalysisResult({ batch, guidance, signal, audit }),
      };
    }
    case "batch_guidance": {
      const batchId = await resolveLatestBatchId(context);
      if (!batchId) {
        return {
          status: "blocked",
          body: "BOS could not find a batch for guidance yet.",
          structuredResult: buildCatalogEmptyResult(
            "No batch is available for guidance",
            "BOS could not find a batch to load guidance for yet.",
            "/batches",
          ),
        };
      }
      const [batch, guidance] = await Promise.all([
        context.apiClients.batch.get(batchId),
        context.apiClients.bos.getBatchGuidance(batchId),
      ]);
      return {
        status: "completed",
        body: `BOS loaded the latest guidance for batch ${batch.batch_id}.`,
        structuredResult: buildBatchGuidanceResult({ batch, guidance }),
      };
    }
    case "batch_compare": {
      const batchLimit = context.requestedEntityIds.length >= 2 ? Math.max(...context.requestedEntityIds) : 10;
      const [batchList, signals, audits] = await Promise.all([
        ensureBatchList(context, batchLimit),
        ensureSignals(context),
        ensureAudits(context),
      ]);
      const selectedBatches =
        context.requestedEntityIds.length >= 2
          ? context.requestedEntityIds
              .map((id) => batchList.items.find((item) => item.id === id))
              .filter((item): item is Batch => Boolean(item))
              .slice(0, 2)
          : batchList.items.slice(0, 2);
      return {
        status: "completed",
        body: "BOS compared the latest batch records side by side.",
        structuredResult: buildBatchCompareResult({
          batches: selectedBatches,
          signals,
          audits,
        }),
      };
    }
    default:
      throw new Error(`Unsupported batch triage intent: ${context.intent}`);
  }
}

export async function runReleaseReviewIntent(context: BosGraphContext): Promise<BosGraphNodeOutput> {
  switch (context.intent) {
    case "executive_summary": {
      const [summary, decisions, audits, runtime] = await Promise.all([
        context.apiClients.dashboard.summary(),
        ensureReleaseDecisions(context),
        ensureAudits(context),
        context.apiClients.bos.getBrainRuntime(),
      ]);
      return {
        status: "completed",
        body: "BOS prepared a management-ready summary across dashboard, release, and runtime memory surfaces.",
        structuredResult: buildExecutiveSummaryResult({ summary, decisions, audits, runtime }),
      };
    }
    case "release_summary": {
      const [decisions, audits] = await Promise.all([
        ensureReleaseDecisions(context),
        ensureAudits(context),
      ]);
      return {
        status: "completed",
        body: "BOS summarized current release posture from decisions and audit packets.",
        structuredResult: buildReleaseSummaryResult({ decisions, audits }),
      };
    }
    case "release_risks": {
      const [decisions, audits] = await Promise.all([
        ensureReleaseDecisions(context),
        ensureAudits(context),
      ]);
      return {
        status: "completed",
        body: "BOS extracted the active release risks from current audit packet evidence.",
        structuredResult: buildReleaseRiskResult(decisions, audits),
      };
    }
    case "evaluate_release": {
      const batchId = await resolveLatestBatchId(context);
      if (!batchId) {
        return {
          status: "blocked",
          body: "BOS could not find a batch for release evaluation yet.",
          structuredResult: buildCatalogEmptyResult(
            "No batch is available for release evaluation",
            "BOS could not find a batch to evaluate for release yet.",
            "/batches",
          ),
        };
      }
      const signals = await ensureSignals(context);
      const latestSignal = resolveLatestSignalForBatch(signals, batchId);
      const decision = await context.apiClients.bos.evaluateRelease({
        batch_id: batchId,
        signal_batch_id: latestSignal?.id,
        persist: true,
      });
      await context.queryClient.invalidateQueries({ queryKey: ["bos"] });
      await context.queryClient.invalidateQueries({ queryKey: ["batches"] });
      return {
        status: "completed",
        body: `BOS evaluated release posture for batch ${decision.batch_id}.`,
        structuredResult: buildReleaseEvaluationResult(decision, latestSignal),
      };
    }
    case "export_audit_packet": {
      const batchId = await resolveLatestBatchId(context);
      if (!batchId) {
        return {
          status: "blocked",
          body: "BOS could not find a batch for audit export yet.",
          structuredResult: buildCatalogEmptyResult(
            "No batch is available for audit export",
            "BOS could not find a batch to export an audit packet for yet.",
            "/batches",
          ),
        };
      }
      const format = /\bjson\b/i.test(context.message) ? "json" : "md";
      const blob = await context.apiClients.bos.exportAuditPacket(batchId, format);
      const filename = `audit-packet-batch-${batchId}.${format}`;
      context.effects?.downloadBlob?.(blob, filename);
      return {
        status: "completed",
        body: `BOS exported the audit packet for batch ${batchId}.`,
        structuredResult: {
          title: "Audit packet exported",
          summary: "BOS exported the requested audit packet and started the download from this chat action.",
          metrics: [
            { label: "Batch", value: String(batchId), hint: "Export target" },
            { label: "Format", value: format.toUpperCase(), hint: filename },
          ],
          notes: [
            `Downloaded file: ${filename}`,
            "Use MD for operator review and JSON for downstream machine workflows.",
          ],
          actions: [{ label: "Open signal lab", to: `/bos/signal-lab?batchId=${batchId}` }],
        },
      };
    }
    default:
      throw new Error(`Unsupported release review intent: ${context.intent}`);
  }
}

export async function runSignalRuntimeIntent(context: BosGraphContext): Promise<BosGraphNodeOutput> {
  switch (context.intent) {
    case "compile_signal": {
      const batchId = await resolveLatestBatchId(context);
      if (!batchId) {
        return {
          status: "blocked",
          body: "BOS could not find a batch to compile yet.",
          structuredResult: buildCatalogEmptyResult(
            "No batch is available to compile",
            "BOS could not find a batch to compile a signal for yet.",
            "/batches",
          ),
        };
      }
      const compiled = await context.apiClients.bos.compileSignal({ batch_id: batchId });
      await context.queryClient.invalidateQueries({ queryKey: ["bos"] });
      await context.queryClient.invalidateQueries({ queryKey: ["batches"] });
      return {
        status: "completed",
        body: `BOS compiled a fresh signal for batch ${compiled.batch_id}.`,
        structuredResult: {
          title: "Signal compiled",
          summary: "BOS compiled a new signal packet and returned the fresh signal posture.",
          metrics: [
            { label: "Batch", value: String(compiled.batch_id), hint: compiled.compiled_signal_id || "Compiled signal" },
            { label: "Freshness", value: compiled.freshness_state || "Unknown", hint: compiled.compile_status },
            { label: "Potency", value: formatNumber(compiled.potency, 4), hint: compiled.potency_unit || "SER-equivalent" },
            { label: "Stability(h)", value: formatNumber(compiled.stability_window_hours, 2), hint: compiled.source_mode },
          ],
          actions: [{ label: "Open signal lab", to: `/bos/signal-lab?batchId=${compiled.batch_id}` }],
        },
      };
    }
    case "refresh_signal": {
      const signals = await ensureSignals(context);
      let signal =
        context.requestedEntityId != null
          ? signals
              .filter((item) => item.batch_id === context.requestedEntityId || item.id === context.requestedEntityId)
              .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null
          : null;
      if (!signal) {
        signal = [...signals].sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null;
      }
      if (!signal) {
        return {
          status: "blocked",
          body: "BOS could not find a signal to refresh yet.",
          structuredResult: {
            title: "No signal is available to refresh",
            summary: "BOS could not find any compiled signal packets yet.",
            actions: [{ label: "Open signal lab", to: "/bos/signal-lab" }],
          },
        };
      }
      const refreshed = await context.apiClients.bos.refreshSignal(signal.id);
      await context.queryClient.invalidateQueries({ queryKey: ["bos"] });
      await context.queryClient.invalidateQueries({ queryKey: ["batches"] });
      return {
        status: "completed",
        body: `BOS refreshed signal ${refreshed.signal_batch.compiled_signal_id || refreshed.signal_batch.id}.`,
        structuredResult: {
          title: "Signal refreshed",
          summary: "BOS refreshed the latest signal state against current batch timing and metering freshness.",
          metrics: [
            { label: "Signal", value: refreshed.signal_batch.compiled_signal_id || `Signal ${refreshed.signal_batch.id}`, hint: `Batch ${refreshed.signal_batch.batch_id}` },
            { label: "Freshness", value: refreshed.refreshed_state, hint: `Age ${formatNumber(refreshed.metering_age_hours, 2)}h` },
            { label: "Freshness score", value: formatNumber(refreshed.freshness_score, 4), hint: "Signal timing quality" },
            { label: "Readiness score", value: formatNumber(refreshed.release_readiness_score, 4), hint: "Release posture estimate" },
          ],
          actions: [{ label: "Open signal lab", to: `/bos/signal-lab?batchId=${refreshed.signal_batch.batch_id}` }],
        },
      };
    }
    case "evaluate_supervisor": {
      const batchId = await resolveLatestBatchId(context);
      const signals = await ensureSignals(context);
      const signal =
        signals
          .filter((item) => item.batch_id === batchId)
          .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null;
      if (!signal) {
        return {
          status: "blocked",
          body: "BOS could not find a compiled signal for supervisor evaluation yet.",
          structuredResult: {
            title: "No compiled signal is available",
            summary: "BOS needs a compiled signal before it can run supervisor evaluation.",
            actions: [{ label: "Open signal lab", to: "/bos/signal-lab" }],
          },
        };
      }
      const observation = buildDefaultSupervisorObservation();
      context.intermediateData.supervisorObservation = observation;
      const supervisor = await context.apiClients.bos.evaluateSupervisor(signal.id, observation);
      await context.queryClient.invalidateQueries({ queryKey: ["bos"] });
      return {
        status: "completed",
        body: `BOS evaluated the supervisor posture for signal ${signal.compiled_signal_id || signal.id}.`,
        structuredResult: buildSupervisorResult(supervisor),
      };
    }
    case "handover_recommendation": {
      const batchId = await resolveLatestBatchId(context);
      const signals = await ensureSignals(context);
      const signal =
        signals
          .filter((item) => item.batch_id === batchId)
          .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null;
      if (!signal) {
        return {
          status: "blocked",
          body: "BOS could not find a compiled signal for handover recommendation yet.",
          structuredResult: {
            title: "No compiled signal is available",
            summary: "BOS needs a compiled signal before it can run handover recommendation.",
            actions: [{ label: "Open signal lab", to: "/bos/signal-lab" }],
          },
        };
      }
      const observation = buildDefaultSupervisorObservation();
      context.intermediateData.supervisorObservation = observation;
      const recommendation = await context.apiClients.bos.getHandoverRecommendation(signal.id, observation);
      await context.queryClient.invalidateQueries({ queryKey: ["bos"] });
      return {
        status: "completed",
        body: `BOS evaluated the handover recommendation for signal ${signal.compiled_signal_id || signal.id}.`,
        structuredResult: buildHandoverRecommendationResult(recommendation),
      };
    }
    default:
      throw new Error(`Unsupported signal runtime intent: ${context.intent}`);
  }
}
