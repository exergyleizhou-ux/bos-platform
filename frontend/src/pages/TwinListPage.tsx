import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Cpu, Plus, Sparkles } from "lucide-react";

import { useCreateTwin, useTwinList } from "@/hooks/useTwin";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, StatCard } from "@/components/ui/Card";
import { EmptyState, ErrorState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { SpinnerOverlay } from "@/components/ui/Spinner";
import { Textarea } from "@/components/ui/Textarea";
import { DEFAULT_TWIN_PARAMETERS } from "@/types/twin";
import { formatDate, formatNumber } from "@/lib/utils";

const PAGE_SIZE = 12;

const twinSchema = z.object({
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

  const { data, isLoading, isError, refetch } = useTwinList(page, PAGE_SIZE);
  const createTwin = useCreateTwin();

  const form = useForm<TwinFormData>({
    resolver: zodResolver(twinSchema),
    defaultValues: {
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
      avgMuMax,
      avgTemp,
      speciesCount,
    };
  }, [data]);

  const onCreate = async (values: TwinFormData) => {
    const created = await createTwin.mutateAsync({
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
    <div className="space-y-6">
      <PageHeader
        eyebrow="Digital Twins"
        title="Twin portfolio console"
        description="Inspect available digital twins, tune model defaults, and launch a new simulation asset without leaving the portfolio surface."
        badges={[
          { label: "Forecast support", variant: "info" },
          { label: "Model-driven", variant: "brand" },
        ]}
        actions={
          <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setCreateOpen(true)}>
            New twin
          </Button>
        }
        stats={[
          {
            label: "Published twins",
            value: portfolioSummary?.count ?? data?.total ?? "Loading",
            hint: "Current digital twin inventory",
          },
          {
            label: "Species coverage",
            value: portfolioSummary?.speciesCount ?? "Loading",
            hint: "Distinct modeled species",
          },
          {
            label: "Avg mu max",
            value: portfolioSummary ? formatNumber(portfolioSummary.avgMuMax, 3) : "Loading",
            hint: "Portfolio growth-rate baseline",
          },
          {
            label: "Avg temp opt",
            value: portfolioSummary ? `${formatNumber(portfolioSummary.avgTemp, 1)} C` : "Loading",
            hint: "Typical thermal operating point",
          },
        ]}
      />

      {isLoading ? (
        <SpinnerOverlay label="Loading twin portfolio" />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : !data?.items?.length ? (
        <EmptyState
          icon={<Cpu className="h-12 w-12" />}
          title="No digital twins"
          description="Create the first digital twin to enable simulation and forecast support."
          actionLabel="Create twin"
          onAction={() => setCreateOpen(true)}
        />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Total twins" value={data.total} icon={<Cpu className="h-5 w-5" />} color="blue" />
            <StatCard
              label="Species classes"
              value={portfolioSummary?.speciesCount ?? "N/A"}
              icon={<Sparkles className="h-5 w-5" />}
              color="green"
            />
            <StatCard
              label="Avg mu max"
              value={portfolioSummary ? formatNumber(portfolioSummary.avgMuMax, 3) : "N/A"}
              color="amber"
            />
            <StatCard
              label="Avg temp"
              value={portfolioSummary ? formatNumber(portfolioSummary.avgTemp, 1) : "N/A"}
              unit="C"
              color="neutral"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.items.map((twin) => (
              <Card
                key={twin.id}
                hover
                tone="strong"
                onClick={() => navigate(`/twins/${twin.id}`)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-brand-400/20 bg-brand-500/15 text-brand-200 shadow-glow">
                      <Cpu className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="truncate text-lg font-semibold text-white">{twin.name}</h3>
                      <p className="mt-1 text-sm text-surface-400">{twin.species ?? "Unknown species"}</p>
                    </div>
                  </div>
                  <Badge variant="info">Twin</Badge>
                </div>

                <p className="mt-4 line-clamp-3 text-sm leading-6 text-surface-300">
                  {twin.description ?? "No description provided."}
                </p>

                <div className="mt-5 grid grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-white/8 bg-white/5 px-3 py-3">
                    <p className="metric-kicker">mu max</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {formatNumber(twin.parameters.mu_max, 3)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/5 px-3 py-3">
                    <p className="metric-kicker">Temp opt</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {formatNumber(twin.parameters.temp_opt, 1)} C
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between text-xs text-surface-500">
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
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={form.handleSubmit(onCreate)} loading={createTwin.isPending}>
              Create twin
            </Button>
          </>
        }
      >
        <form className="space-y-4" onSubmit={form.handleSubmit(onCreate)} noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Twin name"
              error={form.formState.errors.name?.message}
              {...form.register("name")}
            />
            <Input label="Species" {...form.register("species")} />
          </div>

          <Textarea label="Description" rows={3} {...form.register("description")} />

          <div className="grid gap-4 sm:grid-cols-3">
            <Input
              label="mu max"
              type="number"
              step="0.001"
              error={form.formState.errors.mu_max?.message}
              {...form.register("mu_max")}
            />
            <Input
              label="Temp opt"
              type="number"
              step="0.1"
              error={form.formState.errors.temp_opt?.message}
              {...form.register("temp_opt")}
            />
            <Input
              label="Moisture opt"
              type="number"
              step="0.1"
              error={form.formState.errors.moisture_opt?.message}
              {...form.register("moisture_opt")}
            />
          </div>
        </form>
      </Modal>
    </div>
  );
}
