import { describe, expect, it } from "vitest";

import {
  degradeQualityTier,
  generateProceduralSceneDefinition,
  QUALITY_PROFILES,
} from "./bosSplatSystem";

describe("bosSplatSystem helpers", () => {
  it("degrades quality tier in the expected order", () => {
    expect(degradeQualityTier("ultra")).toBe("high");
    expect(degradeQualityTier("high")).toBe("medium");
    expect(degradeQualityTier("medium")).toBe("low");
    expect(degradeQualityTier("low")).toBe("low");
  });

  it("defines particle scaling budgets for every quality tier", () => {
    expect(QUALITY_PROFILES.low.particleScale).toBeLessThan(QUALITY_PROFILES.medium.particleScale);
    expect(QUALITY_PROFILES.medium.particleScale).toBeLessThan(QUALITY_PROFILES.high.particleScale);
    expect(QUALITY_PROFILES.high.particleScale).toBeLessThanOrEqual(QUALITY_PROFILES.ultra.particleScale);
  });

  it("generates native layer outputs for every procedural scene", () => {
    const scenes = [
      "neural_core",
      "reactor_interior",
      "synaptic_web",
      "data_void",
      "bio_matrix",
    ] as const;

    for (const sceneId of scenes) {
      const scene = generateProceduralSceneDefinition(sceneId, 3000);
      expect(scene.nativeLayers).toBeDefined();
      expect(scene.positions.length).toBeGreaterThan(0);
      expect(scene.colors.length).toBe(scene.positions.length);
      expect(scene.sizes.length).toBe(scene.alphas.length);

      const totalLayerParticles = Object.values(scene.nativeLayers ?? {}).reduce(
        (sum, layer) => sum + (layer?.sizes.length ?? 0),
        0,
      );
      expect(totalLayerParticles).toBe(scene.sizes.length);
      expect(totalLayerParticles).toBeGreaterThan(0);
    }
  });
});
