/**
 * Phase B B6 — unit tests for `CausalMermaidPanel`.
 *
 * Pins the `dagToMermaidSource` pure converter and a static-markup
 * smoke render. Matches the codebase convention (renderToStaticMarkup
 * + vitest, no @testing-library/react).
 *
 * The mermaid SVG diff is NOT pinned — mermaid's SVG is
 * implementation-defined and would make tests brittle across
 * library upgrades. We pin the input source string the converter
 * produces; the SVG is mermaid's responsibility.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

// Mock mermaid before importing the component. The runtime is not
// exercised by static markup; the mock keeps the import side-effect
// free under jsdom.
vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async () => ({
      svg: "<svg data-mocked='true'></svg>",
    })),
  },
}));

import {
  CausalMermaidPanel,
  dagToMermaidSource,
  type DagSpecShape,
} from "./CausalMermaidPanel";


const backdoorDag: DagSpecShape = {
  nodes: [
    { name: "T", node_kind: "treatment" },
    { name: "Y", node_kind: "outcome" },
    { name: "Z", node_kind: "covariate" },
  ],
  edges: [
    { src: "T", dst: "Y" },
    { src: "Z", dst: "T", edge_kind: "confounding" },
    { src: "Z", dst: "Y", edge_kind: "confounding" },
  ],
};

const mediationDag: DagSpecShape = {
  nodes: [
    { name: "T", node_kind: "treatment" },
    { name: "M", node_kind: "mediator" },
    { name: "Y", node_kind: "outcome" },
    { name: "Z", node_kind: "covariate" },
  ],
  edges: [
    { src: "T", dst: "M" },
    { src: "M", dst: "Y" },
    { src: "T", dst: "Y" },
    { src: "Z", dst: "T", edge_kind: "confounding" },
    { src: "Z", dst: "Y", edge_kind: "confounding" },
  ],
};


describe("dagToMermaidSource", () => {
  it("emits a graph LR header line", () => {
    const src = dagToMermaidSource(backdoorDag);
    expect(src.startsWith("graph LR")).toBe(true);
  });

  it("renders treatment as rectangle [name]", () => {
    const src = dagToMermaidSource(backdoorDag);
    expect(src).toContain("T[T]");
  });

  it("renders outcome as circle ((name))", () => {
    const src = dagToMermaidSource(backdoorDag);
    expect(src).toContain("Y((Y))");
  });

  it("renders covariate as rounded rect (name)", () => {
    const src = dagToMermaidSource(backdoorDag);
    expect(src).toContain("Z(Z)");
  });

  it("renders mediator as hexagon {{name}}", () => {
    const src = dagToMermaidSource(mediationDag);
    expect(src).toContain("M{{M}}");
  });

  it("renders direct edges with solid arrow -->", () => {
    const src = dagToMermaidSource(backdoorDag);
    // T -> Y is a direct edge (no edge_kind, defaults to direct).
    expect(src).toContain("T --> Y");
  });

  it("renders confounding edges with dashed arrow -.->", () => {
    const src = dagToMermaidSource(backdoorDag);
    expect(src).toContain("Z -.-> T");
    expect(src).toContain("Z -.-> Y");
  });

  it("preserves edge order from the input DAG", () => {
    const src = dagToMermaidSource(backdoorDag);
    const ty = src.indexOf("T --> Y");
    const zt = src.indexOf("Z -.-> T");
    const zy = src.indexOf("Z -.-> Y");
    expect(ty).toBeGreaterThan(0);
    expect(zt).toBeGreaterThan(ty);
    expect(zy).toBeGreaterThan(zt);
  });

  it("falls back to a rectangle for unknown node_kind", () => {
    // Defensive: a future node_kind value should not crash the
    // panel. The converter falls back to a plain rectangle.
    const weird: DagSpecShape = {
      nodes: [
        {
          name: "Q",
          node_kind:
            "fictional" as unknown as DagSpecShape["nodes"][number]["node_kind"],
        },
      ],
      edges: [],
    };
    const src = dagToMermaidSource(weird);
    expect(src).toContain("Q[Q]");
  });

  it("produces a multi-line string with at least nodes + edges", () => {
    const src = dagToMermaidSource(backdoorDag);
    // graph LR + 3 node lines + 3 edge lines = 7 lines.
    expect(src.split("\n").length).toBe(7);
  });

  it("returns just the header on an empty DAG", () => {
    const src = dagToMermaidSource({ nodes: [], edges: [] });
    expect(src).toBe("graph LR");
  });
});


describe("CausalMermaidPanel (static markup smoke)", () => {
  it("renders the panel testid wrapper", () => {
    const html = renderToStaticMarkup(
      <CausalMermaidPanel dag={backdoorDag} />,
    );
    expect(html).toContain('data-testid="causal-mermaid-panel"');
    expect(html).toContain('data-testid="causal-mermaid-svg"');
  });

  it("renders the optional title inside an h4", () => {
    const html = renderToStaticMarkup(
      <CausalMermaidPanel dag={backdoorDag} title="Backdoor DAG" />,
    );
    expect(html).toContain("<h4");
    expect(html).toContain("Backdoor DAG");
  });

  it("appends the supplied className to the wrapper", () => {
    const html = renderToStaticMarkup(
      <CausalMermaidPanel dag={backdoorDag} className="custom-class" />,
    );
    expect(html).toContain("custom-class");
  });

  it("does not render an error banner on initial paint", () => {
    // Initial paint has no error state; the mermaid render is async
    // and runs in useEffect (not exercised by static markup).
    const html = renderToStaticMarkup(
      <CausalMermaidPanel dag={backdoorDag} />,
    );
    expect(html).not.toContain('data-testid="causal-mermaid-error"');
  });
});
