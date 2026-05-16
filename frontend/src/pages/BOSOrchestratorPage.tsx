import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  Activity,
  ArrowRight,
  Beaker,
  CheckCircle2,
  ClipboardCheck,
  Download,
  ExternalLink,
  FlaskConical,
  GitBranch,
  Layers3,
  MessageSquareText,
  RefreshCcw,
  RadioTower,
  ShieldCheck,
  Sparkles,
  Wand2,
} from "lucide-react";

import { assistantApi } from "@/api/assistantApi";
import { batchApi } from "@/api/batchApi";
import { bosApi } from "@/api/bosApi";
import client from "@/api/client";
import { BrainOperatorContextCard } from "@/components/bos/BrainOperatorContextCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import { translateText } from "@/lib/i18n";
import { downloadBlob, formatDateTime } from "@/lib/utils";
import type { AssistantRunResponse } from "@/types/assistant";

const DEFAULT_ORCHESTRATOR_URL =
  import.meta.env.VITE_ASSISTANT_ORCHESTRATOR_URL ?? "http://127.0.0.1:4173";

interface NativeRecipePreset {
  id: string;
  title: string;
  batchId: number;
  createdAt: string;
}

interface NativeRecipeHistoryEntry {
  id: string;
  title: string;
  batchId: number;
  compiledSignalId: string | null;
  releaseDecision: string;
  guidanceSummary: string;
  createdAt: string;
}

const BUILT_IN_NATIVE_RECIPES = [
  {
    id: "signal-readiness",
    title: "Signal readiness",
    description: "Compile signal, fetch guidance, and evaluate release for the selected batch.",
  },
  {
    id: "guidance-sweep",
    title: "Guidance sweep",
    description: "Refresh batch guidance only, useful when operators need next actions first.",
  },
  {
    id: "release-posture",
    title: "Release posture",
    description: "Re-evaluate release posture for the currently selected batch.",
  },
] as const;

const RESEARCH_REVIEW_LANES = [
  "intake",
  "protocol",
  "mechanism",
  "evidence",
  "twin",
  "integrity",
  "scientific gate",
  "evidence audit",
  "synthesis",
] as const;

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function recordArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map(recordValue).filter((item) => Object.keys(item).length > 0) : [];
}

function auditValue(value: unknown, fallback = "pending") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function isResearchReviewRun(run: AssistantRunResponse) {
  const intent = recordValue(run.parsed_intent);
  const summary = recordValue(run.result_summary);
  return intent.mode === "research_review" || summary.mode === "research_review";
}

export default function BOSOrchestratorPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const orchestratorUrl = useMemo(() => DEFAULT_ORCHESTRATOR_URL, []);
  const [refreshKey, setRefreshKey] = useState(0);
  const [surfaceMode, setSurfaceMode] = useState<"native" | "embedded">("native");
  const [draftBatchId, setDraftBatchId] = useState("orch-batch");
  const [draftSpecies, setDraftSpecies] = useState("BSF");
  const [draftDmIn, setDraftDmIn] = useState("10");
  const [draftDmOut, setDraftDmOut] = useState("4");
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [nativeRecipeTitle, setNativeRecipeTitle] = useState("Signal readiness recipe");
  const [nativeRecipeResult, setNativeRecipeResult] = useState<{
    batchId: number;
    signal: Awaited<ReturnType<typeof bosApi.compileSignal>>;
    guidance: Awaited<ReturnType<typeof bosApi.getBatchGuidance>>;
    release: Awaited<ReturnType<typeof bosApi.evaluateRelease>>;
  } | null>(null);
  const [nativeRecipes, setNativeRecipes] = useLocalStorage<NativeRecipePreset[]>(
    "bos-native-orchestrator-recipes",
    [],
  );
  const [nativeRecipeHistory, setNativeRecipeHistory] = useLocalStorage<NativeRecipeHistoryEntry[]>(
    "bos-native-orchestrator-history",
    [],
  );

  const healthQuery = useQuery({
    queryKey: ["orchestrator", "health"],
    queryFn: async () => {
      const { data } = await client.get("/health/live");
      return data;
    },
  });

  const batchStatsQuery = useQuery({
    queryKey: ["orchestrator", "batch-stats"],
    queryFn: () => batchApi.stats(),
  });

  const recentBatchesQuery = useQuery({
    queryKey: ["orchestrator", "recent-batches"],
    queryFn: () =>
      batchApi.list(1, 5, {
        sort_by: "created_at",
        sort_order: "desc",
      }),
  });

  const signalsQuery = useQuery({
    queryKey: ["orchestrator", "signals"],
    queryFn: () => bosApi.listSignals(),
  });

  const auditPacketsQuery = useQuery({
    queryKey: ["orchestrator", "audit-packets"],
    queryFn: () => bosApi.listAuditPackets(),
  });

  const assistantRunsQuery = useQuery({
    queryKey: ["orchestrator", "assistant-runs", refreshKey],
    queryFn: () => assistantApi.listRuns(20),
  });

  const batchGuidanceMutation = useMutation({
    mutationFn: (batchId: number) => bosApi.getBatchGuidance(batchId),
    onError: () => toast.error("Failed to load batch guidance"),
  });

  const releaseDecisionMutation = useMutation({
    mutationFn: (batchId: number) =>
      bosApi.evaluateRelease({
        batch_id: batchId,
        persist: true,
      }),
    onError: () => toast.error("Failed to evaluate release"),
  });

  const compileSignalMutation = useMutation({
    mutationFn: (batchId: number) =>
      bosApi.compileSignal({
        batch_id: batchId,
      }),
    onSuccess: async () => {
      toast.success("Signal compiled");
      await signalsQuery.refetch();
    },
    onError: () => toast.error("Failed to compile signal"),
  });

  const exportAuditPacketMutation = useMutation({
    mutationFn: async ({ batchId, format }: { batchId: number; format: "md" | "json" }) => {
      const blob = await bosApi.exportAuditPacket(batchId, format);
      return { blob, batchId, format };
    },
    onSuccess: ({ blob, batchId, format }) => {
      downloadBlob(blob, `audit_packet_batch_${batchId}.${format}`);
      toast.success(`Exported audit packet (${format})`);
    },
    onError: () => toast.error("Failed to export audit packet"),
  });

  const nativeRecipeMutation = useMutation({
    mutationFn: async (batchId: number) => {
      const signal = await bosApi.compileSignal({ batch_id: batchId });
      const guidance = await bosApi.getBatchGuidance(batchId);
      const release = await bosApi.evaluateRelease({ batch_id: batchId, persist: true });
      return { batchId, signal, guidance, release };
    },
    onSuccess: async (result) => {
      setNativeRecipeResult(result);
      setNativeRecipeHistory((current) => [
        {
          id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
          title: nativeRecipeTitle,
          batchId: result.batchId,
          compiledSignalId: result.signal.compiled_signal_id,
          releaseDecision: result.release.decision,
          guidanceSummary: result.guidance.recommended_actions[0] ?? "Guidance ready",
          createdAt: new Date().toISOString(),
        },
        ...current,
      ].slice(0, 8));
      toast.success("Native orchestration recipe completed");
      await Promise.all([signalsQuery.refetch(), auditPacketsQuery.refetch()]);
    },
    onError: () => toast.error("Native orchestration recipe failed"),
  });

  const createBatchMutation = useMutation({
    mutationFn: () =>
      batchApi.create({
        batch_id: draftBatchId,
        species: draftSpecies,
        dm_in: Number(draftDmIn),
        dm_out: Number(draftDmOut),
      }),
    onSuccess: async (batch) => {
      toast.success(`Created batch ${batch.batch_id}`);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["orchestrator", "batch-stats"] }),
        queryClient.invalidateQueries({ queryKey: ["orchestrator", "recent-batches"] }),
        queryClient.invalidateQueries({ queryKey: ["orchestrator", "audit-packets"] }),
      ]);
    },
    onError: () => {
      toast.error("Failed to create batch");
    },
  });

  const totalBatches = batchStatsQuery.data?.total ?? 0;
  const activeBatches = batchStatsQuery.data?.by_status?.active ?? 0;
  const completedBatches = batchStatsQuery.data?.by_status?.completed ?? 0;
  const signalCount = signalsQuery.data?.length ?? 0;
  const auditPacketCount = auditPacketsQuery.data?.length ?? 0;
  const researchReviewRuns = (assistantRunsQuery.data ?? []).filter(isResearchReviewRun);
  const latestResearchReviewRun = researchReviewRuns[0] ?? null;
  const latestResearchSummary = recordValue(latestResearchReviewRun?.result_summary);
  const latestResearchFinal = recordValue(latestResearchReviewRun?.final_synthesis ?? latestResearchSummary.final_synthesis);
  const latestResearchTeamPlan = latestResearchReviewRun?.team_plan?.length
    ? latestResearchReviewRun.team_plan
    : recordArray(latestResearchSummary.team_plan);
  const latestResearchVerdicts = latestResearchReviewRun?.review_verdicts?.length
    ? latestResearchReviewRun.review_verdicts
    : recordArray(latestResearchSummary.review_verdicts);
  const latestResearchActions = latestResearchReviewRun?.action_ledger?.length
    ? latestResearchReviewRun.action_ledger
    : recordArray(latestResearchSummary.action_ledger);
  const latestResearchHandoffs = latestResearchReviewRun?.handoff_records?.length
    ? latestResearchReviewRun.handoff_records
    : recordArray(latestResearchSummary.handoff_records);
  const latestResearchResultIds = recordValue(latestResearchSummary.result_ids);
  const latestResearchHumanQueue = recordValue(latestResearchSummary.human_review_queue);
  const latestResearchDebateTurns = recordArray(latestResearchFinal.debate_turns);
  const latestResearchReasoningStages = recordArray(latestResearchFinal.reasoning_stages);
  const latestResearchEvidenceStatus = recordArray(latestResearchFinal.evidence_status);
  const latestResearchExperimentPlan = recordArray(latestResearchFinal.experiment_plan);
  const latestResearchTopic = auditValue(latestResearchFinal.topic ?? latestResearchReviewRun?.user_message, "No topic captured");
  const latestResearchReviewPacketId =
    latestResearchFinal.review_packet_snapshot_id ??
    latestResearchResultIds.review_packet_snapshot_id ??
    latestResearchHumanQueue.source_review_packet_id ??
    "pending";
  const latestResearchEvidencePackId =
    latestResearchReviewRun?.evidence_pack_id ??
    latestResearchResultIds.evidence_pack_id ??
    latestResearchHumanQueue.evidence_pack_id ??
    "pending";
  const latestResearchGate = String(latestResearchFinal.approval_state ?? "review_required");
  const latestResearchLedgerSummary = `${latestResearchActions.length} actions`;
  const latestResearchTraceSummary = `${latestResearchHandoffs.length} handoffs / ${latestResearchVerdicts.length} verdicts`;
  const latestResearchDebatePreview = latestResearchDebateTurns.length
    ? latestResearchDebateTurns.slice(0, 3)
    : [{ speaker: "Synthesis", stance: "No debate turns captured yet.", challenges: "Use the specialist cards below." }];
  const latestResearchReasoningPreview = latestResearchReasoningStages.length
    ? latestResearchReasoningStages
    : [{ stage: "Gate posture", status: "review_required", readout: "Reasoning timeline not captured yet." }];
  const latestResearchEvidencePreview = latestResearchEvidenceStatus.length
    ? latestResearchEvidenceStatus
    : [{ claim: "Candidate evidence", status: "candidate_evidence", gate: "review_required", basis: "No evidence matrix captured yet." }];
  const latestResearchExperimentPreview = latestResearchExperimentPlan.length
    ? latestResearchExperimentPlan
    : [{ step: "Review-gated pilot", design: "No pilot plan captured yet.", gate: "review_required", stop_rule: "Human review required." }];
  const batchOptions = recentBatchesQuery.data?.items ?? [];
  const hasBatchOptions = batchOptions.length > 0;
  const effectiveBatchId = selectedBatchId ?? batchOptions[0]?.id ?? null;
  const selectedBatchLabel =
    batchOptions.find((batch) => batch.id === effectiveBatchId)?.batch_id ??
    (effectiveBatchId ? `Batch ${effectiveBatchId}` : "No batch selected");
  const latestAuditPacket =
    (auditPacketsQuery.data ?? []).find((packet) => packet.batch_id === effectiveBatchId) ??
    (auditPacketsQuery.data ?? [])[0] ??
    null;

  const saveNativeRecipePreset = () => {
    if (!effectiveBatchId) {
      toast.error("Select a batch first");
      return;
    }
    const title = nativeRecipeTitle.trim() || `Recipe ${selectedBatchLabel}`;
    setNativeRecipes((current) => [
      {
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        title,
        batchId: effectiveBatchId,
        createdAt: new Date().toISOString(),
      },
      ...current.filter((item) => !(item.batchId === effectiveBatchId && item.title === title)),
    ].slice(0, 6));
    toast.success("Native recipe saved");
  };

  const runSavedNativeRecipe = (recipe: NativeRecipePreset) => {
    setSelectedBatchId(recipe.batchId);
    setNativeRecipeTitle(recipe.title);
    nativeRecipeMutation.mutate(recipe.batchId);
  };

  const removeSavedNativeRecipe = (recipeId: string) => {
    setNativeRecipes((current) => current.filter((recipe) => recipe.id !== recipeId));
  };

  const nativeControlRoom = (
    <section className="orchestrator-control-shell overflow-hidden rounded-[26px] border border-white/8 px-5 py-5 shadow-card md:px-6 md:py-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="success" className="border border-white/10 bg-white/5 text-white">
              Live API
            </Badge>
            <Badge variant="warning">review_required</Badge>
          </div>
          <h2 className="mt-4 text-2xl font-semibold tracking-tight text-white">
            Native Control Room
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-7 text-surface-400">
            Main-shell actions stay review-gated: compile, guidance, release evaluation, and audit export only.
          </p>
        </div>
        <div className="orchestrator-control-status">
          <div>
            <p className="text-[10px] uppercase tracking-[0.24em] text-surface-500">Service</p>
            <p className="mt-1 text-sm font-semibold text-white">{healthQuery.data?.status ?? "loading"}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.24em] text-surface-500">Signals</p>
            <p className="mt-1 text-sm font-semibold text-white">{signalCount}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.24em] text-surface-500">Packets</p>
            <p className="mt-1 text-sm font-semibold text-white">{auditPacketCount}</p>
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
        <div className="orchestrator-command-panel">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-surface-500">Active lane</p>
              <h3 className="mt-2 text-xl font-semibold text-white">Review-gated operating lane</h3>
              <p className="mt-2 text-sm leading-6 text-surface-400">
                {hasBatchOptions
                  ? `${selectedBatchLabel} keeps the release gate at review_required.`
                  : "Create or select a batch before running compile, guidance, release, or audit export."}
              </p>
            </div>
            <label className="grid min-w-0 gap-2 lg:min-w-[17rem]">
              <span className="text-xs uppercase tracking-[0.22em] text-surface-500">Target batch</span>
              <select
                value={effectiveBatchId ?? ""}
                onChange={(event) => setSelectedBatchId(event.target.value ? Number(event.target.value) : null)}
                className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white"
              >
                {!hasBatchOptions ? (
                  <option value="">No batch available</option>
                ) : null}
                {batchOptions.map((batch) => (
                  <option key={batch.id} value={batch.id}>
                    {batch.batch_id} 路 {batch.status}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {!hasBatchOptions ? (
            <div className="orchestrator-empty-guide mt-5">
              <div>
                <p className="text-sm font-semibold text-white">No native batch is ready yet</p>
                <p className="mt-1 text-xs leading-6 text-surface-400">
                  Create a batch below to unlock the operating lane. The release posture remains review_required and human-gated.
                </p>
              </div>
              <Badge variant="warning">review_required</Badge>
            </div>
          ) : null}

          <div className="orchestrator-sequence-rail mt-5">
            <div className="orchestrator-sequence-step">
              <RadioTower className="h-4 w-4" />
              <span>Compile</span>
              <small>signal only</small>
            </div>
            <div className="orchestrator-sequence-step">
              <Sparkles className="h-4 w-4" />
              <span>Guidance</span>
              <small>operator review</small>
            </div>
            <div className="orchestrator-sequence-step">
              <Activity className="h-4 w-4" />
              <span>Release review</span>
              <small>review_required</small>
            </div>
            <div className="orchestrator-sequence-step">
              <Download className="h-4 w-4" />
              <span>Audit packet</span>
              <small>export only</small>
            </div>
          </div>

          <div className="mt-5 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <Input
              label="Recipe title"
              value={nativeRecipeTitle}
              onChange={(event) => setNativeRecipeTitle(event.target.value)}
            />
            <Button
              className="h-12"
              leftIcon={<Wand2 className="h-4 w-4" />}
              onClick={() => effectiveBatchId && nativeRecipeMutation.mutate(effectiveBatchId)}
              loading={nativeRecipeMutation.isPending}
              disabled={!effectiveBatchId}
            >
              Run native recipe
            </Button>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <button
              type="button"
              onClick={() => effectiveBatchId && compileSignalMutation.mutate(effectiveBatchId)}
              disabled={!effectiveBatchId || compileSignalMutation.isPending}
              className="orchestrator-action-tile"
            >
              <RadioTower className="h-4 w-4" />
              <span>Compile signal</span>
            </button>
            <button
              type="button"
              onClick={() => effectiveBatchId && batchGuidanceMutation.mutate(effectiveBatchId)}
              disabled={!effectiveBatchId || batchGuidanceMutation.isPending}
              className="orchestrator-action-tile"
            >
              <Sparkles className="h-4 w-4" />
              <span>Get guidance</span>
            </button>
            <button
              type="button"
              onClick={() => effectiveBatchId && releaseDecisionMutation.mutate(effectiveBatchId)}
              disabled={!effectiveBatchId || releaseDecisionMutation.isPending}
              className="orchestrator-action-tile"
            >
              <Activity className="h-4 w-4" />
              <span>Evaluate release</span>
            </button>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              variant="secondary"
              leftIcon={<Sparkles className="h-4 w-4" />}
              onClick={saveNativeRecipePreset}
              disabled={!effectiveBatchId}
            >
              Save native recipe
            </Button>
            <Button
              variant="ghost"
              leftIcon={<ArrowRight className="h-4 w-4" />}
              onClick={() => navigate("/batches")}
            >
              Open batch command
            </Button>
            <Button
              variant="ghost"
              leftIcon={<ArrowRight className="h-4 w-4" />}
              onClick={() => navigate("/bos/console")}
            >
              Open decision console
            </Button>
          </div>

          {(batchGuidanceMutation.data || releaseDecisionMutation.data || compileSignalMutation.data) ? (
            <div className="mt-5 grid gap-3 lg:grid-cols-3">
              <div className="orchestrator-result-card">
                <p className="text-xs uppercase tracking-[0.22em] text-surface-500">Guidance</p>
                <p className="mt-2 text-sm font-semibold text-white">
                  {batchGuidanceMutation.data?.recommended_actions[0] ?? "Awaiting guidance"}
                </p>
                <p className="mt-1 text-xs text-surface-500">
                  {batchGuidanceMutation.data ? `${batchGuidanceMutation.data.gap_items.length} gap items` : "No guidance run"}
                </p>
              </div>

              <div className="orchestrator-result-card">
                <p className="text-xs uppercase tracking-[0.22em] text-surface-500">Release decision</p>
                <p className="mt-2 text-sm font-semibold text-white">
                  {releaseDecisionMutation.data?.decision ?? "review_required"}
                </p>
                <p className="mt-1 text-xs text-surface-500">
                  {releaseDecisionMutation.data?.reason_codes?.slice(0, 2).join(" 路 ") || "Human review stays required"}
                </p>
              </div>

              <div className="orchestrator-result-card">
                <p className="text-xs uppercase tracking-[0.22em] text-surface-500">Compiled signal</p>
                <p className="mt-2 text-sm font-semibold text-white">
                  {compileSignalMutation.data?.compiled_signal_id ?? "Awaiting signal"}
                </p>
                <p className="mt-1 text-xs text-surface-500">
                  {compileSignalMutation.data ? `${compileSignalMutation.data.compile_status} 路 ${compileSignalMutation.data.source_mode}` : "No compile run"}
                </p>
              </div>
            </div>
          ) : null}

          {nativeRecipeResult ? (
            <div className="orchestrator-result-band mt-5">
              <div className="flex items-center gap-3">
                <div className="rounded-2xl border border-brand-300/16 bg-brand-500/12 p-3">
                  <Wand2 className="h-5 w-5 text-brand-200" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">Native orchestration recipe completed</p>
                  <p className="text-xs text-surface-400">Batch {nativeRecipeResult?.batchId} 路 compile, guidance, release all refreshed</p>
                </div>
              </div>

              <div className="mt-4 grid gap-3 lg:grid-cols-3">
                <div className="orchestrator-result-card">
                  <p className="text-xs uppercase tracking-[0.22em] text-surface-500">Signal</p>
                  <p className="mt-2 text-sm font-semibold text-white">
                    {nativeRecipeResult?.signal.compiled_signal_id ?? "Compiled"}
                  </p>
                  <p className="mt-1 text-xs text-surface-400">
                    {nativeRecipeResult?.signal.compile_status} 路 {nativeRecipeResult?.signal.source_mode}
                  </p>
                </div>

                <div className="orchestrator-result-card">
                  <p className="text-xs uppercase tracking-[0.22em] text-surface-500">Guidance</p>
                  <p className="mt-2 text-sm font-semibold text-white">
                    {nativeRecipeResult?.guidance.recommended_actions[0] ?? "Guidance ready"}
                  </p>
                  <p className="mt-1 text-xs text-surface-400">
                    {nativeRecipeResult?.guidance.gap_items.length ?? 0} gaps identified
                  </p>
                </div>

                <div className="orchestrator-result-card">
                  <p className="text-xs uppercase tracking-[0.22em] text-surface-500">Release</p>
                  <p className="mt-2 text-sm font-semibold text-white">
                    {nativeRecipeResult?.release.decision}
                  </p>
                  <p className="mt-1 text-xs text-surface-400">
                    {(nativeRecipeResult?.release.reason_codes ?? []).slice(0, 2).join(" 路 ") || "No reason codes"}
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="space-y-3">
          <details className="orchestrator-control-details" open={!hasBatchOptions}>
            <summary>
              <span>Create batch directly</span>
              <Badge variant="neutral">New batch</Badge>
            </summary>
            <div className="mt-4 grid gap-3">
              <Input label="Batch ID" value={draftBatchId} onChange={(event) => setDraftBatchId(event.target.value)} />
              <Input label="Species" value={draftSpecies} onChange={(event) => setDraftSpecies(event.target.value)} />
              <div className="grid gap-3 sm:grid-cols-2">
                <Input label="DM In" type="number" value={draftDmIn} onChange={(event) => setDraftDmIn(event.target.value)} />
                <Input label="DM Out" type="number" value={draftDmOut} onChange={(event) => setDraftDmOut(event.target.value)} />
              </div>
              <Button
                leftIcon={<Beaker className="h-4 w-4" />}
                onClick={() => createBatchMutation.mutate()}
                loading={createBatchMutation.isPending}
              >
                Create batch
              </Button>
            </div>
          </details>

          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
            {BUILT_IN_NATIVE_RECIPES.map((recipe) => (
              <button
                key={recipe.id}
                type="button"
                onClick={() => {
                  setNativeRecipeTitle(recipe.title);
                  if (!effectiveBatchId) return;
                  if (recipe.id === "signal-readiness") {
                    nativeRecipeMutation.mutate(effectiveBatchId);
                    return;
                  }
                  if (recipe.id === "guidance-sweep") {
                    batchGuidanceMutation.mutate(effectiveBatchId);
                    return;
                  }
                  releaseDecisionMutation.mutate(effectiveBatchId);
                }}
                disabled={!effectiveBatchId}
                className="orchestrator-recipe-chip"
              >
                <span className="text-sm font-semibold text-white">{recipe.title}</span>
                <span className="mt-1 text-xs leading-5 text-surface-400">{recipe.description}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        <details className="orchestrator-control-details">
          <summary>
            <span>Recent batches</span>
            <Badge variant="neutral">{recentBatchesQuery.data?.items.length ?? 0}</Badge>
          </summary>
          <div className="mt-4 grid gap-3">
            {(recentBatchesQuery.data?.items ?? []).map((batch) => (
              <button
                key={batch.id}
                type="button"
                onClick={() => navigate(`/batches/${batch.id}`)}
                className="orchestrator-list-row"
              >
                <span>
                  <span className="block text-sm font-semibold text-white">{batch.batch_id}</span>
                  <span className="mt-1 block text-xs text-surface-400">{batch.species} 路 {batch.status}</span>
                </span>
                <ArrowRight className="h-4 w-4 text-brand-200" />
              </button>
            ))}
          </div>
        </details>

        <details className="orchestrator-control-details">
          <summary>
            <span>Signal batches</span>
            <Badge variant="neutral">{signalCount}</Badge>
          </summary>
          <div className="mt-4 grid gap-3">
            {(signalsQuery.data ?? []).slice(0, 5).map((signal) => (
              <div key={signal.id} className="orchestrator-list-row">
                <span>
                  <span className="block text-sm font-semibold text-white">Signal #{signal.id}</span>
                  <span className="mt-1 block text-xs text-surface-400">Batch {signal.batch_id} 路 {signal.signal_api_version}</span>
                </span>
                <span className="text-xs text-surface-500">{formatDateTime(signal.updated_at)}</span>
              </div>
            ))}
          </div>
        </details>

        <details className="orchestrator-control-details">
          <summary>
            <span>Audit packet export</span>
            <Badge variant="neutral">{auditPacketCount}</Badge>
          </summary>
          <div className="mt-4 space-y-4">
            <div className="orchestrator-result-card">
              <p className="text-sm font-semibold text-white">
                {latestAuditPacket ? `Batch ${latestAuditPacket.batch_id}` : "No packet yet"}
              </p>
              <p className="mt-1 text-xs text-surface-400">
                {latestAuditPacket ? formatDateTime(latestAuditPacket.generated_at) : "Run a native recipe or release evaluation first"}
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Button
                variant="secondary"
                leftIcon={<Download className="h-4 w-4" />}
                onClick={() => effectiveBatchId && exportAuditPacketMutation.mutate({ batchId: effectiveBatchId, format: "md" })}
                loading={exportAuditPacketMutation.isPending}
                disabled={!effectiveBatchId}
              >
                Export markdown
              </Button>
              <Button
                variant="secondary"
                leftIcon={<Download className="h-4 w-4" />}
                onClick={() => effectiveBatchId && exportAuditPacketMutation.mutate({ batchId: effectiveBatchId, format: "json" })}
                loading={exportAuditPacketMutation.isPending}
                disabled={!effectiveBatchId}
              >
                Export JSON
              </Button>
            </div>
          </div>
        </details>

        <details className="orchestrator-control-details">
          <summary>
            <span>Saved native recipes</span>
            <Badge variant="neutral">{nativeRecipes.length}</Badge>
          </summary>
          <div className="mt-4 space-y-3">
            {nativeRecipes.length ? (
              nativeRecipes.map((recipe) => (
                <div key={recipe.id} className="orchestrator-list-row">
                  <span>
                    <span className="block text-sm font-semibold text-white">{recipe.title}</span>
                    <span className="mt-1 block text-xs text-surface-400">
                      Target batch {recipe.batchId} 路 {formatDateTime(recipe.createdAt)}
                    </span>
                  </span>
                  <span className="flex gap-2">
                    <Button size="sm" variant="secondary" onClick={() => runSavedNativeRecipe(recipe)}>
                      Run
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => removeSavedNativeRecipe(recipe.id)}>
                      Remove
                    </Button>
                  </span>
                </div>
              ))
            ) : (
              <div className="orchestrator-result-card text-sm text-surface-400">
                No saved native recipes yet.
              </div>
            )}
          </div>
        </details>

        <details className="orchestrator-control-details lg:col-span-2">
          <summary>
            <span>Native recipe history</span>
            <Badge variant="neutral">{nativeRecipeHistory.length}</Badge>
          </summary>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {nativeRecipeHistory.length ? (
              nativeRecipeHistory.map((entry) => (
                <div key={entry.id} className="orchestrator-result-card">
                  <p className="text-sm font-semibold text-white">{entry.title}</p>
                  <p className="mt-1 text-xs text-surface-400">
                    Batch {entry.batchId} 路 {entry.releaseDecision} 路 {formatDateTime(entry.createdAt)}
                  </p>
                  <p className="mt-3 text-xs leading-6 text-surface-300">{entry.guidanceSummary}</p>
                  <p className="mt-2 text-xs text-surface-500">
                    {entry.compiledSignalId ?? "Compiled signal ready"}
                  </p>
                </div>
              ))
            ) : (
              <div className="orchestrator-result-card text-sm text-surface-400">
                No native recipe runs yet.
              </div>
            )}
          </div>
        </details>
      </div>

      <div className="orchestrator-guardrail-strip mt-5">
        <span className="orchestrator-guardrail-chip">review_required</span>
        <span className="orchestrator-guardrail-chip">no auto approval</span>
        <span className="orchestrator-guardrail-chip">no external share</span>
        <span className="orchestrator-guardrail-chip">no validated defaults write</span>
      </div>
    </section>
  );

  return (
    <div className="space-y-5">
      <section className="orchestrator-hero-shell overflow-hidden rounded-[26px] border border-white/8 px-5 py-5 shadow-card md:px-6 md:py-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="brand" dot>
                BOS Orchestrator
              </Badge>
              <Badge variant={latestResearchReviewRun ? "success" : "info"} dot>
                {latestResearchReviewRun ? translateText("Research Review Audit Console") : translateText("Waiting for run")}
              </Badge>
            </div>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white md:text-4xl">
              {translateText("Research partner cockpit")}
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-surface-300">
              {latestResearchReviewRun
                ? latestResearchTopic
                : translateText("Start from BOS Assistant; the orchestration layer will keep the research trail calm, review-gated, and packet-backed.")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant={surfaceMode === "native" ? "primary" : "secondary"}
              className="cold-control-pill"
              leftIcon={<Activity className="h-4 w-4" />}
              onClick={() => setSurfaceMode("native")}
            >
              Native control
            </Button>
            <Button
              variant={surfaceMode === "embedded" ? "primary" : "secondary"}
              className="cold-control-pill"
              leftIcon={<Wand2 className="h-4 w-4" />}
              onClick={() => setSurfaceMode("embedded")}
            >
              Embedded workspace
            </Button>
            <Button
              variant="secondary"
              className="cold-control-pill"
              leftIcon={<RefreshCcw className="h-4 w-4" />}
              onClick={() => {
                setRefreshKey((current) => current + 1);
                void Promise.all([
                  healthQuery.refetch(),
                  batchStatsQuery.refetch(),
                  recentBatchesQuery.refetch(),
                  signalsQuery.refetch(),
                  auditPacketsQuery.refetch(),
                  assistantRunsQuery.refetch(),
                ]);
              }}
            >
              Refresh
            </Button>
          </div>
        </div>

        <div className="orchestrator-glance-strip mt-5">
          {[
            { label: "Gate", value: latestResearchGate, hint: "review-gated", icon: ShieldCheck },
            { label: "Research reviews", value: researchReviewRuns.length, hint: "assistant runs", icon: MessageSquareText },
            { label: "Batches", value: totalBatches, hint: `${activeBatches} active / ${completedBatches} completed`, icon: Beaker },
            { label: "Signals", value: signalCount, hint: "live records", icon: RadioTower },
            { label: "Health", value: healthQuery.data?.status ?? "loading", hint: healthQuery.data?.environment ?? "waiting", icon: Activity },
          ].map((metric) => {
            const Icon = metric.icon;
            return (
              <div key={metric.label} className="orchestrator-glance">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-surface-400">
                    {translateText(metric.label)}
                  </p>
                  <Icon className="h-4 w-4 text-cyan-100/70" aria-hidden="true" />
                </div>
                <p className="mt-3 break-all text-base font-semibold leading-tight text-white">{metric.value}</p>
                <p className="mt-1 text-xs text-surface-500">{translateText(metric.hint)}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="orchestrator-research-shell overflow-hidden rounded-[26px] border border-white/8 p-4 shadow-card md:p-5">
        <div className="flex flex-col gap-3 border-b border-white/8 pb-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="cockpit-section-label">{translateText("Research Review Audit Console")}</p>
            <h2 className="mt-3 text-xl font-semibold tracking-tight text-white">
              {translateText("Research Review trace is review-gated and packet-backed")}
            </h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant={latestResearchReviewRun ? "success" : "info"} dot>
              {latestResearchReviewRun ? translateText("Audit trace live") : translateText("Waiting for run")}
            </Badge>
            <Badge variant="warning">{latestResearchGate}</Badge>
          </div>
        </div>

        {latestResearchReviewRun ? (
          <div className="mt-5 space-y-5">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.12fr)_minmax(320px,0.88fr)]">
              <div className="orchestrator-focus-pane">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="brand" size="xs">
                    {translateText("National lab audit posture")}
                  </Badge>
                  <Badge variant="neutral" size="xs">
                    Run ID {latestResearchReviewRun.run_id}
                  </Badge>
                </div>
                <p className="mt-4 text-sm leading-7 text-surface-200">{latestResearchTopic}</p>
                <div className="mt-5 grid gap-3 md:grid-cols-3">
                  {[
                    { label: "Gate", value: latestResearchGate, icon: ShieldCheck },
                    { label: "Packet", value: String(latestResearchReviewPacketId), icon: ClipboardCheck },
                    { label: "Evidence", value: String(latestResearchEvidencePackId), icon: Layers3 },
                  ].map((item) => {
                    const Icon = item.icon;
                    return (
                      <div key={item.label} className="orchestrator-token">
                        <Icon className="h-4 w-4 text-cyan-100/70" aria-hidden="true" />
                        <div className="min-w-0">
                          <p className="text-[10px] uppercase tracking-[0.16em] text-surface-500">
                            {translateText(item.label)}
                          </p>
                          <p className="mt-1 truncate text-xs font-semibold text-white">{item.value}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="orchestrator-side-pane">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-surface-400">
                  {translateText("Expert debate synthesis")}
                </p>
                <div className="mt-3 space-y-3">
                  {latestResearchDebatePreview.map((turn) => (
                    <div key={`${turn.speaker}-${turn.stance}`} className="orchestrator-debate-line">
                      <div className="mt-1 h-2 w-2 flex-shrink-0 rounded-full bg-cyan-200/80" />
                      <p className="text-xs leading-6 text-surface-300">
                        <span className="font-semibold text-white">{auditValue(turn.speaker, "Expert")}:</span>{" "}
                        {auditValue(turn.stance, "No stance recorded")}{" "}
                        <span className="text-surface-500">Challenge: {auditValue(turn.challenges, "No challenge recorded")}</span>
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="orchestrator-section">
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-cyan-100/70" aria-hidden="true" />
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-surface-400">
                  {translateText("Research reasoning timeline")}
                </p>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {latestResearchReasoningPreview.map((stage, index) => (
                  <div key={`${stage.stage}-${stage.status}`} className="orchestrator-step">
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full border border-cyan-100/20 bg-cyan-100/8 text-[11px] text-cyan-100">
                        {index + 1}
                      </span>
                      <Badge variant={auditValue(stage.status, "pending") === "review_required" ? "warning" : "success"} size="xs">
                        {auditValue(stage.status, "pending")}
                      </Badge>
                    </div>
                    <p className="mt-3 text-sm font-semibold text-white">{auditValue(stage.stage, "Stage")}</p>
                    <p className="mt-2 text-xs leading-6 text-surface-400">{auditValue(stage.readout, "No readout recorded")}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
              <div className="orchestrator-section">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-cyan-100/70" aria-hidden="true" />
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-surface-400">
                    {translateText("Evidence status matrix")}
                  </p>
                </div>
                <div className="mt-4 space-y-3">
                  {latestResearchEvidencePreview.map((evidence) => (
                    <div key={`${evidence.claim}-${evidence.status}`} className="orchestrator-evidence-row">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-white">{auditValue(evidence.claim, "Evidence claim")}</p>
                        <p className="mt-1 text-xs leading-5 text-surface-400">{auditValue(evidence.basis, "Basis pending")}</p>
                      </div>
                      <div className="flex flex-shrink-0 flex-col items-end gap-1">
                        <Badge variant="info" size="xs">{auditValue(evidence.status, "candidate_evidence")}</Badge>
                        <Badge variant="warning" size="xs">{auditValue(evidence.gate, "review_required")}</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="orchestrator-section">
                <div className="flex items-center gap-2">
                  <FlaskConical className="h-4 w-4 text-cyan-100/70" aria-hidden="true" />
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-surface-400">
                    {translateText("Controlled pilot plan")}
                  </p>
                </div>
                <div className="mt-4 grid gap-3 lg:grid-cols-3">
                  {latestResearchExperimentPreview.map((step) => (
                    <div key={String(step.step ?? step.design)} className="orchestrator-pilot-card">
                      <Badge variant="warning" size="xs">{auditValue(step.gate, "review_required")}</Badge>
                      <p className="mt-3 text-sm font-semibold text-white">{auditValue(step.step, "Pilot step")}</p>
                      <p className="mt-2 text-xs leading-6 text-surface-400">{auditValue(step.design, "Design pending")}</p>
                      <p className="mt-3 border-t border-white/8 pt-3 text-[11px] leading-5 text-surface-500">
                        Stop: {auditValue(step.stop_rule, "Stop rule pending")}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <details className="orchestrator-audit-details">
              <summary className="flex cursor-pointer items-center justify-between gap-3 text-sm font-semibold text-white">
                <span>{translateText("Packet / gate register")}</span>
                <span className="text-xs font-normal text-surface-500">{latestResearchLedgerSummary} 路 {latestResearchTraceSummary}</span>
              </summary>

              <div className="mt-4 grid gap-4 lg:grid-cols-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-surface-500">{translateText("Research Review DAG")}</p>
                  <div className="mt-3 grid gap-2">
                    {RESEARCH_REVIEW_LANES.map((lane, index) => (
                      <div key={lane} className="flex items-center gap-2 rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2">
                        <span className="text-[10px] text-cyan-100/70">S{index + 1}</span>
                        <span className="text-xs font-semibold text-white">{translateText(lane)}</span>
                        {index < RESEARCH_REVIEW_LANES.length - 1 ? <ArrowRight className="ml-auto h-3 w-3 text-surface-600" aria-hidden="true" /> : null}
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-surface-500">Specialist Registry</p>
                  <div className="mt-3 space-y-2">
                    {latestResearchTeamPlan.slice(0, 9).map((step) => (
                      <p key={String(step.specialist_id ?? step.stage)} className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-xs text-surface-300">
                        {String(step.stage ?? "?")}. {String(step.title ?? translateText("Specialist"))} 路 {String(step.specialist_id ?? "")}
                      </p>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-surface-500">Handoff Ledger</p>
                  <div className="mt-3 space-y-2">
                    {latestResearchHandoffs.slice(0, 9).map((handoff) => (
                      <p
                        key={String(handoff.handoff_id ?? `${handoff.source_specialist}-${handoff.target_specialist}`)}
                        className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-xs text-surface-300"
                      >
                        {String(handoff.source_specialist ?? "source")} -&gt; {String(handoff.target_specialist ?? "target")}:{" "}
                        {String(handoff.status ?? "recorded")}
                      </p>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-surface-500">Review Verdicts</p>
                  <div className="mt-3 space-y-2">
                    {latestResearchVerdicts.map((verdict) => (
                      <p key={String(verdict.gate ?? verdict.reviewer_id)} className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-xs text-surface-300">
                        {String(verdict.gate ?? "review_gate")}: {String(verdict.verdict ?? "review_required")}
                      </p>
                    ))}
                    <p className="pt-2 text-xs uppercase tracking-[0.2em] text-surface-500">Action Ledger</p>
                    {latestResearchActions.slice(0, 7).map((action) => (
                      <p key={String(action.action_name)} className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-xs text-surface-300">
                        {String(action.action_name ?? "action")}: {String(action.status ?? "pending")}
                      </p>
                    ))}
                  </div>
                </div>
              </div>
              <div className="mt-4 rounded-lg border border-white/8 bg-white/[0.03] px-3 py-3 text-xs text-surface-400">
                <p className="break-all">Source review packet: {String(latestResearchReviewPacketId)}</p>
                <p className="mt-1 break-all">Evidence pack: {String(latestResearchEvidencePackId)} / final decision: human_only</p>
                <Badge variant="info" size="xs" className="mt-3">
                  {translateText("Read-only packet identifier")}
                </Badge>
              </div>
            </details>
          </div>
        ) : (
          <div className="mt-5 flex flex-col gap-4 rounded-2xl border border-white/8 bg-white/[0.035] p-5 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-semibold text-white">No research_review run yet</p>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-surface-400">
                Start from BOS Assistant with a research protocol review request; this panel will show the registry, DAG lanes, verdicts, action ledger, and packet identifiers.
              </p>
            </div>
            <Button
              variant="secondary"
              className="cold-control-pill w-fit"
              leftIcon={<MessageSquareText className="h-4 w-4" />}
              onClick={() => navigate("/bos")}
            >
              Open Assistant
            </Button>
          </div>
        )}
      </section>

      <details className="orchestrator-audit-details orchestrator-context-wrap">
        <summary className="flex cursor-pointer items-center justify-between gap-3 text-sm font-semibold text-white">
          <span>{translateText("Autonomy orchestrator context")}</span>
          <span className="text-xs font-normal text-surface-500">{translateText("Project brain")}</span>
        </summary>
        <div className="mt-4">
          <BrainOperatorContextCard
            compact
            mode="orchestrator"
            title="Autonomy orchestrator context"
            description="What the project brain thinks should be orchestrated next across native recipes and assistant workflows."
          />
        </div>
      </details>

      {surfaceMode === "native" ? nativeControlRoom : (
        <Card className="rounded-[28px]">
          <CardHeader
            title="Embedded workflow workspace"
            description="Keep the full assistant-orchestrator workspace available while BOS is being migrated into the main shell."
            action={
              <Button
                variant="secondary"
                leftIcon={<ExternalLink className="h-4 w-4" />}
                onClick={() => window.open(orchestratorUrl, "_blank", "noopener,noreferrer")}
              >
                Open standalone
              </Button>
            }
          />
          <CardBody className="space-y-4">
            <div className="rounded-[24px] border border-white/10 bg-surface-950/70 p-2">
              <iframe
                key={refreshKey}
                src={orchestratorUrl}
                title="BOS Orchestrator"
                className="h-[78vh] w-full rounded-[20px] border-0 bg-surface-950"
              />
            </div>
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="rounded-[22px] border border-white/8 bg-white/5 p-4">
                <p className="text-sm font-semibold text-white">What lives here</p>
                <p className="mt-2 text-sm leading-7 text-surface-300">
                  Skills, workflow templates, field selectors, template import/export, and execution history.
                </p>
              </div>
              <div className="rounded-[22px] border border-white/8 bg-white/5 p-4">
                <p className="text-sm font-semibold text-white">Why dual mode exists</p>
                <p className="mt-2 text-sm leading-7 text-surface-300">
                  Native mode covers reconciled BOS actions now, while embedded mode keeps the full orchestration workspace available during migration.
                </p>
              </div>
              <div className="rounded-[22px] border border-white/8 bg-white/5 p-4">
                <p className="text-sm font-semibold text-white">If the panel is blank</p>
                <p className="mt-2 text-sm leading-7 text-surface-300">
                  Start the orchestrator frontend on port 4173, then click refresh or open the standalone workspace.
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
