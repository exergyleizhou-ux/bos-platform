import { BOS_COLORS } from "./colors";
import { clamp01 } from "./math";

declare global {
  interface Window {
    BOS_BREATH?: BOSBreathController;
  }
}

const DEFAULT_PERIOD = 4200;

export class BOSBreathController {
  phase = 0;
  period = DEFAULT_PERIOD;
  color: string = BOS_COLORS.neuralCyan;
  paused = false;
  private elapsed = 0;

  update(dt: number) {
    if (!this.paused) {
      this.elapsed += dt;
    }

    this.phase =
      (Math.sin((this.elapsed / this.period) * Math.PI * 2 - Math.PI / 2) + 1) / 2;
    this.updateCSSVars();
  }

  setPeriod(period: number) {
    this.period = Math.max(800, period);
    this.updateCSSVars();
  }

  setColor(color: string) {
    this.color = color;
    this.updateCSSVars();
  }

  pause() {
    this.paused = true;
    this.updateCSSVars();
  }

  resume() {
    this.paused = false;
    this.updateCSSVars();
  }

  reset() {
    this.elapsed = 0;
    this.period = DEFAULT_PERIOD;
    this.color = BOS_COLORS.neuralCyan;
    this.paused = false;
    this.phase = 0;
    this.updateCSSVars();
  }

  updateCSSVars() {
    const root = document.documentElement;
    root.style.setProperty("--breath-phase", this.phase.toFixed(4));
    root.style.setProperty("--breath-glow", `${4 + this.phase * 18}px`);
    root.style.setProperty("--breath-opacity", `${0.12 + this.phase * 0.34}`);
    root.style.setProperty("--breath-color", this.color);
    root.style.setProperty(
      "--vignette-strength",
      `${0.7 + (1 - clamp01(this.phase)) * 0.15}`,
    );
  }
}

export function getBreathController() {
  if (!window.BOS_BREATH) {
    window.BOS_BREATH = new BOSBreathController();
    window.BOS_BREATH.updateCSSVars();
  }

  return window.BOS_BREATH;
}
