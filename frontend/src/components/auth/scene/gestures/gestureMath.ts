import type { NormalizedLandmark } from "@mediapipe/tasks-vision";

import { clamp01, distance2D } from "../core/math";
import type { Point2D } from "../core/types";

export type HandMetrics = {
  center: Point2D;
  openness: number;
  grip: number;
  pinchDistance: number;
  thumbsUp: boolean;
  indexExtended: boolean;
  middleExtended: boolean;
  ringCurled: boolean;
  pinkyCurled: boolean;
  thumbTip: Point2D;
  indexTip: Point2D;
  middleTip: Point2D;
  pinchCenter: Point2D;
  wristAngle: number;
  depth: number;
  confidence: number;
};

function toPoint(landmark: NormalizedLandmark, width: number, height: number): Point2D {
  return {
    x: (1 - landmark.x) * width,
    y: landmark.y * height,
  };
}

function landmarkDistance(a: NormalizedLandmark, b: NormalizedLandmark) {
  return Math.hypot(a.x - b.x, a.y - b.y, (a.z ?? 0) - (b.z ?? 0));
}

export function analyzeHandMetrics(
  landmarks: NormalizedLandmark[],
  width: number,
  height: number,
): HandMetrics {
  const wrist = landmarks[0];
  const thumbTip = landmarks[4];
  const indexTip = landmarks[8];
  const middleTip = landmarks[12];
  const ringTip = landmarks[16];
  const pinkyTip = landmarks[20];
  const indexPip = landmarks[6];
  const middlePip = landmarks[10];
  const ringPip = landmarks[14];
  const pinkyPip = landmarks[18];
  const middleMcp = landmarks[9];
  const palmDepth =
    -(
      (landmarks[0].z ?? 0) +
      (landmarks[5].z ?? 0) +
      (landmarks[9].z ?? 0) +
      (landmarks[13].z ?? 0) +
      (landmarks[17].z ?? 0)
    ) /
    5;

  const palmCenter = {
    x:
      (landmarks[0].x +
        landmarks[5].x +
        landmarks[9].x +
        landmarks[13].x +
        landmarks[17].x) /
      5,
    y:
      (landmarks[0].y +
        landmarks[5].y +
        landmarks[9].y +
        landmarks[13].y +
        landmarks[17].y) /
      5,
  };

  const openness = clamp01(
    (landmarkDistance(wrist, indexTip) +
      landmarkDistance(wrist, middleTip) +
      landmarkDistance(wrist, ringTip) +
      landmarkDistance(wrist, pinkyTip) -
      0.62) /
      0.68,
  );
  const grip = clamp01(1 - landmarkDistance(thumbTip, indexTip) / 0.12);
  const pinchDistance = Math.hypot(
    ((1 - thumbTip.x) * width) - ((1 - indexTip.x) * width),
    thumbTip.y * height - indexTip.y * height,
  );
  const indexExtended = landmarkDistance(wrist, indexTip) - landmarkDistance(wrist, indexPip) > 0.11;
  const middleExtended =
    landmarkDistance(wrist, middleTip) - landmarkDistance(wrist, middlePip) > 0.11;
  const ringCurled = landmarkDistance(wrist, ringTip) - landmarkDistance(wrist, ringPip) < 0.07;
  const pinkyCurled = landmarkDistance(wrist, pinkyTip) - landmarkDistance(wrist, pinkyPip) < 0.06;
  const thumbsUp =
    thumbTip.y < landmarks[3].y &&
    thumbTip.y < indexTip.y &&
    thumbTip.y < middleTip.y &&
    ringCurled &&
    pinkyCurled;
  const wristAngle = Math.atan2(middleMcp.y - wrist.y, middleMcp.x - wrist.x);

  return {
    center: {
      x: (1 - palmCenter.x) * width,
      y: palmCenter.y * height,
    },
    openness,
    grip,
    pinchDistance,
    thumbsUp,
    indexExtended,
    middleExtended,
    ringCurled,
    pinkyCurled,
    thumbTip: toPoint(thumbTip, width, height),
    indexTip: toPoint(indexTip, width, height),
    middleTip: toPoint(middleTip, width, height),
    pinchCenter: {
      x: ((1 - thumbTip.x) * width + (1 - indexTip.x) * width) / 2,
      y: (thumbTip.y * height + indexTip.y * height) / 2,
    },
    wristAngle,
    depth: palmDepth,
    confidence: clamp01(0.35 + openness * 0.25 + grip * 0.25 + (indexExtended ? 0.15 : 0)),
  };
}

export function detectCircle(
  trajectory: Array<{ point: Point2D; time: number }>,
  minRadius = 60,
) {
  if (trajectory.length < 10) {
    return null;
  }

  const center = trajectory.reduce(
    (accumulator, entry) => ({
      x: accumulator.x + entry.point.x / trajectory.length,
      y: accumulator.y + entry.point.y / trajectory.length,
    }),
    { x: 0, y: 0 },
  );

  const radii = trajectory.map((entry) => distance2D(entry.point.x, entry.point.y, center.x, center.y));
  const averageRadius = radii.reduce((sum, value) => sum + value, 0) / radii.length;
  const variance =
    radii.reduce((sum, value) => sum + (value - averageRadius) ** 2, 0) / radii.length;
  const score = clamp01(1 - variance / Math.max(averageRadius, 1) ** 2);
  if (averageRadius < minRadius || score < 0.72) {
    return null;
  }

  let signedArea = 0;
  for (let index = 0; index < trajectory.length - 1; index += 1) {
    const a = trajectory[index].point;
    const b = trajectory[index + 1].point;
    signedArea += (b.x - a.x) * (b.y + a.y);
  }

  return {
    center,
    radius: averageRadius,
    score,
    clockwise: signedArea > 0,
  };
}
