import type {
  BOSSceneSummary,
  ImmersiveSceneRenderer,
  PulseType,
  QualityTier,
} from "./rendererBackend";
import {
  resolveGaussianSceneManifest,
  type GaussianSceneAsset,
} from "./gaussianAssetManifest";

const DEFAULT_GAUSSIAN_CDN =
  "https://cdn.jsdelivr.net/npm/@mkkellogg/gaussian-splats-3d/build/gaussian-splats-3d.umd.cjs";

function loadScript(src: string) {
  return new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[data-bos-gaussian-src="${src}"]`,
    );
    if (existing) {
      if (existing.dataset.loaded === "true") {
        resolve();
        return;
      }
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error(`Failed to load ${src}`)), {
        once: true,
      });
      return;
    }

    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.dataset.bosGaussianSrc = src;
    script.addEventListener(
      "load",
      () => {
        script.dataset.loaded = "true";
        resolve();
      },
      { once: true },
    );
    script.addEventListener("error", () => reject(new Error(`Failed to load ${src}`)), {
      once: true,
    });
    document.head.appendChild(script);
  });
}

async function ensureGaussianLibrary() {
  if (window.GaussianSplats3D?.Viewer) {
    return window.GaussianSplats3D;
  }

  const cdn = import.meta.env.VITE_GAUSSIAN_SPLATS_CDN || DEFAULT_GAUSSIAN_CDN;
  await loadScript(cdn);
  return window.GaussianSplats3D;
}

export class GaussianRendererBackend extends EventTarget implements ImmersiveSceneRenderer {
  readonly kind = "gaussian" as const;
  private qualityTier: QualityTier = "high";
  private readonly canvas: HTMLCanvasElement;
  private readonly scenes: GaussianSceneAsset[];
  private currentScene: GaussianSceneAsset | null = null;
  private currentIndex = 0;
  private viewer: InstanceType<NonNullable<typeof window.GaussianSplats3D>["Viewer"]> | null = null;
  private host: HTMLDivElement | null = null;
  constructor(
    canvas: HTMLCanvasElement,
    scenes: GaussianSceneAsset[],
    _options: { autoFloat?: boolean } = {},
  ) {
    super();
    this.canvas = canvas;
    this.scenes = scenes;
  }

  async pregenScenes() {
    const gaussian = await ensureGaussianLibrary();
    if (!gaussian?.Viewer || this.scenes.length === 0) {
      throw new Error("Gaussian renderer library or scene manifest unavailable.");
    }

    const parent = this.canvas.parentElement;
    if (!parent) {
      throw new Error("Gaussian scene canvas has no parent element.");
    }

    this.host = document.createElement("div");
    this.host.className = "login-immersive__gaussian-host";
    this.host.style.position = "absolute";
    this.host.style.inset = "0";
    this.host.style.pointerEvents = "none";
    parent.appendChild(this.host);

    this.viewer = new gaussian.Viewer({
      container: this.host,
      cameraUp: [0, -1, 0],
      initialCameraPos: this.scenes[0]?.camPos ?? [0, 0, 5],
      initialCameraLookAt: this.scenes[0]?.camLook ?? [0, 0, 0],
      selfDrivenMode: true,
      useBuiltInControls: false,
      enableSIMDInSort: true,
      sharedMemoryForWorkers: false,
    });

    for (const scene of this.scenes) {
      await this.viewer.addSplatScene(scene.path, {
        showLoadingUI: false,
        position: [0, 0, 0],
        rotation: [0, 0, 0, 1],
        scale: [1, 1, 1],
      });
    }

    this.currentScene = this.scenes[0] ?? null;
    this.dispatchEvent(new Event("scenesready"));
    if (this.currentScene) {
      this.dispatchEvent(
        new CustomEvent<BOSSceneSummary>("scenechange", { detail: this.currentScene }),
      );
    }
  }

  getSceneList(): BOSSceneSummary[] {
    return this.scenes.map(({ id, label, labelEN, ambience }) => ({
      id,
      label,
      labelEN,
      ambience,
    }));
  }

  getCurrentSceneInfo(): BOSSceneSummary | null {
    if (!this.currentScene) return null;
    const { id, label, labelEN, ambience } = this.currentScene;
    return { id, label, labelEN, ambience };
  }

  getQualityTier(): QualityTier {
    return this.qualityTier;
  }

  setQualityTier(tier: QualityTier) {
    this.qualityTier = tier;
  }

  getStats() {
    return {
      fps: 60,
      qualityTier: this.qualityTier,
    };
  }

  loadScene(sceneId: string): BOSSceneSummary | null {
    const index = this.scenes.findIndex((scene) => scene.id === sceneId);
    if (index < 0) return null;
    this.currentIndex = index;
    this.currentScene = this.scenes[index] ?? null;
    if (this.currentScene && this.viewer?.camera?.lookAt) {
      const [x, y, z] = this.currentScene.camPos;
      if (this.viewer.camera.position) {
        this.viewer.camera.position.x = x;
        this.viewer.camera.position.y = y;
        this.viewer.camera.position.z = z;
      }
      this.viewer.camera.lookAt(...this.currentScene.camLook);
      this.dispatchEvent(
        new CustomEvent<BOSSceneSummary>("scenechange", { detail: this.currentScene }),
      );
    }
    return this.getCurrentSceneInfo();
  }

  nextScene(direction: 1 | -1 = 1): BOSSceneSummary | null {
    if (this.scenes.length === 0) return null;
    const nextIndex = (this.currentIndex + direction + this.scenes.length) % this.scenes.length;
    return this.loadScene(this.scenes[nextIndex]?.id ?? this.scenes[0].id);
  }

  start() {
    this.viewer?.start?.();
  }

  stop() {
    this.viewer?.stop?.();
  }

  dispose() {
    this.stop();
    this.viewer?.dispose?.();
    this.host?.remove();
    this.host = null;
    this.viewer = null;
  }

  setBreathPhase(_phase: number) {}

  setAutoFloatEnabled(_enabled: boolean) {}

  setFieldAttractor(_x: number, _y: number, _strength: number) {}

  setChargeState(_level: number) {}

  triggerPulse(_type: PulseType) {}

  freezeField(_flag: boolean) {}

  burstField(_center: { x: number; y: number; z?: number }, _intensity: number) {}

  setGestureFocus(_target: string | null) {}

  setTrackingConfidence(_value: number) {}

  orbitCamera(_dx: number, _dy: number) {}

  zoomCamera(_delta: number) {}

  rotateScene(_dx: number, _dy: number) {}

  resize() {}

  captureSnapshotDataUrl() {
    return this.viewer?.renderer?.domElement?.toDataURL("image/webp", 0.72) ?? null;
  }
}

export async function createGaussianRendererBackend(
  canvas: HTMLCanvasElement,
  options: { autoFloat?: boolean } = {},
) {
  const manifest = await resolveGaussianSceneManifest();
  if (manifest.length === 0) return null;
  const renderer = new GaussianRendererBackend(canvas, manifest, options);
  await renderer.pregenScenes();
  return renderer;
}
