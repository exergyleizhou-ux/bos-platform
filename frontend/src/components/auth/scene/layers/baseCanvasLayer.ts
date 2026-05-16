import type { SceneLayer } from "../core/types";

export abstract class BaseCanvasLayer implements SceneLayer {
  protected readonly canvas = document.createElement("canvas");
  protected readonly ctx: CanvasRenderingContext2D;
  protected width = 1;
  protected height = 1;
  protected dpr = 1;

  constructor() {
    const ctx = this.canvas.getContext("2d");
    if (!ctx) {
      throw new Error("2D canvas context is unavailable");
    }
    this.ctx = ctx;

    this.canvas.style.position = "absolute";
    this.canvas.style.inset = "0";
    this.canvas.style.width = "100%";
    this.canvas.style.height = "100%";
    this.canvas.style.pointerEvents = "none";
  }

  mount(host: HTMLElement) {
    host.appendChild(this.canvas);
  }

  resize(width: number, height: number, dpr: number) {
    this.width = width;
    this.height = height;
    this.dpr = dpr;
    this.canvas.width = Math.max(1, Math.floor(width * dpr));
    this.canvas.height = Math.max(1, Math.floor(height * dpr));
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.onResize(width, height, dpr);
  }

  update(dt: number, now: number) {
    this.ctx.clearRect(0, 0, this.width, this.height);
    this.onUpdate(dt, now);
  }

  dispose() {
    this.onDispose();
    this.canvas.remove();
  }

  protected abstract onResize(width: number, height: number, dpr: number): void;
  protected abstract onUpdate(dt: number, now: number): void;

  protected onDispose() {}
}
