import { describe, expect, it, vi } from "vitest";

import { createBosGraphContext, runBosGraph, runBosGraphWithFallback } from "@/lib/bosGraph";
import type { BosGraphApiClients } from "@/lib/bosGraph";
import type { Batch } from "@/types/batch";
import type { ReleaseDecision, SignalBatch, SignalCompileResponse } from "@/types/bos";

const batch: Batch = {
  id: 12,
  batch_id: "BATCH-12",
  species: "BSF",
  substrate: "bran",
  status: "active",
  dm_in: 10,
  dm_out: 8,
  n_in: null,
  n_larvae: null,
  n_frass: null,
  ash_in: null,
  ash_out: null,
  fat_in: null,
  fat_out: null,
  temperature: 28,
  moisture: 68,
  feed_rate: null,
  density: null,
  score: 0.07,
  operator: null,
  notes: null,
  batch_date: null,
  created_at: "2026-04-23T00:00:00Z",
  updated_at: "2026-04-23T01:00:00Z",
  ser_value: 0.07,
};

const comparisonBatch: Batch = {
  ...batch,
  id: 13,
  batch_id: "BATCH-13",
  status: "completed",
  score: 0.13,
  ser_value: 0.13,
  updated_at: "2026-04-23T02:00:00Z",
};

const signal: SignalBatch = {
  id: 44,
  batch_id: 12,
  user_id: 1,
  tenant_id: 1,
  signal_api_version: "SIG-1.0",
  compiled_signal_id: "SIG-44",
  potency: 0.72,
  potency_unit: "SER",
  potency_basis: null,
  dose_window_min: null,
  dose_window_max: null,
  stability_window_hours: 12,
  kernel_residence_time_hours: null,
  handover_time: null,
  freshness_state: "Fresh",
  qc_markers: null,
  notes: null,
  released_at: null,
  expires_at: null,
  created_at: "2026-04-23T00:00:00Z",
  updated_at: "2026-04-23T01:00:00Z",
};

const releaseDecision: ReleaseDecision = {
  id: 99,
  batch_id: 12,
  signal_batch_id: 44,
  boundary_ledger_id: null,
  control_profile_id: null,
  user_id: 1,
  tenant_id: 1,
  decision: "PASS",
  reason_codes: [],
  blocking_factors: [],
  warning_factors: ["monitor freshness"],
  passed_checks: ["signal fresh"],
  trigger_metrics: {},
  decision_confidence: 0.91,
  approver: "BOS policy engine",
  rationale: "Signal posture is release-ready.",
  decision_time: "2026-04-23T01:30:00Z",
  created_at: "2026-04-23T01:30:00Z",
};

function createApi(overrides: Partial<BosGraphApiClients> = {}): BosGraphApiClients {
  const base: BosGraphApiClients = {
    batch: {
      list: vi.fn(async () => ({
        items: [batch, comparisonBatch],
        total: 2,
        page: 1,
        page_size: 10,
        total_pages: 1,
      })),
      get: vi.fn(async (id: number) => ({
        ...batch,
        id,
        batch_id: `BATCH-${id}`,
      })),
    },
    bos: {
      listSignals: vi.fn(async () => [signal]),
      listAuditPackets: vi.fn(async () => []),
      getBatchGuidance: vi.fn(async () => ({
        batch_id: 12,
        gap_items: [],
        recommended_actions: ["Keep monitoring"],
      })),
      compileSignal: vi.fn(async (): Promise<SignalCompileResponse> => ({
        ...signal,
        compile_status: "compiled",
        source_mode: "batch",
      })),
      refreshSignal: vi.fn(async () => ({
        signal_batch: signal,
        refreshed_state: "Fresh",
        metering_age_hours: 1,
        freshness_score: 0.9,
        release_readiness_score: 0.88,
      })),
      evaluateRelease: vi.fn(async () => releaseDecision),
      exportAuditPacket: vi.fn(async () => new Blob(["audit"])),
      evaluateSupervisor: vi.fn(async () => ({
        id: 1,
        signal_batch_id: 44,
        c_signal_hat: 0.7,
        dc_dt_hat: 0.02,
        confidence: 0.85,
        observed_at: "2026-04-23T01:00:00Z",
        missing_channels: [],
        channels_used: ["uv254"],
        information_loss: 0.1,
        observability_score: 0.9,
        negative_slope_streak: 0,
        trigger_reason: null,
        expected_handover: null,
        mechanistic_context: null,
      })),
      getHandoverRecommendation: vi.fn(async () => ({
        signal_batch_id: 44,
        recommended_handover: false,
        trigger_reason: "monitor_signal",
        expected_freshness_window_hours: 6,
        c_signal_hat: 0.7,
        dc_dt_hat: 0.02,
        confidence: 0.85,
        expected_handover: null,
        confidence_threshold: 0.8,
        negative_slope_persistence: 3,
        observability_required: true,
        missing_channels: [],
        channels_used: ["uv254"],
        information_loss: 0.1,
        observability_score: 0.9,
        mechanistic_context: null,
      })),
      listReleaseDecisions: vi.fn(async () => [releaseDecision]),
      getBrainRuntime: vi.fn(async () => ({
        root_path: ".agents/runtime",
        documents: [],
        total_line_count: 0,
        last_updated_at: null,
      })),
    },
    dashboard: {
      summary: vi.fn(async () => ({
        total_batches: 1,
        active_batches: 1,
        completed_batches: 0,
        avg_ser: 0.07,
        avg_pass_rate: 0.9,
        total_twins: 0,
        batches_this_week: 1,
        ser_improvement_pct: null,
      })),
    },
    twin: {
      list: vi.fn(async () => ({
        items: [],
        total: 0,
        page: 1,
        page_size: 10,
        total_pages: 0,
      })),
    },
  };

  return {
    ...base,
    ...overrides,
    batch: {
      ...base.batch,
      ...overrides.batch,
    },
    bos: {
      ...base.bos,
      ...overrides.bos,
    },
    dashboard: {
      ...base.dashboard,
      ...overrides.dashboard,
    },
    twin: {
      ...base.twin,
      ...overrides.twin,
    },
  };
}

function createContext(graphName: Parameters<typeof createBosGraphContext>[0]["graphName"], message: string, api = createApi()) {
  return createBosGraphContext({
    graphName,
    intent:
      graphName === "batch_triage_graph"
        ? "batch_guidance"
        : graphName === "release_review_graph"
          ? "evaluate_release"
          : "compile_signal",
    message,
    apiClients: api,
    queryClient: { invalidateQueries: vi.fn(async () => undefined) },
    sessionId: 1,
    userRole: "operator",
  });
}

describe("bosGraph runner", () => {
  it("runs the batch triage graph for batch guidance", async () => {
    const context = createContext("batch_triage_graph", "batch guidance 12");

    const result = await runBosGraph("batch_triage_graph", context);

    expect(result.status).toBe("completed");
    expect(result.structuredResult.title).toContain("Batch guidance");
  });

  it("runs every batch triage graph entry intent", async () => {
    const cases = [
      ["riskiest_batch", "Highest-risk batch"],
      ["batch_analysis", "Batch analysis"],
      ["batch_guidance", "Batch guidance"],
      ["batch_compare", "Latest batch comparison"],
    ] as const;

    for (const [intent, expectedTitle] of cases) {
      const context = createContext("batch_triage_graph", `${intent} 12`);
      context.intent = intent;

      const result = await runBosGraph("batch_triage_graph", context);

      expect(result.status).toBe("completed");
      expect(result.structuredResult.title).toContain(expectedTitle);
    }
  });

  it("runs the release review graph for release evaluation", async () => {
    const context = createContext("release_review_graph", "evaluate release 12");

    const result = await runBosGraph("release_review_graph", context);

    expect(result.status).toBe("completed");
    expect(result.structuredResult.title).toBe("Release evaluation completed");
  });

  it("runs the release review graph for executive summary", async () => {
    const context = createContext("release_review_graph", "executive summary");
    context.intent = "executive_summary";

    const result = await runBosGraph("release_review_graph", context);

    expect(result.status).toBe("completed");
    expect(result.structuredResult.title).toBe("Executive BOS summary");
  });

  it("runs every release review graph entry intent", async () => {
    const downloadBlob = vi.fn();
    const cases = [
      ["executive_summary", "Executive BOS summary"],
      ["release_summary", "Release summary"],
      ["release_risks", "Release risks"],
      ["evaluate_release", "Release evaluation completed"],
      ["export_audit_packet", "Audit packet exported"],
    ] as const;

    for (const [intent, expectedTitle] of cases) {
      const context = createContext("release_review_graph", `${intent} 12`);
      context.intent = intent;
      context.effects = { downloadBlob };

      const result = await runBosGraph("release_review_graph", context);

      expect(result.status).toBe("completed");
      expect(result.structuredResult.title).toBe(expectedTitle);
    }
    expect(downloadBlob).toHaveBeenCalledOnce();
  });

  it("runs the signal runtime graph for signal compilation", async () => {
    const context = createContext("signal_runtime_graph", "compile signal 12");

    const result = await runBosGraph("signal_runtime_graph", context);

    expect(result.status).toBe("completed");
    expect(result.structuredResult.title).toBe("Signal compiled");
  });

  it("runs every signal runtime graph entry intent", async () => {
    const cases = [
      ["compile_signal", "Signal compiled"],
      ["refresh_signal", "Signal refreshed"],
      ["evaluate_supervisor", "Supervisor evaluation"],
      ["handover_recommendation", "Handover recommendation"],
    ] as const;

    for (const [intent, expectedTitle] of cases) {
      const context = createContext("signal_runtime_graph", `${intent} 12`);
      context.intent = intent;

      const result = await runBosGraph("signal_runtime_graph", context);

      expect(result.status).toBe("completed");
      expect(result.structuredResult.title).toBe(expectedTitle);
    }
  });

  it("returns a blocked graph result when batch resolution has no candidate", async () => {
    const context = createContext("signal_runtime_graph", "compile signal", createApi({
      batch: {
        list: vi.fn(async () => ({
          items: [],
          total: 0,
          page: 1,
          page_size: 1,
          total_pages: 0,
        })),
        get: vi.fn(async () => batch),
      },
    }));

    const result = await runBosGraph("signal_runtime_graph", context);

    expect(result.status).toBe("blocked");
    expect(result.structuredResult.title).toBe("No batch is available to compile");
  });

  it("falls back when graph execution fails", async () => {
    const api = createApi({
      bos: {
        ...createApi().bos,
        listReleaseDecisions: vi.fn(async () => {
          throw new Error("graph failed");
        }),
      },
    });
    const context = createContext("release_review_graph", "release summary", api);
    context.intent = "release_summary";

    const result = await runBosGraphWithFallback("release_review_graph", context, async () => ({
      status: "completed",
      body: "fallback body",
      structuredResult: { title: "Fallback result" },
    }));

    expect(result.usedFallback).toBe(true);
    expect(result.result.structuredResult.title).toBe("Fallback result");
  });
});
