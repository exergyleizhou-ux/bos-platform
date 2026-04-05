import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Calculator, History, ShieldCheck, Sparkles } from "lucide-react";

import { useComputeSER, useSERHistory } from "@/hooks/useSER";
import { GradeBadge, Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, StatCard } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { SERGauge } from "@/components/charts/SERGauge";
import { Input } from "@/components/ui/Input";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow, TableSkeleton } from "@/components/ui/Table";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
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
    <div className="space-y-6">
      <PageHeader
        eyebrow="SER Analysis"
        title="Matched-boundary SER compute"
        description="High-trust compute surface for substrate efficiency ratio, recovery breakdown, and operator-visible recommendations."
        badges={[
          { label: "Decision-grade compute", variant: "brand" },
          { label: "Matched boundary", variant: "info" },
        ]}
        stats={[
          {
            label: "Draft DM reduction",
            value: draftSummary ? `${draftSummary.dmReduction.toFixed(1)}%` : "Awaiting input",
            hint: "Instant preview from current dry matter inputs",
          },
          {
            label: "N-tracking",
            value: draftSummary?.nTracked ? "Complete" : "Partial",
            hint: "Nitrogen metrics appear only when inputs are supplied",
          },
          {
            label: "Latest result",
            value: result ? formatNumber(result.ser_value, 4) : "None",
            hint: result ? `Computed ${formatDateTime(result.computed_at)}` : "Run a compute job",
          },
          {
            label: "History records",
            value: history.data?.total ?? "Loading",
            hint: "Stored compute outputs",
          },
        ]}
      />

      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      <TabPanel tabId="compute" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <Card tone="strong">
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
                  <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                    <p className="metric-kicker">Compute discipline</p>
                    <p className="mt-2 text-sm leading-6 text-surface-300">
                      This surface stays within current typed backend fields. It does not invent unsupported recovery metrics.
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                    <p className="metric-kicker">Result shape</p>
                    <p className="mt-2 text-sm leading-6 text-surface-300">
                      Output includes SER, EER, MCR, BCR, grade, pass state, and operator recommendations.
                    </p>
                  </div>
                </div>

                <Button
                  type="submit"
                  fullWidth
                  loading={computeSER.isPending}
                  leftIcon={<Calculator className="h-4 w-4" />}
                >
                  Compute SER
                </Button>
              </form>
            </CardBody>
          </Card>

          <div className="space-y-6">
            <Card tone="strong">
              <CardHeader title="Computed result" description="Latest scored output from the current manual payload." />
              <CardBody>
                {result ? (
                  <div className="space-y-5">
                    <div className="flex justify-center rounded-3xl border border-white/8 bg-white/5 p-6">
                      <SERGauge value={result.ser_value} size={220} />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <StatCard label="EER" value={formatNumber(result.eer, 4)} color="blue" />
                      <StatCard label="MCR" value={formatNumber(result.mcr, 4)} color="amber" />
                      <StatCard label="BCR" value={formatNumber(result.bcr, 4)} color="neutral" />
                      <StatCard
                        label="Grade"
                        value={<GradeBadge grade={result.grade} />}
                        color={result.passed ? "green" : "amber"}
                      />
                    </div>

                    <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="metric-kicker">Release posture</p>
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
                  <div className="flex flex-col items-center justify-center rounded-3xl border border-white/8 bg-white/5 py-16 text-center">
                    <Sparkles className="mb-3 h-8 w-8 text-surface-500" />
                    <p className="text-sm text-surface-300">Run a compute job to populate the result console.</p>
                  </div>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Operator recommendations" description="Backend-provided guidance carried through without embellishment." />
              <CardBody className="space-y-3">
                {result?.recommendations?.length ? (
                  result.recommendations.map((recommendation) => (
                    <div
                      key={recommendation}
                      className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm text-surface-300"
                    >
                      {recommendation}
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm text-surface-400">
                    No recommendations available until a compute result exists.
                  </div>
                )}
              </CardBody>
            </Card>
          </div>
        </div>
      </TabPanel>

      <TabPanel tabId="history" activeTab={activeTab}>
        <Card noPadding tone="strong">
          <div className="border-b border-white/8 px-6 py-5">
            <CardHeader
              title="Stored SER history"
              description="Review recent compute outputs and compare grades, pass posture, and decomposition metrics."
            />
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
        </Card>
      </TabPanel>
    </div>
  );
}
