import type { NormalizedLandmark } from "@mediapipe/tasks-vision";

import type { GestureType, Point2D } from "../core/types";
import { clamp01 } from "../core/math";
import { analyzeHandMetrics, detectCircle, type HandMetrics } from "./gestureMath";

type HandDetectionInput = {
  landmarks: NormalizedLandmark[][];
  width: number;
  height: number;
  now: number;
  trajectory: Array<{ point: Point2D; time: number }>;
};

export type GestureDetectionResult = {
  type: GestureType;
  confidence: number;
  points: {
    center?: Point2D;
    indexTip?: Point2D;
    middleTip?: Point2D;
    thumbTip?: Point2D;
    pinchCenter?: Point2D;
    leftHand?: Point2D;
    rightHand?: Point2D;
  };
  swipeDirection?: -1 | 0 | 1;
  clockwise?: boolean;
  rotationDelta?: number;
  pushStrength?: number;
  spreadScale?: number;
  metrics: HandMetrics | null;
  secondaryMetrics: HandMetrics | null;
};

let lastPrimaryAngle = 0;
let lastPrimaryDepth = 0;
let lastSpreadDistance = 0;
let wristRotationStreak = 0;
let handPushStreak = 0;
let spreadStreak = 0;
let lastRotationDelta = 0;
let lastPushDelta = 0;

function easeStreak(current: number, active: boolean, max = 5) {
  if (active) return Math.min(max, current + 1);
  return Math.max(0, current - 1);
}

export function detectGestureCandidate(input: HandDetectionInput): GestureDetectionResult {
  const primary = input.landmarks[0]
    ? analyzeHandMetrics(input.landmarks[0], input.width, input.height)
    : null;
  const secondary = input.landmarks[1]
    ? analyzeHandMetrics(input.landmarks[1], input.width, input.height)
    : null;

  if (
    primary &&
    secondary &&
    primary.openness > 0.7 &&
    secondary.openness > 0.7
  ) {
    const spreadDistance = Math.hypot(
      primary.center.x - secondary.center.x,
      primary.center.y - secondary.center.y,
    );
    const spreadDelta = lastSpreadDistance > 0 ? spreadDistance - lastSpreadDistance : 0;
    const spreadScale = lastSpreadDistance > 0 ? clamp01(spreadDelta / 140 + 0.5) : 0.5;
    lastSpreadDistance = spreadDistance;
    const spreadActive =
      spreadDistance > 220 &&
      spreadDelta > 12 &&
      spreadScale > 0.74 &&
      Math.abs(primary.center.y - secondary.center.y) < 180;
    spreadStreak = easeStreak(spreadStreak, spreadActive, 4);
    if (spreadStreak >= 2 && spreadDistance > 200 && spreadScale > 0.72) {
      return {
        type: "TWO_HANDS_PINCH_APART",
        confidence: clamp01((primary.openness + secondary.openness) / 2 + spreadStreak * 0.04),
        points: {
          center: { x: (primary.center.x + secondary.center.x) / 2, y: (primary.center.y + secondary.center.y) / 2 },
          leftHand: primary.center.x < secondary.center.x ? primary.center : secondary.center,
          rightHand: primary.center.x < secondary.center.x ? secondary.center : primary.center,
        },
        spreadScale,
        metrics: primary,
        secondaryMetrics: secondary,
      };
    }
  }

  if (
    primary &&
    secondary &&
    primary.openness > 0.86 &&
    secondary.openness > 0.86 &&
    Math.abs(primary.center.x - secondary.center.x) > 120
  ) {
    return {
      type: "BOTH_HANDS_OPEN",
      confidence: clamp01((primary.openness + secondary.openness) / 2),
      points: { center: { x: (primary.center.x + secondary.center.x) / 2, y: (primary.center.y + secondary.center.y) / 2 } },
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  if (!primary) {
    lastPrimaryAngle = 0;
    lastPrimaryDepth = 0;
    lastRotationDelta = 0;
    lastPushDelta = 0;
    wristRotationStreak = 0;
    handPushStreak = 0;
    spreadStreak = 0;
    return {
      type: "NONE",
      confidence: 0,
      points: {},
      metrics: null,
      secondaryMetrics: null,
    };
  }

  const rotationDelta = lastPrimaryAngle === 0 ? 0 : primary.wristAngle - lastPrimaryAngle;
  lastPrimaryAngle = primary.wristAngle;
  const smoothRotationDelta = lastRotationDelta * 0.55 + rotationDelta * 0.45;
  lastRotationDelta = smoothRotationDelta;

  const pushDelta = lastPrimaryDepth === 0 ? 0 : primary.depth - lastPrimaryDepth;
  lastPrimaryDepth = primary.depth;
  const smoothPushDelta = lastPushDelta * 0.5 + pushDelta * 0.5;
  lastPushDelta = smoothPushDelta;

  const recent = input.trajectory.filter((entry) => input.now - entry.time <= 800);
  const first = recent[0];
  const last = recent[recent.length - 1];
  const recentDrift =
    first && last ? Math.hypot(last.point.x - first.point.x, last.point.y - first.point.y) : 0;
  const swipeDirection =
    first &&
    last &&
    primary.openness > 0.62 &&
    primary.grip < 0.58 &&
    input.now - first.time <= 220 &&
    Math.abs(last.point.x - first.point.x) > 180 &&
    Math.abs(last.point.y - first.point.y) < 120
      ? (last.point.x > first.point.x ? 1 : -1)
      : 0;
  if (swipeDirection !== 0) {
    return {
      type: "SWIPE",
      confidence: 0.88,
      points: { center: primary.center },
      swipeDirection,
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  const verticalSwipe =
    first &&
    last &&
    primary.openness > 0.62 &&
    primary.grip < 0.58 &&
    input.now - first.time <= 240 &&
    Math.abs(last.point.y - first.point.y) > 170 &&
    Math.abs(last.point.x - first.point.x) < 120
      ? last.point.y < first.point.y
        ? "SWIPE_UP"
        : "SWIPE_DOWN"
      : null;
  if (verticalSwipe) {
    return {
      type: verticalSwipe,
      confidence: 0.86,
      points: { center: primary.center },
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  const rotationActive =
    primary.openness > 0.74 &&
    primary.grip < 0.42 &&
    primary.pinchDistance > 42 &&
    Math.abs(smoothRotationDelta) > 0.075 &&
    recentDrift < 90 &&
    swipeDirection === 0;
  wristRotationStreak = easeStreak(wristRotationStreak, rotationActive, 4);
  if (wristRotationStreak >= 2 && rotationActive) {
    return {
      type: "WRIST_ROTATION",
      confidence: clamp01(primary.openness * 0.82 + wristRotationStreak * 0.05),
      points: { center: primary.center },
      rotationDelta: smoothRotationDelta,
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  const pushActive =
    primary.openness > 0.8 &&
    primary.grip < 0.4 &&
    primary.pinchDistance > 54 &&
    Math.abs(smoothRotationDelta) < 0.07 &&
    recentDrift < 120 &&
    smoothPushDelta > 0.028;
  handPushStreak = easeStreak(handPushStreak, pushActive, 4);
  if (handPushStreak >= 2 && pushActive) {
    return {
      type: "HAND_PUSH",
      confidence: clamp01(primary.openness * 0.8 + smoothPushDelta * 3 + handPushStreak * 0.05),
      points: { center: primary.center },
      pushStrength: clamp01(smoothPushDelta * 6),
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  const pullActive =
    primary.openness > 0.8 &&
    primary.grip < 0.4 &&
    primary.pinchDistance > 54 &&
    Math.abs(smoothRotationDelta) < 0.07 &&
    recentDrift < 120 &&
    smoothPushDelta < -0.022;
  if (handPushStreak >= 1 && pullActive) {
    return {
      type: "HAND_PULL",
      confidence: clamp01(primary.openness * 0.76 + Math.abs(smoothPushDelta) * 3.2 + handPushStreak * 0.04),
      points: { center: primary.center },
      pushStrength: clamp01(Math.abs(smoothPushDelta) * 6),
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  const circle = primary.openness > 0.56 && primary.grip < 0.7 ? detectCircle(recent, 72) : null;
  if (circle) {
    return {
      type: "CIRCLE",
      confidence: circle.score,
      points: { center: circle.center },
      clockwise: circle.clockwise,
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  if (primary.thumbsUp && primary.grip < 0.52) {
    return {
      type: "THUMBS_UP",
      confidence: 0.9,
      points: { center: primary.center, thumbTip: primary.thumbTip },
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  if (
    primary.grip > 0.82 &&
    primary.openness < 0.42 &&
    !primary.indexExtended &&
    !primary.middleExtended &&
    primary.ringCurled &&
    primary.pinkyCurled
  ) {
    return {
      type: "FIST",
      confidence: clamp01(primary.grip * 0.92 + (0.42 - primary.openness) * 0.4),
      points: { center: primary.center },
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  if (primary.grip > 0.86 && primary.openness < 0.76) {
    return {
      type: "PINCH",
      confidence: primary.grip,
      points: {
        center: primary.center,
        pinchCenter: primary.pinchCenter,
        thumbTip: primary.thumbTip,
        indexTip: primary.indexTip,
      },
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  if (
    primary.indexExtended &&
    primary.middleExtended &&
    primary.ringCurled &&
    primary.pinkyCurled &&
    primary.grip < 0.58
  ) {
    return {
      type: "PEACE_SIGN",
      confidence: 0.84,
      points: {
        center: primary.center,
        indexTip: primary.indexTip,
        middleTip: primary.middleTip,
      },
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  if (
    primary.indexExtended &&
    !primary.middleExtended &&
    primary.ringCurled &&
    primary.pinkyCurled &&
    primary.grip < 0.62
  ) {
    return {
      type: "INDEX_POINT",
      confidence: 0.82,
      points: {
        center: primary.center,
        indexTip: primary.indexTip,
      },
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  if (primary.openness > 0.87 && primary.grip < 0.3) {
    wristRotationStreak = 0;
    handPushStreak = 0;
    return {
      type: "OPEN_PALM",
      confidence: primary.openness,
      points: { center: primary.center },
      metrics: primary,
      secondaryMetrics: secondary,
    };
  }

  wristRotationStreak = 0;
  handPushStreak = 0;
  return {
    type: "NONE",
    confidence: Math.max(primary.confidence * 0.4, 0.12),
    points: { center: primary.center },
    metrics: primary,
    secondaryMetrics: secondary,
  };
}
