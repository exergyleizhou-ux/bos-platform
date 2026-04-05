import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { BarChart3, GitCompare, Shuffle } from "lucide-react";

import {
  useBayesianAB,
  useMonteCarloSimulation,
  useSensitivityAnalysis,
} from "@/hooks/useSimulation";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, StatCard } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { MonteCarloHistogram } from "@/components/charts/MonteCarloHistogram";
import { PageHeader } from "@/components/ui/PageHeader";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { formatNumber, formatPercent } from "@/lib/utils";

const mcSchema = z.object({
  dm_in_mean: z.coerce.number().positive(),
  dm_in_std: z.coerce.number().nonnegative(),
  dm_out_mean: z.coerce.number().positive(),
  dm_out_std: z.coerce.number().nonnegative(),
  n_simulations: z.coerce.number().int().min(100).max(100_000),
  seed: z.union([z.coerce.number().int(), z.literal("")]).optional(),
});
type MCFormData = z.infer<typeof mcSchema>;

const sensSchema = z.object({
  dm_in: z.coerce.number().positive(),
  dm_out: z.coerce.number().positive(),
  variation_pct: z.coerce.number().min(0.01).max(1),
  n_steps: z.coerce.number().int().min(5).max(50),
});
type SensFormData = z.infer<typeof sensSchema>;

const abSchema = z.object({
  group_a: z.string().min(1, "Enter comma-separated values"),
  group_b: z.string().min(1, "Enter comma-separated values"),
  n_samples: z.coerce.number().int().min(1000).max(50_000),
});
type ABFormData = z.infer<typeof abSchema>;

const TABS = [
  { id: "mc", label: "Monte Carlo", icon: <Shuffle className="h-4 w-4" /> },
  { id: "sens", label: "Sensitivity", icon: <BarChart3 className="h-4 w-4" /> },
  { id: "ab", label: "Bayesian A/B", icon: <GitCompare className="h-4 w-4" /> },
];

export default function SimulationPage() {
  const [activeTab, setActiveTab] = useState("mc");

  const mc = useMonteCarloSimulation();
  const sens = useSensitivityAnalysis();
  const ab = useBayesianAB();

  const mcForm = useForm<MCFormData>({
    resolver: zodResolver(mcSchema),
    defaultValues: {
      dm_in_mean: 10,
      dm_in_std: 0.5,
      dm_out_mean: 8,
      dm_out_std: 0.3,
      n_simulations: 5000,
      seed: "",
    },
  });

  const sensForm = useForm<SensFormData>({
    resolver: zodResolver(sensSchema),
    defaultValues: { dm_in: 10, dm_out: 8, variation_pct: 0.2, n_steps: 20 },
  });

  const abForm = useForm<ABFormData>({
    resolver: zodResolver(abSchema),
    defaultValues: { group_a: "", group_b: "", n_samples: 10000 },
  });

  const onMC = (data: MCFormData) => {
    mc.mutate({
      ...data,
      seed: data.seed === "" ? undefined : Number(data.seed),
    });
  };

  const onSens = (data: SensFormData) => {
    sens.mutate(data);
  };

  const onAB = (data: ABFormData) => {
    const parseCSV = (value: string) =>
      value
        .split(",")
        .map((entry) => Number.parseFloat(entry.trim()))
        .filter((entry) => !Number.isNaN(entry));

    ab.mutate({
      group_a: parseCSV(data.group_a),
      group_b: parseCSV(data.group_b),
      n_samples: data.n_samples,
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Simulation"
        title="Scenario and uncertainty studio"
        description="Stress-test BOS performance with Monte Carlo, sensitivity ranking, and Bayesian A/B inference."
        badges={[
          { label: `Mode: ${activeTab.toUpperCase()}`, variant: "info" },
          { label: "Operator analysis", variant: "brand" },
        ]}
        stats={[
          {
            label: "Monte Carlo sims",
            value: mcForm.watch("n_simulations"),
            hint: "Current draft count",
          },
          {
            label: "Sensitivity span",
            value: `${formatPercent(sensForm.watch("variation_pct"), 0)}`,
            hint: "Current variation window",
          },
          {
            label: "A/B posterior",
            value: abForm.watch("n_samples"),
            hint: "Posterior sample budget",
          },
          {
            label: "Latest result",
            value: mc.data ? formatNumber(mc.data.ser_mean, 4) : sens.data ? formatNumber(sens.data.base_ser, 4) : "Pending",
            hint: "Most recent analysis surface",
          },
        ]}
      />

      <Tabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

      <TabPanel tabId="mc" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[1fr_1.1fr]">
          <Card tone="strong">
            <CardHeader title="Monte Carlo contract" description="Sample uncertainty around dry matter inputs and quantify pass probability." />
            <CardBody>
              <form onSubmit={mcForm.handleSubmit(onMC)} className="grid gap-4 md:grid-cols-2" noValidate>
                <Input label="DM In mean" type="number" step="0.1" {...mcForm.register("dm_in_mean")} />
                <Input label="DM In std" type="number" step="0.01" {...mcForm.register("dm_in_std")} />
                <Input label="DM Out mean" type="number" step="0.1" {...mcForm.register("dm_out_mean")} />
                <Input label="DM Out std" type="number" step="0.01" {...mcForm.register("dm_out_std")} />
                <Input label="Simulations" type="number" {...mcForm.register("n_simulations")} />
                <Input label="Seed" type="number" placeholder="Optional" {...mcForm.register("seed")} />
                <div className="md:col-span-2">
                  <Button type="submit" fullWidth loading={mc.isPending} leftIcon={<Shuffle className="h-4 w-4" />}>
                    Run Monte Carlo
                  </Button>
                </div>
              </form>
            </CardBody>
          </Card>

          <Card tone="strong">
            <CardHeader title="Uncertainty envelope" description="Distribution of sampled SER outcomes and resulting pass probability." />
            <CardBody>
              {mc.data ? (
                <div className="space-y-5">
                  <MonteCarloHistogram data={mc.data} />
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                    <StatCard label="Mean SER" value={formatNumber(mc.data.ser_mean, 4)} color="green" />
                    <StatCard label="Std dev" value={formatNumber(mc.data.ser_std, 4)} color="neutral" />
                    <StatCard label="Pass prob" value={formatPercent(mc.data.pass_probability)} color="blue" />
                    <StatCard label="P5" value={formatNumber(mc.data.ser_p5, 4)} color="amber" />
                    <StatCard label="Median" value={formatNumber(mc.data.ser_median, 4)} color="neutral" />
                    <StatCard label="P95" value={formatNumber(mc.data.ser_p95, 4)} color="amber" />
                  </div>
                </div>
              ) : (
                <div className="py-20 text-center text-sm text-surface-400">
                  Configure the model and run a simulation to populate the histogram.
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      </TabPanel>

      <TabPanel tabId="sens" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <Card tone="strong">
            <CardHeader title="Sensitivity contract" description="Rank which parameters most strongly affect baseline SER." />
            <CardBody>
              <form onSubmit={sensForm.handleSubmit(onSens)} className="grid gap-4 md:grid-cols-2" noValidate>
                <Input label="DM In" type="number" step="0.1" {...sensForm.register("dm_in")} />
                <Input label="DM Out" type="number" step="0.1" {...sensForm.register("dm_out")} />
                <Input label="Variation span" type="number" step="0.01" {...sensForm.register("variation_pct")} />
                <Input label="Steps" type="number" {...sensForm.register("n_steps")} />
                <div className="md:col-span-2">
                  <Button type="submit" fullWidth loading={sens.isPending} leftIcon={<BarChart3 className="h-4 w-4" />}>
                    Run sensitivity analysis
                  </Button>
                </div>
              </form>
            </CardBody>
          </Card>

          <Card tone="strong">
            <CardHeader title="Parameter ranking" description="Relative leverage of each modeled parameter against baseline SER." />
            <CardBody>
              {sens.data ? (
                <div className="space-y-4">
                  <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                    <p className="metric-kicker">Base SER</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{formatNumber(sens.data.base_ser, 4)}</p>
                  </div>
                  {sens.data.parameter_ranking.map((parameter, index) => (
                    <div key={parameter} className="flex items-center gap-3 rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-xs font-semibold text-white">
                        {index + 1}
                      </span>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-white">{parameter}</p>
                        <p className="text-xs text-surface-500">
                          Impact score {formatNumber(sens.data.impact_scores[parameter], 4)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-20 text-center text-sm text-surface-400">
                  Run the sensitivity model to rank parameter leverage.
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      </TabPanel>

      <TabPanel tabId="ab" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <Card tone="strong">
            <CardHeader title="Bayesian A/B contract" description="Compare two SER cohorts with posterior probability rather than fixed-threshold rhetoric." />
            <CardBody>
              <form onSubmit={abForm.handleSubmit(onAB)} className="space-y-4" noValidate>
                <Input label="Group A values" placeholder="0.15, 0.16, 0.14, 0.17" {...abForm.register("group_a")} />
                <Input label="Group B values" placeholder="0.12, 0.11, 0.10, 0.13" {...abForm.register("group_b")} />
                <Input label="Posterior samples" type="number" {...abForm.register("n_samples")} />
                <Button type="submit" fullWidth loading={ab.isPending} leftIcon={<GitCompare className="h-4 w-4" />}>
                  Run Bayesian A/B
                </Button>
              </form>
            </CardBody>
          </Card>

          <Card tone="strong">
            <CardHeader title="Posterior decision" description="Inference result with probability, effect size, and interval." />
            <CardBody>
              {ab.data ? (
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <StatCard label="Group A mean" value={formatNumber(ab.data.mean_a, 4)} color="amber" />
                    <StatCard label="Group B mean" value={formatNumber(ab.data.mean_b, 4)} color="green" />
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-4">
                    <p className="metric-kicker">Decision</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{ab.data.decision}</p>
                    <p className="mt-3 text-sm leading-6 text-surface-300">
                      P(B better) = {formatPercent(ab.data.prob_b_better)}. Effect size {formatNumber(ab.data.effect_size, 4)} with CI [{formatNumber(ab.data.ci_effect_lower, 4)}, {formatNumber(ab.data.ci_effect_upper, 4)}].
                    </p>
                  </div>
                </div>
              ) : (
                <div className="py-20 text-center text-sm text-surface-400">
                  Run the Bayesian comparison to populate the decision surface.
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      </TabPanel>
    </div>
  );
}
