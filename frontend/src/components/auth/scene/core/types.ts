export type Point2D = {
  x: number;
  y: number;
};

export type GestureType =
  | "NONE"
  | "OPEN_PALM"
  | "FIST"
  | "INDEX_POINT"
  | "PEACE_SIGN"
  | "PINCH"
  | "SWIPE"
  | "SWIPE_UP"
  | "SWIPE_DOWN"
  | "CIRCLE"
  | "THUMBS_UP"
  | "BOTH_HANDS_OPEN"
  | "WRIST_ROTATION"
  | "HAND_PUSH"
  | "HAND_PULL"
  | "TWO_HANDS_PINCH_APART";

export type GestureLifecycle = "idle" | "activating" | "active" | "releasing";

export type GestureFrame = {
  type: GestureType;
  state: GestureLifecycle;
  confidence: number;
  points: Partial<
    Record<
      "center" | "indexTip" | "middleTip" | "thumbTip" | "pinchCenter" | "leftHand" | "rightHand",
      Point2D
    >
  >;
  params: {
    repel: boolean;
    energy: number;
    holdProgress: number;
    swipeDirection: -1 | 0 | 1;
    clockwise: boolean;
    rotationDelta: number;
    pushStrength: number;
    spreadScale: number;
  };
};

export type LoginSceneTelemetry = {
  signal: number;
  grip: number;
  openness: number;
  energy: number;
  arcLoad: number;
  vortexLoad: number;
  gestureLabel: string;
};

export interface SceneLayer {
  mount(host: HTMLElement): void;
  resize(width: number, height: number, dpr: number): void;
  update(dt: number, now: number): void;
  dispose(): void;
}
