import { getBreathController } from "../core/breath";
import { clamp01, lerp } from "../core/math";
import { BaseCanvasLayer } from "./baseCanvasLayer";

const ARM_ANGLES = [270, 30, 150].map((degrees) => (degrees * Math.PI) / 180);
const PALETTE = {
  current: "#00C8D4",
  currentBright: "#1AFFE4",
  currentHot: "rgba(200,255,255,0.95)",
};

export class ReactorCoreLayer extends BaseCanvasLayer {
  private compression = 0;
  private expansion = 0;
  private bigPulse = 0;
  private bigPulseUntil = 0;
  private confirmPulse = 0;
  private confirmUntil = 0;
  private success = 0;
  private successUntil = 0;

  setFocus(_point: { x: number; y: number }) {
    // The reactor now owns the screen center. Keep the API for callers without relocating the core.
  }

  setCompression(value: number) {
    this.compression = clamp01(value);
  }

  setExpansion(value: number) {
    this.expansion = clamp01(value);
  }

  bigExpand(multiplier: number, duration: number) {
    this.bigPulse = Math.max(1, multiplier);
    this.bigPulseUntil = performance.now() + duration;
  }

  triggerConfirmPulse(duration = 900) {
    this.confirmPulse = 1;
    this.confirmUntil = performance.now() + duration;
  }

  triggerSuccess(duration = 1100) {
    this.success = 1;
    this.successUntil = performance.now() + duration;
  }

  protected onResize() {}

  protected onUpdate(_dt: number, now: number) {
    const breath = getBreathController();
    const breathPhase = breath.phase;
    const cx = this.width / 2;
    const cy = this.height / 2;

    if (now > this.bigPulseUntil) {
      this.bigPulse = lerp(this.bigPulse, 1, 0.08);
    }
    if (now > this.confirmUntil) {
      this.confirmPulse = lerp(this.confirmPulse, 0, 0.12);
    }
    if (now > this.successUntil) {
      this.success = lerp(this.success, 0, 0.08);
    }

    const baseRadius = Math.min(this.width, this.height) * 0.38;
    const breathScale = 1 + breathPhase * 0.055 + this.expansion * 0.05 - this.compression * 0.07;
    const reactorRadius = baseRadius * breathScale * Math.max(1, this.bigPulse);

    this.drawHalo(cx, cy, reactorRadius, breathPhase);
    this.drawOuterRings(cx, cy, reactorRadius, breathPhase);
    this.drawTickMarks(cx, cy, reactorRadius, breathPhase);
    this.drawArms(cx, cy, reactorRadius, breathPhase);
    this.drawArmNodes(cx, cy, reactorRadius, breathPhase);
    this.drawCenterCore(cx, cy, reactorRadius, breathPhase);
    this.drawBreathPulses(cx, cy, reactorRadius, breathPhase, now);
    this.drawSuccessWash(cx, cy, reactorRadius);
  }

  private drawHalo(cx: number, cy: number, radius: number, phase: number) {
    const gradient = this.ctx.createRadialGradient(cx, cy, radius * 0.04, cx, cy, radius * 1.2);
    gradient.addColorStop(0, `rgba(0, 200, 215, ${0.08 + phase * 0.08})`);
    gradient.addColorStop(0.45, `rgba(0, 175, 190, ${0.04 + phase * 0.04})`);
    gradient.addColorStop(1, "rgba(0, 175, 190, 0)");
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, radius * 1.2, 0, Math.PI * 2);
    this.ctx.fillStyle = gradient;
    this.ctx.fill();
  }

  private drawOuterRings(cx: number, cy: number, radius: number, phase: number) {
    this.strokeRing(cx, cy, radius, 1 + phase * 0.6, 0.45 + phase * 0.45);
    this.strokeRing(cx, cy, radius + 12, 0.5, 0.12 + phase * 0.08);
    this.strokeRing(cx, cy, radius * 0.68, 0.7, 0.25 + phase * 0.15);
    this.strokeRing(cx, cy, radius * 0.16, 0.8, 0.4 + phase * 0.35);
  }

  private drawTickMarks(cx: number, cy: number, radius: number, phase: number) {
    for (let degree = 0; degree < 360; degree += 6) {
      const angle = ((degree - 90) * Math.PI) / 180;
      const major = degree % 30 === 0;
      const mid = degree % 12 === 0;
      const length = major ? 12 : mid ? 6 : 3;
      const alpha = major
        ? 0.55 + phase * 0.25
        : mid
          ? 0.25 + phase * 0.1
          : 0.1 + phase * 0.05;
      const width = major ? 0.9 : 0.5;
      const startX = cx + Math.cos(angle) * radius;
      const startY = cy + Math.sin(angle) * radius;
      const endX = cx + Math.cos(angle) * (radius - length);
      const endY = cy + Math.sin(angle) * (radius - length);
      this.ctx.beginPath();
      this.ctx.moveTo(startX, startY);
      this.ctx.lineTo(endX, endY);
      this.ctx.strokeStyle = `rgba(0, 195, 210, ${alpha})`;
      this.ctx.lineWidth = width;
      if (major) {
        this.ctx.shadowColor = "#00C8D4";
        this.ctx.shadowBlur = 3 + phase * 4;
      }
      this.ctx.stroke();
      this.ctx.shadowBlur = 0;
    }
  }

  private drawArms(cx: number, cy: number, radius: number, phase: number) {
    const alpha = 0.7 + phase * 0.25 + this.confirmPulse * 0.12;
    for (const angle of ARM_ANGLES) {
      const startX = cx + Math.cos(angle) * radius * 0.16;
      const startY = cy + Math.sin(angle) * radius * 0.16;
      const endX = cx + Math.cos(angle) * radius * 0.68;
      const endY = cy + Math.sin(angle) * radius * 0.68;

      this.ctx.beginPath();
      this.ctx.moveTo(startX, startY);
      this.ctx.lineTo(endX, endY);
      this.ctx.strokeStyle = `rgba(0, 195, 210, ${0.15 + phase * 0.12})`;
      this.ctx.lineWidth = 6;
      this.ctx.stroke();

      this.ctx.beginPath();
      this.ctx.moveTo(startX, startY);
      this.ctx.lineTo(endX, endY);
      this.ctx.strokeStyle = `rgba(0, 205, 220, ${alpha})`;
      this.ctx.lineWidth = 1.5;
      this.ctx.shadowColor = "#00C8D4";
      this.ctx.shadowBlur = 8 + phase * 14;
      this.ctx.stroke();
      this.ctx.shadowBlur = 0;
    }
  }

  private drawArmNodes(cx: number, cy: number, radius: number, phase: number) {
    for (const angle of ARM_ANGLES) {
      const nodeX = cx + Math.cos(angle) * radius * 0.68;
      const nodeY = cy + Math.sin(angle) * radius * 0.68;
      const glowRadius = 14 + phase * 8;
      const glow = this.ctx.createRadialGradient(nodeX, nodeY, 0, nodeX, nodeY, glowRadius);
      glow.addColorStop(0, `rgba(0, 210, 225, ${0.5 + phase * 0.3})`);
      glow.addColorStop(1, "rgba(0, 195, 210, 0)");
      this.ctx.beginPath();
      this.ctx.arc(nodeX, nodeY, glowRadius, 0, Math.PI * 2);
      this.ctx.fillStyle = glow;
      this.ctx.fill();

      this.ctx.beginPath();
      this.ctx.arc(nodeX, nodeY, 5 + phase * 2, 0, Math.PI * 2);
      this.ctx.strokeStyle = `rgba(0, 215, 228, ${0.8 + phase * 0.15})`;
      this.ctx.lineWidth = 1;
      this.ctx.shadowColor = "#00C8D4";
      this.ctx.shadowBlur = 10 + phase * 12;
      this.ctx.stroke();
      this.ctx.shadowBlur = 0;

      this.ctx.beginPath();
      this.ctx.arc(nodeX, nodeY, 2.5, 0, Math.PI * 2);
      this.ctx.fillStyle = "#1AFFE4";
      this.ctx.shadowColor = "#1AFFE4";
      this.ctx.shadowBlur = 15;
      this.ctx.fill();
      this.ctx.shadowBlur = 0;
    }
  }

  private drawCenterCore(cx: number, cy: number, radius: number, phase: number) {
    const coreRadius = 4 + phase * 7 + this.compression * 2;
    const nearGlow = 20 + phase * 24 + this.expansion * 14;
    const farGlow = 48 + phase * 36 + this.expansion * 18;

    const far = this.ctx.createRadialGradient(cx, cy, 0, cx, cy, farGlow);
    far.addColorStop(0, `rgba(0, 195, 210, ${0.08 + phase * 0.06})`);
    far.addColorStop(1, "rgba(0, 195, 210, 0)");
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, farGlow, 0, Math.PI * 2);
    this.ctx.fillStyle = far;
    this.ctx.fill();

    const near = this.ctx.createRadialGradient(cx, cy, 0, cx, cy, nearGlow);
    near.addColorStop(0, `rgba(0, 210, 225, ${0.4 + phase * 0.2})`);
    near.addColorStop(1, "rgba(0, 195, 210, 0)");
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, nearGlow, 0, Math.PI * 2);
    this.ctx.fillStyle = near;
    this.ctx.fill();

    this.ctx.beginPath();
    this.ctx.arc(cx, cy, coreRadius, 0, Math.PI * 2);
    this.ctx.fillStyle = "rgba(200, 255, 255, 0.95)";
    this.ctx.shadowColor = "#1AFFE4";
    this.ctx.shadowBlur = 12 + phase * 28;
    this.ctx.fill();
    this.ctx.shadowBlur = 0;

    const clampRing = radius * (0.22 + this.compression * 0.06);
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, clampRing, 0, Math.PI * 2);
    this.ctx.strokeStyle = `rgba(0, 210, 225, ${0.24 + this.compression * 0.4})`;
    this.ctx.lineWidth = 0.9 + this.compression * 0.5;
    this.ctx.stroke();
  }

  private drawBreathPulses(cx: number, cy: number, radius: number, phase: number, now: number) {
    for (let index = 0; index < 4; index += 1) {
      const delayed = (phase + index * 0.22) % 1;
      const eased = 1 - Math.pow(1 - delayed, 2.5);
      const ringRadius = eased * radius * 0.95;
      const opacity = Math.pow(1 - delayed, 2) * 0.4 + this.confirmPulse * 0.08;
      if (ringRadius < 8 || opacity < 0.01) continue;
      this.ctx.beginPath();
      this.ctx.arc(cx, cy, ringRadius, 0, Math.PI * 2);
      this.ctx.strokeStyle = `rgba(0, 200, 215, ${opacity})`;
      this.ctx.lineWidth = Math.max(0.45, (1 - delayed) * 1.25);
      this.ctx.stroke();
    }

    const sweepPhase = ((now % 5200) / 5200) * Math.PI * 2;
    for (const angle of ARM_ANGLES) {
      const progress = (Math.sin(sweepPhase + angle) + 1) / 2;
      const x = cx + Math.cos(angle) * lerp(radius * 0.18, radius * 0.72, progress);
      const y = cy + Math.sin(angle) * lerp(radius * 0.18, radius * 0.72, progress);
      this.ctx.beginPath();
      this.ctx.arc(x, y, 2, 0, Math.PI * 2);
      this.ctx.fillStyle = PALETTE.currentHot;
      this.ctx.shadowColor = PALETTE.currentBright;
      this.ctx.shadowBlur = 10;
      this.ctx.fill();
      this.ctx.shadowBlur = 0;
    }
  }

  private drawSuccessWash(cx: number, cy: number, radius: number) {
    if (this.success <= 0.01) return;
    const wash = this.ctx.createRadialGradient(cx, cy, radius * 0.2, cx, cy, radius * 1.4);
    wash.addColorStop(0, `rgba(0, 255, 157, ${this.success * 0.18})`);
    wash.addColorStop(1, "rgba(0, 255, 157, 0)");
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, radius * 1.4, 0, Math.PI * 2);
    this.ctx.fillStyle = wash;
    this.ctx.fill();
  }

  private strokeRing(cx: number, cy: number, radius: number, width: number, alpha: number) {
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    this.ctx.strokeStyle = `rgba(0, 200, 215, ${alpha})`;
    this.ctx.lineWidth = width;
    this.ctx.shadowColor = "#00C8D4";
    this.ctx.shadowBlur = width >= 1
      ? 8 + alpha * 22
      : width > 0.8
        ? 6 + alpha * 14
        : 0;
    this.ctx.stroke();
    this.ctx.shadowBlur = 0;
  }
}
