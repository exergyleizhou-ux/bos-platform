import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  Calculator,
  Edit3,
  FileSearch,
  ShieldCheck,
  Trash2,
} from "lucide-react";

import { useBatch, useDeleteBatch } from "@/hooks/useBatches";
import { useComputeSERFromBatch, useSERResult } from "@/hooks/useSER";
import { Badge, GradeBadge, StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, StatCard } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { SERGauge } from "@/components/charts/SERGauge";
import {
  deriveBoundarySummary,
  getControlApiVersion,
  getEvidenceLevel,
  getEvidenceVariant,
  getReleaseReadiness,
  getSignalFreshness,
  getStatusRail,
} from "@/lib/bos";
import { formatDate, formatDateTime, formatNumber, formatPercent } from "@/lib/utils";

export default function BatchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const batchId = Number(id);

  const batch = useBatch(batchId);
  const serResult = useSERResult(batchId);
  const computeSER = useComputeSERFromBatch();
  const deleteBatch = useDeleteBatch();

  const [showDelete, setShowDelete] = useState(false);

  const batchData = batch.data;

  const derived = useMemo(() => {
    if (!batchData) return null;

    const freshness = getSignalFreshness(batchData);
    const readiness = getReleaseReadiness(batchData, serResult.data ?? null);
    const boundary = deriveBoundarySummary(batchData);
    const evidence = getEvidenceLevel(batchData.status);
    const statusRail = getStatusRail(batchData.status);
    const controlVersion = getControlApiVersion(batchData);

    return {
      freshness,
      readiness,
      boundary,
      evidence,
      statusRail,
      controlVersion,
    };
  }, [batchData, serResult.data]);

  if (batch.isLoading) return <SpinnerOverlay label="Loading batch command center" />;
  if (batch.isError) return <ErrorState onRetry={() => batch.refetch()} />;
  if (!batchData || !derived) return <ErrorState title="Batch not found" />;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Batch Command Center"
        title={batchData.batch_id}
        description="Single-batch command surface with release posture, boundary ledger summary, Control-API snapshot, and evidence-bearing next actions."
        badges={[
          { label: `Evidence: ${derived.evidence}`, variant: getEvidenceVariant(derived.evidence) },
          { label: `Signal: ${derived.freshness.label}`, variant: derived.freshness.variant },
          { label: `Control: ${derived.controlVersion}`, variant: "neutral" },
        ]}
        actions={
          <>
            <Button
              variant="ghost"
              leftIcon={<ArrowLeft className="h-4 w-4" />}
              onClick={() => navigate("/batches")}
            >
              Back
            </Button>
            <Button
              variant="secondary"
              leftIcon={<Calculator className="h-4 w-4" />}
              onClick={() => computeSER.mutate(batchId)}
              loading={computeSER.isPending}
            >
              Compute SER
            </Button>
            <Button
              variant="outline"
              leftIcon={<Edit3 className="h-4 w-4" />}
              onClick={() => navigate(`/batches/${batchId}/edit`)}
            >
              Edit
            </Button>
            <Button
              variant="danger"
              leftIcon={<Trash2 className="h-4 w-4" />}
              onClick={() => setShowDelete(true)}
            >
              Delete
            </Button>
          </>
        }
        stats={[
          {
            label: "Species",
            value: batchData.species,
            hint: `Created ${formatDate(batchData.created_at)}`,
          },
          {
            label: "Lifecycle",
            value: <StatusBadge status={batchData.status} />,
            hint: `Last updated ${formatDateTime(batchData.updated_at)}`,
          },
          {
            label: "Release posture",
            value: <Badge variant={derived.readiness.tone}>{derived.readiness.label}</Badge>,
            hint: derived.readiness.description,
          },
          {
            label: "Freshness",
            value: <Badge variant={derived.freshness.variant}>{derived.freshness.label}</Badge>,
            hint: "Signal recency relative to the last update timestamp",
          },
        ]}
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Dry matter reduction"
          value={formatPercent(
            derived.boundary.dryMatterReduction != null
              ? derived.boundary.dryMatterReduction / 100
              : null,
            1,
          )}
          color="blue"
        />
        <StatCard
          label="Nitrogen recovery"
          value={formatPercent(
            derived.boundary.nitrogenRecovery != null
              ? derived.boundary.nitrogenRecovery / 100
              : null,
            1,
          )}
          color="green"
        />
        <StatCard
          label="SER"
          value={formatNumber(serResult.data?.ser_value, 4)}
          color={serResult.data?.passed ? "green" : "amber"}
        />
        <StatCard
          label="Grade"
          value={serResult.data?.grade ? <GradeBadge grade={serResult.data.grade} /> : "N/A"}
          color="neutral"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.55fr_1fr]">
        <div className="space-y-6">
          <Card tone="strong">
            <CardHeader
              title="Release state rail"
              description="Lifecycle progression, current release posture, and blockers requiring operator action."
            />
            <CardBody className="space-y-6">
              <div className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
                <div className="rounded-3xl border border-white/8 bg-white/5 p-5">
                  <p className="metric-kicker">Lifecycle progression</p>
                  <div className="mt-4 flex flex-wrap gap-3">
                    {derived.statusRail.map((step) => (
                      <div
                        key={step.key}
                        className="flex min-w-[8rem] items-center gap-3 rounded-2xl border border-white/8 bg-surface-900/70 px-4 py-3"
                      >
                        <span
                          className={
                            step.active
                              ? "h-3 w-3 rounded-full bg-brand-300 animate-pulse-ring"
                              : step.passed
                                ? "h-3 w-3 rounded-full bg-emerald-300"
                                : "h-3 w-3 rounded-full bg-surface-600"
                          }
                        />
                        <span className="text-sm text-white">{step.label}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-3xl border border-white/8 bg-white/5 p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="metric-kicker">Current release posture</p>
                      <p className="mt-2 text-2xl font-semibold text-white">
                        {derived.readiness.label}
                      </p>
                    </div>
                    <Badge variant={derived.readiness.tone} dot>
                      Live
                    </Badge>
                  </div>

                  <p className="mt-3 text-sm leading-6 text-surface-300">
                    {derived.readiness.description}
                  </p>

                  <div className="mt-4 space-y-2">
                    <p className="metric-kicker">Blocking conditions</p>
                    {derived.readiness.blockers.length ? (
                      derived.readiness.blockers.map((blocker) => (
                        <div
                          key={blocker}
                          className="flex items-start gap-2 rounded-2xl border border-amber-400/15 bg-amber-500/10 px-3 py-2 text-sm text-amber-100"
                        >
                          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                          <span>{blocker}</span>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-2xl border border-emerald-400/15 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
                        No active blockers in the current release evaluation.
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
                <div className="flex items-center justify-center rounded-3xl border border-white/8 bg-white/5 p-6">
                  {serResult.data?.ser_value != null ? (
                    <SERGauge value={serResult.data.ser_value} size={220} />
                  ) : (
                    <div className="space-y-4 text-center">
                      <p className="text-sm text-surface-300">
                        No SER result has been computed for this batch yet.
                      </p>
                      <Button
                        leftIcon={<Calculator className="h-4 w-4" />}
                        onClick={() => computeSER.mutate(batchId)}
                        loading={computeSER.isPending}
                      >
                        Compute now
                      </Button>
                    </div>
                  )}
                </div>

                <div className="rounded-3xl border border-white/8 bg-white/5 p-5">
                  <p className="metric-kicker">Boundary ledger summary</p>
                  <dl className="mt-4 grid gap-4 sm:grid-cols-2">
                    <MetricItem label="DM In" value={`${formatNumber(batchData.dm_in, 3)} kg`} />
                    <MetricItem label="DM Out" value={`${formatNumber(batchData.dm_out, 3)} kg`} />
                    <MetricItem
                      label="Closure residual"
                      value={formatNumber(derived.boundary.closureResidual, 4)}
                    />
                    <MetricItem
                      label="Metering completeness"
                      value={formatPercent(derived.boundary.meteringCompleteness, 0)}
                    />
                    <MetricItem label="Operator" value={batchData.operator ?? "Unassigned"} />
                    <MetricItem label="Batch date" value={formatDate(batchData.batch_date)} />
                  </dl>

                  {serResult.data?.recommendations?.length ? (
                    <div className="mt-5 space-y-2">
                      <p className="metric-kicker">Decision recommendations</p>
                      {serResult.data.recommendations.map((recommendation: string) => (
                        <div
                          key={recommendation}
                          className="rounded-2xl border border-white/8 bg-surface-900/80 px-4 py-3 text-sm text-surface-300"
                        >
                          {recommendation}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            </CardBody>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader
                title="Control and provenance"
                description="Key control settings and operator-facing provenance markers."
              />
              <CardBody className="space-y-4">
                <InfoPanel
                  title="Control-API snapshot"
                  items={[
                    ["Version", derived.controlVersion],
                    ["Status", batchData.status],
                    ["Signal freshness", derived.freshness.label],
                    ["Evidence level", derived.evidence],
                  ]}
                />
                <InfoPanel
                  title="Signal provenance"
                  items={[
                    ["Batch ID", batchData.batch_id],
                    ["Species", batchData.species],
                    ["Last computed", formatDateTime(serResult.data?.computed_at)],
                    ["Updated", formatDateTime(batchData.updated_at)],
                  ]}
                />
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Environment and composition"
                description="Physical operating conditions and compositional breakdown."
              />
              <CardBody className="space-y-4">
                <InfoPanel
                  title="Process environment"
                  items={[
                    ["Temperature", batchData.temperature != null ? `${formatNumber(batchData.temperature, 1)} C` : "N/A"],
                    ["Moisture", batchData.moisture != null ? `${formatNumber(batchData.moisture, 1)} %` : "N/A"],
                    ["Feed rate", batchData.feed_rate != null ? `${formatNumber(batchData.feed_rate, 2)} kg/h` : "N/A"],
                    ["Density", batchData.density != null ? `${formatNumber(batchData.density, 2)} kg/m3` : "N/A"],
                  ]}
                />
                <InfoPanel
                  title="Composition"
                  items={[
                    ["N In", formatNumber(batchData.n_in, 4)],
                    ["N Larvae", formatNumber(batchData.n_larvae, 4)],
                    ["N Frass", formatNumber(batchData.n_frass, 4)],
                    ["Ash In", formatNumber(batchData.ash_in, 4)],
                    ["Ash Out", formatNumber(batchData.ash_out, 4)],
                    ["Fat In", formatNumber(batchData.fat_in, 4)],
                    ["Fat Out", formatNumber(batchData.fat_out, 4)],
                  ]}
                />
              </CardBody>
            </Card>
          </div>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader
              title="Action rail"
              description="What the operator can safely do next from this batch surface."
            />
            <CardBody className="space-y-3">
              <Button
                fullWidth
                leftIcon={<Calculator className="h-4 w-4" />}
                onClick={() => computeSER.mutate(batchId)}
                loading={computeSER.isPending}
              >
                Recompute release score
              </Button>
              <Button
                variant="secondary"
                fullWidth
                leftIcon={<Edit3 className="h-4 w-4" />}
                onClick={() => navigate(`/batches/${batchId}/edit`)}
              >
                Update batch inputs
              </Button>
              <Button
                variant="outline"
                fullWidth
                leftIcon={<FileSearch className="h-4 w-4" />}
                onClick={() => navigate("/ser")}
              >
                Open SER compute surface
              </Button>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Evidence posture"
              description="Trust framing and export readiness for the current record."
            />
            <CardBody className="space-y-4">
              <div className="rounded-3xl border border-white/8 bg-white/5 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="metric-kicker">Evidence level</p>
                    <p className="mt-2 text-lg font-semibold text-white">{derived.evidence}</p>
                  </div>
                  <Badge variant={getEvidenceVariant(derived.evidence)}>
                    Truth-preserving
                  </Badge>
                </div>
                <p className="mt-3 text-sm leading-6 text-surface-300">
                  Current UI presentation keeps evidence level explicit and does not overstate uncomputed or incomplete control logic.
                </p>
              </div>

              <div className="rounded-3xl border border-emerald-400/15 bg-emerald-500/10 p-4">
                <div className="flex items-center gap-3">
                  <ShieldCheck className="h-5 w-5 text-emerald-200" />
                  <p className="text-sm font-medium text-emerald-100">Audit packet export is structurally ready.</p>
                </div>
                <p className="mt-2 text-sm leading-6 text-emerald-100/85">
                  This page exposes lifecycle, control version, provenance, and current release logic in one command surface.
                </p>
              </div>
            </CardBody>
          </Card>

          {batchData.notes ? (
            <Card>
              <CardHeader title="Operator notes" description="Context captured with the batch record." />
              <CardBody>
                <div className="rounded-3xl border border-white/8 bg-white/5 px-4 py-4 text-sm leading-6 text-surface-300 whitespace-pre-wrap">
                  {batchData.notes}
                </div>
              </CardBody>
            </Card>
          ) : null}
        </div>
      </div>

      <ConfirmDialog
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={async () => {
          await deleteBatch.mutateAsync(batchId);
          navigate("/batches");
        }}
        title="Delete batch"
        message={`Delete batch "${batchData.batch_id}"? This action cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        loading={deleteBatch.isPending}
      />
    </div>
  );
}

function MetricItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-surface-900/70 px-4 py-3">
      <dt className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-surface-500">
        {label}
      </dt>
      <dd className="mt-2 text-sm font-medium text-white">{value}</dd>
    </div>
  );
}

function InfoPanel({
  title,
  items,
}: {
  title: string;
  items: Array<[string, string]>;
}) {
  return (
    <div className="rounded-3xl border border-white/8 bg-white/5 p-4">
      <p className="metric-kicker">{title}</p>
      <dl className="mt-4 grid gap-3">
        {items.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-3 text-sm">
            <dt className="text-surface-400">{label}</dt>
            <dd className="text-right font-medium text-white">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
