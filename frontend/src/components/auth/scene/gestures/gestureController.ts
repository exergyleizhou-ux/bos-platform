import type { GestureFrame, GestureLifecycle, GestureType, Point2D } from "../core/types";
import { easeTowards } from "../core/math";

type RawGestureCandidate = {
  type: GestureType;
  confidence: number;
  points: GestureFrame["points"];
  swipeDirection?: -1 | 0 | 1;
  clockwise?: boolean;
  rotationDelta?: number;
  pushStrength?: number;
  spreadScale?: number;
};

const CONFIDENCE_THRESHOLD = 0.72;
const GESTURE_COOLDOWNS: Partial<Record<GestureType, number>> = {
  FIST: 300,
  BOTH_HANDS_OPEN: 2000,
  WRIST_ROTATION: 120,
  HAND_PUSH: 220,
  HAND_PULL: 220,
  SWIPE_UP: 180,
  SWIPE_DOWN: 180,
  TWO_HANDS_PINCH_APART: 180,
};

export class GestureController {
  currentGesture: GestureType = "NONE";
  state: GestureLifecycle = "idle";
  confidence = 0;
  transitionTime = 0;
  params = {
    repel: false,
    energy: 0,
    holdProgress: 0,
    swipeDirection: 0 as -1 | 0 | 1,
    clockwise: true,
    rotationDelta: 0,
    pushStrength: 0,
    spreadScale: 1,
  };
  lastTriggerTimes = new Map<GestureType, number>();

  update(candidate: RawGestureCandidate | null, now: number): GestureFrame {
    const candidateType =
      candidate && candidate.confidence >= CONFIDENCE_THRESHOLD ? candidate.type : "NONE";
    const cooldown = GESTURE_COOLDOWNS[candidateType] ?? 100;
    const lastTrigger = this.lastTriggerTimes.get(candidateType) ?? 0;
    const nextType =
      candidateType !== "NONE" && now - lastTrigger < cooldown ? this.currentGesture : candidateType;
    const nextConfidence = candidate?.confidence ?? 0;

    if (nextType === "NONE") {
      if (this.currentGesture !== "NONE") {
        this.state = "releasing";
        this.transitionTime = now;
      } else {
        this.state = "idle";
      }
      this.currentGesture = "NONE";
    } else if (nextType !== this.currentGesture) {
      this.currentGesture = nextType;
      this.state = "activating";
      this.transitionTime = now;
      this.lastTriggerTimes.set(nextType, now);
    } else if (this.state === "activating" && now - this.transitionTime > 100) {
      this.state = "active";
    }

    if (this.state === "releasing" && now - this.transitionTime > 220) {
      this.state = "idle";
    }

    this.confidence = easeTowards(this.confidence, nextConfidence, 0.18);
    this.params.energy = easeTowards(this.params.energy, nextConfidence, 0.08);
    this.params.holdProgress = easeTowards(
      this.params.holdProgress,
      this.state === "active" ? 1 : 0,
      0.08,
    );
    this.params.repel = nextType === "OPEN_PALM";
    this.params.swipeDirection = candidate?.swipeDirection ?? 0;
    this.params.clockwise = candidate?.clockwise ?? this.params.clockwise;
    this.params.rotationDelta = easeTowards(
      this.params.rotationDelta,
      candidate?.rotationDelta ?? 0,
      0.16,
    );
    this.params.pushStrength = easeTowards(
      this.params.pushStrength,
      candidate?.pushStrength ?? 0,
      0.18,
    );
    this.params.spreadScale = easeTowards(
      this.params.spreadScale,
      candidate?.spreadScale ?? 1,
      0.14,
    );

    return {
      type: this.currentGesture,
      state: this.state,
      confidence: this.confidence,
      points: candidate?.points ?? {},
      params: this.params,
    };
  }
}

export function createEmptyGestureFrame(): GestureFrame {
  return {
    type: "NONE",
    state: "idle",
    confidence: 0,
    points: {},
    params: {
      repel: false,
      energy: 0,
      holdProgress: 0,
      swipeDirection: 0,
      clockwise: true,
      rotationDelta: 0,
      pushStrength: 0,
      spreadScale: 1,
    },
  };
}

export function pointMap(center?: Point2D, extras?: GestureFrame["points"]): GestureFrame["points"] {
  return {
    center,
    ...extras,
  };
}
