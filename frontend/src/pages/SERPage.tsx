import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Calculator, History, ShieldCheck, Sparkles } from "lucide-react";

import { SERGauge } from "@/components/charts/SERGauge";
import { GradeBadge, Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { Input } from "@/components/ui/Input";
import { Pagination } from "@/components/ui/Pagination";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  TableSkeleton,
} from "@/components/ui/Table";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { useComputeSER, useSERHistory } from "@/hooks/useSER";
import { formatDateTime, formatNumber } from "@/lib/utils";
import type { SERComputeRequest } from "@/types/ser";

const serSchema = z.object({
  dm_in: z.coerce.number().positive("Must be positive"),
  dm_out: z.coerce.number().nonnegative("Must be >= 0"),
  n_in: z.union([z.coerce.number().positive(), z.literal("")]).optional(),
  n_larvae: z.union([z.coerce.number().positive(), z.literal("")]).optional(),
  n_frass: z.union([z.coerce.number().nonnegative(), z.literal("")]).optional(),
  ash_in: z.union([z.coerce.number().nonnegative(), z.literal("")]).optional(),
  ash_out: z.union([z.coerce.number().nonnegative(), z.literal("")]).optional(),
  fat_in: z.union([z.coerce.number().nonnegative(), z.literal("")]).optional(),
  fat_out: z.union([z.coerce.number().nonnegative(), z.literal("")]).optional(),
});

type SERFormData = z.infer<typeof serSchema>;

function numberOrUndefined(value: number | "" | undefined) {
  return value === "" || value === undefined ? undefined : Number(value);
}

export default function SERPage() {
  const [activeTab, setActiveTab] = useState("compute");
  const [histPage, setHistPage] = useState(1);

  const computeSER = useComputeSER();
  const history = useSERHistory(histPage, 10);

  const form = useForm<SERFormData>({
    resolver: zodResolver(serSchema),
    defaultValues: {
      dm_in: "" as unknown as number,
      dm_out: "" as unknown as number,
      n_in: "",
      n_larvae: "",
      n_frass: "",
      ash_in: "",
      ash_out: "",
      fat_in: "",
      fat_out: "",
    },
  });

  const result = computeSER.data;
  const values = form.watch();

  const draftSummary = useMemo(() => {
    const dmIn = Number(values.dm_in);
    const dmOut = Number(values.dm_out);
    if (!Number.isFinite(dmIn) || !Number.isFinite(dmOut) || dmIn <= 0) {
      return null;
    }

    return {
      dmReduction: ((dmIn - dmOut) / dmIn) * 100,
      nTracked:
        numberOrUndefined(values.n_in) != null &&
        numberOrUndefined(values.n_larvae) != null &&
        numberOrUndefined(values.n_frass) != null,
    };
  }, [values]);

  const tabs = [
    { id: "compute", label: "Compute", icon: <Calculator className="h-4 w-4" /> },
    { id: "history", label: "History", icon: <History className="h-4 w-4" />, count: history.data?.total },
  ];

  const onSubmit = (data: SERFormData) => {
    const payload: SERComputeRequest = {
      dm_in: data.dm_in,
      dm_out: data.dm_out,
      n_in: numberOrUndefined(data.n_in),
      n_larvae: numberOrUndefined(data.n_larvae),
      n_frass: numberOrUndefined(data.n_frass),
      ash_in: numberOrUndefined(data.ash_in),
      ash_out: numberOrUndefined(data.ash_out),
      fat_in: numberOrUndefined(data.fat_in),
      fat_out: numberOrUndefined(data.fat_out),
    };

    computeSER.mutate(payload);
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
              <CockpitSectionLabel>SER Analysis</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                Matched-boundary SER compute
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                High-trust compute surface for substrate efficiency ratio, recovery
                breakdown, and operator-visible recommendations.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="brand">Decision-grade compute</Badge>
              <Badge variant="info">Matched boundary</Badge>
              {result ? (
                <Badge variant={result.passed ? "success" : "warning"}>
                  {result.passed ? "Release pass" : "Review posture"}
                </Badge>
              ) : null}
            </div>
          </div>

          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
            <CockpitMetric
              label="Draft DM reduction"
              value={draftSummary ? `${draftSummary.dmReduction.toFixed(1)}%` : "Awaiting input"}
              hint="Current form payload"
              accent="cyan"
            />
            <CockpitMetric
              label="N-tracking"
              value={draftSummary?.nTracked ? "Complete" : "Partial"}
              hint="Matched nitrogen fields"
              accent="violet"
            />
            <CockpitMetric
              label="Latest result"
              value={result ? formatNumber(result.ser_value, 4) : "None"}
              hint={result ? `Computed ${formatDateTime(result.computed_at)}` : "Run a compute job"}
              accent="amber"
            />
            <CockpitMetric
              label="History records"
              value={history.data?.total != null ? String(history.data.total) : "Loading"}
              hint="Stored SER evaluations"
              accent="neutral"
            />
          </CockpitGrid>
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <CockpitSectionLabel>Compute controls</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              Move between live compute and stored history without leaving the matched-boundary
              SER surface.
            </p>
          </div>
          <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
        </div>
      </CockpitPanel>

      <TabPanel tabId="compute" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <CockpitPanel className="p-5 lg:p-6">
            <CardHeader
              title="Input contract"
              description="Enter dry matter plus optional nitrogen, ash, and fat metrics for a richer matched-boundary interpretation."
            />
            <CardBody>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="DM In (kg)"
                    type="number"
                    step="0.001"
                    required
                    error={form.formState.errors.dm_in?.message}
                    {...form.register("dm_in")}
                  />
                  <Input
                    label="DM Out (kg)"
                    type="number"
                    step="0.001"
                    required
                    error={form.formState.errors.dm_out?.message}
                    {...form.register("dm_out")}
                  />
                </div>

                <div className="grid gap-4 sm:grid-cols-3">
                  <Input label="N In (kg)" type="number" step="0.001" {...form.register("n_in")} />
                  <Input label="N Larvae (kg)" type="number" step="0.001" {...form.register("n_larvae")} />
                  <Input label="N Frass (kg)" type="number" step="0.001" {...form.register("n_frass")} />
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="Ash In (kg)" type="number" step="0.001" {...form.register("ash_in")} />
                  <Input label="Ash Out (kg)" type="number" step="0.001" {...form.register("ash_out")} />
                  <Input label="Fat In (kg)" type="number" step="0.001" {...form.register("fat_in")} />
                  <Input label="Fat Out (kg)" type="number" step="0.001" {...form.register("fat_out")} />
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
                    <p className="assistant-section-kicker !text-surface-500">Compute discipline</p>
                    <p className="mt-2 text-sm leading-6 text-surface-300">
                      This surface stays within current typed backend fields. It does not invent unsupported recovery metrics.
                    </p>
                  </div>
                  <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
                    <p className="assistant-section-kicker !text-surface-500">Result shape</p>
                    <p className="mt-2 text-sm leading-6 text-surface-300">
                      Output includes SER, EER, MCR, BCR, grade, pass state, and operator recommendations.
                    </p>
                  </div>
                </div>

                <Button type="submit" fullWidth loading={computeSER.isPending} leftIcon={<Calculator className="h-4 w-4" />}>
                  Compute SER
                </Button>
              </form>
            </CardBody>
          </CockpitPanel>

          <div className="space-y-6">
            <CockpitPanel tone="emphasis" className="p-5 lg:p-6">
              <CardHeader title="Computed result" description="Latest scored output from the current manual payload." />
              <CardBody>
                {result ? (
                  <div className="space-y-5">
                    <div className="assistant-thread-shell flex justify-center rounded-3xl border border-white/8 p-6">
                      <SERGauge value={result.ser_value} size={220} />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <ResultTile label="EER" value={formatNumber(result.eer, 4)} />
                      <ResultTile label="MCR" value={formatNumber(result.mcr, 4)} />
                      <ResultTile label="BCR" value={formatNumber(result.bcr, 4)} />
                      <div className="assistant-thread-shell rounded-[22px] border border-white/8 px-4 py-4">
                        <p className="assistant-section-kicker">Grade</p>
                        <div className="mt-3">
                          <GradeBadge grade={result.grade} />
                        </div>
                      </div>
                    </div>

                    <div className="assistant-aside-card rounded-2xl border border-white/8 px-4 py-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="assistant-section-kicker !text-surface-500">Release posture</p>
                          <div className="mt-2 flex items-center gap-2">
                            <Badge variant={result.passed ? "success" : "warning"} dot>
                              {result.passed ? "Pass" : "Review"}
                            </Badge>
                            <GradeBadge grade={result.grade} />
                          </div>
                        </div>
                        <ShieldCheck className="h-5 w-5 text-emerald-200" />
                      </div>
                      <p className="mt-3 text-xs text-surface-500">
                        Computed at {formatDateTime(result.computed_at)}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="assistant-aside-card flex flex-col items-center justify-center rounded-3xl border border-white/8 py-16 text-center">
                    <Sparkles className="mb-3 h-8 w-8 text-surface-500" />
                    <p className="text-sm text-surface-300">Run a compute job to populate the result console.</p>
                  </div>
                )}
              </CardBody>
            </CockpitPanel>

            <CockpitPanel className="p-5 lg:p-6">
              <CardHeader title="Operator recommendations" description="Backend-provided guidance carried through without embellishment." />
              <CardBody className="space-y-3">
                {result?.recommendations?.length ? (
                  result.recommendations.map((recommendation) => (
                    <div key={recommendation} className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3 text-sm text-surface-300">
                      {recommendation}
                    </div>
                  ))
                ) : (
                  <div className="assistant-aside-card rounded-2xl border border-white/8 px-4 py-3 text-sm text-surface-400">
                    No recommendations available until a compute result exists.
                  </div>
                )}
              </CardBody>
            </CockpitPanel>
          </div>
        </div>
      </TabPanel>

      <TabPanel tabId="history" activeTab={activeTab}>
        <CockpitPanel className="overflow-hidden p-0">
          <div className="border-b border-white/8 px-6 py-5">
            <CardHeader title="Stored SER history" description="Review recent compute outputs and compare grades, pass posture, and decomposition metrics." />
          </div>
          <div className="px-4 pb-4 pt-4">
            {history.isLoading ? (
              <TableSkeleton rows={6} cols={7} />
            ) : history.data?.items?.length ? (
              <>
                <Table>
                  <TableHead>
                    <tr>
                      <TableHeaderCell>Computed</TableHeaderCell>
                      <TableHeaderCell>Batch</TableHeaderCell>
                      <TableHeaderCell align="right">SER</TableHeaderCell>
                      <TableHeaderCell align="right">EER</TableHeaderCell>
                      <TableHeaderCell align="right">MCR</TableHeaderCell>
                      <TableHeaderCell align="right">BCR</TableHeaderCell>
                      <TableHeaderCell align="center">Posture</TableHeaderCell>
                    </tr>
                  </TableHead>
                  <TableBody>
                    {history.data.items.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>{formatDateTime(item.computed_at)}</TableCell>
                        <TableCell>{item.batch_id ?? "Manual compute"}</TableCell>
                        <TableCell align="right" mono>{formatNumber(item.ser_value, 4)}</TableCell>
                        <TableCell align="right" mono>{formatNumber(item.eer, 4)}</TableCell>
                        <TableCell align="right" mono>{formatNumber(item.mcr, 4)}</TableCell>
                        <TableCell align="right" mono>{formatNumber(item.bcr, 4)}</TableCell>
                        <TableCell align="center">
                          <div className="flex items-center justify-center gap-2">
                            <GradeBadge grade={item.grade} />
                            <Badge variant={item.passed ? "success" : "warning"}>
                              {item.passed ? "Pass" : "Review"}
                            </Badge>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                <div className="mt-4 px-2">
                  <Pagination
                    page={histPage}
                    totalPages={history.data.total_pages}
                    total={history.data.total}
                    pageSize={10}
                    onPageChange={setHistPage}
                  />
                </div>
              </>
            ) : (
              <div className="py-16 text-center text-sm text-surface-400">
                No SER history has been recorded yet.
              </div>
            )}
          </div>
        </CockpitPanel>
      </TabPanel>
    </div>
  );
}

function ResultTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="assistant-thread-shell rounded-[22px] border border-white/8 px-4 py-4">
      <p className="assistant-section-kicker">{label}</p>
      <p className="mt-3 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}
