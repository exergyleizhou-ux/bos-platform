import * as THREE from "three";

import { getBreathController } from "../core/breath";
import { randomBetween } from "../core/math";
import type { Point2D } from "../core/types";
import { BaseThreeLayer } from "./baseThreeLayer";

const PARTICLE_COUNT = 350;

type Vortex = {
  center: Point2D;
  radius: number;
  spin: number;
  life: number;
  createdAt: number;
};

export class ParticlesLayer extends BaseThreeLayer {
  private readonly positions = new Float32Array(PARTICLE_COUNT * 3);
  private readonly colors = new Float32Array(PARTICLE_COUNT * 3);
  private readonly sizes = new Float32Array(PARTICLE_COUNT);
  private readonly opacity = new Float32Array(PARTICLE_COUNT);
  private readonly masses = new Float32Array(PARTICLE_COUNT);
  private readonly baseX = new Float32Array(PARTICLE_COUNT);
  private readonly baseY = new Float32Array(PARTICLE_COUNT);
  private readonly velocityX = new Float32Array(PARTICLE_COUNT);
  private readonly velocityY = new Float32Array(PARTICLE_COUNT);
  private readonly hues = new Float32Array(PARTICLE_COUNT);
  private readonly geometry = new THREE.BufferGeometry();
  private readonly material = new THREE.PointsMaterial({
    size: 3.2,
    transparent: true,
    vertexColors: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    sizeAttenuation: false,
  });
  private readonly points = new THREE.Points(this.geometry, this.material);
  private attractPoint: Point2D | null = null;
  private attractForce = 0;
  private gravityPoint: Point2D | null = null;
  private gravityForce = 0;
  private repel = false;
  private explosionForce = 0;
  private influenceRadius = 180;
  private vortices: Vortex[] = [];
  private plasmaWaves: Array<{ origin: Point2D; direction: -1 | 1; createdAt: number }> = [];

  constructor() {
    super();
    this.scene.add(this.points);
  }

  setAttractPoint(point: Point2D | null, force = 0, radius?: number) {
    this.attractPoint = point;
    this.attractForce = force;
    if (radius) {
      this.influenceRadius = radius;
    }
  }

  clearAttractPoint() {
    this.attractPoint = null;
    this.attractForce = 0;
  }

  setGravityPoint(point: Point2D | null, force = 0) {
    this.gravityPoint = point;
    this.gravityForce = force;
  }

  clearForces() {
    this.gravityPoint = null;
    this.gravityForce = 0;
    this.clearAttractPoint();
    this.repel = false;
    this.explosionForce = 0;
  }

  setRepel(enabled: boolean) {
    this.repel = enabled;
  }

  explodeFrom(point: Point2D, force = 6) {
    this.gravityPoint = point;
    this.gravityForce = 0;
    this.explosionForce = force;
  }

  bigBang(point: Point2D, force = 8) {
    this.explodeFrom(point, force);
  }

  createVortex(center: Point2D, config: { radius: number; spin: number; life: number }) {
    this.vortices.push({
      center,
      radius: config.radius,
      spin: config.spin,
      life: config.life,
      createdAt: performance.now(),
    });
  }

  setExplosionForce(force: number) {
    this.explosionForce = force;
  }

  setInfluenceRadius(radius: number) {
    this.influenceRadius = radius;
  }

  launchPlasmaWave(origin: Point2D, direction: -1 | 1) {
    this.plasmaWaves.push({ origin, direction, createdAt: performance.now() });
  }

  protected onResize(width: number, height: number) {
    for (let index = 0; index < PARTICLE_COUNT; index += 1) {
      const positionIndex = index * 3;
      this.baseX[index] = randomBetween(0, width);
      this.baseY[index] = randomBetween(0, height);
      this.positions[positionIndex] = this.baseX[index] - width / 2;
      this.positions[positionIndex + 1] = height / 2 - this.baseY[index];
      this.positions[positionIndex + 2] = 0;
      this.sizes[index] = randomBetween(1.5, 4.5);
      this.opacity[index] = randomBetween(0.3, 0.9);
      this.hues[index] = randomBetween(185, 200);
      this.masses[index] = randomBetween(0.5, 2);
    }

    this.geometry.setAttribute("position", new THREE.BufferAttribute(this.positions, 3));
    this.geometry.setAttribute("color", new THREE.BufferAttribute(this.colors, 3));
  }

  protected onUpdate(dt: number, now: number) {
    const breath = getBreathController();
    const influenceRadius = this.influenceRadius * (0.9 + breath.phase * 0.2);
    this.vortices = this.vortices.filter((vortex) => now - vortex.createdAt < vortex.life);
    this.plasmaWaves = this.plasmaWaves.filter((wave) => now - wave.createdAt < 900);

    for (let index = 0; index < PARTICLE_COUNT; index += 1) {
      let screenX = this.positions[index * 3] + this.width / 2;
      let screenY = this.height / 2 - this.positions[index * 3 + 1];
      const mass = this.masses[index];

      const forcePoint = this.gravityPoint ?? this.attractPoint;
      const forceStrength = this.gravityPoint ? this.gravityForce : this.attractForce;
      if (forcePoint && forceStrength > 0) {
        const dx = forcePoint.x - screenX;
        const dy = forcePoint.y - screenY;
        const dist = Math.max(8, Math.hypot(dx, dy));
        const force = (1 - Math.min(dist / influenceRadius, 1)) * 0.08 * forceStrength;
        const direction = this.repel ? -1 : this.gravityPoint ? 1 : 0.4;
        this.velocityX[index] += (dx / dist) * force * direction * mass;
        this.velocityY[index] += (dy / dist) * force * direction * mass;
      }

      if (this.explosionForce > 0 && this.gravityPoint) {
        const dx = screenX - this.gravityPoint.x;
        const dy = screenY - this.gravityPoint.y;
        const dist = Math.max(10, Math.hypot(dx, dy));
        const force = (1 - Math.min(dist / 260, 1)) * this.explosionForce * 0.04;
        this.velocityX[index] += (dx / dist) * force;
        this.velocityY[index] += (dy / dist) * force;
      }

      for (const vortex of this.vortices) {
        const dx = vortex.center.x - screenX;
        const dy = vortex.center.y - screenY;
        const dist = Math.max(12, Math.hypot(dx, dy));
        if (dist > vortex.radius) continue;
        const strength = (1 - dist / vortex.radius) * vortex.spin * 0.05;
        this.velocityX[index] += (-dy / dist) * strength;
        this.velocityY[index] += (dx / dist) * strength;
      }

      for (const wave of this.plasmaWaves) {
        const age = now - wave.createdAt;
        const waveX = wave.origin.x + wave.direction * age * 1.2;
        const distX = Math.abs(screenX - waveX);
        if (distX < 48) {
          this.velocityX[index] += wave.direction * (1 - distX / 48) * 0.28;
        }
      }

      this.velocityX[index] += (this.baseX[index] - screenX) * 0.015;
      this.velocityY[index] += (this.baseY[index] - screenY) * 0.015;
      this.velocityX[index] *= 0.92;
      this.velocityY[index] *= 0.92;

      screenX += this.velocityX[index] * dt * 0.06;
      screenY += this.velocityY[index] * dt * 0.06;

      this.positions[index * 3] = screenX - this.width / 2;
      this.positions[index * 3 + 1] = this.height / 2 - screenY;

      const currentSize = this.sizes[index] * (0.8 + breath.phase * 0.4);
      const currentOpacity = this.opacity[index] * (0.7 + breath.phase * 0.4);
      const color = new THREE.Color(`hsl(${this.hues[index]} 100% 70%)`);
      const colorIndex = index * 3;
      this.colors[colorIndex] = color.r * currentOpacity;
      this.colors[colorIndex + 1] = color.g * currentOpacity;
      this.colors[colorIndex + 2] = color.b * currentOpacity;
      this.material.size = currentSize;
    }

    this.geometry.attributes.position.needsUpdate = true;
    this.geometry.attributes.color.needsUpdate = true;
    this.explosionForce *= 0.93;
  }

  protected override onDispose() {
    this.geometry.dispose();
    this.material.dispose();
  }
}
