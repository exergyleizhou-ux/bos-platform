import { describe, expect, it } from "vitest";

import {
  getSceneTransitionProfile,
  getTransitionCharge,
  type CameraState,
  type SceneTransitionKind,
} from "./ImmersiveLoginScene";

const BASE_TELEMETRY = {
  signal: 64,
  grip: 52,
  openness: 58,
  energy: 68,
  arcLoad: 22,
  vortexLoad: 8,
  gestureLabel: "READY",
};

function createProfile(
  kind: SceneTransitionKind,
  sceneId: string,
  options?: {
    reducedMotion?: boolean;
    cameraState?: CameraState;
    gestureConfidence?: number;
  },
) {
  return getSceneTransitionProfile(
    kind,
    sceneId,
    1,
    { x: 0.52, y: 0.48 },
    BASE_TELEMETRY,
    options?.gestureConfidence ?? 0.88,
    options?.cameraState ?? "ready",
    "immersive",
    options?.reducedMotion ?? false,
  );
}

describe("Immersive login transition helpers", () => {
  it("raises transition charge for ready camera and strong gesture presence", () => {
    const readyCharge = getTransitionCharge(BASE_TELEMETRY, 0.92, "ready", "immersive");
    const deniedCharge = getTransitionCharge(BASE_TELEMETRY, 0.18, "denied", "normal");

    expect(readyCharge).toBeGreaterThan(deniedCharge);
    expect(readyCharge).toBeLessThanOrEqual(1.25);
    expect(deniedCharge).toBeGreaterThanOrEqual(0);
  });

  it("compresses motion and blur under reduced motion mode", () => {
    const fullMotion = createProfile("dive", "data_void");
    const reducedMotion = createProfile("dive", "data_void", { reducedMotion: true });

    expect(reducedMotion.motionScale).toBeLessThan(fullMotion.motionScale);
    expect(reducedMotion.durationMs).toBeLessThan(fullMotion.durationMs);
    expect(reducedMotion.snapshotBlurPx).toBe(0);
    expect(reducedMotion.shardOpacity).toBeLessThan(fullMotion.shardOpacity);
    expect(reducedMotion.ringScale).toBeLessThan(fullMotion.ringScale);
  });

  it("keeps scene-specific transition vocabulary distinct across worlds", () => {
    const neuralPortal = createProfile("portal", "neural_core");
    const reactorPortal = createProfile("portal", "reactor_interior");
    const voidDive = createProfile("dive", "data_void");
    const bioPageTurn = createProfile("page-right", "bio_matrix");

    expect(neuralPortal.durationMs).not.toBe(reactorPortal.durationMs);
    expect(neuralPortal.focusY).not.toBe(reactorPortal.focusY);
    expect(voidDive.snapshotClipStart).toContain("ellipse(");
    expect(bioPageTurn.snapshotClipStart).toContain("inset(");
  });
});
