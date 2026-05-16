import type { BOSSceneSummary } from "./rendererBackend";

export type GaussianSceneAsset = BOSSceneSummary & {
  path: string;
  camPos: [number, number, number];
  camLook: [number, number, number];
};

declare global {
  interface Window {
    __BOS_GAUSSIAN_SCENE_MANIFEST__?: GaussianSceneAsset[];
    GaussianSplats3D?: {
      Viewer: new (options: Record<string, unknown>) => {
        addSplatScene: (
          path: string,
          options?: Record<string, unknown>,
        ) => Promise<unknown>;
        stop?: () => void;
        start?: () => void;
        dispose?: () => void;
        renderer?: {
          render: (scene: unknown, camera: unknown) => void;
          domElement?: HTMLCanvasElement;
        };
        scene?: unknown;
        camera?: {
          position?: {
            x: number;
            y: number;
            z: number;
          };
          lookAt?: (x: number, y: number, z: number) => void;
        };
      };
    };
  }
}

const NORMALIZED_SCENE_LABELS: Record<string, string> = {
  neural_core: "神经核心",
  reactor_interior: "反应堆内核",
  synaptic_web: "突触网络",
  data_void: "数据虚空",
  bio_matrix: "生物矩阵",
};

function normalizeSceneAsset(scene: unknown): GaussianSceneAsset | null {
  if (!scene || typeof scene !== "object") return null;
  const candidate = scene as Record<string, unknown>;
  if (
    typeof candidate.id !== "string" ||
    typeof candidate.label !== "string" ||
    typeof candidate.labelEN !== "string" ||
    typeof candidate.ambience !== "string" ||
    typeof candidate.path !== "string" ||
    !Array.isArray(candidate.camPos) ||
    !Array.isArray(candidate.camLook)
  ) {
    return null;
  }

  return {
    id: candidate.id,
    label: NORMALIZED_SCENE_LABELS[candidate.id] ?? candidate.label,
    labelEN: candidate.labelEN,
    ambience: candidate.ambience,
    path: candidate.path,
    camPos: candidate.camPos as [number, number, number],
    camLook: candidate.camLook as [number, number, number],
  };
}

function normalizeManifest(input: unknown): GaussianSceneAsset[] {
  if (!Array.isArray(input)) return [];
  return input.map(normalizeSceneAsset).filter((scene): scene is GaussianSceneAsset => Boolean(scene));
}

async function readManifestFromUrl(url: string) {
  try {
    const response = await fetch(url, { credentials: "same-origin" });
    if (!response.ok) return [];
    const parsed = await response.json();
    return normalizeManifest(parsed);
  } catch {
    return [];
  }
}

export async function resolveGaussianSceneManifest(): Promise<GaussianSceneAsset[]> {
  const windowManifest = window.__BOS_GAUSSIAN_SCENE_MANIFEST__;
  if (Array.isArray(windowManifest) && windowManifest.length > 0) {
    return normalizeManifest(windowManifest);
  }

  const rawManifest = import.meta.env.VITE_GAUSSIAN_SCENE_MANIFEST;
  if (rawManifest) {
    const trimmed = rawManifest.trim();
    if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
      try {
        return normalizeManifest(JSON.parse(trimmed));
      } catch {
        // Fall through to URL-based discovery.
      }
    } else {
      const byUrl = await readManifestFromUrl(trimmed);
      if (byUrl.length > 0) {
        return byUrl;
      }
    }
  }

  return readManifestFromUrl("/splats/manifest.json");
}
