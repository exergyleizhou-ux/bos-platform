import * as THREE from "three";

import { randomBetween } from "../core/math";
import { BaseThreeLayer } from "./baseThreeLayer";

const STAR_COUNT = 2500;

export class StarfieldLayer extends BaseThreeLayer {
  private readonly positions = new Float32Array(STAR_COUNT * 3);
  private readonly colors = new Float32Array(STAR_COUNT * 3);
  private readonly alphas = new Float32Array(STAR_COUNT);
  private readonly sizes = new Float32Array(STAR_COUNT);
  private readonly velocities = new Float32Array(STAR_COUNT * 2);
  private readonly phases = new Float32Array(STAR_COUNT);
  private readonly periods = new Float32Array(STAR_COUNT);
  private readonly geometry = new THREE.BufferGeometry();
  private readonly material = new THREE.PointsMaterial({
    size: 1.25,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexColors: true,
    sizeAttenuation: false,
  });
  private readonly points = new THREE.Points(this.geometry, this.material);
  private accumulator = 0;

  constructor() {
    super();
    this.scene.add(this.points);
  }

  protected onResize(width: number, height: number) {
    for (let index = 0; index < STAR_COUNT; index += 1) {
      const positionIndex = index * 3;
      const velocityIndex = index * 2;
      this.positions[positionIndex] = randomBetween(-width / 2, width / 2);
      this.positions[positionIndex + 1] = randomBetween(-height / 2, height / 2);
      this.positions[positionIndex + 2] = randomBetween(-60, 40);
      this.velocities[velocityIndex] = randomBetween(-0.02, 0.02);
      this.velocities[velocityIndex + 1] = randomBetween(-0.02, 0.02);
      this.alphas[index] = randomBetween(0.2, 0.7);
      this.sizes[index] = randomBetween(0.3, 1.5);
      this.phases[index] = randomBetween(0, Math.PI * 2);
      this.periods[index] = randomBetween(2000, 6000);
    }

    this.syncColors();
    this.geometry.setAttribute("position", new THREE.BufferAttribute(this.positions, 3));
    this.geometry.setAttribute("color", new THREE.BufferAttribute(this.colors, 3));
  }

  protected onUpdate(dt: number, now: number) {
    this.accumulator += dt;
    if (this.accumulator < 33) {
      return;
    }
    this.accumulator = 0;

    for (let index = 0; index < STAR_COUNT; index += 1) {
      const positionIndex = index * 3;
      const velocityIndex = index * 2;
      const x = this.positions[positionIndex] + this.velocities[velocityIndex] * dt;
      const y = this.positions[positionIndex + 1] + this.velocities[velocityIndex + 1] * dt;
      const wrappedX =
        x < -this.width / 2 ? this.width / 2 : x > this.width / 2 ? -this.width / 2 : x;
      const wrappedY =
        y < -this.height / 2 ? this.height / 2 : y > this.height / 2 ? -this.height / 2 : y;

      this.positions[positionIndex] = wrappedX;
      this.positions[positionIndex + 1] = wrappedY;

      const flicker =
        this.alphas[index] +
        Math.sin((now / this.periods[index]) * Math.PI * 2 + this.phases[index]) * 0.15;
      const alpha = Math.max(0.04, flicker);
      const tone = 0.74 + this.sizes[index] * 0.12;
      this.colors[positionIndex] = tone * alpha;
      this.colors[positionIndex + 1] = 0.88 * alpha;
      this.colors[positionIndex + 2] = 1 * alpha;
    }

    this.geometry.attributes.position.needsUpdate = true;
    this.geometry.attributes.color.needsUpdate = true;
  }

  protected override onDispose() {
    this.geometry.dispose();
    this.material.dispose();
  }

  private syncColors() {
    for (let index = 0; index < STAR_COUNT; index += 1) {
      const positionIndex = index * 3;
      const alpha = this.alphas[index];
      this.colors[positionIndex] = 0.7 * alpha;
      this.colors[positionIndex + 1] = 0.82 * alpha;
      this.colors[positionIndex + 2] = 1 * alpha;
    }
  }
}
