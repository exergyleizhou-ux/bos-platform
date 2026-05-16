import type { AxiosError } from "axios";
import {
  ArrowRight,
  Bot,
  Compass,
  Download,
  Image as ImageIcon,
  Orbit,
  PanelLeftClose,
  PanelLeftOpen,
  PenLine,
  Search,
  SendHorizontal,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import toast from "react-hot-toast";
import { useQueryClient } from "@tanstack/react-query";

import { assistantApi } from "@/api/assistantApi";
import { batchApi } from "@/api/batchApi";
import { bosApi } from "@/api/bosApi";
import { dashboardApi } from "@/api/dashboardApi";
import { codeApi } from "@/api/codeApi";
import { mediaApi } from "@/api/mediaApi";
import { twinApi } from "@/api/twinApi";
import { GradeBarChart } from "@/components/charts/GradeBarChart";
import { SERTrendChart } from "@/components/charts/SERTrendChart";
import { SpeciesPieChart } from "@/components/charts/SpeciesPieChart";
import { TwinTrajectoryChart } from "@/components/charts/TwinTrajectoryChart";
import { CodeRuntimeHud } from "@/components/code/CodeRuntimeHud";
import { AssistantArrivalEffect } from "@/components/layout/AssistantArrivalEffect";
import { Badge } from "@/components/ui/Badge";
import { BOSSigil } from "@/components/ui/BOSSigil";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { CockpitPanel, CockpitSectionLabel } from "@/components/ui/Cockpit";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { SurfaceTileButton } from "@/components/ui/SurfaceTile";
import { Spinner } from "@/components/ui/Spinner";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "@/components/ui/Table";
import { Textarea } from "@/components/ui/Textarea";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import {
  codeKeys,
  useCodeOrchestration,
  useCodeSession,
  useCodeSessionEvents,
  useCodeSessions,
  useCreateCodeSession,
  useCodeRuntime,
  useExecuteNextAutomationAction,
  useUpdateCodeSession,
} from "@/hooks/code/useCode";
import { formatCodeActionCallToAction } from "@/lib/codeActionPolicy";
import { translateText, type AppLocale } from "@/lib/i18n";
import { getLatestProviderIssue } from "@/lib/codeProviderUi";
import {
  scopedAutomationAction,
  runtimeStatusLabel as sessionStatusLabel,
  runtimeStatusVariant as sessionStatusVariant,
} from "@/lib/codeRuntimeUi";
import {
  buildBosAssistantHelpResult,
  detectBosAssistantIntent,
  getBosAssistantGraphName,
  type AssistantStructuredResult,
} from "@/lib/bosAssistant";
import {
  createBosGraphContext,
  runBosGraphWithFallback,
  type BosGraphNodeOutput,
} from "@/lib/bosGraph";
import { getAuditPacketReadModel } from "@/lib/bos-read-model";
import { downloadBlob, formatDateTime, formatNumber, formatPercent, formatRelativeTime, truncate } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import { hasMinimumRole } from "@/types/auth";
import type {
  AuditPacket,
  BrainRuntimeResponse,
  HandoverRecommendationResponse,
  ManuscriptCampaignCatalogResponse,
  NativeModelRuntimeStatus,
  ReleaseDecision,
  SignalBatch,
  SupervisorObservationRequest,
  SupervisorStateResponse,
  TimeseriesRiskResponse,
} from "@/types/bos";
import type { VisionObservation } from "@/types/vision";
import type { CodeSession, CodeTurn } from "@/types/code";
import type {
  DashboardSummary,
  RecentActivityResponse,
  SERTrendResponse,
} from "@/types/dashboard";
import type { RemotionPresetCreateRequest, RemotionRenderKind } from "@/types/media";
import type { Batch } from "@/types/batch";
import type { AssistantRunResponse } from "@/types/assistant";

interface AssistantMediaResult {
  kind: RemotionRenderKind;
  templateId: string;
  fileName: string;
  previewUrl: string;
  createdAt: string;
  presetPayload: RemotionPresetCreateRequest;
  savedPresetName?: string | null;
  sourcePrompt?: string;
  canGenerateAnimation?: boolean;
  animationGenerated?: boolean;
}

interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  body: string;
  createdAt: string | null;
  pending?: boolean;
  streaming?: boolean;
  mediaResult?: AssistantMediaResult;
  structuredResult?: AssistantStructuredResult;
}

interface PersistedThreadTitles {
  [sessionId: number]: string;
}

interface PersistedDrafts {
  [sessionId: number]: string;
}

interface PersistedResearchReviewRuns {
  [sessionId: number]: string;
}

interface AssistantLayoutPrefs {
  leftCollapsed: boolean;
  density: "comfortable" | "compact";
}

interface BosAssistantExecutionResult {
  body: string;
  structuredResult: AssistantStructuredResult;
}

const THINKING_STEPS = [
  {
    eyebrow: "Thinking",
    title: "Gathering the live thread",
    detail: "Pulling the latest context, operator intent, and nearby decision surfaces into one view.",
  },
  {
    eyebrow: "Weighing",
    title: "Balancing signal against noise",
    detail: "Holding the thread steady long enough to surface the next move instead of reacting too early.",
  },
  {
    eyebrow: "Routing",
    title: "Shaping the response",
    detail: "Turning the current posture into a clear answer, with the right surface ready behind it.",
  },
] as const;

const DEFAULT_LAYOUT_PREFS: AssistantLayoutPrefs = {
  leftCollapsed: true,
  density: "comfortable",
};

const ASSISTANT_TEAM_PROVIDER = "openai-team";
const DEFAULT_ASSISTANT_MODEL = "gpt-5.5";
const ASSISTANT_ALLOWED_MODELS = ["gpt-5.5", "gpt-5.4"] as const;

const QUICK_LINKS = [
  {
    title: "Batches",
    description: "Open the live batch surface and inspect current production state.",
    to: "/batches",
  },
  {
    title: "Release",
    description: "Jump into release readiness, verification posture, and trust signals.",
    to: "/release",
  },
  {
    title: "Twins",
    description: "Move directly into digital twin projections and scenario inspection.",
    to: "/twins",
  },
  {
    title: "Forecast",
    description: "Check trend pressure, drift, and what is likely to move next.",
    to: "/forecast",
  },
  {
    title: "Media",
    description: "Generate BOS-branded stills and short animations from the internal Remotion runtime.",
    to: "/bos/media",
  },
];

function threadGlyph(title: string) {
  const clean = title.replace(/[^A-Za-z0-9\u4e00-\u9fff ]/g, "").trim();
  if (!clean) return "BO";
  const tokens = clean.split(/\s+/).filter(Boolean);
  if (tokens.length >= 2) return `${tokens[0][0]}${tokens[1][0]}`.toUpperCase();
  return clean.slice(0, 2).toUpperCase();
}

function threadTone(title: string) {
  const value = title.toLowerCase();
  if (value.includes("release") || value.includes("risk")) {
    return {
      shell: "from-amber-400/18 to-red-400/10 text-amber-100",
      label: "Pressure",
    };
  }
  if (value.includes("batch") || value.includes("issue")) {
    return {
      shell: "from-sky-400/18 to-brand-400/10 text-sky-100",
      label: "Field",
    };
  }
  if (value.includes("forecast") || value.includes("trend")) {
    return {
      shell: "from-violet-400/18 to-sky-400/10 text-violet-100",
      label: "Signal",
    };
  }
  return {
    shell: "from-brand-400/18 to-white/8 text-brand-100",
    label: "Thread",
  };
}

function deriveThreadTitle(message: string) {
  const cleaned = message
    .replace(/\s+/g, " ")
    .replace(/^[-\s]+/, "")
    .replace(/^(please|can you|could you|help me)\s+/i, "")
    .trim();
  if (!cleaned) return "New thread";

  const sentence = cleaned.split(/(?<=[.!?])\s+/)[0] ?? cleaned;
  const normalized = sentence.replace(/[.?!,:;]+$/g, "").trim();
  const titled = normalized.charAt(0).toUpperCase() + normalized.slice(1);
  return truncate(titled, 42);
}

function isResearchReviewFollowUp(message: string, parentRunId?: string | null) {
  if (!parentRunId) return false;
  const text = message.trim().toLowerCase();
  if (!text) return false;
  return (
    /continue|follow up|deeper|counterexample|failure mode|mechanistic analyst|mechanism|evidence auditor|scientific reviewer/.test(
      text,
    ) || /继续|追问|深挖|反证|失效|机制分析师|机制|证据审计|科学审校/.test(message)
  );
}

export function resolveResearchReviewContinuationParentRunId(
  message: string,
  latestResearchReviewRunId?: string | null,
) {
  const detectedIntent = detectBosAssistantIntent(message);
  const intent =
    detectedIntent ??
    (isResearchReviewFollowUp(message, latestResearchReviewRunId) ? "research_review" : null);
  if (intent !== "research_review") return null;
  return isResearchReviewFollowUp(message, latestResearchReviewRunId)
    ? latestResearchReviewRunId ?? null
    : null;
}

function isAllowedAssistantModel(model?: string | null): model is (typeof ASSISTANT_ALLOWED_MODELS)[number] {
  return Boolean(model && ASSISTANT_ALLOWED_MODELS.includes(model as (typeof ASSISTANT_ALLOWED_MODELS)[number]));
}

function buildAssistantModelOptions(runtimeModels: string[]) {
  const available = new Set(runtimeModels);
  return ASSISTANT_ALLOWED_MODELS
    .filter((model) => available.size === 0 || available.has(model))
    .map((model) => ({ value: model, label: model }));
}

function assistantBlocks(content: string) {
  return content
    .replace(/\r\n/g, "\n")
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);
}

function renderAssistantBlock(block: string, key: string) {
  if (block.startsWith("```") && block.endsWith("```")) {
    const body = block.replace(/^```[^\n]*\n?/, "").replace(/\n?```$/, "");
    return (
      <pre
        key={key}
        className="assistant-code-block overflow-x-auto rounded-[20px] px-4 py-4 text-sm leading-7 text-surface-100"
      >
        <code>{body}</code>
      </pre>
    );
  }

  const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
  const bulletLines = lines.filter((line) => /^[-*]\s+/.test(line));
  if (bulletLines.length === lines.length && bulletLines.length > 0) {
    return (
      <ul key={key} className="assistant-list-block space-y-3 pl-1">
        {bulletLines.map((line, index) => (
          <li key={`${key}-${index}`} className="assistant-list-row flex gap-3 text-[0.98rem] leading-8 text-surface-100">
            <span className="mt-[0.7rem] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-brand-300" />
            <span className="assistant-prose !leading-8">{line.replace(/^[-*]\s+/, "")}</span>
          </li>
        ))}
      </ul>
    );
  }

  const numberedLines = lines.filter((line) => /^\d+\.\s+/.test(line));
  if (numberedLines.length === lines.length && numberedLines.length > 0) {
    return (
      <ol key={key} className="assistant-list-block space-y-3 pl-1">
        {numberedLines.map((line, index) => (
          <li key={`${key}-${index}`} className="assistant-list-row flex gap-3 text-[0.98rem] leading-8 text-surface-100">
            <span className="assistant-list-index mt-[0.15rem] flex h-7 min-w-[1.75rem] items-center justify-center rounded-full text-xs font-semibold text-surface-300">
              {index + 1}
            </span>
            <span className="assistant-prose !leading-8">{line.replace(/^\d+\.\s+/, "")}</span>
          </li>
        ))}
      </ol>
    );
  }

  const quoteLines = lines.filter((line) => /^>\s?/.test(line));
  if (quoteLines.length === lines.length && quoteLines.length > 0) {
    return (
      <blockquote
        key={key}
        className="assistant-quote-block pl-4 text-[0.98rem] italic leading-8 text-surface-300"
      >
        {quoteLines.map((line) => line.replace(/^>\s?/, "")).join(" ")}
      </blockquote>
    );
  }

  if (/^#{1,3}\s+/.test(block)) {
    const level = block.match(/^#+/)?.[0].length ?? 1;
    const body = block.replace(/^#{1,3}\s+/, "");
    const headingClass =
      level === 1
        ? "text-xl font-semibold tracking-tight text-white"
        : level === 2
          ? "text-lg font-semibold text-white"
          : "text-base font-semibold text-surface-100";
    return (
      <h3 key={key} className={headingClass}>
        {body}
      </h3>
    );
  }

  return (
    <p key={key} className="assistant-prose text-[1rem]">
      {block}
    </p>
  );
}

function sessionLabel(session: CodeSession, turns: CodeTurn[] | undefined) {
  if (session.title?.trim()) return session.title.trim();
  const firstTurn = turns?.[0]?.user_message?.trim();
  if (firstTurn) return deriveThreadTitle(firstTurn);
  return `Thread ${session.id}`;
}

function renderSessionButton(
  session: CodeSession,
  {
    sessionId,
    sessionDetailId,
    persistedTitle,
    turns,
    onSelect,
  }: {
    sessionId: number | null;
    sessionDetailId: number | undefined;
    persistedTitle?: string;
    turns: CodeTurn[] | undefined;
    onSelect: (id: number) => void;
  },
) {
  const isActive = session.id === sessionId;
  const derivedTurns = isActive && sessionDetailId === session.id ? turns : undefined;
  const summarySource = derivedTurns?.[derivedTurns.length - 1]?.assistant_summary || derivedTurns?.[0]?.user_message || "";
  const summary = truncate(summarySource.replace(/\s+/g, " ").trim(), 74);
  const resolvedTitle = session.title?.trim() || persistedTitle || sessionLabel(session, derivedTurns);
  const tone = threadTone(resolvedTitle);

  return (
    <SurfaceTileButton
      key={session.id}
      onClick={() => onSelect(session.id)}
      selected={isActive}
      className="assistant-thread-button w-full rounded-[24px] px-4 py-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div
          className={[
            "flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-gradient-to-br text-xs font-semibold tracking-[0.18em]",
            tone.shell,
          ].join(" ")}
        >
          {threadGlyph(resolvedTitle)}
        </div>
        <div className="min-w-0">
          <p className="line-clamp-2 text-sm font-semibold leading-6 text-white">
            {resolvedTitle}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-surface-400">
            <span>{session.updated_at ? formatRelativeTime(session.updated_at) : translateText("Just opened")}</span>
            <Badge variant="neutral" size="xs" className="assistant-thread-note-badge">
              {translateText(tone.label)}
            </Badge>
            {isActive ? (
              <Badge variant="info" size="xs" className="assistant-thread-note-badge">
                {translateText("current")}
              </Badge>
            ) : null}
          </div>
          {summary ? (
            <p className="mt-2 line-clamp-2 text-xs leading-6 text-surface-500">
              {summary}
            </p>
          ) : null}
        </div>
        <Badge variant={sessionStatusVariant(session.session_status)} size="xs" className="assistant-thread-status-badge">
          {translateText(sessionStatusLabel(session.session_status))}
        </Badge>
      </div>
    </SurfaceTileButton>
  );
}

function threadMetaCopy(total: number, filtered: number, query: string) {
  if (!total) return translateText("No prior thread history yet.");
  if (!query.trim()) {
    return translateText(`${total} recent thread${total > 1 ? "s" : ""} ready to resume.`);
  }
  return translateText(`${filtered} of ${total} thread${total > 1 ? "s" : ""} match this search.`);
}

function summarizeReleaseDecisions(decisions: ReleaseDecision[]) {
  return decisions.reduce<Record<string, number>>((accumulator, item) => {
    const key = item.decision || "UNKNOWN";
    accumulator[key] = (accumulator[key] ?? 0) + 1;
    return accumulator;
  }, {});
}

function summarizeSignalFreshness(signals: SignalBatch[]) {
  return signals.reduce<Record<string, number>>((accumulator, item) => {
    const key = item.freshness_state || "Unknown";
    accumulator[key] = (accumulator[key] ?? 0) + 1;
    return accumulator;
  }, {});
}

function latestBatchUpdateLabel(items: Array<{ updated_at?: string | null; timestamp?: string | null }>) {
  const timestamps = items
    .map((item) => item.updated_at ?? item.timestamp ?? null)
    .filter((value): value is string => Boolean(value))
    .sort((left, right) => Date.parse(right) - Date.parse(left));
  return timestamps[0] ? formatDateTime(timestamps[0]) : "N/A";
}

function buildOverviewResult(args: {
  summary: DashboardSummary;
  trend: SERTrendResponse;
  activity: RecentActivityResponse;
  batchesTotal: number;
  signals: SignalBatch[];
  audits: AuditPacket[];
  decisions: ReleaseDecision[];
  twinsTotal: number;
  riskItems?: TimeseriesRiskResponse[];
}): AssistantStructuredResult {
  const releaseCounts = summarizeReleaseDecisions(args.decisions);
  const signalFreshness = summarizeSignalFreshness(args.signals);
  const topRisk = args.riskItems
    ?.slice()
    .sort((left, right) => right.future_risk_score - left.future_risk_score)[0];

  return {
    title: "BOS executive overview",
    summary:
      "This is the fastest cross-surface summary of current BOS posture, combining dashboard, signal, audit, release, and twin coverage.",
    metrics: [
      {
        label: "Total batches",
        value: String(args.summary.total_batches || args.batchesTotal),
        hint: `Updated ${latestBatchUpdateLabel(args.activity.activities)}`,
      },
      {
        label: "Average SER",
        value: formatNumber(args.summary.avg_ser, 4),
        hint: "System-wide SER posture",
      },
      {
        label: "Pass rate",
        value: formatPercent(args.summary.avg_pass_rate),
        hint: "Qualified output share",
      },
      {
        label: "Signals online",
        value: String(args.signals.length),
        hint: `Fresh ${signalFreshness.Fresh ?? 0} / Stable ${signalFreshness.Stable ?? 0}`,
      },
      {
        label: "Audit packets",
        value: String(args.audits.length),
        hint: `Release PASS ${releaseCounts.PASS ?? 0}`,
      },
      {
        label: "Twins",
        value: String(args.summary.total_twins || args.twinsTotal),
        hint: "Digital twin surfaces available",
      },
      ...(topRisk
        ? [
            {
              label: "Model risk",
              value: formatPercent(topRisk.future_risk_score),
              hint: `${topRisk.batch_label} · ${topRisk.execution_mode}`,
            },
          ]
        : []),
    ],
    chart: {
      kind: "ser-trend",
      title: "SER trend",
      data: args.trend.data_points,
    },
    notes: [
      `Release decisions: PASS ${releaseCounts.PASS ?? 0}, PASS_WITH_RETUNING ${releaseCounts.PASS_WITH_RETUNING ?? 0}, FAIL ${releaseCounts.FAIL ?? 0}`,
      `Signal freshness: Fresh ${signalFreshness.Fresh ?? 0}, Stable ${signalFreshness.Stable ?? 0}, Stale ${signalFreshness.Stale ?? 0}`,
      topRisk
        ? `Model-backed risk: ${topRisk.batch_label} future ${formatPercent(topRisk.future_risk_score)}, release warning ${formatPercent(topRisk.release_warning_score)}.`
        : "Model-backed risk metrics are not available yet.",
      args.activity.activities[0]
        ? `Latest activity: ${args.activity.activities[0].description}`
        : "Latest activity feed is currently empty.",
    ],
    actions: [
      { label: "Open dashboard", to: "/dashboard" },
      { label: "Open signal lab", to: "/bos/signal-lab" },
      { label: "Open release center", to: "/release" },
    ],
  };
}

function buildBatchesTableResult(payload: Awaited<ReturnType<typeof batchApi.list>>): AssistantStructuredResult {
  return {
    title: "Batch table",
    summary: "Recent batch state, species, substrate, and SER posture from the main BOS batch surface.",
    table: {
      columns: ["Batch", "Status", "Species", "Substrate", "SER", "Updated"],
      rows: payload.items.slice(0, 12).map((item) => [
        item.batch_id,
        item.status,
        item.species,
        item.substrate || "N/A",
        formatNumber(item.ser_value, 4),
        formatDateTime(item.updated_at),
      ]),
    },
    notes: [`Showing ${Math.min(payload.items.length, 12)} of ${payload.total} batches.`],
    actions: [{ label: "Open batch command", to: "/batches" }],
  };
}

function buildSignalsTableResult(signals: SignalBatch[]): AssistantStructuredResult {
  return {
    title: "Signal table",
    summary: "Compiled signal posture including potency, freshness, and stability window.",
    table: {
      columns: ["Signal", "Batch", "Freshness", "Potency", "Stability(h)", "Updated"],
      rows: signals.slice(0, 12).map((item) => [
        item.compiled_signal_id || `Signal ${item.id}`,
        String(item.batch_id),
        item.freshness_state || "Unknown",
        formatNumber(item.potency, 4),
        formatNumber(item.stability_window_hours, 2),
        formatDateTime(item.updated_at),
      ]),
    },
    notes: [`Showing ${Math.min(signals.length, 12)} live signal packets.`],
    actions: [{ label: "Open signal lab", to: "/bos/signal-lab" }],
  };
}

function buildAuditTableResult(audits: AuditPacket[]): AssistantStructuredResult {
  return {
    title: "Audit packet table",
    summary: "Decision-grade packet overview, including evidence level and release posture.",
    table: {
      columns: ["Packet", "Batch", "Evidence", "Decision", "Signal", "Generated"],
      rows: audits.slice(0, 12).map((item) => {
        const readModel = getAuditPacketReadModel(item);
        return [
          `Packet ${item.id}`,
          readModel.batchLabel,
          readModel.evidenceLevel,
          readModel.releaseDecision,
          readModel.signalLabel,
          formatDateTime(item.generated_at),
        ];
      }),
    },
    notes: [`Showing ${Math.min(audits.length, 12)} audit packets.`],
    actions: [
      { label: "Open signal lab", to: "/bos/signal-lab" },
      { label: "Open release center", to: "/release" },
    ],
  };
}

function buildTwinsTableResult(payload: Awaited<ReturnType<typeof twinApi.list>>): AssistantStructuredResult {
  return {
    title: "Twin table",
    summary: "Digital twin state, species, and latest runtime posture.",
    table: {
      columns: ["Twin", "Species", "Biomass", "Substrate", "Version", "Updated"],
      rows: payload.items.slice(0, 12).map((item) => [
        item.name,
        item.species || "N/A",
        formatNumber(item.state.biomass, 3),
        formatNumber(item.state.substrate, 3),
        String(item.version),
        formatDateTime(item.updated_at),
      ]),
    },
    notes: [`Showing ${Math.min(payload.items.length, 12)} of ${payload.total} twins.`],
    actions: [{ label: "Open twins", to: "/twins" }],
  };
}

function buildBrainSummaryResult(runtime: BrainRuntimeResponse): AssistantStructuredResult {
  return {
    title: "Brain runtime summary",
    summary: "Persistent project memory, decision journal, and run ledger status from the BOS brain runtime.",
    metrics: [
      { label: "Documents", value: String(runtime.documents.length), hint: "Runtime memory surfaces" },
      { label: "Total lines", value: String(runtime.total_line_count), hint: "Loaded durable memory" },
      { label: "Root path", value: runtime.root_path, hint: "Repo-local memory area" },
      { label: "Last updated", value: formatDateTime(runtime.last_updated_at), hint: "Most recent runtime write" },
    ],
    table: {
      columns: ["Document", "Lines", "Missing", "Updated"],
      rows: runtime.documents.map((item) => [
        item.title,
        String(item.line_count),
        item.is_missing ? "Yes" : "No",
        formatDateTime(item.updated_at),
      ]),
    },
    actions: [{ label: "Open brain dashboard", to: "/bos/brain" }],
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

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function summaryRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function formatPlanStep(item: unknown) {
  const step = summaryRecord(item);
  const label = typeof step.step === "string" ? step.step : "step";
  const status = typeof step.status === "string" ? step.status : "planned";
  const policy = typeof step.policy === "string" ? step.policy : "unknown_policy";
  const tool = typeof step.tool === "string" ? step.tool : "unmapped_tool";
  return `${label}: ${status} via ${tool} (${policy})`;
}

export function buildSimulationLabAssistantResult(run: AssistantRunResponse): AssistantStructuredResult {
  const summary = run.result_summary ?? {};
  const parsedIntent = run.parsed_intent ?? {};
  const simulationId = typeof summary.simulation_id === "string" ? summary.simulation_id : null;
  const resultIds =
    summary.result_ids && typeof summary.result_ids === "object"
      ? (summary.result_ids as Record<string, unknown>)
      : {};
  const runId = typeof resultIds.run_id === "string" ? resultIds.run_id : typeof summary.run_id === "string" ? summary.run_id : null;
  const evidencePackId =
    typeof resultIds.evidence_pack_id === "string"
      ? resultIds.evidence_pack_id
      : run.evidence_pack_id;
  const releaseAttachmentId =
    typeof resultIds.release_attachment_id === "string" ? resultIds.release_attachment_id : null;
  const benchmarkRunId = typeof resultIds.benchmark_run_id === "string" ? resultIds.benchmark_run_id : null;
  const modelApprovalRequestId =
    typeof resultIds.model_approval_request_id === "string" ? resultIds.model_approval_request_id : null;
  const complianceGateId = typeof resultIds.compliance_gate_id === "string" ? resultIds.compliance_gate_id : null;
  const complianceEvidencePackId =
    typeof resultIds.compliance_evidence_pack_id === "string" ? resultIds.compliance_evidence_pack_id : null;
  const lcaResultId = typeof resultIds.lca_result_id === "string" ? resultIds.lca_result_id : null;
  const teaResultId = typeof resultIds.tea_result_id === "string" ? resultIds.tea_result_id : null;
  const scenario = typeof parsedIntent.scenario === "string" ? parsedIntent.scenario : "unknown";
  const cycles = typeof parsedIntent.cycles === "number" ? String(parsedIntent.cycles) : "unknown";
  const policy = typeof parsedIntent.policy === "string" ? parsedIntent.policy : "rule_based";
  const comparison = summary.comparison && typeof summary.comparison === "object"
    ? summary.comparison as { winner?: { lowest_risk?: unknown; highest_margin?: unknown } }
    : null;
  const exportReady = summary.export_ready === true ? "Ready" : "Review";
  const registryVersion =
    typeof summary.tool_registry_version === "string" ? summary.tool_registry_version : "assistant-tool-registry-v1";
  const executionPlan = Array.isArray(summary.execution_plan) ? summary.execution_plan.map(formatPlanStep) : [];
  const inputSnapshot = summaryRecord(summary.input_snapshot);
  const riskValueDrivers = summaryRecord(summary.risk_value_drivers);
  const humanReviewRequirement = summaryRecord(summary.human_review_requirement);
  const complianceGate = summaryRecord(summary.compliance_gate);
  const lcaValueProof = summaryRecord(summary.lca_value_proof);
  const teaValueProof = summaryRecord(summary.tea_value_proof);
  const uncertaintyWarnings = stringArray(summary.uncertainty_warnings);
  const nextSafeActions = Array.isArray(summary.next_safe_actions)
    ? summary.next_safe_actions.map((item) => summaryRecord(item))
    : [];
  const confirmationRequests = run.confirmation_requests ?? [];
  const reviewState =
    typeof humanReviewRequirement.state === "string" ? humanReviewRequirement.state : "review_required";
  const reviewRequiredFor = stringArray(humanReviewRequirement.required_for);
  const inputSnapshotNotes = [
    typeof inputSnapshot.reference_id === "string" ? `Reference: ${inputSnapshot.reference_id}` : null,
    typeof inputSnapshot.scenario === "string" ? `Scenario: ${inputSnapshot.scenario}` : null,
    typeof inputSnapshot.cycles === "number" ? `Cycles: ${inputSnapshot.cycles}` : null,
    typeof inputSnapshot.policy === "string" ? `Policy: ${inputSnapshot.policy}` : null,
  ].filter((item): item is string => Boolean(item));
  const safeActionNotes = nextSafeActions.map((action) => {
    const label = typeof action.label === "string" ? action.label : "Next action";
    const target = typeof action.target === "string" ? action.target : "pending";
    const confirmation = action.requires_confirmation === "true" ? "confirmation required" : "no confirmation";
    return `${label}: ${target} (${confirmation})`;
  });
  const confirmationQueueNotes = confirmationRequests.map((confirmation) => {
    const payload = confirmation.action_payload ?? {};
    const execution = typeof payload.execution === "string" ? ` / ${payload.execution}` : "";
    return `${confirmation.action_name}: ${confirmation.status}${execution}`;
  });
  const complianceStatus = typeof complianceGate.status === "string" ? complianceGate.status : null;
  const complianceMissingAssays = stringArray(complianceGate.missing_assays);
  const complianceBlockedReasons = stringArray(complianceGate.blocked_reasons);
  const lcaResult = summaryRecord(lcaValueProof.result);
  const teaResult = summaryRecord(teaValueProof.result);
  const lcaAbatement =
    typeof lcaResult.co2e_abatement_kg === "number" ? `${formatNumber(lcaResult.co2e_abatement_kg, 2)} kg` : null;
  const teaMargin =
    typeof teaResult.gross_margin_usd === "number" ? `$${formatNumber(teaResult.gross_margin_usd, 2)}` : null;

  return {
    title: "Simulation Lab assistant run",
    summary:
      run.status === "completed"
        ? "BOS created the scenario, ran the virtual loop, captured tool calls, and linked evidence for review."
        : "BOS attempted a Simulation Lab run and returned the persisted assistant status for review.",
    metrics: [
      { label: "Status", value: run.status, hint: run.run_id },
      { label: "Scenario", value: scenario, hint: simulationId ?? "No simulation id returned" },
      { label: "Run ID", value: runId ? "Linked" : "Missing", hint: runId ?? "No RUN id returned" },
      { label: "Cycles", value: cycles, hint: `Policy ${policy}` },
      { label: "Tools", value: String(run.tool_calls.length), hint: `${run.tool_calls.filter((call) => call.status === "completed").length} completed` },
      { label: "Evidence", value: evidencePackId ? "Linked" : "Missing", hint: evidencePackId ?? "No evidence pack" },
      { label: "Registry", value: registryVersion, hint: "Stable Assistant tool registry contract" },
      { label: "Human review", value: reviewState, hint: reviewRequiredFor.join(", ") || "Review gate remains active" },
      ...(confirmationRequests.length
        ? [
            {
              label: "Confirmations",
              value: String(confirmationRequests.filter((item) => item.status === "pending").length),
              hint: "Pending queue items",
            },
          ]
        : []),
      { label: "Appendix", value: exportReady, hint: "Release appendix still requires review before attachment" },
      ...(releaseAttachmentId
        ? [{ label: "Release packet", value: "Attached", hint: releaseAttachmentId }]
        : []),
      ...(benchmarkRunId
        ? [{ label: "Benchmark", value: "Review gate", hint: benchmarkRunId }]
        : []),
      ...(modelApprovalRequestId
        ? [{ label: "Model review", value: "Pending", hint: modelApprovalRequestId }]
        : []),
      ...(complianceStatus
        ? [{ label: "Compliance", value: complianceStatus, hint: complianceEvidencePackId ?? complianceGateId ?? "Review gate" }]
        : []),
      ...(lcaResultId ? [{ label: "LCA proof", value: lcaAbatement ?? "Linked", hint: lcaResultId }] : []),
      ...(teaResultId ? [{ label: "TEA proof", value: teaMargin ?? "Linked", hint: teaResultId }] : []),
      ...(uncertaintyWarnings.length
        ? [{ label: "Uncertainty", value: String(uncertaintyWarnings.length), hint: uncertaintyWarnings.join(", ") }]
        : []),
    ],
    table: {
      columns: ["Tool", "Status", "Completed"],
      rows: run.tool_calls.map((call) => [
        call.tool_name,
        call.status,
        call.completed_at ? formatDateTime(call.completed_at) : "N/A",
      ]),
    },
    sections: [
      ...(executionPlan.length ? [{ title: "Executable plan", items: executionPlan }] : []),
      ...(inputSnapshotNotes.length ? [{ title: "Input snapshot", items: inputSnapshotNotes }] : []),
      {
        title: "Risk and value drivers",
        items: [...stringArray(riskValueDrivers.risk_drivers), ...stringArray(riskValueDrivers.value_drivers)],
      },
      ...(complianceStatus
        ? [
            {
              title: "Compliance gate result",
              items: [
                `Status: ${complianceStatus}`,
                ...(complianceMissingAssays.length ? [`Missing assays: ${complianceMissingAssays.join(", ")}`] : []),
                ...(complianceBlockedReasons.length ? [`Blocked reasons: ${complianceBlockedReasons.join(", ")}`] : []),
                complianceEvidencePackId ? `Evidence pack: ${complianceEvidencePackId}` : null,
              ].filter((item): item is string => Boolean(item)),
            },
          ]
        : []),
      ...(lcaResultId
        ? [
            {
              title: "LCA value proof",
              items: [
                lcaAbatement ? `CO2e abatement: ${lcaAbatement}` : null,
                typeof lcaResult.baseline_co2e_kg === "number" ? `Baseline CO2e: ${formatNumber(lcaResult.baseline_co2e_kg, 2)} kg` : null,
                typeof lcaResult.alternative_co2e_kg === "number"
                  ? `Alternative CO2e: ${formatNumber(lcaResult.alternative_co2e_kg, 2)} kg`
                  : null,
              ].filter((item): item is string => Boolean(item)),
            },
          ]
        : []),
      ...(teaResultId
        ? [
            {
              title: "TEA value proof",
              items: [
                teaMargin ? `Gross margin: ${teaMargin}` : null,
                typeof teaResult.revenue_usd === "number" ? `Revenue: $${formatNumber(teaResult.revenue_usd, 2)}` : null,
                typeof teaResult.operating_cost_usd === "number"
                  ? `Operating cost: $${formatNumber(teaResult.operating_cost_usd, 2)}`
                  : null,
              ].filter((item): item is string => Boolean(item)),
            },
          ]
        : []),
      ...(uncertaintyWarnings.length ? [{ title: "Uncertainty warnings", items: uncertaintyWarnings }] : []),
      ...(confirmationQueueNotes.length ? [{ title: "Human confirmation queue", items: confirmationQueueNotes }] : []),
      ...(safeActionNotes.length ? [{ title: "Next safe actions", items: safeActionNotes }] : []),
    ],
    notes: [
      comparison?.winner?.lowest_risk ? `Lowest-risk policy: ${String(comparison.winner.lowest_risk)}` : "Policy comparison was not requested or did not return a winner.",
      comparison?.winner?.highest_margin ? `Highest-margin policy: ${String(comparison.winner.highest_margin)}` : "Margin winner is unavailable in this run.",
      simulationId ? `Simulation ID: ${simulationId}` : "No SIM id was returned.",
      runId ? `Run ID: ${runId}` : "No RUN id was returned.",
      evidencePackId ? `Evidence pack: ${evidencePackId}` : "No evidence pack was linked to this assistant run.",
      releaseAttachmentId ? `Release attachment: ${releaseAttachmentId}` : "Release packet attachment was not requested.",
      benchmarkRunId ? `Benchmark run: ${benchmarkRunId}` : "Benchmark run was not requested.",
      modelApprovalRequestId ? `Human approval request: ${modelApprovalRequestId}` : "Model governance review was not requested.",
      complianceGateId ? `Compliance gate: ${complianceGateId}` : "Compliance gate was not requested.",
      lcaResultId ? `LCA result: ${lcaResultId}` : "LCA proof was not requested.",
      teaResultId ? `TEA result: ${teaResultId}` : "TEA proof was not requested.",
    ],
    actions: [
      { label: "Open Simulation Lab", to: "/bos/simulation-lab" },
      ...(simulationId ? [{ label: "View scenario", to: `/bos/simulation-lab?simulationId=${simulationId}` }] : []),
      ...nextSafeActions
        .filter((action) => typeof action.target === "string" && action.target.startsWith("/"))
        .map((action) => ({
          label: typeof action.label === "string" ? action.label : "Open target",
          to: action.target as string,
        })),
    ],
  };
}

function formatResearchReviewStep(item: unknown) {
  const step = summaryRecord(item);
  const stage = typeof step.stage === "number" ? `S${step.stage}` : "S?";
  const title = typeof step.title === "string" ? step.title : "Specialist";
  const objective = typeof step.objective === "string" ? step.objective : "Review objective pending";
  return `${stage} ${title}: ${objective}`;
}

function formatResearchReviewCard(item: unknown) {
  const card = summaryRecord(item);
  const title = typeof card.title === "string" ? card.title : "Specialist";
  const id = typeof card.specialist_id === "string" ? card.specialist_id : "unknown";
  const deliverable = typeof card.deliverable === "string" ? card.deliverable : "Review-gated deliverable pending";
  const gate = card.review_required === true ? "review_required" : "review status pending";
  return `${title} (${id}): ${deliverable} [${gate}]`;
}

function formatResearchReviewAction(item: unknown) {
  const action = summaryRecord(item);
  const name = typeof action.action_name === "string" ? action.action_name : "research_action";
  const policy = typeof action.action_policy === "string" ? action.action_policy : "review_required";
  const status = typeof action.status === "string" ? action.status : "pending";
  const confirmation = action.requires_confirmation === true ? "confirmation required" : "internal only";
  return `${name}: ${status} / ${policy} / ${confirmation}`;
}

function findResearchReviewCard(cards: unknown[], specialistId: string) {
  return (
    cards
      .map(summaryRecord)
      .find((card) => {
        const id = typeof card.specialist_id === "string" ? card.specialist_id : "";
        return id === specialistId || id.includes(specialistId);
      }) ?? null
  );
}

function researchReviewDeliverable(cards: unknown[], specialistId: string, fallback: string) {
  const card = findResearchReviewCard(cards, specialistId);
  return typeof card?.deliverable === "string" && card.deliverable.trim() ? card.deliverable : fallback;
}

function researchReviewUncertainties(cards: unknown[], specialistId: string) {
  const card = findResearchReviewCard(cards, specialistId);
  return Array.isArray(card?.uncertainties) ? card.uncertainties.filter((item): item is string => typeof item === "string") : [];
}

function localeForText(text: string): AppLocale {
  return containsChinese(text) ? "zh-CN" : "en-US";
}

function localizedText(en: string, zh: string, locale: AppLocale) {
  return locale === "zh-CN" ? zh : en;
}

function specialistLabel(title: unknown, locale: AppLocale) {
  if (typeof title !== "string") return localizedText("Specialist", "专家", locale);
  if (locale !== "zh-CN" || containsChinese(title)) return title;
  const labels: Record<string, string> = {
    "Chief Scientist": "首席科学家",
    "Protocol Designer": "方案设计专家",
    "Mechanistic Analyst": "机制分析专家",
    "Reference Evidence Curator": "证据文献策展专家",
    "Digital Twin Analyst": "数字孪生分析专家",
    "Data Integrity Reviewer": "数据完整性审查专家",
    "Scientific Reviewer": "科学审查专家",
    "Evidence Auditor": "证据审计专家",
  };
  return labels[title] ?? title;
}

function cardText(cards: unknown[], specialistId: string, field: "deliverable" | "reasoning_summary", fallback: string) {
  const card = findResearchReviewCard(cards, specialistId);
  const value = card?.[field];
  return typeof value === "string" && value.trim() ? value : fallback;
}

function formatResearchDebateTurn(item: unknown, locale: AppLocale) {
  const turn = summaryRecord(item);
  const speaker = typeof turn.speaker === "string" ? turn.speaker : localizedText("Expert", "专家", locale);
  const stance = typeof turn.stance === "string" ? turn.stance : localizedText("No stance recorded.", "未记录立场。", locale);
  const challenges =
    typeof turn.challenges === "string" ? turn.challenges : localizedText("No challenge recorded.", "未记录追问。", locale);
  const reply = typeof turn.reply === "string" && turn.reply.trim() ? turn.reply : null;
  return locale === "zh-CN"
    ? `${speaker}：${stance} 追问：${challenges}${reply ? ` 回应：${reply}` : ""}`
    : `${speaker}: ${stance} Challenge: ${challenges}${reply ? ` Reply: ${reply}` : ""}`;
}

function buildResearchDebateSynthesis(cards: unknown[], finalSynthesis: Record<string, unknown>, locale: AppLocale) {
  const debateTurns = Array.isArray(finalSynthesis.debate_turns)
    ? finalSynthesis.debate_turns.map((item) => formatResearchDebateTurn(item, locale))
    : [];
  if (debateTurns.length) return debateTurns;

  return [
    localizedText(
      `Mechanistic Analyst: ${cardText(
        cards,
        "mechanistic_analyst",
        "reasoning_summary",
        "Mechanism fit must be challenged before any positive interpretation.",
      )}`,
      `机制分析专家：${cardText(cards, "mechanistic_analyst", "reasoning_summary", "先质疑机制和基质匹配，再解释正向结果。")}`,
      locale,
    ),
    localizedText(
      `Protocol Designer: ${cardText(
        cards,
        "protocol_designer",
        "deliverable",
        "Move through controls, desk review, and simulation scenarios before execution.",
      )}`,
      `方案设计专家：${cardText(cards, "protocol_designer", "deliverable", "先定义对照、桌面审查和仿真情景，再进入执行。")}`,
      locale,
    ),
    localizedText(
      `Evidence Auditor: ${cardText(
        cards,
        "evidence_auditor",
        "reasoning_summary",
        "Every claim needs source evidence or an explicit uncertainty note.",
      )}`,
      `证据审计专家：${cardText(cards, "evidence_auditor", "reasoning_summary", "每个结论都需要来源证据或明确不确定性。")}`,
      locale,
    ),
  ];
}

function looksLikeEnglishResearchBoilerplate(text: string) {
  return (
    text.includes("BOS has formed a fixed expert review team") ||
    text.includes("BOS formed a fixed expert review team") ||
    text.includes("BOS produced a review-gated research protocol critique")
  );
}

function formatResearchReasoningStage(item: unknown, locale: AppLocale) {
  const stage = summaryRecord(item);
  const name = typeof stage.stage === "string" ? stage.stage : localizedText("Reasoning stage", "推演阶段", locale);
  const status = typeof stage.status === "string" ? stage.status : "pending";
  const readout =
    typeof stage.readout === "string"
      ? stage.readout
      : localizedText("No stage readout recorded.", "未记录阶段推演。", locale);
  return locale === "zh-CN" ? `${name} [${status}]：${readout}` : `${name} [${status}]: ${readout}`;
}

function formatResearchEvidenceStatus(item: unknown, locale: AppLocale) {
  const evidence = summaryRecord(item);
  const claim = typeof evidence.claim === "string" ? evidence.claim : localizedText("Evidence claim", "证据判断", locale);
  const status = typeof evidence.status === "string" ? evidence.status : "candidate_evidence";
  const basis = typeof evidence.basis === "string" ? evidence.basis : localizedText("Basis pending review.", "依据待审查。", locale);
  const gate = typeof evidence.gate === "string" ? evidence.gate : "review_required";
  const sourceRef = typeof evidence.source_ref === "string" && evidence.source_ref.trim() ? ` / ${evidence.source_ref}` : "";
  return locale === "zh-CN"
    ? `${claim}：${status} / ${gate}${sourceRef}。${basis}`
    : `${claim}: ${status} / ${gate}${sourceRef}. ${basis}`;
}

function formatResearchExperimentStep(item: unknown, locale: AppLocale) {
  const step = summaryRecord(item);
  const label = typeof step.step === "string" ? step.step : localizedText("Pilot step", "小试步骤", locale);
  const design = typeof step.design === "string" ? step.design : localizedText("Design pending.", "设计待补齐。", locale);
  const controls = Array.isArray(step.controls)
    ? step.controls.filter((control): control is string => typeof control === "string")
    : [];
  const stopRule = typeof step.stop_rule === "string" ? step.stop_rule : localizedText("Stop rule pending.", "停止规则待补齐。", locale);
  const gate = typeof step.gate === "string" ? step.gate : "review_required";
  const controlText = controls.length
    ? localizedText(`Controls: ${controls.join(", ")}`, `对照：${controls.join("、")}`, locale)
    : localizedText("Controls pending", "对照待补齐", locale);
  return locale === "zh-CN"
    ? `${label} [${gate}]：${design} ${controlText}。停止规则：${stopRule}`
    : `${label} [${gate}]: ${design} ${controlText}. Stop rule: ${stopRule}`;
}

export function buildResearchReviewAssistantResult(run: AssistantRunResponse): AssistantStructuredResult {
  const summary = run.result_summary ?? {};
  const finalSynthesis = summaryRecord(run.final_synthesis ?? summary.final_synthesis);
  const continuity = summaryRecord(finalSynthesis.continuity ?? summary.continuity_context);
  const parentRunId = typeof continuity.parent_run_id === "string" ? continuity.parent_run_id : null;
  const locale = localeForText(run.user_message);
  const approvalState =
    typeof finalSynthesis.approval_state === "string" ? finalSynthesis.approval_state : "review_required";
  const rawUnifiedAnswer =
    typeof finalSynthesis.unified_answer === "string"
      ? finalSynthesis.unified_answer
      : "BOS produced a review-gated research protocol critique.";
  const unifiedAnswer =
    locale === "zh-CN" && looksLikeEnglishResearchBoilerplate(rawUnifiedAnswer)
      ? "BOS 已启动固定专家团队，并把这次判断保留在 review_required：先给研究优先级和可验证路径，不自动批准、不外发、不写入 validated defaults。"
      : rawUnifiedAnswer;
  const teamPlan = run.team_plan?.length ? run.team_plan : Array.isArray(summary.team_plan) ? summary.team_plan : [];
  const specialistCards = run.specialist_cards?.length
    ? run.specialist_cards
    : Array.isArray(summary.specialist_cards)
      ? summary.specialist_cards
      : [];
  const verdicts = run.review_verdicts?.length
    ? run.review_verdicts
    : Array.isArray(summary.review_verdicts)
      ? summary.review_verdicts
      : [];
  const actionLedger = run.action_ledger?.length
    ? run.action_ledger
    : Array.isArray(summary.action_ledger)
      ? summary.action_ledger
      : [];
  const evidencePackId =
    run.evidence_pack_id ?? (typeof finalSynthesis.evidence_pack_id === "string" ? finalSynthesis.evidence_pack_id : null);
  const reviewPacketId =
    typeof finalSynthesis.review_packet_snapshot_id === "string" ? finalSynthesis.review_packet_snapshot_id : null;
  const blockedActions = actionLedger.filter((item) => summaryRecord(item).action_policy === "forbidden");
  const confirmationActions = actionLedger.filter((item) => summaryRecord(item).requires_confirmation === true);
  const recommendedNextSteps = Array.isArray(finalSynthesis.recommended_next_steps)
    ? finalSynthesis.recommended_next_steps.filter((item): item is string => typeof item === "string")
    : [];
  const reasoningStages = Array.isArray(finalSynthesis.reasoning_stages)
    ? finalSynthesis.reasoning_stages.map((item) => formatResearchReasoningStage(item, locale))
    : [];
  const evidenceStatuses = Array.isArray(finalSynthesis.evidence_status)
    ? finalSynthesis.evidence_status.map((item) => formatResearchEvidenceStatus(item, locale))
    : [];
  const experimentPlan = Array.isArray(finalSynthesis.experiment_plan)
    ? finalSynthesis.experiment_plan.map((item) => formatResearchExperimentStep(item, locale))
    : [];
  const evidenceVerdict = verdicts
    .map(summaryRecord)
    .find((item) => item.gate === "evidence_traceability" || item.gate === "evidence_audit");
  const scientificVerdict = verdicts
    .map(summaryRecord)
    .find((item) => item.gate === "scientific_rigor" || item.gate === "scientific_gate");
  const evidenceState = typeof evidenceVerdict?.verdict === "string" ? evidenceVerdict.verdict : approvalState;
  const scientificState = typeof scientificVerdict?.verdict === "string" ? scientificVerdict.verdict : approvalState;
  const mechanismQuestions = researchReviewUncertainties(specialistCards, "mechanistic_analyst");
  const evidenceQuestions = researchReviewUncertainties(specialistCards, "reference_evidence_curator");
  const debateSynthesis = buildResearchDebateSynthesis(specialistCards, finalSynthesis, locale);

  return {
    title: localizedText("Research partner readout", "科研伙伴评审", locale),
    summary: parentRunId
      ? localizedText(
          `I continued this as a research partner review from prior thread ${parentRunId} and kept the answer at ${approvalState}. ${unifiedAnswer}`,
          `我沿用上一轮 ${parentRunId} 的专家上下文继续评审，结论仍保持 ${approvalState}。${unifiedAnswer}`,
          locale,
        )
      : localizedText(
          `I treated this like a research partner review, not an approval workflow. ${unifiedAnswer}`,
          `我把这当成科研伙伴评审，不当成批准流程。${unifiedAnswer}`,
          locale,
        ),
    metrics: [
      { label: localizedText("Decision posture", "决策状态", locale), value: approvalState, hint: localizedText("Human review remains required", "仍需人工评审", locale) },
      { label: localizedText("Research team", "专家团队", locale), value: localizedText(`${teamPlan.length} specialists`, `${teamPlan.length} 位专家`, locale), hint: localizedText("Fixed collaborative topology", "固定协作拓扑", locale) },
      { label: localizedText("Audit trail", "审计链路", locale), value: reviewPacketId ? localizedText("Captured", "已捕获", locale) : localizedText("Pending", "待生成", locale), hint: reviewPacketId ?? evidencePackId ?? localizedText("No packet yet", "暂无审查包", locale) },
      { label: localizedText("Blocked actions", "拦截动作", locale), value: String(blockedActions.length), hint: localizedText("Final/external/hardware paths stay guarded", "最终、外部、硬件路径保持安全门", locale) },
      ...(parentRunId ? [{ label: localizedText("Continuity", "连续上下文", locale), value: localizedText("Recalled", "已继承", locale), hint: parentRunId }] : []),
    ],
    sections: [
      ...(teamPlan.length
        ? [
            {
              title: localizedText("Expert team activated", "专家组已启动", locale),
              items: teamPlan.map((item) => {
                const step = summaryRecord(item);
                const stage = typeof step.stage === "number" ? `S${step.stage}` : "S?";
                const title = specialistLabel(step.title, locale);
                const objective = typeof step.objective === "string" ? step.objective : localizedText("Review objective pending", "评审目标待补齐", locale);
                return locale === "zh-CN" ? `${stage} ${title}：${objective}` : `${stage} ${title}: ${objective}`;
              }),
            },
          ]
        : []),
      {
        title: localizedText("Reasoning in progress", "推演进度", locale),
        items: reasoningStages.length
          ? reasoningStages
          : [
              localizedText(
                "Question reframed, specialists routed, debate converged, and the gate remains review_required.",
                "问题已重构、专家已分工、交锋已收敛，安全门仍保持 review_required。",
                locale,
              ),
            ],
      },
      {
        title: localizedText("My read on the proposal", "综合判断", locale),
        items: [
          unifiedAnswer,
          localizedText(
            `Scientific posture: ${scientificState}. Evidence posture: ${evidenceState}.`,
            `科学门状态：${scientificState}。证据门状态：${evidenceState}。`,
            locale,
          ),
          localizedText(
            "I would keep the proposal in review_required until the hypothesis, controls, source quality, and failure modes are explicitly checked by a human reviewer.",
            "在假设、对照、来源质量和失效模式被人工明确检查前，我会保持 review_required。",
            locale,
          ),
        ],
      },
      {
        title: localizedText("Expert debate synthesis", "专家交锋纪要", locale),
        items: debateSynthesis,
      },
      {
        title: localizedText("Evidence status", "证据状态", locale),
        items: evidenceStatuses.length
          ? evidenceStatuses
          : [
              localizedText(
                `Candidate evidence and source packets remain ${approvalState}.`,
                `候选证据和来源包仍保持 ${approvalState}。`,
                locale,
              ),
            ],
      },
      {
        title: localizedText("What I would challenge first", "优先追问", locale),
        items: [
          researchReviewDeliverable(
            specialistCards,
            "mechanistic_analyst",
            localizedText(
              "Mechanism is the first pressure point: name counterexamples, failure modes, and boundary conditions before interpreting any positive result.",
              "机制是第一压力点：先列反例、失效模式和边界条件，再解释正向结果。",
              locale,
            ),
          ),
          researchReviewDeliverable(
            specialistCards,
            "scientific_reviewer",
            localizedText(
              "Scientific rigor is the second pressure point: make falsifiability, controls, and alternative explanations explicit.",
              "科学严谨性是第二压力点：明确可证伪性、对照和替代解释。",
              locale,
            ),
          ),
          ...(mechanismQuestions.length
            ? mechanismQuestions.slice(0, 2).map((item) => localizedText(`Mechanism uncertainty: ${item}`, `机制不确定性：${item}`, locale))
            : []),
          ...(evidenceQuestions.length
            ? evidenceQuestions.slice(0, 2).map((item) => localizedText(`Evidence uncertainty: ${item}`, `证据不确定性：${item}`, locale))
            : []),
        ],
      },
      {
        title: localizedText("Controlled pilot plan", "受控小试计划", locale),
        items: experimentPlan.length
          ? experimentPlan
          : [
              localizedText(
                "Start with a desk evidence review, then a small controlled pilot, then a counterfactual lane if containment and evidence gates stay reviewable.",
                "先做桌面证据审查，再做小规模受控小试；只有在隔离和证据门可审查时才保留反事实路线。",
                locale,
              ),
            ],
      },
      {
        title: localizedText("Next research moves", "下一步研究动作", locale),
        items: recommendedNextSteps.length
          ? recommendedNextSteps
          : [
              localizedText("Turn the objective into a falsifiable hypothesis with explicit controls.", "把目标改写成可证伪假设，并补齐明确对照。", locale),
              localizedText(
                "Map source evidence and mark gaps before treating external material as decision-grade.",
                "先绘制来源证据图谱并标出缺口，再考虑外部资料是否能进入决策级证据。",
                locale,
              ),
              localizedText("Run digital twin sensitivity checks as review evidence, not as approval.", "数字孪生敏感性检查只作为评审证据，不作为批准。", locale),
            ],
      },
      ...(teamPlan.length
        ? [
            {
              title: localizedText("Trace: team plan", "Trace：专家计划", locale),
              items: teamPlan.map(formatResearchReviewStep),
            },
          ]
        : []),
      ...(verdicts.length
        ? [
            {
              title: localizedText("Trace: gate verdicts", "Trace：安全门裁决", locale),
              items: verdicts.map((item) => {
                const verdict = summaryRecord(item);
                const gate = typeof verdict.gate === "string" ? verdict.gate : "review_gate";
                const state = typeof verdict.verdict === "string" ? verdict.verdict : "review_required";
                return `${gate}: ${state}`;
              }),
            },
          ]
        : []),
      ...(specialistCards.length
        ? [
            {
              title: localizedText("Trace: specialist cards", "Trace：专家卡片", locale),
              items: specialistCards.map(formatResearchReviewCard),
            },
          ]
        : []),
      ...(actionLedger.length
        ? [
            {
              title: localizedText("Trace: action ledger", "Trace：动作账本", locale),
              items: actionLedger.map(formatResearchReviewAction),
            },
          ]
        : []),
    ],
    notes: [
      localizedText(
        "Trace and evidence are captured in the background; the foreground answer stays focused on research judgment.",
        "Trace 和证据已经后台捕获；前台回答聚焦科研判断。",
        locale,
      ),
      localizedText(
        `All external sources, candidate data, and experiment suggestions remain ${approvalState}.`,
        `所有外部来源、候选数据和实验建议仍保持 ${approvalState}。`,
        locale,
      ),
      localizedText(
        `${confirmationActions.length} actions require confirmation before any external workflow; ${blockedActions.length} actions are blocked.`,
        `${confirmationActions.length} 个动作在外部流程前需要确认；${blockedActions.length} 个动作已被拦截。`,
        locale,
      ),
      ...(parentRunId ? [localizedText(`Continuation parent: ${parentRunId}`, `连续评审父运行：${parentRunId}`, locale)] : []),
    ],
    actions: [
      { label: localizedText("Open orchestrator trace", "打开 Orchestrator trace", locale), to: "/bos/orchestrator" },
    ],
  };
}

function buildCatalogTableResult(args: {
  title: string;
  summary: string;
  columns: string[];
  rows: string[][];
  action: { label: string; to: string };
  note?: string;
}): AssistantStructuredResult {
  return {
    title: args.title,
    summary: args.summary,
    table: {
      columns: args.columns,
      rows: args.rows,
    },
    notes: args.note ? [args.note] : undefined,
    actions: [args.action],
  };
}

function extractRequestedEntityId(message: string) {
  const match = message.match(/\b(\d{1,6})\b/);
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isInteger(value) && value > 0 ? value : null;
}

function extractRequestedEntityIds(message: string) {
  const matches = message.match(/\b(\d{1,6})\b/g) ?? [];
  return Array.from(
    new Set(
      matches
        .map((item) => Number(item))
        .filter((value) => Number.isInteger(value) && value > 0),
    ),
  );
}

function buildDefaultSupervisorObservation(): SupervisorObservationRequest {
  return {
    uv254: 2.4,
    od280: 2.0,
    do: 5.1,
    ph: 7.1,
    elapsed_hours: 8,
    previous_c_signal_hat: 0.58,
    previous_elapsed_hours: 7,
    previous_dc_dt_hat: 0.03,
    previous_negative_slope_streak: 0,
    confidence_threshold: 0.8,
    negative_slope_persistence: 3,
    observability_required: true,
  };
}

export function buildBatchAnalysisResult(args: {
  batch: Batch;
  guidance: { gap_items: Array<{ severity: string; title: string; message: string }>; recommended_actions: string[] };
  signal: SignalBatch | null;
  audit: AuditPacket | null;
  risk?: TimeseriesRiskResponse | null;
}): AssistantStructuredResult {
  const readModel = args.audit ? getAuditPacketReadModel(args.audit) : null;
  const visionObservation = resolveAssistantVisionObservation(args.signal, readModel);
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
      ...(args.risk
        ? [
            {
              label: "Future risk",
              value: formatPercent(args.risk.future_risk_score),
              hint: `${args.risk.model_name} · ${args.risk.execution_mode}`,
            },
          ]
        : []),
    ],
    notes: [
      ...(args.risk
        ? [
            `Chronos risk: future ${formatPercent(args.risk.future_risk_score)}, freshness drift ${formatPercent(args.risk.freshness_drift_score)}, release warning ${formatPercent(args.risk.release_warning_score)}.`,
            args.risk.explanation,
          ]
        : ["Model-backed risk metrics are not available for this batch yet."]),
      ...(args.guidance.gap_items.length
        ? args.guidance.gap_items.slice(0, 4).map((item) => `[${item.severity}] ${item.title}: ${item.message}`)
        : ["No BOS guidance gaps are currently flagged for this batch."]),
      ...(args.guidance.recommended_actions.length
        ? args.guidance.recommended_actions.slice(0, 4).map((item) => `Recommended: ${item}`)
        : []),
      ...(visionObservation
        ? [
            `Vision observation: ${visionObservation.observation_summary}`,
            `Vision fields: dominant ${visionObservation.dominant_label ?? "none"}, classes ${visionObservation.detected_classes.join(", ") || "none"}, anomaly ${visionObservation.anomaly_flag ? "yes" : "no"}`,
          ]
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
    const signal =
      args.signals
        .filter((item) => item.batch_id === batch.id)
        .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null;
    const audit =
      args.audits.find((item) => item.batch_id === batch.id && (!signal || item.packet?.signal_batch?.id === signal.id)) ??
      args.audits.find((item) => item.batch_id === batch.id) ??
      null;
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

function buildExecutiveSummaryResult(args: {
  summary: DashboardSummary;
  decisions: ReleaseDecision[];
  audits: AuditPacket[];
  runtime: BrainRuntimeResponse;
  riskItems?: TimeseriesRiskResponse[];
}): AssistantStructuredResult {
  const releaseCounts = summarizeReleaseDecisions(args.decisions);
  const latestAudit = args.audits[0] ? getAuditPacketReadModel(args.audits[0]) : null;
  const topRisk = args.riskItems
    ?.slice()
    .sort((left, right) => right.release_warning_score - left.release_warning_score)[0];
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
      ...(topRisk
        ? [
            {
              label: "Chronos risk",
              value: formatPercent(topRisk.release_warning_score),
              hint: `${topRisk.batch_label} release warning`,
            },
          ]
        : []),
    ],
    notes: [
      `Release decisions: PASS ${releaseCounts.PASS ?? 0}, PASS_WITH_RETUNING ${releaseCounts.PASS_WITH_RETUNING ?? 0}, FAIL ${releaseCounts.FAIL ?? 0}`,
      latestAudit
        ? `Latest release rationale: ${latestAudit.rationale}`
        : "No audit packet rationale is available yet.",
      topRisk
        ? `Highest model-backed release warning: ${topRisk.batch_label} at ${formatPercent(topRisk.release_warning_score)} (${topRisk.execution_mode}).`
        : "Model-backed risk metrics are not available yet.",
      `Brain runtime last updated: ${formatDateTime(args.runtime.last_updated_at)}`,
    ],
    actions: [
      { label: "Open dashboard", to: "/dashboard" },
      { label: "Open release center", to: "/release" },
      { label: "Open brain dashboard", to: "/bos/brain" },
    ],
  };
}

function buildReleaseRiskResult(
  decisions: ReleaseDecision[],
  audits: AuditPacket[],
  riskItems: TimeseriesRiskResponse[] = [],
): AssistantStructuredResult {
  const riskRows = audits
    .slice(0, 8)
    .map((item) => getAuditPacketReadModel(item))
    .flatMap((item) => [
      ...item.blockingFactors.map((factor) => [item.batchLabel, "Blocking", factor, item.releaseDecision]),
      ...item.warningFactors.map((factor) => [item.batchLabel, "Warning", factor, item.releaseDecision]),
    ]);

  const releaseCounts = summarizeReleaseDecisions(decisions);
  const topRisk = riskItems
    .slice()
    .sort((left, right) => right.release_warning_score - left.release_warning_score)[0];

  return {
    title: "Release risks",
    summary:
      "Blocking and warning factors extracted from current audit packets and release decisions, ranked in the order they appear in packet evidence.",
    metrics: [
      { label: "Release decisions", value: String(decisions.length), hint: "Persisted decisions in scope" },
      { label: "PASS", value: String(releaseCounts.PASS ?? 0), hint: "Ready candidates" },
      { label: "Retune", value: String(releaseCounts.PASS_WITH_RETUNING ?? 0), hint: "Candidates needing changes" },
      { label: "Fail", value: String(releaseCounts.FAIL ?? 0), hint: "Blocked candidates" },
      ...(topRisk
        ? [
            {
              label: "Model warning",
              value: formatPercent(topRisk.release_warning_score),
              hint: `${topRisk.batch_label} · ${topRisk.execution_mode}`,
            },
          ]
        : []),
    ],
    table: {
      columns: ["Batch", "Severity", "Factor", "Decision"],
      rows: riskRows.length ? riskRows : [["N/A", "Info", "No blocking or warning factors are currently present.", "N/A"]],
    },
    notes: topRisk
      ? [
          `Top model-backed risk: ${topRisk.batch_label} has release warning ${formatPercent(topRisk.release_warning_score)} and future risk ${formatPercent(topRisk.future_risk_score)}.`,
          topRisk.explanation,
        ]
      : ["Model-backed Chronos risk metrics are not available yet."],
    actions: [{ label: "Open release center", to: "/release" }],
  };
}

function buildBatchGuidanceResult(args: {
  batch: Batch;
  guidance: { gap_items: Array<{ severity: string; title: string; message: string }>; recommended_actions: string[] };
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

export function computeBatchRiskScore(args: {
  batch: Batch;
  signal: SignalBatch | null;
  audit: AuditPacket | null;
  guidance?: { gap_items: Array<{ severity: string }> } | null;
}) {
  let score = 0;
  const reasons: string[] = [];
  const readModel = args.audit ? getAuditPacketReadModel(args.audit) : null;
  const visionObservation = resolveAssistantVisionObservation(args.signal, readModel);

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

  if (visionObservation?.anomaly_flag) {
    score += 2;
    reasons.push("Vision observation flagged an anomaly for operator review");
  }
  if (
    typeof visionObservation?.confidence_mean === "number" &&
    visionObservation.confidence_mean < 0.45
  ) {
    score += 1;
    reasons.push("Vision observation confidence is below the preferred review band");
  }

  return {
    score,
    reasons,
    readModel,
  };
}

function resolveAssistantVisionObservation(
  signal: SignalBatch | null,
  readModel: ReturnType<typeof getAuditPacketReadModel> | null,
): (VisionObservation & Record<string, unknown>) | null {
  return readModel?.visionObservation ?? signal?.qc_markers?.vision_observation ?? null;
}

function buildRiskiestBatchResult(args: {
  batch: Batch;
  signal: SignalBatch | null;
  audit: AuditPacket | null;
  guidance: { gap_items: Array<{ severity: string; title: string; message: string }>; recommended_actions: string[] };
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
      ...(args.reasons.length ? args.reasons.slice(0, 5).map((item) => `Why it ranked high: ${item}`) : ["No strong risk factor was detected; this is simply the highest among the current set."]),
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

function buildNativeRuntimeResult(runtime: NativeModelRuntimeStatus): AssistantStructuredResult {
  return {
    title: "Native model runtime",
    summary: "Local BOS model runtime readiness, artifact status, and adapter posture.",
    metrics: [
      { label: "Enabled", value: runtime.enabled ? "Yes" : "No", hint: runtime.version },
      { label: "Cache dir", value: runtime.cache_dir, hint: "Runtime artifact location" },
      { label: "Runtimes", value: String(runtime.runtimes.length), hint: "Configured model adapters" },
    ],
    table: {
      columns: ["Key", "Ready", "State", "Adapter", "Modality", "Next step"],
      rows: runtime.runtimes.slice(0, 12).map((item) => [
        item.key,
        item.ready ? "Yes" : "No",
        item.runtime_state,
        item.adapter_status,
        item.modality,
        item.next_steps[0] || "N/A",
      ]),
    },
    actions: [{ label: "Open signal lab", to: "/bos/signal-lab" }],
  };
}

function buildManuscriptCatalogResult(catalog: ManuscriptCampaignCatalogResponse): AssistantStructuredResult {
  return buildCatalogTableResult({
    title: "Reference campaigns",
    summary: "Campaign and manuscript reference set available inside the BOS atlas.",
    columns: ["Key", "Title", "Evidence", "Campaign type", "Feedstocks"],
    rows: catalog.campaigns.slice(0, 12).map((item) => [
      item.key,
      item.title,
      item.evidence_level,
      item.campaign_type,
      item.feedstocks.slice(0, 3).join(", ") || "N/A",
    ]),
    action: { label: "Open references", to: "/bos/references" },
    note: `Showing ${Math.min(catalog.campaigns.length, 12)} of ${catalog.count} campaigns.`,
  });
}

function renderStructuredChart(chart: AssistantStructuredResult["chart"]) {
  if (!chart) return null;
  switch (chart.kind) {
    case "ser-trend":
      return <SERTrendChart data={chart.data} height={280} />;
    case "grade-distribution":
      return <GradeBarChart data={chart.data} height={260} />;
    case "species-distribution":
      return <SpeciesPieChart data={chart.data} height={260} />;
    case "twin-trajectory":
      return <TwinTrajectoryChart data={chart.data} height={280} />;
    default:
      return null;
  }
}

function StructuredAssistantResultCard({
  result,
  onNavigate,
}: {
  result: AssistantStructuredResult;
  onNavigate: (to: string) => void;
}) {
  const isResearchPartnerResult = result.title === "Research partner readout" || result.title === "科研伙伴评审";
  return (
    <div
      className={`space-y-4 rounded-[24px] border p-4 ${
        isResearchPartnerResult
          ? "border-brand-300/18 bg-[linear-gradient(135deg,rgba(255,255,255,0.075),rgba(255,255,255,0.025))]"
          : "border-white/8 bg-white/5"
      }`}
    >
      <div>
        <p className={isResearchPartnerResult ? "text-base font-semibold text-white" : "text-sm font-semibold text-white"}>
          {translateText(result.title)}
        </p>
        {result.summary ? (
          <p className={isResearchPartnerResult ? "mt-2 text-[0.97rem] leading-8 text-surface-100" : "mt-2 text-sm leading-7 text-surface-300"}>
            {translateText(result.summary)}
          </p>
        ) : null}
      </div>

      {result.metrics?.length ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {result.metrics.map((metric) => (
            <div key={`${metric.label}-${metric.value}`} className="rounded-[20px] border border-white/8 bg-black/15 p-3">
              <p className="text-[11px] uppercase tracking-[0.24em] text-surface-500">{translateText(metric.label)}</p>
              <p className="mt-2 text-lg font-semibold text-white">{translateText(metric.value)}</p>
              {metric.hint ? (
                <p className="mt-1 text-xs leading-6 text-surface-400">{translateText(metric.hint)}</p>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {result.table ? (
        <div className="space-y-2">
          {result.table.title ? (
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-surface-500">
              {translateText(result.table.title)}
            </p>
          ) : null}
          <Table>
            <TableHead>
              <TableRow>
                {result.table.columns.map((column) => (
                  <TableHeaderCell key={column}>{translateText(column)}</TableHeaderCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {result.table.rows.map((row, rowIndex) => (
                <TableRow key={`${result.title}-row-${rowIndex}`}>
                  {row.map((cell, cellIndex) => (
                    <TableCell key={`${result.title}-${rowIndex}-${cellIndex}`}>{translateText(cell)}</TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}

      {result.chart ? (
        <div className="rounded-[20px] border border-white/8 bg-black/10 px-2 py-3">
          {result.chart.title ? (
            <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-[0.24em] text-surface-500">
              {translateText(result.chart.title)}
            </p>
          ) : null}
          {renderStructuredChart(result.chart)}
        </div>
      ) : null}

      {result.sections?.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {result.sections.map((section) => {
            const sectionKey = `${result.title}-${section.title}`;
            const sectionBody = (
              <div className="mt-2 space-y-2">
                {section.items.map((item) => (
                  <p key={`${section.title}-${item}`} className="text-sm leading-6 text-surface-300">
                    {translateText(item)}
                  </p>
                ))}
              </div>
            );
            const isTraceSection = section.title === "Specialist cards" || section.title.startsWith("Trace:") || section.title.startsWith("Trace：");
            const isDebateSection = section.title === "Expert debate synthesis" || section.title === "专家交锋纪要";
            const isResearchPartnerSection =
              isDebateSection ||
              section.title === "Reasoning in progress" ||
              section.title === "推演进度" ||
              section.title === "Evidence status" ||
              section.title === "证据状态" ||
              section.title === "Controlled pilot plan" ||
              section.title === "受控小试计划";
            if (isResearchPartnerSection) {
              return (
                <div key={sectionKey} className="md:col-span-2 rounded-[20px] border border-brand-300/18 bg-brand-400/8 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-brand-100">
                    {translateText(section.title)}
                  </p>
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    {section.items.map((item) => (
                      <p key={`${section.title}-${item}`} className="rounded-[16px] border border-white/8 bg-black/15 px-3 py-2 text-sm leading-7 text-surface-100">
                        {translateText(item)}
                      </p>
                    ))}
                  </div>
                </div>
              );
            }
            if (isTraceSection) {
              return (
                <details key={sectionKey} className="rounded-[18px] border border-white/8 bg-black/10 p-3">
                  <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.24em] text-surface-500">
                    {translateText(section.title)}
                  </summary>
                  {sectionBody}
                </details>
              );
            }
            return (
              <div key={sectionKey} className="rounded-[18px] border border-white/8 bg-black/10 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-surface-500">
                  {translateText(section.title)}
                </p>
                {sectionBody}
              </div>
            );
          })}
        </div>
      ) : null}

      {result.notes?.length ? (
        <div className="space-y-2">
          {result.notes.map((item) => (
            <div key={item} className="rounded-[18px] border border-white/8 bg-black/10 px-3 py-2 text-sm leading-7 text-surface-300">
              {translateText(item)}
            </div>
          ))}
        </div>
      ) : null}

      {result.actions?.length ? (
        <div className="flex flex-wrap gap-2">
          {result.actions.map((action) => (
            <Button
              key={`${result.title}-${action.to}`}
              size="sm"
              variant="secondary"
              leftIcon={<ArrowRight className="h-4 w-4" />}
              onClick={() => onNavigate(action.to)}
            >
              {translateText(action.label)}
            </Button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function inferMediaIntent(message: string): { enabled: boolean; kind: RemotionRenderKind } {
  const normalized = message.toLowerCase();
  const mediaKeywords = [
    "生成图",
    "做图",
    "海报",
    "封面",
    "图片",
    "图像",
    "动画",
    "视频",
    "poster",
    "cover",
    "image",
    "graphic",
    "animation",
    "video",
    "render",
  ];
  const enabled = mediaKeywords.some((keyword) => normalized.includes(keyword));
  // Assistant media mode is intentionally locked to the safest still pipeline for now.
  const kind = "still";
  return { enabled, kind };
}

function getErrorDetail(error: unknown, fallback: string): string {
  const axiosError = error as AxiosError<{ detail?: string | { message?: string; details?: string } }>;
  const detail = axiosError?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object") {
    if (typeof detail.message === "string" && detail.message.trim()) return detail.message;
    if (typeof detail.details === "string" && detail.details.trim()) return detail.details;
  }
  return fallback;
}

function buildAssistantPresetPayload(args: {
  prompt: string;
  renderKind: RemotionRenderKind;
  templateId: string;
  title: string;
  subtitle: string;
  caption: string;
  accentColor: string;
  backgroundColor: string;
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
  extraProps: Record<string, unknown>;
  fileName: string;
}): RemotionPresetCreateRequest {
  const tags = Array.from(
    new Set(
      [
        "assistant",
        args.renderKind,
        args.templateId.replace(/^bos-/, ""),
        /launch|release|发布/.test(args.prompt.toLowerCase()) ? "launch" : null,
        /ops|signal|运营|信号/.test(args.prompt.toLowerCase()) ? "ops" : null,
        /board|executive|汇报|高层/.test(args.prompt.toLowerCase()) ? "board" : null,
        /story|social|社区|社交/.test(args.prompt.toLowerCase()) ? "social" : null,
      ].filter(Boolean) as string[],
    ),
  ).slice(0, 8);

  return {
    name: args.title,
    tags,
    snapshot_file_name: args.fileName,
    snapshot_kind: args.renderKind,
    template_id: args.templateId,
    kind: args.renderKind,
    export_recipe_id:
      args.width === 1080 && args.height === 1920
        ? "douyin-vertical"
        : args.width === 1920 && args.height === 1080
          ? "deck-header"
          : args.width === 1080 && args.height === 1440
            ? "wechat-poster"
            : "web-hero",
    creative_brief: args.prompt,
    audience: "general",
    brand_voice: "balanced",
    title: args.title,
    subtitle: args.subtitle,
    caption: args.caption,
    accent_color: args.accentColor,
    background_color: args.backgroundColor,
    width: String(args.width),
    height: String(args.height),
    fps: String(args.fps),
    duration_in_frames: String(args.durationInFrames),
    dynamic_fields: Object.fromEntries(
      Object.entries(args.extraProps).map(([key, value]) => [key, String(value ?? "")]),
    ),
  };
}

function containsChinese(text: string) {
  return /[\u4e00-\u9fff]/.test(text);
}

export function normalizePromptSubject(message: string) {
  const compact = message.replace(/\s+/g, " ").trim();
  const markers = ["\u4e3b\u9898\u662f", "\u4e3b\u9898\uff1a", "\u4e3b\u9898:", "about ", "for "];
  for (const marker of markers) {
    const index = compact.toLowerCase().indexOf(marker.toLowerCase());
    if (index >= 0) {
      return compact.slice(index + marker.length).trim();
    }
  }
  return compact;
}

export function clampText(text: string, maxLength: number) {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength - 1))}\u2026`;
}

export function splitChineseHeadline(subject: string) {
  const compact = subject.replace(/[\uFF0C\u3002\u3001"'`\u201C\u201D\u2018\u2019\uFF1A:;\uFF1B!\uFF01?\uFF1F]/g, "").trim();
  if (compact.length <= 8) return compact;
  if (compact.length <= 12) return `${compact.slice(0, 6)}\n${compact.slice(6)}`;
  return `${compact.slice(0, 6)}\n${compact.slice(6, 12)}`;
}

export function buildSafeStillCopy(message: string) {
  const subject = normalizePromptSubject(message);
  const chinese = containsChinese(subject);

  if (chinese) {
    let title = splitChineseHeadline(subject);
    let subtitle = "BOS \u5185\u7f6e Media Studio\uff0c\u5148\u4e3a\u8fd9\u4e2a\u8bf7\u6c42\u751f\u6210\u4e00\u5f20\u7a33\u5b9a\u53ef\u9760\u7684\u5b89\u5168\u9759\u6001\u56fe\u3002";
    let metricLabel = "\u6a21\u5f0f";
    let metricValue = "\u7a33\u5b9a";
    const eyebrow = "BOS MEDIA";
    let caption = "\u5b89\u5168\u751f\u6210";

    if (/remotion/i.test(subject)) {
      title = "BOS \u5185\u7f6e\nRemotion";
      subtitle = "\u73b0\u5728\u5df2\u7ecf\u652f\u6301\u5728 BOS \u5185\u76f4\u63a5\u751f\u6210\u56fe\u7247\u4e0e\u52a8\u753b\u3002";
      metricLabel = "\u80fd\u529b";
      metricValue = "\u56fe\u50cf \u00b7 \u52a8\u753b";
      caption = "\u5a92\u4f53\u80fd\u529b\u4e0a\u7ebf";
    } else if (/\u53d1\u5e03|\u6d77\u62a5|\u5c01\u9762/.test(subject)) {
      subtitle = "\u8fd9\u662f\u4e00\u5f20\u504f\u53d1\u5e03\u5411\u7684\u5b89\u5168\u9759\u6001\u56fe\uff0c\u9002\u5408\u5148\u62ff\u5230\u4e00\u7248\u53ef\u7528\u7ed3\u679c\u3002";
      metricLabel = "\u7528\u9014";
      metricValue = "\u53d1\u5e03";
      caption = "\u53d1\u5e03\u6d77\u62a5";
    } else if (/\u8fd0\u8425|\u4fe1\u53f7/.test(subject)) {
      subtitle = "\u8fd9\u662f\u4e00\u5f20\u504f\u8fd0\u8425\u4fe1\u53f7\u7684\u5b89\u5168\u9759\u6001\u56fe\uff0c\u53ef\u4ee5\u76f4\u63a5\u4e0b\u8f7d\u548c\u590d\u7528\u3002";
      metricLabel = "\u7528\u9014";
      metricValue = "\u8fd0\u8425";
      caption = "\u8fd0\u8425\u4fe1\u53f7";
    }

    return {
      title: clampText(title, 18),
      subtitle: clampText(subtitle, 30),
      caption,
      eyebrow,
      metricLabel,
      metricValue,
    };
  }

  const compact = subject.replace(/\s+/g, " ").trim();
  return {
    title: clampText(compact || "BOS Media", 18),
    subtitle: clampText("BOS Assistant generated a stable still graphic for this request.", 42),
    caption: "SAFE STILL",
    eyebrow: "BOS MEDIA",
    metricLabel: "Mode",
    metricValue: "Stable",
  };
}

function buildEmergencyStillPayload(message: string) {
  const copy = buildSafeStillCopy(message);
  return {
    kind: "still" as const,
    template_id: "bos-assistant-safe-still",
    title: copy.title,
    subtitle: copy.subtitle,
    caption: copy.caption,
    accent_color: "#7CFFB2",
    background_color: "#07111F",
    width: 1080,
    height: 1080,
    fps: 30,
    duration_in_frames: 1,
    extra_props: {
      eyebrow: copy.eyebrow,
      supporting_line: `${copy.metricLabel}: ${copy.metricValue}`,
      pill_label: copy.metricValue,
    },
  };
}

function isToday(timestamp: string | null | undefined) {
  if (!timestamp) return false;
  const date = new Date(timestamp);
  const now = new Date();
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}

function turnMessages(
  turns: CodeTurn[],
  pendingPrompt: string | null,
  includePendingAssistant: boolean,
): AssistantMessage[] {
  const items: AssistantMessage[] = [];

  for (const turn of turns) {
    items.push({
      id: `user-${turn.id}`,
      role: "user",
      body: turn.user_message,
      createdAt: turn.created_at,
    });

    if (turn.assistant_summary?.trim()) {
      items.push({
        id: `assistant-${turn.id}`,
        role: "assistant",
        body: turn.assistant_summary,
        createdAt: turn.created_at,
      });
    }
  }

  if (pendingPrompt) {
    items.push({
      id: "pending-user",
      role: "user",
      body: pendingPrompt,
      createdAt: null,
      pending: true,
    });
    if (includePendingAssistant) {
      items.push({
        id: "pending-assistant",
        role: "assistant",
        body: "BOS is thinking through the next move.",
        createdAt: null,
        pending: true,
      });
    }
  }

  return items;
}

function ThinkingCard({
  stepIndex,
  streamState,
  promptLanguage,
}: {
  stepIndex: number;
  streamState: "idle" | "streaming" | "stopped" | "failed";
  promptLanguage: AppLocale;
}) {
  const step = THINKING_STEPS[stepIndex % THINKING_STEPS.length];
  const thinkingStatus =
    streamState === "streaming"
      ? localizedText("BOS is arriving in real time", "BOS 正在实时组织多专家思考", promptLanguage)
      : localizedText("BOS is thinking through the next move.", "BOS 正在推演下一步。", promptLanguage);

  return (
    <div className="assistant-thinking-card rounded-[24px] p-4 sm:p-5">
      <div className="assistant-thinking-shell flex flex-col gap-5 sm:flex-row sm:items-center">
        <div className="assistant-thinking-visual flex-shrink-0">
          <div className="assistant-thinking-orb-wrap assistant-thinking-grid">
            <span className="assistant-thinking-node assistant-thinking-node-primary" />
            <span className="assistant-thinking-node assistant-thinking-node-secondary" />
            <span className="assistant-thinking-node assistant-thinking-node-tertiary" />
            <span className="assistant-thinking-scanline" />
          </div>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="neutral" size="xs" className="assistant-thread-note-badge">
              {translateText(step.eyebrow)}
            </Badge>
            <span className="assistant-thinking-live inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.24em] text-brand-100/78">
              <span className="assistant-stream-cursor" />
              {translateText(thinkingStatus, promptLanguage)}
            </span>
          </div>

          <p className="mt-3 text-lg font-semibold tracking-tight text-white">
            {translateText(step.title, promptLanguage)}
          </p>
          <p className="mt-2 max-w-2xl text-sm leading-7 text-surface-300">
            {translateText(step.detail, promptLanguage)}
          </p>

          <div className="mt-4 flex flex-wrap gap-2.5">
            {THINKING_STEPS.map((item, index) => (
              <div
                key={item.title}
                className={[
                  "assistant-thinking-chip rounded-full border px-3 py-1.5 text-[11px] uppercase tracking-[0.2em]",
                  index === stepIndex % THINKING_STEPS.length
                    ? "assistant-thinking-chip-active"
                    : "",
                ].join(" ")}
              >
                {translateText(item.eyebrow, promptLanguage)}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function BOSAssistantPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const accessToken = useAuthStore((state) => state.accessToken);
  const canUseAssistant = hasMinimumRole(user?.role ?? "viewer", "operator");

  const sessions = useCodeSessions(canUseAssistant);
  const createSession = useCreateCodeSession();
  const runtime = useCodeRuntime(canUseAssistant);
  const orchestration = useCodeOrchestration(canUseAssistant);
  const executeNextAutomationAction = useExecuteNextAutomationAction();

  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [threadQuery, setThreadQuery] = useState("");
  const [prompt, setPrompt] = useState("");
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const [streamingAssistantText, setStreamingAssistantText] = useState("");
  const [localAssistantMessages, setLocalAssistantMessages] = useState<Record<number, AssistantMessage[]>>({});
  const [streamState, setStreamState] = useState<"idle" | "streaming" | "stopped" | "failed">("idle");
  const [streamStatusDetail, setStreamStatusDetail] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [drafts, setDrafts] = useLocalStorage<PersistedDrafts>("bos-assistant-drafts", {});
  const [persistedTitles, setPersistedTitles] = useLocalStorage<PersistedThreadTitles>("bos-assistant-thread-titles", {});
  const [researchReviewRunsBySession, setResearchReviewRunsBySession] = useLocalStorage<PersistedResearchReviewRuns>(
    "bos-assistant-research-review-runs",
    {},
  );
  const [assistantModelPreference, setAssistantModelPreference] = useLocalStorage<string>(
    "bos-assistant-team-model",
    DEFAULT_ASSISTANT_MODEL,
  );
  const [automationResultBySession, setAutomationResultBySession] = useState<Record<number, string>>({});
  const [thinkingStepIndex, setThinkingStepIndex] = useState(0);
  const [shouldAutoFollowThread, setShouldAutoFollowThread] = useState(true);
  const autoCreatedRef = useRef(false);
  const threadEndRef = useRef<HTMLDivElement | null>(null);
  const threadScrollRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const draftPersistTimerRef = useRef<number | null>(null);
  const restoredDraftSessionRef = useRef<number | null>(null);
  const [layoutPrefs, setLayoutPrefs] = useLocalStorage<AssistantLayoutPrefs>(
    "bos-assistant-layout-v1",
    DEFAULT_LAYOUT_PREFS,
  );
  const localAssistantMessagesRef = useRef<Record<number, AssistantMessage[]>>({});

  const sessionId = selectedSessionId ?? sessions.data?.active_session_id ?? sessions.data?.items[0]?.id ?? null;
  const sessionIdSearchParam = searchParams.get("sessionId") ?? "";
  const sessionDetail = useCodeSession(canUseAssistant ? sessionId : null);
  const sessionEvents = useCodeSessionEvents(canUseAssistant ? sessionId : null);
  const updateSession = useUpdateCodeSession(canUseAssistant ? sessionId : null);

  const sessionsStatus = (sessions.error as AxiosError | null)?.response?.status ?? null;
  const providerIssue = useMemo(
    () => getLatestProviderIssue(sessionDetail.data, sessionEvents.data?.items ?? []),
    [sessionDetail.data, sessionEvents.data?.items],
  );
  const assistantRecoveryResultSummary = sessionId ? automationResultBySession[sessionId] ?? null : null;
  const automationTargetSessionId = sessions.data?.items[0]?.id ?? null;
  const assistantAutomationAction = scopedAutomationAction(
    orchestration.data?.automation_ready,
    orchestration.data?.next_automation_action ?? null,
    sessionId,
    automationTargetSessionId,
  );
  const currentSession = sessionDetail.data?.session ?? null;
  const currentSessionId = currentSession?.id ?? null;
  const currentSessionTitle = currentSession?.title?.trim() ?? "";
  const persistedTitleForSession = sessionId ? persistedTitles[sessionId] ?? "" : "";
  const persistedTitleForCurrentSession = currentSessionId ? persistedTitles[currentSessionId] ?? "" : "";
  const firstTurnUserMessage = sessionDetail.data?.turns?.[0]?.user_message?.trim() ?? "";
  const assistantModelOptions = useMemo(
    () => buildAssistantModelOptions(runtime.data?.team_models ?? []),
    [runtime.data?.team_models],
  );
  const selectedAssistantModel = useMemo(() => {
    if (isAllowedAssistantModel(currentSession?.model) && assistantModelOptions.some((option) => option.value === currentSession.model)) {
      return currentSession.model;
    }
    if (isAllowedAssistantModel(assistantModelPreference) && assistantModelOptions.some((option) => option.value === assistantModelPreference)) {
      return assistantModelPreference;
    }
    return assistantModelOptions[0]?.value ?? DEFAULT_ASSISTANT_MODEL;
  }, [assistantModelOptions, assistantModelPreference, currentSession?.model]);

  useEffect(() => {
    if (!executeNextAutomationAction.data?.session_id || !executeNextAutomationAction.data?.summary) return;
    setAutomationResultBySession((current) => ({
      ...current,
      [executeNextAutomationAction.data!.session_id as number]: executeNextAutomationAction.data!.summary,
    }));
  }, [executeNextAutomationAction.data]);

  useEffect(() => {
    if (!canUseAssistant) return;
    const requestedSessionId = Number(sessionIdSearchParam);
    if (Number.isInteger(requestedSessionId) && requestedSessionId > 0) {
      const exists = sessions.data?.items?.some((session) => session.id === requestedSessionId);
      if (exists && selectedSessionId !== requestedSessionId) {
        setSelectedSessionId(requestedSessionId);
        return;
      }
    }
    if (selectedSessionId !== null) return;
    if (sessions.data?.active_session_id) {
      setSelectedSessionId(sessions.data.active_session_id);
      return;
    }
    if (sessions.data?.items?.length) {
      setSelectedSessionId(sessions.data.items[0].id);
    }
  }, [canUseAssistant, selectedSessionId, sessionIdSearchParam, sessions.data]);

  useEffect(() => {
    if (!canUseAssistant || !sessionId) return;
    const current = sessionIdSearchParam;
    const next = String(sessionId);
    if (current === next) return;
    setSearchParams((currentParams) => {
      const updated = new URLSearchParams(currentParams);
      updated.set("sessionId", next);
      return updated;
    }, { replace: true });
  }, [canUseAssistant, sessionId, sessionIdSearchParam, setSearchParams]);

  useEffect(() => {
    const sessionModel = currentSession?.model?.trim();
    if (!isAllowedAssistantModel(sessionModel) || sessionModel === assistantModelPreference) return;
    setAssistantModelPreference(sessionModel);
  }, [assistantModelPreference, currentSession?.model, setAssistantModelPreference]);

  useEffect(() => {
    if (!canUseAssistant) return;
    if (!sessions.data) return;
    if (sessions.data.items.length > 0) return;
    if (createSession.isPending || autoCreatedRef.current) return;

    autoCreatedRef.current = true;
    void createSession
      .mutateAsync({
        acquire_write_lease: false,
        provider: ASSISTANT_TEAM_PROVIDER,
        model: selectedAssistantModel,
      })
      .then((session) => {
        setSelectedSessionId(session.id);
      })
      .catch(() => {
        autoCreatedRef.current = false;
      });
  }, [canUseAssistant, createSession, selectedAssistantModel, sessions.data]);

  const threadMessages = useMemo(
    () =>
      [
        ...turnMessages(
          sessionDetail.data?.turns ?? [],
          pendingPrompt,
          !streamingAssistantText.trim(),
        ),
        ...(sessionId ? localAssistantMessages[sessionId] ?? [] : []),
      ],
    [localAssistantMessages, pendingPrompt, sessionDetail.data?.turns, sessionId, streamingAssistantText],
  );
  const visibleThreadMessages = useMemo(() => {
    if (!streamingAssistantText.trim()) return threadMessages;
    return [
      ...threadMessages,
      {
        id: "streaming-assistant",
        role: "assistant" as const,
        body: streamingAssistantText,
        createdAt: null,
        pending: true,
        streaming: true,
      },
    ];
  }, [streamingAssistantText, threadMessages]);
  const filteredSessions = useMemo(() => {
    const items = sessions.data?.items ?? [];
    const normalizedQuery = threadQuery.trim().toLowerCase();
    if (!normalizedQuery) return items;

    return items.filter((session) => {
      const turns =
        session.id === sessionDetail.data?.session.id ? sessionDetail.data.turns : undefined;
      const label = sessionLabel(session, turns).toLowerCase();
      return (
        label.includes(normalizedQuery) ||
        session.session_status.toLowerCase().includes(normalizedQuery) ||
        String(session.id).includes(normalizedQuery)
      );
    });
  }, [sessionDetail.data?.session.id, sessionDetail.data?.turns, sessions.data?.items, threadQuery]);
  const threadMeta = useMemo(
    () => threadMetaCopy(sessions.data?.items.length ?? 0, filteredSessions.length, threadQuery),
    [filteredSessions.length, sessions.data?.items.length, threadQuery],
  );
  const threadGroups = useMemo(
    () => ({
      today: filteredSessions.filter((session) => isToday(session.updated_at)),
      earlier: filteredSessions.filter((session) => !isToday(session.updated_at)),
    }),
    [filteredSessions],
  );

  function scrollThreadToBottom(behavior: ScrollBehavior = "auto") {
    const node = threadScrollRef.current;
    if (!node) return;
    node.scrollTo({
      top: node.scrollHeight,
      behavior,
    });
  }

  useEffect(() => {
    if (!shouldAutoFollowThread) return;
    const raf = window.requestAnimationFrame(() => {
      scrollThreadToBottom("auto");
    });
    return () => window.cancelAnimationFrame(raf);
  }, [shouldAutoFollowThread, visibleThreadMessages, sessionId, streamState]);

  useEffect(() => {
    setShouldAutoFollowThread(true);
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    composerRef.current?.focus();
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || pendingPrompt) return;
    if (restoredDraftSessionRef.current === sessionId) return;
    restoredDraftSessionRef.current = sessionId;
    const savedDraft = drafts[sessionId] ?? "";
    setPrompt((current) => (current === savedDraft ? current : savedDraft));
    // Restore once per thread switch; live draft writes must not reset the cursor.
  }, [drafts, pendingPrompt, sessionId]);

  useEffect(() => {
    localAssistantMessagesRef.current = localAssistantMessages;
  }, [localAssistantMessages]);

  useEffect(() => {
    return () => {
      Object.values(localAssistantMessagesRef.current)
        .flat()
        .forEach((message) => {
          if (message.mediaResult?.previewUrl) {
            URL.revokeObjectURL(message.mediaResult.previewUrl);
          }
        });
    };
  }, []);

  useEffect(() => {
    const activeTitle = currentSessionTitle || persistedTitleForSession;
    setTitleDraft((current) => (current === activeTitle ? current : activeTitle));
    setEditingTitle((current) => (current ? false : current));
  }, [currentSessionTitle, persistedTitleForSession]);

  useEffect(() => {
    if (!currentSessionId || !firstTurnUserMessage || persistedTitleForCurrentSession) return;
    const nextTitle = deriveThreadTitle(firstTurnUserMessage);
    setPersistedTitles((current) => ({
      ...current,
      [currentSessionId]: nextTitle,
    }));
  }, [currentSessionId, firstTurnUserMessage, persistedTitleForCurrentSession, setPersistedTitles]);

  useEffect(() => {
    if (!streamingAssistantText.trim()) return;
    const latestTurn = sessionDetail.data?.turns?.[sessionDetail.data.turns.length - 1];
    if (!latestTurn?.assistant_summary?.trim()) return;
    if (latestTurn.assistant_summary.trim() === streamingAssistantText.trim()) {
      setStreamingAssistantText("");
      setStreamState("idle");
    }
  }, [sessionDetail.data?.turns, streamingAssistantText]);

  useEffect(() => {
    if (!pendingPrompt && streamState !== "streaming") {
      setThinkingStepIndex(0);
      return;
    }

    const timer = window.setInterval(() => {
      setThinkingStepIndex((current) => (current + 1) % THINKING_STEPS.length);
    }, 2200);

    return () => window.clearInterval(timer);
  }, [pendingPrompt, streamState]);

  useEffect(() => {
    if (!sessionId) return;
    if (draftPersistTimerRef.current !== null) {
      window.clearTimeout(draftPersistTimerRef.current);
    }
    draftPersistTimerRef.current = window.setTimeout(() => {
      draftPersistTimerRef.current = null;
      setDrafts((current) => {
        const existing = current[sessionId] ?? "";
        if (existing === prompt) return current;
        if (!prompt) {
          if (!(sessionId in current)) return current;
          const next = { ...current };
          delete next[sessionId];
          return next;
        }
        return {
          ...current,
          [sessionId]: prompt,
        };
      });
    }, 250);
    return () => {
      if (draftPersistTimerRef.current !== null) {
        window.clearTimeout(draftPersistTimerRef.current);
        draftPersistTimerRef.current = null;
      }
    };
  }, [prompt, sessionId, setDrafts]);

  async function handleNewChat() {
    const session = await createSession.mutateAsync({
      acquire_write_lease: false,
      provider: ASSISTANT_TEAM_PROVIDER,
      model: selectedAssistantModel,
    });
    setSelectedSessionId(session.id);
    setThreadQuery("");
    setPrompt("");
    setPendingPrompt(null);
    setStreamingAssistantText("");
    setStreamState("idle");
  }

  function handleThreadScroll() {
    const node = threadScrollRef.current;
    if (!node) return;
    const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
    setShouldAutoFollowThread(distanceFromBottom < 56);
  }

  function jumpToLatest() {
    setShouldAutoFollowThread(true);
    scrollThreadToBottom("smooth");
  }

  function toggleSidebar(side: "left") {
    setLayoutPrefs((current) => ({
      ...current,
      leftCollapsed: side === "left" ? !current.leftCollapsed : current.leftCollapsed,
    }));
  }

  async function runImperativeBosAssistantIntent(
    message: string,
    intent: NonNullable<ReturnType<typeof detectBosAssistantIntent>>,
    options: { parentResearchReviewRunId?: string | null } = {},
  ): Promise<BosAssistantExecutionResult | null> {
    let structuredResult: AssistantStructuredResult;
    let body = "BOS pulled the requested surface into this thread.";
    const requestedEntityId = extractRequestedEntityId(message);
    const requestedEntityIds = extractRequestedEntityIds(message);

    switch (intent) {
        case "help":
          structuredResult = buildBosAssistantHelpResult();
          body = "BOS can now answer data questions directly inside this assistant thread.";
          break;
        case "simulation_lab": {
          const assistantRun = await assistantApi.createRun({
            message,
            mode: "simulation_lab",
          });
          await queryClient.invalidateQueries({ queryKey: ["bos-simulation-lab"] });
          structuredResult = buildSimulationLabAssistantResult(assistantRun);
          const simulationId =
            typeof assistantRun.result_summary?.simulation_id === "string"
              ? assistantRun.result_summary.simulation_id
              : null;
          const resultIds =
            assistantRun.result_summary?.result_ids && typeof assistantRun.result_summary.result_ids === "object"
              ? (assistantRun.result_summary.result_ids as Record<string, unknown>)
              : {};
          const benchmarkRunId = typeof resultIds.benchmark_run_id === "string" ? resultIds.benchmark_run_id : null;
          const modelApprovalRequestId =
            typeof resultIds.model_approval_request_id === "string" ? resultIds.model_approval_request_id : null;
          body = simulationId
            ? `BOS ran Simulation Lab scenario ${simulationId}${benchmarkRunId ? `, benchmark ${benchmarkRunId}` : ""}${modelApprovalRequestId ? `, and model review ${modelApprovalRequestId}` : ""}.`
            : "BOS completed the Simulation Lab assistant workflow and returned the persisted evidence summary.";
          break;
        }
        case "research_review": {
          const assistantRun = await assistantApi.createRun({
            message,
            mode: "research_review",
            thread_id: sessionId ? String(sessionId) : null,
            parent_run_id: options.parentResearchReviewRunId ?? null,
          });
          await queryClient.invalidateQueries({ queryKey: ["assistant-runs"] });
          if (sessionId) {
            setResearchReviewRunsBySession((current) => ({
              ...current,
              [sessionId]: assistantRun.run_id,
            }));
          }
          structuredResult = buildResearchReviewAssistantResult(assistantRun);
          const finalSynthesis = summaryRecord(assistantRun.final_synthesis ?? assistantRun.result_summary?.final_synthesis);
          const gate =
            typeof finalSynthesis.approval_state === "string" ? finalSynthesis.approval_state : "review_required";
          body =
            localeForText(message) === "zh-CN"
              ? options.parentResearchReviewRunId
                ? `BOS 已沿用上一轮 Research Review ${options.parentResearchReviewRunId}，生成本轮 ${assistantRun.run_id}。多专家交锋、证据包和审查包已带到前台；安全门仍为 ${gate}。`
                : `BOS 已完成 Research Review ${assistantRun.run_id}。多专家交锋、证据包和审查包已带到前台；安全门仍为 ${gate}。`
              : options.parentResearchReviewRunId
                ? `BOS continued Research Review ${options.parentResearchReviewRunId} as ${assistantRun.run_id}. I kept the trace in the background and brought the research-partner readout forward; gate remains ${gate}.`
                : `BOS completed Research Review ${assistantRun.run_id}. I kept the trace in the background and brought the research-partner readout forward; gate remains ${gate}.`;
          break;
        }
        case "riskiest_batch": {
          const [batches, signals, audits] = await Promise.all([
            batchApi.list(1, 8),
            bosApi.listSignals(),
            bosApi.listAuditPackets(),
          ]);
          if (!batches.items.length) {
            structuredResult = {
              title: "No batches are available",
              summary: "BOS could not find any batch records to rank for risk yet.",
              actions: [{ label: "Open batch command", to: "/batches" }],
            };
            body = "BOS could not find any batch records to rank yet.";
            break;
          }

          const scored = await Promise.all(
            batches.items.map(async (batch) => {
              const signal =
                signals
                  .filter((item) => item.batch_id === batch.id)
                  .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null;
              const audit =
                audits.find((item) => item.batch_id === batch.id && (!signal || item.packet?.signal_batch?.id === signal.id)) ??
                audits.find((item) => item.batch_id === batch.id) ??
                null;
              let guidance:
                | { gap_items: Array<{ severity: string; title: string; message: string }>; recommended_actions: string[] }
                | null = null;
              try {
                guidance = await bosApi.getBatchGuidance(batch.id);
              } catch {
                guidance = { gap_items: [], recommended_actions: [] };
              }
              const risk = computeBatchRiskScore({ batch, signal, audit, guidance });
              return {
                batch,
                signal,
                audit,
                guidance,
                score: risk.score,
                reasons: risk.reasons,
              };
            }),
          );

          const highest = [...scored].sort((left, right) => right.score - left.score)[0];
          structuredResult = buildRiskiestBatchResult({
            batch: highest.batch,
            signal: highest.signal,
            audit: highest.audit,
            guidance: highest.guidance,
            score: highest.score,
            reasons: highest.reasons,
          });
          body = `BOS ranked the recent batches and surfaced ${highest.batch.batch_id} as the heaviest current risk.`;
          break;
        }
        case "compile_signal": {
          let batchId = requestedEntityId;
          if (!batchId) {
            const recentBatchList = await batchApi.list(1, 1);
            batchId = recentBatchList.items[0]?.id ?? null;
          }
          if (!batchId) {
            structuredResult = {
              title: "No batch is available to compile",
              summary: "BOS could not find a batch to compile a signal for yet.",
              actions: [{ label: "Open batch command", to: "/batches" }],
            };
            body = "BOS could not find a batch to compile yet.";
            break;
          }
          const compiled = await bosApi.compileSignal({ batch_id: batchId });
          await queryClient.invalidateQueries({ queryKey: ["bos"] });
          await queryClient.invalidateQueries({ queryKey: ["batches"] });
          structuredResult = {
            title: "Signal compiled",
            summary: "BOS compiled a new signal packet and returned the fresh signal posture.",
            metrics: [
              { label: "Batch", value: String(compiled.batch_id), hint: compiled.compiled_signal_id || "Compiled signal" },
              { label: "Freshness", value: compiled.freshness_state || "Unknown", hint: compiled.compile_status },
              { label: "Potency", value: formatNumber(compiled.potency, 4), hint: compiled.potency_unit || "SER-equivalent" },
              { label: "Stability(h)", value: formatNumber(compiled.stability_window_hours, 2), hint: compiled.source_mode },
            ],
            actions: [{ label: "Open signal lab", to: `/bos/signal-lab?batchId=${compiled.batch_id}` }],
          };
          body = `BOS compiled a fresh signal for batch ${compiled.batch_id}.`;
          break;
        }
        case "refresh_signal": {
          const signals = await bosApi.listSignals();
          let signal =
            requestedEntityId != null
              ? signals
                  .filter((item) => item.batch_id === requestedEntityId || item.id === requestedEntityId)
                  .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null
              : null;
          if (!signal) {
            signal = [...signals].sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null;
          }
          if (!signal) {
            structuredResult = {
              title: "No signal is available to refresh",
              summary: "BOS could not find any compiled signal packets yet.",
              actions: [{ label: "Open signal lab", to: "/bos/signal-lab" }],
            };
            body = "BOS could not find a signal to refresh yet.";
            break;
          }
          const refreshed = await bosApi.refreshSignal(signal.id);
          await queryClient.invalidateQueries({ queryKey: ["bos"] });
          await queryClient.invalidateQueries({ queryKey: ["batches"] });
          structuredResult = {
            title: "Signal refreshed",
            summary: "BOS refreshed the latest signal state against current batch timing and metering freshness.",
            metrics: [
              { label: "Signal", value: refreshed.signal_batch.compiled_signal_id || `Signal ${refreshed.signal_batch.id}`, hint: `Batch ${refreshed.signal_batch.batch_id}` },
              { label: "Freshness", value: refreshed.refreshed_state, hint: `Age ${formatNumber(refreshed.metering_age_hours, 2)}h` },
              { label: "Freshness score", value: formatNumber(refreshed.freshness_score, 4), hint: "Signal timing quality" },
              { label: "Readiness score", value: formatNumber(refreshed.release_readiness_score, 4), hint: "Release posture estimate" },
            ],
            actions: [{ label: "Open signal lab", to: `/bos/signal-lab?batchId=${refreshed.signal_batch.batch_id}` }],
          };
          body = `BOS refreshed signal ${refreshed.signal_batch.compiled_signal_id || refreshed.signal_batch.id}.`;
          break;
        }
        case "evaluate_release": {
          let batchId = requestedEntityId;
          if (!batchId) {
            const recentBatchList = await batchApi.list(1, 1);
            batchId = recentBatchList.items[0]?.id ?? null;
          }
          if (!batchId) {
            structuredResult = {
              title: "No batch is available for release evaluation",
              summary: "BOS could not find a batch to evaluate for release yet.",
              actions: [{ label: "Open batch command", to: "/batches" }],
            };
            body = "BOS could not find a batch for release evaluation yet.";
            break;
          }
          const signals = await bosApi.listSignals();
          const latestSignal =
            signals
              .filter((item) => item.batch_id === batchId)
              .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null;
          const decision = await bosApi.evaluateRelease({
            batch_id: batchId,
            signal_batch_id: latestSignal?.id,
            persist: true,
          });
          await queryClient.invalidateQueries({ queryKey: ["bos"] });
          await queryClient.invalidateQueries({ queryKey: ["batches"] });
          structuredResult = {
            title: "Release evaluation completed",
            summary: "BOS evaluated the current release posture and persisted the decision for this batch.",
            metrics: [
              { label: "Batch", value: String(decision.batch_id), hint: latestSignal?.compiled_signal_id || "Latest batch signal" },
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
          body = `BOS evaluated release posture for batch ${decision.batch_id}.`;
          break;
        }
        case "batch_guidance": {
          let batchId = requestedEntityId;
          if (!batchId) {
            const recentBatchList = await batchApi.list(1, 1);
            batchId = recentBatchList.items[0]?.id ?? null;
          }
          if (!batchId) {
            structuredResult = {
              title: "No batch is available for guidance",
              summary: "BOS could not find a batch to load guidance for yet.",
              actions: [{ label: "Open batch command", to: "/batches" }],
            };
            body = "BOS could not find a batch for guidance yet.";
            break;
          }
          const [batch, guidance] = await Promise.all([
            batchApi.get(batchId),
            bosApi.getBatchGuidance(batchId),
          ]);
          structuredResult = buildBatchGuidanceResult({ batch, guidance });
          body = `BOS loaded the latest guidance for batch ${batch.batch_id}.`;
          break;
        }
        case "export_audit_packet": {
          let batchId = requestedEntityId;
          if (!batchId) {
            const recentBatchList = await batchApi.list(1, 1);
            batchId = recentBatchList.items[0]?.id ?? null;
          }
          if (!batchId) {
            structuredResult = {
              title: "No batch is available for audit export",
              summary: "BOS could not find a batch to export an audit packet for yet.",
              actions: [{ label: "Open batch command", to: "/batches" }],
            };
            body = "BOS could not find a batch for audit export yet.";
            break;
          }
          const format = /\bjson\b/i.test(message) ? "json" : "md";
          const blob = await bosApi.exportAuditPacket(batchId, format);
          const filename = `audit-packet-batch-${batchId}.${format}`;
          downloadBlob(blob, filename);
          structuredResult = {
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
          };
          body = `BOS exported the audit packet for batch ${batchId}.`;
          break;
        }
        case "evaluate_supervisor": {
          let batchId = requestedEntityId;
          if (!batchId) {
            const recentBatchList = await batchApi.list(1, 1);
            batchId = recentBatchList.items[0]?.id ?? null;
          }
          const signals = await bosApi.listSignals();
          const signal =
            signals
              .filter((item) => item.batch_id === batchId)
              .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null;
          if (!signal) {
            structuredResult = {
              title: "No compiled signal is available",
              summary: "BOS needs a compiled signal before it can run supervisor evaluation.",
              actions: [{ label: "Open signal lab", to: "/bos/signal-lab" }],
            };
            body = "BOS could not find a compiled signal for supervisor evaluation yet.";
            break;
          }
          const supervisor = await bosApi.evaluateSupervisor(signal.id, buildDefaultSupervisorObservation());
          await queryClient.invalidateQueries({ queryKey: ["bos"] });
          structuredResult = buildSupervisorResult(supervisor);
          body = `BOS evaluated the supervisor posture for signal ${signal.compiled_signal_id || signal.id}.`;
          break;
        }
        case "handover_recommendation": {
          let batchId = requestedEntityId;
          if (!batchId) {
            const recentBatchList = await batchApi.list(1, 1);
            batchId = recentBatchList.items[0]?.id ?? null;
          }
          const signals = await bosApi.listSignals();
          const signal =
            signals
              .filter((item) => item.batch_id === batchId)
              .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null;
          if (!signal) {
            structuredResult = {
              title: "No compiled signal is available",
              summary: "BOS needs a compiled signal before it can run handover recommendation.",
              actions: [{ label: "Open signal lab", to: "/bos/signal-lab" }],
            };
            body = "BOS could not find a compiled signal for handover recommendation yet.";
            break;
          }
          const recommendation = await bosApi.getHandoverRecommendation(
            signal.id,
            buildDefaultSupervisorObservation(),
          );
          await queryClient.invalidateQueries({ queryKey: ["bos"] });
          structuredResult = buildHandoverRecommendationResult(recommendation);
          body = `BOS evaluated the handover recommendation for signal ${signal.compiled_signal_id || signal.id}.`;
          break;
        }
        case "executive_summary": {
          const [summary, decisions, audits, runtime, recentRisks] = await Promise.all([
            dashboardApi.summary(),
            bosApi.listReleaseDecisions(),
            bosApi.listAuditPackets(),
            bosApi.getBrainRuntime(),
            bosApi.getRecentRisks(5).catch(() => null),
          ]);
          structuredResult = buildExecutiveSummaryResult({
            summary,
            decisions,
            audits,
            runtime,
            riskItems: recentRisks?.items ?? [],
          });
          body = "BOS prepared a management-ready summary across dashboard, release, and runtime memory surfaces.";
          break;
        }
        case "batch_analysis": {
          let batchId = requestedEntityId;
          if (!batchId) {
            const recentBatchList = await batchApi.list(1, 1);
            batchId = recentBatchList.items[0]?.id ?? null;
          }
          if (!batchId) {
            structuredResult = {
              title: "No batch is available to analyze",
              summary:
                "BOS could not find any batch records yet, so there is nothing to run a focused batch analysis on.",
              actions: [{ label: "Open batch command", to: "/batches" }],
            };
            body = "BOS could not find a batch to analyze yet.";
            break;
          }

          const [batch, guidance, signals, audits, risk] = await Promise.all([
            batchApi.get(batchId),
            bosApi.getBatchGuidance(batchId),
            bosApi.listSignals(),
            bosApi.listAuditPackets(),
            bosApi.getBatchRisk(batchId).catch(() => null),
          ]);
          const signal = signals
            .filter((item) => item.batch_id === batch.id)
            .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null;
          const audit =
            audits.find((item) => item.batch_id === batch.id && (!signal || item.packet?.signal_batch?.id === signal.id)) ??
            audits.find((item) => item.batch_id === batch.id) ??
            null;

          structuredResult = buildBatchAnalysisResult({
            batch,
            guidance,
            signal,
            audit,
            risk,
          });
          body = `BOS analyzed batch ${batch.batch_id} and pulled its latest guidance into this thread.`;
          break;
        }
        case "batch_compare": {
          const batchLimit = requestedEntityIds.length >= 2 ? Math.max(...requestedEntityIds) : 10;
          const [batches, signals, audits] = await Promise.all([
            batchApi.list(1, batchLimit),
            bosApi.listSignals(),
            bosApi.listAuditPackets(),
          ]);
          const selectedBatches =
            requestedEntityIds.length >= 2
              ? requestedEntityIds
                  .map((id) => batches.items.find((item) => item.id === id))
                  .filter((item): item is Batch => Boolean(item))
                  .slice(0, 2)
              : batches.items.slice(0, 2);
          structuredResult = buildBatchCompareResult({
            batches: selectedBatches,
            signals,
            audits,
          });
          body = "BOS compared the latest batch records side by side.";
          break;
        }
        case "overview": {
          const [summary, trend, activity, batches, signals, audits, decisions, twins, recentRisks] = await Promise.all([
            dashboardApi.summary(),
            dashboardApi.serTrend(30),
            dashboardApi.recentActivity(6),
            batchApi.list(1, 12),
            bosApi.listSignals(),
            bosApi.listAuditPackets(),
            bosApi.listReleaseDecisions(),
            twinApi.list(1, 12),
            bosApi.getRecentRisks(5).catch(() => null),
          ]);
          structuredResult = buildOverviewResult({
            summary,
            trend,
            activity,
            batchesTotal: batches.total,
            signals,
            audits,
            decisions,
            twinsTotal: twins.total,
            riskItems: recentRisks?.items ?? [],
          });
          body = "BOS merged the main dashboard, signal, audit, release, and twin surfaces into one overview.";
          break;
        }
        case "batches_table": {
          const batches = await batchApi.list(1, 12);
          structuredResult = buildBatchesTableResult(batches);
          body = "BOS opened the batch surface as an in-thread table.";
          break;
        }
        case "signals_table": {
          const signals = await bosApi.listSignals();
          structuredResult = buildSignalsTableResult(signals);
          body = "BOS summarized the latest signal packets in-table.";
          break;
        }
        case "audit_table": {
          const audits = await bosApi.listAuditPackets();
          structuredResult = buildAuditTableResult(audits);
          body = "BOS pulled the current audit packets and release posture into this thread.";
          break;
        }
        case "twins_table": {
          const twins = await twinApi.list(1, 12);
          structuredResult = buildTwinsTableResult(twins);
          body = "BOS opened the digital twin registry in-table.";
          break;
        }
        case "ser_trend_chart": {
          const trend = await dashboardApi.serTrend(30);
          structuredResult = {
            title: "SER trend chart",
            summary: "Rolling SER signal across the latest dashboard window.",
            chart: {
              kind: "ser-trend",
              title: "SER trend / 30 days",
              data: trend.data_points,
            },
            notes: trend.data_points.length
              ? [
                  `Latest SER: ${formatNumber(trend.data_points[trend.data_points.length - 1]?.ser_value, 4)}`,
                  `Window: ${trend.period_days} days`,
                ]
              : ["No trend data is available yet for this window."],
            actions: [{ label: "Open dashboard", to: "/dashboard" }],
          };
          body = "BOS rendered the current SER trend directly in the conversation.";
          break;
        }
        case "grade_chart": {
          const gradeDistribution = await dashboardApi.gradeDistribution();
          structuredResult = {
            title: "Grade distribution chart",
            summary: "Current grade mix from dashboard results.",
            chart: {
              kind: "grade-distribution",
              title: "Grade distribution",
              data: gradeDistribution.items,
            },
            notes: [`Total graded items: ${gradeDistribution.total}`],
            actions: [{ label: "Open dashboard", to: "/dashboard" }],
          };
          body = "BOS rendered the grade distribution chart in-thread.";
          break;
        }
        case "species_chart": {
          const speciesDistribution = await dashboardApi.speciesDistribution();
          structuredResult = {
            title: "Species distribution chart",
            summary: "Current species mix based on dashboard distribution data.",
            chart: {
              kind: "species-distribution",
              title: "Species distribution",
              data: speciesDistribution.distribution,
            },
            notes: [`Total items counted: ${speciesDistribution.total}`],
            actions: [{ label: "Open dashboard", to: "/dashboard" }],
          };
          body = "BOS rendered the species mix chart in-thread.";
          break;
        }
        case "brain_summary": {
          const runtime = await bosApi.getBrainRuntime();
          structuredResult = buildBrainSummaryResult(runtime);
          body = "BOS summarized the runtime brain surfaces directly in this thread.";
          break;
        }
        case "release_summary": {
          const [decisions, audits] = await Promise.all([
            bosApi.listReleaseDecisions(),
            bosApi.listAuditPackets(),
          ]);
          structuredResult = buildReleaseSummaryResult({ decisions, audits });
          body = "BOS summarized current release posture from decisions and audit packets.";
          break;
        }
        case "release_risks": {
          const [decisions, audits, recentRisks] = await Promise.all([
            bosApi.listReleaseDecisions(),
            bosApi.listAuditPackets(),
            bosApi.getRecentRisks(5).catch(() => null),
          ]);
          structuredResult = buildReleaseRiskResult(decisions, audits, recentRisks?.items ?? []);
          body = "BOS extracted the active release risks from current audit packet evidence.";
          break;
        }
        case "native_runtime": {
          const runtime = await bosApi.getNativeModelRuntimeStatus();
          structuredResult = buildNativeRuntimeResult(runtime);
          body = "BOS summarized the native model runtime and adapter readiness.";
          break;
        }
        case "species_catalog": {
          const catalog = await bosApi.listSpecies();
          structuredResult = buildCatalogTableResult({
            title: "Species catalog",
            summary: "Reference species available in the BOS atlas.",
            columns: ["Code", "Common name", "Scientific name", "SER", "Development(days)"],
            rows: catalog.species.slice(0, 12).map((item) => [
              item.code,
              item.common_name,
              item.scientific_name,
              formatNumber(item.ser_typical, 4),
              String(item.development_days),
            ]),
            action: { label: "Open references", to: "/bos/references" },
            note: `Showing ${Math.min(catalog.species.length, 12)} of ${catalog.count} species.`,
          });
          body = "BOS opened the species atlas subset inside the thread.";
          break;
        }
        case "feedstocks_catalog": {
          const catalog = await bosApi.listFeedstocks();
          structuredResult = buildCatalogTableResult({
            title: "Feedstock catalog",
            summary: "Reference feedstock entries and suitability posture from the BOS atlas.",
            columns: ["Key", "Display name", "Category", "Moisture risk", "Contamination risk"],
            rows: catalog.feedstocks.slice(0, 12).map((item) => [
              item.key,
              item.display_name,
              item.category,
              item.moisture_risk,
              item.contamination_risk,
            ]),
            action: { label: "Open references", to: "/bos/references" },
            note: `Showing ${Math.min(catalog.feedstocks.length, 12)} of ${catalog.count} feedstocks.`,
          });
          body = "BOS opened the feedstock atlas subset inside the thread.";
          break;
        }
        case "manuscript_catalog": {
          const catalog = await bosApi.listManuscriptCampaigns();
          structuredResult = buildManuscriptCatalogResult(catalog);
          body = "BOS opened the reference campaign catalog inside the thread.";
          break;
        }
        case "open_signal_lab":
          structuredResult = {
            title: "Signal lab shortcut",
            summary: "Jump into signal compile, supervisor, audit, and next-best-action control.",
            actions: [{ label: "Open signal lab", to: "/bos/signal-lab" }],
          };
          body = "BOS prepared the signal lab jump.";
          break;
        case "open_brain":
          structuredResult = {
            title: "Brain dashboard shortcut",
            summary: "Jump into project brain, decision journal, and runtime memory editing.",
            actions: [{ label: "Open brain dashboard", to: "/bos/brain" }],
          };
          body = "BOS prepared the brain dashboard jump.";
          break;
        case "open_release":
          structuredResult = {
            title: "Release center shortcut",
            summary: "Jump into release readiness, dossier review, and release checks.",
            actions: [{ label: "Open release center", to: "/release" }],
          };
          body = "BOS prepared the release center jump.";
          break;
        case "open_dashboard":
          structuredResult = {
            title: "Dashboard shortcut",
            summary: "Jump into executive overview, trend posture, and distribution charts.",
            actions: [{ label: "Open dashboard", to: "/dashboard" }],
          };
          body = "BOS prepared the dashboard jump.";
          break;
        case "open_twins":
          structuredResult = {
            title: "Twins shortcut",
            summary: "Jump into digital twin registry and scenario inspection.",
            actions: [{ label: "Open twins", to: "/twins" }],
          };
          body = "BOS prepared the twin surface jump.";
          break;
        default:
          return null;
      }

    return { body, structuredResult };
  }

  async function handleBosAssistantRequest(message: string) {
    if (!sessionId) return false;
    const latestResearchReviewRunId = researchReviewRunsBySession[sessionId] ?? null;
    const detectedIntent = detectBosAssistantIntent(message);
    const intent =
      detectedIntent ??
      (isResearchReviewFollowUp(message, latestResearchReviewRunId) ? "research_review" : null);
    if (!intent) return false;
    const parentResearchReviewRunId = resolveResearchReviewContinuationParentRunId(
      message,
      latestResearchReviewRunId,
    );

    setPendingPrompt(message);
    setStreamState("streaming");
    setStreamStatusDetail(null);
    setPrompt("");
    setDrafts((current) => {
      const next = { ...current };
      delete next[sessionId];
      return next;
    });

    const userEcho: AssistantMessage = {
      id: `bos-user-${sessionId}-${Date.now()}`,
      role: "user",
      body: message,
      createdAt: new Date().toISOString(),
    };

    setLocalAssistantMessages((current) => ({
      ...current,
      [sessionId]: [...(current[sessionId] ?? []), userEcho],
    }));

    try {
      const graphName = getBosAssistantGraphName(intent);
      let execution: BosAssistantExecutionResult | null = null;
      if (graphName) {
        const context = createBosGraphContext({
          graphName,
          intent,
          message,
          queryClient,
          apiClients: {
            batch: batchApi,
            bos: bosApi,
            dashboard: dashboardApi,
            twin: twinApi,
          },
          sessionId,
          userRole: user?.role ?? "viewer",
          effects: { downloadBlob },
        });
        const graphRun = await runBosGraphWithFallback(graphName, context, async (): Promise<BosGraphNodeOutput> => {
            const fallbackResult = await runImperativeBosAssistantIntent(message, intent, {
              parentResearchReviewRunId,
            });
          if (!fallbackResult) {
            throw new Error(`No fallback available for BOS assistant intent: ${intent}`);
          }
          return {
            status: "completed",
            body: fallbackResult.body,
            structuredResult: fallbackResult.structuredResult,
            diagnostics: [{ scope: "imperative_fallback", message: "Graph execution failed; imperative fallback completed." }],
          };
        });
        execution = {
          body: graphRun.result.body,
          structuredResult: graphRun.result.structuredResult,
        };
      } else {
        execution = await runImperativeBosAssistantIntent(message, intent, {
          parentResearchReviewRunId,
        });
      }

      if (!execution) return false;
      const assistantReply: AssistantMessage = {
        id: `bos-${sessionId}-${Date.now()}`,
        role: "assistant",
        body: execution.body,
        createdAt: new Date().toISOString(),
        structuredResult: execution.structuredResult,
      };

      setLocalAssistantMessages((current) => ({
        ...current,
        [sessionId]: [...(current[sessionId] ?? []), assistantReply],
      }));
      setStreamState("idle");
      return true;
    } catch (error) {
      setStreamState("failed");
      setStreamStatusDetail(getErrorDetail(error, "BOS data request failed"));
      setPrompt(message);
      toast.error(getErrorDetail(error, "BOS could not load that surface"));
      return true;
    } finally {
      setPendingPrompt(null);
    }
  }

  async function handleSubmit() {
    const message = prompt.trim();
    if (!message || !sessionId || !accessToken || pendingPrompt) return;

    const mediaIntent = inferMediaIntent(message);
    if (mediaIntent.enabled) {
      setPendingPrompt(message);
      setStreamState("streaming");
      setStreamStatusDetail(null);
      setPrompt("");
      setDrafts((current) => {
        const next = { ...current };
        delete next[sessionId];
        return next;
      });
      const userEcho: AssistantMessage = {
        id: `media-user-${sessionId}-${Date.now()}`,
        role: "user",
        body: message,
        createdAt: new Date().toISOString(),
      };
      setLocalAssistantMessages((current) => ({
        ...current,
        [sessionId]: [...(current[sessionId] ?? []), userEcho],
      }));
      try {
        const emergencyRender = await mediaApi.render(buildEmergencyStillPayload(message));
        const blob = await mediaApi.fetchAssetBlob(emergencyRender.file_name);
        const previewUrl = URL.createObjectURL(blob);
        const assistantReply: AssistantMessage = {
          id: `media-${sessionId}-${Date.now()}`,
          role: "assistant",
          body:
            "BOS Assistant is currently using the most stable media path, so I generated a safe still graphic for you. " +
            "You can download it now or open Media Studio if you want richer layouts and animation.",
          createdAt: new Date().toISOString(),
          mediaResult: {
            kind: emergencyRender.kind,
            templateId: emergencyRender.template_id,
            fileName: emergencyRender.file_name,
            previewUrl,
            createdAt: emergencyRender.created_at,
            presetPayload: buildAssistantPresetPayload({
              prompt: message,
              renderKind: emergencyRender.kind,
              templateId: emergencyRender.template_id,
              title: "BOS Media",
              subtitle: "Assistant safe still",
              caption: "Safe generation",
              accentColor: "#7CFFB2",
              backgroundColor: "#07111F",
              width: emergencyRender.width,
              height: emergencyRender.height,
              fps: emergencyRender.fps ?? 30,
              durationInFrames: emergencyRender.duration_in_frames ?? 1,
              extraProps: {
                eyebrow: "BOS MEDIA",
                supporting_line: "Mode: Stable",
                pill_label: "READY",
              },
              fileName: emergencyRender.file_name,
            }),
            savedPresetName: null,
            sourcePrompt: message,
            canGenerateAnimation: /动画|视频|video|animation|mp4|motion/.test(message.toLowerCase()),
            animationGenerated: false,
          },
        };
        setLocalAssistantMessages((current) => ({
          ...current,
          [sessionId]: [...(current[sessionId] ?? []), assistantReply],
        }));
        setStreamState("idle");
      } catch (error) {
        setStreamState("failed");
        setStreamStatusDetail(getErrorDetail(error, "Media generation failed"));
        setPrompt(message);
        toast.error(getErrorDetail(error, "Assistant could not generate media"));
      } finally {
        setPendingPrompt(null);
      }
      return;
    }

    const bosRequestHandled = await handleBosAssistantRequest(message);
    if (bosRequestHandled) {
      return;
    }

    setPendingPrompt(message);
    setStreamingAssistantText("");
    setStreamState("streaming");
    setStreamStatusDetail(null);
    setShouldAutoFollowThread(true);
    setPrompt("");
    setDrafts((current) => {
      const next = { ...current };
      delete next[sessionId];
      return next;
    });
    let aborted = false;
    let failed = false;
    try {
      const controller = new AbortController();
      streamAbortRef.current = controller;
      let streamedText = "";
      await codeApi.streamTurn(
        sessionId,
        {
          user_message: message,
          stream: true,
          provider: ASSISTANT_TEAM_PROVIDER,
          model: selectedAssistantModel,
        },
        accessToken,
        {
          onDelta: (delta) => {
            streamedText += delta;
            const waitMs = delta.includes("\n\n") ? 55 : delta.trim().endsWith(".") ? 40 : 22;
            window.setTimeout(() => setStreamingAssistantText(streamedText), waitMs);
          },
          onDone: () => undefined,
          onError: (detail) => {
            throw new Error(detail);
          },
        },
        controller.signal,
      );
      await queryClient.invalidateQueries({ queryKey: codeKeys.sessions() });
      await queryClient.invalidateQueries({ queryKey: codeKeys.session(sessionId) });
      await queryClient.invalidateQueries({ queryKey: codeKeys.events(sessionId) });
    } catch (error) {
      if ((error as Error).name === "AbortError") {
        aborted = true;
        setStreamState("stopped");
        setStreamStatusDetail("Stopped by you");
        await queryClient.invalidateQueries({ queryKey: codeKeys.sessions() });
        await queryClient.invalidateQueries({ queryKey: codeKeys.session(sessionId) });
        await queryClient.invalidateQueries({ queryKey: codeKeys.events(sessionId) });
      } else {
        failed = true;
        setStreamState("failed");
        setStreamStatusDetail((error as Error).message || "Network or provider issue");
        setPrompt(message);
        toast.error("Live streaming failed");
      }
    } finally {
      streamAbortRef.current = null;
      if (!aborted && !failed) {
        setStreamingAssistantText("");
      }
      setPendingPrompt(null);
      window.setTimeout(() => {
        setStreamState((current) => (current === "streaming" ? "idle" : current));
      }, 120);
    }
  }

  async function handleStopGenerating() {
    setStreamState("stopped");
    streamAbortRef.current?.abort();
  }

  async function handleSaveAssistantPreset(messageId: string, mediaResult: AssistantMediaResult) {
    const saved = await mediaApi.createPreset(mediaResult.presetPayload);
    if (!sessionId) return;
    setLocalAssistantMessages((current) => ({
      ...current,
      [sessionId]: (current[sessionId] ?? []).map((message) =>
        message.id === messageId
          ? {
              ...message,
              mediaResult: {
                ...mediaResult,
                savedPresetName: saved.name,
              },
            }
          : message,
      ),
    }));
    toast.success("Saved as team preset");
  }

  async function handleGenerateAssistantAnimation(messageId: string, mediaResult: AssistantMediaResult) {
    if (!sessionId || !mediaResult.sourcePrompt) return;
    try {
      const mediaRun = await mediaApi.assistantRun({
        prompt: mediaResult.sourcePrompt,
        preferred_kind: "video",
      });
      const blob = await mediaApi.fetchAssetBlob(mediaRun.render.file_name);
      const previewUrl = URL.createObjectURL(blob);
      setLocalAssistantMessages((current) => ({
        ...current,
        [sessionId]: (current[sessionId] ?? []).map((message) =>
          message.id === messageId
            ? (() => {
                if (message.mediaResult?.previewUrl) {
                  URL.revokeObjectURL(message.mediaResult.previewUrl);
                }
                return {
                  ...message,
                  body:
                    "BOS upgraded the safe still into a short animation for this same request. " +
                    "You can preview it below, download it, or continue refining in Media Studio.",
                  mediaResult: {
                    ...message.mediaResult!,
                    kind: mediaRun.render.kind,
                    templateId: mediaRun.render.template_id,
                    fileName: mediaRun.render.file_name,
                    previewUrl,
                    createdAt: mediaRun.render.created_at,
                    presetPayload: buildAssistantPresetPayload({
                      prompt: mediaResult.sourcePrompt ?? "",
                      renderKind: mediaRun.render.kind,
                      templateId: mediaRun.render.template_id,
                      title: mediaRun.suggestion.title,
                      subtitle: mediaRun.suggestion.subtitle,
                      caption: mediaRun.suggestion.caption,
                      accentColor: mediaRun.suggestion.accent_color,
                      backgroundColor: mediaRun.suggestion.background_color,
                      width: mediaRun.render.width,
                      height: mediaRun.render.height,
                      fps: mediaRun.render.fps ?? mediaRun.suggestion.fps,
                      durationInFrames:
                        mediaRun.render.duration_in_frames ?? mediaRun.suggestion.duration_in_frames,
                      extraProps: mediaRun.suggestion.extra_props,
                      fileName: mediaRun.render.file_name,
                    }),
                    animationGenerated: true,
                  },
                };
              })()
            : message,
        ),
      }));
      toast.success("Animation generated");
    } catch (error) {
      toast.error(getErrorDetail(error, "Animation generation failed"));
    }
  }

  function handlePromptKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.nativeEvent as KeyboardEvent).isComposing || (event.nativeEvent as KeyboardEvent).keyCode === 229) {
      return;
    }
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    void handleSubmit();
  }

  async function handleRenameSession() {
    if (!sessionId) return;
    const nextTitle = titleDraft.trim();
    await updateSession.mutateAsync({ title: nextTitle || null });
    setPersistedTitles((current) => {
      const next = { ...current };
      if (nextTitle) next[sessionId] = nextTitle;
      else delete next[sessionId];
      return next;
    });
    setEditingTitle(false);
  }

  if (!canUseAssistant) {
    return (
      <div className="space-y-6">
        <div className="assistant-aside-card assistant-sanctuary assistant-hero-shell rounded-[30px] px-6 py-6">
          <div className="relative z-[1] flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="neutral" className="assistant-thread-top-badge bg-white/8 text-white">
                  BOS Assistant
                </Badge>
                <Badge variant="brand" className="assistant-thread-top-badge">{translateText("Conversation-first")}</Badge>
                <Badge variant="warning" className="assistant-thread-top-badge">{translateText("Role-aware access")}</Badge>
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.8rem]">
                {translateText("The front door is now conversational")}
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText("This tenant role can still move through the scientific product surfaces, but BOS Assistant threads are reserved for operator-grade workflows.")}
              </p>
            </div>
            <div className="assistant-hero-sigil-wrap self-start lg:self-center">
              <BOSSigil size="sm" showGlyph className="mx-auto" />
            </div>
          </div>
        </div>
        <Card tone="hero">
          <CardBody className="grid gap-4 lg:grid-cols-2">
            <div className="assistant-side-panel-chip rounded-[24px] p-5">
              <p className="text-sm font-semibold text-white">{translateText("Assistant access is limited for this role")}</p>
              <p className="mt-3 text-sm leading-7 text-surface-300">
                {translateText("BOS Assistant now sits at the front of the product, but this account cannot open live threads yet.")}
                {" "}
                {translateText("The rest of the product remains available from the directory.")}
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {QUICK_LINKS.map((link) => (
                <SurfaceTileButton
                  key={link.to}
                  onClick={() => navigate(link.to)}
                  className="assistant-context-link assistant-side-panel-chip rounded-[24px] p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">{link.title}</p>
                      <p className="mt-2 text-xs leading-6 text-surface-400">{link.description}</p>
                    </div>
                    <ArrowRight className="assistant-context-arrow mt-0.5 h-4 w-4 flex-shrink-0 text-brand-200" />
                  </div>
                </SurfaceTileButton>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>
    );
  }

  if (sessions.isError && sessionsStatus === 404) {
    return (
      <div className="space-y-6">
        <div className="assistant-aside-card assistant-sanctuary assistant-hero-shell rounded-[30px] px-6 py-6">
          <div className="relative z-[1] flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="neutral" className="assistant-thread-top-badge bg-white/8 text-white">
                  BOS Assistant
                </Badge>
                <Badge variant="brand" className="assistant-thread-top-badge">{translateText("Conversation-first")}</Badge>
                <Badge variant="warning" className="assistant-thread-top-badge">{translateText("Runtime unavailable")}</Badge>
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.8rem]">
                {translateText("Assistant runtime is not available here yet")}
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText("The conversation front door is wired up, but this tenant does not currently have the BOS assistant runtime enabled.")}
              </p>
            </div>
            <div className="assistant-hero-sigil-wrap self-start lg:self-center">
              <BOSSigil size="sm" showGlyph className="mx-auto" />
            </div>
          </div>
        </div>
        <CockpitPanel className="assistant-side-shell rounded-[28px] p-5">
          <CardBody className="space-y-4">
            <div className="assistant-side-panel-chip rounded-[24px] p-5 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-white/10 bg-white/6 text-brand-100">
                <Sparkles className="h-7 w-7" />
              </div>
              <p className="mt-4 text-base font-semibold text-white">{translateText("BOS Assistant is offline for this tenant")}</p>
              <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText("Enable the BOS Code capability or use the product surfaces directly from the directory while the assistant runtime is unavailable.")}
              </p>
            </div>
          </CardBody>
        </CockpitPanel>
      </div>
    );
  }

  if (sessions.isError) {
    return (
      <div className="space-y-6">
        <div className="assistant-aside-card assistant-sanctuary assistant-hero-shell rounded-[30px] px-6 py-6">
          <div className="relative z-[1] flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="neutral" className="assistant-thread-top-badge bg-white/8 text-white">
                  BOS Assistant
                </Badge>
                <Badge variant="danger" className="assistant-thread-top-badge">{translateText("Runtime issue")}</Badge>
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.8rem]">
                {translateText("BOS Assistant could not load")}
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText("The conversation layer did not come online cleanly. Retry the page and, if needed, move through the product surfaces from the directory.")}
              </p>
            </div>
            <div className="assistant-hero-sigil-wrap self-start lg:self-center">
              <BOSSigil size="sm" showGlyph className="mx-auto" />
            </div>
          </div>
        </div>
        <CockpitPanel className="assistant-side-shell rounded-[28px] p-5">
          <CardBody className="space-y-4">
            <div className="assistant-side-panel-chip rounded-[24px] p-5 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-red-400/18 bg-red-500/10 text-red-200">
                <Sparkles className="h-7 w-7" />
              </div>
              <p className="mt-4 text-base font-semibold text-white">{translateText("Assistant runtime did not come online cleanly")}</p>
              <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText("Retry the assistant surface now, or move through the nearby BOS decision surfaces while the conversation layer recovers.")}
              </p>
              <div className="mt-5 flex justify-center">
                <Button className="assistant-composer-action assistant-composer-action-primary" onClick={() => void sessions.refetch()}>
                  {translateText("Retry assistant")}
                </Button>
              </div>
            </div>
          </CardBody>
        </CockpitPanel>
      </div>
    );
  }

  return (
    <div className="assistant-ambient-shell space-y-6">
      <div className="assistant-ambient-backdrop" aria-hidden="true">
        <span className="assistant-ambient-orb assistant-ambient-orb-cyan" />
        <span className="assistant-ambient-orb assistant-ambient-orb-violet" />
        <span className="assistant-ambient-orb assistant-ambient-orb-white" />
        <span className="assistant-ambient-grid" />
        <span className="assistant-ambient-scan assistant-ambient-scan-a" />
        <span className="assistant-ambient-scan assistant-ambient-scan-b" />
      </div>
      <div className={["space-y-5", layoutPrefs.density === "compact" ? "assistant-density-compact" : "assistant-density-comfortable"].join(" ")}>
        <div className="space-y-5">
          <CockpitPanel tone="hero" className="assistant-arrival-host p-5 lg:p-6">
            <div className="assistant-flagship-reactor" aria-hidden="true">
              <span className="assistant-flagship-reactor__halo" />
              <span className="assistant-flagship-reactor__shell assistant-flagship-reactor__shell--outer" />
              <span className="assistant-flagship-reactor__shell assistant-flagship-reactor__shell--inner" />
              <span className="assistant-flagship-reactor__rail assistant-flagship-reactor__rail--left" />
              <span className="assistant-flagship-reactor__rail assistant-flagship-reactor__rail--right" />
              <span className="assistant-flagship-reactor__dust" />
            </div>
            <AssistantArrivalEffect />
            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-0 flex-1">
                <Badge variant="neutral" className="assistant-thread-top-badge bg-white/8 text-white">{translateText("BOS Assistant")}</Badge>
                <Badge variant={sessionStatusVariant(currentSession?.session_status ?? "created")} size="xs" className="assistant-thread-top-badge">
                  {translateText(sessionStatusLabel(currentSession?.session_status ?? "created"))}
                </Badge>
                <Badge variant="info" size="xs" className="assistant-thread-top-badge">
                  {selectedAssistantModel}
                </Badge>
                <Badge variant="neutral" size="xs" className="assistant-thread-top-badge">
                  {translateText("BOS APIs · Team pool")}
                </Badge>
                <div className="assistant-arrival-core mt-3 flex flex-wrap items-center gap-3">
                  {editingTitle ? (
                    <>
                      <Input value={titleDraft} onChange={(event) => setTitleDraft(event.target.value)} placeholder={translateText("Name this thread")} className="assistant-title-input max-w-md" />
                      <Button size="sm" onClick={() => void handleRenameSession()} loading={updateSession.isPending} className="assistant-inline-action">{translateText("Save")}</Button>
                      <Button size="sm" variant="ghost" className="assistant-inline-action assistant-inline-action-ghost" onClick={() => { setEditingTitle(false); setTitleDraft(currentSession?.title?.trim() || ""); }}>{translateText("Cancel")}</Button>
                    </>
                  ) : (
                    <>
                      <h2 className="assistant-thread-title assistant-arrival-title max-w-4xl">{translateText(currentSession?.title?.trim() || "Ask BOS for the next move")}</h2>
                      {sessionId ? (
                        <Button size="sm" variant="ghost" className="assistant-inline-action assistant-inline-action-ghost" leftIcon={<PenLine className="h-4 w-4" />} onClick={() => setEditingTitle(true)}>
                          {translateText("Rename")}
                        </Button>
                      ) : null}
                    </>
                  )}
                </div>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-surface-300">
                  {translateText("Use this page for conversation only. Other operational surfaces stay in their own modules.")}
                </p>
              </div>
              <div className="ml-auto flex items-center gap-2">
                {layoutPrefs.leftCollapsed ? (
                  <Button size="sm" variant="ghost" className="assistant-inline-action assistant-inline-action-ghost" leftIcon={<PanelLeftOpen className="h-4 w-4" />} onClick={() => toggleSidebar("left")}>
                    {translateText("Threads")}
                  </Button>
                ) : null}
                <Button size="sm" className="assistant-inline-action" onClick={() => void handleNewChat()} loading={createSession.isPending}>
                  {translateText("New chat")}
                </Button>
              </div>
            </div>
          </CockpitPanel>

          {!layoutPrefs.leftCollapsed ? (
            <div className="assistant-thread-drawer" role="dialog" aria-label={translateText("Threads")}>
              <button
                type="button"
                aria-label={translateText("Close threads")}
                className="assistant-thread-drawer-backdrop"
                onClick={() => toggleSidebar("left")}
              />
              <CockpitPanel tone="rail" className="assistant-thread-drawer-panel p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <CockpitSectionLabel>{translateText("Thread rail")}</CockpitSectionLabel>
                    <p className="mt-3 text-sm leading-6 text-surface-300">
                      {translateText("Resume active operator threads without leaving the control stage.")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="neutral" size="xs" className="assistant-side-count-badge">
                      {sessions.data?.items.length ?? 0}
                    </Badge>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="assistant-inline-action assistant-inline-action-ghost"
                      leftIcon={<PanelLeftClose className="h-4 w-4" />}
                      onClick={() => toggleSidebar("left")}
                    >
                      {translateText("Hide")}
                    </Button>
                  </div>
                </div>
                <div className="mt-4 space-y-3">
                  <Input
                    value={threadQuery}
                    onChange={(event) => setThreadQuery(event.target.value)}
                    placeholder={translateText("Search a live thread")}
                    leftIcon={<Search className="h-4 w-4" />}
                    className="assistant-side-search"
                  />
                  <div className="flex items-center justify-between gap-3 px-1 text-[11px] text-surface-500">
                    <span>{threadMeta}</span>
                    {threadQuery.trim() ? (
                      <button
                        type="button"
                        onClick={() => setThreadQuery("")}
                        className="assistant-side-clear transition-colors hover:text-white"
                      >
                        {translateText("Clear")}
                      </button>
                    ) : null}
                  </div>
                </div>
                {sessions.isLoading || createSession.isPending ? (
                  <div className="assistant-side-panel-chip mt-4 flex items-center gap-3 rounded-[22px] px-4 py-4 text-sm text-surface-300">
                    <Spinner size="sm" />
                    <span>{translateText("Preparing your assistant thread")}</span>
                  </div>
                ) : null}
                <div className="mt-4 space-y-4">
                  {threadGroups.today.length ? (
                    <div className="space-y-2">
                      <p className="assistant-side-group-label px-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-surface-500">
                        {translateText("Today")}
                      </p>
                      {threadGroups.today.map((session) =>
                        renderSessionButton(session, {
                          sessionId,
                          sessionDetailId: sessionDetail.data?.session.id,
                          persistedTitle: persistedTitles[session.id],
                          turns: sessionDetail.data?.turns,
                          onSelect: (id) => {
                            setSelectedSessionId(id);
                            setLayoutPrefs((current) => ({ ...current, leftCollapsed: true }));
                          },
                        }),
                      )}
                    </div>
                  ) : null}
                  {threadGroups.earlier.length ? (
                    <div className="space-y-2">
                      <p className="assistant-side-group-label px-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-surface-500">
                        {translateText("Earlier")}
                      </p>
                      {threadGroups.earlier.map((session) =>
                        renderSessionButton(session, {
                          sessionId,
                          sessionDetailId: sessionDetail.data?.session.id,
                          persistedTitle: persistedTitles[session.id],
                          turns: sessionDetail.data?.turns,
                          onSelect: (id) => {
                            setSelectedSessionId(id);
                            setLayoutPrefs((current) => ({ ...current, leftCollapsed: true }));
                          },
                        }),
                      )}
                    </div>
                  ) : null}
                </div>
                {!sessions.isLoading && !createSession.isPending && !sessions.data?.items.length ? (
                  <EmptyState
                    icon={<Bot className="h-10 w-10" />}
                    title={translateText("No thread yet")}
                    description={translateText("Open the first runtime thread and use this rail as your operator handoff memory.")}
                    actionLabel={translateText("Start first chat")}
                    onAction={() => void handleNewChat()}
                    className="assistant-side-empty mt-4 rounded-[24px] py-10"
                  />
                ) : null}
                {!sessions.isLoading && !createSession.isPending && !!sessions.data?.items.length && !filteredSessions.length ? (
                  <EmptyState
                    icon={<Search className="h-8 w-8" />}
                    title={translateText("No matching thread")}
                    description={translateText("Try a session id, status, or clear the search to restore the full rail.")}
                    className="assistant-side-empty mt-4 rounded-[24px] py-8"
                  />
                ) : null}
              </CockpitPanel>
            </div>
          ) : null}

          <div className="assistant-aside-card assistant-thread-shell assistant-thread-surface rounded-[26px] p-4">
                  <p className="assistant-section-kicker assistant-thread-rail-label">
                    {translateText("Thread")}
                  </p>
                  <div className="mt-4">
                    <CodeRuntimeHud
                      status={currentSession?.session_status ?? "created"}
                      providerIssue={providerIssue}
                      className="border-0 bg-transparent px-0 py-0"
                      label={translateText("Runtime")}
                      resultSummary={assistantRecoveryResultSummary}
                      actionLabel={assistantAutomationAction ? formatCodeActionCallToAction(assistantAutomationAction) : undefined}
                      onAction={assistantAutomationAction ? () => executeNextAutomationAction.mutate() : undefined}
                      actionLoading={executeNextAutomationAction.isPending}
                    />
                  </div>
                  <div
                    ref={threadScrollRef}
                    onScroll={handleThreadScroll}
                    className="assistant-thread-scroll mt-5 max-h-[38rem] space-y-4 overflow-y-auto pr-1"
                  >
                {visibleThreadMessages.length ? (
                  visibleThreadMessages.map((message) => (
                    <div
                      key={message.id}
                      className={[
                        "assistant-message-shell animate-fade-in rounded-[28px] px-5 py-4",
                        message.role === "user"
                          ? "assistant-message-user ml-auto max-w-[85%]"
                          : "assistant-message-bos max-w-[92%]",
                        message.pending ? "opacity-80" : "",
                      ].join(" ")}
                    >
                      <div className="assistant-message-head flex items-center gap-2 text-xs text-surface-400">
                        {message.role === "assistant" ? (
                          <>
                            <Orbit className="h-3.5 w-3.5 text-brand-200" />
                            <span>{translateText("BOS runtime")}</span>
                          </>
                        ) : (
                          <>
                            <Compass className="h-3.5 w-3.5 text-sky-200" />
                            <span>{translateText("Operator")}</span>
                          </>
                        )}
                        {message.pending ? (
                          <Badge variant="neutral" size="xs" className="assistant-thread-note-badge">
                        {translateText(message.streaming ? "arriving" : "thinking")}
                          </Badge>
                        ) : null}
                      </div>
                      <div className="mt-3 space-y-4">
                        {message.role === "assistant" && message.pending && !message.streaming ? (
                          <ThinkingCard
                            stepIndex={thinkingStepIndex}
                            streamState={streamState}
                            promptLanguage={localeForText(pendingPrompt ?? message.body)}
                          />
                        ) : message.role === "assistant"
                          ? assistantBlocks(message.body).map((block, index) =>
                              renderAssistantBlock(block, `${message.id}-block-${index}`),
                            )
                          : (
                            <p className="whitespace-pre-wrap text-sm leading-7 text-white">
                              {message.body}
                            </p>
                          )}
                        {message.mediaResult ? (
                          <div className="space-y-3 rounded-[20px] border border-white/8 bg-black/20 p-3">
                            {message.mediaResult.kind === "video" ? (
                              <video
                                src={message.mediaResult.previewUrl}
                                controls
                                autoPlay
                                loop
                                muted
                                className="block h-auto w-full rounded-[16px]"
                              />
                            ) : (
                              <img
                                src={message.mediaResult.previewUrl}
                                alt="Generated media preview"
                                className="block h-auto w-full rounded-[16px]"
                              />
                            )}
                            <div className="flex flex-wrap gap-2">
                              <Badge variant="info" size="xs">
                                {message.mediaResult.templateId}
                              </Badge>
                              <Badge variant={message.mediaResult.kind === "video" ? "success" : "info"} size="xs">
                                {message.mediaResult.kind}
                              </Badge>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                variant="secondary"
                                leftIcon={<Download className="h-4 w-4" />}
                                onClick={async () => {
                                  const blob = await mediaApi.downloadAssetBlob(message.mediaResult!.fileName);
                                  downloadBlob(blob, message.mediaResult!.fileName);
                                }}
                              >
                                {translateText("Download")}
                              </Button>
                              {message.mediaResult.canGenerateAnimation && !message.mediaResult.animationGenerated ? (
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  leftIcon={<Wand2 className="h-4 w-4" />}
                                  onClick={() => void handleGenerateAssistantAnimation(message.id, message.mediaResult!)}
                                >
                                  {translateText("Generate animation now")}
                                </Button>
                              ) : null}
                              <Button
                                size="sm"
                                variant="secondary"
                                leftIcon={<Sparkles className="h-4 w-4" />}
                                onClick={() => void handleSaveAssistantPreset(message.id, message.mediaResult!)}
                                disabled={Boolean(message.mediaResult.savedPresetName)}
                              >
                                {translateText(message.mediaResult.savedPresetName ? "Saved to presets" : "Save as team preset")}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                leftIcon={message.mediaResult.kind === "video" ? <Wand2 className="h-4 w-4" /> : <ImageIcon className="h-4 w-4" />}
                                onClick={() => navigate("/bos/media")}
                              >
                                {translateText("Open Media Studio")}
                              </Button>
                            </div>
                          </div>
                        ) : null}
                        {message.structuredResult ? (
                          <StructuredAssistantResultCard
                            result={message.structuredResult}
                            onNavigate={(to) => navigate(to)}
                          />
                        ) : null}
                      </div>
                      {message.createdAt ? (
                        <p className="assistant-message-timestamp mt-3 text-[11px] text-surface-500">
                          {formatDateTime(message.createdAt)}
                        </p>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <div className="assistant-idle-stage assistant-idle-command rounded-[28px] p-8 sm:p-10">
                    <div className="assistant-idle-network" />
                    <div className="relative z-[1] mx-auto mt-1 max-w-2xl">
                      <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/6 px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-surface-400">
                        <span className="assistant-stream-cursor" />
                        <span>{translateText("BOS Assistant")}</span>
                      </div>
                      <p className="mt-6 text-lg font-semibold text-white">{translateText("BOS is here.")}</p>
                      <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-surface-300">
                        {translateText("Start with a direct ask. The best openings are plainspoken, grounded, and slightly more thoughtful than urgent.")}
                      </p>
                    </div>
                  </div>
                )}
                    <div ref={threadEndRef} />
                  </div>
                  {!shouldAutoFollowThread && visibleThreadMessages.length ? (
                    <div className="mt-4 flex justify-end">
                      <Button
                        size="sm"
                        className="assistant-jump-latest"
                        rightIcon={<ArrowRight className="h-4 w-4" />}
                        onClick={jumpToLatest}
                      >
                        {translateText("Jump to latest")}
                      </Button>
                    </div>
                  ) : null}
              </div>

              <div className="assistant-aside-card assistant-composer-shell assistant-composer-surface rounded-[28px] p-4">
                <div className="assistant-composer-header flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="assistant-section-kicker assistant-thread-rail-label">
                    {translateText("Compose")}
                  </p>
                  <div className="flex w-full flex-col gap-3 sm:w-auto sm:min-w-[18rem]">
                    <Select
                      aria-label={translateText("Assistant model")}
                      value={selectedAssistantModel}
                      options={assistantModelOptions}
                      onChange={(event) => setAssistantModelPreference(event.target.value)}
                      className="min-w-[14rem]"
                      helperText="BOS APIs stay on; only the team model changes."
                    />
                  </div>
                </div>
                <Textarea
                  ref={composerRef}
                  label="Message BOS"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  onKeyDown={handlePromptKeyDown}
                  placeholder="Ask BOS what matters, what changed, or what should happen next."
                  autoResize
                  className="assistant-composer-input mt-4 min-h-[7rem] border-0 bg-transparent px-0 py-0 text-[0.98rem] leading-8 focus:ring-0"
                />
                  <div className="assistant-composer-footer mt-4 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-3 text-xs text-surface-500">
                    <span className="assistant-runtime-pill inline-flex items-center gap-2">
                      <span className="h-1.5 w-1.5 rounded-full bg-brand-300" />
                      {translateText(`Team pool · ${selectedAssistantModel}`)}
                    </span>
                    {streamState === "streaming" ? (
                      <span className="assistant-runtime-pill inline-flex items-center gap-2 text-brand-200">
                        <span className="assistant-stream-cursor" />
                        {translateText("BOS is arriving in real time")}
                      </span>
                    ) : null}
                    {streamState === "stopped" ? (
                      <span className="assistant-runtime-pill inline-flex items-center gap-2 text-amber-200">
                        <span className="h-1.5 w-1.5 rounded-full bg-amber-300" />
                        {translateText(streamStatusDetail ?? "Generation stopped")}
                      </span>
                    ) : null}
                    {streamState === "failed" ? (
                      <span className="assistant-runtime-pill inline-flex items-center gap-2 text-red-200">
                        <span className="h-1.5 w-1.5 rounded-full bg-red-300" />
                        {translateText(streamStatusDetail ?? "Stream interrupted")}
                      </span>
                    ) : null}
                  </div>
                  <div className="assistant-composer-actions flex items-center gap-3">
                    <p className="assistant-composer-hint text-[11px] text-surface-500">
                      {translateText("Enter to continue, Shift+Enter for a quieter line break")}
                    </p>
                    {pendingPrompt ? (
                      <Button
                        variant="secondary"
                        className="assistant-composer-action"
                        onClick={() => void handleStopGenerating()}
                      >
                        {translateText("Stop")}
                      </Button>
                    ) : (
                      <Button
                        className="assistant-composer-action assistant-composer-action-primary"
                        rightIcon={<SendHorizontal className="h-4 w-4" />}
                        onClick={() => void handleSubmit()}
                        disabled={!prompt.trim() || !sessionId || !accessToken || Boolean(pendingPrompt)}
                      >
                        {translateText("Continue")}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
        </div>

      </div>
    </div>
  );
}
