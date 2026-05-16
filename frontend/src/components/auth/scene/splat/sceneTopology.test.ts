import { describe, expect, it } from "vitest";

import { getSceneNeighbor, SCENE_TOPOLOGY } from "./sceneTopology";

describe("sceneTopology", () => {
  it("defines topology entries for every immersive scene", () => {
    expect(Object.keys(SCENE_TOPOLOGY).sort()).toEqual(
      ["bio_matrix", "data_void", "neural_core", "reactor_interior", "synaptic_web"].sort(),
    );
  });

  it("navigates horizontally through explicit neighbors", () => {
    expect(getSceneNeighbor("neural_core", "horizontal", 1)).toBe("reactor_interior");
    expect(getSceneNeighbor("neural_core", "horizontal", -1)).toBe("synaptic_web");
  });

  it("navigates vertically through explicit neighbors", () => {
    expect(getSceneNeighbor("neural_core", "vertical", 1)).toBe("bio_matrix");
    expect(getSceneNeighbor("neural_core", "vertical", -1)).toBe("data_void");
  });

  it("returns null when the scene is unknown", () => {
    expect(getSceneNeighbor("unknown_scene", "horizontal", 1)).toBeNull();
    expect(getSceneNeighbor(null, "vertical", -1)).toBeNull();
  });
});
