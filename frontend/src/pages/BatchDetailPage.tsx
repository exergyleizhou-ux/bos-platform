import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Calculator,
  Edit3,
  Trash2,
} from "lucide-react";

import { AuditExportCard } from "@/components/bos/AuditExportCard";
import { MechanisticContextCard } from "@/components/bos/MechanisticContextCard";
import { NativeModelRunsCard } from "@/components/bos/NativeModelRunsCard";
import { NextBestActionsCard } from "@/components/bos/NextBestActionsCard";
import type { NextBestActionItem } from "@/components/bos/NextBestActionsCard";
import { SignalCompilerPanel } from "@/components/bos/SignalCompilerPanel";
import { SupervisorHistoryCard } from "@/components/bos/SupervisorHistoryCard";
import { SupervisorSnapshotCard } from "@/components/bos/SupervisorSnapshotCard";
import { SignalSupervisorPanel } from "@/components/bos/SignalSupervisorPanel";
import { useBatch, useDeleteBatch } from "@/hooks/useBatches";
import {
  useBatchGuidance,
  useCompileSignal,
  useEvaluateRelease,
  useExportAuditPacket,
  useNativeModelRuns,
  useRefreshSignal,
} from "@/hooks/useBos";
import { useComputeSERFromBatch, useSERResult } from "@/hooks/useSER";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorState } from "@/components/ui/EmptyState";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { SurfaceTile } from "@/components/ui/SurfaceTile";
import { SERGauge } from "@/components/charts/SERGauge";
import { getEvidenceVariant, getStatusRail } from "@/lib/bos";
import {
  deriveBosNextBestActions,
  getBosActionIntent,
  getBosActionLabel,
} from "@/lib/bosGuidance";
import { getBatchBosReadModel } from "@/lib/bos-read-model";
import { translateText } from "@/lib/i18n";
import { formatDate, formatDateTime, formatNumber, formatPercent } from "@/lib/utils";
import type { Batch } from "@/types/batch";
import type { MechanisticContext } from "@/types/bos";

export default function BatchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const batchId = Number(id);

  const batch = useBatch(batchId);
  const guidance = useBatchGuidance(batchId);
  const serResult = useSERResult(batchId);
  const computeSER = useComputeSERFromBatch();
  const deleteBatch = useDeleteBatch();
  const compileSignal = useCompileSignal();
  const refreshSignal = useRefreshSignal();
  const evaluateRelease = useEvaluateRelease();
  const exportAuditPacket = useExportAuditPacket();
  const nativeRuns = useNativeModelRuns(undefined, batchId, 8);

  const [showDelete, setShowDelete] = useState(false);

  const batchData = batch.data;

  const derived = useMemo(() => {
    if (!batchData) return null;

    const auditPacket = batchData.bos?.audit_packet;
    const bosReadModel = getBatchBosReadModel(
      batchData,
      serResult.data ?? null,
      nativeRuns.data ?? [],
    );
    const packetPayload = auditPacket?.packet ?? null;

    return {
      freshness: {
        label: bosReadModel.signalFreshness,
        variant: mapFreshnessVariant(bosReadModel.signalFreshness),
      },
      readiness: {
        label: bosReadModel.releaseLabel,
        tone: bosReadModel.releaseTone,
        description: bosReadModel.rationale,
        blockers: bosReadModel.blockingFactors.length
          ? bosReadModel.blockingFactors
          : bosReadModel.reasonCodes,
        warnings: bosReadModel.warningFactors,
        passedChecks: bosReadModel.passedChecks,
      },
      boundary: {
        dryMatterReduction:
          bosReadModel.metrics.dPrime != null ? bosReadModel.metrics.dPrime * 100 : null,
        nitrogenRecovery:
          bosReadModel.metrics.gPrime != null ? bosReadModel.metrics.gPrime * 100 : null,
        closureResidual: bosReadModel.metrics.closureResidual,
        meteringCompleteness: bosReadModel.metrics.meteringCompleteness,
      },
      evidence: normalizeEvidenceLevel(bosReadModel.evidenceLevel) ?? "Planned",
      statusRail: getStatusRail(batchData.status),
      controlVersion: bosReadModel.controlVersion,
      auditPacket,
      packetPayload,
      portabilityAudits: bosReadModel.portabilityAudits,
      latestPacketPortability: bosReadModel.portabilityAudits,
      releaseDecision: packetPayload?.release_decision ?? null,
      nextBestActions: deriveBosNextBestActions({
        guidance: guidance.data,
        signal: batchData.bos?.signal_batch ?? null,
        releaseDecision: batchData.bos?.release_decision ?? null,
        portabilityAudits: batchData.bos?.portability_audits ?? [],
        hasControlProfile: Boolean(batchData.bos?.control_profile),
      }),
      compileStatus: batchData.bos?.compile_status ?? null,
      latestSignalStatus: batchData.bos?.latest_signal_status ?? null,
      signalBatchId: batchData.bos?.signal_batch?.id ?? null,
      latestSignal: batchData.bos?.signal_batch ?? null,
      mechanisticContext: extractBatchMechanisticContext(batchData),
      supervisorSnapshot: bosReadModel.packet?.supervisorSnapshot ?? null,
      latestNativeRun: bosReadModel.latestNativeRun,
      nativeForecastEvidence: packetPayload?.native_forecast_evidence ?? null,
    };
  }, [batchData, guidance.data, nativeRuns.data, serResult.data]);

  const actionableNextBestActions = useMemo(
    () =>
      derived
        ? derived.nextBestActions.map((item) => ({
            ...item,
            actionLabel: getBosActionLabel(
              item.actionIntent ?? getBosActionIntent(item),
              "batch",
            ),
          }))
        : [],
    [derived],
  );
  const decisionFlowSteps = useMemo(
    () =>
      derived
        ? buildDecisionFlowSteps({
            signalBatchId: derived.signalBatchId,
            freshnessLabel: derived.freshness.label,
            controlVersion: derived.controlVersion,
            portabilityAudit: derived.portabilityAudits[0] ?? null,
            auditPacketReady: Boolean(derived.auditPacket),
            auditPacketGeneratedAt: derived.auditPacket?.generated_at ?? null,
          })
        : [],
    [derived],
  );

  const openSignalLab = () => {
    const params = new URLSearchParams({ batchId: String(batchId) });
    if (derived?.signalBatchId) params.set("signalId", String(derived.signalBatchId));
    if (batchData?.bos?.control_profile?.id) {
      params.set("controlProfileId", String(batchData.bos.control_profile.id));
    }
    navigate(`/bos/signal-lab?${params.toString()}`);
  };

  const handleBatchAction = (item: Pick<NextBestActionItem, "code" | "recommendedAction" | "actionIntent">) => {
    const actionIntent = item.actionIntent ?? getBosActionIntent(item);

    if (actionIntent === "compile_signal") {
      compileSignal.mutate({
        batch_id: batchId,
        control_profile_id: batchData?.bos?.control_profile?.id ?? undefined,
      });
      return;
    }

    if (actionIntent === "refresh_signal") {
      if (!derived?.signalBatchId) return;
      refreshSignal.mutate(derived.signalBatchId);
      return;
    }

    if (actionIntent === "evaluate_release") {
      evaluateRelease.mutate({
        batch_id: batchId,
        signal_batch_id: derived?.signalBatchId ?? undefined,
        control_profile_id: batchData?.bos?.control_profile?.id ?? undefined,
        persist: true,
      });
      return;
    }

    if (actionIntent === "export_audit_packet") {
      if (!derived?.auditPacket) return;
      exportAuditPacket.mutate({ batchId, format: "md" });
      return;
    }

    if (actionIntent === "compute_ser") {
      computeSER.mutate(batchId);
      return;
    }

    if (actionIntent === "edit_batch") {
      navigate(`/batches/${batchId}/edit`);
      return;
    }

    openSignalLab();
  };

  const handleNextBestAction = (item: NextBestActionItem) => {
    if (!derived) return;
    handleBatchAction(item);
  };

  const handleDecisionFlowAction = (stepKey: string) => {
    if (!derived) return;
    handleBatchAction({
      code: stepKey,
      recommendedAction:
        stepKey === "audit"
          ? "Export audit packet"
          : stepKey === "control"
            ? "Select or create a control profile first"
            : stepKey,
    });
  };

  if (batch.isLoading) return <SpinnerOverlay label={translateText("Loading batch command center")} />;
  if (batch.isError) return <ErrorState onRetry={() => batch.refetch()} />;
  if (!batchData || !derived) return <ErrorState title={translateText("Batch not found")} />;

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
              <CockpitSectionLabel>{translateText("Batch Command Center")}</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                {batchData.batch_id}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText("Single-batch command surface with one decision panel, one deep evidence rail, and direct release-facing actions.")}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant={getEvidenceBadgeVariant(derived.evidence)}>{`${translateText("Evidence")}: ${translateText(derived.evidence)}`}</Badge>
              <Badge variant={derived.freshness.variant}>{`${translateText("Signal")}: ${translateText(derived.freshness.label)}`}</Badge>
              <Button
                variant="ghost"
                leftIcon={<ArrowLeft className="h-4 w-4" />}
                onClick={() => navigate("/batches")}
              >
                {translateText("Back")}
              </Button>
              <Button
                variant="secondary"
                leftIcon={<Calculator className="h-4 w-4" />}
                onClick={() => computeSER.mutate(batchId)}
                loading={computeSER.isPending}
              >
                {translateText("Compute SER")}
              </Button>
              <Button
                variant="outline"
                leftIcon={<ArrowRight className="h-4 w-4" />}
                onClick={() => {
                  const params = new URLSearchParams({ batchId: String(batchId) });
                  if (derived.signalBatchId) params.set("signalId", String(derived.signalBatchId));
                  if (batchData.bos?.control_profile?.id) {
                    params.set("controlProfileId", String(batchData.bos.control_profile.id));
                  }
                  navigate(`/bos/signal-lab?${params.toString()}`);
                }}
              >
                {translateText("Signal lab")}
              </Button>
              <Button
                variant="outline"
                leftIcon={<Edit3 className="h-4 w-4" />}
                onClick={() => navigate(`/batches/${batchId}/edit`)}
              >
                {translateText("Edit")}
              </Button>
              <Button
                variant="danger"
                leftIcon={<Trash2 className="h-4 w-4" />}
                onClick={() => setShowDelete(true)}
              >
                {translateText("Delete")}
              </Button>
            </div>
          </div>

          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
            <CockpitMetric
              label={translateText("Species")}
              value={translateText(batchData.species)}
              hint={`${translateText("Created")} ${formatDate(batchData.created_at)}`}
              accent="cyan"
            />
            <CockpitMetric
              label={translateText("Lifecycle")}
              value={translateText(batchData.status)}
              hint={`${translateText("Last updated")} ${formatDateTime(batchData.updated_at)}`}
              accent="neutral"
            />
            <CockpitMetric
              label={translateText("Release posture")}
              value={translateText(derived.readiness.label)}
              hint={translateText(derived.readiness.description)}
              accent={derived.readiness.tone === "danger" ? "amber" : derived.readiness.tone === "success" ? "cyan" : "violet"}
            />
            <CockpitMetric
              label={translateText("Freshness")}
              value={translateText(derived.freshness.label)}
              hint={translateText("Signal recency relative to the last update timestamp")}
              accent={derived.freshness.variant === "warning" ? "amber" : "neutral"}
            />
          </CockpitGrid>
        </div>
      </CockpitPanel>

      <Card tone="strong" className="assistant-thread-stage">
        <CardHeader
          title="Operator decision panel"
          description="Keep the current release posture, portability recommendation, and highest-leverage actions in one command surface."
        />
        <CardBody className="space-y-5">
          <div className="grid gap-3 xl:grid-cols-4">
            {decisionFlowSteps.map((step) => (
              <SurfaceTile key={step.key} className="rounded-3xl p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="assistant-section-kicker">{step.title}</p>
                  <Badge variant={step.variant}>{step.status}</Badge>
                </div>
                <p className="mt-3 text-sm leading-6 text-surface-300">{step.detail}</p>
                {step.actionLabel ? (
                  <div className="mt-4">
                    <Button size="sm" variant="secondary" onClick={() => handleDecisionFlowAction(step.key)}>
                      {step.actionLabel}
                    </Button>
                  </div>
                ) : null}
              </SurfaceTile>
            ))}
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <SurfaceTile tone="subtle" className="rounded-3xl p-4">
              <p className="assistant-section-kicker">Signal evidence</p>
              <p className="mt-3 text-lg font-semibold text-white">
                {derived.latestSignal?.compiled_signal_id ?? "No signal"}
              </p>
              <p className="mt-2 text-sm text-surface-400">
                {derived.latestSignal?.potency != null
                  ? `Potency ${formatNumber(derived.latestSignal.potency, 3)}`
                  : "Compile or attach a signal first."}
              </p>
            </SurfaceTile>
            <SurfaceTile tone="subtle" className="rounded-3xl p-4">
              <p className="assistant-section-kicker">Decision confidence</p>
              <p className="mt-3 text-lg font-semibold text-white">
                {derived.packetPayload?.release_decision?.decision_confidence != null
                  ? formatPercent(derived.packetPayload.release_decision.decision_confidence, 0)
                  : "N/A"}
              </p>
              <p className="mt-2 text-sm text-surface-400">
                {derived.packetPayload?.release_decision?.decision ?? "No persisted release decision"}
              </p>
            </SurfaceTile>
            <SurfaceTile tone="subtle" className="rounded-3xl p-4">
              <p className="assistant-section-kicker">Portability score</p>
              <p className="mt-3 text-lg font-semibold text-white">
                {derived.portabilityAudits[0]?.portabilityScore != null
                  ? formatPercent(derived.portabilityAudits[0].portabilityScore, 0)
                  : "N/A"}
              </p>
              <p className="mt-2 text-sm text-surface-400">
                {derived.portabilityAudits[0]?.recommendedOutcome ?? "No portability audit yet"}
              </p>
            </SurfaceTile>
            <SurfaceTile tone="subtle" className="rounded-3xl p-4">
              <p className="assistant-section-kicker">Packet version</p>
              <p className="mt-3 text-lg font-semibold text-white">
                {derived.auditPacket?.packet_version ?? "Pending"}
              </p>
              <p className="mt-2 text-sm text-surface-400">
                {derived.packetPayload?.generation_context?.schema_version ?? "No packet compiled yet"}
              </p>
            </SurfaceTile>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="assistant-thread-shell rounded-3xl border border-white/8 p-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={derived.readiness.tone}>{derived.readiness.label}</Badge>
                <Badge variant={getEvidenceBadgeVariant(derived.evidence)}>{derived.evidence}</Badge>
                <Badge variant={derived.freshness.variant}>{derived.freshness.label}</Badge>
                {derived.controlVersion !== "No control contract" ? (
                  <Badge variant="info">{derived.controlVersion}</Badge>
                ) : null}
              </div>
              <p className="mt-4 text-sm leading-7 text-surface-300">{derived.readiness.description}</p>
              {derived.portabilityAudits[0] ? (
                <SurfaceTile className="mt-4">
                  <p className="assistant-section-kicker">Current portability posture</p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Badge variant={mapPortabilityVariant(derived.portabilityAudits[0].recommendedOutcome ?? derived.portabilityAudits[0].outcome)}>
                      {formatBatchRecommendationLabel(
                        derived.portabilityAudits[0].recommendedOutcome ?? derived.portabilityAudits[0].outcome,
                      )}
                    </Badge>
                    {derived.portabilityAudits[0].requiresRequalification ? (
                      <Badge variant="danger">Requalification required</Badge>
                    ) : derived.portabilityAudits[0].retuningAxes?.length ? (
                      <Badge variant="warning">Retuning required</Badge>
                    ) : (
                      <Badge variant="success">Proceed</Badge>
                    )}
                  </div>
                  {derived.portabilityAudits[0].rationale ? (
                    <p className="mt-3 text-sm leading-6 text-surface-300">{derived.portabilityAudits[0].rationale}</p>
                  ) : null}
                  {derived.portabilityAudits[0].recommendedAction ? (
                    <SurfaceTile tone="subtle" className="mt-3 px-3 py-3 text-sm text-surface-200">
                      {derived.portabilityAudits[0].recommendedAction}
                    </SurfaceTile>
                  ) : null}
                </SurfaceTile>
              ) : null}
            </div>

            <div className="assistant-aside-card rounded-3xl border border-white/8 p-5">
              <p className="assistant-section-kicker">Primary actions</p>
              <div className="mt-4 space-y-3">
                <Button
                  fullWidth
                  leftIcon={<ArrowRight className="h-4 w-4" />}
                  onClick={openSignalLab}
                >
                  Open signal lab
                </Button>
                <Button
                  variant="secondary"
                  fullWidth
                  leftIcon={<ArrowRight className="h-4 w-4" />}
                  onClick={() =>
                    handleBatchAction({
                      code: "release_not_evaluated",
                      recommendedAction: "Continue with the release evaluation",
                    })
                  }
                  loading={evaluateRelease.isPending}
                >
                  Evaluate release
                </Button>
                <Button
                  variant="outline"
                  fullWidth
                  leftIcon={<Calculator className="h-4 w-4" />}
                  onClick={() => computeSER.mutate(batchId)}
                  loading={computeSER.isPending}
                >
                  Compute SER
                </Button>
                <Button
                  variant="outline"
                  fullWidth
                  leftIcon={<ArrowRight className="h-4 w-4" />}
                  onClick={() =>
                    exportAuditPacket.mutate({
                      batchId,
                      format: "md",
                    })
                  }
                  loading={exportAuditPacket.isPending && exportAuditPacket.variables?.format === "md"}
                  disabled={!derived.auditPacket}
                >
                  Export audit packet
                </Button>
                <Button
                  variant="ghost"
                  fullWidth
                  leftIcon={<Edit3 className="h-4 w-4" />}
                  onClick={() => navigate(`/batches/${batchId}/edit`)}
                >
                  Edit batch
                </Button>
              </div>
              {actionableNextBestActions.length ? (
                <div className="mt-5 space-y-3">
                  <p className="assistant-section-kicker">Suggested action queue</p>
                  {actionableNextBestActions.slice(0, 3).map((item) => (
                    <div key={item.code} className="rounded-2xl border border-white/8 bg-surface-900/70 px-4 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={item.severity === "critical" ? "danger" : item.severity === "warning" ? "warning" : "info"}>
                          {item.title}
                        </Badge>
                        {item.blocking ? <Badge variant="danger">Blocking</Badge> : null}
                      </div>
                      <p className="mt-3 text-sm leading-6 text-surface-300">{item.recommendedAction}</p>
                      {item.actionLabel ? (
                        <div className="mt-3 flex justify-end">
                          <Button size="sm" variant="secondary" onClick={() => handleNextBestAction(item)}>
                            {item.actionLabel}
                          </Button>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </CardBody>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.55fr_1fr]">
        <div className="space-y-6">
          <Card tone="strong" className="assistant-thread-stage">
            <CardHeader
              title="Evidence rail"
              description="Single decision-support rail for lifecycle status, release posture, boundary evidence, and packet-backed blockers."
            />
            <CardBody className="space-y-6">
              <div className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
                <div className="assistant-thread-shell rounded-3xl border border-white/8 p-5">
                  <p className="assistant-section-kicker">Lifecycle progression</p>
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

                <div className="assistant-aside-card rounded-3xl border border-white/8 p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="assistant-section-kicker">Current release posture</p>
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
                    <p className="assistant-section-kicker">Blocking conditions</p>
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

                  {derived.readiness.warnings.length ? (
                    <div className="mt-4 space-y-2">
                      <p className="assistant-section-kicker">Warning factors</p>
                      {derived.readiness.warnings.map((warning) => (
                        <div
                          key={warning}
                          className="rounded-2xl border border-sky-400/15 bg-sky-500/10 px-3 py-2 text-sm text-sky-100"
                        >
                          {warning}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
                <div className="assistant-thread-shell flex items-center justify-center rounded-3xl border border-white/8 p-6">
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

                <div className="assistant-aside-card rounded-3xl border border-white/8 p-5">
                  <p className="assistant-section-kicker">Boundary and decision support</p>
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
                    <MetricItem
                      label="Packet schema"
                      value={derived.packetPayload?.generation_context?.schema_version ?? "N/A"}
                    />
                    <MetricItem
                      label="Compiled"
                      value={formatDateTime(derived.packetPayload?.generation_context?.compiled_at)}
                    />
                  </dl>

                  {derived.readiness.passedChecks.length ? (
                    <div className="mt-5 space-y-2">
                      <p className="assistant-section-kicker">Passed checks</p>
                      {derived.readiness.passedChecks.map((passedCheck) => (
                        <div
                          key={passedCheck}
                          className="rounded-2xl border border-emerald-400/15 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100"
                        >
                          {passedCheck}
                        </div>
                      ))}
                    </div>
                  ) : serResult.data?.recommendations?.length ? (
                    <div className="mt-5 space-y-2">
                      <p className="assistant-section-kicker">Decision recommendations</p>
                      {serResult.data.recommendations.map((recommendation: string) => (
                        <div
                          key={recommendation}
                          className="rounded-2xl border border-white/8 bg-surface-900/80 px-4 py-3 text-sm text-surface-300"
                        >
                          {recommendation}
                        </div>
                      ))}
                    </div>
                  ) : derived.releaseDecision?.reason_codes?.length ? (
                    <div className="mt-5 space-y-2">
                      <p className="assistant-section-kicker">Release reason codes</p>
                      {derived.releaseDecision.reason_codes.map((reasonCode: string) => (
                        <div
                          key={reasonCode}
                          className="rounded-2xl border border-white/8 bg-surface-900/80 px-4 py-3 text-sm text-surface-300"
                        >
                          {reasonCode}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            </CardBody>
          </Card>

          <div className="space-y-6">
            <Card className="assistant-aside-card rounded-[28px]">
              <CardHeader
                title="Deep evidence rail"
                description="Packet provenance, environment, supervisor state, portability posture, and export context merged into one deep-dive card."
              />
              <CardBody className="space-y-5">
                <div className="grid gap-3 xl:grid-cols-3">
                  <SurfaceTile tone={readinessSummaryTone(derived.readiness.tone)} className="rounded-3xl p-4">
                    <p className="assistant-section-kicker">Release posture</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Badge variant={derived.readiness.tone}>{derived.readiness.label}</Badge>
                      {derived.packetPayload?.release_decision?.decision ? (
                        <Badge
                          variant={mapPortabilityVariantLikeDecision(
                            derived.packetPayload.release_decision.decision,
                          )}
                        >
                          {formatBatchDecisionLabel(derived.packetPayload.release_decision.decision)}
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-3 text-sm leading-6 text-surface-300">{derived.readiness.description}</p>
                  </SurfaceTile>
                  <SurfaceTile
                    tone={portabilitySummaryTone(derived.latestPacketPortability[0] ?? derived.portabilityAudits[0] ?? null)}
                    className="rounded-3xl p-4"
                  >
                    <p className="assistant-section-kicker">Portability posture</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      {derived.latestPacketPortability[0] ? (
                        <>
                          <Badge variant={mapPortabilityVariant(derived.latestPacketPortability[0].recommendedOutcome ?? derived.latestPacketPortability[0].outcome)}>
                            {formatBatchRecommendationLabel(
                              derived.latestPacketPortability[0].recommendedOutcome ?? derived.latestPacketPortability[0].outcome,
                            )}
                          </Badge>
                          {derived.latestPacketPortability[0].requiresRequalification ? (
                            <Badge variant="danger">Requalification required</Badge>
                          ) : null}
                        </>
                      ) : (
                        <Badge variant="neutral">Awaiting portability posture</Badge>
                      )}
                    </div>
                    <p className="mt-3 text-sm leading-6 text-surface-300">
                      {derived.latestPacketPortability[0]?.rationale ??
                        "Portability posture will appear after the first packet-backed audit."}
                    </p>
                  </SurfaceTile>
                  <SurfaceTile
                    tone={derived.auditPacket ? "success" : "warning"}
                    className="rounded-3xl p-4"
                  >
                    <p className="assistant-section-kicker">Audit packet</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Badge variant={derived.auditPacket ? "success" : "warning"}>
                        {derived.auditPacket ? "Ready to export" : "Awaiting packet"}
                      </Badge>
                      {derived.auditPacket?.packet_version ? (
                        <Badge variant="info">{derived.auditPacket.packet_version}</Badge>
                      ) : null}
                    </div>
                    <p className="mt-3 text-sm leading-6 text-surface-300">
                      {derived.auditPacket
                        ? `Compiled ${formatDateTime(derived.auditPacket.generated_at)} with schema ${derived.packetPayload?.generation_context?.schema_version ?? "unknown"}.`
                        : "This batch is still waiting for the first compiled audit packet."}
                    </p>
                  </SurfaceTile>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="space-y-4">
                  <InfoPanel
                    title="Packet and signal footing"
                    items={[
                      ["Version", derived.controlVersion],
                      ["Lifecycle state", derived.packetPayload?.batch?.status ?? "N/A"],
                      ["MTT", formatNumber(derived.packetPayload?.control_profile?.mtt, 3)],
                      [
                        "HAL window",
                        derived.packetPayload?.control_profile?.hal_min != null &&
                        derived.packetPayload?.control_profile?.hal_max != null
                          ? `${formatNumber(derived.packetPayload.control_profile.hal_min, 2)} - ${formatNumber(derived.packetPayload.control_profile.hal_max, 2)}`
                          : "N/A",
                      ],
                      ["Signal freshness", derived.freshness.label],
                      ["Evidence level", derived.evidence],
                      ["Batch ID", derived.packetPayload?.batch?.batch_id ?? batchData.batch_id],
                      ["Signal API", derived.packetPayload?.signal_batch?.signal_api_version ?? "N/A"],
                      ["Compiled signal", derived.packetPayload?.signal_batch?.compiled_signal_id ?? "N/A"],
                      ["Potency", formatNumber(derived.packetPayload?.signal_batch?.potency, 3)],
                      ["Species", derived.packetPayload?.batch?.species ?? batchData.species],
                      ["Last computed", formatDateTime(serResult.data?.computed_at)],
                      ["Packet compiled", formatDateTime(derived.packetPayload?.generation_context?.compiled_at)],
                    ]}
                  />
                  </div>
                  <div className="space-y-4">
                  <InfoPanel
                    title="Operating context"
                    items={[
                      ["Temperature", batchData.temperature != null ? `${formatNumber(batchData.temperature, 1)} C` : "N/A"],
                      ["Moisture", batchData.moisture != null ? `${formatNumber(batchData.moisture, 1)} %` : "N/A"],
                      ["Feed rate", batchData.feed_rate != null ? `${formatNumber(batchData.feed_rate, 2)} kg/h` : "N/A"],
                      ["Density", batchData.density != null ? `${formatNumber(batchData.density, 2)} kg/m3` : "N/A"],
                      ["N In", formatNumber(batchData.n_in, 4)],
                      ["N Larvae", formatNumber(batchData.n_larvae, 4)],
                      ["N Frass", formatNumber(batchData.n_frass, 4)],
                      ["Ash In", formatNumber(batchData.ash_in, 4)],
                      ["Ash Out", formatNumber(batchData.ash_out, 4)],
                      ["Fat In", formatNumber(batchData.fat_in, 4)],
                      ["Fat Out", formatNumber(batchData.fat_out, 4)],
                    ]}
                  />
                  </div>
                  <div className="space-y-4 lg:col-span-2">
                  <div className="assistant-aside-card rounded-3xl border border-white/8 p-4">
                    <p className="assistant-section-kicker">Packet decision and portability</p>
                    <div className="mt-4 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
                      <div className="space-y-4">
                        <p className="assistant-section-kicker !text-surface-500">Decision context</p>
                        <div className="rounded-2xl border border-white/8 bg-surface-900/80 px-4 py-4">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-medium text-white">
                              {derived.packetPayload?.release_decision?.decision
                                ? formatBatchDecisionLabel(derived.packetPayload.release_decision.decision)
                                : "No persisted release decision"}
                            </p>
                            {derived.packetPayload?.release_decision?.decision ? (
                              <Badge
                                variant={mapPortabilityVariantLikeDecision(
                                  derived.packetPayload.release_decision.decision,
                                )}
                              >
                                {formatBatchDecisionLabel(derived.packetPayload.release_decision.decision)}
                              </Badge>
                            ) : null}
                          </div>
                          {derived.packetPayload?.release_decision?.rationale ? (
                            <p className="mt-3 text-sm leading-6 text-surface-300">
                              {derived.packetPayload.release_decision.rationale}
                            </p>
                          ) : null}
                          {derived.packetPayload?.release_decision?.reason_codes?.length ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              {derived.packetPayload.release_decision.reason_codes.map((reasonCode) => (
                                <Badge key={reasonCode} variant="neutral">
                                  {reasonCode}
                                </Badge>
                              ))}
                            </div>
                          ) : null}
                        </div>

                        <InfoPanel
                          title="Audit snapshot"
                          items={[
                            ["Packet version", derived.auditPacket?.packet_version ?? "N/A"],
                            ["Generated", formatDateTime(derived.auditPacket?.generated_at)],
                            [
                              "Integrity hash",
                              derived.packetPayload?.generation_context?.hash?.slice(0, 12) ?? "N/A",
                            ],
                            [
                              "Control profile",
                              derived.packetPayload?.control_profile?.name ?? "N/A",
                            ],
                            [
                              "Boundary SER",
                              formatNumber(derived.packetPayload?.boundary_ledger?.ser_value, 4),
                            ],
                            [
                              "Ledger completeness",
                              formatPercent(
                                derived.packetPayload?.boundary_ledger?.metering_completeness,
                                0,
                              ),
                            ],
                          ]}
                        />

                        <AuditExportCard
                          hasAuditPacket={Boolean(derived.auditPacket)}
                          generatedAt={derived.auditPacket?.generated_at ?? null}
                          onExport={(format) =>
                            exportAuditPacket.mutate({
                              batchId,
                              format,
                            })
                          }
                          exportingFormat={
                            exportAuditPacket.isPending ? exportAuditPacket.variables?.format ?? null : null
                          }
                        />
                      </div>

                      <div className="space-y-4">
                        <p className="assistant-section-kicker !text-surface-500">Portability evidence</p>
                        <SupervisorSnapshotCard
                          snapshot={derived.supervisorSnapshot}
                          title="Packet supervisor snapshot"
                          description="Latest persisted supervisor decision carried by the compiled audit packet."
                        />

                        <div className="space-y-3">
                          {derived.latestPacketPortability.length ? (
                            derived.latestPacketPortability.map((audit) => (
                              <div
                                key={audit.id}
                                className="rounded-2xl border border-white/8 bg-surface-900/80 px-4 py-3"
                              >
                                <div className="flex items-center justify-between gap-3">
                                  <div>
                                    <p className="text-sm font-medium text-white">
                                      {audit.executorLabel} / packet portability #{audit.id}
                                    </p>
                                    <p className="mt-1 text-xs text-surface-400">
                                      {audit.localityLabel}
                                    </p>
                                  </div>
                                  <Badge variant={mapPortabilityVariant(audit.recommendedOutcome ?? audit.outcome)}>
                                    {formatBatchRecommendationLabel(audit.recommendedOutcome ?? audit.outcome)}
                                  </Badge>
                                </div>
                                <div className="mt-3 flex flex-wrap gap-2">
                                  <Badge variant={audit.retuningRequired ? "warning" : "success"}>
                                    {audit.retuningRequired
                                      ? "Retuning required"
                                      : "No retuning required"}
                                  </Badge>
                                  {audit.requiresRequalification ? (
                                    <Badge variant="danger">Requalification required</Badge>
                                  ) : null}
                                  {Object.entries(audit.triggerMetrics ?? {}).slice(0, 4).map(
                                    ([key, value]) => (
                                      <Badge key={key} variant="neutral">
                                        {`${key}: ${formatUnknownValue(value)}`}
                                      </Badge>
                                    ),
                                  )}
                                </div>
                                {audit.rationale ? (
                                  <p className="mt-3 text-sm leading-6 text-surface-300">{audit.rationale}</p>
                                ) : null}
                                {audit.recommendedAction ? (
                                  <div className="mt-3 rounded-2xl border border-white/8 bg-white/5 px-3 py-3 text-sm text-surface-200">
                                    {audit.recommendedAction}
                                  </div>
                                ) : null}
                              </div>
                            ))
                          ) : (
                            <div className="assistant-aside-card rounded-2xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
                              Portability posture will appear here after the first packet-backed audit.
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    </div>
                  </div>
                </div>
              </CardBody>
            </Card>
          </div>
        </div>

        <div className="space-y-6">
          <NextBestActionsCard
            items={actionableNextBestActions}
            isLoading={guidance.isLoading && !derived.nextBestActions.length}
            onAction={(item) => handleNextBestAction(item)}
          />

          <Card className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Latest native evidence"
              description="Most recent frontier-model evidence attached to this batch, summarized directly in the command rail."
            />
            <CardBody>
              {derived.latestNativeRun ? (
                <div className="space-y-4">
                  <div className="assistant-aside-card rounded-3xl border border-white/8 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={derived.latestNativeRun.isLive ? "success" : "warning"}>
                        {derived.latestNativeRun.executionMode}
                      </Badge>
                      <Badge variant="info">{derived.latestNativeRun.modelKey}</Badge>
                      <Badge
                        variant={
                          derived.latestNativeRun.evidenceTier === "bootstrap_public_vision"
                            ? "info"
                            : derived.latestNativeRun.evidenceTier === "specialized_bsf_vision"
                              ? "brand"
                              : "neutral"
                        }
                      >
                        {derived.latestNativeRun.evidenceLabel}
                      </Badge>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-surface-300">
                      {derived.latestNativeRun.metricName ?? "sensor_metric"} · recorded {formatDateTime(derived.latestNativeRun.recordedAt)}
                    </p>
                    {derived.latestNativeRun.evidenceSummary ? (
                      <div className="mt-3 rounded-2xl border border-white/8 bg-surface-900/80 px-3 py-3 text-sm text-surface-300">
                        {derived.latestNativeRun.evidenceSummary}
                      </div>
                    ) : null}
                    {derived.latestNativeRun.topLabel ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Badge variant="info">{derived.latestNativeRun.topLabel}</Badge>
                        {derived.latestNativeRun.detectionCount != null ? (
                          <Badge variant="neutral">{`${derived.latestNativeRun.detectionCount} detections`}</Badge>
                        ) : null}
                        {derived.latestNativeRun.bboxSummary ? (
                          <Badge variant="neutral">{derived.latestNativeRun.bboxSummary}</Badge>
                        ) : null}
                      </div>
                    ) : null}
                    {derived.latestNativeRun.topCandidates?.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {derived.latestNativeRun.topCandidates.slice(0, 5).map((candidate) => (
                          <Badge key={candidate} variant="brand">
                            {candidate}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                    {derived.latestNativeRun.forecastPreview.length ? (
                      <div className="mt-3 rounded-2xl border border-sky-400/15 bg-sky-500/10 px-3 py-3 text-sm text-sky-100">
                        Forecast preview: {derived.latestNativeRun.forecastPreview.join(", ")}
                      </div>
                    ) : null}
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <MetricItem label="Prediction horizon" value={String(derived.latestNativeRun.predictionHorizon ?? "N/A")} />
                      <MetricItem label="Artifact log" value={derived.latestNativeRun.artifactPath} />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-aside-card rounded-2xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
                  No native forecast has been attached to this batch yet.
                </div>
              )}
            </CardBody>
          </Card>

          <SignalCompilerPanel
            compileStatus={derived.compileStatus}
            latestSignalStatus={derived.latestSignalStatus}
            signalFreshness={derived.freshness.label}
            hasSignal={Boolean(derived.signalBatchId)}
            onCompile={() =>
              compileSignal.mutate({
                batch_id: batchId,
                control_profile_id: batchData.bos?.control_profile?.id ?? undefined,
              })
            }
            onRefresh={() => {
              if (derived.signalBatchId) {
                refreshSignal.mutate(derived.signalBatchId);
              }
            }}
            compileLoading={compileSignal.isPending}
            refreshLoading={refreshSignal.isPending}
          />

          <MechanisticContextCard
            context={derived.mechanisticContext}
            signalLabel={derived.latestSignal?.compiled_signal_id ?? null}
            title="Batch mechanistic snapshot"
            description="Latest compiled signal diagnostics carried into the batch detail surface."
          />

          <SignalSupervisorPanel signal={derived.latestSignal} />

          <SupervisorHistoryCard history={derived.latestSignal?.qc_markers?.supervisor_history ?? null} />

          <NativeModelRunsCard
            batchId={batchId}
            runs={nativeRuns.data ?? []}
            isLoading={nativeRuns.isLoading}
          />

          {batchData.notes ? (
            <Card className="assistant-aside-card rounded-[28px]">
              <CardHeader title="Operator notes" description="Context captured with the batch record." />
              <CardBody>
                <div className="assistant-aside-card rounded-3xl border border-white/8 px-4 py-4 text-sm leading-6 text-surface-300 whitespace-pre-wrap">
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
    <div className="assistant-meta-panel rounded-2xl border border-white/8 bg-surface-900/70 px-4 py-3">
      <dt className="assistant-section-kicker !text-surface-500">
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
    <div className="assistant-aside-card rounded-3xl border border-white/8 p-4">
      <p className="assistant-section-kicker">{title}</p>
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

function mapFreshnessVariant(label: string) {
  const normalized = label.toLowerCase();
  if (normalized.includes("fresh")) return "success" as const;
  if (normalized.includes("stable")) return "info" as const;
  return "warning" as const;
}

function normalizeEvidenceLevel(level?: string | null) {
  if (level === "Validated" || level === "Supported" || level === "Planned") {
    return level;
  }
  return null;
}

function getEvidenceBadgeVariant(level: string) {
  const normalized = normalizeEvidenceLevel(level);
  return normalized ? getEvidenceVariant(normalized) : "neutral";
}

function mapPortabilityVariant(value: string) {
  if (value === "PASS") return "success" as const;
  if (value === "PASS_WITH_RETUNING") return "warning" as const;
  return "danger" as const;
}

function mapPortabilityVariantLikeDecision(value: string) {
  if (value === "PASS") return "success" as const;
  if (value === "PASS_WITH_RETUNING") return "warning" as const;
  if (value === "FAIL") return "danger" as const;
  return "neutral" as const;
}

function formatBatchDecisionLabel(value: string) {
  if (value === "PASS") return "Release ready";
  if (value === "PASS_WITH_RETUNING") return "Retune first";
  if (value === "FAIL") return "Hold release";
  return value;
}

function formatBatchRecommendationLabel(value: string) {
  if (value === "PASS") return "Recommend release";
  if (value === "PASS_WITH_RETUNING") return "Release with retuning";
  if (value === "FAIL") return "Do not release";
  return value;
}

function readinessSummaryTone(tone: "success" | "warning" | "danger" | "neutral") {
  if (tone === "success") return "success" as const;
  if (tone === "danger") return "danger" as const;
  if (tone === "warning") return "warning" as const;
  return "subtle" as const;
}

function portabilitySummaryTone(
  audit:
    | {
        recommendedOutcome?: string | null;
        outcome: string;
        requiresRequalification?: boolean;
      }
    | null,
) {
  if (!audit) return "subtle" as const;
  if (audit.requiresRequalification) return "danger" as const;
  const outcome = audit.recommendedOutcome ?? audit.outcome;
  if (outcome === "PASS") return "success" as const;
  if (outcome === "PASS_WITH_RETUNING") return "warning" as const;
  return "danger" as const;
}

function buildDecisionFlowSteps(args: {
  signalBatchId: number | null;
  freshnessLabel: string;
  controlVersion: string;
  portabilityAudit: {
    recommendedOutcome?: string | null;
    rationale?: string | null;
    retuningAxes?: string[] | null;
    requiresRequalification?: boolean;
  } | null;
  auditPacketReady: boolean;
  auditPacketGeneratedAt: string | null;
}) {
  const { signalBatchId, freshnessLabel, controlVersion, portabilityAudit, auditPacketReady, auditPacketGeneratedAt } = args;
  return [
    {
      key: "signal",
      title: "Signal",
      status: signalBatchId ? freshnessLabel : "Missing",
      variant: signalBatchId ? (freshnessLabel.toLowerCase().includes("stale") ? "warning" : "success") : "danger",
      detail: signalBatchId
        ? `Current signal posture is ${freshnessLabel.toLowerCase()}.`
        : "Compile or attach a signal before trusting downstream release posture.",
      actionLabel: "Open signal lab",
    },
    {
      key: "control",
      title: "Control",
      status: controlVersion !== "No control contract" ? "Attached" : "Missing",
      variant: controlVersion !== "No control contract" ? "info" : "warning",
      detail:
        controlVersion !== "No control contract"
          ? `Active control contract: ${controlVersion}.`
          : "No Control-API contract is attached to this batch yet.",
      actionLabel: "Edit batch",
    },
    {
      key: "portability",
      title: "Portability",
      status: !portabilityAudit
        ? "Unknown"
        : portabilityAudit.requiresRequalification
          ? "Requalify"
          : portabilityAudit.retuningAxes?.length
            ? "Retune"
            : "Proceed",
      variant: !portabilityAudit
        ? "warning"
        : portabilityAudit.requiresRequalification
          ? "danger"
          : portabilityAudit.retuningAxes?.length
            ? "warning"
            : "success",
      detail:
        portabilityAudit?.rationale ??
        "Run a portability check to decide whether this batch can proceed, needs retuning, or requires requalification.",
      actionLabel: "Open signal lab",
    },
    {
      key: "audit",
      title: "Audit packet",
      status: auditPacketReady ? "Ready" : "Pending",
      variant: auditPacketReady ? "success" : "warning",
      detail: auditPacketReady
        ? `Latest packet compiled at ${formatDateTime(auditPacketGeneratedAt)}.`
        : "Compile the packet before handoff or export.",
      actionLabel: auditPacketReady ? "Export audit packet" : "Open signal lab",
    },
  ] as const;
}

function formatUnknownValue(value: unknown) {
  if (typeof value === "number") return formatNumber(value, 3);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return value;
  if (value == null) return "null";
  return "object";
}

function extractBatchMechanisticContext(batch: Batch): MechanisticContext | null {
  const signalContext = batch.bos?.signal_batch?.qc_markers?.compile_context?.mechanistic_context;
  if (signalContext) return signalContext;

  const packetContext = batch.bos?.audit_packet?.signal_validity?.mechanistic_context;
  if (packetContext) return packetContext as MechanisticContext;

  const triggerContext = batch.bos?.audit_packet?.packet?.release_decision?.trigger_metrics?.mechanistic_context;
  if (triggerContext && isMechanisticContext(triggerContext)) return triggerContext;

  return null;
}

function isMechanisticContext(value: unknown): value is MechanisticContext {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<MechanisticContext>;
  return Boolean(candidate.c_di_ser && candidate.handover_envelope && candidate.inputs);
}
