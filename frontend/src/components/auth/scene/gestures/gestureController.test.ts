import { describe, expect, it } from "vitest";

import { GestureController } from "./gestureController";

describe("GestureController", () => {
  it("moves through activating and active states for a confident gesture", () => {
    const controller = new GestureController();
    const activating = controller.update(
      {
        type: "OPEN_PALM",
        confidence: 0.9,
        points: {},
      },
      100,
    );
    const active = controller.update(
      {
        type: "OPEN_PALM",
        confidence: 0.9,
        points: {},
      },
      260,
    );

    expect(activating.state).toBe("activating");
    expect(active.state).toBe("active");
  });

  it("returns to releasing and idle when the gesture disappears", () => {
    const controller = new GestureController();
    controller.update(
      {
        type: "PINCH",
        confidence: 0.88,
        points: {},
      },
      100,
    );

    const releasing = controller.update(null, 220);
    const idle = controller.update(null, 500);

    expect(releasing.state).toBe("releasing");
    expect(idle.state).toBe("idle");
    expect(idle.type).toBe("NONE");
  });

  it("accepts the newer vertical swipe and pull gestures", () => {
    const controller = new GestureController();

    const swipeUp = controller.update(
      {
        type: "SWIPE_UP",
        confidence: 0.86,
        points: {},
      },
      240,
    );

    const handPull = controller.update(
      {
        type: "HAND_PULL",
        confidence: 0.84,
        points: {},
        pushStrength: 0.6,
      },
      520,
    );

    expect(swipeUp.type).toBe("SWIPE_UP");
    expect(handPull.type).toBe("HAND_PULL");
    expect(handPull.params.pushStrength).toBeGreaterThan(0);
  });
});
