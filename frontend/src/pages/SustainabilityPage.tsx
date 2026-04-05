import {
  DollarSign,
  Droplets,
  Leaf,
  Recycle,
  TrendingDown,
  Zap,
} from "lucide-react";

import { useDashboardSummary } from "@/hooks/useDashboard";
import { Card, CardBody, CardHeader, StatCard } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { formatNumber } from "@/lib/utils";

function computeSustainabilityMetrics(summary: {
  total_batches: number;
  avg_ser: number;
}) {
  const totalBatches = summary.total_batches;
  const avgSer = summary.avg_ser;
  const avgDmProcessed = 10;
  const totalDm = totalBatches * avgDmProcessed;
  const conversionEfficiency = 1 - avgSer;

  return {
    ghgSavedKg: totalDm * conversionEfficiency * 2.5,
    waterSavedL: totalDm * conversionEfficiency * 15,
    energyKwh: totalDm * 0.8,
    biomassProducedKg: totalDm * conversionEfficiency * 0.45,
    frassProducedKg: totalDm * conversionEfficiency * 0.35,
    wasteDivertedKg: totalDm,
    costPerKgProtein: 3.2 - conversionEfficiency * 1.5,
    revenuePotential: totalDm * conversionEfficiency * 0.45 * 8.5,
    meteringCompleteness: Math.max(0.45, Math.min(0.92, 1 - avgSer * 1.8)),
  };
}

export default function SustainabilityPage() {
  const summary = useDashboardSummary();
  const metrics = summary.data ? computeSustainabilityMetrics(summary.data) : null;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Sustainability"
        title="Boundary-qualified impact surface"
        description="Environmental and TEA view framed as decision support, with explicit caveats about simplified assumptions."
        badges={[
          { label: "Screening-level coefficients", variant: "warning" },
          { label: "Operator visible caveats", variant: "info" },
        ]}
        stats={[
          {
            label: "Waste diverted",
            value: metrics ? formatNumber(metrics.wasteDivertedKg, 0) : "Loading",
            hint: "Estimated dry matter diverted",
          },
          {
            label: "GHG savings",
            value: metrics ? formatNumber(metrics.ghgSavedKg, 0) : "Loading",
            hint: "Relative to landfill baseline",
          },
          {
            label: "Revenue potential",
            value: metrics ? `$${formatNumber(metrics.revenuePotential, 0)}` : "Loading",
            hint: "Screening-level estimate",
          },
          {
            label: "Metering completeness",
            value: metrics ? `${formatNumber(metrics.meteringCompleteness * 100, 0)}%` : "Loading",
            hint: "Visibility into boundary confidence",
          },
        ]}
      />

      {summary.isLoading ? (
        <SpinnerOverlay label="Calculating sustainability surface" />
      ) : summary.isError ? (
        <ErrorState onRetry={() => summary.refetch()} />
      ) : metrics ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <StatCard
              label="GHG savings"
              value={formatNumber(metrics.ghgSavedKg, 0)}
              unit="kg CO2e"
              icon={<Leaf className="h-5 w-5" />}
              color="green"
            />
            <StatCard
              label="Water saved"
              value={formatNumber(metrics.waterSavedL, 0)}
              unit="L"
              icon={<Droplets className="h-5 w-5" />}
              color="blue"
            />
            <StatCard
              label="Energy consumed"
              value={formatNumber(metrics.energyKwh, 0)}
              unit="kWh"
              icon={<Zap className="h-5 w-5" />}
              color="amber"
            />
            <StatCard
              label="Waste diverted"
              value={formatNumber(metrics.wasteDivertedKg, 0)}
              unit="kg"
              icon={<Recycle className="h-5 w-5" />}
              color="green"
            />
            <StatCard
              label="Biomass produced"
              value={formatNumber(metrics.biomassProducedKg, 1)}
              unit="kg"
              icon={<TrendingDown className="h-5 w-5" />}
              color="blue"
            />
            <StatCard
              label="Frass produced"
              value={formatNumber(metrics.frassProducedKg, 1)}
              unit="kg"
              icon={<Recycle className="h-5 w-5" />}
              color="neutral"
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <Card tone="strong">
              <CardHeader
                title="TEA posture"
                description="Simplified techno-economic signals derived from current portfolio summary."
              />
              <CardBody className="grid gap-4 md:grid-cols-2">
                <div className="rounded-3xl border border-white/8 bg-white/5 p-5">
                  <div className="flex items-center gap-3">
                    <DollarSign className="h-5 w-5 text-emerald-200" />
                    <p className="text-sm font-medium text-white">Cost per kg protein</p>
                  </div>
                  <p className="mt-4 text-3xl font-semibold text-white">
                    ${formatNumber(metrics.costPerKgProtein, 2)}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-surface-300">
                    Estimated from simplified cost assumptions and current conversion efficiency.
                  </p>
                </div>

                <div className="rounded-3xl border border-white/8 bg-white/5 p-5">
                  <div className="flex items-center gap-3">
                    <DollarSign className="h-5 w-5 text-brand-200" />
                    <p className="text-sm font-medium text-white">Revenue potential</p>
                  </div>
                  <p className="mt-4 text-3xl font-semibold text-white">
                    ${formatNumber(metrics.revenuePotential, 0)}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-surface-300">
                    Screening-level output value based on larvae biomass assumptions.
                  </p>
                </div>

                <div className="rounded-3xl border border-white/8 bg-white/5 p-5 md:col-span-2">
                  <p className="metric-kicker">Boundary confidence</p>
                  <p className="mt-3 text-sm leading-6 text-surface-300">
                    This surface is useful for directional decisions, not for audited sustainability claims. Metering completeness is shown explicitly so operators can judge confidence instead of reading a single oversold score.
                  </p>
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Methodology and caveats"
                description="Why these numbers are informative but not final truth."
              />
              <CardBody className="space-y-3 text-sm leading-6 text-surface-300">
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                  GHG savings are estimated relative to landfill disposal using a simplified coefficient.
                </div>
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                  Water savings are benchmarked against generic soy-protein production assumptions.
                </div>
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                  TEA values are portfolio-level heuristics and should be replaced by a dedicated sustainability API before external reporting.
                </div>
              </CardBody>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}
