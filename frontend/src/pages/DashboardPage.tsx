import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Beaker,
  Cpu,
  FlaskConical,
  ShieldAlert,
  TrendingUp,
} from "lucide-react";

import {
  useDashboardSummary,
  useSERTrend,
  useSpeciesDistribution,
  useGradeDistribution,
  useRecentActivity,
} from "@/hooks/useDashboard";
import { BrainOperatorContextCard } from "@/components/bos/BrainOperatorContextCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { ErrorState } from "@/components/ui/EmptyState";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { GradeBarChart } from "@/components/charts/GradeBarChart";
import { SERTrendChart } from "@/components/charts/SERTrendChart";
import { SpeciesPieChart } from "@/components/charts/SpeciesPieChart";
import { useBrainRuntime } from "@/hooks/useBos";
import { deriveAutonomyPriority } from "@/lib/autonomyActions";
import { translateText } from "@/lib/i18n";
import { formatNumber, formatPercent, formatRelativeTime } from "@/lib/utils";

export default function DashboardPage() {
  const navigate = useNavigate();
  const [trendDays, setTrendDays] = useState(30);

  const summary = useDashboardSummary();
  const serTrend = useSERTrend(trendDays);
  const speciesDist = useSpeciesDistribution();
  const gradeDist = useGradeDistribution();
  const activity = useRecentActivity(8);
  const brainRuntime = useBrainRuntime();
  const dashboardPriority = brainRuntime.data
    ? deriveAutonomyPriority(brainRuntime.data.documents, "dashboard")
    : null;

  const posture = useMemo(() => {
    const data = summary.data;
    if (!data) {
      return {
        label: "Syncing",
        variant: "neutral" as const,
        description: "Executive summary is still loading.",
      };
    }

    if (data.avg_pass_rate >= 0.85) {
      return {
        label: "Release-ready",
        variant: "success" as const,
        description: "System-wide release posture is healthy with limited queue pressure.",
      };
    }

    if (data.avg_pass_rate >= 0.65) {
      return {
        label: "Watch closely",
        variant: "warning" as const,
        description: "Results are acceptable, but active queue pressure needs operator review.",
      };
    }

    return {
      label: "Constrained",
      variant: "danger" as const,
      description: "Pass rate is below target and requires immediate operational attention.",
    };
  }, [summary.data]);

  const attentionQueue = useMemo(() => {
    const data = summary.data;
    if (!data) return [];

    const items = [];

    if (data.active_batches > Math.max(4, data.completed_batches)) {
      items.push("Active queue is outpacing completed throughput.");
    }

    if (data.avg_pass_rate < 0.75) {
      items.push("Pass rate has dropped below the preferred premium operating band.");
    }

    if ((data.ser_improvement_pct ?? 0) < 0) {
      items.push("SER performance is regressing versus the previous window.");
    }

    if (data.total_twins === 0) {
      items.push("No digital twins are currently published for forecast support.");
    }

    return items;
  }, [summary.data]);

  const commandMetrics = useMemo(() => {
    if (!summary.data) return [];

    return [
      {
        label: "Average SER",
        value: formatNumber(summary.data.avg_ser, 4),
        hint: "Decision-grade performance envelope",
        accent: "cyan" as const,
      },
      {
        label: "Pass rate",
        value: formatPercent(summary.data.avg_pass_rate),
        hint: "Qualified output share",
        accent: summary.data.avg_pass_rate >= 0.8 ? ("cyan" as const) : ("amber" as const),
      },
      {
        label: "Active batches",
        value: String(summary.data.active_batches),
        hint: `${summary.data.completed_batches} completed`,
        accent: summary.data.active_batches > Math.max(4, summary.data.completed_batches)
          ? ("amber" as const)
          : ("neutral" as const),
      },
      {
        label: "Twins online",
        value: String(summary.data.total_twins),
        hint: "Scenario surfaces ready",
        accent: summary.data.total_twins > 0 ? ("violet" as const) : ("neutral" as const),
      },
    ];
  }, [summary.data]);

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
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-3xl">
              <CockpitSectionLabel>{translateText("Executive Overview")}</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                {translateText("Decision command center")}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText(
                  "Decision-first view of release posture, queue pressure, SER performance, and evidence-bearing operator activity.",
                )}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant={posture.variant}>{`${translateText("Posture")}: ${translateText(posture.label)}`}</Badge>
              {dashboardPriority ? (
                <Button
                  variant="outline"
                  leftIcon={<FlaskConical className="h-4 w-4" />}
                  onClick={() => navigate(dashboardPriority.to)}
                >
                  {translateText(dashboardPriority.label)}
                </Button>
              ) : null}
              <Button
                variant="secondary"
                leftIcon={<Beaker className="h-4 w-4" />}
                onClick={() => navigate("/batches")}
              >
                {translateText("Open batch command")}
              </Button>
              <Button
                variant="outline"
                leftIcon={<Cpu className="h-4 w-4" />}
                onClick={() => navigate("/bos/simulation-lab")}
              >
                {translateText("Open 3D Lab Twin")}
              </Button>
            </div>
          </div>

          {commandMetrics.length ? (
            <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
              {commandMetrics.map((metric) => (
                <CockpitMetric
                  key={metric.label}
                  label={translateText(metric.label)}
                  value={metric.value}
                  hint={translateText(metric.hint)}
                  accent={metric.accent}
                />
              ))}
            </CockpitGrid>
          ) : null}
        </div>
      </CockpitPanel>

      {summary.isLoading ? (
        <SpinnerOverlay label="Loading executive summary" />
      ) : summary.isError ? (
        <ErrorState onRetry={() => summary.refetch()} />
      ) : summary.data ? (
        <div className="space-y-4">
          <BrainOperatorContextCard compact mode="dashboard" />
          <CockpitPanel className="p-4 lg:p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl">
                <CockpitSectionLabel>{translateText("Quick surfaces")}</CockpitSectionLabel>
                <p className="mt-3 text-sm leading-7 text-surface-300">
                  {translateText("Jump directly into high-value command flows.")}
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[26rem]">
                <Button
                  variant="secondary"
                  fullWidth
                  leftIcon={<Beaker className="h-4 w-4" />}
                  onClick={() => navigate("/batches")}
                >
                  {translateText("Batch command")}
                </Button>
                <Button
                  variant="outline"
                  fullWidth
                  leftIcon={<Cpu className="h-4 w-4" />}
                  onClick={() => navigate("/bos/simulation-lab")}
                >
                  {translateText("Open 3D Lab Twin")}
                </Button>
              </div>
            </div>
          </CockpitPanel>
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1.7fr_0.92fr]">
        <CockpitPanel tone="emphasis" className="p-5 lg:p-6">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl">
                <CockpitSectionLabel>{translateText("System performance envelope")}</CockpitSectionLabel>
                <p className="mt-3 text-sm leading-7 text-surface-300">
                  {translateText(`SER trend, throughput pressure, and rolling posture over the last ${trendDays} days.`)}
                </p>
              </div>
              <select
                value={trendDays}
                onChange={(event) => setTrendDays(Number(event.target.value))}
                className="rounded-xl border border-white/10 bg-white/6 px-3 py-2 text-xs text-surface-200 outline-none transition-colors hover:bg-white/10"
              >
                <option value={7}>7 days</option>
                <option value={14}>14 days</option>
                <option value={30}>30 days</option>
                <option value={90}>90 days</option>
              </select>
            </div>

            <div className="assistant-thread-console px-1 py-1">
              {serTrend.isLoading ? (
                <SpinnerOverlay label="Loading performance trend" />
              ) : serTrend.isError ? (
                <ErrorState onRetry={() => serTrend.refetch()} />
              ) : serTrend.data?.data_points?.length ? (
                <SERTrendChart data={serTrend.data.data_points} height={340} />
              ) : (
                <div className="px-4 py-16 text-center text-sm text-surface-400">
                  {translateText("No trend data available for the selected window.")}
                </div>
              )}
            </div>

            {summary.data ? (
              <CockpitGrid className="sm:grid-cols-3">
                <CockpitMetric
                  label={translateText("Batches this week")}
                  value={String(summary.data.batches_this_week)}
                  hint={translateText("Observed command volume")}
                  accent="cyan"
                />
                <CockpitMetric
                  label={translateText("Posture")}
                  value={translateText(posture.label)}
                  hint={translateText(posture.description)}
                  accent={posture.variant === "danger" ? "amber" : posture.variant === "success" ? "cyan" : "violet"}
                />
                <CockpitMetric
                  label={translateText("Improvement delta")}
                  value={summary.data.ser_improvement_pct != null ? `${summary.data.ser_improvement_pct.toFixed(1)}%` : translateText("N/A")}
                  hint={translateText("Compared with prior window")}
                  accent="violet"
                />
              </CockpitGrid>
            ) : null}
          </div>
        </CockpitPanel>

        <CockpitPanel className="p-5 lg:p-6">
          <div className="space-y-5">
            <div>
              <CockpitSectionLabel>{translateText("Release posture")}</CockpitSectionLabel>
              <p className="mt-3 text-sm leading-7 text-surface-300">
                {translateText("Executive interpretation of current system state.")}
              </p>
            </div>

            <div className="assistant-side-panel-chip rounded-[22px] px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="metric-kicker">{translateText("Operator readout")}</p>
                  <p className="mt-2 text-xl font-semibold text-white">{translateText(posture.label)}</p>
                </div>
                <Badge variant={posture.variant} dot>
                  {translateText("Live")}
                </Badge>
              </div>
              <p className="mt-3 text-sm leading-6 text-surface-300">{translateText(posture.description)}</p>
            </div>

            <div className="space-y-2">
              <p className="assistant-section-kicker">{translateText("Needs attention")}</p>
              {attentionQueue.length ? (
                attentionQueue.map((item) => (
                  <div
                    key={item}
                    className="flex items-start gap-3 rounded-2xl border border-amber-400/15 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
                  >
                    <ShieldAlert className="mt-0.5 h-4 w-4 flex-shrink-0" />
                    <span>{translateText(item)}</span>
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-emerald-400/15 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                  {translateText("No urgent queue conditions detected in the current summary window.")}
                </div>
              )}
            </div>

            <div className="space-y-2 border-t border-white/8 pt-4">
              <p className="assistant-section-kicker">{translateText("Next surfaces")}</p>
              <div className="grid gap-3">
                <Button
                  variant="secondary"
                  fullWidth
                  leftIcon={<Beaker className="h-4 w-4" />}
                  onClick={() => navigate("/batches")}
                >
                  {translateText("Batch command center")}
                </Button>
                <Button
                  variant="outline"
                  fullWidth
                  leftIcon={<Cpu className="h-4 w-4" />}
                  onClick={() => navigate("/bos/simulation-lab")}
                >
                  {translateText("3D Lab Twin")}
                </Button>
                <Button
                  variant="outline"
                  fullWidth
                  leftIcon={<FlaskConical className="h-4 w-4" />}
                  onClick={() => navigate("/bos/signal-lab")}
                >
                  {translateText("Signal lab")}
                </Button>
                <Button
                  variant="outline"
                  fullWidth
                  leftIcon={<TrendingUp className="h-4 w-4" />}
                  onClick={() => navigate("/forecast")}
                >
                  {translateText("Forecast and drift")}
                </Button>
              </div>
            </div>
          </div>
        </CockpitPanel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.45fr_0.9fr]">
        <CockpitPanel className="p-5 lg:p-6">
          <div>
            <CockpitSectionLabel>{translateText("Analytical mix")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Portfolio composition and quality distribution in one lower-priority read.")}
            </p>
          </div>
          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            <div className="assistant-thread-console rounded-[24px] px-3 pb-4 pt-3">
              <p className="assistant-section-kicker px-3">{translateText("Feedstock mix")}</p>
              <div className="mt-2">
                {speciesDist.isLoading ? (
                  <SpinnerOverlay label="Loading species mix" />
                ) : speciesDist.isError ? (
                  <ErrorState onRetry={() => speciesDist.refetch()} />
                ) : speciesDist.data?.distribution?.length ? (
                  <SpeciesPieChart data={speciesDist.data.distribution} height={250} />
                ) : (
                  <div className="px-4 py-14 text-center text-sm text-surface-400">
                    {translateText("No species distribution data available.")}
                  </div>
                )}
              </div>
            </div>

            <div className="assistant-thread-console rounded-[24px] px-3 pb-4 pt-3">
              <p className="assistant-section-kicker px-3">{translateText("Grade distribution")}</p>
              <div className="mt-2">
                {gradeDist.isLoading ? (
                  <SpinnerOverlay label="Loading grade distribution" />
                ) : gradeDist.isError ? (
                  <ErrorState onRetry={() => gradeDist.refetch()} />
                ) : gradeDist.data?.items?.length ? (
                  <GradeBarChart data={gradeDist.data.items} height={250} />
                ) : (
                  <div className="px-4 py-14 text-center text-sm text-surface-400">
                    {translateText("No grade data available yet.")}
                  </div>
                )}
              </div>
            </div>
          </div>
        </CockpitPanel>

        <CockpitPanel className="p-5 lg:p-6">
          <div>
            <CockpitSectionLabel>{translateText("Recent operator activity")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Latest evidence-bearing actions across the console.")}
            </p>
          </div>
          <div className="mt-5">
            {activity.isLoading ? (
              <SpinnerOverlay label="Loading activity" />
            ) : activity.isError ? (
              <ErrorState onRetry={() => activity.refetch()} />
            ) : activity.data?.activities?.length ? (
              <ul className="space-y-3">
                {activity.data.activities.map((item) => (
                  <li
                    key={item.id}
                    className="assistant-side-panel-chip rounded-2xl px-4 py-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm text-white">
                          <span className="font-medium">{item.user_name}</span>{" "}
                          {translateText(item.description)}
                        </p>
                        <p className="mt-1 text-xs text-surface-400">
                          {formatRelativeTime(item.timestamp)}
                        </p>
                      </div>
                      <Badge variant="neutral">{translateText(item.entity_type)}</Badge>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="py-12 text-center text-sm text-surface-400">
                {translateText("No recent operator activity.")}
              </div>
            )}
          </div>
        </CockpitPanel>
      </div>
    </div>
  );
}
