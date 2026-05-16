import type { BosGraphContext, BosGraphDefinition, BosGraphName, BosGraphNodeOutput } from "@/lib/bosGraph/contracts";
import { bosGraphs } from "@/lib/bosGraph/graphs";

export function getBosGraphDefinition(name: BosGraphName): BosGraphDefinition {
  return bosGraphs[name];
}

export async function runBosGraph(name: BosGraphName, context: BosGraphContext): Promise<BosGraphNodeOutput> {
  const graph = getBosGraphDefinition(name);
  return graph.execute(context);
}

export async function runBosGraphWithFallback(
  name: BosGraphName,
  context: BosGraphContext,
  fallback: () => Promise<BosGraphNodeOutput>,
): Promise<{ result: BosGraphNodeOutput; usedFallback: boolean }> {
  try {
    const result = await runBosGraph(name, context);
    return { result, usedFallback: false };
  } catch {
    const result = await fallback();
    return { result, usedFallback: true };
  }
}
