import * as THREE from "three";

import { ARC_COLORS, BOS_COLORS } from "../core/colors";
import { getBreathController } from "../core/breath";
import { clamp01, distance2D, pickRandom, randomBetween } from "../core/math";
import type { Point2D } from "../core/types";
import { BaseThreeLayer } from "./baseThreeLayer";

const NODE_COUNT = 80;
const CONNECT_DISTANCE = 200;
const MAX_SEGMENTS = NODE_COUNT * NODE_COUNT;

export type NeuralNode = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  pulsePhase: number;
  pulseSpeed: number;
  baseR: number;
  energy: number;
};

export class NeuralMeshLayer extends BaseThreeLayer {
  private readonly nodes: NeuralNode[] = [];
  private readonly nodePositions = new Float32Array(NODE_COUNT * 3);
  private readonly nodeColors = new Float32Array(NODE_COUNT * 3);
  private readonly linePositions = new Float32Array(MAX_SEGMENTS * 3 * 2);
  private readonly lineColors = new Float32Array(MAX_SEGMENTS * 3 * 2);
  private readonly pointGeometry = new THREE.BufferGeometry();
  private readonly lineGeometry = new THREE.BufferGeometry();
  private readonly pointMaterial = new THREE.PointsMaterial({
    size: 5,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexColors: true,
    sizeAttenuation: false,
  });
  private readonly lineMaterial = new THREE.LineBasicMaterial({
    transparent: true,
    opacity: 0.45,
    vertexColors: true,
    blending: THREE.AdditiveBlending,
  });
  private readonly points = new THREE.Points(this.pointGeometry, this.pointMaterial);
  private readonly lines = new THREE.LineSegments(this.lineGeometry, this.lineMaterial);
  private expandForce = 1;
  private attractPoint: Point2D | null = null;
  private attractForce = 0;

  constructor() {
    super();
    this.scene.add(this.lines);
    this.scene.add(this.points);
  }

  setExpandForce(force: number) {
    this.expandForce = force;
  }

  setAttractPoint(point: Point2D | null, force = 0) {
    this.attractPoint = point;
    this.attractForce = force;
  }

  getNodes() {
    return this.nodes;
  }

  exciteNode(index: number, amount = 1) {
    const node = this.nodes[index];
    if (!node) return;
    node.energy = Math.max(node.energy, amount);
  }

  selectArcNodes(minDistance = 150, maxDistance = 500) {
    const energetic = [...this.nodes.entries()]
      .sort((a, b) => b[1].energy - a[1].energy)
      .slice(0, 16);
    const start = (energetic[0] ?? pickRandom([...this.nodes.entries()]))?.[0];
    if (start == null) {
      return null;
    }

    const candidates = this.nodes
      .map((node, index) => ({ node, index }))
      .filter(({ index, node }) => {
        if (index === start) return false;
        const distance = distance2D(
          this.nodes[start].x,
          this.nodes[start].y,
          node.x,
          node.y,
        );
        return distance >= minDistance && distance <= maxDistance;
      });

    const target = pickRandom(candidates);
    if (!target) return null;
    return { fromIndex: start, toIndex: target.index };
  }

  protected onResize(width: number, height: number) {
    this.nodes.length = 0;
    for (let index = 0; index < NODE_COUNT; index += 1) {
      this.nodes.push({
        x: randomBetween(-width * 0.42, width * 0.42),
        y: randomBetween(-height * 0.32, height * 0.32),
        vx: randomBetween(-0.3, 0.3),
        vy: randomBetween(-0.3, 0.3),
        pulsePhase: randomBetween(0, Math.PI * 2),
        pulseSpeed: randomBetween(0.5, 1.5),
        baseR: 2.5,
        energy: 0,
      });
    }

    this.pointGeometry.setAttribute("position", new THREE.BufferAttribute(this.nodePositions, 3));
    this.pointGeometry.setAttribute("color", new THREE.BufferAttribute(this.nodeColors, 3));
    this.lineGeometry.setAttribute("position", new THREE.BufferAttribute(this.linePositions, 3));
    this.lineGeometry.setAttribute("color", new THREE.BufferAttribute(this.lineColors, 3));
    this.lineGeometry.setDrawRange(0, 0);
  }

  protected onUpdate(dt: number, now: number) {
    const breath = getBreathController().phase;
    const centerForce = (this.expandForce - 1) * 0.0022;

    for (let index = 0; index < this.nodes.length; index += 1) {
      const node = this.nodes[index];
      const distanceFromCenter = Math.max(1, Math.hypot(node.x, node.y));
      const outwardX = node.x / distanceFromCenter;
      const outwardY = node.y / distanceFromCenter;

      node.vx += outwardX * centerForce * dt;
      node.vy += outwardY * centerForce * dt;

      if (this.attractPoint) {
        const worldX = this.attractPoint.x - this.width / 2;
        const worldY = this.height / 2 - this.attractPoint.y;
        const dx = worldX - node.x;
        const dy = worldY - node.y;
        const dist = Math.max(30, Math.hypot(dx, dy));
        const pull = (1 - Math.min(dist / 420, 1)) * this.attractForce * 0.0014 * dt;
        node.vx += (dx / dist) * pull;
        node.vy += (dy / dist) * pull;
      }

      node.x += node.vx;
      node.y += node.vy;
      node.vx *= 0.992;
      node.vy *= 0.992;
      node.energy *= 0.96;

      if (node.x < -this.width / 2 || node.x > this.width / 2) {
        node.vx *= -1;
      }
      if (node.y < -this.height / 2 || node.y > this.height / 2) {
        node.vy *= -1;
      }

      node.x = Math.max(-this.width / 2, Math.min(this.width / 2, node.x));
      node.y = Math.max(-this.height / 2, Math.min(this.height / 2, node.y));

      const positionIndex = index * 3;
      this.nodePositions[positionIndex] = node.x;
      this.nodePositions[positionIndex + 1] = node.y;
      this.nodePositions[positionIndex + 2] = 0;

      const pulse =
        (Math.sin(now * 0.001 * node.pulseSpeed + node.pulsePhase) + 1) / 2;
      const energyMix = clamp01(node.energy);
      const color = new THREE.Color(
        energyMix > 0.5 ? pickRandom(ARC_COLORS) : BOS_COLORS.neuralCyan,
      );
      const glow = 0.45 + breath * 0.28 + pulse * 0.18 + energyMix * 0.5;
      this.nodeColors[positionIndex] = color.r * glow;
      this.nodeColors[positionIndex + 1] = color.g * glow;
      this.nodeColors[positionIndex + 2] = color.b * glow;
    }

    let segmentCount = 0;
    for (let a = 0; a < this.nodes.length; a += 1) {
      for (let b = a + 1; b < this.nodes.length; b += 1) {
        const nodeA = this.nodes[a];
        const nodeB = this.nodes[b];
        const dist = distance2D(nodeA.x, nodeA.y, nodeB.x, nodeB.y);
        if (dist > CONNECT_DISTANCE) {
          continue;
        }

        const opacity = (1 - dist / CONNECT_DISTANCE) * 0.25 * (0.7 + breath * 0.4);
        const baseIndex = segmentCount * 6;

        this.linePositions[baseIndex] = nodeA.x;
        this.linePositions[baseIndex + 1] = nodeA.y;
        this.linePositions[baseIndex + 2] = 0;
        this.linePositions[baseIndex + 3] = nodeB.x;
        this.linePositions[baseIndex + 4] = nodeB.y;
        this.linePositions[baseIndex + 5] = 0;

        for (let colorIndex = 0; colorIndex < 2; colorIndex += 1) {
          const offset = baseIndex + colorIndex * 3;
          this.lineColors[offset] = 0 * opacity;
          this.lineColors[offset + 1] = 0.78 * opacity;
          this.lineColors[offset + 2] = 0.96 * opacity;
        }

        segmentCount += 1;
      }
    }

    this.lineGeometry.setDrawRange(0, segmentCount * 2);
    this.pointGeometry.attributes.position.needsUpdate = true;
    this.pointGeometry.attributes.color.needsUpdate = true;
    this.lineGeometry.attributes.position.needsUpdate = true;
    this.lineGeometry.attributes.color.needsUpdate = true;
    this.pointMaterial.size = 4.5 + breath * 4;
  }

  protected override onDispose() {
    this.pointGeometry.dispose();
    this.lineGeometry.dispose();
    this.pointMaterial.dispose();
    this.lineMaterial.dispose();
  }
}
