/**
 * BOS Uncertainty Band panel (Phase C C6).
 *
 * Renders one or more uncertainty intervals (Bayesian HDI, Conformal
 * prediction, Credibility band, frequentist CI) side-by-side on a
 * shared horizontal axis. Pure SVG — no charting library dependency.
 *
 * Reference: _reports/PHASE_C_PLAN.md §2.6.
 *
 * Pure presentational component (mirrors CausalMermaidPanel):
 * - props: `bands` (one per interval) + optional `title`, `className`,
 *   `xMin`, `xMax`
 * - no API calls, no router state, no global store
 *
 * Auto-scaling x-axis: min/max derived from band bounds unless caller
 * supplies explicit xMin/xMax (e.g. to align two adjacent panels).
 *
 * Kind → colour convention (Tailwind palette):
 * - hdi             -> indigo  (Bayesian Highest Density Interval)
 * - conformal       -> emerald (distribution-free split conformal)
 * - credibility     -> sky     (C4 final_ser_credibility_band)
 * - frequentist_ci  -> amber   (Phase B B.2 LinearDML CI)
 *
 * Empty bands → "No uncertainty data" notice (defensive — a malformed
 * upstream call should not crash the surrounding chat panel).
 */

import { useId } from "react";

/** Band semantic kind (drives colour + legend text). */
export type UncertaintyBandKind =
  | "hdi"
  | "conformal"
  | "credibility"
  | "frequentist_ci";

export interface UncertaintyBandSpec {
  /** Short label shown to the left of the bar (e.g. "Bayesian HDI 95%"). */
  label: string;
  /** Lower bound (alpha/2 quantile for credibility, HDI low, CI low). */
  low: number;
  /** Upper bound. */
  high: number;
  /** Point summary (posterior mean / median / DML point). */
  point: number;
  /** Semantic kind — controls colour. */
  kind: UncertaintyBandKind;
}

export interface UncertaintyBandPanelProps {
  bands: UncertaintyBandSpec[];
  /** Optional title rendered above the chart. */
  title?: string;
  /** Tailwind classes appended to the outer wrapper. */
  className?: string;
  /** Override x-axis lower bound (otherwise auto from bands). */
  xMin?: number;
  /** Override x-axis upper bound (otherwise auto from bands). */
  xMax?: number;
}

const KIND_COLOUR: Record<UncertaintyBandKind, { bar: string; tick: string; legend: string }> = {
  hdi: {
    bar: "#a5b4fc",       // indigo-300
    tick: "#3730a3",      // indigo-800
    legend: "Bayesian HDI",
  },
  conformal: {
    bar: "#6ee7b7",       // emerald-300
    tick: "#065f46",      // emerald-800
    legend: "Conformal interval",
  },
  credibility: {
    bar: "#7dd3fc",       // sky-300
    tick: "#0c4a6e",      // sky-900
    legend: "Credibility band",
  },
  frequentist_ci: {
    bar: "#fcd34d",       // amber-300
    tick: "#92400e",      // amber-800
    legend: "Frequentist CI",
  },
};

const SVG_WIDTH = 480;
const SVG_HEIGHT_PER_BAND = 36;
const SVG_PAD_TOP = 16;
const SVG_PAD_BOTTOM = 32;
const SVG_PAD_LEFT = 140;
const SVG_PAD_RIGHT = 24;
const BAR_HEIGHT = 12;
const TICK_HEIGHT = 18;

/**
 * Pure helper: compute the shared x-axis range from bands.
 *
 * Exported so unit tests can pin the auto-scaling rule without
 * pulling SVG output through jsdom.
 */
export function computeXRange(
  bands: UncertaintyBandSpec[],
  xMinOverride?: number,
  xMaxOverride?: number,
): { xMin: number; xMax: number } {
  if (bands.length === 0) {
    return { xMin: xMinOverride ?? 0, xMax: xMaxOverride ?? 1 };
  }
  let lo = Infinity;
  let hi = -Infinity;
  for (const b of bands) {
    if (b.low < lo) lo = b.low;
    if (b.high > hi) hi = b.high;
    if (b.point < lo) lo = b.point;
    if (b.point > hi) hi = b.point;
  }
  // 5% padding on each side, unless overridden.
  const span = Math.max(hi - lo, 1e-9);
  const pad = span * 0.05;
  return {
    xMin: xMinOverride ?? lo - pad,
    xMax: xMaxOverride ?? hi + pad,
  };
}

/**
 * Pure helper: map a data-space x value to SVG pixel space.
 *
 * Exported for tests.
 */
export function xToPixel(x: number, xMin: number, xMax: number): number {
  const usable = SVG_WIDTH - SVG_PAD_LEFT - SVG_PAD_RIGHT;
  if (xMax <= xMin) return SVG_PAD_LEFT;
  const t = (x - xMin) / (xMax - xMin);
  return SVG_PAD_LEFT + t * usable;
}

/**
 * React component. Renders a horizontal SVG with one row per band.
 * Each row shows: label (left), bar from low→high, point tick in middle.
 * Bottom axis shows xMin / xMid / xMax tick labels.
 */
export function UncertaintyBandPanel({
  bands,
  title,
  className,
  xMin: xMinOverride,
  xMax: xMaxOverride,
}: UncertaintyBandPanelProps) {
  const reactId = useId();
  const svgId = `uncertainty-band-${reactId.replace(/:/g, "_")}`;

  const wrapperClass = [
    "rounded-lg border border-slate-200 bg-white p-4 shadow-sm",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  if (bands.length === 0) {
    return (
      <div
        className={wrapperClass}
        data-testid="uncertainty-band-panel"
      >
        {title ? (
          <h4 className="mb-2 text-sm font-semibold text-slate-700">
            {title}
          </h4>
        ) : null}
        <div
          className="rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500"
          data-testid="uncertainty-band-empty"
        >
          No uncertainty data to display.
        </div>
      </div>
    );
  }

  const { xMin, xMax } = computeXRange(bands, xMinOverride, xMaxOverride);
  const xMid = (xMin + xMax) / 2;
  const svgHeight =
    SVG_PAD_TOP + bands.length * SVG_HEIGHT_PER_BAND + SVG_PAD_BOTTOM;

  return (
    <div className={wrapperClass} data-testid="uncertainty-band-panel">
      {title ? (
        <h4 className="mb-2 text-sm font-semibold text-slate-700">
          {title}
        </h4>
      ) : null}
      <svg
        id={svgId}
        width={SVG_WIDTH}
        height={svgHeight}
        role="img"
        aria-label={title ?? "Uncertainty band panel"}
        data-testid="uncertainty-band-svg"
        viewBox={`0 0 ${SVG_WIDTH} ${svgHeight}`}
        className="block"
      >
        {/* Baseline axis (horizontal line at bottom of chart area). */}
        {(() => {
          const axisY = SVG_PAD_TOP + bands.length * SVG_HEIGHT_PER_BAND + 4;
          return (
            <g data-testid="uncertainty-band-axis">
              <line
                x1={SVG_PAD_LEFT}
                x2={SVG_WIDTH - SVG_PAD_RIGHT}
                y1={axisY}
                y2={axisY}
                stroke="#94a3b8"
                strokeWidth={1}
              />
              {/* Three tick labels: min, mid, max */}
              {[
                { x: xMin, anchor: "start" as const },
                { x: xMid, anchor: "middle" as const },
                { x: xMax, anchor: "end" as const },
              ].map((t) => (
                <text
                  key={t.anchor}
                  x={xToPixel(t.x, xMin, xMax)}
                  y={axisY + 16}
                  textAnchor={t.anchor}
                  fontSize={10}
                  fill="#475569"
                >
                  {t.x.toFixed(3)}
                </text>
              ))}
            </g>
          );
        })()}

        {/* One row per band. */}
        {bands.map((band, idx) => {
          const rowY = SVG_PAD_TOP + idx * SVG_HEIGHT_PER_BAND;
          const colour = KIND_COLOUR[band.kind];
          const barY = rowY + (SVG_HEIGHT_PER_BAND - BAR_HEIGHT) / 2;
          const x0 = xToPixel(band.low, xMin, xMax);
          const x1 = xToPixel(band.high, xMin, xMax);
          const xPoint = xToPixel(band.point, xMin, xMax);
          const invalid = band.low > band.high;
          return (
            <g
              key={`band-${idx}`}
              data-testid={`uncertainty-band-row-${idx}`}
              data-kind={band.kind}
            >
              {/* Label */}
              <text
                x={SVG_PAD_LEFT - 8}
                y={rowY + SVG_HEIGHT_PER_BAND / 2 + 4}
                textAnchor="end"
                fontSize={11}
                fill="#1e293b"
              >
                {band.label}
              </text>

              {/* Invalid-band fallback: red strikethrough text only. */}
              {invalid ? (
                <text
                  x={SVG_PAD_LEFT + 8}
                  y={rowY + SVG_HEIGHT_PER_BAND / 2 + 4}
                  fontSize={10}
                  fill="#b91c1c"
                  data-testid={`uncertainty-band-invalid-${idx}`}
                >
                  Invalid band: low ({band.low}) {">"} high ({band.high})
                </text>
              ) : (
                <>
                  {/* Bar from low to high */}
                  <rect
                    x={x0}
                    y={barY}
                    width={Math.max(x1 - x0, 1)}
                    height={BAR_HEIGHT}
                    fill={colour.bar}
                    stroke={colour.tick}
                    strokeWidth={0.5}
                  />
                  {/* Point tick (thin vertical line through bar) */}
                  <line
                    x1={xPoint}
                    x2={xPoint}
                    y1={barY - (TICK_HEIGHT - BAR_HEIGHT) / 2}
                    y2={barY + BAR_HEIGHT + (TICK_HEIGHT - BAR_HEIGHT) / 2}
                    stroke={colour.tick}
                    strokeWidth={2}
                  />
                </>
              )}
            </g>
          );
        })}
      </svg>

      {/* Legend below SVG. */}
      <div
        className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600"
        data-testid="uncertainty-band-legend"
      >
        {Array.from(new Set(bands.map((b) => b.kind))).map((kind) => (
          <span
            key={kind}
            className="inline-flex items-center gap-1"
            data-kind={kind}
          >
            <span
              className="inline-block h-3 w-4 rounded-sm"
              style={{
                background: KIND_COLOUR[kind].bar,
                border: `0.5px solid ${KIND_COLOUR[kind].tick}`,
              }}
            />
            {KIND_COLOUR[kind].legend}
          </span>
        ))}
      </div>
    </div>
  );
}

export default UncertaintyBandPanel;
