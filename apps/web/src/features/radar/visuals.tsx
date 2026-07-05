import { useEffect, useRef } from 'react';

export function RadarCanvas() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return undefined;
    const canvasElement = canvas;
    const context = ctx;
    let width = 0;
    let height = 0;
    let pixelRatio = 1;
    let sweep = 0;
    let frame = 0;

    function resizeCanvas() {
      pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvasElement.width = Math.floor(width * pixelRatio);
      canvasElement.height = Math.floor(height * pixelRatio);
      canvasElement.style.width = `${width}px`;
      canvasElement.style.height = `${height}px`;
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    }

    function drawRadar() {
      context.clearRect(0, 0, width, height);
      const centerX = width * 0.79;
      const centerY = height * 0.68;
      const radius = Math.min(width, height) * 0.42;
      context.save();
      context.translate(centerX, centerY);
      for (let i = 1; i <= 5; i += 1) {
        context.beginPath();
        context.arc(0, 0, (radius / 5) * i, 0, Math.PI * 2);
        context.strokeStyle = `rgba(255,255,255,${0.025 + i * 0.006})`;
        context.lineWidth = 1;
        context.stroke();
      }
      for (let i = 0; i < 10; i += 1) {
        const angle = (Math.PI * 2 * i) / 10;
        context.beginPath();
        context.moveTo(0, 0);
        context.lineTo(Math.cos(angle) * radius, Math.sin(angle) * radius);
        context.strokeStyle = "rgba(255,255,255,0.028)";
        context.stroke();
      }
      const gradient = context.createConicGradient(sweep, 0, 0);
      gradient.addColorStop(0, "rgba(255,46,115,0)");
      gradient.addColorStop(0.07, "rgba(255,46,115,0.22)");
      gradient.addColorStop(0.13, "rgba(118,215,255,0.08)");
      gradient.addColorStop(0.2, "rgba(255,46,115,0)");
      gradient.addColorStop(1, "rgba(255,46,115,0)");
      context.fillStyle = gradient;
      context.beginPath();
      context.arc(0, 0, radius, 0, Math.PI * 2);
      context.fill();
      [
        [0.12, 0.42, "#71e4a3"],
        [-0.3, -0.18, "#ffd166"],
        [0.44, -0.25, "#ff647c"],
        [-0.58, 0.22, "#76d7ff"],
      ].forEach(([x, y, color], index) => {
        const pulse = 2 + Math.sin(sweep * 2 + index) * 1.5;
        context.beginPath();
        context.arc(Number(x) * radius, Number(y) * radius, 3.5 + pulse, 0, Math.PI * 2);
        context.fillStyle = String(color);
        context.globalAlpha = 0.5;
        context.fill();
        context.globalAlpha = 1;
      });
      context.restore();
      sweep += 0.006;
      frame = requestAnimationFrame(drawRadar);
    }

    resizeCanvas();
    drawRadar();
    window.addEventListener("resize", resizeCanvas);
    return () => {
      window.removeEventListener("resize", resizeCanvas);
      window.cancelAnimationFrame(frame);
    };
  }, []);

  return <canvas className="radar-canvas" id="radarCanvas" aria-hidden="true" ref={canvasRef}></canvas>;
}

export function SceneOrbit() {
  return (
    <div className="scene-orbit" aria-hidden="true">
      <div className="dish">
        <span className="dish-pan"></span>
        <span className="dish-arm arm-a"></span>
        <span className="dish-arm arm-b"></span>
        <span className="dish-base"></span>
      </div>
      <div className="signal-slab slab-one"></div>
      <div className="signal-slab slab-two"></div>
    </div>
  );
}
