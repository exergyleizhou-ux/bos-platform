// @vitest-environment jsdom
import { describe, expect, it } from "vitest";

import { BOSBreathController } from "./breath";

describe("BOSBreathController", () => {
  it("updates phase and css variables from a single sine cycle", () => {
    const controller = new BOSBreathController();
    controller.update(1000);

    expect(controller.phase).toBeGreaterThan(0);
    expect(document.documentElement.style.getPropertyValue("--breath-phase")).not.toBe("");
    expect(document.documentElement.style.getPropertyValue("--breath-color")).toBe(controller.color);
  });

  it("supports pause, resume, period and color changes", () => {
    const controller = new BOSBreathController();
    controller.setPeriod(2500);
    controller.setColor("#00FF9D");
    controller.pause();
    controller.update(800);
    const pausedPhase = controller.phase;
    controller.resume();
    controller.update(800);

    expect(controller.period).toBe(2500);
    expect(controller.color).toBe("#00FF9D");
    expect(pausedPhase).not.toBe(controller.phase);
  });
});
