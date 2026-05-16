import * as THREE from "three";

import type { SceneLayer } from "../core/types";

export abstract class BaseThreeLayer implements SceneLayer {
  protected readonly scene = new THREE.Scene();
  protected readonly camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 2000);
  protected readonly renderer = new THREE.WebGLRenderer({
    alpha: true,
    antialias: true,
    powerPreference: "high-performance",
  });
  protected width = 1;
  protected height = 1;
  protected dpr = 1;

  constructor() {
    this.camera.position.z = 1000;
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.domElement.style.position = "absolute";
    this.renderer.domElement.style.inset = "0";
    this.renderer.domElement.style.width = "100%";
    this.renderer.domElement.style.height = "100%";
    this.renderer.domElement.style.pointerEvents = "none";
  }

  mount(host: HTMLElement) {
    host.appendChild(this.renderer.domElement);
  }

  resize(width: number, height: number, dpr: number) {
    this.width = width;
    this.height = height;
    this.dpr = dpr;
    this.renderer.setPixelRatio(dpr);
    this.renderer.setSize(width, height, false);
    this.camera.left = -width / 2;
    this.camera.right = width / 2;
    this.camera.top = height / 2;
    this.camera.bottom = -height / 2;
    this.camera.updateProjectionMatrix();
    this.onResize(width, height, dpr);
  }

  update(dt: number, now: number) {
    this.onUpdate(dt, now);
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.onDispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  protected abstract onResize(width: number, height: number, dpr: number): void;
  protected abstract onUpdate(dt: number, now: number): void;

  protected onDispose() {}
}
