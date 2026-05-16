import { getBreathController } from "../core/breath";
import { lerp, randomBetween } from "../core/math";
import type { Point2D } from "../core/types";
import { BaseCanvasLayer } from "./baseCanvasLayer";

type PlasmaCloud = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  phase: number;
  phaseSpeed: number;
  opacity: number;
  target: Point2D | null;
  targetForce: number;
};

type LightningSegment = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

type LightningBolt = {
  segments: LightningSegment[];
  startTime: number;
  duration: number;
  color: string;
  width: number;
};

type DataDrop = {
  y: number;
  char: string;
  alpha: number;
  size: number;
  timer: number;
};

type Stream = {
  x: number;
  baseSpeed: number;
  speedBoost: number;
  drops: DataDrop[];
};

const DATA_CHARS = "01アイウエオカキクケコ∑∆Ωπ≈≠∞◈◇▲△●○";
const CLOUD_COUNT = 40;
const STREAMS_PER_SIDE = 8;
const MAGNETIC_LINES = 24;
const TIDE_PERIOD = 20_000;

export class AtmosphereLayer extends BaseCanvasLayer {
  private readonly clouds: PlasmaCloud[] = [];
  private readonly bolts: LightningBolt[] = [];
  private readonly streams: Stream[] = [];
  private pointer: Point2D = { x: 0, y: 0 };
  private magneticFocus: Point2D | null = null;
  private magneticStrength = 0;
  private fieldExtension = 1;
  private fieldTarget = 1;
  private streamBoost = 1;
  private streamBoostUntil = 0;
  private nextLightningAt = 0;
  private lightningStormUntil = 0;

  setPointer(point: Point2D) {
    this.pointer = point;
  }

  setMagneticFocus(point: Point2D | null, strength = 0) {
    this.magneticFocus = point;
    this.magneticStrength = strength;
  }

  expandField(multiplier: number, duration = 1200) {
    this.fieldTarget = multiplier;
    window.setTimeout(() => {
      this.fieldTarget = 1;
    }, duration);
  }

  accelerateStreams(multiplier: number, duration: number) {
    this.streamBoost = multiplier;
    this.streamBoostUntil = performance.now() + duration;
  }

  pulseClouds(center: Point2D, force: number) {
    for (const cloud of this.clouds) {
      const dx = cloud.x - center.x;
      const dy = cloud.y - center.y;
      const dist = Math.max(1, Math.hypot(dx, dy));
      cloud.vx += (dx / dist) * force * 0.25;
      cloud.vy += (dy / dist) * force * 0.25;
    }
  }

  triggerLightningStorm(duration = 3000, burstCount = 3) {
    this.lightningStormUntil = performance.now() + duration;
    for (let index = 0; index < burstCount; index += 1) {
      this.spawnLightning();
    }
  }

  protected onResize(width: number, height: number) {
    this.pointer = { x: width / 2, y: height / 2 };
    this.clouds.length = 0;
    this.streams.length = 0;

    for (let index = 0; index < CLOUD_COUNT; index += 1) {
      this.clouds.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.15,
        vy: (Math.random() - 0.5) * 0.15,
        radius: 60 + Math.random() * 120,
        phase: Math.random() * Math.PI * 2,
        phaseSpeed: 0.0004 + Math.random() * 0.0003,
        opacity: 0.03 + Math.random() * 0.04,
        target: null,
        targetForce: 0,
      });
    }

    const leftBounds = [20, 130];
    const rightBounds = [Math.max(width - 130, width * 0.8), Math.max(width - 20, width * 0.84)];
    for (let index = 0; index < STREAMS_PER_SIDE; index += 1) {
      this.streams.push(this.createStream(randomBetween(leftBounds[0], leftBounds[1])));
      this.streams.push(this.createStream(randomBetween(rightBounds[0], rightBounds[1])));
    }
    this.nextLightningAt = performance.now() + randomBetween(4000, 12000);
  }

  protected onUpdate(dt: number, now: number) {
    const breath = getBreathController().phase;
    const center = { x: this.width / 2, y: this.height / 2 };

    this.fieldExtension = lerp(this.fieldExtension, this.fieldTarget, 0.08);
    if (now > this.streamBoostUntil) {
      this.streamBoost = lerp(this.streamBoost, 1, 0.05);
    }

    if (now >= this.nextLightningAt || (this.lightningStormUntil > now && Math.random() < 0.08)) {
      this.spawnLightning();
      this.nextLightningAt = now + randomBetween(4000, 12000);
    }

    this.drawTide(now);
    this.updateClouds(dt);
    this.drawClouds(breath);
    this.updateStreams();
    this.drawStreams(breath);
    this.drawMagneticField(center, breath);
    this.drawLightning(now);
  }

  private createStream(x: number): Stream {
    return {
      x,
      baseSpeed: randomBetween(0.4, 0.9),
      speedBoost: 1,
      drops: Array.from({ length: 8 }, () => ({
        y: Math.random() * this.height,
        char: this.randomChar(),
        alpha: 0.04 + Math.random() * 0.08,
        size: 9 + Math.random() * 3,
        timer: 0,
      })),
    };
  }

  private updateClouds(dt: number) {
    for (const cloud of this.clouds) {
      if (cloud.target) {
        const dx = cloud.target.x - cloud.x;
        const dy = cloud.target.y - cloud.y;
        const dist = Math.max(1, Math.hypot(dx, dy));
        cloud.vx += (dx / dist) * cloud.targetForce * 0.02;
        cloud.vy += (dy / dist) * cloud.targetForce * 0.02;
      }

      cloud.x += cloud.vx * dt * 0.06;
      cloud.y += cloud.vy * dt * 0.06;
      cloud.phase += cloud.phaseSpeed * dt;
      cloud.vx *= 0.996;
      cloud.vy *= 0.996;

      if (cloud.x < -cloud.radius) cloud.x = this.width + cloud.radius;
      if (cloud.x > this.width + cloud.radius) cloud.x = -cloud.radius;
      if (cloud.y < -cloud.radius) cloud.y = this.height + cloud.radius;
      if (cloud.y > this.height + cloud.radius) cloud.y = -cloud.radius;
    }
  }

  private drawClouds(breathPhase: number) {
    for (const cloud of this.clouds) {
      const pulse = Math.sin(cloud.phase) * 0.3 + 0.7;
      const opacity = cloud.opacity * pulse * (0.8 + breathPhase * 0.2);
      const gradient = this.ctx.createRadialGradient(
        cloud.x,
        cloud.y,
        0,
        cloud.x,
        cloud.y,
        cloud.radius * pulse,
      );
      gradient.addColorStop(0, `rgba(0, 195, 210, ${opacity})`);
      gradient.addColorStop(0.5, `rgba(0, 175, 190, ${opacity * 0.4})`);
      gradient.addColorStop(1, "rgba(0, 160, 180, 0)");
      this.ctx.beginPath();
      this.ctx.arc(cloud.x, cloud.y, cloud.radius * pulse, 0, Math.PI * 2);
      this.ctx.fillStyle = gradient;
      this.ctx.fill();
    }
  }

  private updateStreams() {
    for (const stream of this.streams) {
      const speed = stream.baseSpeed * this.streamBoost;
      for (const drop of stream.drops) {
        drop.y += speed;
        drop.timer += 1;
        if (drop.timer > 20) {
          drop.char = this.randomChar();
          drop.timer = 0;
        }
        if (drop.y > this.height + 20) {
          drop.y = -20;
        }
      }
    }
  }

  private drawStreams(breathPhase: number) {
    for (const stream of this.streams) {
      for (const drop of stream.drops) {
        this.ctx.font = `${drop.size}px "Share Tech Mono", monospace`;
        this.ctx.fillStyle = `rgba(0, 185, 200, ${drop.alpha * (0.8 + breathPhase * 0.3)})`;
        this.ctx.fillText(drop.char, stream.x, drop.y);
      }
    }
  }

  private drawMagneticField(center: Point2D, breathPhase: number) {
    const focus = this.magneticFocus ?? this.pointer;
    const radius = Math.min(this.width, this.height) * 0.38;
    for (let index = 0; index < MAGNETIC_LINES; index += 1) {
      const angle = (index / MAGNETIC_LINES) * Math.PI * 2;
      const startX = center.x + Math.cos(angle) * radius * 0.16;
      const startY = center.y + Math.sin(angle) * radius * 0.16;
      const endX = center.x + Math.cos(angle) * (radius + 30 * this.fieldExtension);
      const endY = center.y + Math.sin(angle) * (radius + 30 * this.fieldExtension);

      const midX = (startX + endX) / 2;
      const midY = (startY + endY) / 2;
      const dx = focus.x - midX;
      const dy = focus.y - midY;
      const distance = Math.max(1, Math.hypot(dx, dy));
      const influence = Math.min(1, 200 / distance) * (1 + this.magneticStrength * 0.5);
      const cpX = midX + dx * influence * 0.15;
      const cpY = midY + dy * influence * 0.15;
      const armAngles = [270, 30, 150];
      const degrees = (angle * 180) / Math.PI;
      const nearArm = armAngles.some((arm) => Math.abs((((degrees + 360) % 360) - arm + 540) % 360 - 180) < 20);
      const alpha = nearArm ? 0.2 + breathPhase * 0.12 : 0.06 + breathPhase * 0.04;

      this.ctx.beginPath();
      this.ctx.moveTo(startX, startY);
      this.ctx.quadraticCurveTo(cpX, cpY, endX, endY);
      this.ctx.strokeStyle = `rgba(0, 185, 200, ${alpha})`;
      this.ctx.lineWidth = nearArm ? 0.7 : 0.4;
      this.ctx.stroke();
    }
  }

  private spawnLightning() {
    const side = Math.floor(Math.random() * 4);
    let startX = 0;
    let startY = 0;
    if (side === 0) {
      startX = Math.random() * this.width;
      startY = 0;
    } else if (side === 1) {
      startX = this.width;
      startY = Math.random() * this.height;
    } else if (side === 2) {
      startX = Math.random() * this.width;
      startY = this.height;
    } else {
      startX = 0;
      startY = Math.random() * this.height;
    }

    const segments = this.generateBoltPath(
      startX,
      startY,
      startX + (Math.random() - 0.5) * 800,
      startY + (Math.random() - 0.5) * 800,
      4,
    );
    this.bolts.push({
      segments,
      startTime: performance.now(),
      duration: 120 + Math.random() * 80,
      color: Math.random() < 0.8 ? "#00C8D4" : "#1AFFE4",
      width: 0.5 + Math.random() * 0.8,
    });
  }

  private generateBoltPath(x1: number, y1: number, x2: number, y2: number, depth: number): LightningSegment[] {
    if (depth === 0) {
      return [{ x1, y1, x2, y2 }];
    }
    const midX = (x1 + x2) / 2 + (Math.random() - 0.5) * (60 / depth);
    const midY = (y1 + y2) / 2 + (Math.random() - 0.5) * (60 / depth);
    const segments = [
      ...this.generateBoltPath(x1, y1, midX, midY, depth - 1),
      ...this.generateBoltPath(midX, midY, x2, y2, depth - 1),
    ];
    if (Math.random() < 0.3 && depth > 1) {
      const branchX = midX + (Math.random() - 0.5) * 200;
      const branchY = midY + (Math.random() - 0.5) * 200;
      segments.push(...this.generateBoltPath(midX, midY, branchX, branchY, depth - 2));
    }
    return segments;
  }

  private drawLightning(now: number) {
    this.bolts.splice(
      0,
      this.bolts.length - 12 > 0 ? this.bolts.length - 12 : 0,
    );
    for (let index = this.bolts.length - 1; index >= 0; index -= 1) {
      const bolt = this.bolts[index];
      const t = (now - bolt.startTime) / bolt.duration;
      if (t >= 1) {
        this.bolts.splice(index, 1);
        continue;
      }
      const flicker = Math.random() < 0.3 ? 0.3 : 1;
      const alpha = (1 - t) * 0.6 * flicker;
      for (const segment of bolt.segments) {
        this.ctx.beginPath();
        this.ctx.moveTo(segment.x1, segment.y1);
        this.ctx.lineTo(segment.x2, segment.y2);
        this.ctx.strokeStyle = withAlpha(bolt.color, alpha);
        this.ctx.lineWidth = bolt.width;
        this.ctx.shadowColor = bolt.color;
        this.ctx.shadowBlur = 6;
        this.ctx.stroke();
      }
      this.ctx.shadowBlur = 0;
    }
  }

  private drawTide(timestamp: number) {
    const phase = (Math.sin((timestamp / TIDE_PERIOD) * Math.PI * 2) + 1) / 2;
    const centerX = this.width / 2;
    const centerY = this.height / 2;
    const gradient = this.ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, this.height * 0.7);
    gradient.addColorStop(0, `rgba(0, 175, 190, ${0.04 + phase * 0.04})`);
    gradient.addColorStop(0.6, `rgba(0, 160, 175, ${0.01 + phase * 0.02})`);
    gradient.addColorStop(1, "rgba(0, 150, 165, 0)");
    this.ctx.fillStyle = gradient;
    this.ctx.fillRect(0, 0, this.width, this.height);
  }

  private randomChar() {
    return DATA_CHARS[Math.floor(Math.random() * DATA_CHARS.length)] ?? "0";
  }
}

function withAlpha(hex: string, alpha: number) {
  const clean = hex.replace("#", "");
  const value = clean.length === 3
    ? clean
        .split("")
        .map((part) => `${part}${part}`)
        .join("")
    : clean;
  const r = Number.parseInt(value.slice(0, 2), 16);
  const g = Number.parseInt(value.slice(2, 4), 16);
  const b = Number.parseInt(value.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
