import { clamp01, randomBetween } from "../core/math";
import type { Point2D } from "../core/types";
import { BaseCanvasLayer } from "./baseCanvasLayer";

type ArcRecord = {
  id: number;
  from: Point2D;
  to: Point2D;
  cpX: number;
  cpY: number;
  startAt: number;
  duration: number;
  color: string;
  width: number;
  glow: number;
  persistent?: boolean;
};

const ARC_COLORS = ["#D9E7EB", "#F7FCFF", "#FFFFFF"] as const;

export class ElectricArcsLayer extends BaseCanvasLayer {
  private readonly active = new Map<number, ArcRecord>();
  private held: ArcRecord | null = null;
  private nextId = 1;

  spawnArc(from: Point2D, to: Point2D, overrides?: Partial<ArcRecord>) {
    const arc = this.createArc(from, to, overrides);
    this.active.set(arc.id, arc);
    return arc.id;
  }

  spawnFromPoint(point: Point2D, options?: { to?: Point2D; delay?: number }) {
    const angle = randomBetween(0, Math.PI * 2);
    const distance = randomBetween(80, 220);
    const to =
      options?.to ??
      ({
        x: point.x + Math.cos(angle) * distance,
        y: point.y + Math.sin(angle) * distance,
      } satisfies Point2D);
    return this.spawnArc(point, to, {
      startAt: performance.now() + (options?.delay ?? 0),
      duration: randomBetween(460, 920),
    });
  }

  spawnRadial(center: Point2D, angle: number) {
    const distance = randomBetween(140, 280);
    return this.spawnFromPoint(center, {
      to: {
        x: center.x + Math.cos(angle) * distance,
        y: center.y + Math.sin(angle) * distance,
      },
    });
  }

  holdArc(start: Point2D, end: Point2D) {
    if (!this.held) {
      this.held = this.createArc(start, end, {
        persistent: true,
        duration: 999_999,
        width: 2.1,
        glow: 18,
        color: "#F7FCFF",
      });
    }
    this.updateHeldArc(start, end);
  }

  updateHeldArc(start: Point2D, end: Point2D) {
    if (!this.held) return;
    this.held.from = start;
    this.held.to = end;
    const control = getPerpendicularControl(start, end, 0.22);
    this.held.cpX = control.x;
    this.held.cpY = control.y;
  }

  releaseHeldArc() {
    if (!this.held) return;
    this.held.persistent = false;
    this.held.startAt = performance.now();
    this.held.duration = 320;
    this.active.set(this.held.id, this.held);
    this.held = null;
  }

  protected onResize() {}

  protected onUpdate(_dt: number, now: number) {
    if (this.held) {
      this.drawArc(this.held, 1, now);
    }

    for (const [id, arc] of this.active) {
      const elapsed = now - arc.startAt;
      if (elapsed < 0) continue;
      const t = clamp01(elapsed / arc.duration);
      this.drawArc(arc, t, now);
      if (t >= 1) {
        this.active.delete(id);
      }
    }
  }

  private drawArc(arc: ArcRecord, t: number, now: number) {
    const steps = 48;
    const segments = Math.max(2, Math.floor(steps * Math.max(0.06, t)));
    let head: Point2D = arc.from;

    this.ctx.beginPath();
    for (let index = 0; index <= segments; index += 1) {
      const progress = index / steps;
      const point = quadraticBezier(arc.from, { x: arc.cpX, y: arc.cpY }, arc.to, progress);
      head = point;
      if (index === 0) {
        this.ctx.moveTo(point.x, point.y);
      } else {
        this.ctx.lineTo(point.x, point.y);
      }
    }

    const alpha = arc.persistent ? 0.86 : t < 0.82 ? 1 : (1 - t) / 0.18;
    this.ctx.strokeStyle = arc.color;
    this.ctx.lineWidth = arc.width;
    this.ctx.globalAlpha = alpha;
    this.ctx.shadowColor = arc.color;
    this.ctx.shadowBlur = arc.glow;
    this.ctx.stroke();
    this.ctx.shadowBlur = 0;
    this.ctx.globalAlpha = 1;

    this.ctx.beginPath();
    this.ctx.arc(head.x, head.y, arc.width + 1.2 + Math.sin(now * 0.02) * 0.5, 0, Math.PI * 2);
    this.ctx.fillStyle = "#FFFFFF";
    this.ctx.globalAlpha = alpha;
    this.ctx.shadowColor = "#F7FCFF";
    this.ctx.shadowBlur = arc.glow;
    this.ctx.fill();
    this.ctx.shadowBlur = 0;
    this.ctx.globalAlpha = 1;
  }

  private createArc(from: Point2D, to: Point2D, overrides?: Partial<ArcRecord>) {
    const control = getPerpendicularControl(from, to, randomBetween(0.18, 0.34));
    return {
      id: this.nextId++,
      from,
      to,
      cpX: control.x,
      cpY: control.y,
      startAt: performance.now(),
      duration: randomBetween(620, 1320),
      color: ARC_COLORS[Math.floor(Math.random() * ARC_COLORS.length)] ?? ARC_COLORS[0],
      width: randomBetween(0.8, 1.8),
      glow: randomBetween(6, 16),
      ...overrides,
    };
  }
}

function quadraticBezier(start: Point2D, control: Point2D, end: Point2D, t: number) {
  const inverse = 1 - t;
  return {
    x: inverse * inverse * start.x + 2 * inverse * t * control.x + t * t * end.x,
    y: inverse * inverse * start.y + 2 * inverse * t * control.y + t * t * end.y,
  };
}

function getPerpendicularControl(start: Point2D, end: Point2D, bend: number) {
  const midX = (start.x + end.x) / 2;
  const midY = (start.y + end.y) / 2;
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  return {
    x: midX - dy * bend * (Math.random() < 0.5 ? -1 : 1),
    y: midY + dx * bend * (Math.random() < 0.5 ? -1 : 1),
  };
}
