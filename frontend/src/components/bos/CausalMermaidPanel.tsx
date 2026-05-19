/**
 * BOS Causal DAG panel (Phase B B6 — D12 = β-lite).
 *
 * Renders a Phase B `DagSpec` (the JSON contract from
 * `backend/app/schemas/causal_common.py`) as a Mermaid `graph LR`
 * SVG, mirroring the agent-side `render_dag_as_mermaid` helper from
 * Plan v2 §3.6.
 *
 * Pure presentational component:
 * - props: `dag` (a `DagSpec`-shaped object) plus optional `title`
 *   and `className`.
 * - no API calls, no router state, no global store.
 *
 * Node-shape convention (mirrors Plan v2 §3.6):
 * - treatment  -> rectangle      `[name]`
 * - outcome    -> circle         `((name))`
 * - mediator   -> hexagon        `{{name}}`
 * - covariate  -> rounded rect   `(name)`
 * - instrument -> asymmetric     `>name]`
 * - latent     -> parallelogram  `[/name/]`
 *
 * Edge convention:
 * - direct      -> solid arrow `-->`
 * - confounding -> dashed       `-.->`  (Mermaid's dashed-arrow)
 *
 * Future B6 follow-up: take the markdown the agent emits and
 * auto-render any embedded `\`\`\`mermaid` block (rather than
 * requiring the caller to pass a `DagSpec` directly). For B6 MVP
 * we keep the API to a single shape.
 */

import { useEffect, useId, useRef, useState } from "react";

// `mermaid` is a default-export ESM module; the type stub ships with
// the package since v10.
import mermaid from "mermaid";

/** Node roles supported by `DagSpec` (see causal_common.py). */
export type DagNodeKind =
  | "treatment"
  | "outcome"
  | "mediator"
  | "covariate"
  | "instrument"
  | "latent";

/** Edge roles supported by `DagSpec`. */
export type DagEdgeKind = "direct" | "confounding";

export interface DagNodeShape {
  name: string;
  node_kind: DagNodeKind;
}

export interface DagEdgeShape {
  src: string;
  dst: string;
  edge_kind?: DagEdgeKind;
}

export interface DagSpecShape {
  nodes: DagNodeShape[];
  edges: DagEdgeShape[];
  // The full DagSpec from the backend has more fields (source,
  // provenance_meta, citation); none affect the rendering so we
  // type the panel against the minimum required surface.
}

export interface CausalMermaidPanelProps {
  dag: DagSpecShape;
  /** Optional title rendered above the graph. */
  title?: string;
  /** Tailwind classes appended to the outer wrapper. */
  className?: string;
}

const NODE_SHAPE: Record<DagNodeKind, (n: string) => string> = {
  treatment: (n) => `${n}[${n}]`,
  outcome: (n) => `${n}((${n}))`,
  mediator: (n) => `${n}{{${n}}}`,
  covariate: (n) => `${n}(${n})`,
  instrument: (n) => `${n}>${n}]`,
  latent: (n) => `${n}[/${n}/]`,
};

/**
 * Pure converter: `DagSpecShape` -> Mermaid `graph LR` source.
 *
 * Exported so unit tests can pin the string contract without
 * actually rendering through the mermaid runtime (which requires
 * a DOM and a non-trivial async init).
 */
export function dagToMermaidSource(dag: DagSpecShape): string {
  const lines: string[] = ["graph LR"];
  for (const node of dag.nodes) {
    const factory = NODE_SHAPE[node.node_kind];
    if (!factory) {
      // Defensive: a future node_kind addition should not crash
      // the panel. Fall back to a plain rectangle and label it.
      lines.push(`  ${node.name}[${node.name}]`);
      continue;
    }
    lines.push(`  ${factory(node.name)}`);
  }
  for (const edge of dag.edges) {
    const arrow = edge.edge_kind === "confounding" ? "-.->" : "-->";
    lines.push(`  ${edge.src} ${arrow} ${edge.dst}`);
  }
  return lines.join("\n");
}

// Mermaid global init — runs once per browser session. Safe to
// call multiple times (mermaid de-duplicates internally).
let _mermaidInitialised = false;
function ensureMermaidInit(): void {
  if (_mermaidInitialised) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "default",
    securityLevel: "strict",
    flowchart: { curve: "basis", htmlLabels: false },
  });
  _mermaidInitialised = true;
}

/**
 * React component. Renders the DAG as a Mermaid SVG. Errors are
 * surfaced inline (small red panel) rather than thrown — a
 * malformed DAG should not crash the surrounding chat.
 */
export function CausalMermaidPanel({
  dag,
  title,
  className,
}: CausalMermaidPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const reactId = useId();
  // Mermaid ids cannot contain colons; React's useId emits some.
  const mermaidId = `mermaid-${reactId.replace(/:/g, "_")}`;
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    ensureMermaidInit();
    let cancelled = false;
    const source = dagToMermaidSource(dag);
    mermaid
      .render(mermaidId, source)
      .then(({ svg }) => {
        if (cancelled) return;
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
          setErrorMessage(null);
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : String(err);
        setErrorMessage(msg);
      });
    return () => {
      cancelled = true;
    };
  }, [dag, mermaidId]);

  const wrapperClass = [
    "rounded-lg border border-slate-200 bg-white p-4 shadow-sm",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={wrapperClass} data-testid="causal-mermaid-panel">
      {title ? (
        <h4 className="mb-2 text-sm font-semibold text-slate-700">
          {title}
        </h4>
      ) : null}
      {errorMessage ? (
        <div
          className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700"
          data-testid="causal-mermaid-error"
        >
          Mermaid render failed: {errorMessage}
        </div>
      ) : null}
      <div ref={containerRef} data-testid="causal-mermaid-svg" />
    </div>
  );
}

export default CausalMermaidPanel;
