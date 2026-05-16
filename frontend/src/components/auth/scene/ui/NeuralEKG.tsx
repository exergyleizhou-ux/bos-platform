import { useEffect, useRef } from "react";

import { getBreathController } from "../core/breath";

type NeuralEKGProps = {
  signalStrength: number;
};

export function NeuralEKG({ signalStrength }: NeuralEKGProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const dataRef = useRef<number[]>([]);
  const phaseRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const resize = () => {
      canvas.width = 280;
      canvas.height = 48;
      if (dataRef.current.length !== canvas.width) {
        dataRef.current = new Array(canvas.width).fill(canvas.height / 2);
      }
    };

    resize();
    let frameId = 0;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      phaseRef.current += 0.08;
      const nextValue =
        height / 2 +
        Math.sin(phaseRef.current * 2.3) * (signalStrength * 0.16) +
        Math.sin(phaseRef.current * 5.1) * (signalStrength * 0.06) +
        (Math.random() - 0.5) * (signalStrength * 0.04);

      dataRef.current.push(nextValue);
      dataRef.current.shift();

      const breath = getBreathController();
      context.clearRect(0, 0, width, height);
      context.strokeStyle = "rgba(0, 200, 212, 0.05)";
      context.lineWidth = 0.5;
      for (let x = 0; x < width; x += 28) {
        context.beginPath();
        context.moveTo(x, 0);
        context.lineTo(x, height);
        context.stroke();
      }

      context.beginPath();
      context.strokeStyle = `rgba(0,200,212, ${0.56 + breath.phase * 0.36})`;
      context.lineWidth = 1;
      context.shadowColor = breath.color;
      context.shadowBlur = 3 + breath.phase * 6;
      dataRef.current.forEach((y, index) => {
        if (index === 0) {
          context.moveTo(index, y);
        } else {
          context.lineTo(index, y);
        }
      });
      context.stroke();
      context.shadowBlur = 0;
      frameId = window.requestAnimationFrame(render);
    };

    frameId = window.requestAnimationFrame(render);
    return () => window.cancelAnimationFrame(frameId);
  }, [signalStrength]);

  return <canvas ref={canvasRef} className="login-signal-panel__ekg" aria-hidden="true" />;
}
