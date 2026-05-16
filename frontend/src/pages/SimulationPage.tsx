import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { BarChart3, Cpu, GitCompare, Shuffle } from "lucide-react";

import { MonteCarloHistogram } from "@/components/charts/MonteCarloHistogram";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardBody, CardHeader } from "@/components/ui/Card";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { Input } from "@/components/ui/Input";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import {
  useBayesianAB,
  useMonteCarloSimulation,
  useSensitivityAnalysis,
} from "@/hooks/useSimulation";
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
  const navigate = useNavigate();
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

  const latestResult = mc.data
    ? formatNumber(mc.data.ser_mean, 4)
    : sens.data
      ? formatNumber(sens.data.base_ser, 4)
      : ab.data
        ? ab.data.decision
        : "Pending";

  const posture = useMemo(() => {
    if (mc.data?.pass_probability != null) {
      return {
        label: mc.data.pass_probability >= 0.8 ? "Confidence high" : "Needs review",
        variant: mc.data.pass_probability >= 0.8 ? ("success" as const) : ("warning" as const),
      };
    }

    if (ab.data) {
      return { label: "Posterior ready", variant: "brand" as const };
    }

    if (sens.data) {
      return { label: "Sensitivity ranked", variant: "info" as const };
    }

    return { label: "Awaiting run", variant: "neutral" as const };
  }, [ab.data, mc.data, sens.data]);

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
              <CockpitSectionLabel>Simulation</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                Scenario and uncertainty studio
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                Stress-test BOS performance with Monte Carlo envelopes, sensitivity ranking,
                and Bayesian A/B inference in one operator-ready surface.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="secondary"
                leftIcon={<Cpu className="h-4 w-4" />}
                onClick={() => navigate("/bos/simulation-lab")}
              >
                Open 3D Lab Twin
              </Button>
              <Badge variant="info">{`Mode: ${activeTab.toUpperCase()}`}</Badge>
              <Badge variant={posture.variant}>{posture.label}</Badge>
              <Badge variant="brand">Operator analysis</Badge>
            </div>
          </div>

          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
            <CockpitMetric label="Active mode" value={activeTab.toUpperCase()} hint="Current simulation workflow" accent="cyan" />
            <CockpitMetric
              label="Configured volume"
              value={String(mcForm.watch("n_simulations"))}
              hint="Monte Carlo samples"
              accent="violet"
            />
            <CockpitMetric
              label="Sensitivity span"
              value={formatPercent(sensForm.watch("variation_pct"), 0)}
              hint={`${sensForm.watch("n_steps")} ranking steps`}
              accent="amber"
            />
            <CockpitMetric
              label="Latest result"
              value={latestResult}
              hint={`A/B samples ${abForm.watch("n_samples")}`}
              accent="neutral"
            />
          </CockpitGrid>
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-3xl">
            <CockpitSectionLabel>3D Lab Twin</CockpitSectionLabel>
            <h2 className="mt-3 text-xl font-semibold text-white">LabSim Twin Studio replay</h2>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              Launch the Three.js laboratory view for material-flow replay, reactor liquid state,
              sensor pulses, station labels, review locks, and release appendix evidence.
            </p>
          </div>
          <Button
            variant="secondary"
            leftIcon={<Cpu className="h-4 w-4" />}
            onClick={() => navigate("/bos/simulation-lab")}
          >
            Open LabSim Twin Studio
          </Button>
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <CockpitSectionLabel>Simulation controls</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              Choose a modeling mode, adjust the supported parameters, and keep the
              resulting uncertainty surface in view as you switch between workflows.
            </p>
          </div>
          <Tabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />
        </div>
      </CockpitPanel>

      <TabPanel tabId="mc" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[1fr_1.1fr]">
          <CockpitPanel className="p-5 lg:p-6">
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
          </CockpitPanel>

          <CockpitPanel tone="emphasis" className="p-5 lg:p-6">
            <CardHeader title="Uncertainty envelope" description="Distribution of sampled SER outcomes and resulting pass probability." />
            <CardBody>
              {mc.data ? (
                <div className="space-y-5">
                  <MonteCarloHistogram data={mc.data} />
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                    <MetricTile label="Mean SER" value={formatNumber(mc.data.ser_mean, 4)} />
                    <MetricTile label="Std dev" value={formatNumber(mc.data.ser_std, 4)} />
                    <MetricTile label="Pass prob" value={formatPercent(mc.data.pass_probability)} />
                    <MetricTile label="P5" value={formatNumber(mc.data.ser_p5, 4)} />
                    <MetricTile label="Median" value={formatNumber(mc.data.ser_median, 4)} />
                    <MetricTile label="P95" value={formatNumber(mc.data.ser_p95, 4)} />
                  </div>
                </div>
              ) : (
                <EmptyConsole copy="Configure the model and run a simulation to populate the histogram." />
              )}
            </CardBody>
          </CockpitPanel>
        </div>
      </TabPanel>

      <TabPanel tabId="sens" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <CockpitPanel className="p-5 lg:p-6">
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
          </CockpitPanel>

          <CockpitPanel tone="emphasis" className="p-5 lg:p-6">
            <CardHeader title="Parameter ranking" description="Relative leverage of each modeled parameter against baseline SER." />
            <CardBody>
              {sens.data ? (
                <div className="space-y-4">
                  <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
                    <p className="assistant-section-kicker !text-surface-500">Base SER</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{formatNumber(sens.data.base_ser, 4)}</p>
                  </div>
                  {sens.data.parameter_ranking.map((parameter, index) => (
                    <div key={parameter} className="assistant-thread-shell flex items-center gap-3 rounded-2xl border border-white/8 px-4 py-3">
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
                <EmptyConsole copy="Run the sensitivity model to rank parameter leverage." />
              )}
            </CardBody>
          </CockpitPanel>
        </div>
      </TabPanel>

      <TabPanel tabId="ab" activeTab={activeTab}>
        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <CockpitPanel className="p-5 lg:p-6">
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
          </CockpitPanel>

          <CockpitPanel tone="emphasis" className="p-5 lg:p-6">
            <CardHeader title="Posterior decision" description="Inference result with probability, effect size, and interval." />
            <CardBody>
              {ab.data ? (
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <MetricTile label="Group A mean" value={formatNumber(ab.data.mean_a, 4)} />
                    <MetricTile label="Group B mean" value={formatNumber(ab.data.mean_b, 4)} />
                  </div>
                  <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-4">
                    <p className="assistant-section-kicker !text-surface-500">Decision</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{ab.data.decision}</p>
                    <p className="mt-3 text-sm leading-6 text-surface-300">
                      P(B better) = {formatPercent(ab.data.prob_b_better)}. Effect size {formatNumber(ab.data.effect_size, 4)} with CI [{formatNumber(ab.data.ci_effect_lower, 4)}, {formatNumber(ab.data.ci_effect_upper, 4)}].
                    </p>
                  </div>
                </div>
              ) : (
                <EmptyConsole copy="Run the Bayesian comparison to populate the decision surface." />
              )}
            </CardBody>
          </CockpitPanel>
        </div>
      </TabPanel>
    </div>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="assistant-thread-shell rounded-[22px] border border-white/8 px-4 py-4">
      <p className="assistant-section-kicker">{label}</p>
      <p className="mt-3 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function EmptyConsole({ copy }: { copy: string }) {
  return <div className="py-20 text-center text-sm text-surface-400">{copy}</div>;
}
