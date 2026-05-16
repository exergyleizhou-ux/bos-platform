export type SceneAxis = "horizontal" | "vertical";

export type SceneTopologyNode = {
  id: string;
  left: string;
  right: string;
  up: string;
  down: string;
};

export const SCENE_TOPOLOGY: Record<string, SceneTopologyNode> = {
  neural_core: {
    id: "neural_core",
    left: "synaptic_web",
    right: "reactor_interior",
    up: "bio_matrix",
    down: "data_void",
  },
  reactor_interior: {
    id: "reactor_interior",
    left: "neural_core",
    right: "bio_matrix",
    up: "synaptic_web",
    down: "data_void",
  },
  synaptic_web: {
    id: "synaptic_web",
    left: "bio_matrix",
    right: "neural_core",
    up: "data_void",
    down: "reactor_interior",
  },
  data_void: {
    id: "data_void",
    left: "bio_matrix",
    right: "synaptic_web",
    up: "neural_core",
    down: "reactor_interior",
  },
  bio_matrix: {
    id: "bio_matrix",
    left: "reactor_interior",
    right: "synaptic_web",
    up: "neural_core",
    down: "data_void",
  },
};

export function getSceneNeighbor(
  currentSceneId: string | null | undefined,
  axis: SceneAxis,
  direction: 1 | -1,
) {
  if (!currentSceneId) return null;
  const node = SCENE_TOPOLOGY[currentSceneId];
  if (!node) return null;
  if (axis === "horizontal") {
    return direction > 0 ? node.right : node.left;
  }
  return direction > 0 ? node.up : node.down;
}
