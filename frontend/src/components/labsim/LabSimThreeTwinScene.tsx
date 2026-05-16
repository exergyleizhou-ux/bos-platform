import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { Badge } from "@/components/ui/Badge";
import { formatNumber, formatPercent } from "@/lib/utils";
import type { SimulationLabCycle, SimulationLabRunResponse, SimulationScenarioCreate } from "@/types/simulationLab";
import type { LabSimPreset, TwinZone, TwinZoneId } from "./LabSimTwinStudio";

interface LabSimThreeTwinSceneProps {
  form: SimulationScenarioCreate;
  preset: LabSimPreset;
  zones: TwinZone[];
  run: SimulationLabRunResponse | null;
  cycle: SimulationLabCycle | null;
  selectedZoneId: TwinZoneId;
  riskVariant: "danger" | "neutral" | "success" | "warning";
  moistureLevel: number;
  biomassLevel: number;
  sensorHeat: number;
  cycleCount: number;
  selectedCycleIndex: number;
  assistantCue?: LabAssistantCue | null;
  onSelectZone: (zoneId: TwinZoneId) => void;
}

type CameraMode = "focus" | "overview" | "tour";
type ReplayPhaseId = "actuating" | "assay" | "evidence" | "intake" | "pretreatment" | "reacting" | "review" | "sensing" | "setup";

export interface LabAssistantCue {
  boundary: string;
  commandLabel: string;
  nonce: number;
  response: string;
  zoneId: TwinZoneId;
}

interface ReplayPhase {
  description: string;
  id: ReplayPhaseId;
  label: string;
  progress: number;
  zoneId: TwinZoneId;
}

const zonePositions: Record<TwinZoneId, [number, number, number]> = {
  intake: [-5.4, 0.35, -2.8],
  pretreatment: [-2.7, 0.35, -2.8],
  sensors: [0.5, 0.35, -3.1],
  bay: [-4.3, 0.35, 0.15],
  reactor: [-0.65, 0.35, 0.25],
  review: [3.65, 0.35, -0.95],
  assay: [-4.1, 0.35, 3.0],
  actuator: [-0.15, 0.35, 3.0],
  appendix: [3.55, 0.35, 2.35],
};

const zoneLabelPositions: Record<TwinZoneId, { left: string; top: string }> = {
  intake: { left: "9%", top: "25%" },
  pretreatment: { left: "24%", top: "28%" },
  sensors: { left: "44%", top: "22%" },
  bay: { left: "14%", top: "48%" },
  reactor: { left: "40%", top: "47%" },
  review: { left: "67%", top: "33%" },
  assay: { left: "12%", top: "72%" },
  actuator: { left: "43%", top: "73%" },
  appendix: { left: "68%", top: "67%" },
};

const replayPhases: Array<Omit<ReplayPhase, "progress">> = [
  {
    id: "intake",
    label: "Intake loading",
    description: "Reference-gated material enters the virtual lab path.",
    zoneId: "intake",
  },
  {
    id: "pretreatment",
    label: "Pretreatment conditioning",
    description: "Moisture and substrate conditions are staged before reaction.",
    zoneId: "pretreatment",
  },
  {
    id: "reacting",
    label: "Reactor digestion",
    description: "The reactor fill and risk tint replay the selected cycle state.",
    zoneId: "reactor",
  },
  {
    id: "sensing",
    label: "Sensor sampling",
    description: "Sensor mast pulses from temperature, moisture, and NH3 telemetry.",
    zoneId: "sensors",
  },
  {
    id: "assay",
    label: "Assay check",
    description: "Assay evidence is visualized without promoting candidate values.",
    zoneId: "assay",
  },
  {
    id: "actuating",
    label: "Actuator sandbox",
    description: "Recommended actions stay virtual; hardware execution is disabled.",
    zoneId: "actuator",
  },
  {
    id: "review",
    label: "Review gate",
    description: "Risk and heavy-metal gates remain human-review required where needed.",
    zoneId: "review",
  },
  {
    id: "evidence",
    label: "Evidence packet",
    description: "Appendix evidence is sealed for review without release mutation.",
    zoneId: "appendix",
  },
];

const flowPathZoneIds: TwinZoneId[] = ["intake", "pretreatment", "reactor", "sensors", "assay", "actuator", "review", "appendix"];

const toneColors: Record<TwinZone["tone"], number> = {
  amber: 0xf59e0b,
  cyan: 0x22d3ee,
  emerald: 0x34d399,
  neutral: 0x94a3b8,
  red: 0xf87171,
  sky: 0x38bdf8,
  violet: 0xa78bfa,
};

const riskColors = {
  danger: 0xef4444,
  neutral: 0x94a3b8,
  success: 0x22c55e,
  warning: 0xf59e0b,
} as const;

export function LabSimThreeTwinScene({
  form,
  preset,
  zones,
  run,
  cycle,
  selectedZoneId,
  riskVariant,
  moistureLevel,
  biomassLevel,
  sensorHeat,
  cycleCount,
  selectedCycleIndex,
  assistantCue,
  onSelectZone,
}: LabSimThreeTwinSceneProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const [cameraMode, setCameraMode] = useState<CameraMode>("overview");
  const [rendererReady, setRendererReady] = useState(false);

  const riskScore = cycle?.risk_prediction.future_risk_score ?? run?.summary.ending_risk ?? null;
  const supervisor = cycle?.supervisor_decision.recommended_handover ? "handover" : cycle ? "continue" : "standby";
  const action = cycle?.agent_action.recommended_action.replace(/_/g, " ") ?? "awaiting run";
  const replayPhase = useMemo(
    () => getReplayPhase({ cycle, cycleCount, selectedCycleIndex }),
    [cycle, cycleCount, selectedCycleIndex],
  );

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    cleanupRef.current?.();
    host.innerHTML = "";
    setRendererReady(false);

    if (typeof window.WebGLRenderingContext === "undefined") {
      return;
    }

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
        preserveDrawingBuffer: true,
      });
    } catch {
      return;
    }

    renderer.domElement.dataset.testid = "labsim-3d-canvas";
    renderer.domElement.className = "absolute inset-0 h-full w-full";
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x020617, 0);
    host.appendChild(renderer.domElement);
    setRendererReady(true);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x020617, 9, 20);

    const focusZoneId = assistantCue?.zoneId ?? (cameraMode === "tour" ? replayPhase.zoneId : selectedZoneId);
    const [focusX, , focusZ] = zonePositions[focusZoneId];
    const cameraTarget =
      cameraMode === "overview" ? new THREE.Vector3(0, 0.95, 0) : new THREE.Vector3(focusX * 0.18, 1.05, focusZ * 0.16);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 80);
    camera.position.set(
      cameraMode === "tour" ? 4.9 + focusX * 0.18 : 5.8 + focusX * 0.1,
      cameraMode === "tour" ? 4.7 : 5.4,
      cameraMode === "tour" ? 7.2 + focusZ * 0.16 : 8.4 + focusZ * 0.08,
    );
    camera.lookAt(cameraTarget);

    const labGroup = new THREE.Group();
    labGroup.rotation.y = -0.48;
    scene.add(labGroup);

    const hemiLight = new THREE.HemisphereLight(0xbfefff, 0x0f172a, 1.4);
    scene.add(hemiLight);
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.45);
    keyLight.position.set(3.5, 6.5, 4.5);
    scene.add(keyLight);
    const rimLight = new THREE.PointLight(riskColors[riskVariant], 2.4, 14);
    rimLight.position.set(1.5, 3, -2.4);
    scene.add(rimLight);

    const floor = new THREE.Mesh(
      new THREE.BoxGeometry(12.4, 0.14, 7.4),
      new THREE.MeshStandardMaterial({ color: 0x142235, roughness: 0.78, metalness: 0.14 }),
    );
    floor.position.y = -0.08;
    labGroup.add(floor);

    const grid = new THREE.GridHelper(12, 18, 0x164e63, 0x1e293b);
    grid.position.y = 0.02;
    labGroup.add(grid);

    const flow = new THREE.Mesh(
      new THREE.BoxGeometry(10.2, 0.08, 0.13),
      new THREE.MeshStandardMaterial({ color: 0x67e8f9, emissive: 0x155e75, emissiveIntensity: cycle ? 0.7 : 0.2 }),
    );
    flow.position.set(-0.35, 0.12, -1.45);
    labGroup.add(flow);

    const flowPath = flowPathZoneIds.map((zoneId) => {
      const [x, , z] = zonePositions[zoneId];
      return new THREE.Vector3(x, 0.54, z);
    });
    const flowLine = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(flowPath),
      new THREE.LineBasicMaterial({ color: cycle ? 0x67e8f9 : 0x334155, transparent: true, opacity: cycle ? 0.85 : 0.45 }),
    );
    labGroup.add(flowLine);

    const flowDots: THREE.Mesh[] = [];
    const flowDotMaterial = new THREE.MeshStandardMaterial({
      color: 0xfef3c7,
      emissive: cycle ? 0xf59e0b : 0x334155,
      emissiveIntensity: cycle ? 1.1 : 0.2,
      roughness: 0.3,
    });
    for (let index = 0; index < 18; index += 1) {
      const dot = new THREE.Mesh(new THREE.SphereGeometry(index % 3 === 0 ? 0.075 : 0.055, 12, 12), flowDotMaterial);
      labGroup.add(dot);
      flowDots.push(dot);
    }

    const pickables: THREE.Object3D[] = [];
    let reactorFill: THREE.Mesh | null = null;
    let reactorSurface: THREE.Mesh | null = null;
    const steelMaterial = new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.34, metalness: 0.58 });
    const darkSteelMaterial = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.46, metalness: 0.42 });
    const benchMaterial = new THREE.MeshStandardMaterial({ color: 0x0f2537, roughness: 0.62, metalness: 0.18 });
    const wallMaterial = new THREE.MeshStandardMaterial({ color: 0xe5edf4, roughness: 0.7, metalness: 0.03 });
    const wallTrimMaterial = new THREE.MeshStandardMaterial({ color: 0x7f8ea3, roughness: 0.52, metalness: 0.18 });
    const trayBlueMaterial = new THREE.MeshStandardMaterial({ color: 0x0ea5e9, emissive: 0x075985, emissiveIntensity: 0.1, roughness: 0.48 });
    const labLightMaterial = new THREE.MeshStandardMaterial({
      color: 0xecfeff,
      emissive: 0xbae6fd,
      emissiveIntensity: 0.7,
      roughness: 0.24,
    });
    const pipeMaterial = new THREE.MeshStandardMaterial({ color: 0xcbd5e1, roughness: 0.42, metalness: 0.44 });
    const glassMaterial = new THREE.MeshStandardMaterial({
      color: 0x93c5fd,
      emissive: 0x0e7490,
      emissiveIntensity: 0.12,
      transparent: true,
      opacity: 0.24,
      roughness: 0.08,
      metalness: 0.05,
    });
    const substrateMaterial = new THREE.MeshStandardMaterial({
      color: 0xa16207,
      emissive: cycle ? 0x713f12 : 0x1f2937,
      emissiveIntensity: cycle ? 0.28 : 0.08,
      roughness: 0.72,
    });
    const larvaMaterial = new THREE.MeshStandardMaterial({
      color: 0xfef3c7,
      emissive: cycle ? 0x92400e : 0x0f172a,
      emissiveIntensity: cycle ? 0.18 : 0.04,
      roughness: 0.55,
    });
    const makeMaterial = (zone: TwinZone, selected: boolean) =>
      new THREE.MeshStandardMaterial({
        color: toneColors[zone.tone],
        emissive: selected || zone.id === replayPhase.zoneId ? toneColors[zone.tone] : 0x020617,
        emissiveIntensity: selected ? 0.64 : zone.id === replayPhase.zoneId ? 0.42 : 0.12,
        roughness: 0.42,
        metalness: 0.22,
        transparent: true,
        opacity: selected || zone.id === replayPhase.zoneId ? 0.96 : 0.82,
      });

    const tagZone = (object: THREE.Object3D, zoneId: TwinZoneId) => {
      object.userData.zoneId = zoneId;
      object.traverse((child) => {
        child.userData.zoneId = zoneId;
      });
      pickables.push(object);
    };

    const addBox = (
      group: THREE.Group,
      size: [number, number, number],
      position: [number, number, number],
      material: THREE.Material,
    ) => {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), material);
      mesh.position.set(...position);
      group.add(mesh);
      return mesh;
    };

    const addCylinder = (
      group: THREE.Group,
      radiusTop: number,
      radiusBottom: number,
      height: number,
      position: [number, number, number],
      material: THREE.Material,
      radialSegments = 24,
    ) => {
      const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radiusTop, radiusBottom, height, radialSegments), material);
      mesh.position.set(...position);
      group.add(mesh);
      return mesh;
    };

    const addBench = (group: THREE.Group, width: number, depth: number, height = 0.48) => {
      addBox(group, [width, 0.12, depth], [0, height, 0], benchMaterial);
      const legX = width / 2 - 0.12;
      const legZ = depth / 2 - 0.12;
      [
        [-legX, height / 2, -legZ],
        [legX, height / 2, -legZ],
        [-legX, height / 2, legZ],
        [legX, height / 2, legZ],
      ].forEach((position) => addBox(group, [0.08, height, 0.08], position as [number, number, number], darkSteelMaterial));
    };

    const addLarvaeTray = (group: THREE.Group, z: number, y: number) => {
      addBox(group, [1.7, 0.08, 0.52], [0, y, z], darkSteelMaterial);
      addBox(group, [1.54, 0.06, 0.38], [0, y + 0.06, z], substrateMaterial);
      for (let index = 0; index < 9; index += 1) {
        const larva = new THREE.Mesh(new THREE.SphereGeometry(0.055, 12, 8), larvaMaterial);
        larva.scale.set(1.7, 0.55, 0.75);
        larva.rotation.z = index % 2 ? 0.35 : -0.2;
        larva.position.set(-0.62 + index * 0.155, y + 0.13, z - 0.08 + (index % 3) * 0.07);
        group.add(larva);
      }
    };

    const addWallRack = (x: number, z: number, width = 1.75) => {
      const rack = new THREE.Group();
      rack.position.set(x, 0, z);
      [-width / 2, width / 2].forEach((offsetX) => {
        addBox(rack, [0.06, 1.55, 0.06], [offsetX, 0.82, 0], steelMaterial);
      });
      [0.36, 0.74, 1.12, 1.5].forEach((height) => {
        addBox(rack, [width, 0.055, 0.5], [0, height, 0], wallTrimMaterial);
        [-0.46, 0, 0.46].forEach((offsetX) => {
          addBox(rack, [0.34, 0.09, 0.34], [offsetX, height + 0.08, 0.02], trayBlueMaterial);
        });
      });
      labGroup.add(rack);
    };

    const addPipeRun = (z: number, y: number, length = 10.2) => {
      const pipe = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, length, 16), pipeMaterial);
      pipe.position.set(0, y, z);
      pipe.rotation.z = Math.PI / 2;
      labGroup.add(pipe);
      [-4.5, -1.5, 1.5, 4.5].forEach((x) => {
        addCylinder(labGroup, 0.03, 0.03, 0.55, [x, y - 0.25, z], pipeMaterial, 12);
      });
    };

    const addStationModel = (zone: TwinZone, group: THREE.Group, selected: boolean) => {
      const accentMaterial = makeMaterial(zone, selected);
      switch (zone.id) {
        case "intake": {
          addBench(group, 1.9, 1.05);
          addBox(group, [0.72, 0.16, 0.48], [-0.42, 0.62, -0.08], substrateMaterial);
          addBox(group, [0.46, 0.08, 0.34], [0.45, 0.64, 0.12], glassMaterial);
          addBox(group, [0.08, 0.42, 0.08], [0.74, 0.76, -0.18], steelMaterial);
          addBox(group, [0.42, 0.08, 0.24], [0.74, 1.02, -0.18], accentMaterial);
          break;
        }
        case "pretreatment": {
          addBench(group, 1.8, 1.1);
          addCylinder(group, 0.48, 0.54, 0.75, [0, 0.9, 0], glassMaterial, 32);
          addCylinder(group, 0.34, 0.38, 0.52, [0, 0.82, 0], substrateMaterial, 28);
          addCylinder(group, 0.035, 0.035, 1.05, [0, 1.23, 0], steelMaterial, 12);
          addBox(group, [0.85, 0.06, 0.1], [0, 1.0, 0], accentMaterial).rotation.y = 0.55;
          addBox(group, [0.9, 0.07, 0.1], [0, 1.08, 0], accentMaterial).rotation.y = -0.4;
          break;
        }
        case "sensors": {
          addCylinder(group, 0.34, 0.42, 0.12, [0, 0.12, 0], darkSteelMaterial, 28);
          addCylinder(group, 0.055, 0.065, 2.25, [0, 1.18, 0], steelMaterial, 18);
          addBox(group, [0.52, 0.32, 0.32], [0.32, 1.85, 0], accentMaterial);
          addBox(group, [0.42, 0.1, 0.32], [-0.28, 1.32, 0], glassMaterial);
          [0.78, 1.18, 1.58].forEach((height) => {
            const ring = new THREE.Mesh(new THREE.TorusGeometry(0.36, 0.018, 10, 42), accentMaterial);
            ring.position.set(0, height, 0);
            ring.rotation.x = Math.PI / 2;
            group.add(ring);
          });
          break;
        }
        case "bay": {
          addBox(group, [1.95, 0.08, 0.08], [0, 0.32, -0.34], steelMaterial);
          addBox(group, [1.95, 0.08, 0.08], [0, 1.02, -0.34], steelMaterial);
          addBox(group, [0.08, 1.08, 0.08], [-0.92, 0.56, -0.34], steelMaterial);
          addBox(group, [0.08, 1.08, 0.08], [0.92, 0.56, -0.34], steelMaterial);
          addLarvaeTray(group, -0.18, 0.36);
          addLarvaeTray(group, 0.24, 0.7);
          addLarvaeTray(group, 0.62, 1.04);
          break;
        }
        case "reactor": {
          const height = 1.35 + biomassLevel / 80;
          addCylinder(group, 0.72, 0.82, height, [0, 0.28 + height / 2, 0], glassMaterial, 36);
          addCylinder(group, 0.12, 0.16, 0.46, [0, 0.18, 0], steelMaterial, 18);
          addCylinder(group, 0.045, 0.055, height + 0.45, [0, 0.54 + height / 2, 0], steelMaterial, 12);
          addBox(group, [0.64, 0.07, 0.12], [0, 0.96, 0], accentMaterial).rotation.y = 0.72;
          addBox(group, [0.68, 0.07, 0.12], [0, 1.15, 0], accentMaterial).rotation.y = -0.48;
          const fillHeight = Math.max(
            0.34,
            Math.min(height - 0.22, 0.44 + biomassLevel / 55 + (cycle ? selectedCycleIndex * 0.08 + replayPhase.progress * 0.18 : 0)),
          );
          reactorFill = addCylinder(
            group,
            0.48,
            0.6,
            fillHeight,
            [0, 0.32 + fillHeight / 2, 0],
            new THREE.MeshStandardMaterial({
              color: riskVariant === "danger" ? 0xf97316 : 0x10b981,
              emissive: riskVariant === "danger" ? 0x7f1d1d : 0x065f46,
              emissiveIntensity: cycle ? 0.48 : 0.2,
              transparent: true,
              opacity: 0.72,
              roughness: 0.35,
            }),
            28,
          );
          reactorSurface = new THREE.Mesh(
            new THREE.TorusGeometry(0.52, 0.024, 12, 48),
            new THREE.MeshStandardMaterial({
              color: riskVariant === "danger" ? 0xfbbf24 : 0xa7f3d0,
              emissive: riskVariant === "danger" ? 0xf97316 : 0x10b981,
              emissiveIntensity: cycle ? 0.75 : 0.28,
            }),
          );
          reactorSurface.position.set(0, 0.34 + fillHeight, 0);
          reactorSurface.rotation.x = Math.PI / 2;
          group.add(reactorSurface);
          for (let index = 0; index < 10; index += 1) {
            const bubble = new THREE.Mesh(new THREE.SphereGeometry(0.035 + (index % 3) * 0.01, 10, 8), glassMaterial);
            bubble.position.set(-0.32 + (index % 5) * 0.16, 0.58 + (index % 4) * 0.22, -0.2 + Math.floor(index / 5) * 0.36);
            group.add(bubble);
          }
          break;
        }
        case "review": {
          addBox(group, [1.55, 1.45, 0.72], [0, 0.82, 0], darkSteelMaterial);
          addBox(group, [1.32, 1.12, 0.05], [0, 0.85, -0.39], accentMaterial);
          addBox(group, [0.55, 0.16, 0.06], [-0.34, 1.22, -0.43], steelMaterial);
          addBox(group, [0.18, 0.18, 0.08], [0.48, 0.74, -0.45], steelMaterial);
          const lock = new THREE.Mesh(new THREE.TorusGeometry(0.18, 0.025, 10, 34), accentMaterial);
          lock.position.set(0.48, 0.92, -0.46);
          group.add(lock);
          break;
        }
        case "assay": {
          addBench(group, 1.95, 1.05);
          addCylinder(group, 0.18, 0.24, 0.12, [-0.42, 0.64, -0.02], steelMaterial, 24);
          addCylinder(group, 0.055, 0.06, 0.7, [-0.42, 1.0, -0.02], steelMaterial, 14);
          addCylinder(group, 0.18, 0.12, 0.28, [-0.22, 1.22, -0.02], accentMaterial, 20).rotation.z = Math.PI / 2;
          addBox(group, [0.16, 0.08, 0.44], [0.45, 0.64, -0.2], steelMaterial);
          for (let index = 0; index < 4; index += 1) {
            addCylinder(group, 0.045, 0.055, 0.34, [0.27 + index * 0.13, 0.86, 0.18], glassMaterial, 12);
          }
          break;
        }
        case "actuator": {
          addBench(group, 1.7, 0.95);
          addBox(group, [0.82, 0.16, 0.48], [-0.28, 0.67, 0.02], darkSteelMaterial);
          addBox(group, [0.54, 0.05, 0.3], [-0.28, 0.78, -0.03], accentMaterial);
          addCylinder(group, 0.08, 0.1, 0.64, [0.45, 0.85, 0.0], steelMaterial, 14).rotation.z = 0.62;
          const valve = new THREE.Mesh(new THREE.TorusGeometry(0.22, 0.025, 10, 34), accentMaterial);
          valve.position.set(0.68, 1.07, 0.18);
          valve.rotation.y = Math.PI / 2;
          group.add(valve);
          break;
        }
        case "appendix": {
          addBox(group, [1.65, 1.25, 0.78], [0, 0.72, 0], darkSteelMaterial);
          [-0.38, 0, 0.38].forEach((offset, index) => {
            addBox(group, [1.34, 0.06, 0.05], [0, 0.35 + index * 0.3, -0.43], steelMaterial);
            addBox(group, [0.24, 0.18, 0.06], [offset, 0.47 + index * 0.3, -0.46], accentMaterial);
          });
          const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.32, 1.7, 24, 1, true), glassMaterial);
          beam.position.set(0, 1.05, 0);
          group.add(beam);
          break;
        }
        default:
          addBox(group, [1.2, 0.8, 0.9], [0, 0.55, 0], accentMaterial);
      }
    };

    const backWall = new THREE.Mesh(new THREE.BoxGeometry(12.2, 2.65, 0.08), wallMaterial);
    backWall.position.set(0, 1.24, -3.72);
    labGroup.add(backWall);

    const leftWall = new THREE.Mesh(new THREE.BoxGeometry(0.08, 2.45, 7.2), wallMaterial);
    leftWall.position.set(-6.14, 1.16, -0.16);
    labGroup.add(leftWall);

    const rightWall = new THREE.Mesh(new THREE.BoxGeometry(0.08, 2.45, 7.2), wallMaterial);
    rightWall.position.set(6.08, 1.16, -0.16);
    labGroup.add(rightWall);

    [-3.1, 0.1, 3.3].forEach((x) => addWallRack(x, -3.28));

    [-4.4, -1.45, 1.45, 4.4].forEach((x) => {
      addBox(labGroup, [1.7, 0.08, 0.28], [x, 2.48, -1.35], labLightMaterial);
    });

    [-2.62, -0.32, 1.98].forEach((z) => addPipeRun(z, 2.28));

    [-5.15, 5.1].forEach((x) => {
      addBox(labGroup, [0.06, 1.92, 6.6], [x, 1.05, -0.18], wallTrimMaterial);
    });

    addBox(labGroup, [1.35, 0.88, 0.045], [-5.98, 1.55, -1.95], glassMaterial);
    addBox(labGroup, [1.35, 0.88, 0.045], [5.92, 1.55, -1.95], glassMaterial);
    addBox(labGroup, [1.08, 0.22, 0.05], [0.1, 2.2, -3.63], trayBlueMaterial);

    [-3.6, -1.2, 1.2, 3.6].forEach((x) => {
      const panel = new THREE.Mesh(
        new THREE.BoxGeometry(1.35, 0.58, 0.04),
        new THREE.MeshStandardMaterial({ color: 0x123047, emissive: 0x0e7490, emissiveIntensity: 0.14, roughness: 0.5 }),
      );
      panel.position.set(x, 1.55, -3.66);
      labGroup.add(panel);
    });

    zones.forEach((zone) => {
      const selected = zone.id === selectedZoneId;
      const [x, y, z] = zonePositions[zone.id];
      const stationGroup = new THREE.Group();
      stationGroup.name = `labsim-3d-${zone.id}`;
      stationGroup.position.set(x, y, z);
      addStationModel(zone, stationGroup, selected);
      tagZone(stationGroup, zone.id);
      labGroup.add(stationGroup);

      const pickSurface = new THREE.Mesh(
        new THREE.CylinderGeometry(zone.id === "review" ? 1.16 : 0.94, zone.id === "review" ? 1.24 : 1.02, 0.05, 24),
        new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.001, depthWrite: false }),
      );
      pickSurface.position.set(x, 0.2, z);
      pickSurface.userData.zoneId = zone.id;
      labGroup.add(pickSurface);
      pickables.push(pickSurface);

      const base = new THREE.Mesh(
        new THREE.CylinderGeometry(0.82, 0.9, 0.08, 24),
        new THREE.MeshStandardMaterial({ color: selected ? 0xe0f2fe : 0x1e293b, roughness: 0.55, metalness: 0.18 }),
      );
      base.position.set(x, 0.08, z);
      base.scale.x = zone.id === "review" ? 1.35 : 1;
      base.userData.zoneId = zone.id;
      labGroup.add(base);
      pickables.push(base);

      if (selected || zone.id === replayPhase.zoneId) {
        const focusRing = new THREE.Mesh(
          new THREE.TorusGeometry(zone.id === "review" ? 1.18 : 0.94, selected ? 0.035 : 0.024, 16, 72),
          new THREE.MeshStandardMaterial({
            color: selected ? 0xe0f2fe : 0x67e8f9,
            emissive: toneColors[zone.tone],
            emissiveIntensity: selected ? 0.72 : 0.48,
          }),
        );
        focusRing.position.set(x, 0.18, z);
        focusRing.rotation.x = Math.PI / 2;
        labGroup.add(focusRing);
      }
    });

    const phasePosition = zonePositions[assistantCue?.zoneId ?? replayPhase.zoneId];
    const phaseBeacon = new THREE.Mesh(
      new THREE.ConeGeometry(0.32, 0.75, 24),
      new THREE.MeshStandardMaterial({
        color: riskColors[riskVariant],
        emissive: riskColors[riskVariant],
        emissiveIntensity: cycle ? 0.95 : 0.35,
        transparent: true,
        opacity: cycle ? 0.82 : 0.45,
      }),
    );
    phaseBeacon.position.set(phasePosition[0], 2.55, phasePosition[2]);
    labGroup.add(phaseBeacon);

    const heatRing = new THREE.Mesh(
      new THREE.TorusGeometry(1.42 + sensorHeat * 0.24, 0.035, 16, 72),
      new THREE.MeshStandardMaterial({
        color: riskColors[riskVariant],
        emissive: riskColors[riskVariant],
        emissiveIntensity: 0.9,
      }),
    );
    heatRing.position.set(-0.65, 1.4, 0.25);
    heatRing.rotation.x = Math.PI / 2;
    labGroup.add(heatRing);

    const sensorPulses: THREE.Mesh[] = [0.72, 1.08, 1.44].map((radius) => {
      const pulse = new THREE.Mesh(
        new THREE.TorusGeometry(radius, 0.018, 12, 56),
        new THREE.MeshStandardMaterial({
          color: riskColors[riskVariant],
          emissive: riskColors[riskVariant],
          emissiveIntensity: cycle ? 0.82 : 0.25,
          transparent: true,
          opacity: 0.65,
        }),
      );
      pulse.position.set(0.5, 1.9, -3.1);
      pulse.rotation.x = Math.PI / 2;
      labGroup.add(pulse);
      return pulse;
    });

    const assayVial = new THREE.Mesh(
      new THREE.CylinderGeometry(0.18, 0.22, 0.68, 20),
      new THREE.MeshStandardMaterial({
        color: 0x22d3ee,
        emissive: cycle ? 0x0891b2 : 0x164e63,
        emissiveIntensity: cycle && replayPhase.id === "assay" ? 1.05 : cycle ? 0.45 : 0.18,
        transparent: true,
        opacity: 0.78,
      }),
    );
    assayVial.position.set(-4.1, 1.05, 3);
    labGroup.add(assayVial);

    const reviewLock = new THREE.Mesh(
      new THREE.TorusGeometry(0.48, 0.04, 12, 46),
      new THREE.MeshStandardMaterial({
        color: riskVariant === "success" ? 0x34d399 : 0xf59e0b,
        emissive: riskVariant === "danger" ? 0xef4444 : 0xf59e0b,
        emissiveIntensity: replayPhase.id === "review" ? 1.0 : 0.35,
      }),
    );
    reviewLock.position.set(3.65, 1.45, -0.95);
    labGroup.add(reviewLock);

    const evidenceBeam = new THREE.Mesh(
      new THREE.CylinderGeometry(0.22, 0.38, 2.1, 24, 1, true),
      new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        emissive: 0x38bdf8,
        emissiveIntensity: replayPhase.id === "evidence" ? 0.82 : 0.24,
        transparent: true,
        opacity: replayPhase.id === "evidence" ? 0.26 : 0.12,
        side: THREE.DoubleSide,
      }),
    );
    evidenceBeam.position.set(3.55, 1.45, 2.35);
    labGroup.add(evidenceBeam);

    const moisturePool = new THREE.Mesh(
      new THREE.BoxGeometry(2.2, 0.08, Math.max(0.35, moistureLevel / 35)),
      new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x0e7490, emissiveIntensity: 0.28 }),
    );
    moisturePool.position.set(-2.7, 0.18, -2.8);
    labGroup.add(moisturePool);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let dragging = false;
    let moved = false;
    let lastX = 0;
    let lastY = 0;
    let frame = 0;

    const positionOnFlowPath = (progress: number) => {
      const clamped = ((progress % 1) + 1) % 1;
      const scaled = clamped * (flowPath.length - 1);
      const index = Math.min(Math.floor(scaled), flowPath.length - 2);
      const local = scaled - index;
      return flowPath[index].clone().lerp(flowPath[index + 1], local);
    };

    const sizeRenderer = () => {
      const rect = host.getBoundingClientRect();
      const width = Math.max(1, Math.floor(rect.width));
      const height = Math.max(1, Math.floor(rect.height));
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };

    const resizeObserver = new ResizeObserver(sizeRenderer);
    resizeObserver.observe(host);
    sizeRenderer();

    const onPointerDown = (event: PointerEvent) => {
      dragging = true;
      moved = false;
      lastX = event.clientX;
      lastY = event.clientY;
      renderer.domElement.setPointerCapture(event.pointerId);
    };
    const onPointerMove = (event: PointerEvent) => {
      if (!dragging) return;
      const dx = event.clientX - lastX;
      const dy = event.clientY - lastY;
      if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;
      labGroup.rotation.y += dx * 0.008;
      labGroup.rotation.x = Math.max(-0.32, Math.min(0.2, labGroup.rotation.x + dy * 0.004));
      lastX = event.clientX;
      lastY = event.clientY;
    };
    const onPointerUp = (event: PointerEvent) => {
      dragging = false;
      renderer.domElement.releasePointerCapture(event.pointerId);
      if (moved) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -(((event.clientY - rect.top) / rect.height) * 2 - 1);
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(pickables, false)[0];
      const zoneId = hit?.object.userData.zoneId as TwinZoneId | undefined;
      if (zoneId) onSelectZone(zoneId);
    };
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      camera.position.multiplyScalar(event.deltaY > 0 ? 1.06 : 0.94);
      camera.position.clampLength(7.2, 14.5);
      camera.lookAt(cameraTarget);
    };

    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    renderer.domElement.addEventListener("pointermove", onPointerMove);
    renderer.domElement.addEventListener("pointerup", onPointerUp);
    renderer.domElement.addEventListener("wheel", onWheel, { passive: false });

    const animate = () => {
      frame = window.requestAnimationFrame(animate);
      const t = performance.now() * 0.001;
      heatRing.rotation.z = t * 0.75;
      heatRing.scale.setScalar(1 + Math.sin(t * 2.1) * 0.025);
      sensorPulses.forEach((pulse, index) => {
        const pulseScale = 1 + ((t * (cycle ? 0.55 + sensorHeat * 0.35 : 0.18) + index * 0.33) % 1) * 0.7;
        pulse.scale.setScalar(pulseScale);
        const material = pulse.material as THREE.MeshStandardMaterial;
        material.opacity = Math.max(0.08, 0.62 - (pulseScale - 1) * 0.62);
      });
      flowDots.forEach((dot, index) => {
        const offset = index / flowDots.length;
        const travel = cycle
          ? t * (assistantCue ? 0.28 : 0.18) + replayPhase.progress * 0.9 + offset
          : 0.12 + offset * (assistantCue ? 0.62 : 0.42) + (assistantCue ? t * 0.2 : 0);
        dot.position.copy(positionOnFlowPath(travel));
        dot.position.y += Math.sin(t * 2.4 + index) * 0.035;
        dot.scale.setScalar(cycle ? 1 + Math.sin(t * 3 + index) * 0.16 : 0.72);
      });
      if (reactorFill) {
        reactorFill.rotation.y = t * (cycle ? 0.28 : 0.08);
        reactorFill.position.y += Math.sin(t * 2.2) * (cycle ? 0.0025 : 0.0008);
      }
      if (reactorSurface) {
        reactorSurface.rotation.z = t * (cycle ? 0.7 : 0.18);
        reactorSurface.scale.setScalar(1 + Math.sin(t * 2.4) * (cycle ? 0.035 : 0.012));
      }
      phaseBeacon.rotation.y = t * 0.8;
      phaseBeacon.position.y = 2.48 + Math.sin(t * 2.2) * 0.08;
      assayVial.rotation.y = t * 0.36;
      reviewLock.rotation.z = t * (replayPhase.id === "review" ? 0.8 : 0.18);
      evidenceBeam.rotation.y = t * 0.24;
      if (!dragging) labGroup.rotation.y += cameraMode === "tour" ? 0.0024 : 0.0015;
      camera.lookAt(cameraTarget);
      renderer.render(scene, camera);
    };
    animate();

    cleanupRef.current = () => {
      window.cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      renderer.domElement.removeEventListener("pointermove", onPointerMove);
      renderer.domElement.removeEventListener("pointerup", onPointerUp);
      renderer.domElement.removeEventListener("wheel", onWheel);
      renderer.dispose();
      host.innerHTML = "";
    };

    return cleanupRef.current;
  }, [
    biomassLevel,
    cameraMode,
    cycle,
    cycleCount,
    form.feedstock,
    form.species,
    moistureLevel,
    onSelectZone,
    replayPhase.description,
    replayPhase.id,
    replayPhase.label,
    replayPhase.progress,
    replayPhase.zoneId,
    assistantCue,
    riskVariant,
    selectedCycleIndex,
    selectedZoneId,
    sensorHeat,
    zones,
    run?.summary.simulation_id,
  ]);

  return (
    <section
      data-testid="labsim-3d-twin"
      className="relative min-h-[46rem] overflow-hidden rounded-2xl bg-slate-950 xl:min-h-[calc(100vh-8rem)]"
      aria-label="3D Lab Twin"
    >
      <div ref={hostRef} className="absolute inset-0" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_18%,rgba(34,211,238,0.18),transparent_34%),linear-gradient(180deg,rgba(2,6,23,0.05),rgba(2,6,23,0.72))]" />
      <div className="pointer-events-none absolute left-4 top-4 max-w-[16rem] rounded-xl border border-white/10 bg-slate-950/62 p-3 backdrop-blur">
        <p className="text-[0.64rem] uppercase tracking-[0.18em] text-cyan-100/70">3D Lab Twin</p>
        <h3 className="mt-1 text-sm font-semibold text-white">{preset.shortLabel} experiment replay</h3>
        <p className="mt-1 text-xs leading-5 text-surface-300">
          {`${form.species} on ${form.feedstock.replace(/_/g, " ")}`}
        </p>
      </div>
      <div
        data-testid="labsim-3d-replay-hud"
        className="pointer-events-none absolute left-4 top-[7.25rem] max-w-[16rem] rounded-xl border border-white/10 bg-slate-950/70 p-3 text-xs leading-5 text-surface-200 backdrop-blur"
      >
        <div className="grid gap-1">
          <p className="uppercase tracking-[0.16em] text-cyan-100/70">Experiment phase</p>
          <span data-testid="labsim-3d-experiment-phase" className="font-semibold text-white">
            {replayPhase.label}
          </span>
        </div>
        <p className="mt-2 text-surface-300">{replayPhase.description}</p>
        <div className="mt-3">
          <div className="flex items-center justify-between gap-3 uppercase tracking-[0.14em] text-surface-500">
            <span>Material flow</span>
            <span>{cycle ? `${Math.round(replayPhase.progress * 100)}%` : "standby"}</span>
          </div>
          <span data-testid="labsim-3d-material-flow" className="mt-1 block h-1.5 overflow-hidden rounded-full bg-white/10">
            <span className="block h-full rounded-full bg-cyan-200" style={{ width: `${Math.max(10, replayPhase.progress * 100)}%` }} />
          </span>
        </div>
        <div data-testid="labsim-3d-phase-rail" className="mt-3 grid grid-cols-4 gap-1">
          {replayPhases.map((phase) => (
            <span
              key={phase.id}
              className={[
                "truncate rounded-md border px-1.5 py-1 text-center text-[0.56rem] font-semibold uppercase tracking-[0.08em]",
                phase.id === replayPhase.id
                  ? "border-cyan-100 bg-cyan-100 text-slate-950"
                  : "border-white/10 bg-white/[0.04] text-surface-500",
              ].join(" ")}
            >
              {phase.id === "pretreatment" ? "prep" : phase.id}
            </span>
          ))}
        </div>
      </div>
      {assistantCue ? (
        <div
          data-testid="labsim-3d-assistant-cue"
          className="pointer-events-none absolute left-1/2 top-4 w-[min(34rem,calc(100%-2rem))] -translate-x-1/2 rounded-2xl border border-cyan-100/40 bg-slate-950/72 p-3 text-sm shadow-2xl shadow-cyan-950/30 backdrop-blur"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[0.64rem] uppercase tracking-[0.18em] text-cyan-100/75">Lab assistant demo</p>
              <p className="mt-1 truncate font-semibold text-white">{assistantCue.commandLabel}</p>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-surface-200">{assistantCue.response}</p>
            </div>
            <Badge variant="info">virtual</Badge>
          </div>
          <p className="mt-2 text-[0.68rem] leading-5 text-surface-400">{assistantCue.boundary}</p>
        </div>
      ) : null}
      <div className="pointer-events-none absolute right-4 top-4 flex flex-wrap justify-end gap-2">
        <Badge variant={rendererReady ? "success" : "warning"}>Three.js scene</Badge>
        <Badge variant={cycle ? riskVariant : "neutral"}>{cycle ? `cycle ${cycle.cycle}` : "standby"}</Badge>
        <Badge variant="info">{cycleCount ? `${selectedCycleIndex + 1}/${cycleCount}` : "no run"}</Badge>
      </div>
      <div
        data-testid="labsim-3d-camera-modes"
        className="absolute right-4 top-[4.35rem] flex max-w-[17rem] flex-wrap justify-end gap-1.5"
        aria-label="3D camera modes"
      >
        {(["overview", "focus", "tour"] as CameraMode[]).map((mode) => (
          <button
            key={mode}
            type="button"
            className={[
              "rounded-md border px-2.5 py-1 text-xs font-semibold capitalize transition",
              cameraMode === mode
                ? "border-cyan-100 bg-cyan-100 text-slate-950"
                : "border-white/10 bg-slate-950/70 text-surface-200 hover:border-cyan-200/70",
            ].join(" ")}
            aria-pressed={cameraMode === mode}
            onClick={() => setCameraMode(mode)}
          >
            {mode === "tour" ? "Replay tour" : mode}
          </button>
        ))}
      </div>
      <div data-testid="labsim-3d-station-markers" className="pointer-events-none absolute inset-0">
        {zones.map((zone, index) => (
          <button
            key={zone.id}
            type="button"
            data-testid={`labsim-3d-station-marker-${zone.id}`}
            className={[
              "pointer-events-auto absolute grid h-8 w-8 place-items-center rounded-full border text-xs font-bold shadow-lg backdrop-blur transition hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200",
              zone.id === selectedZoneId || zone.id === replayPhase.zoneId
                ? "border-cyan-100 bg-cyan-100 text-slate-950"
                : "border-white/20 bg-slate-950/70 text-surface-100 hover:border-cyan-200/70",
            ].join(" ")}
            style={zoneLabelPositions[zone.id]}
            aria-label={`Station ${index + 1}: ${zone.label}`}
            aria-pressed={zone.id === selectedZoneId}
            onClick={() => onSelectZone(zone.id)}
          >
            {index + 1}
          </button>
        ))}
        {zones
          .filter((zone) => zone.id === selectedZoneId || (zone.id === replayPhase.zoneId && zone.id !== selectedZoneId))
          .map((zone) => {
            const selected = zone.id === selectedZoneId;
            return (
              <button
                key={`label-${zone.id}`}
                type="button"
                data-testid={`labsim-3d-station-label-${zone.id}`}
                className={[
                  "pointer-events-auto absolute max-w-[11rem] translate-x-9 rounded-lg border px-2.5 py-1.5 text-left text-[0.68rem] font-semibold leading-tight shadow-lg backdrop-blur transition",
                  selected
                    ? "border-cyan-100 bg-cyan-100 text-slate-950"
                    : "border-white/10 bg-slate-950/78 text-surface-100",
                ].join(" ")}
                style={zoneLabelPositions[zone.id]}
                aria-pressed={selected}
                onClick={() => onSelectZone(zone.id)}
              >
                <span className="block truncate">{selected ? "Selected station" : "Active phase"}</span>
                <span className="mt-0.5 block truncate">{zone.label}</span>
                <span className={selected ? "block truncate text-slate-700" : "block truncate text-surface-400"}>{zone.value}</span>
              </button>
            );
          })}
      </div>
      <div
        data-testid="labsim-3d-metric-strip"
        className="pointer-events-none absolute bottom-4 left-4 right-4 grid gap-2 text-xs sm:grid-cols-4 lg:right-auto lg:max-w-[44rem]"
      >
        <SceneMetric label="Risk" value={riskScore == null ? "pending" : formatPercent(riskScore, 1)} />
        <SceneMetric label="Supervisor" value={supervisor} />
        <SceneMetric label="Moisture" value={`${formatNumber(Number(cycle?.state_after.moisture ?? form.initial_state.moisture), 1)}%`} />
        <SceneMetric label="Action" value={action} />
      </div>
      <div className="pointer-events-none absolute bottom-[6.25rem] right-4 max-w-[13rem] rounded-xl border border-white/10 bg-slate-950/64 p-2.5 text-[0.68rem] leading-5 text-surface-300 lg:bottom-4">
        Runtime blocked. Hardware execution blocked. Validated defaults locked.
      </div>
      {!rendererReady ? (
        <div className="absolute inset-0 grid place-items-center bg-slate-950 text-sm text-surface-300">
          3D renderer unavailable in this environment; LabSim data and 2.5D twin remain available.
        </div>
      ) : null}
    </section>
  );
}

function SceneMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/75 p-3 backdrop-blur">
      <p className="text-[0.62rem] uppercase tracking-[0.16em] text-surface-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function getReplayPhase({
  cycle,
  cycleCount,
  selectedCycleIndex,
}: {
  cycle: SimulationLabCycle | null;
  cycleCount: number;
  selectedCycleIndex: number;
}): ReplayPhase {
  if (!cycle || !cycleCount) {
    return {
      description: "Visual replay only; run an experiment to animate the lab sequence.",
      id: "setup",
      label: "Standby setup",
      progress: 0.1,
      zoneId: "intake",
    };
  }

  const runProgress = cycleCount > 1 ? selectedCycleIndex / (cycleCount - 1) : 1;
  const scaled = runProgress * replayPhases.length;
  const phaseIndex = Math.min(Math.floor(scaled), replayPhases.length - 1);
  const phaseProgress = phaseIndex === replayPhases.length - 1 ? 1 : Math.max(0.08, scaled - phaseIndex);
  return {
    ...replayPhases[phaseIndex],
    progress: phaseProgress,
  };
}
