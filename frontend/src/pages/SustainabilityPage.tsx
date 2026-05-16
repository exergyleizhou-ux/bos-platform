import {
  ShieldCheck,
} from "lucide-react";

import { useBOSLedgerSummary } from "@/hooks/useDashboard";
import { Badge } from "@/components/ui/Badge";
import { CardBody, CardHeader } from "@/components/ui/Card";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { ErrorState } from "@/components/ui/EmptyState";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { SurfaceTile } from "@/components/ui/SurfaceTile";
import { formatNumber, formatPercent } from "@/lib/utils";

export default function SustainabilityPage() {
  const summary = useBOSLedgerSummary();
  const metrics = summary.data;

  return (
    <div className="assistant-ambient-shell space-y-6">
      <div className="assistant-ambient-backdrop" aria-hidden="true">
        <span className="assistant-ambient-orb assistant-ambient-orb-cyan" />
        <span className="assistant-ambient-orb assistant-ambient-orb-violet" />
        <span className="assistant-ambient-orb assistant-ambient-orb-white" />
        <span className="assistant-ambient-grid" />
        <span className="assistant-ambient-scan assistant-ambient-scan-a" />
        <span className="assistant-ambient-scan assistant-ambient-scan-b" />
      </div>

      <CockpitPanel tone="hero" className="p-6 lg:p-7">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <CockpitSectionLabel>Sustainability</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                Boundary-qualified ledger surface
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                Persisted D', G', SER, release pass rate, and evidence posture from the BOS boundary ledger.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant="success">Ledger-driven</Badge>
              <Badge variant="info">Audit visible evidence</Badge>
            </div>
          </div>

          {metrics ? (
            <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
              <CockpitMetric label="Average SER" value={formatNumber(metrics.avg_ser, 4)} hint="Persisted ledger average" accent="cyan" />
              <CockpitMetric label="Average G'" value={formatPercent(metrics.avg_g_prime ?? null, 1)} hint="Boundary-qualified recovery" accent="violet" />
              <CockpitMetric label="Boundary records" value={formatNumber(metrics.boundary_records, 0)} hint="Matched-boundary entries" accent="amber" />
              <CockpitMetric label="Audit packets" value={formatNumber(metrics.total_audit_packets, 0)} hint="Evidence-bearing exports" accent="neutral" />
            </CockpitGrid>
          ) : null}
        </div>
      </CockpitPanel>

      {summary.isLoading ? (
        <SpinnerOverlay label="Calculating sustainability surface" />
      ) : summary.isError ? (
        <ErrorState onRetry={() => summary.refetch()} />
      ) : metrics ? (
        <>
          <CockpitGrid className="md:grid-cols-2 xl:grid-cols-3">
            <CockpitMetric label="Dry matter in" value={formatNumber(metrics.total_dm_in, 1)} hint="kg" accent="cyan" />
            <CockpitMetric label="Dry matter out" value={formatNumber(metrics.total_dm_out, 1)} hint="kg" accent="violet" />
            <CockpitMetric label="Average SER" value={formatNumber(metrics.avg_ser, 4)} hint="Boundary rollup" accent="amber" />
            <CockpitMetric label="Average G'" value={formatPercent(metrics.avg_g_prime ?? null, 1)} hint="Recovery ratio" accent="neutral" />
            <CockpitMetric label="Boundary records" value={formatNumber(metrics.boundary_records, 0)} hint="Matched-boundary entries" accent="neutral" />
            <CockpitMetric label="Audit packets" value={formatNumber(metrics.total_audit_packets, 0)} hint="Evidence-bearing exports" accent="neutral" />
          </CockpitGrid>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <CockpitPanel tone="emphasis" className="p-5 lg:p-6">
              <CardHeader
                title="Ledger posture"
                description="Matched-boundary rollup from persisted boundary ledgers and release decisions."
              />
              <CardBody className="grid gap-4 md:grid-cols-2">
                <SurfaceTile className="assistant-thread-shell rounded-3xl p-5">
                  <div className="flex items-center gap-3">
                    <ShieldCheck className="h-5 w-5 text-emerald-200" />
                    <p className="text-sm font-medium text-white">Evidence distribution</p>
                  </div>
                  <div className="mt-4 space-y-2 text-sm text-surface-300">
                    {Object.entries(metrics.evidence_distribution).length ? (
                      Object.entries(metrics.evidence_distribution).map(([level, count]) => (
                        <div key={level} className="flex items-center justify-between gap-3">
                          <span>{level}</span>
                          <span className="font-medium text-white">{count}</span>
                        </div>
                      ))
                    ) : (
                      <div>No persisted boundary evidence yet.</div>
                    )}
                  </div>
                </SurfaceTile>

                <SurfaceTile className="rounded-3xl p-5">
                  <div className="flex items-center gap-3">
                    <ShieldCheck className="h-5 w-5 text-brand-200" />
                    <p className="text-sm font-medium text-white">Decision counts</p>
                  </div>
                  <div className="mt-4 space-y-2 text-sm text-surface-300">
                    {Object.entries(metrics.decision_counts).length ? (
                      Object.entries(metrics.decision_counts).map(([decision, count]) => (
                        <div key={decision} className="flex items-center justify-between gap-3">
                          <span>{decision}</span>
                          <span className="font-medium text-white">{count}</span>
                        </div>
                      ))
                    ) : (
                      <div>No persisted release decisions yet.</div>
                    )}
                  </div>
                </SurfaceTile>

                <SurfaceTile className="rounded-3xl p-5 md:col-span-2">
                  <p className="assistant-section-kicker">Boundary confidence</p>
                  <p className="mt-3 text-sm leading-6 text-surface-300">
                    This surface is driven by persisted BOS ledger records. If metering completeness is low or release decisions are sparse, the page shows that gap directly instead of filling it with heuristic sustainability coefficients.
                  </p>
                </SurfaceTile>
              </CardBody>
            </CockpitPanel>

            <CockpitPanel className="p-5 lg:p-6">
              <CardHeader
                title="Methodology and caveats"
                description="What is now grounded in the ledger, and what still is not."
              />
              <CardBody className="space-y-3 text-sm leading-6 text-surface-300">
                <SurfaceTile className="px-4 py-3">
                  D', G', SER, closure residual, and metering completeness come from persisted boundary ledgers.
                </SurfaceTile>
                <SurfaceTile className="px-4 py-3">
                  Release pass rate is derived from stored BOS decisions, not from frontend heuristics.
                </SurfaceTile>
                <SurfaceTile className="px-4 py-3">
                  GHG, water, energy, and TEA remain separate engines and are not yet folded into this unified ledger view.
                </SurfaceTile>
                <SurfaceTile className="px-4 py-3">
                  If no ledgers or audit packets exist yet, this page will stay sparse by design rather than synthesizing unsupported claims.
                </SurfaceTile>
              </CardBody>
            </CockpitPanel>
          </div>
        </>
      ) : null}
    </div>
  );
}
