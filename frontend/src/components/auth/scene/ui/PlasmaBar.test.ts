import { describe, expect, it } from "vitest";

import { glowForValue } from "./PlasmaBar";

describe("glowForValue", () => {
  it("maps low values to base current cyan", () => {
    expect(glowForValue(20)).toBe("#00C8D4");
  });

  it("maps mid values to bright current", () => {
    expect(glowForValue(60)).toBe("#1AFFE4");
  });

  it("maps high values to hot current", () => {
    expect(glowForValue(90)).toBe("#80FFF5");
  });
});
