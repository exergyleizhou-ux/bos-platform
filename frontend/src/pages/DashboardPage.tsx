import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Beaker,
  CheckCircle2,
  Cpu,
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
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, StatCard } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { GradeBarChart } from "@/components/charts/GradeBarChart";
import { SERTrendChart } from "@/components/charts/SERTrendChart";
import { SpeciesPieChart } from "@/components/charts/SpeciesPieChart";
import { formatNumber, formatPercent, formatRelativeTime } from "@/lib/utils";

export default function DashboardPage() {
  const navigate = useNavigate();
  const [trendDays, setTrendDays] = useState(30);

  const summary = useDashboardSummary();
  const serTrend = useSERTrend(trendDays);
  const speciesDist = useSpeciesDistribution();
  const gradeDist = useGradeDistribution();
  const activity = useRecentActivity(8);

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

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Executive Overview"
        title="Premium BOS command center"
        description="Decision-first view of release posture, queue pressure, SER performance, and evidence-bearing operator activity."
        badges={[
          { label: `Posture: ${posture.label}`, variant: posture.variant },
          { label: "Dark-first console", variant: "neutral" },
          { label: "Audit-visible", variant: "info" },
        ]}
        actions={
          <>
            <Button
              variant="secondary"
              leftIcon={<Beaker className="h-4 w-4" />}
              onClick={() => navigate("/batches")}
            >
              Open batch command
            </Button>
            <Button
              rightIcon={<ArrowRight className="h-4 w-4" />}
              onClick={() => navigate("/twins")}
            >
              Review twins
            </Button>
          </>
        }
        stats={[
          {
            label: "Average SER",
            value: summary.data ? formatNumber(summary.data.avg_ser, 4) : "Loading",
            hint: "Matched-boundary performance baseline",
          },
          {
            label: "Pass rate",
            value: summary.data ? formatPercent(summary.data.avg_pass_rate) : "Loading",
            hint: "Portfolio-level release quality",
          },
          {
            label: "Active batches",
            value: summary.data ? summary.data.active_batches : "Loading",
            hint: "Current command pressure",
          },
          {
            label: "Twins online",
            value: summary.data ? summary.data.total_twins : "Loading",
            hint: "Forecast surfaces available",
          },
        ]}
      />

      {summary.isLoading ? (
        <SpinnerOverlay label="Loading executive summary" />
      ) : summary.isError ? (
        <ErrorState onRetry={() => summary.refetch()} />
      ) : summary.data ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Total batches"
            value={summary.data.total_batches}
            icon={<Beaker className="h-5 w-5" />}
            color="blue"
          />
          <StatCard
            label="Active queue"
            value={summary.data.active_batches}
            icon={<Activity className="h-5 w-5" />}
            color="amber"
          />
          <StatCard
            label="SER uplift"
            value={
              summary.data.ser_improvement_pct != null
                ? formatPercent(summary.data.ser_improvement_pct / 100, 1)
                : "N/A"
            }
            icon={<TrendingUp className="h-5 w-5" />}
            color="green"
          />
          <StatCard
            label="Completed"
            value={summary.data.completed_batches}
            icon={<CheckCircle2 className="h-5 w-5" />}
            color="green"
          />
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1.65fr_1fr]">
        <Card tone="strong" noPadding>
          <div className="border-b border-white/8 px-6 py-5">
            <CardHeader
              title="System performance envelope"
              description={`SER trend, throughput pressure, and rolling posture over the last ${trendDays} days.`}
              action={
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
              }
            />
          </div>

          <div className="px-4 pb-5 pt-2">
            {serTrend.isLoading ? (
              <SpinnerOverlay label="Loading performance trend" />
            ) : serTrend.isError ? (
              <ErrorState onRetry={() => serTrend.refetch()} />
            ) : serTrend.data?.data_points?.length ? (
              <SERTrendChart data={serTrend.data.data_points} height={340} />
            ) : (
              <div className="px-4 py-16 text-center text-sm text-surface-400">
                No trend data available for the selected window.
              </div>
            )}
          </div>

          {summary.data ? (
            <div className="grid gap-3 border-t border-white/8 px-6 py-5 sm:grid-cols-3">
              <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                <p className="metric-kicker">Batches this week</p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  {summary.data.batches_this_week}
                </p>
              </div>
              <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                <p className="metric-kicker">Posture</p>
                <div className="mt-2 flex items-center gap-2">
                  <Badge variant={posture.variant}>{posture.label}</Badge>
                </div>
              </div>
              <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                <p className="metric-kicker">Improvement delta</p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  {summary.data.ser_improvement_pct != null
                    ? `${summary.data.ser_improvement_pct.toFixed(1)}%`
                    : "N/A"}
                </p>
              </div>
            </div>
          ) : null}
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader
              title="Release posture"
              description="Executive interpretation of current system state."
            />
            <CardBody className="space-y-4">
              <div className="rounded-2xl border border-white/8 bg-white/5 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="metric-kicker">Operator readout</p>
                    <p className="mt-2 text-xl font-semibold text-white">{posture.label}</p>
                  </div>
                  <Badge variant={posture.variant} dot>
                    Live
                  </Badge>
                </div>
                <p className="mt-3 text-sm leading-6 text-surface-300">{posture.description}</p>
              </div>

              <div className="space-y-2">
                <p className="metric-kicker">Needs attention</p>
                {attentionQueue.length ? (
                  attentionQueue.map((item) => (
                    <div
                      key={item}
                      className="flex items-start gap-3 rounded-2xl border border-amber-400/15 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
                    >
                      <ShieldAlert className="mt-0.5 h-4 w-4 flex-shrink-0" />
                      <span>{item}</span>
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-emerald-400/15 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                    No urgent queue conditions detected in the current summary window.
                  </div>
                )}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Quick surfaces"
              description="Jump directly into high-value command flows."
            />
            <CardBody className="grid gap-3">
              <Button
                variant="secondary"
                fullWidth
                leftIcon={<Beaker className="h-4 w-4" />}
                onClick={() => navigate("/batches")}
              >
                Batch command center
              </Button>
              <Button
                variant="outline"
                fullWidth
                leftIcon={<Cpu className="h-4 w-4" />}
                onClick={() => navigate("/twins")}
              >
                Digital twin surface
              </Button>
              <Button
                variant="outline"
                fullWidth
                leftIcon={<TrendingUp className="h-4 w-4" />}
                onClick={() => navigate("/forecast")}
              >
                Forecast and drift
              </Button>
            </CardBody>
          </Card>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card noPadding>
          <div className="border-b border-white/8 px-6 py-5">
            <CardHeader
              title="Feedstock mix"
              description="Species balance across the current portfolio."
            />
          </div>
          <div className="px-2 pb-5 pt-2">
            {speciesDist.isLoading ? (
              <SpinnerOverlay label="Loading species mix" />
            ) : speciesDist.isError ? (
              <ErrorState onRetry={() => speciesDist.refetch()} />
            ) : speciesDist.data?.distribution?.length ? (
              <SpeciesPieChart data={speciesDist.data.distribution} height={280} />
            ) : (
              <div className="px-4 py-16 text-center text-sm text-surface-400">
                No species distribution data available.
              </div>
            )}
          </div>
        </Card>

        <Card noPadding>
          <div className="border-b border-white/8 px-6 py-5">
            <CardHeader
              title="Grade distribution"
              description="SER quality split across completed computations."
            />
          </div>
          <div className="px-2 pb-5 pt-2">
            {gradeDist.isLoading ? (
              <SpinnerOverlay label="Loading grade distribution" />
            ) : gradeDist.isError ? (
              <ErrorState onRetry={() => gradeDist.refetch()} />
            ) : gradeDist.data?.items?.length ? (
              <GradeBarChart data={gradeDist.data.items} height={280} />
            ) : (
              <div className="px-4 py-16 text-center text-sm text-surface-400">
                No grade data available yet.
              </div>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Recent operator activity"
            description="Latest evidence-bearing actions across the console."
          />
          <CardBody>
            {activity.isLoading ? (
              <SpinnerOverlay label="Loading activity" />
            ) : activity.isError ? (
              <ErrorState onRetry={() => activity.refetch()} />
            ) : activity.data?.activities?.length ? (
              <ul className="space-y-3">
                {activity.data.activities.map((item) => (
                  <li
                    key={item.id}
                    className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm text-white">
                          <span className="font-medium">{item.user_name}</span>{" "}
                          {item.description}
                        </p>
                        <p className="mt-1 text-xs text-surface-400">
                          {formatRelativeTime(item.timestamp)}
                        </p>
                      </div>
                      <Badge variant="neutral">{item.entity_type}</Badge>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="py-12 text-center text-sm text-surface-400">
                No recent operator activity.
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
