import { type ChangeEvent, type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bug,
  Download,
  FlaskConical,
  Gauge,
  History,
  Image,
  Microscope,
  Play,
  RadioTower,
  RefreshCw,
  ScrollText,
  ShieldAlert,
  Warehouse,
} from "lucide-react";
import toast from "react-hot-toast";

import { simulationLabApi } from "@/api/simulationLabApi";
import {
  LabSimTwinStudio,
  type HeavyMetalKey,
  type LabSimPreset,
} from "@/components/labsim/LabSimTwinStudio";
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
import { Select } from "@/components/ui/Select";
import { downloadBlob, formatNumber, formatPercent } from "@/lib/utils";
import type {
  LabAssayMeasurements,
  SimulationLabCycle,
  SimulationLabRunHistoryItem,
  SimulationLabRunResponse,
  SimulationPolicy,
  SimulationPolicyComparisonResponse,
  SimulationScenario,
  SimulationScenarioCreate,
  SimulationScenarioImportResponse,
  SimulationScenarioResponse,
} from "@/types/simulationLab";

const scenarioOptions: Array<{ value: SimulationScenario; label: string }> = [
  { value: "normal", label: "Normal" },
  { value: "moisture_drift", label: "Moisture drift" },
  { value: "temperature_spike", label: "Temperature spike" },
  { value: "underfeeding", label: "Underfeeding" },
];

const policyOptions: Array<{ value: SimulationPolicy; label: string }> = [
  { value: "rule_based", label: "Rule based" },
  { value: "conservative", label: "Conservative" },
  { value: "growth_optimized", label: "Growth optimized" },
  { value: "risk_minimizing", label: "Risk minimizing" },
];

const defaultForm: SimulationScenarioCreate = {
  species: "BSF",
  feedstock: "mixed_food_waste",
  scenario: "moisture_drift",
  cycles: 8,
  seed: 17,
  policy: "rule_based",
  initial_state: {
    biomass: 0.5,
    substrate: 10,
    temperature: 28,
    moisture: 70,
    nitrogen: 50,
  },
};

const labSimPresets: LabSimPreset[] = [
  {
    id: "grub_manure_humus",
    label: "Grub manure and humus lane",
    shortLabel: "Grub",
    species: "grub",
    feedstock: "livestock_manure_humus_mix",
    scenario: "moisture_drift",
    policy: "risk_minimizing",
    initial_state: { biomass: 0.42, substrate: 8.6, temperature: 26.5, moisture: 72, nitrogen: 62 },
    reviewStatus: "Soil-remediation study only",
    productLock: "No feed or fertilizer release without reviewed assay packet",
    containment: "Biosafety and odor-control bench",
    evidenceMode: "Lab measurement candidate",
    heavyMetals: { Cd: 0.36, Pb: 0.42, Hg: 0.24, As: 0.33, Cr: 0.39 },
    notes: ["Organic matter degradation", "Frass stability", "Bioaccumulation watch"],
  },
  {
    id: "mealworm_straw_distillers",
    label: "Mealworm straw and distillers grain lane",
    shortLabel: "Mealworm",
    species: "mealworm",
    feedstock: "straw_distillers_grain_blend",
    scenario: "underfeeding",
    policy: "growth_optimized",
    initial_state: { biomass: 0.35, substrate: 7.2, temperature: 27, moisture: 58, nitrogen: 38 },
    reviewStatus: "Nutrition-growth calibration",
    productLock: "Feed pathway locked until source and assay review",
    containment: "Dry substrate insect culture bench",
    evidenceMode: "Prediction vs measured calibration",
    heavyMetals: { Cd: 0.18, Pb: 0.2, Hg: 0.1, As: 0.16, Cr: 0.19 },
    notes: ["Protein and lipid output", "Fiber limitation", "Water activity control"],
  },
  {
    id: "bsf_distillers_grain",
    label: "BSF distillers grain high-moisture lane",
    shortLabel: "BSF",
    species: "BSF",
    feedstock: "distillers_grain",
    scenario: "normal",
    policy: "rule_based",
    initial_state: { biomass: 0.5, substrate: 10, temperature: 28, moisture: 70, nitrogen: 50 },
    reviewStatus: "Pilot-ready after assay review",
    productLock: "Scale-up requires moisture and ammonia evidence",
    containment: "High-throughput larval tray bay",
    evidenceMode: "BOS virtual batch plus lab assay",
    heavyMetals: { Cd: 0.14, Pb: 0.17, Hg: 0.08, As: 0.12, Cr: 0.15 },
    notes: ["High organic load", "Dewatering cost", "Ammonia and heat watch"],
  },
  {
    id: "bsf_sludge_redline",
    label: "BSF sludge heavy-metal redline lane",
    shortLabel: "Sludge",
    species: "BSF",
    feedstock: "municipal_sludge_heavy_metal_screen",
    scenario: "temperature_spike",
    policy: "risk_minimizing",
    initial_state: { biomass: 0.28, substrate: 6.4, temperature: 29, moisture: 76, nitrogen: 68 },
    reviewStatus: "Human review required",
    productLock: "Research simulation only; no product-use recommendation",
    containment: "Restricted hazardous sample bench",
    evidenceMode: "Official-standard redline candidate",
    heavyMetals: { Cd: 0.82, Pb: 0.78, Hg: 0.69, As: 0.74, Cr: 0.71 },
    notes: ["Heavy-metal migration", "Pathogen and odor risk", "Release route blocked"],
  },
];

const labStations = [
  { name: "Sample intake", detail: "source batch, chain of custody", tone: "cyan", className: "col-span-2" },
  { name: "Pretreatment", detail: "mixing, moisture, C/N adjustment", tone: "violet", className: "col-span-2" },
  { name: "Grub bay", detail: "manure and humus degradation", tone: "amber", className: "" },
  { name: "Mealworm bay", detail: "dry protein-growth calibration", tone: "emerald", className: "" },
  { name: "BSF bay", detail: "high-throughput wet organics", tone: "sky", className: "" },
  { name: "Restricted sludge", detail: "heavy-metal review lock", tone: "red", className: "" },
  { name: "Assay bench", detail: "moisture, protein, lipid, TS/VS", tone: "cyan", className: "col-span-2" },
  { name: "Evidence vault", detail: "SOP, raw data, model version", tone: "neutral", className: "col-span-2" },
];

function findLabPreset(form: SimulationScenarioCreate): LabSimPreset {
  return (
    labSimPresets.find((preset) => preset.species === form.species && preset.feedstock === form.feedstock)
    ?? labSimPresets[2]
  );
}

function latestCycle(run: SimulationLabRunResponse | null): SimulationLabCycle | null {
  if (!run?.cycles.length) return null;
  return run.cycles[run.cycles.length - 1];
}

function formatPolicy(policy: SimulationPolicy): string {
  return policyOptions.find((option) => option.value === policy)?.label ?? policy.replace("_", " ");
}

function formFromScenario(scenario: SimulationScenarioResponse): SimulationScenarioCreate {
  return {
    species: scenario.species,
    feedstock: scenario.feedstock,
    scenario: scenario.scenario,
    cycles: scenario.cycles,
    seed: scenario.seed,
    policy: scenario.policy,
    lab_assay_measurements: scenario.lab_assay_measurements,
    initial_state: scenario.initial_state,
  };
}

function isSimulationLabDisabledError(error: unknown): boolean {
  return (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "bos_simulation_lab_disabled";
}

function buildLocalReviewRun(
  form: SimulationScenarioCreate,
  preset: LabSimPreset,
  simulationId: string,
): SimulationLabRunResponse {
  const startedAt = new Date().toISOString();
  const cycles = Array.from({ length: Math.max(1, form.cycles) }, (_, index): SimulationLabCycle => {
    const cycleNumber = index + 1;
    const progress = form.cycles > 1 ? index / (form.cycles - 1) : 1;
    const riskBase = preset.id.includes("sludge") ? 0.72 : preset.scenario === "temperature_spike" ? 0.54 : 0.38;
    const futureRiskScore = Math.min(0.92, Math.max(0.18, riskBase - progress * 0.08));
    const stateBefore = {
      biomass: form.initial_state.biomass + progress * 0.1,
      substrate: form.initial_state.substrate - progress * 1.4,
      temperature: form.initial_state.temperature + (form.scenario === "temperature_spike" ? 1.5 : 0.2) * progress,
      moisture: form.initial_state.moisture - progress * 2.2,
      nitrogen: form.initial_state.nitrogen - progress * 1.5,
    };
    const stateAfter = {
      biomass: stateBefore.biomass + 0.03,
      substrate: Math.max(0, stateBefore.substrate - 0.2),
      temperature: stateBefore.temperature,
      moisture: Math.max(0, stateBefore.moisture - 0.3),
      nitrogen: Math.max(0, stateBefore.nitrogen - 0.2),
    };

    return {
      cycle: cycleNumber,
      timestamp: startedAt,
      state_before: stateBefore,
      sensor_observation: {
        temperature: stateAfter.temperature,
        moisture: stateAfter.moisture,
        nh3: 1.1 + progress * 0.6,
      },
      supervisor_decision: {
        recommended_handover: futureRiskScore >= 0.68,
        mode: "local_review_replay",
      },
      risk_prediction: {
        future_risk_score: futureRiskScore,
        release_warning_score: Math.min(1, futureRiskScore + 0.08),
        forecast_window: "local frontend replay",
        model_name: "simulation_lab_frontend_review_preview",
        driver_features: {
          moisture: stateAfter.moisture,
          temperature: stateAfter.temperature,
          heavy_metal_index: preset.heavyMetals.Cd,
        },
        source: "frontend_fallback",
        execution_mode: "review_evidence_only",
        confidence_band: {
          lower: Math.max(0, futureRiskScore - 0.08),
          median: futureRiskScore,
          upper: Math.min(1, futureRiskScore + 0.08),
        },
        lab_governance: {
          profile_id: preset.id,
          heavy_metal_gate: preset.id.includes("sludge") ? "human_review_required" : "screened",
          product_use_lock: preset.productLock,
          review_status: preset.reviewStatus,
        },
        lab_assay_comparison: {
          source_kind: "frontend_fallback",
          source_ref: `local_review_preview:${preset.id}`,
          review_status: preset.reviewStatus,
          measurement_mode: "profile_anchor",
          human_review_required: true,
          numeric_values_included: false,
          release_evidence_allowed: false,
          runtime_activation_enabled: false,
          validated_default_write_enabled: false,
          promotion_enabled: false,
          predicted: {
            biomass: stateAfter.biomass,
            substrate: stateAfter.substrate,
            moisture: stateAfter.moisture,
            heavy_metal_index: preset.heavyMetals.Cd,
          },
          measured_anchor: {
            biomass: form.initial_state.biomass,
            substrate: form.initial_state.substrate,
            moisture: form.initial_state.moisture,
            heavy_metal_index: preset.heavyMetals.Cd,
          },
          residuals: {
            biomass: 0,
            substrate: 0,
            moisture: 0,
            heavy_metal_index: 0,
          },
          out_of_band: [],
          calibration_status: "frontend_review_preview",
        },
      },
      visual_observation: {
        source: "frontend_preview",
        frame_id: `preview-${cycleNumber}`,
        anomaly_labels: preset.id.includes("sludge") ? ["restricted_material"] : [],
        confidence: 0.72,
        ultralytics_dry_run: true,
        hardware_camera_used: false,
      },
      evidence_sources: [
        {
          field: "frontend_review_replay",
          source_kind: "synthetic",
          source_ref: `local_review_preview:${preset.id}`,
          confidence: 0.72,
          fallback_used: true,
          notes: "Frontend-only replay shown because backend execution is unavailable.",
          measurement_mode: "profile_anchor",
          review_status: preset.reviewStatus,
          human_review_required: true,
          numeric_values_included: false,
          release_evidence_allowed: false,
          runtime_activation_enabled: false,
          validated_default_write_enabled: false,
          promotion_enabled: false,
        },
      ],
      agent_action: {
        policy: form.policy,
        recommended_action: futureRiskScore >= 0.68 ? "hold_for_review" : "feed",
        intensity: futureRiskScore >= 0.68 ? 0 : 0.35,
        duration_minutes: futureRiskScore >= 0.68 ? 0 : 15,
        reason_codes: ["frontend_review_preview", "frontend_only_review_replay"],
        confidence: 0.72,
        expected_risk_reduction: 0,
      },
      actuator_result: {
        action: "none",
        status: "blocked",
        expected_effect: { runtime: "blocked" },
        actual_effect: { hardware_execution: "false" },
        hardware_execution: false,
      },
      state_after: stateAfter,
      audit_event: {
        event_type: "frontend_review_preview",
        runtime_activation_enabled: false,
        hardware_execution: false,
        validated_default_write_enabled: false,
      },
    };
  });
  const endingRisk = cycles[cycles.length - 1]?.risk_prediction.future_risk_score ?? 0.38;

  return {
    scenario: {
      ...form,
      simulation_id: simulationId,
      batch_id: "frontend-review-preview",
      tenant_id: 0,
      status: "frontend_review_preview",
      created_at: startedAt,
      evidence_sources: cycles[0]?.evidence_sources ?? [],
    },
    summary: {
      simulation_id: simulationId,
      cycle_count: cycles.length,
      scenario: form.scenario,
      policy: form.policy,
      starting_risk: cycles[0]?.risk_prediction.future_risk_score ?? endingRisk,
      ending_risk: endingRisk,
      risk_delta: endingRisk - (cycles[0]?.risk_prediction.future_risk_score ?? endingRisk),
      action_count: cycles.length,
      audit_event_count: cycles.length,
      final_state: cycles[cycles.length - 1]?.state_after ?? form.initial_state,
    },
    cycles,
  };
}

export default function BOSSimulationLabPage() {
  const urlSimulationId = useMemo(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("simulationId") ?? "";
  }, []);
  const [form, setForm] = useState<SimulationScenarioCreate>(defaultForm);
  const [run, setRun] = useState<SimulationLabRunResponse | null>(null);
  const [comparison, setComparison] = useState<SimulationPolicyComparisonResponse | null>(null);
  const [importResult, setImportResult] = useState<SimulationScenarioImportResponse | null>(null);
  const [referenceId, setReferenceId] = useState("beer_lees_moisture_gradient");
  const [selectedPolicies, setSelectedPolicies] = useState<SimulationPolicy[]>(
    policyOptions.map((option) => option.value),
  );
  const [scenarios, setScenarios] = useState<SimulationScenarioResponse[]>([]);
  const [historyScenarioId, setHistoryScenarioId] = useState<string>("");
  const [runTargetSimulationId, setRunTargetSimulationId] = useState<string>(urlSimulationId);
  const [runHistory, setRunHistory] = useState<SimulationLabRunHistoryItem[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [isImportingReference, setIsImportingReference] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isExportingAppendix, setIsExportingAppendix] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [selectedTwinCycleIndex, setSelectedTwinCycleIndex] = useState(0);

  const lastCycle = latestCycle(run);
  const activeLabPreset = useMemo(() => findLabPreset(form), [form]);
  const selectedTwinCycle = run?.cycles[selectedTwinCycleIndex] ?? lastCycle;
  const assayComparison = lastCycle?.risk_prediction.lab_assay_comparison;
  const importedAssaySource = importResult?.scenario.evidence_sources.find(
    (source) => source.field === "lab_assay_measurements",
  );
  const riskPosture = useMemo(() => {
    const endingRisk = run?.summary.ending_risk;
    if (endingRisk == null) return { label: "Awaiting run", variant: "neutral" as const };
    if (endingRisk < 0.45) return { label: "Risk contained", variant: "success" as const };
    if (endingRisk < 0.68) return { label: "Risk watch", variant: "warning" as const };
    return { label: "Human review", variant: "danger" as const };
  }, [run]);

  const updateField = (field: keyof SimulationScenarioCreate) => (
    event: ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    const value = event.target.value;
    setRunTargetSimulationId("");
    setForm((current) => ({
      ...current,
      [field]: field === "cycles" || field === "seed" ? Number(value) : value,
    }));
  };

  const updateInitialState = (field: keyof SimulationScenarioCreate["initial_state"]) => (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const value = Number(event.target.value);
    setRunTargetSimulationId("");
    setForm((current) => ({
      ...current,
      initial_state: {
        ...current.initial_state,
        [field]: value,
      },
    }));
  };

  const updateAssayMeasurement = (field: keyof LabAssayMeasurements) => (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const rawValue = event.target.value;
    setRunTargetSimulationId("");
    setForm((current) => ({
      ...current,
      lab_assay_measurements: {
        ...(current.lab_assay_measurements ?? {}),
        [field]: rawValue === "" ? null : Number(rawValue),
      },
    }));
  };

  const loadHistory = useCallback(async (preferredSimulationId?: string) => {
    setIsLoadingHistory(true);
    try {
      const scenarioItems = await simulationLabApi.listScenarios({ limit: 8 });
      setScenarios(scenarioItems);
      const targetSimulationId = preferredSimulationId || scenarioItems[0]?.simulation_id || "";
      setHistoryScenarioId(targetSimulationId);
      const selectedScenario = preferredSimulationId
        ? scenarioItems.find((scenario) => scenario.simulation_id === preferredSimulationId)
        : undefined;
      if (selectedScenario) {
        setForm(formFromScenario(selectedScenario));
        setRunTargetSimulationId(selectedScenario.simulation_id);
      }
      if (targetSimulationId) {
        setRunHistory(await simulationLabApi.listRuns(targetSimulationId));
      } else {
        setRunHistory([]);
      }
    } catch {
      setRunHistory([]);
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory(urlSimulationId || undefined);
  }, [loadHistory, urlSimulationId]);

  useEffect(() => {
    setSelectedTwinCycleIndex(run?.cycles.length ? run.cycles.length - 1 : 0);
  }, [run?.summary.simulation_id, run?.cycles.length]);

  const changeHistoryScenario = async (event: ChangeEvent<HTMLSelectElement>) => {
    const nextSimulationId = event.target.value;
    setHistoryScenarioId(nextSimulationId);
    setRunTargetSimulationId(nextSimulationId);
    const selectedScenario = scenarios.find((scenario) => scenario.simulation_id === nextSimulationId);
    if (selectedScenario) {
      setForm(formFromScenario(selectedScenario));
    }
    setIsLoadingHistory(true);
    try {
      setRunHistory(nextSimulationId ? await simulationLabApi.listRuns(nextSimulationId) : []);
    } catch {
      setRunHistory([]);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const applyLabPreset = (preset: LabSimPreset) => {
    setRunTargetSimulationId("");
    setForm((current) => ({
      ...current,
      species: preset.species,
      feedstock: preset.feedstock,
      scenario: preset.scenario,
      policy: preset.policy,
      initial_state: preset.initial_state,
      lab_assay_measurements: null,
    }));
    setReferenceId(preset.id);
  };

  const runCurrentScenario = async () => {
    setIsRunning(true);
    let targetSimulationId = runTargetSimulationId;
    try {
      targetSimulationId = targetSimulationId || (await simulationLabApi.createScenario(form)).simulation_id;
      const nextRun = await simulationLabApi.runScenario(targetSimulationId);
      setRun(nextRun);
      setComparison(null);
      setRunTargetSimulationId(targetSimulationId);
      await loadHistory(targetSimulationId);
      toast.success("Simulation Lab run completed");
    } catch (error) {
      if (isSimulationLabDisabledError(error)) {
        const localRun = buildLocalReviewRun(
          form,
          activeLabPreset,
          targetSimulationId || `SIM-FRONTEND-${Date.now().toString(16).toUpperCase()}`,
        );
        setRun(localRun);
        setComparison(null);
        setRunTargetSimulationId(localRun.summary.simulation_id);
        setRunHistory([]);
        toast.success("Local review replay loaded; backend run remains disabled");
      } else {
        toast.error("Simulation Lab run failed");
      }
    } finally {
      setIsRunning(false);
    }
  };

  const submitScenario = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await runCurrentScenario();
  };

  const togglePolicy = (policy: SimulationPolicy) => {
    setSelectedPolicies((current) => {
      if (current.includes(policy)) {
        return current.length === 1 ? current : current.filter((item) => item !== policy);
      }
      return [...current, policy];
    });
  };

  const comparePolicies = async () => {
    const simulationId = run?.summary.simulation_id || historyScenarioId;
    if (!simulationId) {
      toast.error("Create or select a scenario before comparing policies");
      return;
    }
    setIsComparing(true);
    try {
      const nextComparison = await simulationLabApi.comparePolicies(simulationId, {
        baseline_policy: "rule_based",
        policies: selectedPolicies,
      });
      setComparison(nextComparison);
      await loadHistory(simulationId);
      toast.success("Policy comparison completed");
    } catch (error) {
      if (isSimulationLabDisabledError(error)) {
        toast.success("Policy comparison is unavailable; local review replay remains visible");
      } else {
        toast.error("Policy comparison failed");
      }
    } finally {
      setIsComparing(false);
    }
  };

  const importFromReference = async () => {
    if (!referenceId.trim()) {
      toast.error("Enter a reference id before importing");
      return;
    }
    setIsImportingReference(true);
    try {
      const imported = await simulationLabApi.importScenarioFromReference({
        reference_id: referenceId.trim(),
        policy: form.policy,
        cycles: form.cycles,
        seed: form.seed,
      });
      setImportResult(imported);
      setForm((current) => ({
        ...current,
        species: imported.scenario.species,
        feedstock: imported.scenario.feedstock,
        scenario: imported.scenario.scenario,
        initial_state: imported.scenario.initial_state,
        policy: imported.scenario.policy,
        cycles: imported.scenario.cycles,
        seed: imported.scenario.seed,
        lab_assay_measurements: imported.scenario.lab_assay_measurements,
      }));
      await loadHistory(imported.scenario.simulation_id);
      setRunTargetSimulationId(imported.scenario.simulation_id);
      toast.success("Reference scenario imported");
    } catch {
      toast.error("Reference import failed");
    } finally {
      setIsImportingReference(false);
    }
  };

  const exportRun = async () => {
    if (!run) return;
    setIsExporting(true);
    try {
      const blob = await simulationLabApi.exportRun(run.summary.simulation_id);
      downloadBlob(blob, `${run.summary.simulation_id}-simulation-audit.json`);
    } catch {
      toast.error("Simulation export failed");
    } finally {
      setIsExporting(false);
    }
  };

  const exportAppendix = async () => {
    const simulationId = run?.summary.simulation_id || historyScenarioId;
    if (!simulationId) {
      toast.error("Create or select a scenario before exporting an appendix");
      return;
    }
    setIsExportingAppendix(true);
    try {
      const blob = await simulationLabApi.exportReleaseAppendix(simulationId, "md");
      downloadBlob(blob, `${simulationId}-release-appendix.md`);
    } catch {
      toast.error("Simulation appendix export failed");
    } finally {
      setIsExportingAppendix(false);
    }
  };

  return (
    <div className="assistant-ambient-shell space-y-6">
      <div className="assistant-ambient-backdrop" aria-hidden="true">
        <span className="assistant-ambient-grid" />
        <span className="assistant-ambient-scan assistant-ambient-scan-a" />
        <span className="assistant-ambient-scan assistant-ambient-scan-b" />
      </div>

      <CockpitPanel tone="hero" className="p-6 lg:p-7">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-3xl">
              <CockpitSectionLabel>BOS Simulation Lab</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                Virtual closed-loop biowaste agent testbed
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                Run synthetic sensors, digital twin updates, supervisor decisions,
                virtual actuator effects, and audit evidence without touching production batches.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant={riskPosture.variant}>{riskPosture.label}</Badge>
              <Badge variant="info">Persisted v2.1</Badge>
              <Badge variant="brand">No hardware execution</Badge>
            </div>
          </div>

          <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-5">
            <CockpitMetric
              label="Scenario"
              value={run?.scenario.scenario.replace("_", " ") ?? form.scenario.replace("_", " ")}
              hint="Virtual batch condition"
              accent="cyan"
            />
            <CockpitMetric
              label="Cycles"
              value={String(run?.summary.cycle_count ?? form.cycles)}
              hint="Closed-loop iterations"
              accent="violet"
            />
            <CockpitMetric
              label="Ending risk"
              value={run ? formatPercent(run.summary.ending_risk, 1) : "Pending"}
              hint={run ? `Delta ${formatNumber(run.summary.risk_delta, 3)}` : "Deterministic proxy"}
              accent="amber"
            />
            <CockpitMetric
              label="Audit events"
              value={String(run?.summary.audit_event_count ?? 0)}
              hint="Cycle evidence records"
              accent="neutral"
            />
            <CockpitMetric
              label="Calibration"
              value={assayComparison ? assayComparison.calibration_status.replace(/_/g, " ") : "Pending"}
              hint={assayComparison ? "Prediction vs lab assay" : activeLabPreset.evidenceMode}
              accent="cyan"
            />
          </CockpitGrid>
        </div>
      </CockpitPanel>

      <CockpitPanel className="overflow-hidden p-5 lg:p-6">
        <CardHeader
          title="LabSim Twin Studio"
          description="Interactive factory-floor twin for choosing the lane, running the virtual experiment, and replaying cycle results."
          action={<Warehouse className="h-5 w-5 text-cyan-200" />}
        />
        <CardBody>
          <LabSimTwinStudio
            form={form}
            preset={activeLabPreset}
            presets={labSimPresets}
            scenarioOptions={scenarioOptions}
            policyOptions={policyOptions}
            run={run}
            cycle={selectedTwinCycle}
            selectedCycleIndex={selectedTwinCycleIndex}
            referenceId={referenceId}
            importResult={importResult}
            canExportAppendix={Boolean(run || historyScenarioId)}
            onSelectCycle={setSelectedTwinCycleIndex}
            onApplyPreset={applyLabPreset}
            onScenarioChange={(scenario) => {
              setRunTargetSimulationId("");
              setForm((current) => ({ ...current, scenario }));
            }}
            onPolicyChange={(policy) => {
              setRunTargetSimulationId("");
              setForm((current) => ({ ...current, policy }));
            }}
            onCyclesChange={(cycles) => {
              setRunTargetSimulationId("");
              setForm((current) => ({ ...current, cycles }));
            }}
            onSeedChange={(seed) => {
              setRunTargetSimulationId("");
              setForm((current) => ({ ...current, seed }));
            }}
            onReferenceIdChange={setReferenceId}
            onImportReference={() => void importFromReference()}
            onRunExperiment={() => void runCurrentScenario()}
            onExportAppendix={() => void exportAppendix()}
            isRunning={isRunning}
            isImportingReference={isImportingReference}
            isExportingAppendix={isExportingAppendix}
          />
        </CardBody>
      </CockpitPanel>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <CockpitPanel className="overflow-hidden p-5 lg:p-6">
          <CardHeader
            title="LabSim state-key laboratory map"
            description="Pixel-style digital twin shell for insect bioconversion lanes, assay governance, and controlled sample movement."
            action={<Microscope className="h-5 w-5 text-cyan-200" />}
          />
          <CardBody>
            <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="grid min-h-[23rem] grid-cols-4 gap-3 rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                {labStations.map((station) => (
                  <div
                    key={station.name}
                    className={[
                      "relative flex min-h-24 flex-col justify-between rounded-xl border p-3 shadow-inner",
                      station.className,
                      station.tone === "red"
                        ? "border-red-400/20 bg-red-500/10"
                        : station.tone === "amber"
                          ? "border-amber-300/20 bg-amber-400/10"
                          : station.tone === "emerald"
                            ? "border-emerald-300/20 bg-emerald-400/10"
                            : station.tone === "violet"
                              ? "border-violet-300/20 bg-violet-400/10"
                              : station.tone === "sky"
                                ? "border-sky-300/20 bg-sky-400/10"
                                : station.tone === "cyan"
                                  ? "border-cyan-300/20 bg-cyan-400/10"
                                  : "border-white/10 bg-white/[0.04]",
                    ].join(" ")}
                  >
                    <span className="text-[0.68rem] uppercase tracking-[0.16em] text-surface-500">controlled zone</span>
                    <span className="text-sm font-semibold text-white">{station.name}</span>
                    <span className="text-xs leading-5 text-surface-400">{station.detail}</span>
                  </div>
                ))}
              </div>

              <div className="space-y-4">
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-surface-500">Experiment passport</p>
                      <h2 className="mt-2 text-lg font-semibold text-white">{activeLabPreset.label}</h2>
                    </div>
                    <Badge variant={activeLabPreset.id.includes("sludge") ? "danger" : "info"}>
                      {activeLabPreset.shortLabel}
                    </Badge>
                  </div>
                  <div className="mt-4 grid gap-3 text-sm">
                    <TraceRow label="Review status" value={activeLabPreset.reviewStatus} />
                    <TraceRow label="Containment" value={activeLabPreset.containment} />
                    <TraceRow label="Product lock" value={activeLabPreset.productLock} />
                    <TraceRow label="Evidence mode" value={activeLabPreset.evidenceMode} />
                  </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <p className="text-xs uppercase tracking-[0.18em] text-surface-500">Heavy-metal gate</p>
                    <ShieldAlert className="h-4 w-4 text-amber-200" />
                  </div>
                  <HeavyMetalGate metals={activeLabPreset.heavyMetals} />
                  <p className="mt-4 text-xs leading-6 text-surface-400">
                    Sludge and manure routes stay review-gated. Simulation output is evidence for human review, not a
                    validated product-use decision.
                  </p>
                </div>
              </div>
            </div>
          </CardBody>
        </CockpitPanel>

        <CockpitPanel className="p-5 lg:p-6">
          <CardHeader
            title="Species and feedstock lanes"
            description="Load a governed experimental seed before running the virtual closed loop."
            action={<Bug className="h-5 w-5 text-emerald-200" />}
          />
          <CardBody>
            <div className="grid gap-3">
              {labSimPresets.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => applyLabPreset(preset)}
                  className={[
                    "rounded-2xl border p-4 text-left transition hover:bg-white/[0.07]",
                    activeLabPreset.id === preset.id
                      ? "border-brand-300/40 bg-brand-400/10"
                      : "border-white/10 bg-white/[0.04]",
                  ].join(" ")}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-white">{preset.label}</span>
                    <Badge variant={preset.id.includes("sludge") ? "danger" : "neutral"}>{preset.shortLabel}</Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {preset.notes.map((note) => (
                      <span
                        key={note}
                        className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-surface-300"
                      >
                        {note}
                      </span>
                    ))}
                  </div>
                </button>
              ))}
            </div>
          </CardBody>
        </CockpitPanel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <CockpitPanel className="p-5 lg:p-6">
          <CardHeader
            title="Advanced scenario parameters"
            description="Detailed state and assay controls for operators who need to override the Twin Studio defaults."
            action={<FlaskConical className="h-5 w-5 text-sky-200" />}
          />
          <CardBody>
            <form onSubmit={submitScenario} className="grid gap-4 md:grid-cols-2" noValidate>
              <Input label="Species" value={form.species} onChange={updateField("species")} />
              <Input label="Feedstock" value={form.feedstock} onChange={updateField("feedstock")} />
              <Select
                label="Scenario"
                options={scenarioOptions}
                value={form.scenario}
                onChange={(event) => {
                  setRunTargetSimulationId("");
                  setForm((current) => ({ ...current, scenario: event.target.value as SimulationScenario }));
                }}
              />
              <Input label="Seed" type="number" value={form.seed} onChange={updateField("seed")} />
              <Input label="Cycles" type="number" min={5} max={24} value={form.cycles} onChange={updateField("cycles")} />
              <Input label="Biomass" type="number" step="0.1" value={form.initial_state.biomass} onChange={updateInitialState("biomass")} />
              <Input label="Substrate" type="number" step="0.1" value={form.initial_state.substrate} onChange={updateInitialState("substrate")} />
              <Input label="Temperature" type="number" step="0.1" value={form.initial_state.temperature} onChange={updateInitialState("temperature")} />
              <Input label="Moisture" type="number" step="0.1" value={form.initial_state.moisture} onChange={updateInitialState("moisture")} />
              <Input label="Nitrogen" type="number" step="0.1" value={form.initial_state.nitrogen} onChange={updateInitialState("nitrogen")} />
              <div className="md:col-span-2">
                <p className="text-xs uppercase tracking-[0.18em] text-surface-500">Optional measured assay anchors</p>
                <p className="mt-1 text-xs leading-6 text-surface-400">
                  Operator-entered or reference-imported lab measurements override profile anchors and remain review-gated evidence.
                </p>
              </div>
              <Input
                label="Measured biomass"
                type="number"
                step="0.01"
                value={form.lab_assay_measurements?.biomass ?? ""}
                onChange={updateAssayMeasurement("biomass")}
              />
              <Input
                label="Measured substrate"
                type="number"
                step="0.01"
                value={form.lab_assay_measurements?.substrate ?? ""}
                onChange={updateAssayMeasurement("substrate")}
              />
              <Input
                label="Measured moisture"
                type="number"
                step="0.1"
                min={0}
                max={100}
                value={form.lab_assay_measurements?.moisture ?? ""}
                onChange={updateAssayMeasurement("moisture")}
              />
              <Input
                label="Measured HM index"
                type="number"
                step="0.01"
                min={0}
                max={1}
                value={form.lab_assay_measurements?.heavy_metal_index ?? ""}
                onChange={updateAssayMeasurement("heavy_metal_index")}
              />
              <div className="flex items-end gap-3 md:col-span-2">
                <Button type="submit" loading={isRunning} leftIcon={<Play className="h-4 w-4" />}>
                  Run virtual loop
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!run}
                  loading={isExporting}
                  leftIcon={<Download className="h-4 w-4" />}
                  onClick={exportRun}
                >
                  Export audit JSON
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!run && !historyScenarioId}
                  loading={isExportingAppendix}
                  leftIcon={<Download className="h-4 w-4" />}
                  onClick={() => void exportAppendix()}
                >
                  Export release appendix
                </Button>
              </div>
            </form>
          </CardBody>
        </CockpitPanel>

        <CockpitPanel className="p-5 lg:p-6">
          <CardHeader
            title="Import from reference"
            description="Seed a persisted scenario from staged, promoted, or manuscript reference data."
            action={<Download className="h-5 w-5 text-emerald-200" />}
          />
          <CardBody>
            <div className="grid gap-4">
              <Input
                label="Reference ID"
                value={referenceId}
                onChange={(event) => setReferenceId(event.target.value)}
              />
              <div className="flex flex-wrap gap-3">
                <Button
                  type="button"
                  variant="secondary"
                  loading={isImportingReference}
                  leftIcon={<Download className="h-4 w-4" />}
                  onClick={() => void importFromReference()}
                >
                  Import reference seed
                </Button>
              </div>
              {importResult ? (
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm text-surface-300">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <span className="font-medium text-white">{importResult.import_metadata.source_title}</span>
                    <Badge variant="info">{formatPercent(importResult.import_metadata.extraction_confidence, 0)}</Badge>
                  </div>
                  <p className="mt-3 text-xs leading-6 text-surface-400">
                    Source {importResult.import_metadata.reference_source}; fallbacks {importResult.import_metadata.fallbacks.length}
                  </p>
                  <p className="mt-2 text-xs leading-6 text-surface-300">
                    Review {importResult.import_metadata.review_status}; numeric values{" "}
                    {importResult.import_metadata.numeric_values_included ? "included" : "not exposed"}; release evidence{" "}
                    {importResult.import_metadata.release_evidence_allowed ? "allowed" : "blocked"}
                  </p>
                  <p className="text-xs leading-6 text-surface-500">
                    Runtime activation {importResult.import_metadata.runtime_activation_enabled ? "enabled" : "blocked"};
                    validated defaults {importResult.import_metadata.validated_default_write_enabled ? "write enabled" : "locked"}
                  </p>
                  {importResult.scenario.lab_assay_measurements ? (
                    <div className="mt-2 space-y-1 text-xs leading-6 text-emerald-100">
                      <p>
                        Imported assay anchors: {Object.entries(importResult.scenario.lab_assay_measurements)
                          .filter(([, value]) => value !== null && value !== undefined)
                          .map(([field, value]) => `${field} ${formatNumber(Number(value), 3)}`)
                          .join(" / ")}
                      </p>
                      <p className="text-surface-300">
                        Evidence mode {importedAssaySource?.measurement_mode ?? "reference_imported"}; review{" "}
                        {importedAssaySource?.review_status ?? "pending_review"}
                      </p>
                    </div>
                  ) : null}
                </div>
              ) : (
                <EmptyTraceState label="Import a reference to preview extracted scenario assumptions." />
              )}
            </div>
          </CardBody>
        </CockpitPanel>

        <CockpitPanel className="p-5 lg:p-6">
          <CardHeader
            title="Run summary"
            description={run ? run.summary.simulation_id : "No run has been executed in this browser session."}
            action={<Gauge className="h-5 w-5 text-amber-200" />}
          />
          <CardBody>
            {run ? (
              <div className="grid gap-4 md:grid-cols-2">
                <TraceMetric label="Starting risk" value={formatPercent(run.summary.starting_risk, 1)} />
                <TraceMetric label="Ending risk" value={formatPercent(run.summary.ending_risk, 1)} />
                <TraceMetric label="Action count" value={String(run.summary.action_count)} />
                <TraceMetric label="Audit completeness" value={formatPercent(run.summary.audit_event_count / run.summary.cycle_count, 0)} />
                <TraceMetric label="Final biomass" value={formatNumber(run.summary.final_state.biomass, 3)} />
                <TraceMetric label="Final substrate" value={formatNumber(run.summary.final_state.substrate, 3)} />
              </div>
            ) : (
              <EmptyTraceState />
            )}
          </CardBody>
        </CockpitPanel>
      </div>

      <CockpitPanel className="p-5 lg:p-6">
        <CardHeader
          title="Run history"
          description="Persisted scenarios and latest run summaries for this tenant."
          action={<History className="h-5 w-5 text-sky-200" />}
        />
        <CardBody>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="w-full max-w-xl">
              <Select
                label="Scenario"
                placeholder="No persisted scenarios"
                options={scenarios.map((scenario) => ({
                  value: scenario.simulation_id,
                  label: `${scenario.simulation_id} - ${scenario.scenario.replace("_", " ")}`,
                }))}
                value={historyScenarioId}
                onChange={changeHistoryScenario}
              />
            </div>
            <Button
              type="button"
              variant="secondary"
              loading={isLoadingHistory}
              leftIcon={<RefreshCw className="h-4 w-4" />}
              onClick={() => void loadHistory(historyScenarioId)}
            >
              Refresh history
            </Button>
          </div>
          {runHistory.length ? (
            <div className="mt-5 overflow-hidden rounded-2xl border border-white/10">
              <table className="w-full text-left text-sm">
                <thead className="bg-white/6 text-xs uppercase tracking-[0.18em] text-surface-400">
                  <tr>
                    <th className="px-4 py-3">Run</th>
                    <th className="px-4 py-3">Policy</th>
                    <th className="px-4 py-3">Cycles</th>
                    <th className="px-4 py-3">Risk delta</th>
                    <th className="px-4 py-3">Audit events</th>
                    <th className="px-4 py-3">Completed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/8">
                  {runHistory.map((item) => (
                    <tr key={item.run_id} className="text-surface-200">
                      <td className="px-4 py-3 font-medium text-white">{item.run_id}</td>
                      <td className="px-4 py-3">{formatPolicy(item.policy)}</td>
                      <td className="px-4 py-3">{item.cycle_count}</td>
                      <td className="px-4 py-3">{formatNumber(item.risk_delta, 3)}</td>
                      <td className="px-4 py-3">{item.audit_event_count}</td>
                      <td className="px-4 py-3">
                        {item.completed_at ? new Date(item.completed_at).toLocaleString() : item.status}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="mt-5">
              <EmptyTraceState />
            </div>
          )}
        </CardBody>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <CardHeader
          title="Policy comparison"
          description="Run multiple virtual policies from the same persisted scenario seed."
          action={<Gauge className="h-5 w-5 text-violet-200" />}
        />
        <CardBody>
          <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {policyOptions.map((policy) => (
                <label
                  key={policy.value}
                  className="flex min-h-12 items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-surface-200"
                >
                  <input
                    type="checkbox"
                    checked={selectedPolicies.includes(policy.value)}
                    onChange={() => togglePolicy(policy.value)}
                    className="h-4 w-4 rounded border-white/20 bg-white/10 text-brand-400"
                  />
                  <span>{policy.label}</span>
                </label>
              ))}
            </div>
            <Button
              type="button"
              loading={isComparing}
              disabled={!run && !historyScenarioId}
              leftIcon={<Play className="h-4 w-4" />}
              onClick={() => void comparePolicies()}
            >
              Compare policies
            </Button>
          </div>
          <p className="mt-4 text-xs leading-6 text-surface-400">
            Simulation appendix is review evidence only; it does not change release decisions.
          </p>

          {comparison ? (
            <div className="mt-5 space-y-4">
              <div className="grid gap-3 md:grid-cols-3">
                <TraceMetric label="Lowest risk" value={comparison.winner.lowest_risk ? formatPolicy(comparison.winner.lowest_risk) : "n/a"} />
                <TraceMetric label="Highest biomass gain" value={comparison.winner.highest_biomass_gain ? formatPolicy(comparison.winner.highest_biomass_gain) : "n/a"} />
                <TraceMetric label="Fewest interventions" value={comparison.winner.fewest_interventions ? formatPolicy(comparison.winner.fewest_interventions) : "n/a"} />
              </div>
              <div className="overflow-hidden rounded-2xl border border-white/10">
                <table className="w-full text-left text-sm">
                  <thead className="bg-white/6 text-xs uppercase tracking-[0.18em] text-surface-400">
                    <tr>
                      <th className="px-4 py-3">Policy</th>
                      <th className="px-4 py-3">Risk delta</th>
                      <th className="px-4 py-3">Biomass gain</th>
                      <th className="px-4 py-3">Substrate use</th>
                      <th className="px-4 py-3">Interventions</th>
                      <th className="px-4 py-3">Human reviews</th>
                    <th className="px-4 py-3">Audit completeness</th>
                    <th className="px-4 py-3">Energy</th>
                    <th className="px-4 py-3">CO2e</th>
                    <th className="px-4 py-3">Margin</th>
                    <th className="px-4 py-3">Release</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/8">
                    {comparison.runs.map((item) => (
                      <tr key={item.run_id} className="text-surface-200">
                        <td className="px-4 py-3 font-medium text-white">{formatPolicy(item.policy)}</td>
                        <td className="px-4 py-3">{formatNumber(item.metrics.risk_delta, 3)}</td>
                        <td className="px-4 py-3">{formatNumber(item.metrics.biomass_gain, 3)}</td>
                        <td className="px-4 py-3">{formatNumber(item.metrics.substrate_use, 3)}</td>
                        <td className="px-4 py-3">{item.metrics.intervention_count}</td>
                        <td className="px-4 py-3">{item.metrics.human_review_count}</td>
                        <td className="px-4 py-3">{formatPercent(item.metrics.audit_completeness, 0)}</td>
                        <td className="px-4 py-3">{formatNumber(item.metrics.energy_kwh_estimate, 3)} kWh</td>
                        <td className="px-4 py-3">{formatNumber(item.metrics.co2e_estimate, 3)} kg</td>
                        <td className="px-4 py-3">{formatNumber(item.metrics.gross_margin_estimate, 2)}</td>
                        <td className="px-4 py-3">{item.metrics.release_readiness.replace("_", " ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="mt-5">
              <EmptyTraceState label="Run a comparison to populate policy metrics." />
            </div>
          )}
        </CardBody>
      </CockpitPanel>

      <div className="grid gap-6 xl:grid-cols-5">
        <TracePanel
          title="Sensor stream"
          icon={<RadioTower className="h-5 w-5 text-sky-200" />}
          rows={lastCycle ? [
            ["Temperature", `${lastCycle.sensor_observation.temperature} C`],
            ["Moisture", `${lastCycle.sensor_observation.moisture}%`],
            ["pH", String(lastCycle.sensor_observation.ph)],
            ["DO", String(lastCycle.sensor_observation.do)],
            ["CO2", String(lastCycle.sensor_observation.co2)],
            ["NH3", String(lastCycle.sensor_observation.nh3)],
            ["Weight", String(lastCycle.sensor_observation.weight)],
          ] : []}
        />
        <TracePanel
          title="Twin trajectory"
          icon={<Activity className="h-5 w-5 text-violet-200" />}
          rows={lastCycle ? [
            ["Biomass", formatNumber(lastCycle.state_after.biomass, 3)],
            ["Substrate", formatNumber(lastCycle.state_after.substrate, 3)],
            ["Temperature", formatNumber(lastCycle.state_after.temperature, 2)],
            ["Moisture", formatNumber(lastCycle.state_after.moisture, 2)],
            ["Nitrogen", formatNumber(lastCycle.state_after.nitrogen, 2)],
          ] : []}
        />
        <TracePanel
          title="Agent action trace"
          icon={<Play className="h-5 w-5 text-emerald-200" />}
          rows={lastCycle ? [
            ["Action", lastCycle.agent_action.recommended_action],
            ["Intensity", formatNumber(lastCycle.agent_action.intensity, 2)],
            ["Confidence", formatPercent(lastCycle.agent_action.confidence, 1)],
            ["Risk reduction", formatNumber(lastCycle.agent_action.expected_risk_reduction, 3)],
            ["Reason", lastCycle.agent_action.reason_codes.join(", ")],
            ["Status", lastCycle.actuator_result.status],
          ] : []}
        />
        <TracePanel
          title="Visual observation"
          icon={<Image className="h-5 w-5 text-amber-200" />}
          rows={lastCycle?.visual_observation ? [
            ["Frame", lastCycle.visual_observation.frame_id],
            ["Source", lastCycle.visual_observation.source],
            ["Source kind", lastCycle.evidence_sources.find((source) => source.field === "visual_observation")?.source_kind ?? "synthetic"],
            ["Labels", lastCycle.visual_observation.anomaly_labels.join(", ")],
            ["Confidence", formatPercent(lastCycle.visual_observation.confidence, 1)],
            ["Ultralytics", lastCycle.visual_observation.ultralytics_dry_run ? "dry run" : "live"],
            ["Camera", lastCycle.visual_observation.hardware_camera_used ? "hardware" : "synthetic"],
          ] : []}
        />
        <TracePanel
          title="Assay calibration"
          icon={<Microscope className="h-5 w-5 text-cyan-200" />}
          rows={assayComparison ? [
            ["Status", assayComparison.calibration_status.replace(/_/g, " ")],
            ["Source", assayComparison.source_ref],
            [
              "Biomass",
              `${formatNumber(assayComparison.predicted.biomass, 3)} vs ${formatNumber(assayComparison.measured_anchor.biomass, 3)}`,
            ],
            [
              "Substrate",
              `${formatNumber(assayComparison.predicted.substrate, 3)} vs ${formatNumber(assayComparison.measured_anchor.substrate, 3)}`,
            ],
            [
              "Moisture",
              `${formatNumber(assayComparison.predicted.moisture, 2)} vs ${formatNumber(assayComparison.measured_anchor.moisture, 2)}`,
            ],
            [
              "HM index",
              `${formatNumber(assayComparison.predicted.heavy_metal_index, 2)} vs ${formatNumber(assayComparison.measured_anchor.heavy_metal_index, 2)}`,
            ],
          ] : []}
        />
      </div>

      <CockpitPanel className="p-5 lg:p-6">
        <CardHeader
          title="Audit trace"
          description="Cycle-level evidence chain for export and handoff review."
          action={<ScrollText className="h-5 w-5 text-surface-200" />}
        />
        <CardBody>
          {run ? (
            <div className="overflow-hidden rounded-2xl border border-white/10">
              <table className="w-full text-left text-sm">
                <thead className="bg-white/6 text-xs uppercase tracking-[0.18em] text-surface-400">
                  <tr>
                    <th className="px-4 py-3">Cycle</th>
                    <th className="px-4 py-3">Risk</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Supervisor</th>
                    <th className="px-4 py-3">Evidence</th>
                    <th className="px-4 py-3">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/8">
                  {run.cycles.map((cycle) => (
                    <tr key={cycle.cycle} className="text-surface-200">
                      <td className="px-4 py-3 font-medium text-white">{cycle.cycle}</td>
                      <td className="px-4 py-3">{formatPercent(cycle.risk_prediction.future_risk_score, 1)}</td>
                      <td className="px-4 py-3">{cycle.agent_action.recommended_action}</td>
                      <td className="px-4 py-3">
                        {cycle.supervisor_decision.recommended_handover ? "handover" : "continue"}
                      </td>
                      <td className="px-4 py-3">
                        {Array.isArray(cycle.audit_event.evidence_chain)
                          ? cycle.audit_event.evidence_chain.join(" > ")
                          : "recorded"}
                      </td>
                      <td className="px-4 py-3">
                        {cycle.evidence_sources.map((source) => `${source.field}:${source.source_kind}`).join(", ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyTraceState />
          )}
        </CardBody>
      </CockpitPanel>
    </div>
  );
}

function TraceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-surface-400">{label}</span>
      <span className="max-w-[18rem] text-right font-medium text-white">{value}</span>
    </div>
  );
}

function HeavyMetalGate({ metals }: { metals: Record<HeavyMetalKey, number> }) {
  return (
    <div className="space-y-3">
      {Object.entries(metals).map(([metal, value]) => {
        const posture = value >= 0.68 ? "redline" : value >= 0.35 ? "review" : "screened";
        return (
          <div key={metal} className="grid grid-cols-[2.5rem_1fr_4.5rem] items-center gap-3 text-xs">
            <span className="font-semibold text-white">{metal}</span>
            <span className="h-2 overflow-hidden rounded-full bg-white/10">
              <span
                className={[
                  "block h-full rounded-full",
                  value >= 0.68 ? "bg-red-300" : value >= 0.35 ? "bg-amber-300" : "bg-emerald-300",
                ].join(" ")}
                style={{ width: `${Math.round(value * 100)}%` }}
              />
            </span>
            <span className={value >= 0.68 ? "text-red-200" : value >= 0.35 ? "text-amber-200" : "text-emerald-200"}>
              {posture}
            </span>
          </div>
        );
      })}
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

function TracePanel({
  title,
  icon,
  rows,
}: {
  title: string;
  icon: ReactNode;
  rows: Array<[string, string]>;
}) {
  return (
    <CockpitPanel className="p-5 lg:p-6">
      <CardHeader title={title} action={icon} />
      <CardBody>
        {rows.length ? (
          <div className="space-y-3">
            {rows.map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-4 text-sm">
                <span className="text-surface-400">{label}</span>
                <span className="max-w-[12rem] truncate font-medium text-white">{value}</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyTraceState />
        )}
      </CardBody>
    </CockpitPanel>
  );
}

function EmptyTraceState({ label = "Run a virtual loop to populate this panel." }: { label?: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-5 text-sm text-surface-400">
      {label}
    </div>
  );
}
