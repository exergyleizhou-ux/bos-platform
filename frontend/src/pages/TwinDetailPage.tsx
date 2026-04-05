import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, Cpu, Edit3, Play, Trash2 } from "lucide-react";

import { useDeleteTwin, useSimulateTwin, useTwin, useUpdateTwin } from "@/hooks/useTwin";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, StatCard } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ErrorState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { Textarea } from "@/components/ui/Textarea";
import { TwinTrajectoryChart } from "@/components/charts/TwinTrajectoryChart";
import { formatDate, formatNumber } from "@/lib/utils";
import type { TwinSimulateRequest } from "@/types/twin";

const simSchema = z.object({
  duration_hours: z.coerce.number().min(1).max(720),
  time_step: z.coerce.number().min(0.01).max(10),
  temperature: z.union([z.coerce.number(), z.literal("")]).optional(),
  moisture: z.union([z.coerce.number().min(0).max(100), z.literal("")]).optional(),
  feed_rate: z.union([z.coerce.number().positive(), z.literal("")]).optional(),
});

const twinEditSchema = z.object({
  name: z.string().min(1, "Name is required"),
  species: z.string().optional(),
  description: z.string().optional(),
  mu_max: z.coerce.number().positive(),
  temp_opt: z.coerce.number().positive(),
  moisture_opt: z.coerce.number().min(0).max(100),
});

type SimFormData = z.infer<typeof simSchema>;
type TwinEditFormData = z.infer<typeof twinEditSchema>;

function optionalNumber(value: number | "" | undefined) {
  return value === "" || value === undefined ? undefined : Number(value);
}

export default function TwinDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const twinId = Number(id);

  const twin = useTwin(twinId);
  const updateTwin = useUpdateTwin(twinId);
  const deleteTwin = useDeleteTwin();
  const simulate = useSimulateTwin();

  const [showDelete, setShowDelete] = useState(false);
  const [editOpen, setEditOpen] = useState(false);

  const simForm = useForm<SimFormData>({
    resolver: zodResolver(simSchema),
    defaultValues: { duration_hours: 72, time_step: 1, temperature: "", moisture: "", feed_rate: "" },
  });

  const editForm = useForm<TwinEditFormData>({
    resolver: zodResolver(twinEditSchema),
  });

  if (twin.isLoading) return <SpinnerOverlay label="Loading twin command center" />;
  if (twin.isError) return <ErrorState onRetry={() => twin.refetch()} />;
  if (!twin.data) return <ErrorState title="Twin not found" />;

  const t = twin.data;
  const simResult = simulate.data;

  const twinSummary = useMemo(
    () => ({
      thermalBand: `${formatNumber(t.parameters.temp_opt - t.parameters.temp_range, 1)} to ${formatNumber(t.parameters.temp_opt + t.parameters.temp_range, 1)} C`,
      moistureBand: `${formatNumber(t.parameters.moisture_opt - t.parameters.moisture_range, 1)} to ${formatNumber(t.parameters.moisture_opt + t.parameters.moisture_range, 1)}%`,
    }),
    [t.parameters],
  );

  const onSimulate = (data: SimFormData) => {
    const payload: TwinSimulateRequest = {
      duration_hours: data.duration_hours,
      time_step: data.time_step,
      temperature: optionalNumber(data.temperature),
      moisture: optionalNumber(data.moisture),
      feed_rate: optionalNumber(data.feed_rate),
    };

    simulate.mutate({ id: twinId, payload });
  };

  const openEdit = () => {
    editForm.reset({
      name: t.name,
      species: t.species ?? "",
      description: t.description ?? "",
      mu_max: t.parameters.mu_max,
      temp_opt: t.parameters.temp_opt,
      moisture_opt: t.parameters.moisture_opt,
    });
    setEditOpen(true);
  };

  const onEdit = async (values: TwinEditFormData) => {
    await updateTwin.mutateAsync({
      name: values.name,
      species: values.species || undefined,
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
    <div className="space-y-6">
      <PageHeader
        eyebrow="Twin Command Center"
        title={t.name}
        description="Model inspection, simulation control, and trajectory review in one digital twin surface."
        badges={[
          { label: t.species ?? "Unknown species", variant: "info" },
          { label: "Simulation-ready", variant: "brand" },
        ]}
        actions={
          <>
            <Button variant="ghost" leftIcon={<ArrowLeft className="h-4 w-4" />} onClick={() => navigate("/twins")}>
              Back
            </Button>
            <Button variant="secondary" leftIcon={<Edit3 className="h-4 w-4" />} onClick={openEdit}>
              Edit
            </Button>
            <Button variant="danger" leftIcon={<Trash2 className="h-4 w-4" />} onClick={() => setShowDelete(true)}>
              Delete
            </Button>
          </>
        }
        stats={[
          {
            label: "Species",
            value: t.species ?? "Unknown",
            hint: `Created ${formatDate(t.created_at)}`,
          },
          {
            label: "mu max",
            value: formatNumber(t.parameters.mu_max, 3),
            hint: "Maximum specific growth rate",
          },
          {
            label: "Thermal band",
            value: twinSummary.thermalBand,
            hint: "Approximate preferred operating window",
          },
          {
            label: "Moisture band",
            value: twinSummary.moistureBand,
            hint: "Approximate preferred moisture window",
          },
        ]}
      />

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-6">
          <Card tone="strong">
            <CardHeader
              title="Model profile"
              description={t.description ?? "No description supplied for this twin."}
            />
            <CardBody>
              <div className="grid gap-3 sm:grid-cols-2">
                {Object.entries(t.parameters).map(([key, value]) => (
                  <div key={key} className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                    <p className="metric-kicker">{key}</p>
                    <p className="mt-2 text-lg font-semibold text-white">{formatNumber(value, 4)}</p>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Simulation controls"
              description="Override environmental parameters and run a scenario against the current twin."
            />
            <CardBody>
              <form onSubmit={simForm.handleSubmit(onSimulate)} className="space-y-4" noValidate>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="Duration (hours)"
                    type="number"
                    error={simForm.formState.errors.duration_hours?.message}
                    {...simForm.register("duration_hours")}
                  />
                  <Input
                    label="Time step"
                    type="number"
                    step="0.1"
                    error={simForm.formState.errors.time_step?.message}
                    {...simForm.register("time_step")}
                  />
                  <Input
                    label="Temperature"
                    type="number"
                    step="0.1"
                    placeholder={`Default ${t.parameters.temp_opt}`}
                    {...simForm.register("temperature")}
                  />
                  <Input
                    label="Moisture"
                    type="number"
                    step="0.1"
                    placeholder={`Default ${t.parameters.moisture_opt}`}
                    {...simForm.register("moisture")}
                  />
                  <Input
                    label="Feed rate"
                    type="number"
                    step="0.01"
                    placeholder="Optional"
                    {...simForm.register("feed_rate")}
                  />
                </div>

                <Button
                  type="submit"
                  fullWidth
                  loading={simulate.isPending}
                  leftIcon={<Play className="h-4 w-4" />}
                >
                  Run simulation
                </Button>
              </form>
            </CardBody>
          </Card>
        </div>

        <div className="space-y-6">
          <Card tone="strong" noPadding>
            <div className="border-b border-white/8 px-6 py-5">
              <CardHeader
                title="Simulation result surface"
                description="Trajectory, computed SER, and final state in one visual readout."
              />
            </div>

            {simResult ? (
              <>
                <div className="grid grid-cols-2 gap-4 px-5 py-5 sm:grid-cols-4">
                  <StatCard
                    label="Computed SER"
                    value={formatNumber(simResult.computed_ser, 4)}
                    color="green"
                  />
                  <StatCard
                    label="Final biomass"
                    value={formatNumber(simResult.final_biomass, 3)}
                    unit="kg"
                    color="blue"
                  />
                  <StatCard
                    label="Final substrate"
                    value={formatNumber(simResult.final_substrate, 3)}
                    unit="kg"
                    color="amber"
                  />
                  <StatCard
                    label="Peak growth"
                    value={formatNumber(simResult.peak_growth_rate, 5)}
                    unit="1/h"
                    color="neutral"
                  />
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
          </Card>

          <Card>
            <CardHeader
              title="Simulation posture"
              description="Interpretation of the latest simulation run."
            />
            <CardBody className="space-y-3">
              {simResult ? (
                <>
                  <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="metric-kicker">Current state</p>
                      <Badge variant={simResult.computed_ser <= 0.12 ? "success" : "warning"} dot>
                        {simResult.computed_ser <= 0.12 ? "In preferred window" : "Needs tuning"}
                      </Badge>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-surface-300">
                      Duration {simResult.duration_hours}h with compute time {formatNumber(simResult.computation_time_ms, 1)} ms.
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm leading-6 text-surface-300">
                    Use the trajectory panel to compare biomass gain against substrate drawdown and see whether the scenario warrants retuning.
                  </div>
                </>
              ) : (
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm text-surface-400">
                  No simulation run has been executed in this session.
                </div>
              )}
            </CardBody>
          </Card>
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
            <Button onClick={editForm.handleSubmit(onEdit)} loading={updateTwin.isPending}>
              Save changes
            </Button>
          </>
        }
      >
        <form className="space-y-4" onSubmit={editForm.handleSubmit(onEdit)} noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Twin name" error={editForm.formState.errors.name?.message} {...editForm.register("name")} />
            <Input label="Species" {...editForm.register("species")} />
          </div>
          <Textarea label="Description" rows={3} {...editForm.register("description")} />
          <div className="grid gap-4 sm:grid-cols-3">
            <Input
              label="mu max"
              type="number"
              step="0.001"
              error={editForm.formState.errors.mu_max?.message}
              {...editForm.register("mu_max")}
            />
            <Input
              label="Temp opt"
              type="number"
              step="0.1"
              error={editForm.formState.errors.temp_opt?.message}
              {...editForm.register("temp_opt")}
            />
            <Input
              label="Moisture opt"
              type="number"
              step="0.1"
              error={editForm.formState.errors.moisture_opt?.message}
              {...editForm.register("moisture_opt")}
            />
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={async () => {
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
