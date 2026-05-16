import { useEffect, useMemo, useState } from "react";
import { ArrowRight, RefreshCcw, Sparkles, Waves } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { AuditExportCard } from "@/components/bos/AuditExportCard";
import { BrainOperatorContextCard } from "@/components/bos/BrainOperatorContextCard";
import { MechanisticContextCard } from "@/components/bos/MechanisticContextCard";
import { NextBestActionsCard } from "@/components/bos/NextBestActionsCard";
import { PortabilityRecommendationCard } from "@/components/bos/PortabilityRecommendationCard";
import { SignalSupervisorPanel } from "@/components/bos/SignalSupervisorPanel";
import { SupervisorHistoryCard } from "@/components/bos/SupervisorHistoryCard";
import { SupervisorSnapshotCard } from "@/components/bos/SupervisorSnapshotCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { ErrorState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "@/components/ui/Table";
import { useBatchList } from "@/hooks/useBatches";
import { useAttachVisionObservation, useVisionDetection, useVisionRuns } from "@/hooks/useVision";
import {
  useAuditPackets,
  useBatchGuidance,
  useBrainRuntime,
  useCompileSignal,
  useControlProfiles,
  useEvaluateRelease,
  useExecutorProfiles,
  useExportAuditPacket,
  useLocalityProfiles,
  usePortabilityAudits,
  usePortabilityRecommendation,
  useRefreshSignal,
  useReleaseDecisions,
  useSignalBatches,
} from "@/hooks/useBos";
import {
  deriveBosNextBestActions,
  getBosActionIntent,
  getBosActionLabel,
} from "@/lib/bosGuidance";
import { getAuditPacketReadModel } from "@/lib/bos-read-model";
import { deriveAutonomyPriority } from "@/lib/autonomyActions";
import { translateText } from "@/lib/i18n";
import { formatDateTime, formatNumber, formatPercent } from "@/lib/utils";
import type { AuditPacket, MechanisticContext, SignalBatch } from "@/types/bos";
import type { NextBestActionItem } from "@/components/bos/NextBestActionsCard";

export default function SignalLabPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const batches = useBatchList(1, 100);
  const signals = useSignalBatches();
  const controlProfiles = useControlProfiles();
  const localityProfiles = useLocalityProfiles();
  const executorProfiles = useExecutorProfiles();
  const portabilityAudits = usePortabilityAudits();
  const releaseDecisions = useReleaseDecisions();
  const auditPackets = useAuditPackets();
  const brainRuntime = useBrainRuntime();
  const compileSignal = useCompileSignal();
  const refreshSignal = useRefreshSignal();
  const evaluateRelease = useEvaluateRelease();
  const exportAuditPacket = useExportAuditPacket();
  const signalPriority = brainRuntime.data
    ? deriveAutonomyPriority(brainRuntime.data.documents, "signal")
    : null;

  const initialBatchId = readNumericParam(searchParams.get("batchId"));
  const initialSignalId = readNumericParam(searchParams.get("signalId"));
  const initialControlProfileId = readNumericParam(searchParams.get("controlProfileId"));
  const initialExecutorProfileId = readNumericParam(searchParams.get("executorProfileId"));
  const initialLocalityProfileId = readNumericParam(searchParams.get("localityProfileId"));

  const [selectedBatchId, setSelectedBatchId] = useState<number | undefined>(initialBatchId);
  const [selectedSignalId, setSelectedSignalId] = useState<number | undefined>(initialSignalId);
  const [selectedControlProfileId, setSelectedControlProfileId] = useState<number | undefined>(initialControlProfileId);
  const [selectedExecutorProfileId, setSelectedExecutorProfileId] = useState<number | undefined>(initialExecutorProfileId);
  const [selectedLocalityProfileId, setSelectedLocalityProfileId] = useState<number | undefined>(initialLocalityProfileId);

  const batchItems = batches.data?.items ?? [];
  const signalItems = signals.data ?? [];
  const effectiveBatchId = selectedBatchId ?? batchItems[0]?.id;
  const controlItems = useMemo(
    () =>
      [...(controlProfiles.data ?? [])].sort(
        (left, right) =>
          Number(right.active) - Number(left.active) ||
          Date.parse(right.updated_at) - Date.parse(left.updated_at),
      ),
    [controlProfiles.data],
  );
  const localityItems = localityProfiles.data ?? [];
  const localityMap = useMemo(() => new Map(localityItems.map((item) => [item.id, item])), [localityItems]);
  const executorItems = useMemo(
    () =>
      [...(executorProfiles.data ?? [])].sort(
        (left, right) =>
          Number(right.active) - Number(left.active) ||
          Date.parse(right.updated_at) - Date.parse(left.updated_at),
      ),
    [executorProfiles.data],
  );
  const executorMap = useMemo(() => new Map(executorItems.map((item) => [item.id, item])), [executorItems]);

  const batchSignals = useMemo(
    () =>
      signalItems
        .filter((item) => item.batch_id === effectiveBatchId)
        .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at)),
    [effectiveBatchId, signalItems],
  );

  useEffect(() => {
    if (!batchItems.length) return;
    if (!selectedBatchId || !batchItems.some((item) => item.id === selectedBatchId)) {
      setSelectedBatchId(batchItems[0]?.id);
    }
  }, [batchItems, selectedBatchId]);

  useEffect(() => {
    if (!batchSignals.length) {
      if (selectedSignalId !== undefined) setSelectedSignalId(undefined);
      return;
    }
    if (!selectedSignalId || !batchSignals.some((item) => item.id === selectedSignalId)) {
      setSelectedSignalId(batchSignals[0]?.id);
    }
  }, [batchSignals, selectedSignalId]);

  useEffect(() => {
    if (!controlItems.length) return;
    if (!selectedControlProfileId || !controlItems.some((item) => item.id === selectedControlProfileId)) {
      setSelectedControlProfileId(controlItems[0]?.id);
    }
  }, [controlItems, selectedControlProfileId]);

  useEffect(() => {
    if (!executorItems.length) return;
    if (!selectedExecutorProfileId || !executorItems.some((item) => item.id === selectedExecutorProfileId)) {
      setSelectedExecutorProfileId(executorItems[0]?.id);
    }
  }, [executorItems, selectedExecutorProfileId]);

  const effectiveSignalId = selectedSignalId ?? batchSignals[0]?.id;
  const effectiveControlProfileId = selectedControlProfileId ?? controlItems[0]?.id;
  const effectiveExecutorProfileId = selectedExecutorProfileId ?? executorItems[0]?.id;
  const selectedBatch = batchItems.find((item) => item.id === effectiveBatchId) ?? null;
  const batchGuidance = useBatchGuidance(effectiveBatchId ?? 0);
  const selectedSignal = batchSignals.find((item) => item.id === effectiveSignalId) ?? batchSignals[0] ?? null;
  const selectedControlProfile =
    controlItems.find((item) => item.id === effectiveControlProfileId) ?? controlItems[0] ?? null;
  const selectedExecutorProfile =
    executorItems.find((item) => item.id === effectiveExecutorProfileId) ?? executorItems[0] ?? null;
  const selectedLocalityProfile =
    localityItems.find((item) => item.id === selectedLocalityProfileId) ?? null;

  useEffect(() => {
    const nextParams = new URLSearchParams();
    if (effectiveBatchId) nextParams.set("batchId", String(effectiveBatchId));
    if (effectiveSignalId) nextParams.set("signalId", String(effectiveSignalId));
    if (effectiveControlProfileId) nextParams.set("controlProfileId", String(effectiveControlProfileId));
    if (effectiveExecutorProfileId) nextParams.set("executorProfileId", String(effectiveExecutorProfileId));
    if (selectedLocalityProfile?.id) nextParams.set("localityProfileId", String(selectedLocalityProfile.id));

    if (nextParams.toString() !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [
    effectiveBatchId,
    effectiveControlProfileId,
    effectiveExecutorProfileId,
    effectiveSignalId,
    searchParams,
    selectedLocalityProfile,
    setSearchParams,
  ]);

  const portabilityRecommendation = usePortabilityRecommendation(
    selectedSignal?.id,
    selectedExecutorProfile?.id,
    selectedLocalityProfile?.id,
  );

  const selectedAuditPacket = useMemo(() => {
    const packets = auditPackets.data ?? [];
    return (
      packets.find((packet) => packet.batch_id === effectiveBatchId && packetMatchesSignal(packet, selectedSignal)) ??
      packets.find((packet) => packet.batch_id === effectiveBatchId) ??
      null
    );
  }, [auditPackets.data, effectiveBatchId, selectedSignal]);

  const selectedAuditPacketView = selectedAuditPacket ? getAuditPacketReadModel(selectedAuditPacket) : null;

  const selectedReleaseDecision = useMemo(() => {
    const decisions = releaseDecisions.data ?? [];
    return (
      decisions.find(
        (item) =>
          item.batch_id === effectiveBatchId &&
          (selectedSignal ? item.signal_batch_id === selectedSignal.id : true),
      ) ??
      decisions.find((item) => item.batch_id === effectiveBatchId) ??
      null
    );
  }, [releaseDecisions.data, effectiveBatchId, selectedSignal]);

  const selectedMechanisticContext = resolveMechanisticContext(selectedSignal, selectedAuditPacket);
  const signalLabel = selectedSignal?.compiled_signal_id ?? selectedAuditPacketView?.signalLabel ?? null;
  const releaseSummary = getReleaseSummary(selectedAuditPacketView, selectedReleaseDecision);
  const matchingPortabilityAudits = useMemo(
    () => {
      const persisted = portabilityAudits.data ?? [];
      const relevantSignalIds = new Set(batchSignals.map((item) => item.id));
      return persisted
        .filter((audit) => {
          if (!relevantSignalIds.has(audit.signal_batch_id)) return false;
          if (selectedSignal && audit.signal_batch_id !== selectedSignal.id) return false;
          if (selectedExecutorProfile && audit.executor_profile_id !== selectedExecutorProfile.id) return false;
          if (selectedLocalityProfile && audit.locality_profile_id !== selectedLocalityProfile.id) return false;
          return true;
        })
        .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))
        .map((audit) => ({
          ...audit,
          signalLabel:
            signalItems.find((item) => item.id === audit.signal_batch_id)?.compiled_signal_id ??
            `Signal ${audit.signal_batch_id}`,
          executorLabel: executorMap.get(audit.executor_profile_id)?.name ?? `Executor ${audit.executor_profile_id}`,
          localityLabel:
            audit.locality_profile_id != null
              ? localityMap.get(audit.locality_profile_id)?.name ?? `Locality ${audit.locality_profile_id}`
              : "No locality override",
        }));
    },
    [
      batchSignals,
      executorMap,
      localityMap,
      portabilityAudits.data,
      selectedExecutorProfile,
      selectedLocalityProfile,
      selectedSignal,
      signalItems,
    ],
  );
  const nextBestActions = useMemo(
    () =>
      deriveBosNextBestActions({
        guidance: batchGuidance.data,
        signal: selectedSignal,
        releaseDecision: selectedReleaseDecision,
        portabilityAudits: matchingPortabilityAudits,
        hasControlProfile: Boolean(selectedControlProfile),
        hasLocalityProfile: Boolean(selectedLocalityProfile),
      }),
    [
      batchGuidance.data,
      matchingPortabilityAudits,
      selectedControlProfile,
      selectedLocalityProfile,
      selectedReleaseDecision,
      selectedSignal,
      ],
  );

  const actionableNextBestActions = useMemo(
    () =>
      nextBestActions.map((item) => ({
        ...item,
        actionLabel: getBosActionLabel(
          item.actionIntent ?? getBosActionIntent(item),
          "signal_lab",
        ),
      })),
    [nextBestActions],
  );

  const handleNextBestAction = (item: NextBestActionItem) => {
    if (!effectiveBatchId) return;
    const actionIntent = item.actionIntent ?? getBosActionIntent(item);

    if (actionIntent === "compile_signal") {
      compileSignal.mutate({
        batch_id: effectiveBatchId,
        control_profile_id: selectedControlProfile?.id,
        locality_profile_id: selectedLocalityProfile?.id,
      });
      return;
    }

    if (actionIntent === "refresh_signal") {
      if (!selectedSignal?.id) return;
      refreshSignal.mutate(selectedSignal.id);
      return;
    }

    if (actionIntent === "evaluate_release") {
      evaluateRelease.mutate({
        batch_id: effectiveBatchId,
        signal_batch_id: selectedSignal?.id,
        control_profile_id: selectedControlProfile?.id,
        locality_profile_id: selectedLocalityProfile?.id,
        persist: true,
      });
      return;
    }

    if (actionIntent === "export_audit_packet") {
      exportAuditPacket.mutate({ batchId: effectiveBatchId, format: "md" });
      return;
    }

    if (actionIntent === "compute_ser") {
      navigate(`/batches/${effectiveBatchId}`);
      return;
    }

    navigate("/bos/console");
  };

  const isLoading =
    batches.isLoading ||
    signals.isLoading ||
    controlProfiles.isLoading ||
    localityProfiles.isLoading ||
    executorProfiles.isLoading ||
    portabilityAudits.isLoading ||
    releaseDecisions.isLoading ||
    auditPackets.isLoading;
  const isError =
    batches.isError ||
    signals.isError ||
    controlProfiles.isError ||
    localityProfiles.isError ||
    executorProfiles.isError ||
    portabilityAudits.isError ||
    releaseDecisions.isError ||
    auditPackets.isError;

  if (isLoading) return <SpinnerOverlay label={translateText("Loading signal lab")} />;

  if (isError) {
    return (
      <ErrorState
        title={translateText("Signal lab unavailable")}
        description={translateText("We could not load the signal, contract, and audit surfaces needed for this operator lab.")}
        onRetry={() => {
          void batches.refetch();
          void signals.refetch();
          void controlProfiles.refetch();
          void localityProfiles.refetch();
          void executorProfiles.refetch();
          void releaseDecisions.refetch();
          void auditPackets.refetch();
        }}
      />
    );
  }

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
              <CockpitSectionLabel>{translateText("BOS / Signal Lab")}</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                {translateText("Compile, inspect, and qualify the handover signal")}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText("Focused operator surface for signal freshness, Control-API alignment, release readiness, portability, and supervisor evidence.")}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant={releaseSummary.variant}>{translateText(releaseSummary.label)}</Badge>
              <Badge variant={selectedSignal ? freshnessVariant(selectedSignal.freshness_state) : "warning"}>
                {selectedSignal ? translateText(`Signal ${selectedSignal.freshness_state ?? "Unknown"}`) : translateText("Signal missing")}
              </Badge>
              {signalPriority ? (
                <Button
                  variant="outline"
                  leftIcon={<ArrowRight className="h-4 w-4" />}
                  onClick={() => navigate(signalPriority.to)}
                >
                  {translateText(signalPriority.label)}
                </Button>
              ) : null}
              <Button
                variant="ghost"
                leftIcon={<ArrowRight className="h-4 w-4" />}
                onClick={() => navigate("/bos/console")}
              >
                {translateText("Open decision console")}
              </Button>
            </div>
          </div>

          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-5">
            <CockpitMetric
              label={translateText("Selected batch")}
              value={selectedBatch?.batch_id ?? translateText("No batch")}
              hint={selectedBatch ? `${translateText("Status")} ${translateText(selectedBatch.status)}` : translateText("Load batches to start the lab")}
              accent="cyan"
            />
            <CockpitMetric
              label={translateText("Potency")}
              value={selectedSignal?.potency != null ? formatNumber(selectedSignal.potency, 3) : translateText("N/A")}
              hint={translateText(selectedSignal?.potency_unit ?? "SER-equivalent")}
              accent="violet"
            />
            <CockpitMetric
              label={translateText("Dose window")}
              value={formatDoseWindow(selectedSignal?.dose_window_min, selectedSignal?.dose_window_max)}
              hint={selectedControlProfile ? `${translateText(selectedControlProfile.name)} ${translateText("contract")}` : translateText("No active contract")}
              accent="neutral"
            />
            <CockpitMetric
              label={translateText("Decision confidence")}
              value={releaseSummary.confidence}
              hint={translateText(releaseSummary.hint)}
              accent="amber"
            />
            <CockpitMetric
              label={translateText("Portability score")}
              value={portabilityRecommendation.data?.portability_score != null ? formatPercent(portabilityRecommendation.data.portability_score, 0) : translateText("N/A")}
              hint={translateText(selectedExecutorProfile ? selectedExecutorProfile.name : "Select an executor")}
              accent="neutral"
            />
          </CockpitGrid>
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div>
          <CockpitSectionLabel>{translateText("Lab controls")}</CockpitSectionLabel>
          <p className="mt-3 text-sm leading-7 text-surface-300">
            {translateText("Pick the batch, signal, contract, and executor you want to qualify.")}
          </p>
        </div>
        <div className="mt-5 grid gap-4 xl:grid-cols-5">
          <Select
            label={translateText("Batch")}
            value={effectiveBatchId ? String(effectiveBatchId) : ""}
            onChange={(event) => setSelectedBatchId(Number(event.target.value))}
            options={batchItems.map((item) => ({
              value: String(item.id),
              label: `${item.batch_id} - ${item.status}`,
            }))}
            placeholder={translateText("Select batch")}
          />
          <Select
            label={translateText("Signal")}
            value={selectedSignal?.id ? String(selectedSignal.id) : ""}
            onChange={(event) => setSelectedSignalId(Number(event.target.value))}
            options={batchSignals.map((item) => ({
              value: String(item.id),
              label: `${item.compiled_signal_id ?? `Signal ${item.id}`} - ${item.freshness_state ?? "Unknown"}`,
            }))}
            placeholder={batchSignals.length ? translateText("Select signal") : translateText("No signal for this batch")}
            disabled={!batchSignals.length}
          />
          <Select
            label={translateText("Control contract")}
            value={effectiveControlProfileId ? String(effectiveControlProfileId) : ""}
            onChange={(event) => setSelectedControlProfileId(Number(event.target.value))}
            options={controlItems.map((item) => ({
              value: String(item.id),
              label: `${item.name} - ${item.version}${item.active ? " - active" : ""}`,
            }))}
            placeholder={translateText("Select control profile")}
          />
          <Select
            label={translateText("Executor")}
            value={effectiveExecutorProfileId ? String(effectiveExecutorProfileId) : ""}
            onChange={(event) => setSelectedExecutorProfileId(Number(event.target.value))}
            options={executorItems.map((item) => ({
              value: String(item.id),
              label: `${item.name}${item.active ? " - active" : ""}`,
            }))}
            placeholder={translateText("Select executor")}
          />
          <Select
            label={translateText("Locality override")}
            value={selectedLocalityProfile?.id ? String(selectedLocalityProfile.id) : ""}
            onChange={(event) =>
              setSelectedLocalityProfileId(event.target.value ? Number(event.target.value) : undefined)
            }
            options={localityItems.map((item) => ({
              value: String(item.id),
              label: item.name,
            }))}
            placeholder={translateText("No locality override")}
          />
        </div>
      </CockpitPanel>

      <BrainOperatorContextCard
        compact
        mode="signal"
        title="Autonomy signal context"
        description="Current focus, next slices, and heuristics from the project brain while you qualify the signal."
      />

      <div className="grid gap-6 xl:grid-cols-[1.35fr_0.95fr]">
        <div className="space-y-6">
          <MechanisticContextCard context={selectedMechanisticContext} signalLabel={signalLabel} />

          <Card className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Operator decision panel"
              description="Compile, refresh, and evaluate release from one focused decision surface."
            />
            <CardBody className="grid gap-3 md:grid-cols-3">
              <Button
                fullWidth
                leftIcon={<Sparkles className="h-4 w-4" />}
                onClick={() => {
                  if (!effectiveBatchId) return;
                  compileSignal.mutate({
                    batch_id: effectiveBatchId,
                    control_profile_id: selectedControlProfile?.id,
                    locality_profile_id: selectedLocalityProfile?.id,
                  });
                }}
                loading={compileSignal.isPending}
                disabled={!effectiveBatchId}
              >
                Compile signal
              </Button>
              <Button
                variant="secondary"
                fullWidth
                leftIcon={<RefreshCcw className="h-4 w-4" />}
                onClick={() => {
                  if (!selectedSignal?.id) return;
                  refreshSignal.mutate(selectedSignal.id);
                }}
                loading={refreshSignal.isPending}
                disabled={!selectedSignal?.id}
              >
                Refresh signal
              </Button>
              <Button
                variant="outline"
                fullWidth
                leftIcon={<Waves className="h-4 w-4" />}
                onClick={() => {
                  if (!effectiveBatchId) return;
                  evaluateRelease.mutate({
                    batch_id: effectiveBatchId,
                    signal_batch_id: selectedSignal?.id,
                    control_profile_id: selectedControlProfile?.id,
                    locality_profile_id: selectedLocalityProfile?.id,
                    persist: true,
                  });
                }}
                loading={evaluateRelease.isPending}
                disabled={!effectiveBatchId}
              >
                Evaluate release
              </Button>
            </CardBody>
          </Card>

          <VisionObservationReviewCard signal={selectedSignal} />

          <SignalSupervisorPanel signal={selectedSignal} />
          <SupervisorSnapshotCard snapshot={selectedAuditPacketView?.supervisorSnapshot ?? null} />
          <SupervisorHistoryCard
            history={
              selectedSignal?.qc_markers?.supervisor_history ??
              selectedAuditPacketView?.supervisorHistory ??
              null
            }
          />
        </div>

        <div className="space-y-6">
          <Card className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Current decision posture"
              description="Keep the live release posture, freshness, and next high-leverage actions visible while you qualify the batch."
            />
            <CardBody className="space-y-4">
              <div className="assistant-thread-shell rounded-3xl border border-white/8 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={releaseSummary.variant}>{releaseSummary.label}</Badge>
                  {selectedSignal ? (
                    <Badge variant={freshnessVariant(selectedSignal.freshness_state)}>
                      {selectedSignal.freshness_state ?? "Unknown"}
                    </Badge>
                  ) : null}
                  {selectedControlProfile ? (
                    <Badge variant="info">{selectedControlProfile.version}</Badge>
                  ) : null}
                </div>
                <p className="mt-3 text-sm leading-6 text-surface-300">{releaseSummary.rationale}</p>
              </div>
              <div className="grid gap-3">
                <Button
                  fullWidth
                  leftIcon={<Sparkles className="h-4 w-4" />}
                  onClick={() => {
                    if (!effectiveBatchId) return;
                    compileSignal.mutate({
                      batch_id: effectiveBatchId,
                      control_profile_id: selectedControlProfile?.id,
                      locality_profile_id: selectedLocalityProfile?.id,
                    });
                  }}
                  loading={compileSignal.isPending}
                  disabled={!effectiveBatchId}
                >
                  Compile signal
                </Button>
                <Button
                  variant="secondary"
                  fullWidth
                  leftIcon={<RefreshCcw className="h-4 w-4" />}
                  onClick={() => {
                    if (!selectedSignal?.id) return;
                    refreshSignal.mutate(selectedSignal.id);
                  }}
                  loading={refreshSignal.isPending}
                  disabled={!selectedSignal?.id}
                >
                  Refresh signal
                </Button>
                <Button
                  variant="outline"
                  fullWidth
                  leftIcon={<Waves className="h-4 w-4" />}
                  onClick={() => {
                    if (!effectiveBatchId) return;
                    evaluateRelease.mutate({
                      batch_id: effectiveBatchId,
                      signal_batch_id: selectedSignal?.id,
                      control_profile_id: selectedControlProfile?.id,
                      locality_profile_id: selectedLocalityProfile?.id,
                      persist: true,
                    });
                  }}
                  loading={evaluateRelease.isPending}
                  disabled={!effectiveBatchId}
                >
                  Evaluate release
                </Button>
                <Button
                  variant="ghost"
                  fullWidth
                  leftIcon={<ArrowRight className="h-4 w-4" />}
                  onClick={() => navigate("/bos/console")}
                >
                  Open decision console
                </Button>
              </div>
            </CardBody>
          </Card>

          <NextBestActionsCard
            items={actionableNextBestActions}
            isLoading={batchGuidance.isLoading && !nextBestActions.length}
            onAction={(item) => handleNextBestAction(item)}
          />

          <Card className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Current release posture"
              description="Current decision grammar, blockers, and checks for the selected batch."
            />
            <CardBody className="space-y-4">
              <div className="assistant-thread-shell rounded-3xl border border-white/8 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={releaseSummary.variant}>{releaseSummary.label}</Badge>
                  {selectedControlProfile ? (
                    <Badge variant="info">{`${selectedControlProfile.name} / ${selectedControlProfile.version}`}</Badge>
                  ) : null}
                </div>
                <p className="mt-3 text-sm leading-6 text-surface-300">{releaseSummary.rationale}</p>
              </div>

              <ListPanel
                title="Blocking factors"
                items={releaseSummary.blockers}
                empty="No blocking factors are active for the current selection."
                tone="warning"
              />
              <ListPanel
                title="Warnings"
                items={releaseSummary.warnings}
                empty="No warning factors are currently attached."
                tone="neutral"
              />
              <ListPanel
                title="Passed checks"
                items={releaseSummary.passedChecks}
                empty="No passed checks have been recorded yet."
                tone="success"
              />
            </CardBody>
          </Card>

          <Card className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Contract and executor"
              description="Keep the active Control-API and execution target visible while qualifying the signal."
            />
            <CardBody className="space-y-4">
              <ContractPanel
                title="Control-API"
                rows={[
                  ["HAL", formatDoseWindow(selectedControlProfile?.hal_min, selectedControlProfile?.hal_max)],
                  ["MTT", selectedControlProfile?.mtt != null ? formatNumber(selectedControlProfile.mtt, 2) : "N/A"],
                  [
                    "Stability",
                    selectedControlProfile?.stability_window_hours != null
                      ? `${formatNumber(selectedControlProfile.stability_window_hours, 1)} h`
                      : "N/A",
                  ],
                ]}
              />
              <ContractPanel
                title="Executor"
                rows={[
                  ["Name", selectedExecutorProfile?.name ?? "No executor"],
                  ["Type", selectedExecutorProfile?.executor_type ?? "N/A"],
                  ["Plugin mode", selectedExecutorProfile?.plugin_mode ?? "N/A"],
                ]}
              />
              <ContractPanel
                title="Locality"
                rows={[
                  ["Name", selectedLocalityProfile?.name ?? "No locality override"],
                  [
                    "Dose shift",
                    selectedLocalityProfile?.dose_window_shift_pct != null
                      ? `${formatNumber(selectedLocalityProfile.dose_window_shift_pct, 1)}%`
                      : "N/A",
                  ],
                  [
                    "MTT shift",
                    selectedLocalityProfile?.mtt_shift_pct != null
                      ? `${formatNumber(selectedLocalityProfile.mtt_shift_pct, 1)}%`
                      : "N/A",
                  ],
                ]}
              />
            </CardBody>
          </Card>

          <PortabilityRecommendationCard
            recommendation={portabilityRecommendation.data}
            isLoading={portabilityRecommendation.isLoading}
            emptyMessage="Select a signal and executor to preview the current portability posture."
          />

          <Card className="assistant-aside-card rounded-[28px]">
            <CardHeader
              title="Portability evidence rail"
              description="Persisted portability evidence filtered to the current batch, signal, and executor context."
            />
            <CardBody className="space-y-3">
              {matchingPortabilityAudits.length ? (
                <Table>
                  <TableHead>
                    <tr>
                      <TableHeaderCell>Outcome</TableHeaderCell>
                      <TableHeaderCell>Signal</TableHeaderCell>
                      <TableHeaderCell>Executor</TableHeaderCell>
                      <TableHeaderCell>Locality</TableHeaderCell>
                      <TableHeaderCell align="right">Score</TableHeaderCell>
                      <TableHeaderCell align="right">Retuning</TableHeaderCell>
                      <TableHeaderCell align="right">Recorded</TableHeaderCell>
                    </tr>
                  </TableHead>
                  <TableBody>
                    {matchingPortabilityAudits.map((item) => (
                      <TableRow
                        key={item.id}
                        onClick={() => {
                          setSelectedSignalId(item.signal_batch_id);
                          setSelectedExecutorProfileId(item.executor_profile_id);
                          setSelectedLocalityProfileId(item.locality_profile_id ?? undefined);
                        }}
                      >
                        <TableCell>
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant={recommendationVariant(item.outcome)}>{item.outcome}</Badge>
                            {item.recommended_outcome ? (
                              <Badge variant="info">{item.recommended_outcome}</Badge>
                            ) : null}
                            {item.requires_requalification ? (
                              <Badge variant="danger">Requalify</Badge>
                            ) : null}
                          </div>
                          {item.rationale ? (
                            <p className="mt-2 max-w-sm text-xs leading-5 text-surface-400">{item.rationale}</p>
                          ) : null}
                        </TableCell>
                        <TableCell>
                          <div>
                            <p className="font-medium text-white">{item.signalLabel}</p>
                            <p className="mt-1 text-xs text-surface-400">audit #{item.id}</p>
                          </div>
                        </TableCell>
                        <TableCell>{item.executorLabel}</TableCell>
                        <TableCell>{item.localityLabel}</TableCell>
                        <TableCell align="right">
                          {item.portability_score != null ? formatPercent(item.portability_score, 0) : "N/A"}
                        </TableCell>
                        <TableCell align="right">
                          <div className="space-y-1">
                            <p>{item.retuning_required ? "Yes" : "No"}</p>
                            <p className="text-xs text-surface-500">
                              {item.retuning_magnitude != null ? formatNumber(item.retuning_magnitude, 3) : "N/A"}
                            </p>
                          </div>
                        </TableCell>
                        <TableCell align="right">{formatDateTime(item.created_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="assistant-aside-card rounded-3xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
                  No persisted portability audit matches the current signal yet.
                </div>
              )}
              {matchingPortabilityAudits.length ? (
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm text-surface-300">
                  Click a row to focus the lab on that persisted audit context.
                </div>
              ) : null}
              {matchingPortabilityAudits.length ? (
                <div className="space-y-2">
                  <p className="assistant-section-kicker">Current portability posture</p>
                  {matchingPortabilityAudits.slice(0, 2).map((item) => (
                    <div
                      key={`posture-${item.id}`}
                      className="rounded-2xl border border-white/8 bg-surface-900/70 px-4 py-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={recommendationVariant(item.recommended_outcome ?? item.outcome)}>
                          {item.recommended_outcome ?? item.outcome}
                        </Badge>
                        {item.requires_requalification ? (
                          <Badge variant="danger">Requalification required</Badge>
                        ) : item.retuning_axes?.length ? (
                          <Badge variant="warning">Retuning required</Badge>
                        ) : (
                          <Badge variant="success">Proceed</Badge>
                        )}
                      </div>
                      {item.rationale ? (
                        <p className="mt-3 text-sm leading-6 text-surface-300">{item.rationale}</p>
                      ) : null}
                      {item.recommended_action ? (
                        <div className="mt-3 rounded-2xl border border-white/8 bg-white/5 px-3 py-3 text-sm text-surface-200">
                          {item.recommended_action}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
              {matchingPortabilityAudits.some((item) => item.notes) ? (
                <div className="space-y-2">
                  <p className="assistant-section-kicker">Operator notes</p>
                  {matchingPortabilityAudits
                    .filter((item) => item.notes)
                    .map((item) => (
                      <div
                        key={`note-${item.id}`}
                        className="rounded-2xl border border-white/8 bg-surface-900/70 px-4 py-3 text-sm text-surface-300"
                      >
                        <span className="font-medium text-white">{item.signalLabel}</span>
                        {" - "}
                        {item.notes}
                      </div>
                    ))}
                </div>
              ) : null}
            </CardBody>
          </Card>

          <AuditExportCard
            hasAuditPacket={Boolean(selectedAuditPacket)}
            generatedAt={selectedAuditPacket?.generated_at ?? null}
            onExport={(format) => {
              if (!effectiveBatchId) return;
              exportAuditPacket.mutate({ batchId: effectiveBatchId, format });
            }}
            exportingFormat={exportAuditPacket.isPending ? exportAuditPacket.variables?.format ?? null : null}
          />

          {selectedAuditPacket ? (
            <Button
              variant="outline"
              fullWidth
              leftIcon={<ArrowRight className="h-4 w-4" />}
              onClick={() => navigate(`/bos/console?auditPacketId=${selectedAuditPacket.id}`)}
            >
              Open audit packet detail
            </Button>
          ) : null}

          {effectiveBatchId ? (
            <Button
              variant="secondary"
              fullWidth
              leftIcon={<ArrowRight className="h-4 w-4" />}
              onClick={() => navigate(`/batches/${effectiveBatchId}`)}
            >
              Open batch command center
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function VisionObservationReviewCard({ signal }: { signal?: SignalBatch | null }) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const detection = useVisionDetection();
  const attachObservation = useAttachVisionObservation();
  const recentRuns = useVisionRuns(3);
  const result = detection.data ?? recentRuns.data?.[0] ?? null;
  const observation = result?.observation ?? null;
  const resultWarnings = result?.warnings ?? [];
  const attachedObservation = signal?.qc_markers?.vision_observation ?? null;

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return (
    <Card className="assistant-aside-card rounded-[28px]">
      <CardHeader
        title="Vision observation review"
        description="Upload one image, run detection, and review the structured BOS observation before any downstream automation."
      />
      <CardBody className="space-y-4">
        <div className="assistant-thread-shell rounded-3xl border border-white/8 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">Phase 1 detection</Badge>
            <Badge variant="warning">Operator review only</Badge>
            {result ? (
              <Badge variant={result.fallback_used ? "warning" : "success"}>
                {result.model_status}
              </Badge>
            ) : null}
          </div>
          <p className="mt-3 text-sm leading-6 text-surface-300">
            This review surface does not execute the supervisor. It only prepares a structured observation that an operator can inspect.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
          <div className="space-y-3">
            <Input
              label="Image upload"
              type="file"
              accept="image/*"
              helperText="Single-image detection only. Video and segmentation are out of scope for phase 1."
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
              }}
            />
            <Button
              fullWidth
              leftIcon={<Sparkles className="h-4 w-4" />}
              loading={detection.isPending}
              disabled={!file}
              onClick={() => {
                if (file) detection.mutate(file);
              }}
            >
              Run detection review
            </Button>
            <Button
              fullWidth
              variant="secondary"
              leftIcon={<ArrowRight className="h-4 w-4" />}
              loading={attachObservation.isPending}
              disabled={!result?.run_id || !signal?.id}
              onClick={() => {
                if (result?.run_id && signal?.id) {
                  attachObservation.mutate({ runId: result.run_id, signalBatchId: signal.id });
                }
              }}
            >
              Attach reviewed observation
            </Button>
            {previewUrl ? (
              <div className="overflow-hidden rounded-3xl border border-white/8 bg-black/20">
                <img src={previewUrl} alt="Uploaded vision frame" className="max-h-72 w-full object-contain" />
              </div>
            ) : (
              <div className="rounded-3xl border border-dashed border-white/10 bg-white/3 px-4 py-10 text-center text-sm text-surface-400">
                Upload an image to preview the frame before detection.
              </div>
            )}
          </div>

          <div className="space-y-4">
            {attachedObservation ? (
              <div className="assistant-aside-card rounded-3xl border border-emerald-400/15 bg-emerald-500/10 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="success">Attached to signal</Badge>
                  <Badge variant="neutral">{attachedObservation.image_id}</Badge>
                  {attachedObservation.dominant_label ? (
                    <Badge variant="info">{attachedObservation.dominant_label}</Badge>
                  ) : null}
                </div>
                <p className="mt-3 text-sm leading-6 text-emerald-100">
                  {attachedObservation.observation_summary}
                </p>
              </div>
            ) : null}
            {observation ? (
              <>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <VisionMetricTile label="Image ID" value={observation.image_id} />
                  <VisionMetricTile label="Dominant label" value={observation.dominant_label ?? "None"} />
                  <VisionMetricTile label="Confidence" value={formatPercent(observation.confidence_mean, 0)} />
                  <VisionMetricTile label="Anomaly" value={observation.anomaly_flag ? "Yes" : "No"} />
                </div>

                <div className="assistant-aside-card rounded-3xl border border-white/8 p-4">
                  <p className="assistant-section-kicker">Structured observation preview</p>
                  <p className="mt-3 text-sm leading-6 text-surface-300">{observation.observation_summary}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Badge variant="info">{`${observation.detections.length} detections`}</Badge>
                    <Badge variant="neutral">
                      {`coverage ${formatPercent(observation.bbox_coverage_ratio, 0)}`}
                    </Badge>
                    {observation.detected_classes.map((item) => (
                      <Badge key={item} variant="brand">
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>

                {observation.detections.length ? (
                  <Table>
                    <TableHead>
                      <tr>
                        <TableHeaderCell>Label</TableHeaderCell>
                        <TableHeaderCell align="right">Confidence</TableHeaderCell>
                        <TableHeaderCell>BBox</TableHeaderCell>
                      </tr>
                    </TableHead>
                    <TableBody>
                      {observation.detections.map((item, index) => (
                        <TableRow key={`${item.label}-${index}`}>
                          <TableCell>{item.label}</TableCell>
                          <TableCell align="right">{formatPercent(item.confidence, 0)}</TableCell>
                          <TableCell>{item.bbox.map((value) => formatNumber(value, 1)).join(", ")}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="rounded-3xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
                    No detection boxes are available for this observation.
                  </div>
                )}

                {resultWarnings.length ? (
                  <div className="flex flex-wrap gap-2">
                    {resultWarnings.map((warning) => (
                      <Badge key={warning} variant="warning">
                        {warning}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </>
            ) : (
              <div className="rounded-3xl border border-dashed border-white/10 bg-white/3 px-4 py-12 text-center text-sm text-surface-400">
                Run detection to see the BOS-ready observation fields here.
              </div>
            )}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

function VisionMetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="assistant-meta-panel rounded-2xl border border-white/8 bg-surface-900/70 px-4 py-3">
      <p className="assistant-section-kicker !text-surface-500">{translateText(label)}</p>
      <p className="mt-2 truncate text-sm font-medium text-white">{value}</p>
    </div>
  );
}

function ListPanel({
  title,
  items,
  empty,
  tone,
}: {
  title: string;
  items: string[];
  empty: string;
  tone: "success" | "warning" | "neutral";
}) {
  const toneClass =
    tone === "success"
      ? "border-emerald-400/15 bg-emerald-500/10 text-emerald-100"
      : tone === "warning"
        ? "border-amber-400/15 bg-amber-500/10 text-amber-100"
        : "border-white/8 bg-white/5 text-surface-300";

  return (
    <div className="space-y-2">
      <p className="assistant-section-kicker">{title}</p>
      {items.length ? (
        items.map((item) => (
          <div key={item} className={`rounded-2xl border px-4 py-3 text-sm ${toneClass}`}>
            {item}
          </div>
        ))
      ) : (
        <div className="rounded-2xl border border-dashed border-white/10 bg-white/3 px-4 py-6 text-sm text-surface-400">
          {empty}
        </div>
      )}
    </div>
  );
}

function ContractPanel({
  title,
  rows,
}: {
  title: string;
  rows: Array<[string, string]>;
}) {
  return (
    <div className="assistant-aside-card rounded-3xl border border-white/8 p-4">
      <p className="assistant-section-kicker">{title}</p>
      <dl className="mt-4 space-y-3">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-3 text-sm">
            <dt className="text-surface-400">{label}</dt>
            <dd className="text-right font-medium text-white">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function resolveMechanisticContext(
  signal: SignalBatch | null,
  packet: AuditPacket | null,
): MechanisticContext | null {
  const signalContext = signal?.qc_markers?.compile_context?.mechanistic_context;
  if (signalContext) return signalContext;
  if (!packet) return null;
  return getAuditPacketReadModel(packet).mechanisticContext;
}

function packetMatchesSignal(packet: AuditPacket, signal: SignalBatch | null): boolean {
  if (!signal) return true;
  return packet.packet?.signal_batch?.id === signal.id;
}

function getReleaseSummary(
  packetView: ReturnType<typeof getAuditPacketReadModel> | null,
  decision: {
    decision?: string | null;
    rationale?: string | null;
    blocking_factors?: string[] | null;
    warning_factors?: string[] | null;
    passed_checks?: string[] | null;
    decision_confidence?: number | null;
  } | null,
) {
  if (packetView) {
    return {
      label: packetView.readinessLabel,
      variant:
        packetView.readinessTone === "success"
          ? ("success" as const)
          : packetView.readinessTone === "danger"
            ? ("danger" as const)
            : ("warning" as const),
      rationale: packetView.rationale,
      blockers: packetView.blockingFactors,
      warnings: packetView.warningFactors,
      passedChecks: packetView.passedChecks,
      confidence: packetView.decisionConfidence != null ? formatPercent(packetView.decisionConfidence, 0) : "N/A",
      hint: packetView.controlLabel,
    };
  }

  const rawDecision = decision?.decision ?? "INSUFFICIENT_EVIDENCE";
  return {
    label: rawDecision,
    variant: recommendationVariant(rawDecision),
    rationale: decision?.rationale ?? "No release decision has been persisted for this batch yet.",
    blockers: decision?.blocking_factors ?? [],
    warnings: decision?.warning_factors ?? [],
    passedChecks: decision?.passed_checks ?? [],
    confidence: decision?.decision_confidence != null ? formatPercent(decision.decision_confidence, 0) : "N/A",
    hint: "Awaiting audit packet",
  };
}

function formatDoseWindow(min?: number | null, max?: number | null) {
  if (min == null && max == null) return "N/A";
  if (min != null && max != null) return `${formatNumber(min, 2)} - ${formatNumber(max, 2)}`;
  if (min != null) return `>= ${formatNumber(min, 2)}`;
  return `<= ${formatNumber(max, 2)}`;
}

function freshnessVariant(value?: string | null) {
  const normalized = value?.toLowerCase() ?? "";
  if (normalized.includes("fresh")) return "success" as const;
  if (normalized.includes("stable")) return "warning" as const;
  if (normalized.includes("stale")) return "danger" as const;
  return "neutral" as const;
}

function recommendationVariant(value?: string | null) {
  if (value === "PASS" || value === "Ready") return "success" as const;
  if (value === "PASS_WITH_RETUNING" || value === "Retune") return "warning" as const;
  if (value === "FAIL" || value === "Blocked") return "danger" as const;
  return "warning" as const;
}

function readNumericParam(value: string | null) {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}
