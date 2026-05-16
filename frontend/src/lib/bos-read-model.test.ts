import { describe, expect, it } from "vitest";

import {
  sampleAuditPacket,
  sampleAuditPacketView,
} from "@/lib/bos-read-model.fixture";
import { getAuditPacketReadModel, getBatchBosReadModel, summarizeAuditPackets } from "@/lib/bos-read-model";
import type { AuditPacket, NativeModelRunArtifact } from "@/types/bos";
import type { Batch } from "@/types/batch";

describe("BOS read model contract", () => {
  it("prefers human-readable packet names over raw ids", () => {
    const view = getAuditPacketReadModel(sampleAuditPacket);

    expect(view.batchLabel).toBe("BOS-DEMO-042");
    expect(view.signalLabel).toBe("SIG-BOS-DEMO-042");
    expect(view.controlLabel).toBe("Default BOS Contract / CTRL-2.0");
    expect(view.portabilityAudits[0].executorLabel).toBe("Shanghai Executor");
    expect(view.portabilityAudits[0].localityLabel).toBe("Shanghai Site A");
    expect(view.portabilityAudits[0].recommendedOutcome).toBe("PASS_WITH_RETUNING");
    expect(view.portabilityAudits[0].retuningAxes).toEqual(["locality_shift"]);
    expect(view.portabilityAudits[0].portabilityScore).toBe(0.88);
  });

  it("preserves protocol metadata required by packet-driven pages", () => {
    expect(sampleAuditPacketView.packetVersion).toBe("AUD-2.0");
    expect(sampleAuditPacketView.schemaVersion).toBe("AUD-2.0");
    expect(sampleAuditPacketView.integrityHash).toHaveLength(64);
    expect(sampleAuditPacketView.passedChecks).toContain(
      "Potency meets or exceeds the minimum transfer threshold.",
    );
    expect(sampleAuditPacketView.mechanisticContext?.handover_envelope.tau_star_min).toBe(94.6);
    expect(sampleAuditPacketView.mechanisticContext?.c_di_ser.score).toBe(0.42);
    expect(sampleAuditPacketView.supervisorSnapshot?.mode).toBe("handover");
    expect(sampleAuditPacketView.supervisorHistory).toHaveLength(2);
  });

  it("extracts attached vision observations from signal validity", () => {
    const packet: AuditPacket = {
      ...sampleAuditPacket,
      signal_validity: {
        ...sampleAuditPacket.signal_validity,
        vision_observation: {
          image_id: "vision-read-model-001",
          detected_classes: ["larvae_cluster"],
          detections: [
            {
              label: "larvae_cluster",
              confidence: 0.91,
              bbox: [10, 20, 120, 160],
            },
          ],
          dominant_label: "larvae_cluster",
          confidence_mean: 0.91,
          anomaly_flag: false,
          observation_summary: "1 detection; dominant label larvae_cluster; mean confidence 0.91.",
          bbox_coverage_ratio: 0.24,
        },
      },
    };

    const view = getAuditPacketReadModel(packet);

    expect(view.visionObservation?.image_id).toBe("vision-read-model-001");
    expect(view.visionObservation?.dominant_label).toBe("larvae_cluster");
    expect(view.visionObservation?.confidence_mean).toBe(0.91);
  });

  it("summarizes packet feeds without re-deriving BOS semantics in the page", () => {
    const summary = summarizeAuditPackets([sampleAuditPacket]);

    expect(summary.summary.packets).toBe(1);
    expect(summary.summary.freshSignals).toBe(1);
    expect(summary.summary.passRate).toBe(1);
    expect(summary.portabilityAudits[0].signalLabel).toBe("SIG-BOS-DEMO-042");
    expect(summary.portabilityAudits[0].executorLabel).toBe("Shanghai Executor");
  });

  it("falls back to trigger metrics mechanistic context when signal validity omits it", () => {
    const packet: AuditPacket = {
      ...sampleAuditPacket,
      signal_validity: {
        ...sampleAuditPacket.signal_validity,
        mechanistic_context: undefined,
      },
      packet: {
        ...sampleAuditPacket.packet,
        release_decision: {
          ...sampleAuditPacket.packet.release_decision,
          trigger_metrics: {
            ...sampleAuditPacket.packet.release_decision.trigger_metrics,
            mechanistic_context: sampleAuditPacket.signal_validity?.mechanistic_context,
          },
        },
      },
    };

    const view = getAuditPacketReadModel(packet);

    expect(view.mechanisticContext?.c_di_ser.score).toBe(0.42);
    expect(view.mechanisticContext?.handover_envelope.tau_star_min).toBe(94.6);
  });

  it("prefers first-class release confidence when the packet exposes it", () => {
    const packet: AuditPacket = {
      ...sampleAuditPacket,
      packet: {
        ...sampleAuditPacket.packet,
        release_decision: {
          ...sampleAuditPacket.packet.release_decision,
          decision_confidence: 0.88,
          trigger_metrics: {
            potency: 0.24,
            mtt: 0.18,
          },
        },
      },
    };

    const view = getAuditPacketReadModel(packet);

    expect(view.decisionConfidence).toBe(0.88);
  });

  it("surfaces the latest native run summary in the batch read model", () => {
    const batch = {
      id: 42,
      batch_id: "BOS-DEMO-042",
      species: "BSF",
      status: "completed",
      dm_in: 10,
      dm_out: 4,
      n_in: 1,
      n_larvae: 0.5,
      n_frass: 0.3,
      ash_in: null,
      ash_out: null,
      fat_in: null,
      fat_out: null,
      temperature: 28,
      moisture: 66,
      feed_rate: 1.2,
      density: 4.1,
      score: null,
      operator: null,
      notes: null,
      batch_date: null,
      created_at: "2026-04-16T00:00:00Z",
      updated_at: "2026-04-16T00:00:00Z",
      bos: null,
    } satisfies Batch;

    const nativeRuns = [
      {
        model_key: "timer_s1",
        execution_mode: "bos_fallback_projection",
        recorded_at: "2026-04-16T00:00:00Z",
        artifact_path: "C:/tmp/runs/timer.json",
        payload_echo: {},
        result: {
          metric_name: "decomposition_rate",
          forecast: [0.41, 0.44, 0.48],
          forecast_preview: [0.41, 0.44, 0.48],
          prediction_horizon: 3,
          batch_context: { batch_id: 42 },
        },
        warnings: [],
      },
      {
        model_key: "chronos_bolt",
        execution_mode: "chronos_bolt_live",
        recorded_at: "2026-04-16T01:00:00Z",
        artifact_path: "C:/tmp/runs/chronos.json",
        payload_echo: {},
        result: {
          metric_name: "tray_temperature",
          forecast: [28.1, 28.0, 27.8],
          forecast_preview: [28.1, 28.0, 27.8],
          prediction_horizon: 3,
          batch_context: { batch_id: 42 },
        },
        warnings: [],
      },
    ] satisfies NativeModelRunArtifact[];

    const view = getBatchBosReadModel(batch, null, nativeRuns);

    expect(view.latestNativeRun?.modelKey).toBe("chronos_bolt");
    expect(view.latestNativeRun?.isLive).toBe(true);
    expect(view.latestNativeRun?.forecastPreview).toEqual(["28.1", "28", "27.8"]);
    expect(view.latestNativeRun?.evidenceSummary).toContain("tray_temperature");
  });

  it("prefers backend-provided latest native run summary when present", () => {
    const batch = {
      id: 42,
      batch_id: "BOS-DEMO-042",
      species: "BSF",
      status: "completed",
      dm_in: 10,
      dm_out: 4,
      n_in: 1,
      n_larvae: 0.5,
      n_frass: 0.3,
      ash_in: null,
      ash_out: null,
      fat_in: null,
      fat_out: null,
      temperature: 28,
      moisture: 66,
      feed_rate: 1.2,
      density: 4.1,
      score: null,
      operator: null,
      notes: null,
      batch_date: null,
      created_at: "2026-04-16T00:00:00Z",
      updated_at: "2026-04-16T00:00:00Z",
      bos: {
        signal_batch: null,
        control_profile: null,
        boundary_ledger: null,
        release_decision: null,
        audit_packet: null,
        portability_audits: [],
        compile_status: "not_started",
        latest_signal_status: "missing",
        latest_native_run: {
          modelKey: "chronos_bolt",
          modality: "time-series",
          evidenceTier: "stabilized_live_timeseries",
          evidenceLabel: "Stabilized live timeseries",
          executionMode: "chronos_bolt_live",
          recordedAt: "2026-04-16T01:00:00Z",
          artifactPath: "C:/tmp/runs/chronos.json",
          metricName: "tray_temperature",
          predictionHorizon: 3,
          forecastPreview: ["28.1", "28.0", "27.8"],
          isLive: true,
        },
      },
    } satisfies Batch;

    const view = getBatchBosReadModel(batch, null, []);

    expect(view.latestNativeRun?.modelKey).toBe("chronos_bolt");
    expect(view.latestNativeRun?.forecastPreview).toEqual(["28.1", "28.0", "27.8"]);
  });

  it("classifies insecta runs as bootstrap public vision when deriving locally", () => {
    const batch = {
      id: 42,
      batch_id: "BOS-DEMO-042",
      species: "BSF",
      status: "completed",
      dm_in: 10,
      dm_out: 4,
      n_in: 1,
      n_larvae: 0.5,
      n_frass: 0.3,
      ash_in: null,
      ash_out: null,
      fat_in: null,
      fat_out: null,
      temperature: 28,
      moisture: 66,
      feed_rate: 1.2,
      density: 4.1,
      score: null,
      operator: null,
      notes: null,
      batch_date: null,
      created_at: "2026-04-16T00:00:00Z",
      updated_at: "2026-04-16T00:00:00Z",
      bos: null,
    } satisfies Batch;

    const nativeRuns = [
      {
        model_key: "insecta",
        execution_mode: "insecta_bootstrap_live",
        recorded_at: "2026-04-16T02:00:00Z",
        artifact_path: "C:/tmp/runs/insecta.json",
        payload_echo: {},
        result: {
          detection_count: 3,
          top_label: "鞘翅目_步甲科,Carabidae",
          top_candidates: [
            { label: "鞘翅目_步甲科,Carabidae" },
            { label: "鞘翅目_步甲科_麻步甲,Carabus brandti" },
          ],
          bbox_summary: "544, 289, 546, 303",
          batch_context: { batch_id: 42 },
        },
        warnings: [],
      },
    ] satisfies NativeModelRunArtifact[];

    const view = getBatchBosReadModel(batch, null, nativeRuns);

    expect(view.latestNativeRun?.evidenceTier).toBe("bootstrap_public_vision");
    expect(view.latestNativeRun?.evidenceLabel).toBe("Bootstrap public vision");
    expect(view.latestNativeRun?.evidenceSummary).toContain("detections");
    expect(view.latestNativeRun?.topLabel).toBe("鞘翅目_步甲科,Carabidae");
    expect(view.latestNativeRun?.topCandidates).toEqual([
      "鞘翅目_步甲科,Carabidae",
      "鞘翅目_步甲科_麻步甲,Carabus brandti",
    ]);
  });
});
