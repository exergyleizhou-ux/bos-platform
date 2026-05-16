import type { BosGraphDefinition } from "@/lib/bosGraph/contracts";
import {
  runBatchTriageIntent,
  runReleaseReviewIntent,
  runSignalRuntimeIntent,
} from "@/lib/bosGraph/nodes";

export const batchTriageGraph: BosGraphDefinition = {
  name: "batch_triage_graph",
  intents: ["riskiest_batch", "batch_analysis", "batch_guidance", "batch_compare"],
  execute: runBatchTriageIntent,
};

export const releaseReviewGraph: BosGraphDefinition = {
  name: "release_review_graph",
  intents: ["executive_summary", "release_summary", "release_risks", "evaluate_release", "export_audit_packet"],
  execute: runReleaseReviewIntent,
};

export const signalRuntimeGraph: BosGraphDefinition = {
  name: "signal_runtime_graph",
  intents: ["compile_signal", "refresh_signal", "evaluate_supervisor", "handover_recommendation"],
  execute: runSignalRuntimeIntent,
};

export const bosGraphs = {
  batch_triage_graph: batchTriageGraph,
  release_review_graph: releaseReviewGraph,
  signal_runtime_graph: signalRuntimeGraph,
};
