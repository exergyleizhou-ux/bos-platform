import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, Cpu, Edit3, Play, Radar, Save, Trash2 } from "lucide-react";

import {
  useDeleteTwin,
  usePredictTwinStep,
  useSimulateTwin,
  useTwin,
  useUpdateTwin,
  useUpdateTwinObservations,
} from "@/hooks/useTwin";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { SurfaceTile } from "@/components/ui/SurfaceTile";
import { Textarea } from "@/components/ui/Textarea";
import { TwinTrajectoryChart } from "@/components/charts/TwinTrajectoryChart";
import { formatDate, formatNumber } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import { hasMinimumRole } from "@/types/auth";
import type { TwinSimulateRequest } from "@/types/twin";

const simSchema = z.object({
  duration_hours: z.coerce.number().min(1).max(720),
  time_step: z.coerce.number().min(0.01).max(10),
  temperature: z.union([z.coerce.number(), z.literal("")]).optional(),
  moisture: z.union([z.coerce.number().min(0).max(100), z.literal("")]).optional(),
  feed_rate: z.union([z.coerce.number().positive(), z.literal("")]).optional(),
});

const predictSchema = z.object({
  dt: z.coerce.number().min(0.01).max(24),
  feed_rate: z.union([z.coerce.number().min(0), z.literal("")]).optional(),
  ventilation: z.union([z.coerce.number().min(0), z.literal("")]).optional(),
  heating: z.union([z.coerce.number().min(0), z.literal("")]).optional(),
});

const observationSchema = z.object({
  weight: z.union([z.coerce.number().positive(), z.literal("")]).optional(),
  temperature: z.union([z.coerce.number().min(0).max(60), z.literal("")]).optional(),
  moisture: z.union([z.coerce.number().min(0).max(100), z.literal("")]).optional(),
});

const twinEditSchema = z.object({
  name: z.string().min(1, "Name is required"),
  status: z.enum(["active", "inactive"]),
  description: z.string().optional(),
  mu_max: z.coerce.number().positive(),
  temp_opt: z.coerce.number().positive(),
  moisture_opt: z.coerce.number().min(0).max(100),
});

type SimFormData = z.infer<typeof simSchema>;
type PredictFormData = z.infer<typeof predictSchema>;
type ObservationFormData = z.infer<typeof observationSchema>;
type TwinEditFormData = z.infer<typeof twinEditSchema>;

function optionalNumber(value: number | "" | undefined) {
  return value === "" || value === undefined ? undefined : Number(value);
}

export default function TwinDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const twinId = Number(id);
  const user = useAuthStore((state) => state.user);
  const canManageTwin = hasMinimumRole(user?.role ?? "", "scientist");

  const twin = useTwin(twinId);
  const updateTwin = useUpdateTwin(twinId);
  const deleteTwin = useDeleteTwin();
  const simulate = useSimulateTwin();
  const predictTwin = usePredictTwinStep(twinId);
  const updateObservations = useUpdateTwinObservations(twinId);

  const [showDelete, setShowDelete] = useState(false);
  const [editOpen, setEditOpen] = useState(false);

  const simForm = useForm<SimFormData>({
    resolver: zodResolver(simSchema),
    defaultValues: { duration_hours: 72, time_step: 1, temperature: "", moisture: "", feed_rate: "" },
  });
  const predictForm = useForm<PredictFormData>({
    resolver: zodResolver(predictSchema),
    defaultValues: { dt: 1, feed_rate: "", ventilation: "", heating: "" },
  });
  const observationForm = useForm<ObservationFormData>({
    resolver: zodResolver(observationSchema),
    defaultValues: { weight: "", temperature: "", moisture: "" },
  });

  const editForm = useForm<TwinEditFormData>({
    resolver: zodResolver(twinEditSchema),
  });

  const twinSummary = useMemo(
    () => ({
      thermalBand: twin.data
        ? `${formatNumber(twin.data.parameters.temp_opt - twin.data.parameters.temp_range, 1)} to ${formatNumber(twin.data.parameters.temp_opt + twin.data.parameters.temp_range, 1)} C`
        : "Pending",
      moistureBand: twin.data
        ? `${formatNumber(twin.data.parameters.moisture_opt - twin.data.parameters.moisture_range, 1)} to ${formatNumber(twin.data.parameters.moisture_opt + twin.data.parameters.moisture_range, 1)}%`
        : "Pending",
    }),
    [twin.data],
  );

  if (twin.isLoading) return <SpinnerOverlay label="Loading twin command center" />;
  if (twin.isError) return <ErrorState onRetry={() => twin.refetch()} />;
  if (!twin.data) return <ErrorState title="Twin not found" />;

  const t = twin.data;
  const simResult = simulate.data;
  const predictResult = predictTwin.data;
  const observationResult = updateObservations.data;
  const canOperateTwin = hasMinimumRole(user?.role ?? "", "operator");
  const canRunSimulation = canManageTwin && t.is_active;
  const canRunRuntimeControls = canOperateTwin && t.is_active;

  const onSimulate = (data: SimFormData) => {
    if (!canRunSimulation) return;

    const payload: TwinSimulateRequest = {
      duration_hours: data.duration_hours,
      time_step: data.time_step,
      temperature: optionalNumber(data.temperature),
      moisture: optionalNumber(data.moisture),
      feed_rate: optionalNumber(data.feed_rate),
    };

    simulate.mutate({ id: twinId, payload });
  };

  const onPredict = (data: PredictFormData) => {
    if (!canRunRuntimeControls) return;

    predictTwin.mutate({
      dt: data.dt,
      feed_rate: optionalNumber(data.feed_rate),
      ventilation: optionalNumber(data.ventilation),
      heating: optionalNumber(data.heating),
    });
  };

  const onObservationUpdate = (data: ObservationFormData) => {
    if (!canRunRuntimeControls) return;

    updateObservations.mutate({
      weight: optionalNumber(data.weight),
      temperature: optionalNumber(data.temperature),
      moisture: optionalNumber(data.moisture),
    });
  };

  const openEdit = () => {
    if (!canManageTwin) return;

    editForm.reset({
      name: t.name,
      status: t.is_active ? "active" : "inactive",
      description: t.description ?? "",
      mu_max: t.parameters.mu_max,
      temp_opt: t.parameters.temp_opt,
      moisture_opt: t.parameters.moisture_opt,
    });
    setEditOpen(true);
  };

  const onEdit = async (values: TwinEditFormData) => {
    if (!canManageTwin) return;

    await updateTwin.mutateAsync({
      name: values.name,
      is_active: values.status === "active",
      description: values.description || undefined,
      parameters: {
        mu_max: values.mu_max,
        temp_opt: values.temp_opt,
        moisture_opt: values.moisture_opt,
      },
    });
    setEditOpen(false);
  };

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
              <CockpitSectionLabel>Twin Command Center</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                {t.name}
              </h1>
              <p className="mt-3 text-xs uppercase tracking-[0.22em] text-surface-500">
                Twin ID {t.twin_id}
              </p>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                Model inspection, runtime control, and trajectory review in one digital twin surface.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="info">{t.species ?? "Unknown species"}</Badge>
              <Badge variant={t.is_active ? "success" : "warning"} dot>
                {t.is_active ? "Active" : "Inactive"}
              </Badge>
              <Button variant="ghost" leftIcon={<ArrowLeft className="h-4 w-4" />} onClick={() => navigate("/twins")}>
                Back
              </Button>
              <Button
                variant="secondary"
                leftIcon={<Edit3 className="h-4 w-4" />}
                onClick={openEdit}
                disabled={!canManageTwin}
                title={!canManageTwin ? "Scientist role required to edit twins" : undefined}
              >
                Edit
              </Button>
              <Button
                variant="danger"
                leftIcon={<Trash2 className="h-4 w-4" />}
                onClick={() => setShowDelete(true)}
                disabled={!canManageTwin}
                title={!canManageTwin ? "Scientist role required to delete twins" : undefined}
              >
                Delete
              </Button>
            </div>
          </div>

          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-5">
            <CockpitMetric
              label="Twin ID"
              value={t.twin_id}
              hint="Stable backend identifier"
              accent="cyan"
            />
            <CockpitMetric
              label="Status"
              value={t.is_active ? "Active" : "Inactive"}
              hint={t.is_active ? "Available for simulation and maintenance" : "Retained for reference only"}
              accent="violet"
            />
            <CockpitMetric
              label="Species"
              value={t.species ?? "Unknown"}
              hint={`Created ${formatDate(t.created_at)}`}
              accent="amber"
            />
            <CockpitMetric
              label="mu max"
              value={formatNumber(t.parameters.mu_max, 3)}
              hint="Maximum specific growth rate"
              accent="neutral"
            />
            <CockpitMetric
              label="Thermal band"
              value={twinSummary.thermalBand}
              hint={twinSummary.moistureBand}
              accent="neutral"
            />
          </CockpitGrid>

          {!canManageTwin ? (
            <p className="text-xs text-surface-400">
              {canOperateTwin
                ? "This account can advance twin state and apply observations, but simulation, configuration edits, and deletion require scientist or admin access."
                : "This account can inspect twin details, but runtime actions require operator or higher access."}
            </p>
          ) : null}
        </div>
      </CockpitPanel>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-6">
          <CockpitPanel tone="emphasis" className="p-5 lg:p-6">
            <CardHeader
              title="Model profile"
              description={t.description ?? "No description supplied for this twin."}
            />
            <CardBody>
              <div className="grid gap-3 sm:grid-cols-2">
                {Object.entries(t.parameters).map(([key, value]) => (
                  <SurfaceTile key={key} className="px-4 py-3">
                    <p className="metric-kicker">{key}</p>
                    <p className="mt-2 text-lg font-semibold text-white">{formatNumber(value, 4)}</p>
                  </SurfaceTile>
                ))}
              </div>
            </CardBody>
          </CockpitPanel>

          <CockpitPanel className="p-5 lg:p-6">
            <CardHeader
              title="Current twin state"
              description="Live state vector currently stored for this twin."
            />
            <CardBody>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
                  <p className="assistant-section-kicker !text-surface-500">Biomass</p>
                  <p className="mt-2 text-lg font-semibold text-white">{formatNumber(t.state.biomass, 3)} kg</p>
                </div>
                <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
                  <p className="assistant-section-kicker !text-surface-500">Substrate</p>
                  <p className="mt-2 text-lg font-semibold text-white">{formatNumber(t.state.substrate, 3)} kg</p>
                </div>
                <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
                  <p className="assistant-section-kicker !text-surface-500">Temperature</p>
                  <p className="mt-2 text-lg font-semibold text-white">{formatNumber(t.state.temperature, 2)} C</p>
                </div>
                <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
                  <p className="assistant-section-kicker !text-surface-500">Moisture</p>
                  <p className="mt-2 text-lg font-semibold text-white">{formatNumber(t.state.moisture, 2)}%</p>
                </div>
                <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
                  <p className="assistant-section-kicker !text-surface-500">Nitrogen</p>
                  <p className="mt-2 text-lg font-semibold text-white">{formatNumber(t.state.nitrogen, 3)}</p>
                </div>
                <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
                  <p className="assistant-section-kicker !text-surface-500">Timestamp</p>
                  <p className="mt-2 text-lg font-semibold text-white">{formatNumber(t.state.timestamp_hours, 2)} h</p>
                </div>
              </div>
            </CardBody>
          </CockpitPanel>

          <CockpitPanel className="p-5 lg:p-6">
            <CardHeader
              title="Runtime operation readout"
              description="Latest predict-step and observation-update results for this session."
            />
            <CardBody className="space-y-4">
              {predictResult ? (
                <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="assistant-section-kicker">Latest predict step</p>
                    <Badge variant="info" dot>
                      Timestamp {formatNumber(predictResult.timestamp_hours, 2)} h
                    </Badge>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div>
                      <p className="assistant-section-kicker !text-surface-500">Growth rate</p>
                      <p className="mt-2 text-lg font-semibold text-white">
                        {formatNumber(predictResult.growth_rate, 5)}
                      </p>
                    </div>
                    <div>
                      <p className="assistant-section-kicker !text-surface-500">Instant SER</p>
                      <p className="mt-2 text-lg font-semibold text-white">
                        {formatNumber(predictResult.ser_instantaneous, 5)}
                      </p>
                    </div>
                    <div>
                      <p className="assistant-section-kicker !text-surface-500">Version</p>
                      <p className="mt-2 text-lg font-semibold text-white">{predictResult.version}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm text-surface-400">
                  No predict step has been executed in this session.
                </div>
              )}

              {observationResult ? (
                <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="assistant-section-kicker">Latest observation update</p>
                    <Badge variant="brand" dot>
                      Version {observationResult.version}
                    </Badge>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    {observationResult.innovation.map((value, index) => (
                      <SurfaceTile key={`${index}-${value}`} className="px-3 py-3">
                        <p className="assistant-section-kicker !text-surface-500">Innovation {index + 1}</p>
                        <p className="mt-2 text-lg font-semibold text-white">{formatNumber(value, 4)}</p>
                      </SurfaceTile>
                    ))}
                  </div>
                </div>
              ) : (
                <SurfaceTile className="px-4 py-3 text-sm text-surface-400">
                  No observation update has been applied in this session.
                </SurfaceTile>
              )}
            </CardBody>
          </CockpitPanel>

          <CockpitPanel className="p-5 lg:p-6">
            <CardHeader
              title="Simulation controls"
              description="Override environmental parameters and run a scenario against the current twin."
            />
            <CardBody>
              <form onSubmit={simForm.handleSubmit(onSimulate)} className="space-y-4" noValidate>
                {!canManageTwin ? (
                  <div className="rounded-2xl border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                    The backend only allows scientist and admin roles to run twin simulations.
                  </div>
                ) : !t.is_active ? (
                  <div className="rounded-2xl border border-surface-400/20 bg-surface-500/10 px-4 py-3 text-sm text-surface-200">
                    This twin is inactive. Re-activate it in the edit panel before running new simulations.
                  </div>
                ) : null}
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="Duration (hours)"
                    type="number"
                    error={simForm.formState.errors.duration_hours?.message}
                    disabled={!canRunSimulation}
                    {...simForm.register("duration_hours")}
                  />
                  <Input
                    label="Time step"
                    type="number"
                    step="0.1"
                    error={simForm.formState.errors.time_step?.message}
                    disabled={!canRunSimulation}
                    {...simForm.register("time_step")}
                  />
                  <Input
                    label="Temperature"
                    type="number"
                    step="0.1"
                    placeholder={`Default ${t.parameters.temp_opt}`}
                    disabled={!canRunSimulation}
                    {...simForm.register("temperature")}
                  />
                  <Input
                    label="Moisture"
                    type="number"
                    step="0.1"
                    placeholder={`Default ${t.parameters.moisture_opt}`}
                    disabled={!canRunSimulation}
                    {...simForm.register("moisture")}
                  />
                  <Input
                    label="Feed rate"
                    type="number"
                    step="0.01"
                    placeholder="Optional"
                    disabled={!canRunSimulation}
                    {...simForm.register("feed_rate")}
                  />
                </div>

                <Button
                  type="submit"
                  fullWidth
                  loading={simulate.isPending}
                  leftIcon={<Play className="h-4 w-4" />}
                  disabled={!canRunSimulation}
                >
                  Run simulation
                </Button>
              </form>
            </CardBody>
          </CockpitPanel>

          <CockpitPanel className="p-5 lg:p-6">
            <CardHeader
              title="Predict next step"
              description="Advance the twin state by one predictive control step."
            />
            <CardBody>
              <form onSubmit={predictForm.handleSubmit(onPredict)} className="space-y-4" noValidate>
                {!canOperateTwin ? (
                  <div className="rounded-2xl border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                    Operator or higher access is required to advance the twin state.
                  </div>
                ) : !t.is_active ? (
                  <div className="rounded-2xl border border-surface-400/20 bg-surface-500/10 px-4 py-3 text-sm text-surface-200">
                    This twin is inactive. Re-activate it before running predictive control steps.
                  </div>
                ) : null}
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="Step dt (hours)"
                    type="number"
                    step="0.1"
                    error={predictForm.formState.errors.dt?.message}
                    disabled={!canRunRuntimeControls}
                    {...predictForm.register("dt")}
                  />
                  <Input
                    label="Feed rate"
                    type="number"
                    step="0.01"
                    placeholder="Optional"
                    disabled={!canRunRuntimeControls}
                    {...predictForm.register("feed_rate")}
                  />
                  <Input
                    label="Ventilation"
                    type="number"
                    step="0.01"
                    placeholder="Optional"
                    disabled={!canRunRuntimeControls}
                    {...predictForm.register("ventilation")}
                  />
                  <Input
                    label="Heating"
                    type="number"
                    step="0.01"
                    placeholder="Optional"
                    disabled={!canRunRuntimeControls}
                    {...predictForm.register("heating")}
                  />
                </div>
                <Button
                  type="submit"
                  fullWidth
                  loading={predictTwin.isPending}
                  leftIcon={<Radar className="h-4 w-4" />}
                  disabled={!canRunRuntimeControls}
                >
                  Predict step
                </Button>
              </form>
            </CardBody>
          </CockpitPanel>

          <CockpitPanel className="p-5 lg:p-6">
            <CardHeader
              title="Apply observations"
              description="Correct the twin state with live sensor observations."
            />
            <CardBody>
              <form
                onSubmit={observationForm.handleSubmit(onObservationUpdate)}
                className="space-y-4"
                noValidate
              >
                {!canOperateTwin ? (
                  <div className="rounded-2xl border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                    Operator or higher access is required to apply observations.
                  </div>
                ) : !t.is_active ? (
                  <div className="rounded-2xl border border-surface-400/20 bg-surface-500/10 px-4 py-3 text-sm text-surface-200">
                    This twin is inactive. Re-activate it before applying live observations.
                  </div>
                ) : null}
                <div className="grid gap-4 sm:grid-cols-3">
                  <Input
                    label="Observed weight"
                    type="number"
                    step="0.01"
                    placeholder="Optional"
                    disabled={!canRunRuntimeControls}
                    {...observationForm.register("weight")}
                  />
                  <Input
                    label="Observed temperature"
                    type="number"
                    step="0.1"
                    placeholder="Optional"
                    disabled={!canRunRuntimeControls}
                    {...observationForm.register("temperature")}
                  />
                  <Input
                    label="Observed moisture"
                    type="number"
                    step="0.1"
                    placeholder="Optional"
                    disabled={!canRunRuntimeControls}
                    {...observationForm.register("moisture")}
                  />
                </div>
                <Button
                  type="submit"
                  fullWidth
                  loading={updateObservations.isPending}
                  leftIcon={<Save className="h-4 w-4" />}
                  disabled={!canRunRuntimeControls}
                >
                  Apply observations
                </Button>
              </form>
            </CardBody>
          </CockpitPanel>
        </div>

        <div className="space-y-6">
          <CockpitPanel tone="emphasis" className="overflow-hidden p-0">
            <div className="border-b border-white/8 px-6 py-5">
              <CardHeader
                title="Simulation result surface"
                description="Trajectory, computed SER, and final state in one visual readout."
              />
            </div>

            {simResult ? (
              <>
                <div className="grid grid-cols-2 gap-4 px-5 py-5 sm:grid-cols-4">
                  <div className="assistant-thread-shell rounded-[22px] border border-white/8 px-4 py-4">
                    <p className="assistant-section-kicker">Computed SER</p>
                    <p className="mt-3 text-2xl font-semibold text-white">{formatNumber(simResult.computed_ser, 4)}</p>
                  </div>
                  <div className="assistant-thread-shell rounded-[22px] border border-white/8 px-4 py-4">
                    <p className="assistant-section-kicker">Final biomass</p>
                    <p className="mt-3 text-2xl font-semibold text-white">{formatNumber(simResult.final_biomass, 3)}</p>
                    <p className="mt-1 text-xs text-surface-400">kg</p>
                  </div>
                  <div className="assistant-thread-shell rounded-[22px] border border-white/8 px-4 py-4">
                    <p className="assistant-section-kicker">Final substrate</p>
                    <p className="mt-3 text-2xl font-semibold text-white">{formatNumber(simResult.final_substrate, 3)}</p>
                    <p className="mt-1 text-xs text-surface-400">kg</p>
                  </div>
                  <div className="assistant-thread-shell rounded-[22px] border border-white/8 px-4 py-4">
                    <p className="assistant-section-kicker">Peak growth</p>
                    <p className="mt-3 text-2xl font-semibold text-white">{formatNumber(simResult.peak_growth_rate, 5)}</p>
                    <p className="mt-1 text-xs text-surface-400">1/h</p>
                  </div>
                </div>

                <div className="px-2 pb-5">
                  <TwinTrajectoryChart data={simResult.trajectory} />
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-surface-400">
                <Cpu className="mb-3 h-10 w-10 text-surface-500" />
                <p className="text-sm">Run a simulation to populate the trajectory surface.</p>
              </div>
            )}
          </CockpitPanel>

          <CockpitPanel className="p-5 lg:p-6">
            <CardHeader
              title="Simulation posture"
              description="Interpretation of the latest simulation run."
            />
            <CardBody className="space-y-3">
              {simResult ? (
                <>
                  <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="assistant-section-kicker">Current state</p>
                      <Badge variant={simResult.computed_ser <= 0.12 ? "success" : "warning"} dot>
                        {simResult.computed_ser <= 0.12 ? "In preferred window" : "Needs tuning"}
                      </Badge>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-surface-300">
                      Duration {simResult.duration_hours}h with compute time {formatNumber(simResult.computation_time_ms, 1)} ms.
                    </p>
                  </div>
                  <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3 text-sm leading-6 text-surface-300">
                    Use the trajectory panel to compare biomass gain against substrate drawdown and see whether the scenario warrants retuning.
                  </div>
                </>
              ) : (
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm text-surface-400">
                  No simulation run has been executed in this session.
                </div>
              )}
            </CardBody>
          </CockpitPanel>
        </div>
      </div>

      <Modal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title="Edit digital twin"
        description="Update identity and top-level operating defaults."
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={editForm.handleSubmit(onEdit)}
              loading={updateTwin.isPending}
              disabled={!canManageTwin}
            >
              Save changes
            </Button>
          </>
        }
      >
        <form className="space-y-4" onSubmit={editForm.handleSubmit(onEdit)} noValidate>
          {!canManageTwin ? (
            <div className="rounded-2xl border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              Twin edits are limited to scientist and admin roles.
            </div>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-1">
            <Input
              label="Twin name"
              error={editForm.formState.errors.name?.message}
              disabled={!canManageTwin}
              {...editForm.register("name")}
            />
          </div>
          <Select
            label="Status"
            helperText="Maps directly to the backend is_active flag."
            options={[
              { value: "active", label: "Active" },
              { value: "inactive", label: "Inactive" },
            ]}
            disabled={!canManageTwin}
            {...editForm.register("status")}
          />
          <Textarea
            label="Description"
            rows={3}
            helperText="Stored in twin config because the backend does not expose a top-level description field."
            disabled={!canManageTwin}
            {...editForm.register("description")}
          />
          <div className="grid gap-4 sm:grid-cols-3">
            <Input
              label="mu max"
              type="number"
              step="0.001"
              error={editForm.formState.errors.mu_max?.message}
              disabled={!canManageTwin}
              {...editForm.register("mu_max")}
            />
            <Input
              label="Temp opt"
              type="number"
              step="0.1"
              error={editForm.formState.errors.temp_opt?.message}
              disabled={!canManageTwin}
              {...editForm.register("temp_opt")}
            />
            <Input
              label="Moisture opt"
              type="number"
              step="0.1"
              error={editForm.formState.errors.moisture_opt?.message}
              disabled={!canManageTwin}
              {...editForm.register("moisture_opt")}
            />
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={async () => {
          if (!canManageTwin) return;
          await deleteTwin.mutateAsync(twinId);
          navigate("/twins");
        }}
        title="Delete twin"
        message={`Delete "${t.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        variant="danger"
        loading={deleteTwin.isPending}
      />
    </div>
  );
}
