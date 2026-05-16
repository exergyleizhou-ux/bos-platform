import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";

import { Badge } from "@/components/ui/Badge";
import { formatNumber, formatPercent } from "@/lib/utils";
import type { SimulationLabCycle, SimulationLabRunResponse, SimulationScenarioCreate } from "@/types/simulationLab";
import type { LabAssistantCue } from "./LabSimThreeTwinScene";
import type { LabSimPreset, TwinZone, TwinZoneId } from "./LabSimTwinStudio";

interface LabSimGaussianSplatStageProps {
  form: SimulationScenarioCreate;
  preset: LabSimPreset;
  zones: TwinZone[];
  run: SimulationLabRunResponse | null;
  cycle: SimulationLabCycle | null;
  selectedZoneId: TwinZoneId;
  riskVariant: "danger" | "neutral" | "success" | "warning";
  moistureLevel: number;
  sensorHeat: number;
  cycleCount: number;
  selectedCycleIndex: number;
  assistantCue?: LabAssistantCue | null;
  onSelectZone: (zoneId: TwinZoneId) => void;
}

type GaussianCameraMode = "overview" | "focus" | "tour";

const demoSplatAssetUrl = "/splats/labsim-demo-lab.ply";

const markerPositions: Record<TwinZoneId, { left: string; top: string }> = {
  intake: { left: "9%", top: "27%" },
  pretreatment: { left: "24%", top: "31%" },
  sensors: { left: "47%", top: "24%" },
  bay: { left: "15%", top: "51%" },
  reactor: { left: "42%", top: "48%" },
  review: { left: "70%", top: "35%" },
  assay: { left: "13%", top: "73%" },
  actuator: { left: "43%", top: "74%" },
  appendix: { left: "70%", top: "68%" },
};

const worldPositions: Record<TwinZoneId, [number, number, number]> = {
  intake: [-4.5, 0.5, -2.35],
  pretreatment: [-2.3, 0.45, -2.15],
  sensors: [0.35, 1.15, -2.35],
  bay: [-3.75, 0.5, 0.15],
  reactor: [-0.4, 0.9, 0.1],
  review: [3.0, 0.85, -0.8],
  assay: [-3.4, 0.62, 2.25],
  actuator: [-0.15, 0.6, 2.25],
  appendix: [3.0, 0.75, 1.65],
};

const zoneOrder: TwinZoneId[] = ["intake", "pretreatment", "reactor", "sensors", "assay", "actuator", "review", "appendix"];

const riskColors = {
  danger: 0xef4444,
  neutral: 0x94a3b8,
  success: 0x22c55e,
  warning: 0xf59e0b,
} as const;

const toneClasses: Record<TwinZone["tone"], string> = {
  amber: "border-amber-200/70 bg-amber-200 text-slate-950",
  cyan: "border-cyan-100 bg-cyan-100 text-slate-950",
  emerald: "border-emerald-200/70 bg-emerald-200 text-slate-950",
  neutral: "border-white/20 bg-slate-950/72 text-surface-100",
  red: "border-red-200/80 bg-red-200 text-slate-950",
  sky: "border-sky-200/80 bg-sky-200 text-slate-950",
  violet: "border-violet-200/80 bg-violet-200 text-slate-950",
};

const vertexShader = `
  attribute vec3 color;
  varying vec3 vColor;
  uniform float uPointScale;
  uniform float uPulse;

  void main() {
    vColor = color;
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    float distanceScale = clamp(9.5 / -mvPosition.z, 0.45, 2.6);
    gl_PointSize = uPointScale * distanceScale * (1.0 + uPulse * 0.08);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const fragmentShader = `
  varying vec3 vColor;

  void main() {
    vec2 centered = gl_PointCoord - vec2(0.5);
    float radius = dot(centered, centered);
    if (radius > 0.25) discard;
    float alpha = exp(-radius * 9.0) * 0.86;
    gl_FragColor = vec4(vColor, alpha);
  }
`;

export function LabSimGaussianSplatStage({
  form,
  preset,
  zones,
  run,
  cycle,
  selectedZoneId,
  riskVariant,
  moistureLevel,
  sensorHeat,
  cycleCount,
  selectedCycleIndex,
  assistantCue,
  onSelectZone,
}: LabSimGaussianSplatStageProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const [cameraMode, setCameraMode] = useState<GaussianCameraMode>("overview");
  const [rendererState, setRendererState] = useState<"loading" | "ready" | "unavailable">("loading");
  const riskScore = cycle?.risk_prediction.future_risk_score ?? run?.summary.ending_risk ?? null;
  const action = cycle?.agent_action.recommended_action.replace(/_/g, " ") ?? "awaiting run";
  const activeZoneId = assistantCue?.zoneId ?? (cameraMode === "tour" ? zoneOrder[selectedCycleIndex % zoneOrder.length] : selectedZoneId);
  const activeZone = zones.find((zone) => zone.id === activeZoneId) ?? zones[0];
  const materialProgress = cycleCount ? (selectedCycleIndex + 1) / cycleCount : assistantCue ? 0.58 : 0.16;
  const statusLabel = rendererState === "ready" ? "Demo PLY splat loaded" : rendererState === "loading" ? "Loading demo splat" : "Splat renderer unavailable";

  const flowLineStyle = useMemo(
    () => ({
      clipPath: `inset(0 ${Math.max(0, 100 - materialProgress * 100)}% 0 0)`,
    }),
    [materialProgress],
  );

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    cleanupRef.current?.();
    host.innerHTML = "";
    setRendererState("loading");

    if (typeof window.WebGLRenderingContext === "undefined") {
      setRendererState("unavailable");
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
      setRendererState("unavailable");
      return;
    }

    renderer.domElement.dataset.testid = "labsim-3d-canvas";
    renderer.domElement.className = "absolute inset-0 h-full w-full";
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x020617, 0);
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x020617, 8, 22);

    const camera = new THREE.PerspectiveCamera(43, 1, 0.1, 90);
    const focus = new THREE.Vector3(...worldPositions[activeZoneId]);
    const cameraTarget = cameraMode === "overview" ? new THREE.Vector3(-0.25, 0.75, 0.05) : focus.clone().multiplyScalar(0.22);
    camera.position.set(
      cameraMode === "tour" ? 4.8 + focus.x * 0.15 : 5.9 + focus.x * 0.08,
      cameraMode === "overview" ? 4.8 : 3.95,
      cameraMode === "tour" ? 7.7 + focus.z * 0.12 : 8.5 + focus.z * 0.08,
    );
    camera.lookAt(cameraTarget);

    const stageGroup = new THREE.Group();
    stageGroup.rotation.y = -0.44;
    scene.add(stageGroup);

    scene.add(new THREE.HemisphereLight(0xdffbff, 0x0f172a, 1.2));
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.75);
    keyLight.position.set(3.4, 6, 4);
    scene.add(keyLight);
    const riskLight = new THREE.PointLight(riskColors[riskVariant], 2.2, 12);
    riskLight.position.set(focus.x, 2.2, focus.z);
    scene.add(riskLight);

    const shaderMaterial = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      uniforms: {
        uPointScale: { value: 36 },
        uPulse: { value: 0 },
      },
      vertexShader,
      fragmentShader,
    });

    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(10, 6.4),
      new THREE.MeshBasicMaterial({ color: 0x0f172a, transparent: true, opacity: 0.28, side: THREE.DoubleSide }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.08;
    stageGroup.add(floor);

    const loader = new PLYLoader();
    let disposed = false;
    let splatPoints: THREE.Points<THREE.BufferGeometry, THREE.ShaderMaterial> | null = null;
    loader.load(
      demoSplatAssetUrl,
      (geometry) => {
        if (disposed) {
          geometry.dispose();
          return;
        }
        geometry.computeBoundingSphere();
        geometry.center();
        geometry.scale(1.05, 1.05, 1.05);
        ensureColorAttribute(geometry);
        const splatGeometry = mergeSplatGeometries(densifySplatGeometry(geometry), createFallbackSplatGeometry());
        geometry.dispose();
        splatPoints = new THREE.Points(splatGeometry, shaderMaterial);
        splatPoints.rotation.x = -0.02;
        stageGroup.add(splatPoints);
        setRendererState("ready");
      },
      undefined,
      () => {
        if (disposed) return;
        const geometry = createFallbackSplatGeometry();
        splatPoints = new THREE.Points(geometry, shaderMaterial);
        stageGroup.add(splatPoints);
        setRendererState("ready");
      },
    );

    const flowPoints = zoneOrder.map((zoneId) => new THREE.Vector3(...worldPositions[zoneId]));
    const flowLine = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(flowPoints),
      new THREE.LineBasicMaterial({ color: assistantCue || cycle ? 0x67e8f9 : 0x334155, transparent: true, opacity: assistantCue || cycle ? 0.82 : 0.42 }),
    );
    stageGroup.add(flowLine);

    const focusBeacon = new THREE.Mesh(
      new THREE.TorusGeometry(0.48, 0.025, 12, 56),
      new THREE.MeshBasicMaterial({ color: riskColors[riskVariant], transparent: true, opacity: 0.9 }),
    );
    focusBeacon.position.set(focus.x, focus.y + 0.28, focus.z);
    focusBeacon.rotation.x = Math.PI / 2;
    stageGroup.add(focusBeacon);

    const routeDot = new THREE.Mesh(
      new THREE.SphereGeometry(0.095, 18, 18),
      new THREE.MeshBasicMaterial({ color: 0xfef3c7 }),
    );
    stageGroup.add(routeDot);

    const positionOnRoute = (progress: number) => {
      const scaled = Math.min(0.999, Math.max(0, progress)) * (flowPoints.length - 1);
      const index = Math.min(Math.floor(scaled), flowPoints.length - 2);
      const local = scaled - index;
      return flowPoints[index].clone().lerp(flowPoints[index + 1], local);
    };

    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    let frame = 0;

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
      lastX = event.clientX;
      lastY = event.clientY;
      renderer.domElement.setPointerCapture(event.pointerId);
    };
    const onPointerMove = (event: PointerEvent) => {
      if (!dragging) return;
      const dx = event.clientX - lastX;
      const dy = event.clientY - lastY;
      stageGroup.rotation.y += dx * 0.006;
      stageGroup.rotation.x = Math.max(-0.24, Math.min(0.16, stageGroup.rotation.x + dy * 0.003));
      lastX = event.clientX;
      lastY = event.clientY;
    };
    const onPointerUp = (event: PointerEvent) => {
      dragging = false;
      renderer.domElement.releasePointerCapture(event.pointerId);
    };
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      camera.position.multiplyScalar(event.deltaY > 0 ? 1.05 : 0.95);
      camera.position.clampLength(6.8, 14.2);
      camera.lookAt(cameraTarget);
    };

    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    renderer.domElement.addEventListener("pointermove", onPointerMove);
    renderer.domElement.addEventListener("pointerup", onPointerUp);
    renderer.domElement.addEventListener("wheel", onWheel, { passive: false });

    const animate = () => {
      frame = window.requestAnimationFrame(animate);
      const t = performance.now() * 0.001;
      shaderMaterial.uniforms.uPulse.value = Math.sin(t * 1.6);
      if (splatPoints) {
        splatPoints.rotation.y += dragging ? 0 : cameraMode === "tour" ? 0.0018 : 0.0009;
      }
      focusBeacon.rotation.z = t * 1.1;
      focusBeacon.scale.setScalar(1 + Math.sin(t * 2.2) * (assistantCue ? 0.12 : 0.04));
      routeDot.position.copy(positionOnRoute((materialProgress + t * (assistantCue || cycle ? 0.08 : 0.025)) % 1));
      routeDot.position.y += Math.sin(t * 2.5) * 0.045;
      riskLight.intensity = 1.7 + sensorHeat * 1.2 + Math.sin(t * 2.2) * 0.2;
      camera.lookAt(cameraTarget);
      renderer.render(scene, camera);
    };
    animate();

    cleanupRef.current = () => {
      disposed = true;
      window.cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      renderer.domElement.removeEventListener("pointermove", onPointerMove);
      renderer.domElement.removeEventListener("pointerup", onPointerUp);
      renderer.domElement.removeEventListener("wheel", onWheel);
      shaderMaterial.dispose();
      renderer.dispose();
      host.innerHTML = "";
    };

    return cleanupRef.current;
  }, [
    activeZoneId,
    assistantCue,
    cameraMode,
    cycle,
    materialProgress,
    riskVariant,
    sensorHeat,
  ]);

  return (
    <section
      data-testid="labsim-3d-twin"
      data-labsim-stage="gaussian-splat"
      className="relative min-h-[46rem] overflow-hidden rounded-2xl bg-slate-950 xl:min-h-[calc(100vh-8rem)]"
      aria-label="Realistic Lab / Gaussian Splat"
    >
      <span data-testid="labsim-gaussian-splat-stage" className="sr-only">
        Realistic Lab / Gaussian Splat
      </span>
      <div ref={hostRef} className="absolute inset-0" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_48%_16%,rgba(186,230,253,0.18),transparent_32%),linear-gradient(180deg,rgba(2,6,23,0.05),rgba(2,6,23,0.76))]" />
      <div className="pointer-events-none absolute left-4 top-4 max-w-[17rem] rounded-xl border border-white/10 bg-slate-950/68 p-3 backdrop-blur">
        <p className="text-[0.64rem] uppercase tracking-[0.18em] text-cyan-100/70">Realistic Lab / Gaussian Splat</p>
        <h3 className="mt-1 text-sm font-semibold text-white">{preset.shortLabel} real lab proof</h3>
        <p className="mt-1 text-xs leading-5 text-surface-300">
          {`${form.species} on ${form.feedstock.replace(/_/g, " ")}`}
        </p>
      </div>
      <div
        data-testid="labsim-3d-replay-hud"
        className="pointer-events-none absolute left-4 top-[7.35rem] max-w-[17rem] rounded-xl border border-white/10 bg-slate-950/72 p-3 text-xs leading-5 text-surface-200 backdrop-blur"
      >
        <p className="uppercase tracking-[0.16em] text-cyan-100/70">Experiment phase</p>
        <p className="mt-1 uppercase tracking-[0.16em] text-cyan-100/60">Splat proof layer</p>
        <p className="mt-1 font-semibold text-white">{activeZone?.label ?? "Lab station"}</p>
        <p className="mt-1 text-surface-300">{activeZone?.detail ?? "Realistic stage keeps the BOS overlay review-only."}</p>
        <div className="mt-3">
          <div className="flex items-center justify-between gap-3 uppercase tracking-[0.14em] text-surface-500">
            <span>Material flow</span>
            <span>{cycle ? `${Math.round(materialProgress * 100)}%` : "standby"}</span>
          </div>
          <span data-testid="labsim-3d-material-flow" className="mt-1 block h-1.5 overflow-hidden rounded-full bg-white/10">
            <span className="block h-full rounded-full bg-cyan-200" style={{ width: `${Math.max(10, materialProgress * 100)}%` }} />
          </span>
        </div>
        <div data-testid="labsim-3d-phase-rail" className="mt-3 grid grid-cols-4 gap-1">
          {zoneOrder.map((zoneId) => (
            <span
              key={zoneId}
              className={[
                "truncate rounded-md border px-1.5 py-1 text-center text-[0.56rem] font-semibold uppercase tracking-[0.08em]",
                zoneId === activeZoneId
                  ? "border-cyan-100 bg-cyan-100 text-slate-950"
                  : "border-white/10 bg-white/[0.04] text-surface-500",
              ].join(" ")}
            >
              {zoneId === "pretreatment" ? "prep" : zoneId}
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
      <div className="pointer-events-none absolute right-4 top-4 flex max-w-[18rem] flex-wrap justify-end gap-2">
        <Badge variant={rendererState === "ready" ? "success" : "warning"}>{statusLabel}</Badge>
        <Badge variant="neutral">Visual replay only</Badge>
        <Badge variant="info">3D Lab Twin fallback retained</Badge>
        <Badge variant={cycle ? riskVariant : "neutral"}>{cycle ? `cycle ${cycle.cycle}` : "standby"}</Badge>
      </div>
      <div
        data-testid="labsim-3d-camera-modes"
        className="absolute right-4 top-[5.8rem] flex max-w-[17rem] flex-wrap justify-end gap-1.5"
        aria-label="Gaussian splat camera modes"
      >
        {(["overview", "focus", "tour"] as GaussianCameraMode[]).map((mode) => (
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
      <div className="pointer-events-none absolute inset-0">
        <svg className="absolute inset-0 h-full w-full" aria-hidden="true">
          <polyline
            points="9,27 24,31 42,48 47,24 13,73 43,74 70,35 70,68"
            vectorEffect="non-scaling-stroke"
            className="fill-none stroke-cyan-200/20"
            strokeWidth="2"
          />
          <polyline
            points="9,27 24,31 42,48 47,24 13,73 43,74 70,35 70,68"
            vectorEffect="non-scaling-stroke"
            className="fill-none stroke-cyan-100/80"
            strokeWidth="2"
            style={flowLineStyle}
          />
        </svg>
        {zones.map((zone, index) => {
          const selected = zone.id === selectedZoneId;
          const active = zone.id === activeZoneId;
          return (
            <button
              key={zone.id}
              type="button"
              data-testid={`labsim-3d-station-marker-${zone.id}`}
              className={[
                "pointer-events-auto absolute grid h-8 w-8 place-items-center rounded-full border text-xs font-bold shadow-lg backdrop-blur transition hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200",
                selected || active ? toneClasses[zone.tone] : "border-white/20 bg-slate-950/72 text-surface-100 hover:border-cyan-200/70",
              ].join(" ")}
              style={markerPositions[zone.id]}
              aria-label={`Station ${index + 1}: ${zone.label}`}
              aria-pressed={selected}
              onClick={() => onSelectZone(zone.id)}
            >
              {index + 1}
            </button>
          );
        })}
        {zones
          .filter((zone) => zone.id === selectedZoneId || (zone.id === activeZoneId && zone.id !== selectedZoneId))
          .map((zone) => {
            const selected = zone.id === selectedZoneId;
            return (
              <button
                key={`label-${zone.id}`}
                type="button"
                data-testid={`labsim-3d-station-label-${zone.id}`}
                className={[
                  "pointer-events-auto absolute max-w-[12rem] translate-x-9 rounded-lg border px-2.5 py-1.5 text-left text-[0.68rem] font-semibold leading-tight shadow-lg backdrop-blur transition",
                  selected
                    ? "border-cyan-100 bg-cyan-100 text-slate-950"
                    : "border-white/10 bg-slate-950/78 text-surface-100",
                ].join(" ")}
                style={markerPositions[zone.id]}
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
        data-testid="labsim-gaussian-metric-strip"
        className="pointer-events-none absolute bottom-4 left-4 right-4 grid gap-2 text-xs sm:grid-cols-4 lg:right-auto lg:max-w-[44rem]"
      >
        <GaussianMetric label="Risk" value={riskScore == null ? "pending" : formatPercent(riskScore, 1)} />
        <GaussianMetric label="Splat asset" value="local demo PLY placeholder" />
        <GaussianMetric label="Moisture" value={`${formatNumber(moistureLevel, 1)}%`} />
        <GaussianMetric label="Action" value={action} />
      </div>
      <div className="pointer-events-none absolute bottom-[6.25rem] right-4 max-w-[13rem] rounded-xl border border-white/10 bg-slate-950/64 p-2.5 text-[0.68rem] leading-5 text-surface-300 lg:bottom-4">
        Runtime blocked. Hardware execution blocked. Validated defaults locked.
      </div>
      {rendererState === "unavailable" ? (
        <div className="absolute inset-0 grid place-items-center bg-slate-950 text-center text-sm text-surface-300">
          Gaussian splat renderer unavailable in this environment; Digital Twin fallback remains available.
        </div>
      ) : null}
    </section>
  );
}

function GaussianMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/75 p-3 backdrop-blur">
      <p className="text-[0.62rem] uppercase tracking-[0.16em] text-surface-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function ensureColorAttribute(geometry: THREE.BufferGeometry) {
  if (geometry.getAttribute("color")) return;
  const position = geometry.getAttribute("position");
  const colors: number[] = [];
  for (let index = 0; index < position.count; index += 1) {
    const y = position.getY(index);
    const z = position.getZ(index);
    colors.push(0.2 + y * 0.12, 0.54 + z * 0.04, 0.62 + Math.max(0, y) * 0.08);
  }
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
}

function densifySplatGeometry(source: THREE.BufferGeometry) {
  const sourcePosition = source.getAttribute("position");
  const sourceColor = source.getAttribute("color");
  const positions: number[] = [];
  const colors: number[] = [];
  const samplesPerPoint = 18;

  for (let index = 0; index < sourcePosition.count; index += 1) {
    const x = sourcePosition.getX(index);
    const y = sourcePosition.getY(index);
    const z = sourcePosition.getZ(index);
    const red = sourceColor.getX(index);
    const green = sourceColor.getY(index);
    const blue = sourceColor.getZ(index);
    for (let sample = 0; sample < samplesPerPoint; sample += 1) {
      const ring = 0.035 + (sample % 6) * 0.012;
      const angle = sample * 2.399963 + index * 0.73;
      const vertical = ((sample % 5) - 2) * 0.018;
      positions.push(
        x + Math.cos(angle) * ring,
        y + vertical + Math.sin(index * 0.47 + sample) * 0.012,
        z + Math.sin(angle) * ring,
      );
      const tint = 0.9 + (sample % 4) * 0.035;
      colors.push(Math.min(1, red * tint), Math.min(1, green * tint), Math.min(1, blue * tint));
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  return geometry;
}

function mergeSplatGeometries(...sources: THREE.BufferGeometry[]) {
  const positions: number[] = [];
  const colors: number[] = [];
  sources.forEach((source) => {
    const sourcePosition = source.getAttribute("position");
    const sourceColor = source.getAttribute("color");
    for (let index = 0; index < sourcePosition.count; index += 1) {
      positions.push(sourcePosition.getX(index), sourcePosition.getY(index), sourcePosition.getZ(index));
      colors.push(sourceColor.getX(index), sourceColor.getY(index), sourceColor.getZ(index));
    }
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  return geometry;
}

function createFallbackSplatGeometry() {
  const positions: number[] = [];
  const colors: number[] = [];

  const pushPoint = (x: number, y: number, z: number, color: [number, number, number], seed: number) => {
    positions.push(
      x + Math.sin(seed * 1.7) * 0.018,
      y + Math.cos(seed * 1.3) * 0.014,
      z + Math.sin(seed * 2.1) * 0.018,
    );
    colors.push(color[0], color[1], color[2]);
  };

  const addPlane = ({
    color,
    countA,
    countB,
    fixedAxis,
    fixedValue,
    maxA,
    maxB,
    minA,
    minB,
  }: {
    color: [number, number, number];
    countA: number;
    countB: number;
    fixedAxis: "x" | "y" | "z";
    fixedValue: number;
    maxA: number;
    maxB: number;
    minA: number;
    minB: number;
  }) => {
    for (let a = 0; a < countA; a += 1) {
      for (let b = 0; b < countB; b += 1) {
        const valueA = minA + ((maxA - minA) * a) / Math.max(1, countA - 1);
        const valueB = minB + ((maxB - minB) * b) / Math.max(1, countB - 1);
        if (fixedAxis === "x") pushPoint(fixedValue, valueA, valueB, color, a * 31 + b);
        if (fixedAxis === "y") pushPoint(valueA, fixedValue, valueB, color, a * 31 + b);
        if (fixedAxis === "z") pushPoint(valueA, valueA * 0 + valueB, fixedValue, color, a * 31 + b);
      }
    }
  };

  const addCuboid = (center: [number, number, number], size: [number, number, number], color: [number, number, number]) => {
    const [cx, cy, cz] = center;
    const [sx, sy, sz] = size;
    for (let xStep = 0; xStep < 10; xStep += 1) {
      for (let zStep = 0; zStep < 8; zStep += 1) {
        const x = cx - sx / 2 + (sx * xStep) / 9;
        const z = cz - sz / 2 + (sz * zStep) / 7;
        pushPoint(x, cy + sy / 2, z, color, xStep * 17 + zStep);
      }
    }
    for (let xStep = 0; xStep < 10; xStep += 1) {
      for (let yStep = 0; yStep < 5; yStep += 1) {
        const x = cx - sx / 2 + (sx * xStep) / 9;
        const y = cy - sy / 2 + (sy * yStep) / 4;
        pushPoint(x, y, cz - sz / 2, color, xStep * 23 + yStep);
        pushPoint(x, y, cz + sz / 2, color, xStep * 29 + yStep);
      }
    }
  };

  addPlane({ fixedAxis: "y", fixedValue: -0.08, minA: -5.4, maxA: 5.2, minB: -3.4, maxB: 3.2, countA: 26, countB: 16, color: [0.08, 0.15, 0.23] });
  addPlane({ fixedAxis: "z", fixedValue: -3.35, minA: -5.4, maxA: 5.2, minB: 0.0, maxB: 3.2, countA: 26, countB: 11, color: [0.34, 0.42, 0.52] });
  addPlane({ fixedAxis: "x", fixedValue: -5.45, minA: 0.0, maxA: 2.7, minB: -3.35, maxB: 3.2, countA: 10, countB: 16, color: [0.22, 0.32, 0.42] });
  addCuboid([-4.0, 0.52, -2.2], [1.1, 0.55, 0.8], [0.12, 0.72, 0.82]);
  addCuboid([-2.2, 0.58, -2.0], [1.35, 0.62, 0.82], [0.55, 0.36, 0.95]);
  addCuboid([-3.6, 0.52, 0.25], [1.7, 0.55, 1.05], [0.22, 0.78, 0.56]);
  addCuboid([-3.2, 0.62, 2.15], [1.35, 0.55, 0.85], [0.1, 0.78, 0.9]);
  addCuboid([2.95, 0.75, -0.75], [1.45, 1.2, 0.85], [0.82, 0.32, 0.32]);
  addCuboid([3.05, 0.72, 1.65], [1.2, 1.05, 0.75], [0.58, 0.64, 0.72]);

  for (let index = 0; index < 220; index += 1) {
    const angle = index * 0.31;
    const radius = 0.58 + Math.sin(index * 0.17) * 0.08;
    const y = 0.32 + (index % 18) * 0.055;
    pushPoint(-0.4 + Math.cos(angle) * radius, y, 0.08 + Math.sin(angle) * radius, [0.9, 0.55, 0.14], index);
  }

  for (let index = 0; index < 120; index += 1) {
    const x = -0.2 + Math.sin(index * 0.61) * 0.18;
    const z = 2.2 + Math.cos(index * 0.47) * 0.18;
    const y = 0.28 + (index % 12) * 0.07;
    pushPoint(x, y, z, [0.66, 0.5, 0.96], index);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  return geometry;
}
