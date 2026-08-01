import { useEffect, useRef } from 'react';

// ─── Threads Background (React Bits port) ────────────────────────────────────
// Animated flowing thread lines, tuned for DriveMind dark theme
export default function Threads({
  color = [99, 102, 241],
  amplitude = 1,
  distance = 0,
  enableMouseInteraction = true,
}) {
  const canvasRef = useRef(null);
  const animRef   = useRef(null);
  const mouseRef  = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx    = canvas.getContext('2d');
    let width, height;

    const THREAD_COUNT  = 24;
    const POINTS        = 80;

    const threads = Array.from({ length: THREAD_COUNT }, (_, i) => ({
      y:     (i / (THREAD_COUNT - 1)),
      phase: Math.random() * Math.PI * 2,
      speed: 0.003 + Math.random() * 0.003,
      amp:   0.03 + Math.random() * 0.07,
    }));

    function resize() {
      width  = canvas.offsetWidth;
      height = canvas.offsetHeight;
      canvas.width  = width;
      canvas.height = height;
    }
    resize();
    window.addEventListener('resize', resize);

    if (enableMouseInteraction) {
      const onMove = (e) => {
        const r = canvas.getBoundingClientRect();
        mouseRef.current = {
          x: (e.clientX - r.left) / width,
          y: (e.clientY - r.top)  / height,
        };
      };
      canvas.addEventListener('mousemove', onMove);
    }

    let t = 0;
    function draw() {
      ctx.clearRect(0, 0, width, height);
      t += 1;

      threads.forEach((thread) => {
        ctx.beginPath();
        const mx = mouseRef.current.x;
        const my = mouseRef.current.y;

        for (let p = 0; p < POINTS; p++) {
          const x  = (p / (POINTS - 1)) * width;
          const nx = p / (POINTS - 1);
          const dist = Math.abs(nx - mx);
          const influence = Math.max(0, 1 - dist * 4);

          const wave = Math.sin(nx * 6 + t * thread.speed * 60 + thread.phase) * thread.amp * amplitude;
          const mouseWave = influence * (my - thread.y) * 0.3;
          const y = (thread.y + wave + mouseWave + distance * 0.01) * height;

          if (p === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }

        const grad = ctx.createLinearGradient(0, 0, width, 0);
        grad.addColorStop(0,   `rgba(${color[0]},${color[1]},${color[2]},0)`);
        grad.addColorStop(0.3, `rgba(${color[0]},${color[1]},${color[2]},0.15)`);
        grad.addColorStop(0.7, `rgba(${color[0]},${color[1]},${color[2]},0.15)`);
        grad.addColorStop(1,   `rgba(${color[0]},${color[1]},${color[2]},0)`);

        ctx.strokeStyle = grad;
        ctx.lineWidth   = 1;
        ctx.stroke();
      });

      animRef.current = requestAnimationFrame(draw);
    }

    draw();
    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener('resize', resize);
    };
  }, [color, amplitude, distance, enableMouseInteraction]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: enableMouseInteraction ? 'auto' : 'none',
        zIndex: 0,
      }}
    />
  );
}
