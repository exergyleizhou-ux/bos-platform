// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

import { resolveGaussianSceneManifest } from "./gaussianAssetManifest";

describe("resolveGaussianSceneManifest", () => {
  afterEach(() => {
    delete window.__BOS_GAUSSIAN_SCENE_MANIFEST__;
    vi.unstubAllGlobals();
  });

  it("prefers the window manifest when present", async () => {
    window.__BOS_GAUSSIAN_SCENE_MANIFEST__ = [
      {
        id: "neural_core",
        label: "Neural Core",
        labelEN: "NEURAL CORE",
        ambience: "#00C8D4",
        path: "/assets/splats/neural_core.splat",
        camPos: [0, 0.5, 5.5],
        camLook: [0, 0, 0],
      },
    ];

    const manifest = await resolveGaussianSceneManifest();

    expect(manifest).toHaveLength(1);
    expect(manifest[0]?.id).toBe("neural_core");
    expect(manifest[0]?.label).toBe("神经核心");
  });

  it("filters malformed manifest entries", async () => {
    window.__BOS_GAUSSIAN_SCENE_MANIFEST__ = [
      {
        id: "valid",
        label: "Valid",
        labelEN: "VALID",
        ambience: "#00C8D4",
        path: "/valid.splat",
        camPos: [0, 0, 0],
        camLook: [0, 0, 0],
      },
      {
        id: "invalid",
        label: "bad",
      } as never,
    ];

    const manifest = await resolveGaussianSceneManifest();

    expect(manifest).toHaveLength(1);
    expect(manifest[0]?.id).toBe("valid");
  });

  it("falls back to the public manifest endpoint when no explicit config exists", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            id: "reactor_interior",
            label: "Reactor Interior",
            labelEN: "REACTOR INTERIOR",
            ambience: "#00C8D4",
            path: "/assets/splats/reactor.splat",
            camPos: [0, 1.5, 6],
            camLook: [0, 0, 0],
          },
        ],
      }),
    );

    const manifest = await resolveGaussianSceneManifest();

    expect(fetch).toHaveBeenCalledWith("/splats/manifest.json", { credentials: "same-origin" });
    expect(manifest).toHaveLength(1);
    expect(manifest[0]?.id).toBe("reactor_interior");
    expect(manifest[0]?.label).toBe("反应堆内核");
  });
});
