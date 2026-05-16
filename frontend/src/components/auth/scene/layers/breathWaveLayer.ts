import * as THREE from "three";

import { getBreathController } from "../core/breath";
import { BOS_COLORS } from "../core/colors";
import type { Point2D } from "../core/types";
import { BaseThreeLayer } from "./baseThreeLayer";

const RING_COUNT = 6;

export class BreathWaveLayer extends BaseThreeLayer {
  private readonly rings: THREE.LineLoop[] = [];
  private readonly ringMaterials: THREE.LineBasicMaterial[] = [];
  private readonly coreMaterial = new THREE.SpriteMaterial({
    color: BOS_COLORS.neuralCyan,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  private readonly core = new THREE.Sprite(this.coreMaterial);
  private scaleMultiplier = 1.18;
  private bigExpandStrength = 1;
  private bigExpandUntil = 0;
  private focus: Point2D = { x: 0.5, y: 0.52 };

  constructor() {
    super();
    for (let index = 0; index < RING_COUNT; index += 1) {
      const curve = new THREE.EllipseCurve(0, 0, 1, 1, 0, Math.PI * 2, false, 0);
      const points = curve
        .getPoints(128)
        .map((point: THREE.Vector2) => new THREE.Vector3(point.x, point.y, 0));
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const material = new THREE.LineBasicMaterial({
        color: BOS_COLORS.neuralCyan,
        transparent: true,
        opacity: 0.4,
        blending: THREE.AdditiveBlending,
      });
      const ring = new THREE.LineLoop(geometry, material);
      this.rings.push(ring);
      this.ringMaterials.push(material);
      this.scene.add(ring);
    }

    this.scene.add(this.core);
  }

  setScaleMultiplier(multiplier: number) {
    this.scaleMultiplier = multiplier;
  }

  bigExpand(multiplier: number, duration: number) {
    this.bigExpandStrength = multiplier;
    this.bigExpandUntil = performance.now() + duration;
  }

  setFocus(point: Point2D) {
    this.focus = point;
  }

  protected onResize() {}

  protected onUpdate(_dt: number, now: number) {
    const breath = getBreathController();
    const maxRadius = Math.max(this.width, this.height) * 0.65;
    const worldX = this.focus.x * this.width - this.width / 2;
    const worldY = this.height / 2 - this.focus.y * this.height;
    const bigExpandPulse = now < this.bigExpandUntil ? this.bigExpandStrength : 1;

    for (let index = 0; index < this.rings.length; index += 1) {
      const ring = this.rings[index];
      const material = this.ringMaterials[index];
      const delay = index * 0.18;
      const phase = (breath.phase + delay) % 1;
      const radius = Math.max(1, phase * maxRadius * this.scaleMultiplier * bigExpandPulse);
      const opacity = Math.min(0.9, (1 - phase) * (1 - phase) * 0.95 + 0.06);

      ring.position.set(worldX, worldY, 0);
      ring.scale.set(radius, radius * 0.68, 1);
      material.opacity = opacity;
      material.color.set(breath.color);
    }

    const coreSize = 18 + breath.phase * 28 * this.scaleMultiplier;
    this.core.position.set(worldX, worldY, 0);
    this.core.scale.set(coreSize, coreSize, 1);
    this.coreMaterial.opacity = 0.78 + breath.phase * 0.22;
    this.coreMaterial.color.set(breath.color);
  }

  protected override onDispose() {
    for (const ring of this.rings) {
      ring.geometry.dispose();
    }
    for (const material of this.ringMaterials) {
      material.dispose();
    }
    this.coreMaterial.dispose();
  }
}
