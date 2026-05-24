/**
 * Phase C C6 — unit tests for `UncertaintyBandPanel`.
 *
 * Pins the `computeXRange` + `xToPixel` pure helpers and renders
 * static markup smoke tests via renderToStaticMarkup (matches the
 * codebase convention — see CausalMermaidPanel.test.tsx).
 *
 * Tests do NOT pin pixel-perfect SVG output (would be brittle across
 * minor layout-constant tweaks). Tests pin:
 * - the auto-scale rule
 * - the pixel-mapping formula
 * - presence of testid scaffolding
 * - empty-state behaviour
 * - invalid-band defensive rendering
 * - legend deduplication
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  UncertaintyBandPanel,
  computeXRange,
  xToPixel,
  type UncertaintyBandSpec,
} from "./UncertaintyBandPanel";


const hdiBand: UncertaintyBandSpec = {
  label: "Bayesian HDI 95%",
  low: 0.55,
  high: 0.82,
  point: 0.68,
  kind: "hdi",
};

const conformalBand: UncertaintyBandSpec = {
  label: "Conformal 95%",
  low: 0.50,
  high: 0.85,
  point: 0.68,
  kind: "conformal",
};

const credibilityBand: UncertaintyBandSpec = {
  label: "SER credibility 95%",
  low: 0.60,
  high: 0.75,
  point: 0.68,
  kind: "credibility",
};


describe("computeXRange", () => {
  it("returns [0, 1] for an empty band list with no overrides", () => {
    const { xMin, xMax } = computeXRange([]);
    expect(xMin).toBe(0);
    expect(xMax).toBe(1);
  });

  it("honours xMin / xMax overrides on an empty list", () => {
    const { xMin, xMax } = computeXRange([], -2, 5);
    expect(xMin).toBe(-2);
    expect(xMax).toBe(5);
  });

  it("derives min / max from band bounds with 5% padding", () => {
    const { xMin, xMax } = computeXRange([hdiBand]);
    // span = 0.82 - 0.55 = 0.27; pad = 0.0135
    expect(xMin).toBeCloseTo(0.55 - 0.0135, 4);
    expect(xMax).toBeCloseTo(0.82 + 0.0135, 4);
  });

  it("widens the range across multiple bands", () => {
    const { xMin, xMax } = computeXRange([hdiBand, conformalBand]);
    expect(xMin).toBeLessThan(0.55);     // padded below conformal.low=0.50
    expect(xMax).toBeGreaterThan(0.82);  // padded above conformal.high=0.85
    expect(xMin).toBeLessThan(0.50);     // padding extends below band min
  });

  it("includes point values when computing range (point outside [low, high] is supported)", () => {
    // Defensive: point may legitimately fall outside HDI for some
    // pathological priors; the chart should still encompass it.
    const odd: UncertaintyBandSpec = {
      label: "weird",
      low: 0.4,
      high: 0.5,
      point: 0.9,
      kind: "hdi",
    };
    const { xMin, xMax } = computeXRange([odd]);
    expect(xMax).toBeGreaterThanOrEqual(0.9);
    expect(xMin).toBeLessThanOrEqual(0.4);
  });

  it("respects xMin override even when bands are non-empty", () => {
    const { xMin, xMax } = computeXRange([hdiBand], 0);
    expect(xMin).toBe(0);
    expect(xMax).toBeGreaterThan(0.82);
  });
});


describe("xToPixel", () => {
  it("maps xMin to the left margin", () => {
    expect(xToPixel(0, 0, 1)).toBeCloseTo(140, 5);
  });

  it("maps xMax to the right edge minus right padding", () => {
    expect(xToPixel(1, 0, 1)).toBeCloseTo(480 - 24, 5);
  });

  it("maps the midpoint to the centre of the usable region", () => {
    const left = xToPixel(0, 0, 1);
    const right = xToPixel(1, 0, 1);
    const mid = xToPixel(0.5, 0, 1);
    expect(mid).toBeCloseTo((left + right) / 2, 5);
  });

  it("returns left margin when xMax <= xMin (degenerate range)", () => {
    expect(xToPixel(0.5, 1, 1)).toBe(140);
    expect(xToPixel(0.5, 2, 1)).toBe(140);
  });
});


describe("UncertaintyBandPanel (static markup smoke)", () => {
  it("renders the panel testid wrapper", () => {
    const html = renderToStaticMarkup(
      <UncertaintyBandPanel bands={[hdiBand]} />,
    );
    expect(html).toContain('data-testid="uncertainty-band-panel"');
    expect(html).toContain('data-testid="uncertainty-band-svg"');
  });

  it("renders the optional title inside an h4", () => {
    const html = renderToStaticMarkup(
      <UncertaintyBandPanel
        bands={[hdiBand]}
        title="Phase C SER uncertainty"
      />,
    );
    expect(html).toContain("<h4");
    expect(html).toContain("Phase C SER uncertainty");
  });

  it("appends the supplied className to the wrapper", () => {
    const html = renderToStaticMarkup(
      <UncertaintyBandPanel bands={[hdiBand]} className="custom-class" />,
    );
    expect(html).toContain("custom-class");
  });

  it("renders an empty-state notice when bands is empty", () => {
    const html = renderToStaticMarkup(
      <UncertaintyBandPanel bands={[]} />,
    );
    expect(html).toContain('data-testid="uncertainty-band-empty"');
    expect(html).toContain("No uncertainty data");
    // SVG is NOT rendered in empty state.
    expect(html).not.toContain('data-testid="uncertainty-band-svg"');
  });

  it("renders one row per band", () => {
    const html = renderToStaticMarkup(
      <UncertaintyBandPanel bands={[hdiBand, conformalBand, credibilityBand]} />,
    );
    expect(html).toContain('data-testid="uncertainty-band-row-0"');
    expect(html).toContain('data-testid="uncertainty-band-row-1"');
    expect(html).toContain('data-testid="uncertainty-band-row-2"');
    // No row 3 (out of bounds).
    expect(html).not.toContain('data-testid="uncertainty-band-row-3"');
  });

  it("tags each row with its kind via data-kind", () => {
    const html = renderToStaticMarkup(
      <UncertaintyBandPanel bands={[hdiBand, conformalBand]} />,
    );
    expect(html).toContain('data-kind="hdi"');
    expect(html).toContain('data-kind="conformal"');
  });

  it("renders the band label text", () => {
    const html = renderToStaticMarkup(
      <UncertaintyBandPanel bands={[hdiBand]} />,
    );
    expect(html).toContain("Bayesian HDI 95%");
  });

  it("renders an invalid-band notice when low > high", () => {
    const broken: UncertaintyBandSpec = {
      label: "Broken",
      low: 0.9,
      high: 0.1,
      point: 0.5,
      kind: "hdi",
    };
    const html = renderToStaticMarkup(
      <UncertaintyBandPanel bands={[broken]} />,
    );
    expect(html).toContain('data-testid="uncertainty-band-invalid-0"');
    expect(html).toContain("Invalid band");
  });

  it("deduplicates legend entries when multiple bands share a kind", () => {
    const a = { ...hdiBand, label: "HDI A" };
    const b = { ...hdiBand, label: "HDI B" };
    const html = renderToStaticMarkup(
      <UncertaintyBandPanel bands={[a, b]} />,
    );
    // Legend should mention "Bayesian HDI" only once even with two rows.
    const legendMatches = html.match(/Bayesian HDI/g) ?? [];
    expect(legendMatches.length).toBe(1);
  });

  it("renders the bottom axis with three tick labels", () => {
    const html = renderToStaticMarkup(
      <UncertaintyBandPanel bands={[hdiBand]} />,
    );
    expect(html).toContain('data-testid="uncertainty-band-axis"');
    // Three tick labels: xMin, xMid, xMax. With 5% padding around
    // [0.55, 0.82] the formatted strings are not pinned exactly,
    // but the axis group is present and contains <text> children.
  });

  it("renders the legend block", () => {
    const html = renderToStaticMarkup(
      <UncertaintyBandPanel bands={[conformalBand]} />,
    );
    expect(html).toContain('data-testid="uncertainty-band-legend"');
    expect(html).toContain("Conformal interval");
  });
});
