import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./gestureMath", () => ({
  analyzeHandMetrics: vi.fn(),
  detectCircle: vi.fn(() => null),
}));

import { detectGestureCandidate } from "./gestureDetection";
import { analyzeHandMetrics } from "./gestureMath";

const analyzeHandMetricsMock = vi.mocked(analyzeHandMetrics);

function resetGestureDetectionState() {
  detectGestureCandidate({
    landmarks: [],
    width: 640,
    height: 480,
    now: 0,
    trajectory: [],
  });
}

describe("detectGestureCandidate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetGestureDetectionState();
  });

  it("recognizes a fist with realistic grip and openness thresholds", () => {
    analyzeHandMetricsMock.mockReturnValue({
      center: { x: 320, y: 240 },
      openness: 0.34,
      grip: 0.86,
      pinchDistance: 22,
      thumbsUp: false,
      indexExtended: false,
      middleExtended: false,
      ringCurled: true,
      pinkyCurled: true,
      thumbTip: { x: 0, y: 0 },
      indexTip: { x: 0, y: 0 },
      middleTip: { x: 0, y: 0 },
      pinchCenter: { x: 0, y: 0 },
      wristAngle: 0,
      depth: 0.1,
      confidence: 0.88,
    });

    const result = detectGestureCandidate({
      landmarks: [[{} as never]],
      width: 640,
      height: 480,
      now: 1000,
      trajectory: [],
    });

    expect(result.type).toBe("FIST");
    expect(result.confidence).toBeGreaterThan(0.7);
  });

  it("does not collapse a wider pinch into a fist", () => {
    analyzeHandMetricsMock.mockReturnValue({
      center: { x: 320, y: 240 },
      openness: 0.58,
      grip: 0.9,
      pinchDistance: 18,
      thumbsUp: false,
      indexExtended: false,
      middleExtended: false,
      ringCurled: true,
      pinkyCurled: true,
      thumbTip: { x: 0, y: 0 },
      indexTip: { x: 0, y: 0 },
      middleTip: { x: 0, y: 0 },
      pinchCenter: { x: 0, y: 0 },
      wristAngle: 0,
      depth: 0.1,
      confidence: 0.88,
    });

    const result = detectGestureCandidate({
      landmarks: [[{} as never]],
      width: 640,
      height: 480,
      now: 1000,
      trajectory: [],
    });

    expect(result.type).toBe("PINCH");
  });
});
