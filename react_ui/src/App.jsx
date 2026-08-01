import { useState, useEffect, useRef, useCallback } from 'react';
import './index.css';
import Threads from './components/Threads';
import GhostCursor from './components/GhostCursor';
import DecryptedText, { CountUp, GlitchText, SpotlightCard, ClickSpark } from './components/ReactBits';
import TelemetryChart from './components/TelemetryChart';

// ─── Logo SVG ─────────────────────────────────────────────────────────────────
const Logo = () => (
  <svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="18" cy="18" r="17" stroke="url(#lg)" strokeWidth="1.5"/>
    <path d="M10 22 L18 10 L26 22" stroke="url(#lg)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <circle cx="18" cy="22" r="3" fill="url(#lg)"/>
    <defs>
      <linearGradient id="lg" x1="0" y1="0" x2="36" y2="36" gradientUnits="userSpaceOnUse">
        <stop stopColor="#6366f1"/><stop offset="1" stopColor="#a78bfa"/>
      </linearGradient>
    </defs>
  </svg>
);

// ─── Tabs config ──────────────────────────────────────────────────────────────
const TABS = [
  { id: 'fleet',   icon: '🚛', label: 'Fleet Intelligence' },
  { id: 'qa',      icon: '🧠', label: 'Q&A Console' },
  { id: 'graph',   icon: '🕸️', label: 'Knowledge Graph' },
  { id: 'eval',    icon: '📊', label: 'Eval Studio' },
];

const STATUS_COLOR = { Healthy: '#10b981', Warning: '#f59e0b', Critical: '#ef4444' };

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [tab,          setTab]          = useState('fleet');
  const [fleet,        setFleet]        = useState([]);
  const [selectedId,   setSelectedId]   = useState(null);
  const [vehicleData,  setVehicleData]  = useState(null);
  const [telemetry,    setTelemetry]    = useState(null);
  const [dataSource,   setDataSource]   = useState(null);
  const [graphData,    setGraphData]    = useState(null);
  const [evalData,     setEvalData]     = useState(null);
  const [messages,     setMessages]     = useState([
    { role: 'bot', text: '👋 Hello! Ask me anything about your fleet — diagnostics, failure predictions, maintenance trends, or warranty status.' }
  ]);
  const [query,        setQuery]        = useState('');
  const [thinking,     setThinking]     = useState(false);
  const [agentTrace,   setAgentTrace]   = useState([]);
  const messagesEndRef = useRef(null);
  const visRef         = useRef(null);
  const networkRef     = useRef(null);

  // ── Initial loads ────────────────────────────────────────────────────────
  useEffect(() => {
    fetch('/api/fleet').then(r => r.json()).then(d => {
      setFleet(d.vehicles || []);
      const first = (d.vehicles || [])[0];
      if (first) setSelectedId(first.id);
    });
    fetch('/api/data-source').then(r => r.json()).then(setDataSource);
  }, []);

  // ── Load vehicle detail when selection changes ────────────────────────────
  useEffect(() => {
    if (!selectedId) return;
    fetch(`/api/vehicle/${selectedId}`).then(r => r.json()).then(setVehicleData);
    fetch(`/api/telemetry/${selectedId}`).then(r => r.json()).then(setTelemetry);
  }, [selectedId]);

  // ── Graph tab loads ───────────────────────────────────────────────────────
  useEffect(() => {
    if (tab === 'graph' && !graphData) {
      fetch('/api/graph').then(r => r.json()).then(setGraphData);
    }
  }, [tab, graphData]);

  // ── Vis.js Knowledge Graph ───────────────────────────────────────────────
  useEffect(() => {
    if (tab !== 'graph' || !graphData || !visRef.current) return;
    if (typeof window.vis === 'undefined') return;
    if (networkRef.current) { networkRef.current.destroy(); networkRef.current = null; }

    const nodes = new window.vis.DataSet(graphData.nodes || []);
    const edges = new window.vis.DataSet(graphData.edges || []);
    networkRef.current = new window.vis.Network(visRef.current, { nodes, edges }, {
      nodes: {
        shape: 'dot', size: 12,
        font: { color: '#e2e8f0', size: 11, face: 'Inter' },
        borderWidth: 1.5,
      },
      edges: {
        color: { color: 'rgba(99,102,241,0.3)', highlight: '#6366f1' },
        font: { color: '#64748b', size: 9 },
        width: 1.2, smooth: { type: 'curvedCW', roundness: 0.1 },
      },
      physics: { stabilization: { iterations: 80 } },
      background: { color: 'transparent' },
    });
  }, [tab, graphData]);

  // ── Eval tab ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (tab === 'eval' && !evalData) {
      fetch('/api/evaluation').then(r => r.json()).then(setEvalData);
    }
  }, [tab, evalData]);

  // ── Auto-scroll chat ─────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Q&A send ─────────────────────────────────────────────────────────────
  const sendQuery = useCallback(async () => {
    if (!query.trim() || thinking) return;
    const q = query.trim();
    setQuery('');
    setMessages(m => [...m, { role: 'user', text: q }]);
    setThinking(true);
    setAgentTrace([]);
    try {
      const r = await fetch('/api/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q }),
      });
      const d = await r.json();
      setMessages(m => [...m, { role: 'bot', text: d.answer || 'No response.' }]);
      setAgentTrace(d.trace || []);
    } catch (e) {
      setMessages(m => [...m, { role: 'bot', text: `Error: ${e.message}` }]);
    }
    setThinking(false);
  }, [query, thinking]);

  const onKey = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendQuery(); } };

  // ── Metric cards for a vehicle ───────────────────────────────────────────
  const metrics = vehicleData ? [
    { label: 'Anomaly Score',    value: vehicleData.anomaly_score,    unit: '%',   color: '#ef4444', max: 100 },
    { label: 'Remaining Life',   value: vehicleData.predicted_rul,    unit: ' days', color: '#06b6d4', max: 365 },
    { label: 'Avg Coolant Temp', value: vehicleData.avg_coolant_temp, unit: '°F',  color: '#f59e0b', max: 260 },
    { label: 'Avg Oil Pressure', value: vehicleData.avg_oil_pressure, unit: ' PSI', color: '#10b981', max: 90 },
    { label: 'Max Vibration',    value: vehicleData.max_vibration,    unit: ' g',  color: '#a78bfa', max: 2 },
    { label: 'Avg Voltage',      value: vehicleData.avg_voltage,      unit: ' V',  color: '#38bdf8', max: 16 },
  ] : [];

  const shapFeatures = vehicleData?.shap_features || [];

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <>
      <GhostCursor color="#6366f1" />
      <ClickSpark>
        <div className="app-shell">

          {/* ── Header ── */}
          <header className="header">
            <div className="header-logo">
              <Logo />
              <div>
                <div className="header-wordmark">
                  <DecryptedText text="DriveMind" speed={40} revealDelay={15} />
                </div>
                <div className="header-sub">Fleet Intelligence Platform</div>
              </div>
            </div>
            <div className="header-spacer" />
            {dataSource && (
              <div className={`data-badge ${dataSource.source === 'synthetic_simulator' ? 'synthetic' : ''}`}
                   title={dataSource.description}>
                <span className="pulse-dot" />
                {dataSource.label}
              </div>
            )}
            {fleet.length > 0 && (
              <div style={{ display: 'flex', gap: 16, fontSize: '0.78rem', color: 'var(--muted)', marginLeft: 12 }}>
                <span style={{ color: '#10b981', fontWeight: 700, fontFamily: 'var(--mono)' }}>
                  <CountUp to={fleet.filter(v => v.status === 'Healthy').length} duration={1200} />
                  <span style={{ color: 'var(--muted)', fontWeight: 400 }}> healthy</span>
                </span>
                <span style={{ color: '#f59e0b', fontWeight: 700, fontFamily: 'var(--mono)' }}>
                  <CountUp to={fleet.filter(v => v.status === 'Warning').length} duration={1200} />
                  <span style={{ color: 'var(--muted)', fontWeight: 400 }}> warning</span>
                </span>
                <span style={{ color: '#ef4444', fontWeight: 700, fontFamily: 'var(--mono)' }}>
                  <CountUp to={fleet.filter(v => v.status === 'Critical').length} duration={1200} />
                  <span style={{ color: 'var(--muted)', fontWeight: 400 }}> critical</span>
                </span>
              </div>
            )}
          </header>

          {/* ── Nav ── */}
          <nav className="nav-tabs">
            {TABS.map(t => (
              <button key={t.id} className={`nav-tab${tab === t.id ? ' active' : ''}`} onClick={() => setTab(t.id)}>
                <span className="nav-tab-icon">{t.icon}</span>
                {t.label}
              </button>
            ))}
          </nav>

          {/* ── Main ── */}
          <main className="main-content">

            {/* ── Fleet Intelligence Tab ── */}
            <div className={`tab-panel fleet-panel${tab === 'fleet' ? ' active' : ''}`}>
              {/* Background threads only on fleet tab */}
              <div style={{ position: 'absolute', inset: 0, zIndex: 0, pointerEvents: 'none', opacity: 0.4 }}>
                <Threads color={[99, 102, 241]} amplitude={0.6} enableMouseInteraction={false} />
              </div>

              {/* Sidebar */}
              <aside className="fleet-sidebar" style={{ zIndex: 1 }}>
                <div className="fleet-sidebar-header">
                  <span className="fleet-sidebar-title">Vehicles</span>
                  <span className="fleet-count">{fleet.length} units</span>
                </div>
                <div className="vehicle-list">
                  {fleet.map(v => (
                    <SpotlightCard
                      key={v.id}
                      className={`vehicle-card${selectedId === v.id ? ' selected' : ''}`}
                      onClick={() => setSelectedId(v.id)}
                      spotlightColor={`${STATUS_COLOR[v.status]}22`}
                    >
                      <span className={`vehicle-status-dot ${v.status}`} />
                      <div className="vehicle-info">
                        <div className="vehicle-id">{v.id}</div>
                        <div className="vehicle-model">{v.manufacturer} {v.model} · {v.year}</div>
                      </div>
                      {v.status === 'Critical'
                        ? <GlitchText text="CRIT" className={`vehicle-badge ${v.status}`} style={{ fontSize: '0.58rem' }} />
                        : <span className={`vehicle-badge ${v.status}`}>{v.status.toUpperCase()}</span>
                      }
                    </SpotlightCard>
                  ))}
                </div>
              </aside>

              {/* Detail */}
              <div className="vehicle-detail" style={{ zIndex: 1 }}>
                {!vehicleData ? (
                  <div className="placeholder">
                    <div className="placeholder-icon">🚛</div>
                    Select a vehicle to view diagnostics
                  </div>
                ) : (
                  <>
                    <div className="detail-header">
                      <div>
                        <div className="detail-title">{vehicleData.id}</div>
                        <div className="detail-sub">{vehicleData.manufacturer} {vehicleData.model} · {vehicleData.year}</div>
                      </div>
                      <div className={`detail-status ${vehicleData.status}`}>{vehicleData.status}</div>
                    </div>

                    {/* Metrics */}
                    <p className="section-header">Live Diagnostics</p>
                    <div className="metrics-grid">
                      {metrics.map(m => (
                        <div key={m.label} className="metric-card">
                          <div className="metric-label">{m.label}</div>
                          <div>
                            <span className="metric-value" style={{ color: m.color }}>
                              {typeof m.value === 'number' ? (
                                <CountUp to={m.value} decimals={m.unit === ' g' ? 2 : 1} duration={1000} />
                              ) : (m.value ?? '—')}
                            </span>
                            <span className="metric-unit">{m.unit}</span>
                          </div>
                          <div className="metric-bar">
                            <div
                              className="metric-bar-fill"
                              style={{
                                width: `${Math.min(100, ((m.value || 0) / m.max) * 100)}%`,
                                background: m.color,
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* SHAP */}
                    {shapFeatures.length > 0 && (
                      <>
                        <p className="section-header">SHAP Feature Attribution</p>
                        <div className="ml-card">
                          <div className="ml-card-title">Root Cause Attribution (Explainable AI)</div>
                          <div className="shap-bars">
                            {shapFeatures.map(([feat, pct]) => (
                              <div key={feat} className="shap-bar-row">
                                <span className="shap-bar-label">{feat.replace(/_/g, ' ')}</span>
                                <div className="shap-bar-track">
                                  <div className="shap-bar-fill" style={{ width: `${pct}%` }} />
                                </div>
                                <span className="shap-bar-pct">{pct}%</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </>
                    )}

                    {/* Telemetry charts */}
                    {telemetry && (
                      <>
                        <p className="section-header">Telemetry Trends</p>
                        <div className="chart-wrap">
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 24px' }}>
                            <TelemetryChart data={telemetry.coolant_temp}  label="Coolant Temp"  color="#ef4444" unit="°F" />
                            <TelemetryChart data={telemetry.oil_pressure}  label="Oil Pressure"  color="#10b981" unit="PSI" />
                            <TelemetryChart data={telemetry.engine_rpm}    label="Engine RPM"    color="#f59e0b" unit="RPM" />
                            <TelemetryChart data={telemetry.vibration}     label="Vibration"     color="#a78bfa" unit="g" />
                            <TelemetryChart data={telemetry.voltage}       label="Voltage"       color="#38bdf8" unit="V" />
                            <TelemetryChart data={telemetry.exhaust_temp}  label="Exhaust Temp"  color="#fb923c" unit="°F" />
                          </div>
                        </div>
                      </>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* ── Q&A Tab ── */}
            <div className={`tab-panel qa-panel${tab === 'qa' ? ' active' : ''}`}>
              <div className="qa-chat">
                <div className="qa-messages">
                  {messages.map((m, i) => (
                    <div key={i} className={`msg msg-${m.role}`}>
                      <div className="msg-bubble">{m.text}</div>
                    </div>
                  ))}
                  {thinking && (
                    <div className="msg msg-bot">
                      <div className="msg-bubble" style={{ display: 'flex', gap: 10, alignItems: 'center', color: 'var(--muted)' }}>
                        <div className="spinner" /> Running multi-agent pipeline…
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
                <div className="qa-input-row">
                  <input
                    className="qa-input"
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    onKeyDown={onKey}
                    placeholder="Ask about TRK-427, failure rates, warranty claims…"
                    disabled={thinking}
                  />
                  <button className="qa-btn" onClick={sendQuery} disabled={thinking || !query.trim()}>
                    {thinking ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Running</> : '⚡ Run'}
                  </button>
                </div>
              </div>

              {/* Agent trace panel */}
              <div className="trace-panel">
                <div className="trace-title">Agent Reasoning Trace</div>
                {agentTrace.length === 0 && !thinking && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--muted)', padding: '12px 0' }}>
                    Submit a query to see the multi-agent pipeline trace here.
                  </div>
                )}
                {agentTrace.map((step, i) => (
                  <div key={i} className="trace-step">
                    <div className="trace-step-name">{step.agent}</div>
                    <div className="trace-step-thought">{step.thought}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* ── Knowledge Graph Tab ── */}
            <div className={`tab-panel${tab === 'graph' ? ' active' : ''}`} style={{ width: '100%', height: '100%', flexDirection: 'column' }}>
              <script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js" />
              <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.css" />
              {!graphData ? (
                <div className="placeholder"><div className="placeholder-icon">🕸️</div>Loading graph…</div>
              ) : (
                <div ref={visRef} id="vis-graph" />
              )}
            </div>

            {/* ── Evaluation Tab ── */}
            <div className={`tab-panel${tab === 'eval' ? ' active' : ''}`} style={{ width: '100%' }}>
              <div className="eval-panel">
                {!evalData ? (
                  <div className="placeholder"><div className="placeholder-icon">📊</div>Loading evaluation…</div>
                ) : (
                  <>
                    <p className="section-header" style={{ marginBottom: 20 }}>RAG Pipeline Evaluation Benchmark</p>
                    <div className="eval-grid">
                      {[
                        { icon: '🎯', label: 'MRR@5',         val: evalData.mrr_at_5,          fmt: v => v.toFixed(3) },
                        { icon: '📈', label: 'nDCG@5',         val: evalData.ndcg_at_5,         fmt: v => v.toFixed(3) },
                        { icon: '✅', label: 'Faithfulness',   val: evalData.faithfulness_pct,  fmt: v => `${v.toFixed(1)}%` },
                        { icon: '🚫', label: 'Hallucination',  val: evalData.hallucination_pct, fmt: v => `${v.toFixed(1)}%` },
                        { icon: '⚡', label: 'Avg Latency',    val: evalData.avg_latency_ms,    fmt: v => `${v.toFixed(0)}ms` },
                        { icon: '📦', label: 'Queries Run',    val: evalData.total_queries,     fmt: v => v },
                      ].map(c => (
                        <SpotlightCard key={c.label} className="eval-card">
                          <div className="eval-card-icon">{c.icon}</div>
                          <div className="eval-card-value">
                            {c.label === 'Hallucination' && c.val === 0
                              ? <span style={{ color: '#10b981' }}>0%</span>
                              : c.fmt(c.val)
                            }
                          </div>
                          <div className="eval-card-label">{c.label}</div>
                        </SpotlightCard>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>

          </main>
        </div>
      </ClickSpark>
    </>
  );
}
