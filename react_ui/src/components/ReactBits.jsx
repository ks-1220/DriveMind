import { useEffect, useRef, useState } from 'react';

// ─── DecryptedText (React Bits port) ─────────────────────────────────────────
const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%&';

export default function DecryptedText({
  text = '',
  speed = 60,
  revealDelay = 20,
  className = '',
  style = {},
}) {
  const [displayed, setDisplayed] = useState(
    text.split('').map(() => CHARS[Math.floor(Math.random() * CHARS.length)])
  );
  const revealed = useRef(0);
  const timer = useRef(null);

  useEffect(() => {
    let tick = 0;
    timer.current = setInterval(() => {
      tick++;
      setDisplayed(prev =>
        prev.map((ch, i) => {
          if (i < revealed.current) return text[i];
          return CHARS[Math.floor(Math.random() * CHARS.length)];
        })
      );
      if (tick % revealDelay === 0 && revealed.current < text.length) {
        revealed.current++;
      }
      if (revealed.current >= text.length) {
        clearInterval(timer.current);
        setDisplayed(text.split(''));
      }
    }, speed);
    return () => clearInterval(timer.current);
  }, [text, speed, revealDelay]);

  return (
    <span className={className} style={style}>
      {displayed.map((ch, i) => (
        <span
          key={i}
          style={{
            color: i < revealed.current
              ? 'inherit'
              : 'rgba(129,140,248,0.5)',
            transition: 'color 0.1s',
          }}
        >
          {ch}
        </span>
      ))}
    </span>
  );
}

// ─── CountUp ─────────────────────────────────────────────────────────────────
export function CountUp({ to, duration = 1500, decimals = 0, suffix = '', className = '' }) {
  const [value, setValue] = useState(0);
  const startTime = useRef(null);
  const rafRef    = useRef(null);

  useEffect(() => {
    startTime.current = null;
    const animate = (ts) => {
      if (!startTime.current) startTime.current = ts;
      const progress = Math.min((ts - startTime.current) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(parseFloat((eased * to).toFixed(decimals)));
      if (progress < 1) rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [to, duration, decimals]);

  return (
    <span className={className}>
      {value.toFixed(decimals)}{suffix}
    </span>
  );
}

// ─── GlitchText ──────────────────────────────────────────────────────────────
export function GlitchText({ text, className = '', style = {} }) {
  return (
    <span className={className} style={{ position: 'relative', display: 'inline-block', ...style }}>
      <span style={{
        position: 'absolute',
        top: 0, left: '2px',
        color: '#ef4444',
        clipPath: 'polygon(0 20%, 100% 20%, 100% 40%, 0 40%)',
        animation: 'glitch1 3s infinite',
        opacity: 0.8,
      }}>{text}</span>
      <span style={{
        position: 'absolute',
        top: 0, left: '-2px',
        color: '#06b6d4',
        clipPath: 'polygon(0 60%, 100% 60%, 100% 80%, 0 80%)',
        animation: 'glitch2 3s infinite',
        opacity: 0.8,
      }}>{text}</span>
      <style>{`
        @keyframes glitch1 { 0%,95%,100%{transform:translateX(0)} 96%{transform:translateX(-3px)} 97%{transform:translateX(2px)} 98%{transform:translateX(-1px)} }
        @keyframes glitch2 { 0%,95%,100%{transform:translateX(0)} 96%{transform:translateX(3px)} 97%{transform:translateX(-2px)} 98%{transform:translateX(1px)} }
      `}</style>
      {text}
    </span>
  );
}

// ─── SpotlightCard ────────────────────────────────────────────────────────────
export function SpotlightCard({ children, className = '', style = {}, spotlightColor = 'rgba(99,102,241,0.15)' }) {
  const ref  = useRef(null);
  const spot = useRef({ x: 0, y: 0, opacity: 0 });

  const onMove = (e) => {
    const r = ref.current.getBoundingClientRect();
    spot.current = {
      x: e.clientX - r.left,
      y: e.clientY - r.top,
      opacity: 1,
    };
    ref.current.style.setProperty('--sx', `${spot.current.x}px`);
    ref.current.style.setProperty('--sy', `${spot.current.y}px`);
    ref.current.style.setProperty('--so', '1');
  };
  const onLeave = () => {
    ref.current.style.setProperty('--so', '0');
  };

  return (
    <div
      ref={ref}
      className={className}
      style={{
        position: 'relative',
        overflow: 'hidden',
        ...style,
        '--sc': spotlightColor,
      }}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
    >
      <div style={{
        position: 'absolute',
        inset: 0,
        background: `radial-gradient(350px circle at var(--sx,50%) var(--sy,50%), var(--sc), transparent)`,
        opacity: 'var(--so, 0)',
        transition: 'opacity 0.3s',
        pointerEvents: 'none',
        zIndex: 0,
      }} />
      <div style={{ position: 'relative', zIndex: 1 }}>{children}</div>
    </div>
  );
}

// ─── ClickSpark ──────────────────────────────────────────────────────────────
export function ClickSpark({ children }) {
  const [sparks, setSparks] = useState([]);

  const onClick = (e) => {
    const id = Date.now();
    setSparks(s => [...s, { id, x: e.clientX, y: e.clientY }]);
    setTimeout(() => setSparks(s => s.filter(sp => sp.id !== id)), 700);
  };

  return (
    <div onClick={onClick} style={{ width: '100%', height: '100%', position: 'relative' }}>
      {children}
      {sparks.map(sp => (
        <div key={sp.id} style={{ position: 'fixed', top: sp.y, left: sp.x, pointerEvents: 'none', zIndex: 9998 }}>
          {[...Array(8)].map((_, i) => (
            <div key={i} style={{
              position: 'absolute',
              width: '3px', height: '3px',
              borderRadius: '50%',
              background: '#6366f1',
              animation: `spark${i} 0.6s ease-out forwards`,
            }} />
          ))}
          <style>{[...Array(8)].map((_, i) => {
            const angle = (i / 8) * 360;
            return `@keyframes spark${i}{0%{transform:translate(0,0);opacity:1}100%{transform:translate(${Math.cos(angle*Math.PI/180)*40}px,${Math.sin(angle*Math.PI/180)*40}px);opacity:0}}`;
          }).join('')}</style>
        </div>
      ))}
    </div>
  );
}
