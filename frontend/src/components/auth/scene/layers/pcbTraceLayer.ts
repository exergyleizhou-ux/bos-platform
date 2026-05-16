import { getBreathController } from "../core/breath";
import { clamp01, randomBetween } from "../core/math";
import type { Point2D } from "../core/types";
import { BaseCanvasLayer } from "./baseCanvasLayer";

type TraceLayerName = "dim" | "mid" | "active";

type TraceSegment = {
  startX: number;
  startY: number;
  endX: number;
  endY: number;
  layer: TraceLayerName;
  dense?: boolean;
};

type TraceNode = {
  x: number;
  y: number;
  radius: number;
  pulsePhase: number;
  pulseSpeed: number;
  energy: number;
};

type TracePulse = {
  trace: TraceSegment;
  startAt: number;
  duration: number;
  color: string;
  width: number;
  glow: number;
};

type SweepRecord = {
  center: Point2D;
  direction: -1 | 1;
  startAt: number;
};

const GRID = 32;
const PALETTE = {
  traceDim: "rgba(0, 175, 190, 0.12)",
  traceMid: "rgba(0, 185, 200, 0.25)",
  traceActive: "rgba(0, 200, 215, 0.5)",
  current: "#00C8D4",
  currentBright: "#1AFFE4",
  currentHot: "rgba(200,255,255,0.95)",
};

export class PCBTraceLayer extends BaseCanvasLayer {
  private readonly traces: TraceSegment[] = [];
  private readonly nodes: TraceNode[] = [];
  private readonly pulses: TracePulse[] = [];
  private sweeps: SweepRecord[] = [];
  private activityBoost = 1;
  private activityUntil = 0;
  private pulseAt = 0;

  boostActivity(multiplier: number, duration = 900) {
    this.activityBoost = multiplier;
    this.activityUntil = performance.now() + duration;
  }

  injectEnergy(point: Point2D, radius = 120, amount = 1) {
    for (const node of this.nodes) {
      const distance = Math.hypot(node.x - point.x, node.y - point.y);
      if (distance <= radius) {
        node.energy = Math.max(node.energy, amount * (1 - distance / radius));
      }
    }

    for (let index = 0; index < 4; index += 1) {
      this.spawnPulse(performance.now(), this.pickTraceNear(point, index < 2 ? "active" : "mid"));
    }
  }

  triggerSweep(point: Point2D, direction: -1 | 1) {
    this.sweeps.push({ center: point, direction, startAt: performance.now() });
    this.boostActivity(2.8, 720);
    for (let index = 0; index < 8; index += 1) {
      this.spawnPulse(performance.now() + index * 26);
    }
  }

  protected onResize(width: number, height: number) {
    this.traces.length = 0;
    this.nodes.length = 0;

    const gridColumns = Math.ceil(width / GRID);
    const gridRows = Math.ceil(height / GRID);
    const angles = [0, 45, 90, 135, 180, 225, 270, 315];

    for (let index = 0; index < 120; index += 1) {
      const startX = Math.floor(Math.random() * gridColumns) * GRID;
      const startY = Math.floor(Math.random() * gridRows) * GRID;
      const angle = angles[Math.floor(Math.random() * angles.length)] * (Math.PI / 180);
      const length = (2 + Math.floor(Math.random() * 10)) * GRID;
      const endX = clampToCanvas(startX + Math.cos(angle) * length, width);
      const endY = clampToCanvas(startY + Math.sin(angle) * length, height);
      const layer: TraceLayerName =
        Math.random() < 0.72 ? "dim" : Math.random() < 0.65 ? "mid" : "active";

      this.traces.push({ startX, startY, endX, endY, layer });

      if (Math.random() < 0.28) {
        this.nodes.push({
          x: endX,
          y: endY,
          radius: randomBetween(1.8, 3.8),
          pulsePhase: randomBetween(0, Math.PI * 2),
          pulseSpeed: randomBetween(0.3, 0.8),
          energy: randomBetween(0, 0.25),
        });
      }
    }

    this.generateDenseBlock(width * 0.04, height * 0.06, 220, 180);
    this.generateDenseBlock(width * 0.78, height * 0.05, 220, 170);
    this.generateDenseBlock(width * 0.03, height * 0.72, 220, 180);
    this.generateDenseBlock(width * 0.78, height * 0.72, 220, 180);
    this.boostActivity(1.4, 1200);
  }

  protected onUpdate(_dt: number, now: number) {
    if (now > this.activityUntil) {
      this.activityBoost += (1 - this.activityBoost) * 0.06;
    }

    const breath = getBreathController();
    const phase = breath.phase;

    if (now >= this.pulseAt) {
      const period = randomBetween(600, 1500) / Math.max(1, this.activityBoost * (0.8 + phase * 0.6));
      const burstCount =
        this.activityBoost > 2.2 ? 4 : this.activityBoost > 1.45 ? 3 : 2 + Math.floor(Math.random() * 2);
      for (let index = 0; index < burstCount; index += 1) {
        this.spawnPulse(now + index * 40);
      }
      this.pulseAt = now + randomBetween(period * 0.9, period * 1.2);
    }

    this.drawTraces(phase);
    this.drawNodes(now, phase);
    this.drawPulses(now);
    this.drawSweeps(now);
  }

  private generateDenseBlock(x: number, y: number, width: number, height: number) {
    const step = GRID / 2;
    for (let index = 0; index < 72; index += 1) {
      const startX = x + Math.random() * width;
      const startY = y + Math.random() * height;
      const horizontal = Math.random() < 0.5;
      const length = step * (1 + Math.floor(Math.random() * 4));
      const endX = horizontal ? startX + length : startX;
      const endY = horizontal ? startY : startY + length;
      this.traces.push({ startX, startY, endX, endY, layer: "dim", dense: true });
      if (Math.random() < 0.22) {
        this.nodes.push({
          x: endX,
          y: endY,
          radius: randomBetween(1.4, 2.6),
          pulsePhase: randomBetween(0, Math.PI * 2),
          pulseSpeed: randomBetween(0.3, 0.8),
          energy: randomBetween(0, 0.2),
        });
      }
    }
  }

  private drawTraces(phase: number) {
    const opacity = {
      dim: 0.14 + phase * 0.04,
      mid: 0.28 + phase * 0.08,
      active: 0.55 + phase * 0.12,
    } satisfies Record<TraceLayerName, number>;
    const centerX = this.width / 2;
    const centerY = this.height / 2;
    const fadeRadius = Math.min(this.width, this.height) * 0.38 * 1.1;

    for (const trace of this.traces) {
      const midX = (trace.startX + trace.endX) / 2;
      const midY = (trace.startY + trace.endY) / 2;
      const distance = Math.hypot(midX - centerX, midY - centerY);
      const centerFade = distance < fadeRadius ? Math.max(0, distance / fadeRadius) : 1;
      const alpha = opacity[trace.layer] * centerFade;
      this.ctx.beginPath();
      this.ctx.moveTo(trace.startX, trace.startY);
      this.ctx.lineTo(trace.endX, trace.endY);
      this.ctx.strokeStyle = trace.dense
        ? colorWithAlpha(PALETTE.traceMid, 0.35 * centerFade)
        : colorWithAlpha(PALETTE.traceMid, alpha);
      this.ctx.lineWidth =
        trace.layer === "active" ? 0.9 : trace.layer === "mid" ? 0.6 : 0.4;
      this.ctx.stroke();
    }
  }

  private drawNodes(now: number, phase: number) {
    for (const node of this.nodes) {
      const pulse = (Math.sin(now * 0.001 * node.pulseSpeed + node.pulsePhase) + 1) / 2;
      const radius = node.radius + pulse * 0.5 + node.energy * 3.5;
      const alpha = 0.18 + phase * 0.12 + pulse * 0.16 + node.energy * 0.58;

      this.ctx.beginPath();
      this.ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
      this.ctx.fillStyle = `rgba(0, 200, 215, ${alpha})`;
      this.ctx.shadowColor = node.energy > 0.5 ? PALETTE.currentBright : PALETTE.current;
      this.ctx.shadowBlur = 4 + node.energy * 16;
      this.ctx.fill();
      this.ctx.shadowBlur = 0;
      node.energy *= 0.965;
    }
  }

  private drawPulses(now: number) {
    for (let index = this.pulses.length - 1; index >= 0; index -= 1) {
      const pulse = this.pulses[index];
      const t = (now - pulse.startAt) / pulse.duration;
      if (t < 0) {
        continue;
      }
      if (t >= 1) {
        this.pulses.splice(index, 1);
        continue;
      }

      const x = pulse.trace.startX + (pulse.trace.endX - pulse.trace.startX) * t;
      const y = pulse.trace.startY + (pulse.trace.endY - pulse.trace.startY) * t;
      const alpha = t < 0.8 ? 1 : (1 - t) / 0.2;

      this.ctx.beginPath();
      this.ctx.arc(x, y, 2, 0, Math.PI * 2);
      this.ctx.fillStyle = pulse.color;
      this.ctx.globalAlpha = alpha;
      this.ctx.shadowColor = pulse.color;
      this.ctx.shadowBlur = 10;
      this.ctx.fill();
      this.ctx.shadowBlur = 0;
      this.ctx.globalAlpha = 1;

      for (const node of this.nodes) {
        if (Math.hypot(node.x - x, node.y - y) < 8) {
          node.energy = Math.max(node.energy, 1);
        }
      }
    }
  }

  private drawSweeps(now: number) {
    this.sweeps = this.sweeps.filter((sweep) => now - sweep.startAt < 720);
    for (const sweep of this.sweeps) {
      const age = clamp01((now - sweep.startAt) / 720);
      const x = sweep.center.x + sweep.direction * age * this.width * 0.5;
      const opacity = (1 - age) * 0.12;
      this.ctx.fillStyle = `rgba(0, 200, 215, ${opacity})`;
      this.ctx.fillRect(x - 1.5, 0, 3, this.height);
      this.ctx.shadowColor = PALETTE.currentBright;
      this.ctx.shadowBlur = 12;
      this.ctx.fillRect(x - 0.5, 0, 1, this.height);
      this.ctx.shadowBlur = 0;
    }
  }

  private spawnPulse(startAt: number, trace = this.pickTrace()) {
    if (!trace) return;
    this.pulses.push({
      trace,
      startAt,
      duration: randomBetween(560, 1000),
      color: PALETTE.currentBright,
      width: 2,
      glow: 10,
    });
  }

  private pickTrace(targetLayer?: TraceLayerName) {
    const activable = this.traces.filter((trace) =>
      targetLayer ? trace.layer === targetLayer : trace.layer !== "dim",
    );
    if (activable.length === 0) return null;
    return activable[Math.floor(Math.random() * activable.length)] ?? null;
  }

  private pickTraceNear(point: Point2D, preferredLayer?: TraceLayerName) {
    const filtered = this.traces
      .filter((trace) => (preferredLayer ? trace.layer === preferredLayer : trace.layer !== "dim"))
      .map((trace) => ({
        trace,
        distance: distanceToSegment(point.x, point.y, trace.startX, trace.startY, trace.endX, trace.endY),
      }))
      .sort((left, right) => left.distance - right.distance);
    return filtered[0]?.trace ?? this.pickTrace(preferredLayer);
  }
}

function clampToCanvas(value: number, limit: number) {
  return Math.max(0, Math.min(limit, value));
}

function colorWithAlpha(source: string, alpha: number) {
  const match = source.match(/rgba?\(([^)]+)\)/);
  if (!match) return source;
  const channels = match[1].split(",").slice(0, 3).join(",");
  return `rgba(${channels}, ${clamp01(alpha)})`;
}

function distanceToSegment(
  px: number,
  py: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  if (dx === 0 && dy === 0) {
    return Math.hypot(px - x1, py - y1);
  }

  const projection = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy);
  const t = Math.max(0, Math.min(1, projection));
  const cx = x1 + dx * t;
  const cy = y1 + dy * t;
  return Math.hypot(px - cx, py - cy);
}
