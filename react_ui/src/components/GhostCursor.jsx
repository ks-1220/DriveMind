import { useEffect, useRef } from 'react';

// ─── Ghost Cursor (React Bits port, vanilla canvas) ──────────────────────────
export default function GhostCursor({
  color = '#6366f1',
  trailLength = 40,
  inertia = 0.12,
}) {
  const canvasRef = useRef(null);
  const animRef   = useRef(null);
  const trail     = useRef([]);
  const mouse     = useRef({ x: -999, y: -999 });
  const current   = useRef({ x: -999, y: -999 });

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx    = canvas.getContext('2d');

    function resize() {
      canvas.width  = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    const onMove = (e) => {
      mouse.current = { x: e.clientX, y: e.clientY };
    };
    window.addEventListener('mousemove', onMove);

    function draw() {
      // lerp towards mouse
      current.current.x += (mouse.current.x - current.current.x) * inertia;
      current.current.y += (mouse.current.y - current.current.y) * inertia;

      trail.current.unshift({ ...current.current });
      if (trail.current.length > trailLength) trail.current.length = trailLength;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      trail.current.forEach((pt, i) => {
        const progress = 1 - i / trailLength;
        const radius   = progress * 8;
        const alpha    = progress * 0.55;

        ctx.beginPath();
        ctx.arc(pt.x, pt.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = hexToRgba(color, alpha);
        ctx.fill();
      });

      // glow at tip
      if (trail.current.length > 0) {
        const tip = trail.current[0];
        const g   = ctx.createRadialGradient(tip.x, tip.y, 0, tip.x, tip.y, 30);
        g.addColorStop(0, hexToRgba(color, 0.3));
        g.addColorStop(1, hexToRgba(color, 0));
        ctx.beginPath();
        ctx.arc(tip.x, tip.y, 30, 0, Math.PI * 2);
        ctx.fillStyle = g;
        ctx.fill();
      }

      animRef.current = requestAnimationFrame(draw);
    }

    draw();
    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', onMove);
    };
  }, [color, trailLength, inertia]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0, left: 0,
        width: '100vw', height: '100vh',
        pointerEvents: 'none',
        zIndex: 9999,
        mixBlendMode: 'screen',
      }}
    />
  );
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
