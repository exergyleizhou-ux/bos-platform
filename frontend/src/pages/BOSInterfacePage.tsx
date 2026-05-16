import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  CirclePlus,
  Cpu,
  Eye,
  MapPin,
  RefreshCcw,
  Shield,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import toast from "react-hot-toast";

import { AuditExportCard } from "@/components/bos/AuditExportCard";
import { MechanisticContextCard } from "@/components/bos/MechanisticContextCard";
import { NativeModelRuntimeCard } from "@/components/bos/NativeModelRuntimeCard";
import { NativeModelStackCard } from "@/components/bos/NativeModelStackCard";
import { PortabilityRecommendationCard } from "@/components/bos/PortabilityRecommendationCard";
import { SupervisorHistoryCard } from "@/components/bos/SupervisorHistoryCard";
import { SignalSupervisorPanel } from "@/components/bos/SignalSupervisorPanel";
import { SupervisorSnapshotCard } from "@/components/bos/SupervisorSnapshotCard";
import {
  useAuditPackets,
  useCompileSignal,
  useControlProfiles,
  useCreateControlProfile,
  useCreateExecutorProfile,
  useCreateLocalityProfile,
  useCreatePortabilityAudit,
  useCreateSignalBatch,
  useExecutorProfiles,
  useEvaluateRelease,
  useExportAuditPacket,
  useFeedstocksCatalog,
  useManuscriptCampaigns,
  useNativeModels,
  useLocalityProfiles,
  usePortabilityAudits,
  usePortabilityRecommendation,
  useRefreshSignal,
  useReleaseDecisions,
  useSignalBatches,
  useSpeciesCatalog,
} from "@/hooks/useBos";
import { useBatchList } from "@/hooks/useBatches";
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
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { Textarea } from "@/components/ui/Textarea";
import {
  getAuditPacketReadModel,
  summarizeAuditPackets,
} from "@/lib/bos-read-model";
import { collectApiErrorDetails } from "@/lib/apiError";
import { translateText } from "@/lib/i18n";
import { formatDateTime, formatNumber, formatPercent } from "@/lib/utils";
import { useI18n } from "@/providers/I18nProvider";
import type { AuditPacket, MechanisticContext, SignalBatch } from "@/types/bos";

const INVALID_JSON = Symbol("invalid-json");

export default function BOSInterfacePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useI18n();
  const signals = useSignalBatches();
  const controlProfiles = useControlProfiles();
  const localityProfiles = useLocalityProfiles();
  const executorProfiles = useExecutorProfiles();
  const portability = usePortabilityAudits();
  const auditPackets = useAuditPackets();
  const releaseDecisions = useReleaseDecisions();
  const batches = useBatchList(1, 100);
  const speciesCatalog = useSpeciesCatalog();
  const feedstocksCatalog = useFeedstocksCatalog();
  const manuscriptCampaigns = useManuscriptCampaigns();
  const latestBatchIdForModelStack = (signals.data ?? [])[0]?.batch_id ?? batches.data?.items?.[0]?.id;
  const nativeModels = useNativeModels(latestBatchIdForModelStack);
  const createSignal = useCreateSignalBatch();
  const createControlProfile = useCreateControlProfile();
  const createLocalityProfile = useCreateLocalityProfile();
  const createExecutorProfile = useCreateExecutorProfile();
  const createPortabilityAudit = useCreatePortabilityAudit();
  const evaluateRelease = useEvaluateRelease();
  const exportAuditPacket = useExportAuditPacket();
  const compileSignal = useCompileSignal();
  const refreshSignal = useRefreshSignal();

  const [signalModalOpen, setSignalModalOpen] = useState(false);
  const [controlModalOpen, setControlModalOpen] = useState(false);
  const [localityModalOpen, setLocalityModalOpen] = useState(false);
  const [executorModalOpen, setExecutorModalOpen] = useState(false);
  const [portabilityModalOpen, setPortabilityModalOpen] = useState(false);
  const initialAuditPacketId = Number(searchParams.get("auditPacketId") ?? "");
  const [selectedAuditPacketId, setSelectedAuditPacketId] = useState<number | null>(
    Number.isFinite(initialAuditPacketId) && initialAuditPacketId > 0 ? initialAuditPacketId : null,
  );
  const [releaseModalOpen, setReleaseModalOpen] = useState(false);
  const [signalForm, setSignalForm] = useState({
    batch_id: "",
    signal_api_version: "SIG-1.0",
    compiled_signal_id: "",
    potency: "",
    potency_unit: "SER-equivalent",
    dose_window_min: "",
    dose_window_max: "",
    stability_window_hours: "",
    freshness_state: "Fresh",
    notes: "",
  });
  const [controlForm, setControlForm] = useState({
    name: "",
    version: "CTRL-1.0",
    mtt: "",
    hal_min: "",
    hal_max: "",
    dose_window_min: "",
    dose_window_max: "",
    stability_window_hours: "",
    notes: "",
  });
  const [localityForm, setLocalityForm] = useState({
    name: "",
    site_code: "",
    substrate_class: "",
    waste_state: "",
    pretreat_flags: "",
    dose_window_shift_pct: "",
    mtt_shift_pct: "",
    notes: "",
    active: "true",
  });
  const [executorForm, setExecutorForm] = useState({
    locality_profile_id: "",
    executor_code: "",
    name: "",
    executor_type: "",
    hal_min: "",
    hal_max: "",
    mtt_nominal: "",
    plugin_mode: "",
    notes: "",
    active: "true",
  });
  const [portabilityForm, setPortabilityForm] = useState({
    signal_batch_id: "",
    executor_profile_id: "",
    locality_profile_id: "",
    outcome: "PASS",
    retuning_required: "false",
    trigger_metrics: "",
    notes: "",
  });
  const [releaseForm, setReleaseForm] = useState({
    batch_id: "",
    signal_batch_id: "",
    control_profile_id: "",
    locality_profile_id: "",
  });

  const portabilityRecommendation = usePortabilityRecommendation(
    portabilityForm.signal_batch_id ? Number(portabilityForm.signal_batch_id) : undefined,
    portabilityForm.executor_profile_id ? Number(portabilityForm.executor_profile_id) : undefined,
    portabilityForm.locality_profile_id ? Number(portabilityForm.locality_profile_id) : undefined,
  );

  const { summary, localityMap, packetPortabilityFeed, packetViews } = useMemo(() => {
    const controlItems = controlProfiles.data ?? [];
    const localityItems = localityProfiles.data ?? [];
    const executorItems = executorProfiles.data ?? [];
    const auditItems = auditPackets.data ?? [];
    const packetSummary = summarizeAuditPackets(auditItems);

    return {
      summary: {
        signals: packetSummary.summary.packets,
        freshSignals: packetSummary.summary.freshSignals,
        controlProfiles: controlItems.length,
        localityProfiles: localityItems.length,
        executorProfiles: executorItems.length,
        releaseDecisions: packetSummary.summary.packets,
        portabilityPassRate: packetSummary.summary.passRate,
        auditPackets: packetSummary.summary.packets,
      },
      localityMap: new Map(localityItems.map((item) => [item.id, item])),
      packetPortabilityFeed: packetSummary.portabilityAudits,
      packetViews: packetSummary.views,
    };
  }, [
    controlProfiles.data,
    localityProfiles.data,
    executorProfiles.data,
    auditPackets.data,
  ]);

  async function handleCreateLocality() {
    const wasteState = parseOptionalJsonObject(localityForm.waste_state, "Waste state");
    const pretreatFlags = parseOptionalJsonObject(
      localityForm.pretreat_flags,
      "Pretreat flags",
    );
    if (wasteState === INVALID_JSON || pretreatFlags === INVALID_JSON) return;

    await createLocalityProfile.mutateAsync({
      name: localityForm.name,
      site_code: localityForm.site_code || undefined,
      substrate_class: localityForm.substrate_class || undefined,
      waste_state: wasteState || undefined,
      pretreat_flags: pretreatFlags || undefined,
      dose_window_shift_pct: parseOptionalNumber(localityForm.dose_window_shift_pct),
      mtt_shift_pct: parseOptionalNumber(localityForm.mtt_shift_pct),
      notes: localityForm.notes || undefined,
      active: localityForm.active === "true",
    });

    setLocalityModalOpen(false);
    setLocalityForm({
      name: "",
      site_code: "",
      substrate_class: "",
      waste_state: "",
      pretreat_flags: "",
      dose_window_shift_pct: "",
      mtt_shift_pct: "",
      notes: "",
      active: "true",
    });
  }

  async function handleCreateExecutor() {
    await createExecutorProfile.mutateAsync({
      locality_profile_id: executorForm.locality_profile_id
        ? Number(executorForm.locality_profile_id)
        : undefined,
      executor_code: executorForm.executor_code,
      name: executorForm.name,
      executor_type: executorForm.executor_type || undefined,
      hal_min: parseOptionalNumber(executorForm.hal_min),
      hal_max: parseOptionalNumber(executorForm.hal_max),
      mtt_nominal: parseOptionalNumber(executorForm.mtt_nominal),
      plugin_mode: executorForm.plugin_mode || undefined,
      notes: executorForm.notes || undefined,
      active: executorForm.active === "true",
    });

    setExecutorModalOpen(false);
    setExecutorForm({
      locality_profile_id: "",
      executor_code: "",
      name: "",
      executor_type: "",
      hal_min: "",
      hal_max: "",
      mtt_nominal: "",
      plugin_mode: "",
      notes: "",
      active: "true",
    });
  }

  async function handleCreatePortabilityAudit() {
    const triggerMetrics = parseOptionalJsonObject(
      portabilityForm.trigger_metrics,
      "Trigger metrics",
    );
    if (triggerMetrics === INVALID_JSON) return;

    await createPortabilityAudit.mutateAsync({
      signal_batch_id: Number(portabilityForm.signal_batch_id),
      executor_profile_id: Number(portabilityForm.executor_profile_id),
      locality_profile_id: portabilityForm.locality_profile_id
        ? Number(portabilityForm.locality_profile_id)
        : undefined,
      outcome: portabilityForm.outcome,
      retuning_required: portabilityForm.retuning_required === "true",
      notes: portabilityForm.notes || undefined,
      trigger_metrics: triggerMetrics || undefined,
    });

    setPortabilityModalOpen(false);
    setPortabilityForm({
      signal_batch_id: "",
      executor_profile_id: "",
      locality_profile_id: "",
      outcome: "PASS",
      retuning_required: "false",
      trigger_metrics: "",
      notes: "",
    });
  }

  const isLoading =
    signals.isLoading ||
    controlProfiles.isLoading ||
    localityProfiles.isLoading ||
    executorProfiles.isLoading ||
    releaseDecisions.isLoading ||
    portability.isLoading ||
    auditPackets.isLoading ||
    nativeModels.isLoading;
  const isError =
    signals.isError ||
    controlProfiles.isError ||
    localityProfiles.isError ||
    executorProfiles.isError ||
    releaseDecisions.isError ||
    portability.isError ||
    auditPackets.isError ||
    nativeModels.isError;
  const selectedAuditPacket =
    (auditPackets.data ?? []).find((packet) => packet.id === selectedAuditPacketId) ?? null;
  const selectedAuditPacketView = selectedAuditPacket
    ? getAuditPacketReadModel(selectedAuditPacket)
    : null;
  const latestAuditPacket = (auditPackets.data ?? [])[0] ?? null;
  const latestAuditPacketView = latestAuditPacket ? getAuditPacketReadModel(latestAuditPacket) : null;
  const auditPacketForExport = selectedAuditPacket ?? latestAuditPacket;
  const auditPacketForExportView = selectedAuditPacketView ?? latestAuditPacketView;
  const latestDecisionConfidence = latestAuditPacketView?.decisionConfidence ?? null;
  const latestContractStatus =
    typeof latestAuditPacket?.contract_evaluation?.status === "string"
      ? latestAuditPacket.contract_evaluation.status
      : "unknown";
  const latestThresholdBreaches = latestAuditPacket?.contract_evaluation?.threshold_breaches ?? [];
  const latestSourceMode = latestAuditPacket?.packet?.generation_context?.source_mode ?? null;
  const latestSignalStatus =
    typeof latestAuditPacket?.signal_validity?.status === "string"
      ? latestAuditPacket.signal_validity.status
      : "unknown";
  const latestRecommendation = Array.isArray(latestAuditPacket?.retuning_axes?.recommended_by_portability)
    ? latestAuditPacket.retuning_axes.recommended_by_portability[0]
    : null;
  const latestSignal = (signals.data ?? [])[0] ?? null;
  const latestMechanisticContext = extractMechanisticContext(latestSignal, latestAuditPacket);
  const latestSignalLabel = latestSignal?.compiled_signal_id ?? latestAuditPacketView?.signalLabel ?? null;
  const errorDetails = useMemo(
    () =>
      collectApiErrorDetails([
        { label: "Signals", error: signals.isError ? signals.error : null },
        { label: "Control profiles", error: controlProfiles.isError ? controlProfiles.error : null },
        { label: "Locality profiles", error: localityProfiles.isError ? localityProfiles.error : null },
        { label: "Executor profiles", error: executorProfiles.isError ? executorProfiles.error : null },
        { label: "Release decisions", error: releaseDecisions.isError ? releaseDecisions.error : null },
        { label: "Portability audits", error: portability.isError ? portability.error : null },
        { label: "Audit packets", error: auditPackets.isError ? auditPackets.error : null },
        { label: "Native models", error: nativeModels.isError ? nativeModels.error : null },
      ]),
    [
      auditPackets.error,
      auditPackets.isError,
      controlProfiles.error,
      controlProfiles.isError,
      executorProfiles.error,
      executorProfiles.isError,
      localityProfiles.error,
      localityProfiles.isError,
      nativeModels.error,
      nativeModels.isError,
      portability.error,
      portability.isError,
      releaseDecisions.error,
      releaseDecisions.isError,
      signals.error,
      signals.isError,
    ],
  );

  if (isLoading) return <SpinnerOverlay label={t("Loading BOS Code decision center")} />;
  if (isError) {
    return (
      <ErrorState
        title="Decision console unavailable"
        description="One or more BOS control-plane requests failed while loading this view."
        details={errorDetails}
        onRetry={() => {
          void signals.refetch();
          void controlProfiles.refetch();
          void localityProfiles.refetch();
          void executorProfiles.refetch();
          void releaseDecisions.refetch();
          void portability.refetch();
          void auditPackets.refetch();
          void nativeModels.refetch();
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
              <CockpitSectionLabel>{t("BOS Code Decision Center")}</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                {t("Signal, contract, release, portability, and audit")}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                {t(
                  "Operator-facing write and review surface for BOS Code: released signals, active contracts, executor and locality profiles, portability outcomes, and compiled audit packets.",
                )}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="success">{t("Protocol-first")}</Badge>
              <Button
                variant="secondary"
                leftIcon={<CirclePlus className="h-4 w-4" />}
                onClick={() => setSignalModalOpen(true)}
              >
                {translateText("New signal")}
              </Button>
              <Button
                variant="outline"
                leftIcon={<ShieldCheck className="h-4 w-4" />}
                onClick={() => setReleaseModalOpen(true)}
              >
                {translateText("Evaluate release")}
              </Button>
              <Button
                variant="ghost"
                leftIcon={<ArrowRight className="h-4 w-4" />}
                onClick={() => {
                  const latestSignalId = latestSignal?.id;
                  const latestBatchId = latestSignal?.batch_id ?? batches.data?.items?.[0]?.id;
                  const latestControlProfileId = controlProfiles.data?.[0]?.id;
                  const params = new URLSearchParams();
                  if (latestBatchId) params.set("batchId", String(latestBatchId));
                  if (latestSignalId) params.set("signalId", String(latestSignalId));
                  if (latestControlProfileId) params.set("controlProfileId", String(latestControlProfileId));
                  navigate(`/bos/signal-lab${params.toString() ? `?${params.toString()}` : ""}`);
                }}
              >
                {translateText("Open signal lab")}
              </Button>
              <Button
                variant="outline"
                leftIcon={<ArrowRight className="h-4 w-4" />}
                onClick={() => navigate("/bos/references")}
              >
                {translateText("Open reference atlas")}
              </Button>
            </div>
          </div>

          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-5">
            <CockpitMetric
              label={t("Signals")}
              value={String(summary.signals)}
              hint={`${summary.freshSignals} ${t("currently fresh")}`}
              accent="cyan"
            />
            <CockpitMetric
              label={t("Control contracts")}
              value={String(summary.controlProfiles)}
              hint={translateText("Persisted Control-API versions")}
              accent="violet"
            />
            <CockpitMetric
              label={t("Executor / locality")}
              value={`${summary.executorProfiles} / ${summary.localityProfiles}`}
              hint={translateText("Active portability environment")}
              accent="neutral"
            />
            <CockpitMetric
              label={t("Portability pass rate")}
              value={summary.portabilityPassRate != null ? formatPercent(summary.portabilityPassRate, 1) : translateText("N/A")}
              hint={translateText("Recommend release and release-with-retuning outcomes")}
              accent="amber"
            />
            <CockpitMetric
              label={t("Audit packets")}
              value={String(summary.auditPackets)}
              hint={`${summary.releaseDecisions} ${t("release decisions persisted")}`}
              accent="neutral"
            />
          </CockpitGrid>
        </div>
      </CockpitPanel>

      <NativeModelStackCard catalog={nativeModels.data ?? null} />

      <NativeModelRuntimeCard batchId={latestBatchIdForModelStack} />

      <CockpitPanel tone="emphasis" className="p-5 lg:p-6">
        <div>
          <CockpitSectionLabel>{translateText("Decision summary rail")}</CockpitSectionLabel>
          <p className="mt-3 text-sm leading-7 text-surface-300">
            {translateText("Latest contract, evidence, release, and portability posture for BOS Code decision review.")}
          </p>
        </div>
        <div className="mt-5 space-y-4">
          {latestAuditPacket && latestAuditPacketView ? (
            <>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                <MiniMetric label="Release" value={formatDecisionLabel(latestAuditPacketView.releaseDecision)} />
                <MiniMetric label="Decision confidence" value={formatPercent(latestDecisionConfidence, 0)} />
                <MiniMetric label="Contract status" value={formatContractStatusLabel(latestContractStatus)} />
                <MiniMetric label="Signal validity" value={formatSignalStatusLabel(latestSignalStatus)} />
                <MiniMetric
                  label="Current portability posture"
                  value={
                    latestRecommendation
                      ? formatRecommendationLabel(latestRecommendation.recommended_outcome)
                      : t("Awaiting portability posture")
                  }
                />
              </div>
              <div className="grid gap-4 xl:grid-cols-[1.18fr_0.82fr]">
                <div className="assistant-thread-shell rounded-3xl border border-white/8 p-5">
                  <div className="flex items-center gap-2">
                    <Shield className="h-4 w-4 text-brand-200" />
                    <p className="assistant-section-kicker !text-surface-300">
                      {t("Decision rationale")}
                    </p>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-surface-300">{latestAuditPacketView.rationale}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {latestAuditPacketView.blockingFactors.map((item) => (
                      <Badge key={item} variant="danger">{item}</Badge>
                    ))}
                    {latestAuditPacketView.warningFactors.map((item) => (
                      <Badge key={item} variant="warning">{item}</Badge>
                    ))}
                    {latestAuditPacketView.passedChecks.map((item) => (
                      <Badge key={item} variant="success">{item}</Badge>
                    ))}
                  </div>
                </div>
                <div className="assistant-aside-card rounded-3xl border border-white/8 p-5">
                  <p className="assistant-section-kicker">{t("Current portability posture")}</p>
                  <p className="mt-3 text-sm leading-6 text-surface-300">
                    {latestRecommendation
                      ? latestRecommendation.rationale ??
                        formatRecommendationPreview(
                          latestRecommendation.recommended_outcome,
                          latestRecommendation.retuning_axes?.length ?? 0,
                        )
                      : t("Complete one portability check first to see a clearer portability posture.")}
                  </p>
                  {latestRecommendation ? (
                    <div className="mt-3 rounded-2xl border border-white/8 bg-white/5 px-3 py-3 text-sm text-surface-200">
                      {latestRecommendation.recommended_action ??
                        formatRecommendationAction(
                          latestRecommendation.recommended_outcome,
                          latestRecommendation.retuning_axes ?? [],
                        )}
                    </div>
                  ) : null}
                  {latestRecommendation?.requires_requalification ? (
                    <div className="mt-3">
                      <Badge variant="danger">{t("Requalification required")}</Badge>
                    </div>
                  ) : null}
                  {latestRecommendation?.retuning_axes?.length ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {latestRecommendation.retuning_axes.map((axis: string) => (
                        <Badge key={axis} variant="info">{axis}</Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            </>
          ) : (
            <div className="rounded-2xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-sm text-surface-400">
              {t(
                "No audit packet exists yet. Create a signal, run portability, and evaluate release to populate the decision rail.",
              )}
            </div>
          )}
        </div>
      </CockpitPanel>

      <MechanisticContextCard
        context={latestMechanisticContext}
        signalLabel={latestSignalLabel}
      />

      <SignalSupervisorPanel signal={latestSignal} />

      <SupervisorHistoryCard history={latestSignal?.qc_markers?.supervisor_history ?? null} />

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="assistant-aside-card rounded-[28px]">
          <CardHeader
            title="Released signals"
            description="Signal-API objects with potency, freshness, and release windows."
            action={
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<Sparkles className="h-4 w-4" />}
                  onClick={() => setSignalModalOpen(true)}
                >
                  Compile from batch
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<RefreshCcw className="h-4 w-4" />}
                  onClick={() => {
                    if (latestSignal) {
                      refreshSignal.mutate(latestSignal.id);
                    }
                  }}
                  loading={refreshSignal.isPending}
                  disabled={!latestSignal}
                >
                  Refresh latest
                </Button>
              </div>
            }
          />
          <CardBody className="space-y-3">
            {packetViews.length ? (
              packetViews.slice(0, 6).map((packet) => (
                <div key={packet.id} className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-white">
                        {packet.signalLabel}
                      </p>
                      <p className="mt-1 text-xs text-surface-400">
                        {packet.packetVersion} / {packet.batchLabel}
                      </p>
                    </div>
                    <Badge variant={freshnessVariant(packet.signalFreshness)}>
                      {packet.signalFreshness}
                    </Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Badge variant={signalStatusVariant(packet.signalStatus)}>
                      {formatSignalStatusLabel(packet.signalStatus)}
                    </Badge>
                    <Badge variant={decisionVariant(packet.releaseDecision)}>
                      {formatDecisionLabel(packet.releaseDecision)}
                    </Badge>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <MiniMetric label="Potency" value={formatNumber(packet.metrics.potency, 3)} />
                    <MiniMetric
                      label="Decision"
                      value={formatDecisionLabel(packet.releaseDecision)}
                    />
                    <MiniMetric label="Compiled" value={formatDateTime(packet.compiledAt)} />
                  </div>
                </div>
              ))
            ) : (
              <EmptyPanel message="No signal batches have been released yet." />
            )}
          </CardBody>
        </Card>

        <Card className="assistant-aside-card rounded-[28px]">
          <CardHeader
            title="Control contracts"
            description="Versioned Control-API profiles with MTT, HAL, and stability bounds."
          />
          <CardBody className="space-y-3">
            {(auditPackets.data ?? []).length ? (
              auditPackets.data!.slice(0, 6).map((packet) => (
                <div key={packet.id} className="rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-white">
                        {packet.packet?.control_profile?.name ?? t("No control contract")}
                      </p>
                      <p className="mt-1 text-xs text-surface-400">
                        {packet.packet?.control_profile?.version ?? packet.packet_version}
                      </p>
                    </div>
                    <Badge variant="info">
                      {packet.packet?.generation_context?.schema_version ?? packet.packet_version}
                    </Badge>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <MiniMetric label="MTT" value={formatNumber(packet.packet?.control_profile?.mtt, 3)} />
                    <MiniMetric
                      label="Dose window"
                      value={
                        packet.packet?.control_profile?.dose_window_min != null &&
                        packet.packet?.control_profile?.dose_window_max != null
                          ? `${formatNumber(packet.packet.control_profile.dose_window_min, 2)} - ${formatNumber(packet.packet.control_profile.dose_window_max, 2)}`
                          : "N/A"
                      }
                    />
                    <MiniMetric
                      label="Stability"
                      value={
                        packet.packet?.control_profile?.stability_window_hours != null
                          ? `${formatNumber(packet.packet.control_profile.stability_window_hours, 0)} h`
                          : "N/A"
                      }
                    />
                  </div>
                </div>
              ))
            ) : (
              <EmptyPanel message="No Control-API profiles are defined yet." />
            )}
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="assistant-aside-card rounded-[28px]">
          <CardHeader
            title="Reference species and feedstocks"
            description="BOS-ready defaults merged from the manuscript relay and public benchmark sources."
          />
          <CardBody className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <MiniMetric
                label="Species references"
                value={String(speciesCatalog.data?.count ?? 0)}
              />
              <MiniMetric
                label="Feedstock references"
                value={String(feedstocksCatalog.data?.count ?? 0)}
              />
            </div>
            <div className="space-y-3">
              {(speciesCatalog.data?.species ?? []).slice(0, 3).map((item) => (
                <div key={item.code} className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-white">{`${item.code} / ${item.common_name}`}</p>
                      <p className="mt-1 text-xs text-surface-400">{item.scientific_name}</p>
                    </div>
                    <Badge variant="info">{item.source_basis}</Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-surface-300">{item.notes}</p>
                </div>
              ))}
            </div>
            <div className="space-y-3">
              {(feedstocksCatalog.data?.feedstocks ?? []).slice(0, 3).map((item) => (
                <div key={item.key} className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-white">{item.display_name}</p>
                      <p className="mt-1 text-xs text-surface-400">{item.category}</p>
                    </div>
                    <Badge variant={item.contamination_risk === "critical" ? "danger" : item.contamination_risk === "high" ? "warning" : "success"}>
                      {item.contamination_risk}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-surface-300">{item.suitability_notes}</p>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>

        <Card className="assistant-aside-card rounded-[28px]">
          <CardHeader
            title="Manuscript evidence campaigns"
            description="Experimental scenarios extracted from the supplied manuscript and now queryable inside BOS."
          />
          <CardBody className="space-y-3">
            {(manuscriptCampaigns.data?.campaigns ?? []).slice(0, 4).map((item) => (
              <div key={item.key} className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-white">{item.title}</p>
                    <p className="mt-1 text-xs text-surface-400">{item.source_anchor}</p>
                  </div>
                  <Badge variant="brand">{item.evidence_level}</Badge>
                </div>
                <p className="mt-3 text-sm leading-6 text-surface-300">{item.summary}</p>
              </div>
            ))}
          </CardBody>
        </Card>

        <Card className="assistant-aside-card rounded-[28px]">
          <CardHeader
            title="Locality profiles"
            description="Site-level locality shifts and pretreatment assumptions used by portability audits."
            action={
              <Button
                size="sm"
                variant="outline"
                leftIcon={<MapPin className="h-4 w-4" />}
                onClick={() => setLocalityModalOpen(true)}
              >
                New locality
              </Button>
            }
          />
          <CardBody className="space-y-3">
            {(localityProfiles.data ?? []).length ? (
              localityProfiles.data!.slice(0, 6).map((profile) => (
                <div key={profile.id} className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-white">{profile.name}</p>
                      <p className="mt-1 text-xs text-surface-400">
                        {profile.site_code ?? t("No site code")} / {profile.substrate_class ?? t("No substrate")}
                      </p>
                    </div>
                    <Badge variant={profile.active ? "success" : "neutral"}>
                      {profile.active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <MiniMetric
                      label="Dose shift"
                      value={
                        profile.dose_window_shift_pct != null
                          ? `${formatNumber(profile.dose_window_shift_pct, 2)}%`
                          : "N/A"
                      }
                    />
                    <MiniMetric
                      label="MTT shift"
                      value={
                        profile.mtt_shift_pct != null
                          ? `${formatNumber(profile.mtt_shift_pct, 2)}%`
                          : "N/A"
                      }
                    />
                  </div>
                </div>
              ))
            ) : (
              <EmptyPanel message="No locality profiles have been defined yet." />
            )}
          </CardBody>
        </Card>

        <Card className="assistant-aside-card rounded-[28px]">
          <CardHeader
            title="Executor profiles"
            description="Executor-specific operating envelopes and plugin modes used in portability checks."
            action={
              <Button
                size="sm"
                variant="outline"
                leftIcon={<Cpu className="h-4 w-4" />}
                onClick={() => setExecutorModalOpen(true)}
              >
                New executor
              </Button>
            }
          />
          <CardBody className="space-y-3">
            {(executorProfiles.data ?? []).length ? (
              executorProfiles.data!.slice(0, 6).map((profile) => {
                const locality = profile.locality_profile_id
                  ? localityMap.get(profile.locality_profile_id)
                  : null;
                return (
                  <div key={profile.id} className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-white">{profile.name}</p>
                        <p className="mt-1 text-xs text-surface-400">
                          {profile.executor_code} / {profile.executor_type ?? t("Generic executor")}
                        </p>
                      </div>
                      <Badge variant={profile.active ? "success" : "neutral"}>
                        {profile.active ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <MiniMetric
                        label="HAL"
                        value={
                          profile.hal_min != null && profile.hal_max != null
                            ? `${formatNumber(profile.hal_min, 2)} - ${formatNumber(profile.hal_max, 2)}`
                            : "N/A"
                        }
                      />
                      <MiniMetric label="MTT nominal" value={formatNumber(profile.mtt_nominal, 3)} />
                      <MiniMetric label="Locality" value={locality?.name ?? t("Unbound")} />
                    </div>
                  </div>
                );
              })
            ) : (
              <EmptyPanel message="No executor profiles have been defined yet." />
            )}
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader
            title="Release decision rail"
            description="Recent release-ready, retune-first, and hold-release evaluations across BOS-controlled batches."
          />
          <CardBody className="space-y-3">
            {packetViews.length ? (
              packetViews.slice(0, 8).map((packet) => (
                <div key={packet.id} className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-white">{packet.batchLabel}</p>
                      <p className="mt-1 text-xs text-surface-400">
                        {formatDateTime(packet.compiledAt)} / {t("compiled by user")} {packet.compiledByUserId}
                      </p>
                    </div>
                    <Badge variant={decisionVariant(packet.releaseDecision)}>
                      {formatDecisionLabel(packet.releaseDecision)}
                    </Badge>
                  </div>
                  {packet.reasonCodes.length ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {packet.reasonCodes.map((reasonCode) => (
                        <Badge key={reasonCode} variant="neutral">
                          {reasonCode}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))
            ) : (
              <EmptyPanel message="No release posture has been recorded yet." />
            )}
          </CardBody>
        </Card>

        <Card className="assistant-aside-card rounded-[28px]">
          <CardHeader
            title="Portability matrix feed"
            description="Recent packet-backed portability posture across released signals."
          />
          <CardBody className="space-y-3">
            {packetPortabilityFeed.length ? (
              packetPortabilityFeed.slice(0, 8).map((audit) => {
                return (
                  <div key={`${audit.packetId}-${audit.id}`} className="assistant-thread-shell flex items-center justify-between gap-3 rounded-2xl border border-white/8 px-4 py-3">
                    <div>
                      <p className="text-sm font-medium text-white">
                        {audit.executorLabel}
                        {" / "}
                        {audit.signalLabel}
                      </p>
                      <p className="mt-1 text-xs text-surface-400">
                        {audit.localityLabel}
                        {" / "}
                        {audit.retuningRequired ? t("Retuning required") : t("No retuning required")}
                        {audit.recommendedOutcome ? ` / ${formatRecommendationLabel(audit.recommendedOutcome)}` : ""}
                        {audit.portabilityScore != null ? ` / ${formatPercent(audit.portabilityScore, 0)}` : ""}
                        {" / "}
                        {formatDateTime(audit.compiledAt)}
                      </p>
                    </div>
                    <Badge variant={portabilityVariant(audit.outcome)}>
                      {formatRecommendationLabel(audit.outcome)}
                    </Badge>
                  </div>
                );
              })
            ) : (
              <EmptyPanel message="No portability posture has been recorded yet." />
            )}
          </CardBody>
        </Card>

        <Card className="assistant-aside-card rounded-[28px]">
          <CardHeader
            title="Audit packets"
            description="Compiled evidence packets ready for operator inspection and export."
          />
          <CardBody className="space-y-3">
            {(auditPackets.data ?? []).length ? (
              auditPackets.data!.slice(0, 8).map((packet) => (
                <div key={packet.id} className="assistant-thread-shell flex items-center justify-between gap-3 rounded-2xl border border-white/8 px-4 py-3">
                  <div>
                    <p className="text-sm font-medium text-white">
                      {t("Audit Packet")} {packet.packet_version} / {t("Batch")} {packet.batch_id}
                    </p>
                    <p className="mt-1 text-xs text-surface-400">
                      {packet.evidence_level ?? t("Unknown evidence")} / {formatDateTime(packet.generated_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={evidenceVariant(packet.evidence_level)}>
                      {packet.evidence_level ?? t("Unknown")}
                    </Badge>
                    <Button
                      size="sm"
                      variant="ghost"
                      leftIcon={<ArrowRight className="h-4 w-4" />}
                      onClick={() => {
                        const params = new URLSearchParams();
                        params.set("batchId", String(packet.batch_id));
                        const signalId = packet.packet?.signal_batch?.id;
                        const controlProfileId = packet.packet?.control_profile?.id;
                        if (signalId) params.set("signalId", String(signalId));
                        if (controlProfileId) params.set("controlProfileId", String(controlProfileId));
                        navigate(`/bos/signal-lab?${params.toString()}`);
                      }}
                    >
                      Signal lab
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      leftIcon={<Eye className="h-4 w-4" />}
                      onClick={() => setSelectedAuditPacketId(packet.id)}
                    >
                      View packet
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <EmptyPanel message="No audit packets have been compiled yet." />
            )}
          </CardBody>
        </Card>

        <AuditExportCard
          hasAuditPacket={Boolean(auditPacketForExport)}
          generatedAt={auditPacketForExport?.generated_at ?? null}
          onExport={(format) => {
            if (!auditPacketForExport) return;
            exportAuditPacket.mutate({ batchId: auditPacketForExport.batch_id, format });
          }}
          exportingFormat={exportAuditPacket.isPending ? exportAuditPacket.variables?.format ?? null : null}
        />
      </div>

      {latestAuditPacket && latestAuditPacketView ? (
        <Card className="assistant-aside-card rounded-[28px]">
          <CardHeader
            title="Latest packet provenance"
            description="Keep the latest packet exportable, traceable, and explicit about contract gaps."
          />
          <CardBody className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
            <div className="rounded-3xl border border-white/8 bg-white/5 p-4">
              <p className="metric-kicker">Contract evaluation</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge variant={contractVariant(latestContractStatus)}>
                  {`Status ${latestContractStatus}`}
                </Badge>
                {latestDecisionConfidence != null ? (
                  <Badge variant="info">
                    {`Decision confidence ${formatPercent(latestDecisionConfidence, 0)}`}
                  </Badge>
                ) : null}
                {latestSourceMode ? <Badge variant="neutral">{`Source ${latestSourceMode}`}</Badge> : null}
              </div>
              <p className="mt-4 text-xs uppercase tracking-[0.24em] text-surface-500">Threshold breaches</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {latestThresholdBreaches.length ? (
                  latestThresholdBreaches.map((breach) => (
                    <Badge key={breach} variant="warning">
                      {breach}
                    </Badge>
                  ))
                ) : (
                  <Badge variant="success">None</Badge>
                )}
              </div>
              <p className="mt-4 text-xs uppercase tracking-[0.24em] text-surface-500">Integrity hash</p>
              <p className="mt-2 break-all text-sm leading-6 text-surface-300">
                {auditPacketForExportView?.integrityHash || "N/A"}
              </p>
            </div>

            <div className="rounded-3xl border border-white/8 bg-white/5 p-4">
              <p className="metric-kicker">Source provenance</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {getSourceEntries(latestAuditPacket).map(([label, value]) => (
                  <div key={label} className="rounded-2xl border border-white/8 bg-surface-950/60 px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.22em] text-surface-500">{label}</p>
                    <p className="mt-2 text-sm font-medium text-white">{value}</p>
                  </div>
                ))}
              </div>
            </div>
          </CardBody>
        </Card>
      ) : null}

      <Modal
        open={selectedAuditPacket !== null}
        onClose={() => setSelectedAuditPacketId(null)}
        title={
          selectedAuditPacket
            ? `${t("Audit Packet")} ${selectedAuditPacket.packet_version}`
            : t("Audit Packet")
        }
        description="Structured packet view for control contract, boundary ledger, release decision, and portability evidence."
        size="lg"
        footer={
          <div className="flex items-center gap-3">
            {selectedAuditPacket ? (
              <>
                <Button
                  variant="outline"
                  onClick={() => exportAuditPacket.mutate({ batchId: selectedAuditPacket.batch_id, format: "json" })}
                  loading={
                    exportAuditPacket.isPending &&
                    exportAuditPacket.variables?.batchId === selectedAuditPacket.batch_id &&
                    exportAuditPacket.variables?.format === "json"
                  }
                >
                  Export JSON
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => exportAuditPacket.mutate({ batchId: selectedAuditPacket.batch_id, format: "md" })}
                  loading={
                    exportAuditPacket.isPending &&
                    exportAuditPacket.variables?.batchId === selectedAuditPacket.batch_id &&
                    exportAuditPacket.variables?.format === "md"
                  }
                >
                  Export Markdown
                </Button>
              </>
            ) : null}
            <Button variant="secondary" onClick={() => setSelectedAuditPacketId(null)}>
              Close
            </Button>
          </div>
        }
      >
        {selectedAuditPacket && selectedAuditPacketView ? (
          <div className="space-y-4">
            <PacketInfoPanel
              title="Packet header"
              items={[
                ["Batch", selectedAuditPacketView.batchLabel],
                ["Evidence", selectedAuditPacketView.evidenceLevel],
                ["Compiled", formatDateTime(selectedAuditPacketView.compiledAt)],
                ["Schema", selectedAuditPacketView.schemaVersion],
              ]}
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <PacketInfoPanel
                title="Control contract"
                items={[
                  ["Profile", selectedAuditPacket.packet?.control_profile?.name ?? "N/A"],
                  ["Version", selectedAuditPacket.packet?.control_profile?.version ?? "N/A"],
                  ["MTT", formatNumber(selectedAuditPacket.packet?.control_profile?.mtt, 3)],
                  [
                    "Dose window",
                    selectedAuditPacket.packet?.control_profile?.dose_window_min != null &&
                    selectedAuditPacket.packet?.control_profile?.dose_window_max != null
                      ? `${formatNumber(selectedAuditPacket.packet.control_profile.dose_window_min, 2)} - ${formatNumber(selectedAuditPacket.packet.control_profile.dose_window_max, 2)}`
                      : "N/A",
                  ],
                  ["Contract status", selectedAuditPacket.contract_evaluation?.status ?? "N/A"],
                ]}
              />
              <PacketInfoPanel
                title="Boundary ledger"
                items={[
                  ["SER", formatNumber(selectedAuditPacket.packet?.boundary_ledger?.ser_value, 4)],
                  ["D'", formatNumber(selectedAuditPacket.packet?.boundary_ledger?.d_prime, 4)],
                  ["G'", formatNumber(selectedAuditPacket.packet?.boundary_ledger?.g_prime, 4)],
                  ["DeltaDeltaSER", formatNumber(selectedAuditPacket.packet?.boundary_ledger?.delta_delta_ser, 4)],
                  [
                    "Metering",
                    formatPercent(selectedAuditPacket.packet?.boundary_ledger?.metering_completeness, 0),
                  ],
                ]}
              />
            </div>
            {selectedAuditPacketView.mechanisticContext ? (
              <MechanisticContextCard
                context={selectedAuditPacketView.mechanisticContext}
                signalLabel={selectedAuditPacketView.signalLabel}
                title="Packet mechanistic diagnostics"
                description="Mechanistic context extracted from this audit packet."
              />
            ) : null}
            {selectedAuditPacketView.supervisorSnapshot ? (
              <>
                <SupervisorSnapshotCard
                  snapshot={selectedAuditPacketView.supervisorSnapshot}
                  title="Packet supervisor snapshot"
                  description="Latest persisted supervisor decision carried by this audit packet."
                />
                <SupervisorHistoryCard
                  history={selectedAuditPacketView.supervisorHistory}
                  title="Packet supervisor history"
                  description="Recent persisted supervisor observations carried by this audit packet."
                />
              </>
            ) : null}
            <div className="rounded-3xl border border-white/8 bg-white/5 p-4">
              <p className="metric-kicker">Release decision</p>
              <div className="mt-4 flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-white">
                  {selectedAuditPacket.packet?.release_decision?.decision
                    ? formatDecisionLabel(selectedAuditPacket.packet.release_decision.decision)
                    : "N/A"}
                </p>
                {selectedAuditPacket.packet?.release_decision?.decision ? (
                  <Badge variant={decisionVariant(selectedAuditPacket.packet.release_decision.decision)}>
                    {formatDecisionLabel(selectedAuditPacket.packet.release_decision.decision)}
                  </Badge>
                ) : null}
              </div>
              {selectedAuditPacket.packet?.release_decision?.rationale ? (
                <p className="mt-3 text-sm leading-6 text-surface-300">
                  {selectedAuditPacket.packet.release_decision.rationale}
                </p>
              ) : null}
              {selectedAuditPacket.packet?.release_decision?.reason_codes?.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {selectedAuditPacket.packet.release_decision.reason_codes.map((reasonCode) => (
                    <Badge key={reasonCode} variant="neutral">
                      {reasonCode}
                    </Badge>
                  ))}
                </div>
              ) : null}
              {selectedAuditPacket.contract_evaluation?.threshold_breaches?.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {selectedAuditPacket.contract_evaluation.threshold_breaches.map((breach) => (
                    <Badge key={breach} variant="warning">
                      {`${t("Threshold")} ${breach}`}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="rounded-3xl border border-white/8 bg-white/5 p-4">
              <p className="metric-kicker">Portability evidence rail</p>
              <div className="mt-4 space-y-3">
                {selectedAuditPacket.packet?.portability_audits?.length ? (
                  selectedAuditPacket.packet.portability_audits.map((audit) => (
                    <div
                      key={audit.id}
                      className="rounded-2xl border border-white/8 bg-surface-900/80 px-4 py-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-white">
                            {audit.executor_name ?? `${t("Executor")} ${audit.executor_profile_id}`} / {t("portability")} #{audit.id}
                          </p>
                          <p className="mt-1 text-xs text-surface-400">
                            {audit.locality_name ??
                              (audit.locality_profile_id != null
                                ? `${t("Locality")} ${audit.locality_profile_id}`
                                : t("No locality override"))}
                          </p>
                        </div>
                        <Badge variant={portabilityVariant(audit.outcome)}>
                          {formatRecommendationLabel(audit.outcome)}
                        </Badge>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Badge variant={audit.retuning_required ? "warning" : "success"}>
                          {audit.retuning_required ? t("Retuning required") : t("No retuning required")}
                        </Badge>
                        {audit.requires_requalification ? (
                          <Badge variant="danger">{t("Requalification required")}</Badge>
                        ) : null}
                        {audit.recommended_outcome ? (
                          <Badge variant={portabilityVariant(audit.recommended_outcome)}>
                            {`${t("Recommended")} ${formatRecommendationLabel(audit.recommended_outcome)}`}
                          </Badge>
                        ) : null}
                        {audit.portability_score != null ? (
                          <Badge variant="info">
                            {`${t("Score")} ${formatPercent(audit.portability_score, 0)}`}
                          </Badge>
                        ) : null}
                        {audit.retuning_axes?.map((axis) => (
                          <Badge key={`${audit.id}-${axis}`} variant="warning">
                            {`${t("Axis")} ${axis}`}
                          </Badge>
                        ))}
                        {Object.entries(audit.trigger_metrics ?? {}).slice(0, 4).map(([key, value]) => (
                          <Badge key={key} variant="neutral">
                            {`${key}: ${formatUnknownValue(value)}`}
                          </Badge>
                        ))}
                      </div>
                      {audit.rationale ? (
                        <p className="mt-3 text-sm leading-6 text-surface-300">{audit.rationale}</p>
                      ) : null}
                      {audit.recommended_action ? (
                        <div className="mt-3 rounded-2xl border border-white/8 bg-white/5 px-3 py-3 text-sm text-surface-200">
                          {audit.recommended_action}
                        </div>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <EmptyPanel message="This packet does not include portability entries." />
                )}
              </div>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={releaseModalOpen}
        onClose={() => setReleaseModalOpen(false)}
        title="Evaluate Release"
        description="Run the current release / reject / requalify decision chain for a batch."
        footer={
          <>
            <Button variant="secondary" onClick={() => setReleaseModalOpen(false)}>
              Cancel
            </Button>
            <Button
              loading={evaluateRelease.isPending}
              onClick={async () => {
                await evaluateRelease.mutateAsync({
                  batch_id: Number(releaseForm.batch_id),
                  signal_batch_id: releaseForm.signal_batch_id ? Number(releaseForm.signal_batch_id) : undefined,
                  control_profile_id: releaseForm.control_profile_id ? Number(releaseForm.control_profile_id) : undefined,
                  locality_profile_id: releaseForm.locality_profile_id ? Number(releaseForm.locality_profile_id) : undefined,
                  persist: true,
                });
                setReleaseModalOpen(false);
                setReleaseForm({
                  batch_id: "",
                  signal_batch_id: "",
                  control_profile_id: "",
                  locality_profile_id: "",
                });
              }}
              disabled={!releaseForm.batch_id}
            >
              Evaluate
            </Button>
          </>
        }
      >
        <div className="grid gap-4">
          <Select
            label="Batch"
            required
            options={(batches.data?.items ?? []).map((batch) => ({
              value: String(batch.id),
              label: `${batch.batch_id} / ${batch.species}`,
            }))}
            value={releaseForm.batch_id}
            onChange={(event) => setReleaseForm((current) => ({ ...current, batch_id: event.target.value }))}
            placeholder="Select batch"
          />
          <Select
            label="Signal batch"
            options={(signals.data ?? []).map((signal) => ({
              value: String(signal.id),
              label: `${signal.compiled_signal_id ?? `Signal ${signal.id}`} / batch ${signal.batch_id}`,
            }))}
            value={releaseForm.signal_batch_id}
            onChange={(event) => setReleaseForm((current) => ({ ...current, signal_batch_id: event.target.value }))}
            placeholder="Latest signal if empty"
          />
          <Select
            label="Control profile"
            options={(controlProfiles.data ?? []).map((profile) => ({
              value: String(profile.id),
              label: `${profile.name} / ${profile.version}`,
            }))}
            value={releaseForm.control_profile_id}
            onChange={(event) => setReleaseForm((current) => ({ ...current, control_profile_id: event.target.value }))}
            placeholder="Active profile if empty"
          />
          <Select
            label="Locality"
            options={(localityProfiles.data ?? []).map((profile) => ({
              value: String(profile.id),
              label: `${profile.name}${profile.site_code ? ` / ${profile.site_code}` : ""}`,
            }))}
            value={releaseForm.locality_profile_id}
            onChange={(event) => setReleaseForm((current) => ({ ...current, locality_profile_id: event.target.value }))}
            placeholder="Optional locality context"
          />
        </div>
      </Modal>

      <Modal
        open={signalModalOpen}
        onClose={() => setSignalModalOpen(false)}
        title="Create Signal Batch"
        description="Persist a releasable Signal-API object for an existing batch."
        footer={
          <>
            <Button variant="secondary" onClick={() => setSignalModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="outline"
              leftIcon={<Sparkles className="h-4 w-4" />}
              loading={compileSignal.isPending}
              onClick={async () => {
                await compileSignal.mutateAsync({
                  batch_id: Number(signalForm.batch_id),
                });
                setSignalModalOpen(false);
              }}
              disabled={!signalForm.batch_id}
            >
              Compile signal
            </Button>
            <Button
              loading={createSignal.isPending}
              onClick={async () => {
                await createSignal.mutateAsync({
                  batch_id: Number(signalForm.batch_id),
                  signal_api_version: signalForm.signal_api_version,
                  compiled_signal_id: signalForm.compiled_signal_id || undefined,
                  potency: signalForm.potency ? Number(signalForm.potency) : undefined,
                  potency_unit: signalForm.potency_unit || undefined,
                  dose_window_min: signalForm.dose_window_min ? Number(signalForm.dose_window_min) : undefined,
                  dose_window_max: signalForm.dose_window_max ? Number(signalForm.dose_window_max) : undefined,
                  stability_window_hours: signalForm.stability_window_hours ? Number(signalForm.stability_window_hours) : undefined,
                  freshness_state: signalForm.freshness_state || undefined,
                  notes: signalForm.notes || undefined,
                });
                setSignalModalOpen(false);
                setSignalForm({
                  batch_id: "",
                  signal_api_version: "SIG-1.0",
                  compiled_signal_id: "",
                  potency: "",
                  potency_unit: "SER-equivalent",
                  dose_window_min: "",
                  dose_window_max: "",
                  stability_window_hours: "",
                  freshness_state: "Fresh",
                  notes: "",
                });
              }}
              disabled={!signalForm.batch_id}
            >
              Create signal
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Select
            label="Batch"
            required
            options={(batches.data?.items ?? []).map((batch) => ({
              value: String(batch.id),
              label: `${batch.batch_id} / ${batch.species}`,
            }))}
            value={signalForm.batch_id}
            onChange={(event) => setSignalForm((current) => ({ ...current, batch_id: event.target.value }))}
            placeholder="Select batch"
          />
          <Input
            label="Signal API version"
            value={signalForm.signal_api_version}
            onChange={(event) => setSignalForm((current) => ({ ...current, signal_api_version: event.target.value }))}
          />
          <Input
            label="Compiled signal ID"
            value={signalForm.compiled_signal_id}
            onChange={(event) => setSignalForm((current) => ({ ...current, compiled_signal_id: event.target.value }))}
          />
          <Input
            label="Potency"
            type="number"
            step="0.001"
            value={signalForm.potency}
            onChange={(event) => setSignalForm((current) => ({ ...current, potency: event.target.value }))}
          />
          <Input
            label="Dose window min"
            type="number"
            step="0.001"
            value={signalForm.dose_window_min}
            onChange={(event) => setSignalForm((current) => ({ ...current, dose_window_min: event.target.value }))}
          />
          <Input
            label="Dose window max"
            type="number"
            step="0.001"
            value={signalForm.dose_window_max}
            onChange={(event) => setSignalForm((current) => ({ ...current, dose_window_max: event.target.value }))}
          />
          <Input
            label="Stability window (h)"
            type="number"
            step="1"
            value={signalForm.stability_window_hours}
            onChange={(event) => setSignalForm((current) => ({ ...current, stability_window_hours: event.target.value }))}
          />
          <Select
            label="Freshness"
            options={[
              { value: "Fresh", label: "Fresh" },
              { value: "Stable", label: "Stable" },
              { value: "Stale", label: "Stale" },
            ]}
            value={signalForm.freshness_state}
            onChange={(event) => setSignalForm((current) => ({ ...current, freshness_state: event.target.value }))}
          />
        </div>
        <div className="mt-4">
          <Textarea
            label="Notes"
            value={signalForm.notes}
            onChange={(event) => setSignalForm((current) => ({ ...current, notes: event.target.value }))}
          />
        </div>
      </Modal>

      <Modal
        open={controlModalOpen}
        onClose={() => setControlModalOpen(false)}
        title="Create Control Profile"
        description="Persist a versioned Control-API contract with MTT, HAL, and release bounds."
        footer={
          <>
            <Button variant="secondary" onClick={() => setControlModalOpen(false)}>
              Cancel
            </Button>
            <Button
              loading={createControlProfile.isPending}
              onClick={async () => {
                await createControlProfile.mutateAsync({
                  name: controlForm.name,
                  version: controlForm.version,
                  mtt: controlForm.mtt ? Number(controlForm.mtt) : undefined,
                  hal_min: controlForm.hal_min ? Number(controlForm.hal_min) : undefined,
                  hal_max: controlForm.hal_max ? Number(controlForm.hal_max) : undefined,
                  dose_window_min: controlForm.dose_window_min ? Number(controlForm.dose_window_min) : undefined,
                  dose_window_max: controlForm.dose_window_max ? Number(controlForm.dose_window_max) : undefined,
                  stability_window_hours: controlForm.stability_window_hours ? Number(controlForm.stability_window_hours) : undefined,
                  notes: controlForm.notes || undefined,
                });
                setControlModalOpen(false);
                setControlForm({
                  name: "",
                  version: "CTRL-1.0",
                  mtt: "",
                  hal_min: "",
                  hal_max: "",
                  dose_window_min: "",
                  dose_window_max: "",
                  stability_window_hours: "",
                  notes: "",
                });
              }}
              disabled={!controlForm.name || !controlForm.version}
            >
              Create control profile
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Name"
            required
            value={controlForm.name}
            onChange={(event) => setControlForm((current) => ({ ...current, name: event.target.value }))}
          />
          <Input
            label="Version"
            required
            value={controlForm.version}
            onChange={(event) => setControlForm((current) => ({ ...current, version: event.target.value }))}
          />
          <Input
            label="MTT"
            type="number"
            step="0.001"
            value={controlForm.mtt}
            onChange={(event) => setControlForm((current) => ({ ...current, mtt: event.target.value }))}
          />
          <Input
            label="HAL min"
            type="number"
            step="0.001"
            value={controlForm.hal_min}
            onChange={(event) => setControlForm((current) => ({ ...current, hal_min: event.target.value }))}
          />
          <Input
            label="HAL max"
            type="number"
            step="0.001"
            value={controlForm.hal_max}
            onChange={(event) => setControlForm((current) => ({ ...current, hal_max: event.target.value }))}
          />
          <Input
            label="Dose window min"
            type="number"
            step="0.001"
            value={controlForm.dose_window_min}
            onChange={(event) => setControlForm((current) => ({ ...current, dose_window_min: event.target.value }))}
          />
          <Input
            label="Dose window max"
            type="number"
            step="0.001"
            value={controlForm.dose_window_max}
            onChange={(event) => setControlForm((current) => ({ ...current, dose_window_max: event.target.value }))}
          />
          <Input
            label="Stability window (h)"
            type="number"
            step="1"
            value={controlForm.stability_window_hours}
            onChange={(event) => setControlForm((current) => ({ ...current, stability_window_hours: event.target.value }))}
          />
        </div>
        <div className="mt-4">
          <Textarea
            label="Notes"
            value={controlForm.notes}
            onChange={(event) => setControlForm((current) => ({ ...current, notes: event.target.value }))}
          />
        </div>
      </Modal>

      <Modal
        open={localityModalOpen}
        onClose={() => setLocalityModalOpen(false)}
        title="Create Locality Profile"
        description="Persist a site-local portability context with dose and MTT shifts."
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setLocalityModalOpen(false)}>
              Cancel
            </Button>
            <Button
              loading={createLocalityProfile.isPending}
              onClick={handleCreateLocality}
              disabled={!localityForm.name}
            >
              Create locality profile
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Name"
            required
            value={localityForm.name}
            onChange={(event) => setLocalityForm((current) => ({ ...current, name: event.target.value }))}
          />
          <Input
            label="Site code"
            value={localityForm.site_code}
            onChange={(event) => setLocalityForm((current) => ({ ...current, site_code: event.target.value }))}
          />
          <Input
            label="Substrate class"
            value={localityForm.substrate_class}
            onChange={(event) => setLocalityForm((current) => ({ ...current, substrate_class: event.target.value }))}
          />
          <Input
            label="Dose window shift (%)"
            type="number"
            step="0.01"
            value={localityForm.dose_window_shift_pct}
            onChange={(event) => setLocalityForm((current) => ({ ...current, dose_window_shift_pct: event.target.value }))}
          />
          <Input
            label="MTT shift (%)"
            type="number"
            step="0.01"
            value={localityForm.mtt_shift_pct}
            onChange={(event) => setLocalityForm((current) => ({ ...current, mtt_shift_pct: event.target.value }))}
          />
          <Select
            label="Status"
            options={[
              { value: "true", label: "Active" },
              { value: "false", label: "Inactive" },
            ]}
            value={localityForm.active}
            onChange={(event) => setLocalityForm((current) => ({ ...current, active: event.target.value }))}
          />
        </div>
        <div className="mt-4 space-y-4">
          <Textarea
            label="Waste state JSON"
            rows={4}
            value={localityForm.waste_state}
            onChange={(event) => setLocalityForm((current) => ({ ...current, waste_state: event.target.value }))}
            helperText='Optional JSON object, e.g. {"dry_matter":0.34,"contamination":"low"}'
          />
          <Textarea
            label="Pretreat flags JSON"
            rows={4}
            value={localityForm.pretreat_flags}
            onChange={(event) => setLocalityForm((current) => ({ ...current, pretreat_flags: event.target.value }))}
            helperText='Optional JSON object, e.g. {"heat_treated":true,"screened":false}'
          />
          <Textarea
            label="Notes"
            value={localityForm.notes}
            onChange={(event) => setLocalityForm((current) => ({ ...current, notes: event.target.value }))}
          />
        </div>
      </Modal>

      <Modal
        open={executorModalOpen}
        onClose={() => setExecutorModalOpen(false)}
        title="Create Executor Profile"
        description="Persist an executor-specific portability target with HAL, MTT, and plugin mode."
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setExecutorModalOpen(false)}>
              Cancel
            </Button>
            <Button
              loading={createExecutorProfile.isPending}
              onClick={handleCreateExecutor}
              disabled={!executorForm.executor_code || !executorForm.name}
            >
              Create executor profile
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="Executor code"
            required
            value={executorForm.executor_code}
            onChange={(event) => setExecutorForm((current) => ({ ...current, executor_code: event.target.value }))}
          />
          <Input
            label="Name"
            required
            value={executorForm.name}
            onChange={(event) => setExecutorForm((current) => ({ ...current, name: event.target.value }))}
          />
          <Select
            label="Default locality"
            options={(localityProfiles.data ?? []).map((profile) => ({
              value: String(profile.id),
              label: `${profile.name}${profile.site_code ? ` / ${profile.site_code}` : ""}`,
            }))}
            value={executorForm.locality_profile_id}
            onChange={(event) => setExecutorForm((current) => ({ ...current, locality_profile_id: event.target.value }))}
            placeholder="No default locality"
          />
          <Input
            label="Executor type"
            value={executorForm.executor_type}
            onChange={(event) => setExecutorForm((current) => ({ ...current, executor_type: event.target.value }))}
          />
          <Input
            label="HAL min"
            type="number"
            step="0.001"
            value={executorForm.hal_min}
            onChange={(event) => setExecutorForm((current) => ({ ...current, hal_min: event.target.value }))}
          />
          <Input
            label="HAL max"
            type="number"
            step="0.001"
            value={executorForm.hal_max}
            onChange={(event) => setExecutorForm((current) => ({ ...current, hal_max: event.target.value }))}
          />
          <Input
            label="MTT nominal"
            type="number"
            step="0.001"
            value={executorForm.mtt_nominal}
            onChange={(event) => setExecutorForm((current) => ({ ...current, mtt_nominal: event.target.value }))}
          />
          <Input
            label="Plugin mode"
            value={executorForm.plugin_mode}
            onChange={(event) => setExecutorForm((current) => ({ ...current, plugin_mode: event.target.value }))}
          />
          <Select
            label="Status"
            options={[
              { value: "true", label: "Active" },
              { value: "false", label: "Inactive" },
            ]}
            value={executorForm.active}
            onChange={(event) => setExecutorForm((current) => ({ ...current, active: event.target.value }))}
          />
        </div>
        <div className="mt-4">
          <Textarea
            label="Notes"
            value={executorForm.notes}
            onChange={(event) => setExecutorForm((current) => ({ ...current, notes: event.target.value }))}
          />
        </div>
      </Modal>

      <Modal
        open={portabilityModalOpen}
        onClose={() => setPortabilityModalOpen(false)}
        title="Record Portability Audit"
        description="Persist an executor-locality portability outcome for a released signal."
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPortabilityModalOpen(false)}>
              Cancel
            </Button>
            <Button
              loading={createPortabilityAudit.isPending}
              onClick={handleCreatePortabilityAudit}
              disabled={!portabilityForm.signal_batch_id || !portabilityForm.executor_profile_id}
            >
              Record portability audit
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Select
            label="Signal batch"
            required
            options={(signals.data ?? []).map((signal) => ({
              value: String(signal.id),
              label: `${signal.compiled_signal_id ?? `Signal ${signal.id}`} / batch ${signal.batch_id}`,
            }))}
            value={portabilityForm.signal_batch_id}
            onChange={(event) => setPortabilityForm((current) => ({ ...current, signal_batch_id: event.target.value }))}
            placeholder="Select signal"
          />
          <Select
            label="Executor profile"
            required
            options={(executorProfiles.data ?? []).map((profile) => ({
              value: String(profile.id),
              label: `${profile.name} / ${profile.executor_code}`,
            }))}
            value={portabilityForm.executor_profile_id}
            onChange={(event) => setPortabilityForm((current) => ({ ...current, executor_profile_id: event.target.value }))}
            placeholder="Select executor"
          />
          <Select
            label="Locality override"
            options={(localityProfiles.data ?? []).map((profile) => ({
              value: String(profile.id),
              label: `${profile.name}${profile.site_code ? ` / ${profile.site_code}` : ""}`,
            }))}
            value={portabilityForm.locality_profile_id}
            onChange={(event) => setPortabilityForm((current) => ({ ...current, locality_profile_id: event.target.value }))}
            placeholder="Use executor default if empty"
          />
          <Select
            label="Outcome"
            options={[
              { value: "PASS", label: "PASS" },
              { value: "PASS_WITH_RETUNING", label: "PASS_WITH_RETUNING" },
              { value: "FAIL", label: "FAIL" },
            ]}
            value={portabilityForm.outcome}
            onChange={(event) => setPortabilityForm((current) => ({ ...current, outcome: event.target.value }))}
          />
          <Select
            label="Retuning required"
            options={[
              { value: "false", label: "No" },
              { value: "true", label: "Yes" },
            ]}
            value={portabilityForm.retuning_required}
            onChange={(event) => setPortabilityForm((current) => ({ ...current, retuning_required: event.target.value }))}
          />
        </div>
        <div className="mt-4">
          <PortabilityRecommendationCard
            recommendation={portabilityRecommendation.data}
            isLoading={portabilityRecommendation.isLoading}
            emptyMessage="Select a signal and executor first. Add a locality override if you also want to simulate site-level differences."
          />
        </div>
        <div className="mt-4 space-y-4">
          <Textarea
            label="Trigger metrics JSON"
            rows={4}
            value={portabilityForm.trigger_metrics}
            onChange={(event) => setPortabilityForm((current) => ({ ...current, trigger_metrics: event.target.value }))}
            helperText='Optional JSON object, e.g. {"hal_delta":0.08,"mtt_ratio":1.04}'
          />
          <Textarea
            label="Notes"
            value={portabilityForm.notes}
            onChange={(event) => setPortabilityForm((current) => ({ ...current, notes: event.target.value }))}
          />
        </div>
      </Modal>
    </div>
  );
}

function parseOptionalNumber(value: string) {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseOptionalJsonObject(labelValue: string, label: string) {
  if (!labelValue.trim()) return undefined;
  try {
    const parsed = JSON.parse(labelValue) as unknown;
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      toast.error(`${label} must be a JSON object`);
      return INVALID_JSON;
    }
    return parsed as Record<string, unknown>;
  } catch {
    toast.error(`${label} must be valid JSON`);
    return INVALID_JSON;
  }
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="assistant-meta-panel rounded-2xl border border-white/8 bg-surface-900/70 px-3 py-3">
      <p className="assistant-section-kicker !text-surface-500">
        {translateText(label)}
      </p>
      <p className="mt-2 text-sm font-medium text-white">{translateText(value)}</p>
    </div>
  );
}

function PacketInfoPanel({
  title,
  items,
}: {
  title: string;
  items: Array<[string, string]>;
}) {
  return (
    <div className="rounded-3xl border border-white/8 bg-white/5 p-4">
      <p className="metric-kicker">{translateText(title)}</p>
      <dl className="mt-4 grid gap-3">
        {items.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-3 text-sm">
            <dt className="text-surface-400">{translateText(label)}</dt>
            <dd className="text-right font-medium text-white">{translateText(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function EmptyPanel({ message }: { message: string }) {
  return (
    <div className="assistant-aside-card rounded-2xl border border-dashed border-white/10 bg-white/3 px-4 py-8 text-center text-sm text-surface-400">
      {translateText(message)}
    </div>
  );
}

function freshnessVariant(value?: string | null) {
  const normalized = (value ?? "").toLowerCase();
  if (normalized.includes("fresh")) return "success" as const;
  if (normalized.includes("stable")) return "info" as const;
  return "warning" as const;
}

function portabilityVariant(value: string) {
  if (value === "PASS") return "success" as const;
  if (value === "PASS_WITH_RETUNING") return "warning" as const;
  return "danger" as const;
}

function evidenceVariant(value?: string | null) {
  if (value === "Validated") return "success" as const;
  if (value === "Supported") return "info" as const;
  return "neutral" as const;
}

function contractVariant(value?: string | null) {
  const normalized = (value ?? "").toLowerCase();
  if (normalized.includes("within") || normalized.includes("pass")) return "success" as const;
  if (normalized.includes("review") || normalized.includes("warn")) return "warning" as const;
  if (!normalized) return "neutral" as const;
  return "danger" as const;
}

function formatContractStatusLabel(value?: string | null) {
  const normalized = (value ?? "").toLowerCase();
  if (normalized.includes("within")) return "Within window";
  if (normalized.includes("review")) return "Needs review";
  if (normalized.includes("warn")) return "Watch";
  if (!normalized || normalized === "unknown") return "Unknown contract state";
  return value ?? "Unknown contract state";
}

function decisionVariant(value: string) {
  if (value === "PASS") return "success" as const;
  if (value === "PASS_WITH_RETUNING") return "warning" as const;
  if (value === "FAIL") return "danger" as const;
  return "neutral" as const;
}

function signalStatusVariant(value: string) {
  if (value === "valid") return "success" as const;
  if (value === "review") return "warning" as const;
  if (value === "blocked") return "danger" as const;
  return "neutral" as const;
}

function formatSignalStatusLabel(value: string) {
  if (value === "valid") return "Ready";
  if (value === "review") return "Needs review";
  if (value === "blocked") return "Blocked";
  return "Unknown signal state";
}

function formatDecisionLabel(value: string) {
  if (value === "PASS") return "Release ready";
  if (value === "PASS_WITH_RETUNING") return "Retune first";
  if (value === "FAIL") return "Hold release";
  return value;
}

function formatRecommendationLabel(value: string) {
  if (value === "PASS") return "Recommend release";
  if (value === "PASS_WITH_RETUNING") return "Release with retuning";
  if (value === "FAIL") return "Do not release";
  return value;
}

function formatRecommendationPreview(value: string, axesCount: number) {
  if (value === "PASS") return "Recommend release. There are no obvious portability blockers under the current conditions.";
  if (value === "PASS_WITH_RETUNING") {
    return `Release is possible, but address ${axesCount} retuning direction${axesCount === 1 ? "" : "s"} before formal execution.`;
  }
  return "Do not release yet. Portability risk remains too high under the current conditions.";
}

function formatRecommendationAction(value: string, axes: string[]) {
  if (value === "PASS") return "Proceed with the current executor-locality pairing.";
  if (value === "PASS_WITH_RETUNING") {
    const axisText = axes.length ? axes.join(", ") : "the active execution settings";
    return `Retune ${axisText} before formal release.`;
  }
  return "Requalify the signal under a different executor or locality before release.";
}

function getSourceEntries(packet: AuditPacket): Array<[string, string]> {
  const sourceIds = packet.packet?.generation_context?.source_ids;
  return [
    ["Signal batch", formatSourceValue(sourceIds?.signal_batch_id)],
    ["Control profile", formatSourceValue(sourceIds?.control_profile_id)],
    ["Boundary ledger", formatSourceValue(sourceIds?.boundary_ledger_id)],
    ["Release decision", formatSourceValue(sourceIds?.release_decision_id)],
    [
      "Portability audits",
      formatSourceValue(
        sourceIds?.portability_audit_ids?.length ? sourceIds.portability_audit_ids.join(", ") : null,
      ),
    ],
  ];
}

function formatSourceValue(value: number | string | null | undefined) {
  if (value == null || value === "") return "N/A";
  return String(value);
}

function extractMechanisticContext(
  signal: SignalBatch | null,
  packet: AuditPacket | null,
): MechanisticContext | null {
  const signalContext = signal?.qc_markers?.compile_context?.mechanistic_context;
  if (signalContext) return signalContext;

  const validityContext = packet?.signal_validity?.mechanistic_context;
  if (validityContext) return validityContext;

  const triggerContext = packet?.packet?.release_decision?.trigger_metrics?.mechanistic_context;
  if (isMechanisticContext(triggerContext)) return triggerContext;

  return null;
}

function isMechanisticContext(value: unknown): value is MechanisticContext {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<MechanisticContext>;
  return Boolean(candidate.c_di_ser && candidate.handover_envelope && candidate.inputs);
}

function formatUnknownValue(value: unknown) {
  if (typeof value === "number") return formatNumber(value, 3);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return value;
  if (value == null) return "null";
  return "object";
}
