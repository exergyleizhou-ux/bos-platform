export type BOSSceneSummary = {
  id: string;
  label: string;
  labelEN: string;
  ambience: string;
};

export type QualityTier = "low" | "medium" | "high" | "ultra";
export type PulseType = "soft" | "confirm" | "success" | "burst" | "disturbance";

export interface ImmersiveSceneRenderer {
  readonly kind: "procedural" | "gaussian";
  pregenScenes(): void;
  getSceneList(): BOSSceneSummary[];
  getCurrentSceneInfo(): BOSSceneSummary | null;
  getQualityTier(): QualityTier;
  setQualityTier(tier: QualityTier): void;
  getStats(): { fps: number; qualityTier: QualityTier };
  loadScene(sceneId: string): BOSSceneSummary | null;
  nextScene(direction?: 1 | -1): BOSSceneSummary | null;
  start(): void;
  stop(): void;
  dispose(): void;
  setBreathPhase(phase: number): void;
  setAutoFloatEnabled(enabled: boolean): void;
  setFieldAttractor(x: number, y: number, strength: number): void;
  setChargeState(level: number): void;
  triggerPulse(type: PulseType): void;
  freezeField(flag: boolean): void;
  burstField(center: { x: number; y: number; z?: number }, intensity: number): void;
  setGestureFocus(target: string | null): void;
  setTrackingConfidence(value: number): void;
  orbitCamera(dx: number, dy: number): void;
  zoomCamera(delta: number): void;
  rotateScene(dx: number, dy: number): void;
  resize(): void;
  captureSnapshotDataUrl(): string | null;
  addEventListener(type: string, listener: EventListenerOrEventListenerObject | null): void;
  removeEventListener(type: string, listener: EventListenerOrEventListenerObject | null): void;
}

export type SceneRendererMode = "auto" | "procedural" | "gaussian";

export async function createProceduralRenderer(
  canvas: HTMLCanvasElement,
  options: { particleCount?: number; autoFloat?: boolean } = {},
): Promise<ImmersiveSceneRenderer> {
  const module = await import("./bosSplatSystem");
  return new module.BOSSplatSystem(canvas, options);
}

export async function createGaussianRenderer(
  canvas: HTMLCanvasElement,
  options: { particleCount?: number; autoFloat?: boolean } = {},
): Promise<ImmersiveSceneRenderer | null> {
  const module = await import("./gaussianRendererBackend");
  return module.createGaussianRendererBackend(canvas, options);
}

export async function createSceneRenderer(
  canvas: HTMLCanvasElement,
  options: { particleCount?: number; autoFloat?: boolean; mode?: SceneRendererMode } = {},
): Promise<ImmersiveSceneRenderer> {
  const mode = options.mode ?? "auto";

  if (mode === "procedural") {
    return createProceduralRenderer(canvas, options);
  }

  if (mode === "gaussian") {
    const gaussian = await createGaussianRenderer(canvas, options);
    if (!gaussian) {
      throw new Error("Gaussian renderer backend is not available in this workspace.");
    }
    return gaussian;
  }

  const gaussian = await createGaussianRenderer(canvas, options);
  if (gaussian) {
    return gaussian;
  }

  return createProceduralRenderer(canvas, options);
}
