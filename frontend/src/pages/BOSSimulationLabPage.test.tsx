/**
 * @vitest-environment jsdom
 */

import { act } from "react";
import { Simulate } from "react-dom/test-utils";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import toast from "react-hot-toast";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { simulationLabApi } from "@/api/simulationLabApi";
import BOSSimulationLabPage from "@/pages/BOSSimulationLabPage";
import type { SimulationLabRunResponse, SimulationScenarioResponse } from "@/types/simulationLab";

vi.mock("react-hot-toast", () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/api/simulationLabApi", () => ({
  simulationLabApi: {
    createScenario: vi.fn(),
    importScenarioFromReference: vi.fn(),
    listScenarios: vi.fn(),
    runScenario: vi.fn(),
    comparePolicies: vi.fn(),
    listRuns: vi.fn(),
    getCycles: vi.fn(),
    getAuditTrace: vi.fn(),
    getEvidenceSources: vi.fn(),
    exportRun: vi.fn(),
    getReleaseAppendix: vi.fn(),
    exportReleaseAppendix: vi.fn(),
    replayRun: vi.fn(),
    diffRuns: vi.fn(),
  },
}));

const scenarioFixture: SimulationScenarioResponse = {
  simulation_id: "SIM-X",
  batch_id: "BATCH-SIM-X",
  tenant_id: 1,
  species: "BSF",
  feedstock: "mixed_food_waste",
  scenario: "moisture_drift",
  initial_state: {
    biomass: 0.5,
    substrate: 10,
    temperature: 28,
    moisture: 70,
    nitrogen: 50,
  },
  cycles: 8,
  seed: 17,
  policy: "rule_based",
  status: "created",
  created_at: "2026-04-24T00:00:00Z",
  evidence_sources: [],
};

function runFixture(scenario: SimulationScenarioResponse): SimulationLabRunResponse {
  return {
    scenario,
    summary: {
      simulation_id: scenario.simulation_id,
      cycle_count: scenario.cycles,
      scenario: scenario.scenario,
      policy: scenario.policy,
      starting_risk: 0.6,
      ending_risk: 0.35,
      risk_delta: -0.25,
      action_count: 2,
      audit_event_count: scenario.cycles,
      final_state: { ...scenario.initial_state },
    },
    cycles: [
      {
        cycle: 1,
        timestamp: "2026-04-24T00:00:00Z",
        state_before: { ...scenario.initial_state },
        sensor_observation: {
          temperature: 28,
          moisture: 70,
          ph: 7,
          do: 6,
          co2: 720,
          nh3: 2.1,
          weight: 1.2,
        },
        supervisor_decision: { recommended_handover: false },
        risk_prediction: {
          future_risk_score: 0.35,
          release_warning_score: 0.42,
          forecast_window: "next_6_cycles",
          model_name: "simulation_lab_deterministic_proxy",
          driver_features: {},
          lab_assay_comparison: {
            source_kind: "manuscript_campaign",
            source_ref: "labsim_assay_anchor:bsf_sludge_heavy_metal_redline",
            review_status: "human_review_required",
            measurement_mode: "profile_anchor",
            predicted: {
              biomass: 0.71,
              substrate: 3.8,
              moisture: 74.2,
              heavy_metal_index: 0.82,
            },
            measured_anchor: {
              biomass: 0.72,
              substrate: 3.85,
              moisture: 74,
              heavy_metal_index: 0.82,
            },
            residuals: {
              biomass: -0.01,
              substrate: -0.05,
              moisture: 0.2,
              heavy_metal_index: 0,
            },
            out_of_band: [],
            calibration_status: "review_required",
          },
        },
        visual_observation: null,
        evidence_sources: [],
        agent_action: {
          policy: scenario.policy,
          recommended_action: "request_human_review",
          intensity: 1,
          duration_minutes: 5,
          reason_codes: ["heavy_metal_gate"],
          confidence: 0.8,
          expected_risk_reduction: 0.1,
        },
        actuator_result: {
          action: "request_human_review",
          status: "review_requested",
          expected_effect: {},
          actual_effect: {},
          hardware_execution: false,
        },
        state_after: { ...scenario.initial_state },
        audit_event: {},
      },
    ],
  };
}

function renderInteractive() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => {
    root.render(<BOSSimulationLabPage />);
  });
  return { container, root };
}

async function flushAsyncWork() {
  await act(async () => {
    await Promise.resolve();
  });
}

function buttonByText(container: HTMLElement, text: string): HTMLButtonElement {
  const button = Array.from(container.querySelectorAll("button")).find((item) =>
    item.textContent?.includes(text),
  );
  if (!button) throw new Error(`Button not found: ${text}`);
  return button as HTMLButtonElement;
}

describe("BOSSimulationLabPage", () => {
  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    vi.mocked(simulationLabApi.createScenario).mockReset();
    vi.mocked(simulationLabApi.runScenario).mockReset();
    vi.mocked(simulationLabApi.listScenarios).mockReset();
    vi.mocked(simulationLabApi.listRuns).mockReset();
    vi.mocked(toast.success).mockReset();
    vi.mocked(toast.error).mockReset();
    window.history.replaceState(null, "", "/");
    vi.mocked(simulationLabApi.listScenarios).mockResolvedValue([scenarioFixture]);
    vi.mocked(simulationLabApi.listRuns).mockResolvedValue([]);
    vi.mocked(simulationLabApi.runScenario).mockResolvedValue(runFixture(scenarioFixture));
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("renders scenario setup, run summary, timeline panels, and audit trace", () => {
    const html = renderToStaticMarkup(<BOSSimulationLabPage />);

    expect(html).toContain("BOS Simulation Lab");
    expect(html).toContain("Virtual closed-loop biowaste agent testbed");
    expect(html).toContain("LabSim Twin Studio");
    expect(html).toContain("Interactive factory-floor twin");
    expect(html).toContain("Experiment replay");
    expect(html).toContain("Experiment goal");
    expect(html).toContain("Organism");
    expect(html).toContain("BSF larvae");
    expect(html).toContain("Feedstock");
    expect(html).toContain("Distillers grain");
    expect(html).toContain("What the replay is doing");
    expect(html).toContain("Feedstock intake");
    expect(html).toContain("Larvae conversion bay");
    expect(html).toContain("3D Lab Twin");
    expect(html).toContain("Lab view mode");
    expect(html).toContain("Realistic Lab / Gaussian Splat");
    expect(html).toContain("Digital Twin");
    expect(html).toContain("Splat proof layer");
    expect(html).toContain("Three.js scene");
    expect(html).toContain("labsim-3d-station-marker-reactor");
    expect(html).toContain("labsim-3d-station-label-reactor");
    expect(html).toContain("Experiment phase");
    expect(html).toContain("Material flow");
    expect(html).toContain("Replay tour");
    expect(html).toContain("labsim-3d-phase-rail");
    expect(html).toContain("Lab assistant command");
    expect(html).toContain("Say one sentence and the bench demonstrates the operation.");
    expect(html).toContain("Demonstrate intake to reactor route");
    expect(html).toContain("Run virtual experiment and show assay bench");
    expect(html).toContain("Visual replay only");
    expect(html).toContain("Loading demo splat");
    expect(html).toContain("local demo PLY placeholder");
    expect(html).toContain("Studio control");
    expect(html).toContain("Run this review-only replay after the route is clear.");
    expect(html).toContain("Run experiment");
    expect(html).toContain("Route");
    expect(html).toContain("Policy");
    expect(html).toContain("Import reference");
    expect(html).toContain("Twin proof rail");
    expect(html).toContain("Reference seed");
    expect(html).toContain("Run proof");
    expect(html).toContain("Assay proof");
    expect(html).toContain("Cycle playback");
    expect(html).toContain("Twin boundary");
    expect(html).toContain("Selected station");
    expect(html).toContain("Station operations");
    expect(html).toContain("Station workflow");
    expect(html).toContain("Run experiment to generate cycle proof.");
    expect(html).toContain("Twin output is evidence for review and does not mutate runtime state.");
    expect(html).toContain("Evidence source");
    expect(html).toContain("Guardrail");
    expect(html).toContain("Click stations");
    expect(html).toContain("Batch flow");
    expect(html).toContain("Sensor heat");
    expect(html).toContain("Cycle telemetry overlay");
    expect(html).toContain("Risk score");
    expect(html).toContain("Supervisor");
    expect(html).toContain("route selected");
    expect(html).toContain("standby");
    expect(html).toContain("LabSim state-key laboratory map");
    expect(html).toContain("Experiment passport");
    expect(html).toContain("Heavy-metal gate");
    expect(html).toContain("BSF sludge heavy-metal redline lane");
    expect(html).toContain("Advanced scenario parameters");
    expect(html).toContain("Import from reference");
    expect(html).toContain("Import reference seed");
    expect(html).toContain("Run summary");
    expect(html).toContain("Run history");
    expect(html).toContain("Policy comparison");
    expect(html).toContain("Compare policies");
    expect(html).toContain("Export release appendix");
    expect(html).toContain("does not change release decisions");
    expect(html).toContain("Persisted v2.1");
    expect(html).toContain("Sensor stream");
    expect(html).toContain("Twin trajectory");
    expect(html).toContain("Agent action trace");
    expect(html).toContain("Visual observation");
    expect(html).toContain("Assay calibration");
    expect(html).toContain("Audit trace");
    expect(html).toContain("Run virtual loop");
  });

  it("lets operators inspect stations in the twin studio scene", async () => {
    const { container, root } = renderInteractive();
    await flushAsyncWork();

    expect(container.textContent).toContain("Twin reactor state");
    expect(container.textContent).toContain("Realistic Lab / Gaussian Splat");
    expect(container.textContent).toContain("Digital Twin");
    expect(container.querySelector('[data-testid="labsim-gaussian-splat-stage"]')).not.toBeNull();
    await act(async () => {
      buttonByText(container, "Digital Twin").click();
    });
    expect(container.querySelector('[data-testid="labsim-3d-twin"]')).not.toBeNull();
    await act(async () => {
      buttonByText(container, "Realistic Lab / Gaussian Splat").click();
    });
    expect(container.querySelector('[data-testid="labsim-gaussian-splat-stage"]')).not.toBeNull();
    expect(container.querySelectorAll('[data-testid^="labsim-3d-station-marker-"]')).toHaveLength(9);
    expect(container.querySelectorAll('[data-testid^="labsim-3d-station-label-"]').length).toBeGreaterThanOrEqual(1);
    expect(container.querySelectorAll('[data-testid^="labsim-3d-station-label-"]').length).toBeLessThanOrEqual(2);
    expect(container.querySelector('[data-testid="labsim-experiment-overview"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="labsim-organism-visual"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="labsim-feedstock-visual"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="labsim-experiment-timeline"]')).not.toBeNull();
    expect(container.textContent).toContain("Experiment phase");
    expect(container.textContent).toContain("Material flow");
    expect(container.textContent).toContain("Replay tour");
    expect(container.querySelector('[data-testid="labsim-3d-phase-rail"]')).not.toBeNull();

    await act(async () => {
      buttonByText(container, "Assay bench").click();
    });

    expect(container.textContent).toContain("Selected station");
    expect(container.textContent).toContain("Measured or reference-imported assay anchors");
    expect(container.textContent).toContain("Station operations");
    expect(container.textContent).toContain("Station workflow");
    expect(container.textContent).toContain("Assay evidence");
    expect(container.textContent).toContain("No promotion");
    expect(container.textContent).toContain("Review evidence only; no runtime activation");

    await act(async () => {
      buttonByText(container, "Focus larvae tray rack").click();
    });

    expect(container.querySelector('[data-testid="labsim-3d-assistant-cue"]')).not.toBeNull();
    expect(container.textContent).toContain("Larvae tray rack demonstration");
    expect(container.textContent).toContain("The tray rack is selected");
    expect(container.textContent).toContain("Lab assistant demo");

    act(() => root.unmount());
  });

  it("exposes cycle step controls after a twin run completes", async () => {
    vi.mocked(simulationLabApi.createScenario).mockResolvedValue(scenarioFixture);
    const { container, root } = renderInteractive();
    await flushAsyncWork();

    await act(async () => {
      buttonByText(container, "Run experiment").click();
    });
    await flushAsyncWork();

    expect(container.textContent).toContain("Previous cycle");
    expect(container.textContent).toContain("Next cycle");
    expect(container.textContent).toContain("Cycle risk");
    expect(container.textContent).toContain("Replay seed");
    expect(container.textContent).toContain("Cycle telemetry overlay");
    expect(container.textContent).toContain("request human review");
    expect(container.textContent).toContain("NH3");
    const overlay = container.querySelector('[data-testid="cycle-telemetry-overlay"]');
    expect(overlay?.textContent).toContain("cycle 1");
    expect(overlay?.textContent).toContain("35.0%");
    expect(overlay?.textContent).toContain("28.0 C");
    expect(overlay?.textContent).toContain("70.0 %");
    expect(overlay?.textContent).toContain("2.10");
    expect(overlay?.textContent).toContain("request human review");
    expect(overlay?.textContent).not.toContain("standby");

    act(() => root.unmount());
  });

  it("falls back to a local review replay when the backend simulation flag is disabled", async () => {
    vi.mocked(simulationLabApi.createScenario).mockRejectedValue({
      response: { data: { detail: "bos_simulation_lab_disabled" } },
    });
    const { container, root } = renderInteractive();
    await flushAsyncWork();

    await act(async () => {
      buttonByText(container, "Run experiment").click();
    });
    await flushAsyncWork();

    expect(container.textContent).toContain("Cycle playback");
    expect(container.textContent).toContain("frontend review preview");
    expect(container.textContent).toContain("frontend_only_review_replay");
    expect(container.textContent).not.toContain("Simulation Lab flag is disabled");
    expect(toast.error).not.toHaveBeenCalledWith("Simulation Lab flag is disabled");
    expect(toast.success).toHaveBeenCalledWith("Local review replay loaded; backend run remains disabled");
    act(() => root.unmount());
  });

  it("reruns the URL-selected scenario without creating a new scenario", async () => {
    window.history.replaceState(null, "", "/bos/simulation-lab?simulationId=SIM-X");
    const { container, root } = renderInteractive();
    await flushAsyncWork();

    await act(async () => {
      buttonByText(container, "Run virtual loop").click();
    });
    await flushAsyncWork();

    expect(simulationLabApi.runScenario).toHaveBeenCalledWith("SIM-X");
    expect(simulationLabApi.createScenario).not.toHaveBeenCalled();
    act(() => root.unmount());
  });

  it("creates a new scenario before running when the selected scenario form is edited", async () => {
    window.history.replaceState(null, "", "/bos/simulation-lab?simulationId=SIM-X");
    vi.mocked(simulationLabApi.createScenario).mockResolvedValue({
      ...scenarioFixture,
      simulation_id: "SIM-FORM",
      species: "BSFL",
    });
    vi.mocked(simulationLabApi.runScenario).mockResolvedValue(
      runFixture({ ...scenarioFixture, simulation_id: "SIM-FORM", species: "BSFL" }),
    );
    const { container, root } = renderInteractive();
    await flushAsyncWork();

    const speciesInput = Array.from(container.querySelectorAll("input")).find(
      (input) => input.value === "BSF",
    ) as HTMLInputElement | undefined;
    if (!speciesInput) throw new Error("Species input not found");
    await act(async () => {
      Simulate.change(speciesInput, { target: { value: "BSFL" } as EventTarget & { value: string } });
    });

    await act(async () => {
      buttonByText(container, "Run virtual loop").click();
    });
    await flushAsyncWork();

    expect(simulationLabApi.createScenario).toHaveBeenCalledWith(expect.objectContaining({ species: "BSFL" }));
    expect(simulationLabApi.runScenario).toHaveBeenCalledWith("SIM-FORM");
    act(() => root.unmount());
  });

  it("loads the sludge heavy-metal LabSim preset before creating a scenario", async () => {
    vi.mocked(simulationLabApi.createScenario).mockResolvedValue({
      ...scenarioFixture,
      simulation_id: "SIM-SLUDGE",
      feedstock: "municipal_sludge_heavy_metal_screen",
      scenario: "temperature_spike",
      policy: "risk_minimizing",
    });
    vi.mocked(simulationLabApi.runScenario).mockResolvedValue(
      runFixture({
        ...scenarioFixture,
        simulation_id: "SIM-SLUDGE",
        feedstock: "municipal_sludge_heavy_metal_screen",
        scenario: "temperature_spike",
        policy: "risk_minimizing",
      }),
    );
    const { container, root } = renderInteractive();
    await flushAsyncWork();

    await act(async () => {
      buttonByText(container, "BSF sludge heavy-metal redline lane").click();
    });
    await act(async () => {
      buttonByText(container, "Run virtual loop").click();
    });
    await flushAsyncWork();

    expect(simulationLabApi.createScenario).toHaveBeenCalledWith(
      expect.objectContaining({
        species: "BSF",
        feedstock: "municipal_sludge_heavy_metal_screen",
        scenario: "temperature_spike",
        policy: "risk_minimizing",
      }),
    );
    expect(simulationLabApi.runScenario).toHaveBeenCalledWith("SIM-SLUDGE");
    expect(container.textContent).toContain("labsim_assay_anchor:bsf_sludge_heavy_metal_redline");
    expect(container.textContent).toContain("Restricted review lock");
    expect(container.textContent).toContain("Research simulation only; no product-use recommendation");
    expect(container.textContent).toContain("0.710 vs 0.720");
    act(() => root.unmount());
  });

  it("sends operator-entered assay measurements with the scenario payload", async () => {
    vi.mocked(simulationLabApi.createScenario).mockResolvedValue({
      ...scenarioFixture,
      simulation_id: "SIM-ASSAY",
      lab_assay_measurements: {
        biomass: 0.91,
        heavy_metal_index: 0.09,
      },
    });
    vi.mocked(simulationLabApi.runScenario).mockResolvedValue(
      runFixture({ ...scenarioFixture, simulation_id: "SIM-ASSAY" }),
    );
    const { container, root } = renderInteractive();
    await flushAsyncWork();

    const biomassInput = container.querySelector("#measured-biomass") as HTMLInputElement | null;
    const hmInput = container.querySelector("#measured-hm-index") as HTMLInputElement | null;
    if (!biomassInput || !hmInput) throw new Error("Measured assay inputs not found");
    await act(async () => {
      Simulate.change(biomassInput, { target: { value: "0.91" } as EventTarget & { value: string } });
      Simulate.change(hmInput, { target: { value: "0.09" } as EventTarget & { value: string } });
    });
    await act(async () => {
      buttonByText(container, "Run virtual loop").click();
    });
    await flushAsyncWork();

    expect(simulationLabApi.createScenario).toHaveBeenCalledWith(
      expect.objectContaining({
        lab_assay_measurements: expect.objectContaining({
          biomass: 0.91,
          heavy_metal_index: 0.09,
        }),
      }),
    );
    act(() => root.unmount());
  });

  it("fills assay inputs after importing a reference scenario", async () => {
    const importedScenario: SimulationScenarioResponse = {
      ...scenarioFixture,
      simulation_id: "SIM-REFERENCE-ASSAY",
      species: "BSF",
      feedstock: "distillers_grain",
      lab_assay_measurements: {
        biomass: 0.93,
        substrate: 4.25,
        moisture: 66.4,
        heavy_metal_index: 0.12,
      },
      evidence_sources: [
        {
          field: "lab_assay_measurements",
          source_kind: "staged_reference",
          source_ref: "reference_assay_measurements",
          confidence: 0.89,
          fallback_used: false,
          notes: "review-gated measured assay values imported from reference/candidate evidence",
          payload: { biomass: 0.93, substrate: 4.25, moisture: 66.4, heavy_metal_index: 0.12 },
          measurement_mode: "reference_imported",
          review_status: "pending_review",
        },
      ],
    };
    vi.mocked(simulationLabApi.importScenarioFromReference).mockResolvedValue({
      scenario: importedScenario,
      import_metadata: {
        reference_id: "reference_assay_measurements",
        reference_source: "staged_reference",
        source_title: "Reference assay measurements",
        review_status: "pending_review",
        human_review_required: true,
        numeric_values_included: true,
        release_evidence_allowed: false,
        runtime_activation_enabled: false,
        validated_default_write_enabled: false,
        promotion_enabled: false,
        extraction_confidence: 0.89,
        field_sources: {
          "lab_assay_measurements.biomass": "reference.lab_assay_measurements",
        },
        fallbacks: [],
        environmental_drift_assumptions: {},
        expected_risk_constraints: {},
      },
    });
    vi.mocked(simulationLabApi.listScenarios).mockResolvedValue([importedScenario]);
    vi.mocked(simulationLabApi.listRuns).mockResolvedValue([]);
    vi.mocked(simulationLabApi.getCycles).mockResolvedValue({ simulation_id: importedScenario.simulation_id, cycles: [] });
    const { container, root } = renderInteractive();
    await flushAsyncWork();

    const referenceInput = container.querySelector("#reference-id") as HTMLInputElement | null;
    if (!referenceInput) throw new Error("Reference ID input not found");
    await act(async () => {
      Simulate.change(referenceInput, { target: { value: "reference_assay_measurements" } as EventTarget & { value: string } });
    });
    await act(async () => {
      buttonByText(container, "Import reference seed").click();
    });
    await flushAsyncWork();

    expect((container.querySelector("#measured-biomass") as HTMLInputElement).value).toBe("0.93");
    expect((container.querySelector("#measured-substrate") as HTMLInputElement).value).toBe("4.25");
    expect((container.querySelector("#measured-moisture") as HTMLInputElement).value).toBe("66.4");
    expect((container.querySelector("#measured-hm-index") as HTMLInputElement).value).toBe("0.12");
    expect(container.textContent).toContain("Imported assay anchors");
    expect(container.textContent).toContain("Evidence mode reference_imported; review pending_review");
    expect(container.textContent).toContain("Review pending_review; numeric values included; release evidence blocked");
    expect(container.textContent).toContain("Runtime activation blocked; validated defaults locked");
    act(() => root.unmount());
  });

  it("shows metadata-only imports without filling assay anchors", async () => {
    const importedScenario: SimulationScenarioResponse = {
      ...scenarioFixture,
      simulation_id: "SIM-METADATA-ONLY",
      species: "BSF",
      feedstock: "distillers_grain",
      lab_assay_measurements: null,
      evidence_sources: [],
    };
    vi.mocked(simulationLabApi.importScenarioFromReference).mockResolvedValue({
      scenario: importedScenario,
      import_metadata: {
        reference_id: "LIT-LABSIM-METADATA-ONLY-001",
        reference_source: "peer_reviewed_literature",
        source_title: "Literature candidate metadata-only assay",
        review_status: "pending_review",
        human_review_required: true,
        numeric_values_included: false,
        release_evidence_allowed: false,
        runtime_activation_enabled: false,
        validated_default_write_enabled: false,
        promotion_enabled: false,
        extraction_confidence: 0.89,
        field_sources: {},
        fallbacks: [],
        environmental_drift_assumptions: {},
        expected_risk_constraints: {},
      },
    });
    vi.mocked(simulationLabApi.listScenarios).mockResolvedValue([importedScenario]);
    vi.mocked(simulationLabApi.listRuns).mockResolvedValue([]);
    vi.mocked(simulationLabApi.getCycles).mockResolvedValue({ simulation_id: importedScenario.simulation_id, cycles: [] });
    const { container, root } = renderInteractive();
    await flushAsyncWork();

    const referenceInput = container.querySelector("#reference-id") as HTMLInputElement | null;
    if (!referenceInput) throw new Error("Reference ID input not found");
    await act(async () => {
      Simulate.change(referenceInput, { target: { value: "LIT-LABSIM-METADATA-ONLY-001" } as EventTarget & { value: string } });
    });
    await act(async () => {
      buttonByText(container, "Import reference seed").click();
    });
    await flushAsyncWork();

    expect((container.querySelector("#measured-biomass") as HTMLInputElement).value).toBe("");
    expect(container.textContent).toContain("Review pending_review; numeric values not exposed; release evidence blocked");
    expect(container.textContent).toContain("Runtime activation blocked; validated defaults locked");
    expect(container.textContent).not.toContain("Imported assay anchors");
    act(() => root.unmount());
  });
});
