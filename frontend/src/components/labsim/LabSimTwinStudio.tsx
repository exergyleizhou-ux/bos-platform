import { type ChangeEvent, type FormEvent, type ReactNode, useMemo, useState } from "react";
import { Bot, Download, Lock, Minus, Play, Plus, Route, Send, ShieldCheck, Target } from "lucide-react";

import { LabSimGaussianSplatStage } from "@/components/labsim/LabSimGaussianSplatStage";
import { LabSimThreeTwinScene, type LabAssistantCue } from "@/components/labsim/LabSimThreeTwinScene";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { formatNumber, formatPercent } from "@/lib/utils";
import type {
  SimulationLabCycle,
  SimulationLabRunResponse,
  SimulationPolicy,
  SimulationScenario,
  SimulationScenarioCreate,
  SimulationScenarioImportResponse,
} from "@/types/simulationLab";

export type HeavyMetalKey = "Cd" | "Pb" | "Hg" | "As" | "Cr";
export type TwinZoneTone = "amber" | "cyan" | "emerald" | "neutral" | "red" | "sky" | "violet";
export type TwinZoneId =
  | "intake"
  | "pretreatment"
  | "sensors"
  | "bay"
  | "reactor"
  | "review"
  | "assay"
  | "actuator"
  | "appendix";

export interface TwinZone {
  id: TwinZoneId;
  label: string;
  value: string;
  detail: string;
  tone: TwinZoneTone;
  x: number;
  y: number;
  w: number;
  h: number;
  metrics: Array<[string, string]>;
}

interface TwinStationOperation {
  status: string;
  variant: "danger" | "info" | "neutral" | "success" | "warning";
  phase: string;
  evidence: string;
  nextStep: string;
  boundary: string;
}

interface TwinWorkflowStep {
  label: string;
  detail: string;
  variant: "danger" | "info" | "neutral" | "success" | "warning";
}

interface VisualProfile {
  detail: string;
  label: string;
  tone: "amber" | "brown" | "cream" | "dark" | "emerald" | "yellow";
  type: "bsf" | "feedstock" | "grub" | "mealworm";
}

interface ExperimentTimelineStep {
  detail: string;
  label: string;
  zoneId: TwinZoneId;
}

type LabStageMode = "digitalTwin" | "gaussianSplat";

export interface LabSimPreset {
  id: string;
  label: string;
  shortLabel: string;
  species: string;
  feedstock: string;
  scenario: SimulationScenario;
  policy: SimulationPolicy;
  initial_state: SimulationScenarioCreate["initial_state"];
  reviewStatus: string;
  productLock: string;
  containment: string;
  evidenceMode: string;
  heavyMetals: Record<HeavyMetalKey, number>;
  notes: string[];
}

interface SelectOption<TValue extends string = string> {
  value: TValue;
  label: string;
}

interface LabSimTwinStudioProps {
  form: SimulationScenarioCreate;
  preset: LabSimPreset;
  presets: LabSimPreset[];
  scenarioOptions: Array<SelectOption<SimulationScenario>>;
  policyOptions: Array<SelectOption<SimulationPolicy>>;
  run: SimulationLabRunResponse | null;
  cycle: SimulationLabCycle | null;
  selectedCycleIndex: number;
  referenceId: string;
  importResult: SimulationScenarioImportResponse | null;
  canExportAppendix: boolean;
  isRunning: boolean;
  isImportingReference: boolean;
  isExportingAppendix: boolean;
  onSelectCycle: (index: number) => void;
  onApplyPreset: (preset: LabSimPreset) => void;
  onScenarioChange: (scenario: SimulationScenario) => void;
  onPolicyChange: (policy: SimulationPolicy) => void;
  onCyclesChange: (cycles: number) => void;
  onSeedChange: (seed: number) => void;
  onReferenceIdChange: (referenceId: string) => void;
  onImportReference: () => void;
  onRunExperiment: () => void;
  onExportAppendix: () => void;
}

export function LabSimTwinStudio({
  form,
  preset,
  presets,
  scenarioOptions,
  policyOptions,
  run,
  cycle,
  selectedCycleIndex,
  referenceId,
  importResult,
  canExportAppendix,
  isRunning,
  isImportingReference,
  isExportingAppendix,
  onSelectCycle,
  onApplyPreset,
  onScenarioChange,
  onPolicyChange,
  onCyclesChange,
  onSeedChange,
  onReferenceIdChange,
  onImportReference,
  onRunExperiment,
  onExportAppendix,
}: LabSimTwinStudioProps) {
  const riskScore = cycle?.risk_prediction.future_risk_score ?? run?.summary.ending_risk ?? null;
  const moisture = Number(cycle?.state_after.moisture ?? form.initial_state.moisture);
  const substrate = Number(cycle?.state_after.substrate ?? form.initial_state.substrate);
  const biomass = Number(cycle?.state_after.biomass ?? form.initial_state.biomass);
  const action = cycle?.agent_action.recommended_action ?? "ready_to_run";
  const assay = cycle?.risk_prediction.lab_assay_comparison ?? null;
  const riskVariant = riskScore == null ? "neutral" : riskScore >= 0.68 ? "danger" : riskScore >= 0.45 ? "warning" : "success";
  const moistureLevel = Math.min(100, Math.max(0, moisture));
  const biomassLevel = Math.min(100, Math.max(8, biomass * 38));
  const substrateLevel = Math.min(100, Math.max(8, substrate * 8));
  const cycleCount = run?.cycles.length ?? 0;
  const [selectedZoneId, setSelectedZoneId] = useState<TwinZoneId>("reactor");
  const [assistantPrompt, setAssistantPrompt] = useState("");
  const [assistantCue, setAssistantCue] = useState<LabAssistantCue | null>(null);
  const [labStageMode, setLabStageMode] = useState<LabStageMode>("gaussianSplat");
  const previousCycle = () => onSelectCycle(Math.max(0, selectedCycleIndex - 1));
  const nextCycle = () => onSelectCycle(Math.min(Math.max(0, cycleCount - 1), selectedCycleIndex + 1));
  const sensorHeat = Math.min(1, Math.max(0.18, (riskScore ?? 0.24) + (moistureLevel > 75 ? 0.12 : 0)));
  const importedAssaySource = importResult?.scenario.evidence_sources.find(
    (source) => source.field === "lab_assay_measurements",
  );
  const twinZones = useMemo<TwinZone[]>(() => [
    {
      id: "intake",
      label: "Sample intake",
      value: form.feedstock,
      detail: "Incoming material identity and chain-of-custody state for this virtual batch.",
      tone: "cyan",
      x: 4,
      y: 8,
      w: 22,
      h: 18,
      metrics: [
        ["Species", form.species],
        ["Feedstock", form.feedstock],
      ],
    },
    {
      id: "pretreatment",
      label: "Pretreatment mixer",
      value: `${formatNumber(moisture, 1)}% moisture`,
      detail: "Moisture and substrate conditioning before the insect lane receives the batch.",
      tone: "violet",
      x: 29,
      y: 8,
      w: 22,
      h: 18,
      metrics: [
        ["Moisture", `${formatNumber(moisture, 1)}%`],
        ["Substrate", formatNumber(substrate, 3)],
      ],
    },
    {
      id: "sensors",
      label: "Sensor mast",
      value: cycle ? `cycle ${cycle.cycle}` : "standby",
      detail: "Synthetic telemetry panel for temperature, moisture, ammonia, and visual observation feeds.",
      tone: "sky",
      x: 54,
      y: 8,
      w: 18,
      h: 18,
      metrics: [
        ["Cycle", cycle ? String(cycle.cycle) : "not run"],
        ["Risk", riskScore == null ? "pending" : formatPercent(riskScore, 1)],
      ],
    },
    {
      id: "bay",
      label: "Insect processing bay",
      value: preset.label,
      detail: "The selected species/feedstock lane where the virtual biological conversion occurs.",
      tone: "emerald",
      x: 5,
      y: 40,
      w: 28,
      h: 28,
      metrics: [
        ["Biomass", formatNumber(biomass, 3)],
        ["Lane", preset.shortLabel],
      ],
    },
    {
      id: "reactor",
      label: "Twin reactor state",
      value: action.replace(/_/g, " "),
      detail: "Current modeled state after supervisor decision and virtual actuator effects.",
      tone: "amber",
      x: 36,
      y: 37,
      w: 28,
      h: 32,
      metrics: [
        ["Biomass", `${formatPercent(biomassLevel / 100, 0)} scaled`],
        ["Substrate", `${formatPercent(substrateLevel / 100, 0)} scaled`],
        ["Moisture", `${formatPercent(moistureLevel / 100, 0)} scaled`],
      ],
    },
    {
      id: "review",
      label: "Restricted review lock",
      value: preset.productLock,
      detail: "Human-review boundary for release, runtime activation, and validated-default write protection.",
      tone: preset.id.includes("sludge") || riskVariant === "danger" ? "red" : "neutral",
      x: 67,
      y: 35,
      w: 28,
      h: 34,
      metrics: [
        ["Review", preset.reviewStatus],
        ["Runtime", "blocked"],
        ["Defaults", "locked"],
      ],
    },
    {
      id: "assay",
      label: "Assay bench",
      value: assay?.source_kind ?? preset.evidenceMode,
      detail: "Measured or reference-imported assay anchors used to compare prediction against review-gated evidence.",
      tone: "cyan",
      x: 5,
      y: 76,
      w: 22,
      h: 16,
      metrics: [
        ["Mode", assay?.measurement_mode ?? "profile anchor"],
        ["Source", assay?.source_ref ?? "profile"],
      ],
    },
    {
      id: "actuator",
      label: "Actuator sandbox",
      value: cycle?.actuator_result.status ?? "not executed",
      detail: "Virtual-only actuator result. Hardware execution remains disabled in LabSim.",
      tone: "violet",
      x: 31,
      y: 76,
      w: 20,
      h: 16,
      metrics: [
        ["Action", action.replace(/_/g, " ")],
        ["Hardware", "disabled"],
      ],
    },
    {
      id: "appendix",
      label: "Evidence vault",
      value: "release review only",
      detail: "Audit JSON and release appendix evidence for human review; no release state mutation is performed.",
      tone: "neutral",
      x: 55,
      y: 76,
      w: 39,
      h: 16,
      metrics: [
        ["Appendix", "downloadable"],
        ["Release effect", "none"],
      ],
    },
  ], [
    action,
    assay,
    biomass,
    biomassLevel,
    cycle,
    form.feedstock,
    form.species,
    moisture,
    moistureLevel,
    preset,
    riskScore,
    riskVariant,
    substrate,
    substrateLevel,
  ]);
  const selectedZone = twinZones.find((zone) => zone.id === selectedZoneId) ?? twinZones[4];
  const stationOperations = twinZones.reduce(
    (operations, zone) => ({
      ...operations,
      [zone.id]: getStationOperation({
        zoneId: zone.id,
        preset,
        run,
        cycle,
        importResult,
        riskVariant,
      }),
    }),
    {} as Record<TwinZoneId, TwinStationOperation>,
  );
  const selectedOperation = stationOperations[selectedZone.id];
  const selectedWorkflow = getStationWorkflow({
    zoneId: selectedZone.id,
    preset,
    run,
    importResult,
  });
  const organismProfile = getOrganismProfile(preset);
  const feedstockProfile = getFeedstockProfile(preset);
  const experimentGoal = getExperimentGoal(preset, form);
  const routeOutcome = getRouteOutcome(preset, run);
  const submitAssistantCommand = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const command = resolveLabAssistantCommand(assistantPrompt, selectedZone.id);
    setSelectedZoneId(command.zoneId);
    setAssistantCue({
      boundary: command.boundary,
      commandLabel: command.commandLabel,
      nonce: Date.now(),
      response: command.response,
      zoneId: command.zoneId,
    });
    if (command.shouldRun && !isRunning) {
      onRunExperiment();
    }
  };
  const quickAssistantCommand = (prompt: string) => {
    setAssistantPrompt(prompt);
    const command = resolveLabAssistantCommand(prompt, selectedZone.id);
    setSelectedZoneId(command.zoneId);
    setAssistantCue({
      boundary: command.boundary,
      commandLabel: command.commandLabel,
      nonce: Date.now(),
      response: command.response,
      zoneId: command.zoneId,
    });
    if (command.shouldRun && !isRunning) {
      onRunExperiment();
    }
  };

  return (
    <div className="space-y-5">
      <ExperimentOverviewBanner
        preset={preset}
        organism={organismProfile}
        feedstock={feedstockProfile}
        experimentGoal={experimentGoal}
        routeOutcome={routeOutcome}
      />

      <div className="min-w-0 space-y-4">
        <div
          data-testid="labsim-stage-mode-toggle"
          className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-slate-950/70 p-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-cyan-100/70">Lab view mode</p>
            <p className="mt-1 text-sm text-surface-300">
              Gaussian Splat shows the local realistic proof asset; Digital Twin keeps the existing Three.js scene fallback.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:w-[24rem]" role="group" aria-label="Lab view mode">
            {([
              { id: "gaussianSplat", label: "Realistic Lab / Gaussian Splat", icon: <Target className="h-4 w-4" /> },
              { id: "digitalTwin", label: "Digital Twin", icon: <Route className="h-4 w-4" /> },
            ] as Array<{ id: LabStageMode; label: string; icon: ReactNode }>).map((option) => (
              <button
                key={option.id}
                type="button"
                className={[
                  "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition",
                  labStageMode === option.id
                    ? "border-cyan-100 bg-cyan-100 text-slate-950"
                    : "border-white/10 bg-white/[0.04] text-surface-200 hover:border-cyan-200/60 hover:text-cyan-100",
                ].join(" ")}
                aria-pressed={labStageMode === option.id}
                onClick={() => setLabStageMode(option.id)}
              >
                {option.icon}
                <span className="leading-tight">{option.label}</span>
              </button>
            ))}
          </div>
        </div>

        {labStageMode === "gaussianSplat" ? (
          <LabSimGaussianSplatStage
            form={form}
            preset={preset}
            zones={twinZones}
            run={run}
            cycle={cycle}
            selectedZoneId={selectedZone.id}
            riskVariant={riskVariant}
            moistureLevel={moistureLevel}
            sensorHeat={sensorHeat}
            cycleCount={cycleCount}
            selectedCycleIndex={selectedCycleIndex}
            assistantCue={assistantCue}
            onSelectZone={setSelectedZoneId}
          />
        ) : (
          <LabSimThreeTwinScene
            form={form}
            preset={preset}
            zones={twinZones}
            run={run}
            cycle={cycle}
            selectedZoneId={selectedZone.id}
            riskVariant={riskVariant}
            moistureLevel={moistureLevel}
            biomassLevel={biomassLevel}
            sensorHeat={sensorHeat}
            cycleCount={cycleCount}
            selectedCycleIndex={selectedCycleIndex}
            assistantCue={assistantCue}
            onSelectZone={setSelectedZoneId}
          />
        )}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <form
            data-testid="labsim-assistant-command"
            className="rounded-2xl border border-cyan-200/20 bg-slate-950/80 p-4 shadow-2xl shadow-cyan-950/20"
            onSubmit={submitAssistantCommand}
          >
            <div className="flex items-start gap-3">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-cyan-200/30 bg-cyan-200/10 text-cyan-100">
                <Bot className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-xs uppercase tracking-[0.18em] text-cyan-100/70">Lab assistant command</p>
                <h3 className="mt-1 text-base font-semibold text-white">Say one sentence and the bench demonstrates the operation.</h3>
                <p className="mt-1 text-xs leading-5 text-surface-400">
                  The assistant can focus stations, replay the material path, and call the existing review-only run. Hardware execution remains blocked.
                </p>
              </div>
            </div>
            <div className="mt-4 grid gap-2 lg:grid-cols-[minmax(0,1fr)_9rem]">
              <Input
                id="labsim-assistant-prompt"
                aria-label="Lab assistant command"
                placeholder="Ask Lab Assistant to demonstrate reactor, assay, or run the review-only experiment..."
                value={assistantPrompt}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setAssistantPrompt(event.target.value)}
                className="text-sm"
              />
              <Button type="submit" leftIcon={<Send className="h-4 w-4" />}>
                Demonstrate
              </Button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {[
                "Demonstrate intake to reactor route",
                "Focus larvae tray rack",
                "Run virtual experiment and show assay bench",
              ].map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-surface-200 transition hover:border-cyan-200/50 hover:text-cyan-100"
                  onClick={() => quickAssistantCommand(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
            {assistantCue ? (
              <div className="mt-4 rounded-xl border border-cyan-200/20 bg-cyan-200/10 p-3 text-sm leading-6 text-surface-200">
                <p className="font-semibold text-white">{assistantCue.commandLabel}</p>
                <p className="mt-1">{assistantCue.response}</p>
                <p className="mt-1 text-xs text-surface-400">{assistantCue.boundary}</p>
              </div>
            ) : null}
          </form>

          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-cyan-100/70">Studio control</p>
                <p className="mt-2 text-sm font-semibold text-white">Run this review-only replay after the route is clear.</p>
              </div>
              <Button
                id="twin-studio-run-experiment"
                type="button"
                loading={isRunning}
                leftIcon={<Play className="h-4 w-4" />}
                onClick={onRunExperiment}
              >
                Run experiment
              </Button>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <p className="text-xs uppercase tracking-[0.18em] text-surface-500 md:col-span-2">Experiment lane</p>
              <Select
                id="twin-studio-route"
                label="Route"
                className="pr-8 text-[0.95rem]"
                options={presets.map((item) => ({
                  value: item.id,
                  label: formatRouteOptionLabel(item),
                }))}
                value={preset.id}
                onChange={(event) => {
                  const nextPreset = presets.find((item) => item.id === event.target.value);
                  if (nextPreset) onApplyPreset(nextPreset);
                }}
              />
              <Select
                id="twin-studio-scenario"
                label="Scenario"
                className="pr-8 text-[0.95rem]"
                options={scenarioOptions.map((item) => ({
                  value: item.value,
                  label: formatScenarioOptionLabel(item.value),
                }))}
                value={form.scenario}
                onChange={(event) => onScenarioChange(event.target.value as SimulationScenario)}
              />
              <Select
                id="twin-studio-policy"
                label="Policy"
                className="pr-8 text-[0.95rem]"
                options={policyOptions.map((item) => ({
                  value: item.value,
                  label: formatPolicyOptionLabel(item.value),
                }))}
                value={form.policy}
                onChange={(event) => onPolicyChange(event.target.value as SimulationPolicy)}
              />
              <Input
                id="twin-studio-seed"
                label="Replay seed"
                type="number"
                value={form.seed}
                onChange={(event: ChangeEvent<HTMLInputElement>) => onSeedChange(Number(event.target.value))}
              />
              <div className="md:col-span-2">
                <label htmlFor="twin-studio-cycles" className="mb-1.5 block text-sm font-medium text-surface-300">
                  Cycles
                </label>
                <div className="grid grid-cols-[2.75rem_1fr_2.75rem] gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    aria-label="Decrease cycles"
                    disabled={form.cycles <= 5}
                    onClick={() => onCyclesChange(Math.max(5, form.cycles - 1))}
                  >
                    <Minus className="h-4 w-4" />
                  </Button>
                  <Input
                    id="twin-studio-cycles"
                    type="number"
                    min={5}
                    max={24}
                    value={form.cycles}
                    onChange={(event: ChangeEvent<HTMLInputElement>) => onCyclesChange(Number(event.target.value))}
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    aria-label="Increase cycles"
                    disabled={form.cycles >= 24}
                    onClick={() => onCyclesChange(Math.min(24, form.cycles + 1))}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <ExperimentTimeline
            activeZoneId={selectedZone.id}
            steps={getExperimentTimeline(preset)}
            onSelectZone={setSelectedZoneId}
          />
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-surface-500">Twin boundary</p>
            <div className="mt-3 space-y-2 text-sm text-surface-300">
              <TraceRow label="Runtime activation" value="blocked" />
              <TraceRow label="Hardware execution" value="blocked" />
              <TraceRow label="Validated defaults" value="locked" />
              <TraceRow label="Release effect" value="review evidence only" />
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <TwinZoneDetail
          zone={selectedZone}
          operation={selectedOperation}
          workflow={selectedWorkflow}
          riskVariant={riskVariant}
          riskScore={riskScore}
        />
        <TwinPlaybackControls
          cycle={cycle}
          cycleCount={cycleCount}
          selectedCycleIndex={selectedCycleIndex}
          previousCycle={previousCycle}
          nextCycle={nextCycle}
          onSelectCycle={onSelectCycle}
        />
      </div>

      <details className="rounded-2xl border border-white/10 bg-white/[0.04] p-4" open>
        <summary className="cursor-pointer text-xs uppercase tracking-[0.18em] text-surface-500">
          Reference import and release tools
        </summary>
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="grid gap-3">
            <Input
              id="twin-studio-reference-id"
              label="Reference ID"
              value={referenceId}
              onChange={(event: ChangeEvent<HTMLInputElement>) => onReferenceIdChange(event.target.value)}
              className="font-mono text-xs"
            />
            <div className="grid gap-2 sm:grid-cols-2">
              <Button
                id="twin-studio-import-reference"
                type="button"
                variant="secondary"
                loading={isImportingReference}
                leftIcon={<Download className="h-4 w-4" />}
                onClick={onImportReference}
              >
                Import reference
              </Button>
              <Button
                id="twin-studio-export-appendix"
                type="button"
                variant="secondary"
                disabled={!canExportAppendix}
                loading={isExportingAppendix}
                leftIcon={<Download className="h-4 w-4" />}
                onClick={onExportAppendix}
              >
                Export release appendix
              </Button>
            </div>
            {importResult ? (
              <ImportEvidenceSummary importResult={importResult} importedAssaySource={importedAssaySource} />
            ) : null}
          </div>
          <TwinProofRail
            run={run}
            importResult={importResult}
            canExportAppendix={canExportAppendix}
          />
        </div>
      </details>

      <TwinFactoryScene
        zones={twinZones}
        operations={stationOperations}
        cycle={cycle}
        selectedZoneId={selectedZone.id}
        riskVariant={riskVariant}
        biomassLevel={biomassLevel}
        sensorHeat={sensorHeat}
        cycleCount={cycleCount}
        selectedCycleIndex={selectedCycleIndex}
        onSelectZone={setSelectedZoneId}
      />
    </div>
  );
}

interface LabAssistantCommand {
  boundary: string;
  commandLabel: string;
  response: string;
  shouldRun: boolean;
  zoneId: TwinZoneId;
}

function resolveLabAssistantCommand(prompt: string, fallbackZoneId: TwinZoneId): LabAssistantCommand {
  const normalized = prompt.trim().toLowerCase();
  if (!normalized) {
    return {
      boundary: "This is a local visual demonstration; runtime activation, hardware execution, validated-default writes, and release mutation remain blocked.",
      commandLabel: "Bench route demonstration",
      response: "The assistant keeps the current station selected and animates the material path so the operator can inspect the virtual bench.",
      shouldRun: false,
      zoneId: fallbackZoneId,
    };
  }
  const zoneRules: Array<{ keywords: string[]; response: string; title: string; zoneId: TwinZoneId }> = [
    {
      keywords: ["intake", "feedstock", "sample", "进料", "接收", "样品", "物料"],
      response: "The bench opens the sample intake lane, highlights incoming feedstock, and sends the first material packets into the governed path.",
      title: "Sample intake demonstration",
      zoneId: "intake",
    },
    {
      keywords: ["prep", "pretreatment", "mix", "moisture", "预处理", "混合", "水分"],
      response: "The mixer becomes the active station, showing moisture conditioning before the material enters the biological lane.",
      title: "Pretreatment mixer demonstration",
      zoneId: "pretreatment",
    },
    {
      keywords: ["larva", "larvae", "tray", "insect", "幼虫", "托盘", "养殖", "虫"],
      response: "The tray rack is selected so the stage can show layered larvae trays and the controlled conversion bay.",
      title: "Larvae tray rack demonstration",
      zoneId: "bay",
    },
    {
      keywords: ["reactor", "tank", "ferment", "digestion", "反应器", "反应", "发酵", "罐"],
      response: "The transparent reactor is brought forward, with animated fill and material motion showing the virtual digestion state.",
      title: "Transparent reactor demonstration",
      zoneId: "reactor",
    },
    {
      keywords: ["sensor", "temperature", "ammonia", "telemetry", "传感", "温度", "氨", "遥测"],
      response: "The sensor mast is focused for temperature, moisture, ammonia, and risk observation replay.",
      title: "Sensor mast demonstration",
      zoneId: "sensors",
    },
    {
      keywords: ["assay", "microscope", "vial", "test", "检测", "显微", "试管", "化验"],
      response: "The assay bench is selected to compare model prediction with measured or profile evidence.",
      title: "Assay bench demonstration",
      zoneId: "assay",
    },
    {
      keywords: ["actuator", "valve", "dose", "执行", "阀", "调节", "投加"],
      response: "The virtual actuator and valve station is highlighted; the action remains a simulated effect only.",
      title: "Virtual actuator demonstration",
      zoneId: "actuator",
    },
    {
      keywords: ["review", "lock", "cabinet", "gate", "复核", "锁", "样品柜", "受限"],
      response: "The restricted review cabinet is selected to show why the route remains locked behind review evidence.",
      title: "Review lock demonstration",
      zoneId: "review",
    },
    {
      keywords: ["appendix", "evidence", "report", "export", "附录", "证据", "报告", "文件"],
      response: "The evidence cabinet is selected; appendix output remains a review packet, not release approval.",
      title: "Evidence cabinet demonstration",
      zoneId: "appendix",
    },
  ];
  const matchedRule = zoneRules.find((rule) => rule.keywords.some((keyword) => normalized.includes(keyword)));
  const shouldRun = /run|start|simulate|experiment|运行|开始|执行|实验|演示/.test(normalized);
  const zoneId = matchedRule?.zoneId ?? fallbackZoneId;
  const commandLabel = shouldRun ? `${matchedRule?.title ?? "Bench route demonstration"} + review-only run` : matchedRule?.title ?? "Bench route demonstration";
  const response =
    matchedRule?.response ??
    "The assistant keeps the current station selected and animates the material path so the operator can inspect the virtual bench.";
  return {
    boundary: shouldRun
      ? "Review-only run call is allowed here; runtime activation, hardware execution, validated-default writes, and release mutation remain blocked."
      : "This is a local visual demonstration; runtime activation, hardware execution, validated-default writes, and release mutation remain blocked.",
    commandLabel,
    response,
    shouldRun,
    zoneId,
  };
}

function ExperimentOverviewBanner({
  preset,
  organism,
  feedstock,
  experimentGoal,
  routeOutcome,
}: {
  preset: LabSimPreset;
  organism: VisualProfile;
  feedstock: VisualProfile;
  experimentGoal: string;
  routeOutcome: string;
}) {
  return (
    <section
      data-testid="labsim-experiment-overview"
      className="grid gap-4 rounded-2xl border border-cyan-300/20 bg-slate-950/55 p-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(18rem,0.95fr)]"
      aria-label="Experiment overview"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={preset.id.includes("sludge") ? "danger" : "info"}>{preset.shortLabel}</Badge>
          <Badge variant="warning">Review evidence only</Badge>
          <Badge variant="neutral">No runtime or hardware</Badge>
        </div>
        <h3 className="mt-3 text-xl font-semibold text-white">Experiment replay: {preset.label}</h3>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-surface-300">
          BOS is replaying how a selected organism converts a selected waste stream, then checking moisture drift,
          assay calibration, and review locks before any release-facing interpretation.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <OverviewFact icon={<Target className="h-4 w-4" />} label="Experiment goal" value={experimentGoal} />
          <OverviewFact icon={<Route className="h-4 w-4" />} label="Route outcome" value={routeOutcome} />
          <OverviewFact icon={<ShieldCheck className="h-4 w-4" />} label="Safety mode" value="Review evidence only; runtime, hardware, and validated-default writes remain blocked." />
          <OverviewFact icon={<Lock className="h-4 w-4" />} label="Product lock" value={preset.productLock} />
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
        <VisualIdentityCard
          testId="labsim-organism-visual"
          title="Organism"
          profile={organism}
        />
        <VisualIdentityCard
          testId="labsim-feedstock-visual"
          title="Feedstock"
          profile={feedstock}
        />
      </div>
    </section>
  );
}

function OverviewFact({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-white/10 bg-white/[0.045] p-3">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-cyan-100/70">
        {icon}
        <span>{label}</span>
      </div>
      <p className="mt-2 text-sm leading-5 text-white">{value}</p>
    </div>
  );
}

function VisualIdentityCard({
  profile,
  testId,
  title,
}: {
  profile: VisualProfile;
  testId: string;
  title: string;
}) {
  return (
    <div data-testid={testId} className="rounded-xl border border-white/10 bg-white/[0.045] p-3">
      <p className="text-xs uppercase tracking-[0.16em] text-surface-500">{title}</p>
      <div className="mt-3 flex min-h-[7.5rem] items-center justify-center overflow-hidden rounded-lg border border-white/10 bg-slate-950/70 p-3">
        {profile.type === "feedstock" ? <FeedstockSpecimen tone={profile.tone} /> : <OrganismSpecimen profile={profile} />}
      </div>
      <h4 className="mt-3 text-base font-semibold text-white">{profile.label}</h4>
      <p className="mt-1 text-xs leading-5 text-surface-400">{profile.detail}</p>
    </div>
  );
}

function OrganismSpecimen({ profile }: { profile: VisualProfile }) {
  const segmentClass = {
    amber: "border-amber-100/50 bg-amber-300/80",
    brown: "border-amber-900/50 bg-amber-700/80",
    cream: "border-orange-100/70 bg-orange-100/90",
    dark: "border-slate-400/50 bg-slate-500/80",
    emerald: "border-emerald-100/50 bg-emerald-300/80",
    yellow: "border-yellow-100/60 bg-yellow-400/85",
  }[profile.tone];
  const segmentCount = profile.type === "grub" ? 7 : 8;

  return (
    <div
      className={[
        "relative flex items-center gap-1.5",
        profile.type === "grub" ? "rotate-[-18deg] rounded-full" : "rotate-[-8deg]",
      ].join(" ")}
      aria-hidden="true"
    >
      {Array.from({ length: segmentCount }).map((_, index) => (
        <span
          key={index}
          className={[
            "block border shadow-[0_10px_28px_rgba(0,0,0,0.20)]",
            segmentClass,
            profile.type === "grub"
              ? index < 2 || index > 5
                ? "h-8 w-6 rounded-[45%]"
                : "h-10 w-7 rounded-[48%]"
              : "h-6 w-4 rounded-full",
          ].join(" ")}
        />
      ))}
      <span className="ml-0.5 h-4 w-4 rounded-full border border-slate-900/50 bg-slate-900/80" />
    </div>
  );
}

function FeedstockSpecimen({ tone }: { tone: VisualProfile["tone"] }) {
  const particleClass = {
    amber: "bg-amber-300/80",
    brown: "bg-amber-800/85",
    cream: "bg-orange-100/85",
    dark: "bg-slate-700/95",
    emerald: "bg-emerald-300/80",
    yellow: "bg-yellow-400/85",
  }[tone];
  const secondaryClass = tone === "dark" ? "bg-red-400/75" : tone === "brown" ? "bg-stone-500/80" : "bg-lime-300/70";

  return (
    <div className="relative h-24 w-32 overflow-hidden rounded-xl border border-white/10 bg-slate-900" aria-hidden="true">
      <div className="absolute inset-x-4 bottom-3 h-14 rounded-[45%] border border-white/10 bg-white/[0.04]" />
      {Array.from({ length: 22 }).map((_, index) => (
        <span
          key={index}
          className={[
            "absolute rounded-full shadow-[0_4px_12px_rgba(0,0,0,0.28)]",
            index % 5 === 0 ? secondaryClass : particleClass,
          ].join(" ")}
          style={{
            height: `${0.42 + (index % 4) * 0.16}rem`,
            left: `${10 + ((index * 17) % 78)}%`,
            top: `${28 + ((index * 11) % 48)}%`,
            width: `${0.42 + (index % 3) * 0.18}rem`,
          }}
        />
      ))}
      {tone === "dark" ? (
        <span className="absolute right-3 top-3 rounded-full border border-red-200/40 bg-red-500/25 px-2 py-1 text-[0.6rem] font-bold uppercase tracking-[0.12em] text-red-100">
          lock
        </span>
      ) : null}
    </div>
  );
}

function ExperimentTimeline({
  activeZoneId,
  onSelectZone,
  steps,
}: {
  activeZoneId: TwinZoneId;
  onSelectZone: (zoneId: TwinZoneId) => void;
  steps: ExperimentTimelineStep[];
}) {
  return (
    <div data-testid="labsim-experiment-timeline" className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-surface-500">Experiment timeline</p>
          <h3 className="mt-2 text-base font-semibold text-white">What the replay is doing</h3>
        </div>
        <Badge variant="info">6 review steps</Badge>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {steps.map((step, index) => (
          <button
            key={step.zoneId}
            type="button"
            onClick={() => onSelectZone(step.zoneId)}
            className={[
              "min-w-0 rounded-xl border p-3 text-left transition hover:border-cyan-200/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200",
              step.zoneId === activeZoneId ? "border-cyan-200/70 bg-cyan-300/12" : "border-white/10 bg-slate-950/30",
            ].join(" ")}
          >
            <span className="flex items-center gap-2">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-white/10 text-xs font-bold text-white">
                {index + 1}
              </span>
              <span className="text-sm font-semibold text-white">{step.label}</span>
            </span>
            <span className="mt-2 block text-xs leading-5 text-surface-400">{step.detail}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function ImportEvidenceSummary({
  importResult,
  importedAssaySource,
}: {
  importResult: SimulationScenarioImportResponse;
  importedAssaySource: SimulationScenarioImportResponse["scenario"]["evidence_sources"][number] | undefined;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.05] p-3 text-xs leading-6 text-surface-300">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <span className="font-medium text-white">{importResult.import_metadata.source_title}</span>
        <Badge variant="info">{formatPercent(importResult.import_metadata.extraction_confidence, 0)}</Badge>
      </div>
      <p className="mt-2">
        Review {importResult.import_metadata.review_status}; numeric values{" "}
        {importResult.import_metadata.numeric_values_included ? "included" : "not exposed"}; release evidence{" "}
        {importResult.import_metadata.release_evidence_allowed ? "allowed" : "blocked"}
      </p>
      <p className="text-surface-500">
        Runtime activation {importResult.import_metadata.runtime_activation_enabled ? "enabled" : "blocked"};
        validated defaults {importResult.import_metadata.validated_default_write_enabled ? "write enabled" : "locked"}
      </p>
      {importResult.scenario.lab_assay_measurements ? (
        <p className="mt-1 text-emerald-100">
          Imported assay anchors: {Object.entries(importResult.scenario.lab_assay_measurements)
            .filter(([, value]) => value !== null && value !== undefined)
            .map(([field, value]) => `${field} ${formatNumber(Number(value), 3)}`)
            .join(" / ")}
          {importedAssaySource ? `; evidence ${importedAssaySource.measurement_mode ?? "reference_imported"}` : ""}
        </p>
      ) : null}
    </div>
  );
}

function TwinProofRail({
  run,
  importResult,
  canExportAppendix,
}: {
  run: SimulationLabRunResponse | null;
  importResult: SimulationScenarioImportResponse | null;
  canExportAppendix: boolean;
}) {
  const assayMode = importResult?.scenario.lab_assay_measurements
    ? "anchors imported"
    : importResult
      ? "metadata only"
      : "profile pending";
  const proofItems: Array<{
    label: string;
    value: string;
    variant: "info" | "neutral" | "success" | "warning";
  }> = [
    {
      label: "Reference seed",
      value: importResult ? importResult.import_metadata.reference_source : "not imported",
      variant: importResult ? "info" : "neutral",
    },
    {
      label: "Run proof",
      value: run ? run.summary.simulation_id : "not run",
      variant: run ? "success" : "neutral",
    },
    {
      label: "Assay proof",
      value: assayMode,
      variant: assayMode === "anchors imported" ? "success" : assayMode === "metadata only" ? "warning" : "neutral",
    },
    {
      label: "Appendix",
      value: canExportAppendix ? "ready" : "blocked",
      variant: canExportAppendix ? "info" : "neutral",
    },
  ];

  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/35 p-3">
      <p className="text-xs uppercase tracking-[0.18em] text-surface-500">Twin proof rail</p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {proofItems.map((item) => (
          <div key={item.label} className="min-w-0 rounded-lg border border-white/10 bg-white/[0.04] p-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[0.68rem] uppercase tracking-[0.14em] text-surface-500">{item.label}</span>
              <Badge variant={item.variant} size="xs" className="max-w-[8rem] overflow-hidden text-ellipsis">
                {item.value}
              </Badge>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function getOrganismProfile(preset: LabSimPreset): VisualProfile {
  if (preset.species.toLowerCase().includes("mealworm")) {
    return {
      detail: "Yellow-brown segmented larva used here for dry substrate growth calibration.",
      label: "Mealworm",
      tone: "yellow",
      type: "mealworm",
    };
  }
  if (preset.species.toLowerCase().includes("grub")) {
    return {
      detail: "Pale curved grub route for manure and humus degradation with bioaccumulation watch.",
      label: "Grub",
      tone: "cream",
      type: "grub",
    };
  }
  return {
    detail: "Black soldier fly larvae route for high-load wet organics and larval tray conversion.",
    label: "BSF larvae",
    tone: preset.id.includes("sludge") ? "dark" : "cream",
    type: "bsf",
  };
}

function getFeedstockProfile(preset: LabSimPreset): VisualProfile {
  if (preset.feedstock.includes("sludge")) {
    return {
      detail: "Restricted sludge lane with heavy-metal screen and a visible review lock.",
      label: "Municipal sludge",
      tone: "dark",
      type: "feedstock",
    };
  }
  if (preset.feedstock.includes("manure")) {
    return {
      detail: "Manure and humus mix for odor-controlled organic matter degradation.",
      label: "Manure and humus",
      tone: "brown",
      type: "feedstock",
    };
  }
  if (preset.feedstock.includes("distillers")) {
    return {
      detail: "Distillers grain and straw blend, shown as dry granular feedstock.",
      label: preset.feedstock.includes("straw") ? "Straw + distillers grain" : "Distillers grain",
      tone: "amber",
      type: "feedstock",
    };
  }
  return {
    detail: "Mixed food waste route for high-moisture organic conversion replay.",
    label: "Mixed food waste",
    tone: "emerald",
    type: "feedstock",
  };
}

function getExperimentGoal(preset: LabSimPreset, form: SimulationScenarioCreate): string {
  const scenarioGoal: Record<SimulationScenario, string> = {
    moisture_drift: "Moisture drift review and conversion stability",
    normal: "Bioconversion replay with assay and ammonia evidence",
    temperature_spike: "Temperature spike and heavy-metal review gate",
    underfeeding: "Underfeeding response and growth calibration",
  };
  if (preset.evidenceMode.toLowerCase().includes("calibration")) {
    return `${scenarioGoal[form.scenario]}; assay calibration stays review-gated.`;
  }
  if (preset.id.includes("sludge")) {
    return `${scenarioGoal[form.scenario]}; restricted material cannot become a product-use recommendation.`;
  }
  return `${scenarioGoal[form.scenario]}; outputs remain virtual evidence.`;
}

function getRouteOutcome(preset: LabSimPreset, run: SimulationLabRunResponse | null): string {
  if (run) {
    return `Prove ${preset.shortLabel} route behavior across ${run.summary.cycle_count} cycles; ending risk ${formatPercent(run.summary.ending_risk, 1)}.`;
  }
  if (preset.id.includes("sludge")) {
    return "Show why the sludge route remains locked behind heavy-metal and human-review evidence.";
  }
  return `Show whether ${preset.shortLabel} can process ${formatCompactFeedstock(preset.feedstock)} while preserving review controls.`;
}

function getExperimentTimeline(preset: LabSimPreset): ExperimentTimelineStep[] {
  return [
    {
      detail: `${formatCompactFeedstock(preset.feedstock)} enters with identity and chain-of-custody visible.`,
      label: "Feedstock intake",
      zoneId: "intake",
    },
    {
      detail: `${getOrganismProfile(preset).label} receives the batch in the conversion bay.`,
      label: "Larvae conversion bay",
      zoneId: "bay",
    },
    {
      detail: "Moisture, substrate, heat, and biomass drift through the virtual reactor.",
      label: "Reactor drift",
      zoneId: "reactor",
    },
    {
      detail: "Sensors replay temperature, moisture, ammonia, and risk-driving observations.",
      label: "Sensor observation",
      zoneId: "sensors",
    },
    {
      detail: "Assay anchors compare model prediction with measured or profile evidence.",
      label: "Assay comparison",
      zoneId: "assay",
    },
    {
      detail: "Appendix output stays a review packet, not a release approval or runtime activation.",
      label: "Review evidence",
      zoneId: "appendix",
    },
  ];
}

function formatCompactFeedstock(feedstock: string): string {
  return feedstock
    .replace("municipal_sludge_heavy_metal_screen", "sludge heavy-metal screen")
    .replace("livestock_manure_humus_mix", "manure humus mix")
    .replace("straw_distillers_grain_blend", "straw distillers grain")
    .replace("mixed_food_waste", "mixed food waste")
    .replace(/_/g, " ");
}

function formatRouteOptionLabel(preset: LabSimPreset): string {
  if (preset.id.includes("sludge")) return "BSF sludge redline";
  if (preset.feedstock.includes("manure")) return "Grub manure";
  if (preset.species.toLowerCase().includes("mealworm")) return "Mealworm grain";
  if (preset.feedstock.includes("distillers")) return "BSF distillers";
  return `${preset.shortLabel} route`;
}

function formatScenarioOptionLabel(scenario: SimulationScenario): string {
  const labels: Record<SimulationScenario, string> = {
    moisture_drift: "Moisture drift",
    normal: "Normal",
    temperature_spike: "Temp spike",
    underfeeding: "Underfeeding",
  };
  return labels[scenario];
}

function formatPolicyOptionLabel(policy: SimulationPolicy): string {
  const labels: Record<SimulationPolicy, string> = {
    conservative: "Conservative",
    growth_optimized: "Growth opt.",
    risk_minimizing: "Risk min.",
    rule_based: "Rule based",
  };
  return labels[policy];
}

function getStationOperation({
  zoneId,
  preset,
  run,
  cycle,
  importResult,
  riskVariant,
}: {
  zoneId: TwinZoneId;
  preset: LabSimPreset;
  run: SimulationLabRunResponse | null;
  cycle: SimulationLabCycle | null;
  importResult: SimulationScenarioImportResponse | null;
  riskVariant: "danger" | "neutral" | "success" | "warning";
}): TwinStationOperation {
  const sourceKind = importResult?.import_metadata.reference_source ?? "profile";
  const reviewStatus = importResult?.import_metadata.review_status ?? preset.reviewStatus;
  const cyclePhase = cycle ? `Cycle ${cycle.cycle} replay` : run ? "Run summary loaded" : "Pre-run setup";
  const riskStatus =
    riskVariant === "danger" ? "review required" : riskVariant === "warning" ? "risk watch" : riskVariant === "success" ? "contained" : "standby";
  const commonBoundary = "Review evidence only; no runtime activation, hardware execution, or validated-default write.";
  const operations: Record<TwinZoneId, TwinStationOperation> = {
    intake: {
      status: importResult ? "reference staged" : "route selected",
      variant: importResult ? "info" : "neutral",
      phase: "Material identity",
      evidence: `Source ${sourceKind}; review ${reviewStatus}`,
      nextStep: "Confirm species, feedstock, chain of custody, and reference import before running.",
      boundary: commonBoundary,
    },
    pretreatment: {
      status: "conditioning",
      variant: "info",
      phase: cyclePhase,
      evidence: cycle ? "Synthetic moisture and substrate telemetry from the selected cycle." : "Initial state values from the active route.",
      nextStep: "Use advanced parameters only when an operator needs a deliberate state override.",
      boundary: commonBoundary,
    },
    sensors: {
      status: cycle ? "telemetry live" : "standby",
      variant: cycle ? "success" : "neutral",
      phase: cyclePhase,
      evidence: cycle ? `Temperature ${formatNumber(Number(cycle.sensor_observation.temperature), 1)} C; NH3 ${formatNumber(Number(cycle.sensor_observation.nh3), 2)}` : "No synthetic sensor cycle has been generated yet.",
      nextStep: "Run the virtual loop, then replay cycles to inspect risk-driving telemetry.",
      boundary: commonBoundary,
    },
    bay: {
      status: preset.shortLabel,
      variant: preset.id.includes("sludge") ? "warning" : "success",
      phase: preset.containment,
      evidence: preset.notes.join(" / "),
      nextStep: "Keep lane selection explicit before importing references or starting the run.",
      boundary: commonBoundary,
    },
    reactor: {
      status: riskStatus,
      variant: riskVariant === "neutral" ? "neutral" : riskVariant,
      phase: cyclePhase,
      evidence: cycle ? cycle.agent_action.reason_codes.join(" / ") || "agent action recorded" : "Awaiting deterministic twin execution.",
      nextStep: cycle ? cycle.agent_action.recommended_action.replace(/_/g, " ") : "Run experiment",
      boundary: commonBoundary,
    },
    review: {
      status: preset.id.includes("sludge") || riskVariant === "danger" ? "locked" : "review gate",
      variant: preset.id.includes("sludge") || riskVariant === "danger" ? "danger" : "warning",
      phase: preset.reviewStatus,
      evidence: preset.productLock,
      nextStep: "Prepare an appendix for human review; do not mutate release state.",
      boundary: commonBoundary,
    },
    assay: {
      status: importResult?.scenario.lab_assay_measurements ? "anchors imported" : "profile anchor",
      variant: importResult?.scenario.lab_assay_measurements ? "success" : "neutral",
      phase: "Assay evidence",
      evidence: importResult
        ? `Numeric values ${importResult.import_metadata.numeric_values_included ? "included" : "not exposed"}; source ${sourceKind}`
        : preset.evidenceMode,
      nextStep: "Compare predicted state against measured or profile anchors without promoting raw values.",
      boundary: commonBoundary,
    },
    actuator: {
      status: cycle?.actuator_result.status ?? "disabled",
      variant: "neutral",
      phase: "Virtual actuator sandbox",
      evidence: cycle ? `Hardware execution ${cycle.actuator_result.hardware_execution ? "enabled" : "false"}` : "No actuator effect generated yet.",
      nextStep: "Use actuator output as simulated evidence only.",
      boundary: commonBoundary,
    },
    appendix: {
      status: "downloadable",
      variant: "info",
      phase: "Release review packet",
      evidence: run ? run.summary.simulation_id : "No simulation selected yet.",
      nextStep: "Export appendix after import/run proof is available.",
      boundary: commonBoundary,
    },
  };
  return operations[zoneId];
}

function getStationWorkflow({
  zoneId,
  preset,
  run,
  importResult,
}: {
  zoneId: TwinZoneId;
  preset: LabSimPreset;
  run: SimulationLabRunResponse | null;
  importResult: SimulationScenarioImportResponse | null;
}): TwinWorkflowStep[] {
  const isRestrictedRoute = preset.id.includes("sludge") || preset.feedstock.includes("sludge");
  const importStatus = importResult ? "Reference imported into a persisted simulation scenario." : "Use Reference ID or route defaults before run.";
  const runStatus = run ? `Run proof available: ${run.summary.simulation_id}` : "Run experiment to generate cycle proof.";
  const assayStatus = importResult?.scenario.lab_assay_measurements
    ? "Measured assay anchors are present and review-gated."
    : importResult
      ? "Metadata-only import keeps numeric anchors hidden."
      : "Profile anchors are used until a reference import is reviewed.";
  const restrictedReviewStep: TwinWorkflowStep = {
    label: "Human review gate",
    detail: isRestrictedRoute
      ? "Restricted feedstock stays locked for research simulation and review evidence only."
      : "Review gate remains visible before any release-facing interpretation.",
    variant: isRestrictedRoute ? "danger" : "warning",
  };
  const workflows: Record<TwinZoneId, TwinWorkflowStep[]> = {
    intake: [
      { label: "Identify batch", detail: `${preset.species} on ${preset.feedstock}`, variant: "info" },
      { label: "Import reference", detail: importStatus, variant: importResult ? "success" : "neutral" },
      restrictedReviewStep,
    ],
    pretreatment: [
      { label: "Set conditioning", detail: "Moisture, substrate, temperature, and nitrogen remain editable in advanced parameters.", variant: "info" },
      { label: "Route defaults", detail: `${preset.shortLabel} preset keeps validated defaults untouched.`, variant: "success" },
      { label: "Run boundary", detail: "All effects are virtual; no hardware execution is enabled.", variant: "neutral" },
    ],
    sensors: [
      { label: "Generate telemetry", detail: runStatus, variant: run ? "success" : "neutral" },
      { label: "Replay cycles", detail: "Use Previous cycle, Next cycle, or slider playback to inspect drift.", variant: "info" },
      { label: "Risk heat", detail: "Sensor heat is a UI risk layer, not a release decision.", variant: "warning" },
    ],
    bay: [
      { label: "Lane intent", detail: preset.containment, variant: isRestrictedRoute ? "warning" : "success" },
      { label: "Route notes", detail: preset.notes.join(" / "), variant: "info" },
      restrictedReviewStep,
    ],
    reactor: [
      { label: "Run experiment", detail: runStatus, variant: run ? "success" : "neutral" },
      { label: "Supervisor action", detail: run ? run.summary.policy.replace(/_/g, " ") : "Policy selected but not executed.", variant: "info" },
      { label: "Result status", detail: "Twin output is evidence for review and does not mutate runtime state.", variant: "warning" },
    ],
    review: [
      restrictedReviewStep,
      { label: "Product lock", detail: preset.productLock, variant: isRestrictedRoute ? "danger" : "warning" },
      { label: "Appendix only", detail: "Release appendix documents evidence without changing release status.", variant: "info" },
    ],
    assay: [
      { label: "Assay state", detail: assayStatus, variant: importResult?.scenario.lab_assay_measurements ? "success" : "neutral" },
      {
        label: "Numeric boundary",
        detail: importResult?.import_metadata.numeric_values_included
          ? "Numeric anchors are shown as review-gated."
          : "Numeric values are not exposed.",
        variant: importResult?.import_metadata.numeric_values_included ? "info" : "warning",
      },
      { label: "No promotion", detail: "Candidate or literature values do not become validated defaults.", variant: "warning" },
    ],
    actuator: [
      { label: "Sandbox action", detail: run ? "Virtual actuator output has cycle evidence." : "No actuator effect until a run exists.", variant: run ? "success" : "neutral" },
      { label: "Hardware lock", detail: "Hardware execution remains false for LabSim.", variant: "warning" },
      { label: "Operator use", detail: "Treat recommendations as simulation evidence only.", variant: "info" },
    ],
    appendix: [
      { label: "Evidence packet", detail: runStatus, variant: run ? "success" : "neutral" },
      { label: "Download appendix", detail: "Markdown export is available when a run or scenario is selected.", variant: run ? "info" : "neutral" },
      { label: "Release boundary", detail: "Exporting does not approve, promote, or activate release state.", variant: "warning" },
    ],
  };
  return workflows[zoneId];
}

function TwinFactoryScene({
  zones,
  operations,
  cycle,
  selectedZoneId,
  riskVariant,
  biomassLevel,
  sensorHeat,
  cycleCount,
  selectedCycleIndex,
  onSelectZone,
}: {
  zones: TwinZone[];
  operations: Record<TwinZoneId, TwinStationOperation>;
  cycle: SimulationLabCycle | null;
  selectedZoneId: TwinZoneId;
  riskVariant: "danger" | "neutral" | "success" | "warning";
  biomassLevel: number;
  sensorHeat: number;
  cycleCount: number;
  selectedCycleIndex: number;
  onSelectZone: (zoneId: TwinZoneId) => void;
}) {
  const progress = cycleCount ? Math.round(((selectedCycleIndex + 1) / cycleCount) * 100) : 18;
  const heatColor = riskVariant === "danger" ? "rgba(248,113,113,0.24)" : riskVariant === "warning" ? "rgba(252,211,77,0.22)" : "rgba(103,232,249,0.20)";

  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-950/60 p-4">
      <div className="relative min-h-[32rem] min-w-[44rem] overflow-hidden rounded-2xl border border-white/10 bg-[linear-gradient(135deg,rgba(14,165,233,0.10),rgba(15,23,42,0.35)_34%,rgba(16,185,129,0.08))]">
        <div
          className="absolute inset-6 rounded-[2rem] border border-cyan-200/10 bg-slate-950/60"
          style={{
            backgroundImage:
              "linear-gradient(rgba(148,163,184,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.08) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
            transform: "skewY(-5deg)",
          }}
        />
        <div
          className="absolute rounded-full blur-2xl transition-all duration-500"
          style={{
            left: "52%",
            top: "9%",
            width: `${14 + sensorHeat * 16}%`,
            height: `${14 + sensorHeat * 16}%`,
            background: heatColor,
          }}
        />
        <div className="absolute left-[8%] right-[8%] top-[32%] h-3 rounded-full bg-cyan-200/40 shadow-[0_0_22px_rgba(103,232,249,0.25)]" />
        <div className="absolute bottom-[18%] left-[10%] right-[8%] h-3 rounded-full bg-emerald-200/30 shadow-[0_0_22px_rgba(110,231,183,0.18)]" />
        <div className="absolute left-[8%] right-[8%] top-[30%]">
          <div className="mb-2 flex items-center justify-between text-[0.62rem] uppercase tracking-[0.16em] text-cyan-100/70">
            <span>Batch flow</span>
            <span>{cycleCount ? `cycle ${selectedCycleIndex + 1}` : "standby"}</span>
          </div>
          <span className="block h-2 overflow-hidden rounded-full bg-white/10">
            <span
              className="block h-full rounded-full bg-cyan-200 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </span>
        </div>
        <div className="absolute left-[15%] top-[34%] flex w-[70%] justify-between">
          {Array.from({ length: 6 }).map((_, index) => (
            <span
              key={index}
              className={[
                "h-2.5 w-2.5 rounded-full",
                index <= Math.round(progress / 20) ? "animate-pulse bg-cyan-100" : "bg-white/20",
              ].join(" ")}
            />
          ))}
        </div>
        {zones.map((zone) => (
          <TwinZoneButton
            key={zone.id}
            zone={zone}
            operation={operations[zone.id]}
            selected={zone.id === selectedZoneId}
            onSelect={() => onSelectZone(zone.id)}
          />
        ))}
        <div className="absolute left-[9%] top-[49%] grid w-[19%] grid-cols-5 gap-1">
          {Array.from({ length: 15 }).map((_, index) => (
            <span
              key={index}
              className={[
                "aspect-square rounded-sm border",
                index < Math.round(biomassLevel / 7)
                  ? "border-emerald-100/40 bg-emerald-300/35"
                  : "border-white/10 bg-white/[0.04]",
              ].join(" ")}
            />
          ))}
        </div>
        <div className="absolute right-6 top-6 flex flex-wrap justify-end gap-2">
          <Badge variant={riskVariant}>Twin risk layer</Badge>
          <Badge variant="info">Sensor heat</Badge>
          <Badge variant="brand">Click stations</Badge>
        </div>
        <TwinCycleTelemetryOverlay cycle={cycle} riskVariant={riskVariant} />
      </div>
    </div>
  );
}

function TwinCycleTelemetryOverlay({
  cycle,
  riskVariant,
}: {
  cycle: SimulationLabCycle | null;
  riskVariant: "danger" | "neutral" | "success" | "warning";
}) {
  const sensorValue = (field: string, precision = 1): string => {
    const value = cycle?.sensor_observation[field];
    if (value == null || value === "") return "n/a";
    return typeof value === "number" ? formatNumber(value, precision) : String(value);
  };
  const supervisorStatus = cycle?.supervisor_decision.recommended_handover ? "handover" : cycle ? "continue" : "standby";
  const action = cycle?.agent_action.recommended_action.replace(/_/g, " ") ?? "awaiting run";
  const risk = cycle ? formatPercent(cycle.risk_prediction.future_risk_score, 1) : "pending";

  return (
    <div
      data-testid="cycle-telemetry-overlay"
      className="absolute bottom-6 left-6 w-[20rem] rounded-2xl border border-white/10 bg-slate-950/85 p-3 shadow-2xl backdrop-blur lg:left-auto lg:right-6"
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs uppercase tracking-[0.18em] text-surface-500">Cycle telemetry overlay</p>
        <Badge variant={cycle ? riskVariant : "neutral"}>{cycle ? `cycle ${cycle.cycle}` : "standby"}</Badge>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <TelemetryCell label="Risk score" value={risk} />
        <TelemetryCell label="Supervisor" value={supervisorStatus} />
        <TelemetryCell label="Temperature" value={`${sensorValue("temperature")} C`} />
        <TelemetryCell label="Moisture" value={`${sensorValue("moisture")} %`} />
        <TelemetryCell label="NH3" value={sensorValue("nh3", 2)} />
        <TelemetryCell label="Action" value={action} />
      </div>
    </div>
  );
}

function TelemetryCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-white/10 bg-white/[0.04] p-2">
      <p className="text-[0.62rem] uppercase tracking-[0.14em] text-surface-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function TwinZoneButton({
  zone,
  operation,
  selected,
  onSelect,
}: {
  zone: TwinZone;
  operation: TwinStationOperation;
  selected: boolean;
  onSelect: () => void;
}) {
  const toneClass = {
    amber: "border-amber-300/35 bg-amber-400/15 shadow-[0_0_22px_rgba(252,211,77,0.10)]",
    cyan: "border-cyan-300/35 bg-cyan-400/15 shadow-[0_0_22px_rgba(103,232,249,0.12)]",
    emerald: "border-emerald-300/35 bg-emerald-400/15 shadow-[0_0_22px_rgba(110,231,183,0.12)]",
    neutral: "border-white/15 bg-white/[0.055]",
    red: "border-red-400/40 bg-red-500/15 shadow-[0_0_22px_rgba(248,113,113,0.14)]",
    sky: "border-sky-300/35 bg-sky-400/15 shadow-[0_0_22px_rgba(125,211,252,0.12)]",
    violet: "border-violet-300/35 bg-violet-400/15 shadow-[0_0_22px_rgba(196,181,253,0.12)]",
  }[zone.tone];

  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      className={[
        "absolute rounded-xl border p-3 text-left transition hover:-translate-y-0.5 hover:border-white/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200",
        selected ? "ring-2 ring-cyan-200/80" : "",
        toneClass,
      ].join(" ")}
      style={{
        left: `${zone.x}%`,
        top: `${zone.y}%`,
        width: `${zone.w}%`,
        height: `${zone.h}%`,
      }}
    >
      <span className="flex items-start justify-between gap-2">
        <span className="text-[0.62rem] uppercase tracking-[0.16em] text-surface-500">{zone.label}</span>
        <Badge variant={operation.variant} size="xs" className="max-w-[5.75rem] shrink-0 overflow-hidden text-ellipsis">
          {operation.status}
        </Badge>
      </span>
      <span className="mt-2 block line-clamp-2 text-sm font-semibold text-white">{zone.value}</span>
    </button>
  );
}

function TwinZoneDetail({
  zone,
  operation,
  workflow,
  riskVariant,
  riskScore,
}: {
  zone: TwinZone;
  operation: TwinStationOperation;
  workflow: TwinWorkflowStep[];
  riskVariant: "danger" | "neutral" | "success" | "warning";
  riskScore: number | null;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-surface-500">Selected station</p>
          <h3 className="mt-2 text-base font-semibold text-white">{zone.label}</h3>
        </div>
        <Badge variant={riskVariant}>{riskScore == null ? "Risk pending" : formatPercent(riskScore, 1)}</Badge>
      </div>
      <p className="mt-3 text-sm leading-6 text-surface-300">{zone.detail}</p>
      <div className="mt-4 space-y-2 text-sm">
        {zone.metrics.map(([label, value]) => (
          <TraceRow key={label} label={label} value={value} />
        ))}
      </div>
      <div className="mt-4 rounded-xl border border-white/10 bg-slate-950/35 p-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs uppercase tracking-[0.18em] text-surface-500">Station operations</p>
          <Badge variant={operation.variant}>{operation.status}</Badge>
        </div>
        <div className="mt-3 space-y-2 text-sm">
          <TraceRow label="Phase" value={operation.phase} />
          <TraceRow label="Evidence source" value={operation.evidence} />
          <TraceRow label="Next step" value={operation.nextStep} />
          <TraceRow label="Guardrail" value={operation.boundary} />
        </div>
      </div>
      <div className="mt-4 rounded-xl border border-white/10 bg-slate-950/35 p-3">
        <p className="text-xs uppercase tracking-[0.18em] text-surface-500">Station workflow</p>
        <div className="mt-3 space-y-2">
          {workflow.map((step) => (
            <div key={step.label} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-white">{step.label}</span>
                <Badge variant={step.variant} size="xs">{workflowBadgeLabel(step.variant)}</Badge>
              </div>
              <p className="mt-2 text-xs leading-5 text-surface-400">{step.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function workflowBadgeLabel(variant: TwinWorkflowStep["variant"]): string {
  const labels: Record<TwinWorkflowStep["variant"], string> = {
    danger: "blocked",
    info: "info",
    neutral: "pending",
    success: "ready",
    warning: "watch",
  };
  return labels[variant];
}

function TwinPlaybackControls({
  cycle,
  cycleCount,
  selectedCycleIndex,
  previousCycle,
  nextCycle,
  onSelectCycle,
}: {
  cycle: SimulationLabCycle | null;
  cycleCount: number;
  selectedCycleIndex: number;
  previousCycle: () => void;
  nextCycle: () => void;
  onSelectCycle: (index: number) => void;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs uppercase tracking-[0.18em] text-surface-500">Cycle playback</p>
        <Badge variant={cycleCount ? "info" : "neutral"}>{cycleCount ? `${selectedCycleIndex + 1}/${cycleCount}` : "No run"}</Badge>
      </div>
      {cycleCount ? (
        <div className="mt-4 grid gap-3">
          <div className="grid grid-cols-2 gap-2">
            <Button type="button" variant="secondary" disabled={selectedCycleIndex === 0} onClick={previousCycle}>
              Previous cycle
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={selectedCycleIndex >= cycleCount - 1}
              onClick={nextCycle}
            >
              Next cycle
            </Button>
          </div>
          <input
            aria-label="Twin cycle playback"
            type="range"
            min={0}
            max={cycleCount - 1}
            value={selectedCycleIndex}
            onChange={(event) => onSelectCycle(Number(event.target.value))}
            className="w-full accent-cyan-300"
          />
          <div className="grid grid-cols-2 gap-3 text-sm">
            <TraceMetric label="Cycle risk" value={formatPercent(cycle?.risk_prediction.future_risk_score ?? 0, 1)} />
            <TraceMetric label="Action" value={cycle?.agent_action.recommended_action.replace(/_/g, " ") ?? "n/a"} />
          </div>
        </div>
      ) : (
        <EmptyTraceState label="Run the virtual loop to animate the twin floor." />
      )}
    </div>
  );
}

function TraceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-surface-400">{label}</span>
      <span className="max-w-[18rem] break-words text-right font-medium text-white">{value}</span>
    </div>
  );
}

function TraceMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-surface-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}

function EmptyTraceState({ label = "Run a virtual loop to populate this panel." }: { label?: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-5 text-sm text-surface-400">
      {label}
    </div>
  );
}
