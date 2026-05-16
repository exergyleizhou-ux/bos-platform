import * as THREE from "three";

import type {
  BOSSceneSummary,
  PulseType,
  QualityTier,
} from "./rendererBackend";

type SceneDefinition = {
  id: string;
  label: string;
  labelEN: string;
  camPos: [number, number, number];
  camLook: [number, number, number];
  ambience: string;
  positions: Float32Array;
  colors: Float32Array;
  sizes: Float32Array;
  alphas: Float32Array;
  nativeLayers?: Partial<Record<LayerKind, LayerSource>>;
};

type SplatOptions = {
  particleCount?: number;
  autoFloat?: boolean;
  qualityTier?: QualityTier;
  reducedMotion?: boolean;
};

type CameraTarget = {
  pos: [number, number, number];
  look: [number, number, number];
  fov?: number;
};

type QualityProfile = {
  particleScale: number;
  opacityBoost: number;
  turbulence: number;
};

type LayerKind =
  | "ambientDust"
  | "signalFilaments"
  | "chargeNodes"
  | "haloMembrane"
  | "rareArcSparks"
  | "specialStructure";

const LAYER_ORDER: LayerKind[] = [
  "ambientDust",
  "signalFilaments",
  "chargeNodes",
  "haloMembrane",
  "rareArcSparks",
  "specialStructure",
];

type MutableLayerSource = {
  positions: number[];
  colors: number[];
  sizes: number[];
  alphas: number[];
};

type LayerAccumulator = Record<LayerKind, MutableLayerSource>;

type RuntimeLayer = {
  kind: LayerKind;
  points: THREE.Points<THREE.BufferGeometry, THREE.ShaderMaterial>;
  geometry: THREE.BufferGeometry;
  material: THREE.ShaderMaterial;
};

type LayerSource = {
  positions: Float32Array;
  colors: Float32Array;
  sizes: Float32Array;
  alphas: Float32Array;
};

type SceneCameraProfile = {
  baseFloatRadius: number;
  horizontalSpeed: number;
  verticalSpeed: number;
  verticalAmplitude: number;
  stableFov: number;
  chargedFov: number;
  successFov: number;
  failedFov: number;
  driftEasing: number;
  lookDrift: [number, number, number];
  chargedRadiusScale: number;
  successRadiusScale: number;
  failedRadiusScale: number;
  chargedVerticalBoost: number;
  successVerticalBoost: number;
  failedVerticalBoost: number;
};

export const QUALITY_PROFILES: Record<QualityTier, QualityProfile> = {
  low: { particleScale: 0.42, opacityBoost: 0.82, turbulence: 0.08 },
  medium: { particleScale: 0.62, opacityBoost: 0.92, turbulence: 0.12 },
  high: { particleScale: 0.82, opacityBoost: 1, turbulence: 0.16 },
  ultra: { particleScale: 1, opacityBoost: 1.08, turbulence: 0.22 },
};

export function degradeQualityTier(tier: QualityTier): QualityTier {
  if (tier === "ultra") return "high";
  if (tier === "high") return "medium";
  if (tier === "medium") return "low";
  return "low";
}

const GAUSSIAN_VERT_SHADER = `
  attribute float aSize;
  attribute float aAlpha;
  attribute vec3 aColor;

  varying float vAlpha;
  varying vec3 vColor;

  uniform float uTime;
  uniform float uBreath;
  uniform float uChargeState;
  uniform float uPulseState;
  uniform float uTrackingConfidence;
  uniform float uFreezeField;
  uniform vec3 uFieldAttractor;
  uniform float uFieldStrength;
  uniform vec3 uBurstCenter;
  uniform float uBurstIntensity;
  uniform float uTurbulence;
  uniform float uOpacityBoost;

  void main() {
    vec3 pos = position;
    float phase = position.x * 13.7 + position.y * 7.3 + position.z * 11.1;
    float breath = sin(uTime * 0.6 + phase) * 0.5 + 0.5;
    vec3 attract = uFieldAttractor - pos;
    float distToAttractor = max(length(attract), 0.001);
    pos += normalize(attract) * max(0.0, 1.0 - distToAttractor / 6.0) * uFieldStrength * 0.18;

    vec3 burst = pos - uBurstCenter;
    float burstDistance = max(length(burst), 0.001);
    pos += normalize(burst) * max(0.0, 1.0 - burstDistance / 4.2) * uBurstIntensity * 0.2;

    float turbulence = sin(uTime * (0.45 + uTurbulence) + phase) * 0.06 * (1.0 - uFreezeField);
    pos += vec3(
      sin(phase * 0.7),
      cos(phase * 0.9),
      sin(phase * 0.5)
    ) * turbulence;

    float pulse = 0.84 + breath * 0.28 + uBreath * 0.15 + uChargeState * 0.08 + uPulseState * 0.12;

    vColor = aColor;
    vAlpha = aAlpha * pulse * mix(0.75, 1.0, uTrackingConfidence) * uOpacityBoost;

    vec4 mvPos = modelViewMatrix * vec4(pos, 1.0);
    gl_Position = projectionMatrix * mvPos;

    float dist = -mvPos.z;
    gl_PointSize = clamp(aSize * pulse * (600.0 / max(dist, 1.0)), 1.0, 80.0);
  }
`;

const GAUSSIAN_FRAG_SHADER = `
  varying float vAlpha;
  varying vec3 vColor;

  void main() {
    vec2 uv = gl_PointCoord - vec2(0.5);
    float dist = length(uv) * 2.0;
    if (dist > 1.0) discard;

    float sigma = 0.5;
    float gaussian = exp(-(dist * dist) / (2.0 * sigma * sigma));
    float edge = smoothstep(1.0, 0.0, dist);
    float alpha = vAlpha * gaussian * edge;

    if (alpha < 0.005) discard;
    gl_FragColor = vec4(vColor, alpha);
  }
`;

class SceneDataGenerator {
  static createLayerAccumulator(): LayerAccumulator {
    return Object.fromEntries(
      LAYER_ORDER.map((kind) => [
        kind,
        { positions: [], colors: [], sizes: [], alphas: [] },
      ]),
    ) as unknown as LayerAccumulator;
  }

  static pushToLayer(
    layer: MutableLayerSource,
    position: [number, number, number],
    color: [number, number, number],
    size: number,
    alpha: number,
  ) {
    layer.positions.push(...position);
    layer.colors.push(...color);
    layer.sizes.push(size);
    layer.alphas.push(alpha);
  }

  static finalizeLayers(
    layers: LayerAccumulator,
  ): Partial<Record<LayerKind, LayerSource>> {
    return Object.fromEntries(
      LAYER_ORDER.map((kind) => [
        kind,
        {
          positions: new Float32Array(layers[kind].positions),
          colors: new Float32Array(layers[kind].colors),
          sizes: new Float32Array(layers[kind].sizes),
          alphas: new Float32Array(layers[kind].alphas),
        },
      ]),
    ) as Partial<Record<LayerKind, LayerSource>>;
  }

  static flattenLayers(
    nativeLayers: Partial<Record<LayerKind, LayerSource>>,
  ): Pick<SceneDefinition, "positions" | "colors" | "sizes" | "alphas"> {
    const positions: number[] = [];
    const colors: number[] = [];
    const sizes: number[] = [];
    const alphas: number[] = [];

    for (const kind of LAYER_ORDER) {
      const source = nativeLayers[kind];
      if (!source) continue;
      positions.push(...source.positions);
      colors.push(...source.colors);
      sizes.push(...source.sizes);
      alphas.push(...source.alphas);
    }

    return {
      positions: new Float32Array(positions),
      colors: new Float32Array(colors),
      sizes: new Float32Array(sizes),
      alphas: new Float32Array(alphas),
    };
  }

  static createSceneDefinition(
    input: Omit<SceneDefinition, "positions" | "colors" | "sizes" | "alphas"> & {
      nativeLayers: Partial<Record<LayerKind, LayerSource>>;
    },
  ): SceneDefinition {
    return {
      ...input,
      ...SceneDataGenerator.flattenLayers(input.nativeLayers),
    };
  }

  static gaussianRandom(mean = 0, std = 1) {
    let u = 0;
    let v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return mean + std * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  static randomOnSphere(r = 1): [number, number, number] {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    return [
      r * Math.sin(phi) * Math.cos(theta),
      r * Math.sin(phi) * Math.sin(theta),
      r * Math.cos(phi),
    ];
  }

  static generateNeuralCore(count = 18000): SceneDefinition {
    const G = SceneDataGenerator.gaussianRandom;
    const RS = SceneDataGenerator.randomOnSphere;
    const layers = SceneDataGenerator.createLayerAccumulator();

    const coreCount = Math.floor(count * 0.28);
    for (let index = 0; index < coreCount; index += 1) {
      const r = Math.abs(G(0, 0.28));
      const p = RS(r);
      const brightness = 1 - r * 0.6;
      SceneDataGenerator.pushToLayer(
        layers.chargeNodes,
        p,
        [0.08, brightness * 0.88 + 0.12, brightness * 0.95 + 0.05],
        3.4 + Math.random() * 4.6,
        0.42 + brightness * 0.42,
      );
    }

    const axonAnchors = Array.from({ length: 96 }, () => RS(0.55 + Math.random() * 1.9));
    const sheathAnchors = Array.from({ length: 72 }, () => RS(2.1 + Math.random() * 1.3));
    const axonCount = Math.floor(count * 0.34);
    for (let index = 0; index < axonCount; index += 1) {
      const from = axonAnchors[Math.floor(Math.random() * axonAnchors.length)] ?? [0, 0, 0];
      const to = sheathAnchors[Math.floor(Math.random() * sheathAnchors.length)] ?? [0, 0, 0];
      const t = Math.random();
      const p: [number, number, number] = [
        from[0] + (to[0] - from[0]) * t + G(0, 0.06),
        from[1] + (to[1] - from[1]) * t + G(0, 0.06),
        from[2] + (to[2] - from[2]) * t + G(0, 0.06),
      ];
      const dist = Math.hypot(p[0], p[1], p[2]);
      const fade = Math.max(0, 1 - dist / 3.6);
      SceneDataGenerator.pushToLayer(
        layers.signalFilaments,
        p,
        [0.02, 0.76 + fade * 0.18, 0.88 + fade * 0.08],
        1.2 + Math.random() * 2.2,
        0.12 + fade * 0.2,
      );
    }

    const membraneCount = Math.floor(count * 0.16);
    for (let index = 0; index < membraneCount; index += 1) {
      const shellRadius = 2.5 + G(0, 0.18);
      const p = RS(Math.abs(shellRadius));
      const rim = Math.max(0, 1 - Math.abs(shellRadius - 2.5) / 0.45);
      SceneDataGenerator.pushToLayer(
        layers.haloMembrane,
        p,
        [0.02, 0.56 + rim * 0.18, 0.68 + rim * 0.16],
        2.8 + Math.random() * 4.1,
        0.06 + rim * 0.08,
      );
    }

    const sparkCount = Math.floor(count * 0.05);
    for (let index = 0; index < sparkCount; index += 1) {
      const anchor = axonAnchors[Math.floor(Math.random() * axonAnchors.length)] ?? [0, 0, 0];
      const p: [number, number, number] = [
        anchor[0] + G(0, 0.04),
        anchor[1] + G(0, 0.04),
        anchor[2] + G(0, 0.04),
      ];
      SceneDataGenerator.pushToLayer(
        layers.rareArcSparks,
        p,
        [0.45, 1, 1],
        2.2 + Math.random() * 3,
        0.22 + Math.random() * 0.18,
      );
    }

    const structureCount = Math.floor(count * 0.08);
    for (let index = 0; index < structureCount; index += 1) {
      const arm = ((index % 3) / 3) * Math.PI * 2 + Math.random() * 0.12;
      const t = Math.random();
      const radius = 0.4 + t * 1.2;
      const p: [number, number, number] = [
        Math.cos(arm) * radius + G(0, 0.025),
        (t - 0.5) * 0.9 + G(0, 0.03),
        Math.sin(arm) * radius + G(0, 0.025),
      ];
      SceneDataGenerator.pushToLayer(
        layers.specialStructure,
        p,
        [0.08, 0.8 + (1 - t) * 0.14, 0.92 + (1 - t) * 0.06],
        1.8 + (1 - t) * 2.4,
        0.16 + (1 - t) * 0.18,
      );
    }

    const hazeCount = Math.floor(count * 0.09);
    for (let index = 0; index < hazeCount; index += 1) {
      const p = RS(2 + Math.random() * 2.5);
      SceneDataGenerator.pushToLayer(
        layers.ambientDust,
        p,
        [0, 0.5 + Math.random() * 0.16, 0.62 + Math.random() * 0.16],
        3.8 + Math.random() * 6.5,
        0.03 + Math.random() * 0.04,
      );
    }

    return SceneDataGenerator.createSceneDefinition({
      id: "neural_core",
      label: "神经核心",
      labelEN: "NEURAL CORE",
      camPos: [0, 0.5, 5.5],
      camLook: [0, 0, 0],
      ambience: "#00C8D4",
      nativeLayers: SceneDataGenerator.finalizeLayers(layers),
    });
  }

  static generateReactorInterior(count = 22000): SceneDefinition {
    const G = SceneDataGenerator.gaussianRandom;
    const RS = SceneDataGenerator.randomOnSphere;
    const layers = SceneDataGenerator.createLayerAccumulator();

    const shellCount = Math.floor(count * 0.35);
    for (let index = 0; index < shellCount; index += 1) {
      const shellR = 2.2 + G(0, 0.08);
      const p = RS(Math.abs(shellR));
      const lat = p[1] / Math.abs(shellR);
      const bright = 0.5 + lat * 0.3;
      SceneDataGenerator.pushToLayer(
        layers.haloMembrane,
        p,
        [0.02, bright * 0.8, bright * 0.9],
        1.8 + Math.random() * 2.9,
        0.2 + Math.random() * 0.15,
      );
    }

    const armAngles = [
      Math.PI * 1.5,
      Math.PI * 1.5 + (Math.PI * 2) / 3,
      Math.PI * 1.5 + (Math.PI * 4) / 3,
    ];
    const armCount = Math.floor(count * 0.2);
    for (const angle of armAngles) {
      const perArm = Math.floor(armCount / 3);
      for (let index = 0; index < perArm; index += 1) {
        const t = Math.random();
        const r = t * 1.6;
        const p: [number, number, number] = [
          Math.cos(angle) * r + G(0, 0.05),
          G(0, 0.04),
          Math.sin(angle) * r + G(0, 0.05),
        ];
        const intensity = 1 - t * 0.4;
        SceneDataGenerator.pushToLayer(
          layers.specialStructure,
          p,
          [intensity * 0.1, intensity * 0.9, intensity * 0.97],
          2.4 + (1 - t) * 4.2,
          0.34 + intensity * 0.34,
        );
      }
    }

    const vortexCount = Math.floor(count * 0.25);
    for (let index = 0; index < vortexCount; index += 1) {
      const t = index / vortexCount;
      const angle = t * Math.PI * 16;
      const r = 0.3 + t * 1.8;
      const p: [number, number, number] = [
        Math.cos(angle) * r + G(0, 0.08),
        (t - 0.5) * 3 + G(0, 0.06),
        Math.sin(angle) * r + G(0, 0.08),
      ];
      const bright = 0.5 + (1 - t) * 0.5;
      SceneDataGenerator.pushToLayer(
        layers.signalFilaments,
        p,
        [0, bright * 0.82, bright * 0.92],
        1.5 + Math.random() * 3,
        0.15 + bright * 0.2,
      );
    }

    const coreCount = Math.floor(count * 0.05);
    for (let index = 0; index < coreCount; index += 1) {
      const p = RS(Math.abs(G(0, 0.15)));
      SceneDataGenerator.pushToLayer(
        layers.chargeNodes,
        p,
        [0.6, 1, 1],
        3.2 + Math.random() * 5.4,
        0.52 + Math.random() * 0.34,
      );
    }

    const hazeCount = Math.floor(count * 0.15);
    for (let index = 0; index < hazeCount; index += 1) {
      const p = RS(2.5 + Math.random() * 1.5);
      SceneDataGenerator.pushToLayer(
        layers.ambientDust,
        p,
        [0, 0.5, 0.6],
        6 + Math.random() * 12,
        0.03 + Math.random() * 0.04,
      );
    }

    const cavityCount = Math.floor(count * 0.06);
    for (let index = 0; index < cavityCount; index += 1) {
      const p = RS(4.4 + G(0, 0.18));
      SceneDataGenerator.pushToLayer(
        layers.haloMembrane,
        p,
        [0.02, 0.36, 0.46],
        2.2 + Math.random() * 4.2,
        0.03 + Math.random() * 0.05,
      );
    }

    return SceneDataGenerator.createSceneDefinition({
      id: "reactor_interior",
      label: "反应堆内核",
      labelEN: "REACTOR INTERIOR",
      camPos: [0, 1.5, 6],
      camLook: [0, 0, 0],
      ambience: "#00C8D4",
      nativeLayers: SceneDataGenerator.finalizeLayers(layers),
    });
  }

  static generateSynapticWeb(count = 14000): SceneDefinition {
    const G = SceneDataGenerator.gaussianRandom;
    const RS = SceneDataGenerator.randomOnSphere;
    const layers = SceneDataGenerator.createLayerAccumulator();

    const synapses = Array.from({ length: 200 }, () => RS(0.5 + Math.random() * 4));
    const nodeCount = Math.floor(count * 0.15);
    for (const synapse of synapses) {
      const perNode = Math.max(1, Math.floor(nodeCount / synapses.length));
      for (let index = 0; index < perNode; index += 1) {
        const r = Math.abs(G(0, 0.12));
        const p: [number, number, number] = [
          synapse[0] + G(0, r),
          synapse[1] + G(0, r),
          synapse[2] + G(0, r),
        ];
        const bright = 0.7 + Math.random() * 0.3;
        SceneDataGenerator.pushToLayer(
          layers.chargeNodes,
          p,
          [0, bright * 0.85, bright * 0.95],
          3.4 + Math.random() * 5.6,
          0.38 + bright * 0.28,
        );
      }
    }

    const connCount = Math.floor(count * 0.6);
    for (let index = 0; index < connCount; index += 1) {
      const from = synapses[Math.floor(Math.random() * synapses.length)] ?? [0, 0, 0];
      const to = synapses[Math.floor(Math.random() * synapses.length)] ?? [0, 0, 0];
      const dist = Math.hypot(from[0] - to[0], from[1] - to[1], from[2] - to[2]);
      if (dist > 3.5) continue;
      const t = Math.random();
      const p: [number, number, number] = [
        from[0] + (to[0] - from[0]) * t + G(0, 0.04),
        from[1] + (to[1] - from[1]) * t + G(0, 0.04),
        from[2] + (to[2] - from[2]) * t + G(0, 0.04),
      ];
      const fade = 1 - Math.abs(t - 0.5) * 2;
      SceneDataGenerator.pushToLayer(
        layers.signalFilaments,
        p,
        [0, 0.65 + fade * 0.2, 0.75 + fade * 0.15],
        0.9 + Math.random() * 1.4,
        0.06 + fade * 0.12,
      );
    }

    const bgCount = Math.floor(count * 0.25);
    for (let index = 0; index < bgCount; index += 1) {
      const p = RS(3.5 + Math.random() * 3);
      SceneDataGenerator.pushToLayer(
        layers.ambientDust,
        p,
        [0, 0.4, 0.5],
        2 + Math.random() * 5,
        0.02 + Math.random() * 0.04,
      );
    }

    const cavityCount = Math.floor(count * 0.06);
    for (let index = 0; index < cavityCount; index += 1) {
      const p = RS(4.4 + G(0, 0.18));
      SceneDataGenerator.pushToLayer(
        layers.haloMembrane,
        p,
        [0.02, 0.36, 0.46],
        2.2 + Math.random() * 4.2,
        0.03 + Math.random() * 0.05,
      );
    }

    return SceneDataGenerator.createSceneDefinition({
      id: "synaptic_web",
      label: "突触网络",
      labelEN: "SYNAPTIC WEB",
      camPos: [1.5, 1, 5],
      camLook: [0, 0, 0],
      ambience: "#00A8B8",
      nativeLayers: SceneDataGenerator.finalizeLayers(layers),
    });
  }

  static generateDataVoid(count = 10000): SceneDefinition {
    const G = SceneDataGenerator.gaussianRandom;
    const RS = SceneDataGenerator.randomOnSphere;
    const layers = SceneDataGenerator.createLayerAccumulator();

    const streams = [
      { dir: [0.6, 0.1, 0.8] as const, color: [0, 0.9, 1] as const, spread: 0.06 },
      { dir: [-0.8, 0.3, 0.5] as const, color: [0.1, 0.8, 0.9] as const, spread: 0.05 },
      { dir: [0.2, -0.7, 0.7] as const, color: [0, 0.75, 0.85] as const, spread: 0.07 },
    ];

    const streamCount = Math.floor(count * 0.5);
    for (const stream of streams) {
      const perStream = Math.floor(streamCount / streams.length);
      for (let index = 0; index < perStream; index += 1) {
        const t = (Math.random() - 0.5) * 8;
        const p: [number, number, number] = [
          stream.dir[0] * t + G(0, stream.spread),
          stream.dir[1] * t + G(0, stream.spread),
          stream.dir[2] * t + G(0, stream.spread),
        ];
        const near = 1 - Math.abs(t) / 4;
        SceneDataGenerator.pushToLayer(
          layers.signalFilaments,
          p,
          [
            stream.color[0] * (0.6 + near * 0.4),
            stream.color[1] * (0.6 + near * 0.4),
            stream.color[2] * (0.6 + near * 0.4),
          ],
          1 + near * 3,
          0.08 + near * 0.35,
        );
      }
    }

    const isolatedCount = Math.floor(count * 0.3);
    for (let index = 0; index < isolatedCount; index += 1) {
      const p = RS(4 + Math.random() * 5);
      SceneDataGenerator.pushToLayer(
        layers.ambientDust,
        p,
        [0, 0.35 + Math.random() * 0.15, 0.45 + Math.random() * 0.1],
        0.5 + Math.random() * 1.5,
        0.02 + Math.random() * 0.03,
      );
    }

    const singularCount = Math.floor(count * 0.05);
    for (let index = 0; index < singularCount; index += 1) {
      const p = RS(Math.abs(G(0, 0.08)));
      SceneDataGenerator.pushToLayer(
        layers.chargeNodes,
        p,
        [0.8, 1, 1],
        4 + Math.random() * 8,
        0.55 + Math.random() * 0.4,
      );
    }

    const rainCount = Math.floor(count * 0.15);
    for (let index = 0; index < rainCount; index += 1) {
      const x = G(0, 3);
      const z = G(0, 3);
      const y = (Math.random() - 0.5) * 8;
      const p: [number, number, number] = [x + G(0, 0.02), y, z + G(0, 0.02)];
      const near = Math.max(0, 1 - Math.abs(y) / 4);
      SceneDataGenerator.pushToLayer(
        layers.rareArcSparks,
        p,
        [0, 0.6 + near * 0.3, 0.7 + near * 0.2],
        0.8 + near * 2,
        0.05 + near * 0.15,
      );
    }

    const shellCount = Math.floor(count * 0.06);
    for (let index = 0; index < shellCount; index += 1) {
      const p = RS(5.8 + G(0, 0.24));
      SceneDataGenerator.pushToLayer(
        layers.haloMembrane,
        p,
        [0, 0.24, 0.34],
        1.8 + Math.random() * 3.4,
        0.02 + Math.random() * 0.03,
      );
    }

    return SceneDataGenerator.createSceneDefinition({
      id: "data_void",
      label: "数据虚空",
      labelEN: "DATA VOID",
      camPos: [-2, 0.5, 6],
      camLook: [0, 0, 0],
      ambience: "#006878",
      nativeLayers: SceneDataGenerator.finalizeLayers(layers),
    });
  }

  static generateBioMatrix(count = 20000): SceneDefinition {
    const G = SceneDataGenerator.gaussianRandom;
    const RS = SceneDataGenerator.randomOnSphere;
    const layers = SceneDataGenerator.createLayerAccumulator();

    const gridSize = 5;
    const spacing = 0.9;
    for (let xi = -gridSize; xi <= gridSize; xi += 1) {
      for (let yi = -gridSize; yi <= gridSize; yi += 1) {
        for (let zi = -gridSize; zi <= gridSize; zi += 1) {
          if (Math.random() > 0.5) continue;
          const x = xi * spacing + G(0, 0.12);
          const y = yi * spacing + G(0, 0.12);
          const z = zi * spacing + G(0, 0.12);
          const r = Math.hypot(x, y, z);
          if (r > 4.5) continue;
          const perNode = Math.floor(Math.random() * 3) + 1;
          for (let index = 0; index < perNode; index += 1) {
            const p: [number, number, number] = [x + G(0, 0.05), y + G(0, 0.05), z + G(0, 0.05)];
            const fade = 1 - r / 4.5;
            const isGreen = Math.random() < 0.08;
            SceneDataGenerator.pushToLayer(
              isGreen ? layers.chargeNodes : layers.specialStructure,
              p,
              [0, isGreen ? 0.9 : 0.72 + fade * 0.2, isGreen ? 0.6 : 0.82 + fade * 0.1],
              2 + fade * 3,
              0.2 + fade * 0.35,
            );
          }
        }
      }
    }

    const edgeCount = Math.floor(count * 0.35);
    for (let index = 0; index < edgeCount; index += 1) {
      const xi = Math.floor((Math.random() * 2 - 1) * gridSize);
      const yi = Math.floor((Math.random() * 2 - 1) * gridSize);
      const zi = Math.floor((Math.random() * 2 - 1) * gridSize);
      const axis = Math.floor(Math.random() * 3);
      const t = Math.random();
      const x = xi * spacing + (axis === 0 ? spacing : 0) * t + G(0, 0.04);
      const y = yi * spacing + (axis === 1 ? spacing : 0) * t + G(0, 0.04);
      const z = zi * spacing + (axis === 2 ? spacing : 0) * t + G(0, 0.04);
      const r = Math.hypot(x, y, z);
      if (r > 4.5) continue;
      const fade = 1 - r / 4.5;
      SceneDataGenerator.pushToLayer(
        layers.signalFilaments,
        [x, y, z],
        [0, 0.6 + fade * 0.2, 0.72 + fade * 0.1],
        0.8 + Math.random() * 1.5,
        0.08 + fade * 0.12,
      );
    }

    const membraneCount = Math.floor(count * 0.15);
    for (let index = 0; index < membraneCount; index += 1) {
      const p = RS(Math.abs(4 + G(0, 0.15)));
      SceneDataGenerator.pushToLayer(
        layers.haloMembrane,
        p,
        [0, 0.55, 0.65],
        3 + Math.random() * 6,
        0.04 + Math.random() * 0.06,
      );
    }

    const coreCount = Math.floor(count * 0.1);
    for (let index = 0; index < coreCount; index += 1) {
      const r = Math.abs(G(0, 0.5));
      const p = RS(r);
      const bright = Math.max(0, 1 - r);
      SceneDataGenerator.pushToLayer(
        layers.chargeNodes,
        p,
        [0, 0.85 + bright * 0.15, 0.92 + bright * 0.08],
        2 + bright * 5,
        0.3 + bright * 0.5,
      );
    }

    const dustCount = Math.floor(count * 0.06);
    for (let index = 0; index < dustCount; index += 1) {
      const p = RS(4.8 + Math.random() * 1.4);
      SceneDataGenerator.pushToLayer(
        layers.ambientDust,
        p,
        [0, 0.28 + Math.random() * 0.1, 0.34 + Math.random() * 0.08],
        1.2 + Math.random() * 2.6,
        0.015 + Math.random() * 0.025,
      );
    }

    return SceneDataGenerator.createSceneDefinition({
      id: "bio_matrix",
      label: "生物矩阵",
      labelEN: "BIO MATRIX",
      camPos: [2.5, 1.5, 5.5],
      camLook: [0, 0, 0],
      ambience: "#00D480",
      nativeLayers: SceneDataGenerator.finalizeLayers(layers),
    });
  }
}

const SCENE_ORDER = [
  "neural_core",
  "reactor_interior",
  "synaptic_web",
  "data_void",
  "bio_matrix",
] as const;

const SCENE_LABELS: Record<
  (typeof SCENE_ORDER)[number],
  { label: string; labelEN: string; ambience: string }
> = {
  neural_core: {
    label: "神经核心",
    labelEN: "NEURAL CORE",
    ambience: "#00C8D4",
  },
  reactor_interior: {
    label: "反应堆内核",
    labelEN: "REACTOR INTERIOR",
    ambience: "#00C8D4",
  },
  synaptic_web: {
    label: "突触网络",
    labelEN: "SYNAPTIC WEB",
    ambience: "#00A8B8",
  },
  data_void: {
    label: "数据虚空",
    labelEN: "DATA VOID",
    ambience: "#006878",
  },
  bio_matrix: {
    label: "生物矩阵",
    labelEN: "BIO MATRIX",
    ambience: "#00D480",
  },
};

const SCENE_CAMERA_PROFILES: Record<(typeof SCENE_ORDER)[number], SceneCameraProfile> = {
  neural_core: {
    baseFloatRadius: 5.2,
    horizontalSpeed: 0.034,
    verticalSpeed: 0.018,
    verticalAmplitude: 0.24,
    stableFov: 56,
    chargedFov: 52,
    successFov: 58,
    failedFov: 60,
    driftEasing: 0.0032,
    lookDrift: [0, 0.12, 0],
    chargedRadiusScale: 0.84,
    successRadiusScale: 1.04,
    failedRadiusScale: 1.08,
    chargedVerticalBoost: 0.18,
    successVerticalBoost: 0.1,
    failedVerticalBoost: -0.04,
  },
  reactor_interior: {
    baseFloatRadius: 5.8,
    horizontalSpeed: 0.028,
    verticalSpeed: 0.014,
    verticalAmplitude: 0.18,
    stableFov: 52,
    chargedFov: 48,
    successFov: 55,
    failedFov: 58,
    driftEasing: 0.0028,
    lookDrift: [0, -0.06, 0],
    chargedRadiusScale: 0.78,
    successRadiusScale: 0.94,
    failedRadiusScale: 1.06,
    chargedVerticalBoost: -0.08,
    successVerticalBoost: 0.04,
    failedVerticalBoost: -0.16,
  },
  synaptic_web: {
    baseFloatRadius: 6.3,
    horizontalSpeed: 0.022,
    verticalSpeed: 0.011,
    verticalAmplitude: 0.12,
    stableFov: 58,
    chargedFov: 54,
    successFov: 61,
    failedFov: 63,
    driftEasing: 0.0026,
    lookDrift: [0.18, 0, 0],
    chargedRadiusScale: 0.9,
    successRadiusScale: 1.08,
    failedRadiusScale: 1.14,
    chargedVerticalBoost: 0.06,
    successVerticalBoost: 0.12,
    failedVerticalBoost: -0.02,
  },
  data_void: {
    baseFloatRadius: 6.9,
    horizontalSpeed: 0.018,
    verticalSpeed: 0.009,
    verticalAmplitude: 0.09,
    stableFov: 60,
    chargedFov: 56,
    successFov: 63,
    failedFov: 65,
    driftEasing: 0.0022,
    lookDrift: [-0.14, -0.08, 0.24],
    chargedRadiusScale: 0.76,
    successRadiusScale: 1.12,
    failedRadiusScale: 1.18,
    chargedVerticalBoost: -0.05,
    successVerticalBoost: 0.08,
    failedVerticalBoost: -0.14,
  },
  bio_matrix: {
    baseFloatRadius: 5.9,
    horizontalSpeed: 0.025,
    verticalSpeed: 0.013,
    verticalAmplitude: 0.16,
    stableFov: 54,
    chargedFov: 50,
    successFov: 57,
    failedFov: 59,
    driftEasing: 0.0029,
    lookDrift: [0.08, 0.16, 0],
    chargedRadiusScale: 0.82,
    successRadiusScale: 0.98,
    failedRadiusScale: 1.04,
    chargedVerticalBoost: 0.1,
    successVerticalBoost: 0.14,
    failedVerticalBoost: -0.06,
  },
};

export function generateProceduralSceneDefinition(
  sceneId: (typeof SCENE_ORDER)[number],
  particleCount = 18000,
): SceneDefinition {
  switch (sceneId) {
    case "neural_core":
      return SceneDataGenerator.generateNeuralCore(particleCount);
    case "reactor_interior":
      return SceneDataGenerator.generateReactorInterior(Math.floor(particleCount * 1.2));
    case "synaptic_web":
      return SceneDataGenerator.generateSynapticWeb(Math.floor(particleCount * 0.8));
    case "data_void":
      return SceneDataGenerator.generateDataVoid(Math.floor(particleCount * 0.6));
    case "bio_matrix":
      return SceneDataGenerator.generateBioMatrix(Math.floor(particleCount * 1.1));
  }
}

export class BOSSplatSystem extends EventTarget {
  readonly kind = "procedural" as const;
  private readonly options: Required<SplatOptions>;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly camera: THREE.PerspectiveCamera;
  private readonly scene = new THREE.Scene();
  private readonly clock = new THREE.Clock();
  private readonly uniforms = {
    uTime: { value: 0 },
    uBreath: { value: 0 },
    uChargeState: { value: 0 },
    uPulseState: { value: 0 },
    uTrackingConfidence: { value: 1 },
    uFreezeField: { value: 0 },
    uFieldAttractor: { value: new THREE.Vector3(0, 0, 0) },
    uFieldStrength: { value: 0 },
    uBurstCenter: { value: new THREE.Vector3(0, 0, 0) },
    uBurstIntensity: { value: 0 },
    uTurbulence: { value: 0.16 },
    uOpacityBoost: { value: 1 },
  };
  private readonly sceneMap = new Map<string, SceneDefinition>();

  private readonly layerGroup = new THREE.Group();
  private layers: RuntimeLayer[] = [];
  private currentScene: SceneDefinition | null = null;
  private cameraTarget: CameraTarget | null = null;
  private frameHandle: number | null = null;
  private running = false;
  private breathPhase = 0;
  private autoFloatEnabled = true;
  private qualityTier: QualityTier;
  private readonly reducedMotion: boolean;
  private fps = 60;
  private frameAccumulator = 0;
  private frameSamples = 0;
  private lastPerfAt = performance.now();
  private performanceCooldownUntil = 0;
  private chargeState = 0;
  private pulseState = 0;
  private trackingConfidence = 1;
  private fieldFrozen = false;
  private fieldAttractor = new THREE.Vector3(0, 0, 0);
  private fieldStrength = 0;
  private burstCenter = new THREE.Vector3(0, 0, 0);
  private burstIntensity = 0;
  private gestureFocus: string | null = null;
  private cameraState: "stable" | "charged" | "success" | "failed" = "stable";

  constructor(canvas: HTMLCanvasElement, options: SplatOptions = {}) {
    super();
    this.reducedMotion =
      options.reducedMotion ??
      window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ??
      false;
    this.qualityTier = options.qualityTier ?? (this.reducedMotion ? "medium" : "high");
    this.options = {
      particleCount: options.particleCount ?? 18000,
      autoFloat: options.autoFloat ?? true,
      qualityTier: this.qualityTier,
      reducedMotion: this.reducedMotion,
    };
    this.autoFloatEnabled = this.options.autoFloat;
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: false,
      powerPreference: "high-performance",
      preserveDrawingBuffer: true,
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setClearColor(0x000000, 0);
    this.scene.add(this.layerGroup);

    this.camera = new THREE.PerspectiveCamera(
      60,
      window.innerWidth / window.innerHeight,
      0.1,
      100,
    );
    this.camera.position.set(0, 0.5, 5.5);
    this.resize();
    this.pregenScenes();
  }

  pregenScenes() {
    window.setTimeout(() => {
      const baseCount = this.options.particleCount;
      const scenes = SCENE_ORDER.map((sceneId) =>
        generateProceduralSceneDefinition(sceneId, baseCount),
      );
      for (const scene of scenes) {
        this.sceneMap.set(scene.id, scene);
      }
      this.dispatchEvent(new Event("scenesready"));
      this.loadScene(SCENE_ORDER[0]);
    }, 80);
  }

  getSceneList(): BOSSceneSummary[] {
    return SCENE_ORDER.map((id) => {
      const scene = this.sceneMap.get(id);
      const clean = SCENE_LABELS[id];
      return scene
        ? {
            id: scene.id,
            label: clean.label,
            labelEN: clean.labelEN,
            ambience: clean.ambience,
          }
        : {
            id,
            label: clean.label,
            labelEN: clean.labelEN,
            ambience: clean.ambience,
          };
    });
  }

  getCurrentSceneInfo(): BOSSceneSummary | null {
    if (!this.currentScene) return null;
    const clean = SCENE_LABELS[this.currentScene.id as (typeof SCENE_ORDER)[number]];
    return {
      id: this.currentScene.id,
      label: clean?.label ?? this.currentScene.label,
      labelEN: clean?.labelEN ?? this.currentScene.labelEN,
      ambience: clean?.ambience ?? this.currentScene.ambience,
    };
  }

  getQualityTier(): QualityTier {
    return this.qualityTier;
  }

  setQualityTier(tier: QualityTier) {
    if (tier === this.qualityTier) return;
    this.qualityTier = tier;
    this.options.qualityTier = tier;
    this.rebuildCurrentScene();
  }

  getStats() {
    return {
      fps: this.fps,
      qualityTier: this.qualityTier,
    };
  }

  loadScene(sceneId: string) {
    const data = this.sceneMap.get(sceneId);
    if (!data) return null;

    this.disposeLayers();
    this.layers = this.buildLayers(data);
    this.layers.forEach((layer) => this.layerGroup.add(layer.points));
    this.currentScene = data;
    this.cameraTarget = {
      pos: data.camPos,
      look: data.camLook,
      fov: this.computeTargetFov(),
    };
    const summary = this.getCurrentSceneInfo();
    if (summary) {
      this.dispatchEvent(new CustomEvent<BOSSceneSummary>("scenechange", { detail: summary }));
    }
    return summary;
  }

  nextScene(direction: 1 | -1 = 1) {
    const currentId = this.currentScene?.id ?? SCENE_ORDER[0];
    const currentIndex = Math.max(0, SCENE_ORDER.indexOf(currentId as (typeof SCENE_ORDER)[number]));
    const nextIndex = (currentIndex + direction + SCENE_ORDER.length) % SCENE_ORDER.length;
    return this.loadScene(SCENE_ORDER[nextIndex]);
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.clock.start();
    this.renderLoop();
  }

  stop() {
    this.running = false;
    if (this.frameHandle != null) {
      window.cancelAnimationFrame(this.frameHandle);
      this.frameHandle = null;
    }
  }

  dispose() {
    this.stop();
    this.disposeLayers();
    this.renderer.dispose();
  }

  setBreathPhase(phase: number) {
    this.breathPhase = phase;
  }

  setAutoFloatEnabled(enabled: boolean) {
    this.autoFloatEnabled = enabled;
  }

  setFieldAttractor(x: number, y: number, strength: number) {
    this.fieldAttractor.set(x, y, 0);
    this.fieldStrength = Math.max(0, strength);
  }

  setChargeState(level: number) {
    this.chargeState = THREE.MathUtils.clamp(level, 0, 1.4);
    this.cameraState = this.chargeState > 0.72 ? "charged" : "stable";
  }

  triggerPulse(type: PulseType) {
    this.pulseState =
      type === "burst"
        ? 1.2
        : type === "success"
          ? 1
          : type === "confirm"
            ? 0.74
            : type === "disturbance"
              ? 0.42
              : 0.28;
    if (type === "success") {
      this.cameraState = "success";
    } else if (type === "disturbance") {
      this.cameraState = "failed";
    }
  }

  freezeField(flag: boolean) {
    this.fieldFrozen = flag;
    this.autoFloatEnabled = !flag;
  }

  burstField(center: { x: number; y: number; z?: number }, intensity: number) {
    this.burstCenter.set(center.x, center.y, center.z ?? 0);
    this.burstIntensity = Math.max(this.burstIntensity, intensity);
  }

  setGestureFocus(target: string | null) {
    this.gestureFocus = target;
  }

  setTrackingConfidence(value: number) {
    this.trackingConfidence = THREE.MathUtils.clamp(value, 0, 1);
  }

  orbitCamera(dx: number, dy: number) {
    if (!this.currentScene) return;
    const look = new THREE.Vector3(...this.currentScene.camLook);
    const offset = this.camera.position.clone().sub(look);
    const spherical = new THREE.Spherical().setFromVector3(offset);
    spherical.theta -= dx * 0.012;
    spherical.phi += dy * 0.008;
    spherical.phi = Math.max(0.15, Math.min(Math.PI - 0.15, spherical.phi));
    this.camera.position.setFromSpherical(spherical).add(look);
    this.camera.lookAt(look);
    this.cameraTarget = null;
  }

  zoomCamera(delta: number) {
    if (!this.currentScene) return;
    const look = new THREE.Vector3(...this.currentScene.camLook);
    const dir = look.clone().sub(this.camera.position).normalize();
    this.camera.position.addScaledVector(dir, delta * 0.35);
    this.camera.lookAt(look);
    this.cameraTarget = null;
  }

  rotateScene(dx: number, dy: number) {
    this.layerGroup.rotation.y += dx * 0.004;
    this.layerGroup.rotation.x += dy * 0.003;
  }

  resize() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  captureSnapshotDataUrl() {
    try {
      this.renderer.render(this.scene, this.camera);
      return this.renderer.domElement.toDataURL("image/webp", 0.72);
    } catch {
      return null;
    }
  }

  private renderLoop = () => {
    if (!this.running) return;
    this.frameHandle = window.requestAnimationFrame(this.renderLoop);
    const now = performance.now();
    const elapsed = this.clock.getElapsedTime();
    const dt = now - this.lastPerfAt;
    this.lastPerfAt = now;
    this.uniforms.uTime.value = elapsed;
    this.uniforms.uBreath.value = this.breathPhase;
    this.updateFieldState(dt);
    this.updateLayerUniforms();
    this.updatePerformance(dt);
    if (this.autoFloatEnabled) {
      this.updateAutoFloat(elapsed);
    }
    this.interpolateCamera();
    this.renderer.render(this.scene, this.camera);
  };

  private rebuildCurrentScene() {
    if (!this.currentScene) return;
    this.loadScene(this.currentScene.id);
  }

  private createRuntimeLayer(
    kind: LayerKind,
    source: MutableLayerSource,
  ): RuntimeLayer | null {
    if (source.sizes.length === 0) return null;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(source.positions, 3));
    geometry.setAttribute("aColor", new THREE.Float32BufferAttribute(source.colors, 3));
    geometry.setAttribute("aSize", new THREE.Float32BufferAttribute(source.sizes, 1));
    geometry.setAttribute("aAlpha", new THREE.Float32BufferAttribute(source.alphas, 1));
    const material = new THREE.ShaderMaterial({
      vertexShader: GAUSSIAN_VERT_SHADER,
      fragmentShader: GAUSSIAN_FRAG_SHADER,
      uniforms: this.uniforms,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const points = new THREE.Points(geometry, material);
    return { kind, geometry, material, points };
  }

  private buildLayers(data: SceneDefinition): RuntimeLayer[] {
    const quality = QUALITY_PROFILES[this.qualityTier];
    if (data.nativeLayers) {
      return LAYER_ORDER.flatMap((kind) => {
        const source = data.nativeLayers?.[kind];
        if (!source || source.sizes.length === 0) return [];
        const sampled: MutableLayerSource = {
          positions: [],
          colors: [],
          sizes: [],
          alphas: [],
        };
        for (let index = 0; index < source.sizes.length; index += 1) {
          if (Math.random() > quality.particleScale) continue;
          sampled.positions.push(
            source.positions[index * 3] ?? 0,
            source.positions[index * 3 + 1] ?? 0,
            source.positions[index * 3 + 2] ?? 0,
          );
          sampled.colors.push(
            source.colors[index * 3] ?? 0,
            source.colors[index * 3 + 1] ?? 0,
            source.colors[index * 3 + 2] ?? 0,
          );
          sampled.sizes.push(source.sizes[index] ?? 1);
          sampled.alphas.push((source.alphas[index] ?? 0.2) * quality.opacityBoost);
        }
        const layer = this.createRuntimeLayer(kind, sampled);
        return layer ? [layer] : [];
      });
    }

    const partitions = SceneDataGenerator.createLayerAccumulator();

    for (let index = 0; index < data.sizes.length; index += 1) {
      if (Math.random() > quality.particleScale) continue;
      const px = data.positions[index * 3] ?? 0;
      const py = data.positions[index * 3 + 1] ?? 0;
      const pz = data.positions[index * 3 + 2] ?? 0;
      const r = data.colors[index * 3] ?? 0;
      const g = data.colors[index * 3 + 1] ?? 0;
      const b = data.colors[index * 3 + 2] ?? 0;
      const size = data.sizes[index] ?? 1;
      const alpha = (data.alphas[index] ?? 0.2) * quality.opacityBoost;
      const radial = Math.hypot(px, py, pz);

      let bucket: keyof typeof partitions = "signalFilaments";
      if (size < 1.15 && alpha < 0.09) {
        bucket = "ambientDust";
      } else if (size > 4.6 || alpha > 0.5) {
        bucket = "chargeNodes";
      } else if (radial > 2.7 && size > 2.5) {
        bucket = "haloMembrane";
      } else if ((r + g + b) / 3 > 0.85 && alpha > 0.18) {
        bucket = "rareArcSparks";
      } else if (Math.abs(py) < 0.24 && radial < 1.7 && size > 1.8) {
        bucket = "specialStructure";
      }

      partitions[bucket].positions.push(px, py, pz);
      partitions[bucket].colors.push(r, g, b);
      partitions[bucket].sizes.push(size);
      partitions[bucket].alphas.push(alpha);
    }

    return LAYER_ORDER.flatMap((kind) => {
      const layer = this.createRuntimeLayer(kind, partitions[kind]);
      return layer ? [layer] : [];
    });
  }

  private disposeLayers() {
    this.layers.forEach((layer) => {
      this.layerGroup.remove(layer.points);
      layer.geometry.dispose();
      layer.material.dispose();
    });
    this.layers = [];
  }

  private updateFieldState(dt: number) {
    const lerpSpeed = Math.min(1, dt / 280);
    this.chargeState = THREE.MathUtils.lerp(this.chargeState, 0, lerpSpeed * 0.14);
    this.pulseState = THREE.MathUtils.lerp(this.pulseState, 0, lerpSpeed * 0.2);
    this.fieldStrength = THREE.MathUtils.lerp(this.fieldStrength, 0, lerpSpeed * 0.12);
    this.burstIntensity = THREE.MathUtils.lerp(this.burstIntensity, 0, lerpSpeed * 0.16);
    if (this.cameraState !== "stable" && this.pulseState < 0.06 && this.chargeState < 0.2) {
      this.cameraState = "stable";
    }
  }

  private updateLayerUniforms() {
    const quality = QUALITY_PROFILES[this.qualityTier];
    this.uniforms.uChargeState.value = this.chargeState;
    this.uniforms.uPulseState.value = this.pulseState;
    this.uniforms.uTrackingConfidence.value = this.trackingConfidence;
    this.uniforms.uFreezeField.value = this.fieldFrozen ? 1 : 0;
    this.uniforms.uFieldAttractor.value.set(this.fieldAttractor.x, this.fieldAttractor.y, this.fieldAttractor.z);
    this.uniforms.uFieldStrength.value = this.fieldStrength;
    this.uniforms.uBurstCenter.value.set(this.burstCenter.x, this.burstCenter.y, this.burstCenter.z);
    this.uniforms.uBurstIntensity.value = this.burstIntensity;
    this.uniforms.uTurbulence.value = quality.turbulence + (this.gestureFocus ? 0.04 : 0);
    this.uniforms.uOpacityBoost.value = quality.opacityBoost;
  }

  private updatePerformance(dt: number) {
    this.frameAccumulator += dt;
    this.frameSamples += 1;
    if (this.frameAccumulator < 1000) return;
    this.fps = Math.round((this.frameSamples * 1000) / this.frameAccumulator);
    this.frameAccumulator = 0;
    this.frameSamples = 0;
    if (
      !this.reducedMotion &&
      this.fps < 28 &&
      this.qualityTier !== "low" &&
      performance.now() > this.performanceCooldownUntil
    ) {
      this.qualityTier =
        this.qualityTier === "ultra"
          ? "high"
          : this.qualityTier === "high"
            ? "medium"
            : "low";
      this.performanceCooldownUntil = performance.now() + 6000;
      this.rebuildCurrentScene();
    }
  }

  private computeTargetFov() {
    const profile = this.currentScene
      ? SCENE_CAMERA_PROFILES[this.currentScene.id as (typeof SCENE_ORDER)[number]]
      : SCENE_CAMERA_PROFILES.neural_core;
    if (this.cameraState === "charged") return profile.chargedFov;
    if (this.cameraState === "success") return profile.successFov;
    if (this.cameraState === "failed") return profile.failedFov;
    return profile.stableFov;
  }

  private interpolateCamera() {
    if (!this.cameraTarget) return;
    const target = this.cameraTarget;
    const profile = this.currentScene
      ? SCENE_CAMERA_PROFILES[this.currentScene.id as (typeof SCENE_ORDER)[number]]
      : SCENE_CAMERA_PROFILES.neural_core;
    const stateLerp =
      this.cameraState === "charged"
        ? profile.driftEasing * 1.3
        : this.cameraState === "success"
          ? profile.driftEasing * 1.45
          : this.cameraState === "failed"
            ? profile.driftEasing * 0.7
            : profile.driftEasing;
    this.camera.fov += ((target.fov ?? profile.stableFov) - this.camera.fov) * stateLerp;
    this.camera.updateProjectionMatrix();
    this.camera.position.x += (target.pos[0] - this.camera.position.x) * stateLerp;
    this.camera.position.y += (target.pos[1] - this.camera.position.y) * stateLerp;
    this.camera.position.z += (target.pos[2] - this.camera.position.z) * stateLerp;
    const stateLookScale =
      this.cameraState === "charged"
        ? 1.1
        : this.cameraState === "success"
          ? 0.85
          : this.cameraState === "failed"
            ? 1.25
            : 1;
    this.camera.lookAt(
      target.look[0] + profile.lookDrift[0] * stateLookScale,
      target.look[1] + profile.lookDrift[1] * stateLookScale,
      target.look[2] + profile.lookDrift[2] * stateLookScale,
    );
  }

  private updateAutoFloat(time: number) {
    if (!this.currentScene) return;
    const look = this.currentScene.camLook;
    const profile = SCENE_CAMERA_PROFILES[this.currentScene.id as (typeof SCENE_ORDER)[number]];
    const stateRadiusScale =
      this.cameraState === "charged"
        ? profile.chargedRadiusScale
        : this.cameraState === "success"
          ? profile.successRadiusScale
          : this.cameraState === "failed"
            ? profile.failedRadiusScale
            : 1;
    const verticalBoost =
      this.cameraState === "charged"
        ? profile.chargedVerticalBoost
        : this.cameraState === "success"
          ? profile.successVerticalBoost
          : this.cameraState === "failed"
            ? profile.failedVerticalBoost
            : 0;
    const radius = profile.baseFloatRadius * stateRadiusScale * (1 - this.chargeState * 0.08);
    const chargedBias = this.cameraState === "charged" ? 0.78 : this.cameraState === "failed" ? 0.62 : 1;
    const successBias = this.cameraState === "success" ? 1.18 : 1;
    const horizontalSpeed = profile.horizontalSpeed * chargedBias * successBias;
    const verticalSpeed = profile.verticalSpeed * chargedBias * successBias;
    const gestureLookBoost = this.gestureFocus ? 0.06 : 0;
    const tx =
      look[0] +
      profile.lookDrift[0] +
      Math.sin(time * horizontalSpeed) * radius +
      this.fieldAttractor.x * gestureLookBoost;
    const ty =
      look[1] +
      profile.lookDrift[1] +
      Math.sin(time * verticalSpeed) * radius * profile.verticalAmplitude +
      verticalBoost +
      this.pulseState * 0.05;
    const tz =
      look[2] +
      profile.lookDrift[2] +
      Math.cos(time * horizontalSpeed) * radius +
      this.fieldStrength * 0.08;
    this.camera.position.x += (tx - this.camera.position.x) * profile.driftEasing;
    this.camera.position.y += (ty - this.camera.position.y) * profile.driftEasing;
    this.camera.position.z += (tz - this.camera.position.z) * profile.driftEasing;
    this.camera.lookAt(
      look[0] + profile.lookDrift[0] + this.fieldAttractor.x * gestureLookBoost,
      look[1] + profile.lookDrift[1] + this.fieldAttractor.y * gestureLookBoost,
      look[2] + profile.lookDrift[2],
    );
  }
}
