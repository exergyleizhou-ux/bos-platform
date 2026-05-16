import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Cpu, Plus } from "lucide-react";

import { useCreateTwin, useTwinList } from "@/hooks/useTwin";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { EmptyState, ErrorState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Pagination } from "@/components/ui/Pagination";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { Textarea } from "@/components/ui/Textarea";
import { useAuthStore } from "@/store/authStore";
import { hasMinimumRole } from "@/types/auth";
import { DEFAULT_TWIN_PARAMETERS } from "@/types/twin";
import { formatDate, formatNumber } from "@/lib/utils";

const PAGE_SIZE = 12;
const FILTER_OPTIONS = [
  { value: "all", label: "All twins" },
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
] as const;

const twinSchema = z.object({
  twin_id: z.string().max(100, "Max 100 characters").optional(),
  name: z.string().min(1, "Name is required"),
  species: z.string().optional(),
  description: z.string().optional(),
  mu_max: z.coerce.number().positive(),
  temp_opt: z.coerce.number().positive(),
  moisture_opt: z.coerce.number().min(0).max(100),
});

type TwinFormData = z.infer<typeof twinSchema>;

export default function TwinListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<(typeof FILTER_OPTIONS)[number]["value"]>("all");
  const user = useAuthStore((state) => state.user);
  const canCreateTwin = hasMinimumRole(user?.role ?? "", "scientist");
  const isActiveFilter =
    statusFilter === "all" ? undefined : statusFilter === "active";

  const { data, isLoading, isError, refetch } = useTwinList(page, PAGE_SIZE, isActiveFilter);
  const createTwin = useCreateTwin();

  const form = useForm<TwinFormData>({
    resolver: zodResolver(twinSchema),
    defaultValues: {
      twin_id: "",
      name: "",
      species: "",
      description: "",
      mu_max: DEFAULT_TWIN_PARAMETERS.mu_max,
      temp_opt: DEFAULT_TWIN_PARAMETERS.temp_opt,
      moisture_opt: DEFAULT_TWIN_PARAMETERS.moisture_opt,
    },
  });

  const portfolioSummary = useMemo(() => {
    if (!data?.items?.length) return null;

    const avgMuMax =
      data.items.reduce((sum, twin) => sum + twin.parameters.mu_max, 0) / data.items.length;
    const avgTemp =
      data.items.reduce((sum, twin) => sum + twin.parameters.temp_opt, 0) / data.items.length;
    const speciesCount = new Set(data.items.map((twin) => twin.species ?? "Unknown")).size;

    return {
      count: data.total,
      activeCount: data.items.filter((twin) => twin.is_active).length,
      avgMuMax,
      avgTemp,
      speciesCount,
    };
  }, [data]);

  const onCreate = async (values: TwinFormData) => {
    if (!canCreateTwin) return;

    const created = await createTwin.mutateAsync({
      twin_id: values.twin_id?.trim() || undefined,
      name: values.name,
      species: values.species || undefined,
      description: values.description || undefined,
      parameters: {
        mu_max: values.mu_max,
        temp_opt: values.temp_opt,
        moisture_opt: values.moisture_opt,
      },
    });

    setCreateOpen(false);
    form.reset();
    navigate(`/twins/${created.id}`);
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
              <CockpitSectionLabel>Digital Twins</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                Twin portfolio console
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                Inspect the current twin fleet, route into individual command centers, and
                spin up new simulation assets without leaving the portfolio surface.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="info">Forecast support</Badge>
              <Badge variant="brand">Model-driven</Badge>
              <Badge variant="neutral">{statusFilter === "all" ? "Full portfolio" : `${statusFilter} focus`}</Badge>
            </div>
          </div>

          {portfolioSummary ? (
            <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
              <CockpitMetric
                label={statusFilter === "all" ? "Total twins" : `${statusFilter} twins`}
                value={String(data?.total ?? 0)}
                hint={`${portfolioSummary.activeCount} active`}
                accent="cyan"
              />
              <CockpitMetric
                label="Species classes"
                value={String(portfolioSummary.speciesCount)}
                hint="Distinct model cohorts"
                accent="violet"
              />
              <CockpitMetric
                label="Avg mu max"
                value={formatNumber(portfolioSummary.avgMuMax, 3)}
                hint="Portfolio growth ceiling"
                accent="amber"
              />
              <CockpitMetric
                label="Avg temp opt"
                value={formatNumber(portfolioSummary.avgTemp, 1)}
                hint="Preferred thermal center (C)"
                accent="neutral"
              />
            </CockpitGrid>
          ) : null}
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <CockpitSectionLabel>Portfolio controls</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              Filter the fleet by active state, then open a twin detail surface or create
              a new twin if your role allows it.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="assistant-thread-shell rounded-2xl border border-white/8 px-1.5 py-1">
              <div className="flex items-center gap-1">
                {FILTER_OPTIONS.map((option) => {
                  const selected = statusFilter === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        setStatusFilter(option.value);
                        setPage(1);
                      }}
                      className={[
                        "rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                        selected
                          ? "bg-white/12 text-white"
                          : "text-surface-400 hover:bg-white/6 hover:text-surface-200",
                      ].join(" ")}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <Button
              leftIcon={<Plus className="h-4 w-4" />}
              onClick={() => setCreateOpen(true)}
              disabled={!canCreateTwin}
              title={!canCreateTwin ? "Scientist role required to create twins" : undefined}
            >
              New twin
            </Button>
          </div>
        </div>

        {!canCreateTwin ? (
          <p className="mt-4 text-xs text-surface-400">
            Your current role has read-only access here. A scientist or admin account is required to create digital twins.
          </p>
        ) : null}
      </CockpitPanel>

      {isLoading ? (
        <SpinnerOverlay label="Loading twin portfolio" />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : !data?.items?.length ? (
        <CockpitPanel className="p-5 lg:p-6">
          <EmptyState
            icon={<Cpu className="h-12 w-12" />}
            title="No digital twins"
            description={
              canCreateTwin
                ? "Create the first digital twin to enable simulation and forecast support."
                : "No digital twins are available yet. A scientist or admin account is required to create one."
            }
            actionLabel={canCreateTwin ? "Create twin" : undefined}
            onAction={canCreateTwin ? () => setCreateOpen(true) : undefined}
          />
        </CockpitPanel>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.items.map((twin) => (
              <Card
                key={twin.id}
                hover
                className="assistant-aside-card rounded-[28px]"
                onClick={() => navigate(`/twins/${twin.id}`)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="assistant-thread-shell flex h-12 w-12 items-center justify-center rounded-2xl border border-brand-400/20 text-brand-200 shadow-glow">
                      <Cpu className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="truncate text-lg font-semibold text-white">{twin.name}</h3>
                      <p className="mt-1 truncate text-[0.68rem] uppercase tracking-[0.22em] text-surface-500">
                        {twin.twin_id}
                      </p>
                      <p className="mt-1 text-sm text-surface-400">{twin.species ?? "Unknown species"}</p>
                    </div>
                  </div>
                  <Badge variant={twin.is_active ? "success" : "warning"} dot>
                    {twin.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>

                <p className="mt-4 line-clamp-3 text-sm leading-6 text-surface-300">
                  {twin.description ?? "No description provided."}
                </p>

                <div className="mt-5 grid grid-cols-2 gap-3">
                  <div className="assistant-thread-shell rounded-2xl border border-white/8 px-3 py-3">
                    <p className="assistant-section-kicker !text-surface-500">mu max</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {formatNumber(twin.parameters.mu_max, 3)}
                    </p>
                  </div>
                  <div className="assistant-thread-shell rounded-2xl border border-white/8 px-3 py-3">
                    <p className="assistant-section-kicker !text-surface-500">Temp opt</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {formatNumber(twin.parameters.temp_opt, 1)} C
                    </p>
                  </div>
                </div>

                <div className="assistant-meta-panel mt-4 flex items-center justify-between rounded-2xl border border-white/8 px-3 py-2.5 text-xs text-surface-500">
                  <span>{twin.is_active ? "Ready for simulation" : "Inactive twin"}</span>
                  <span>{twin.twin_id}</span>
                </div>

                <div className="assistant-meta-panel mt-2 flex items-center justify-between rounded-2xl border border-white/8 px-3 py-2.5 text-xs text-surface-500">
                  <span>Moisture {formatNumber(twin.parameters.moisture_opt, 1)}%</span>
                  <span>{formatDate(twin.created_at)}</span>
                </div>
              </Card>
            ))}
          </div>

          <Pagination
            page={page}
            totalPages={data.total_pages}
            total={data.total}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
          />
        </>
      )}

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create digital twin"
        description="Spin up a new simulation asset with a minimal but meaningful parameter set."
        size="lg"
        className="assistant-aside-card rounded-[28px]"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={form.handleSubmit(onCreate)}
              loading={createTwin.isPending}
              disabled={!canCreateTwin}
            >
              Create twin
            </Button>
          </>
        }
      >
        <form className="space-y-4" onSubmit={form.handleSubmit(onCreate)} noValidate>
          {!canCreateTwin ? (
            <div className="rounded-2xl border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              Twin creation is limited to scientist and admin roles because the backend rejects lower-privilege create requests.
            </div>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Twin ID"
              helperText="Optional stable identifier. Leave blank to auto-generate."
              className="batch-create-field"
              disabled={!canCreateTwin}
              {...form.register("twin_id")}
            />
            <Input
              label="Twin name"
              error={form.formState.errors.name?.message}
              className="batch-create-field"
              disabled={!canCreateTwin}
              {...form.register("name")}
            />
            <Input
              label="Species"
              className="batch-create-field"
              disabled={!canCreateTwin}
              {...form.register("species")}
            />
          </div>

          <Textarea
            label="Description"
            rows={3}
            className="batch-create-notes"
            disabled={!canCreateTwin}
            {...form.register("description")}
          />

          <div className="grid gap-4 sm:grid-cols-3">
            <Input
              label="mu max"
              type="number"
              step="0.001"
              error={form.formState.errors.mu_max?.message}
              className="batch-create-field"
              disabled={!canCreateTwin}
              {...form.register("mu_max")}
            />
            <Input
              label="Temp opt"
              type="number"
              step="0.1"
              error={form.formState.errors.temp_opt?.message}
              className="batch-create-field"
              disabled={!canCreateTwin}
              {...form.register("temp_opt")}
            />
            <Input
              label="Moisture opt"
              type="number"
              step="0.1"
              error={form.formState.errors.moisture_opt?.message}
              className="batch-create-field"
              disabled={!canCreateTwin}
              {...form.register("moisture_opt")}
            />
          </div>
        </form>
      </Modal>
    </div>
  );
}
