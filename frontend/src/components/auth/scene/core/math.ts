export function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function clamp01(value: number) {
  return clamp(value, 0, 1);
}

export function lerp(from: number, to: number, alpha: number) {
  return from + (to - from) * alpha;
}

export function easeTowards(current: number, target: number, factor = 0.08) {
  return current + (target - current) * factor;
}

export function distance2D(ax: number, ay: number, bx: number, by: number) {
  return Math.hypot(ax - bx, ay - by);
}

export function randomBetween(min: number, max: number) {
  return min + Math.random() * (max - min);
}

export function pickRandom<T>(values: readonly T[]) {
  return values[Math.floor(Math.random() * values.length)];
}

export function polarToCartesian(angle: number, radius: number) {
  return {
    x: Math.cos(angle) * radius,
    y: Math.sin(angle) * radius,
  };
}
