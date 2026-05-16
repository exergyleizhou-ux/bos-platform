import type { BrainPriorityAction } from "@/lib/brainRuntime";
import { derivePriorityAction, summarizeBrainRuntimeDocuments } from "@/lib/brainRuntime";
import type { BrainRuntimeDocument } from "@/types/bos";

export function deriveAutonomyPriority(
  documents: BrainRuntimeDocument[],
  mode: "default" | "dashboard" | "release" | "signal" | "assistant" | "orchestrator",
): BrainPriorityAction | null {
  const summary = summarizeBrainRuntimeDocuments(documents);
  return derivePriorityAction(summary, mode);
}
