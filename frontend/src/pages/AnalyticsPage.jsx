import React, { useEffect, useState, useCallback, useContext } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
    RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';
import { ThemeContext } from '../hooks/useTheme';
import '../styles/analytics.css';

/* ── Colour palette ── */
const PALETTE = ['#3b7ef8','#6366f1','#8b5cf6','#a78bfa','#c4b5fd','#60a5fa','#38bdf8','#34d399','#4ade80','#facc15'];
const ACCENT  = '#3b7ef8';

/* ── Custom SVG Gauge ── */
function GaugeArc({ value, max = 100, color, label, sublabel }) {
    const { theme } = useContext(ThemeContext);
    const isDark = theme === 'dark';

    const pct    = Math.min(Math.max(value / max, 0), 1);
    const angle  = pct * 180;
    const R = 60; const cx = 75; const cy = 75;
    const toRad  = (deg) => (deg - 180) * (Math.PI / 180);
    const endX   = cx + R * Math.cos(toRad(angle));
    const endY   = cy + R * Math.sin(toRad(angle));
    const large  = angle > 90 ? 1 : 0;

    const trackStroke = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';
    const textFill    = isDark ? '#f0f0f0' : '#0f1117';
    const subFill     = isDark ? 'rgba(255,255,255,0.35)' : '#9ca3af';

    return (
        <div className="gauge-card">
            <svg viewBox="0 0 150 85" className="gauge-svg">
                <path
                    d={`M ${cx-R} ${cy} A ${R} ${R} 0 0 1 ${cx+R} ${cy}`}
                    fill="none" stroke={trackStroke} strokeWidth="10" strokeLinecap="round"/>
                {pct > 0.01 && (
                    <path d={`M ${cx-R} ${cy} A ${R} ${R} 0 ${large} 1 ${endX} ${endY}`}
                        fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"/>
                )}
                <text x={cx} y={cy-8} textAnchor="middle" fill={textFill} fontSize="17" fontWeight="800"
                      fontFamily="Plus Jakarta Sans, sans-serif">
                    {value}{max === 100 ? '%' : ''}
                </text>
                <text x={cx} y={cy+8} textAnchor="middle" fill={subFill} fontSize="8"
                      fontFamily="Plus Jakarta Sans, sans-serif">
                    {sublabel}
                </text>
            </svg>
            <p className="gauge-label">{label}</p>
        </div>
    );
}

/* ── Custom Heatmap (pure CSS) ── */
function HeatmapGrid({ data }) {
    if (!data?.length) return <EmptyState />;
    const maxScore = Math.max(...data.map(d => d.avgScore), 1);
    return (
        <div className="heatmap-grid">
            {data.map((row, i) => {
                const intensity = row.avgScore / maxScore;
                const accentColor = PALETTE[Math.min(Math.floor(intensity * PALETTE.length), PALETTE.length - 1)];
                return (
                    <div key={i} className="heatmap-cell"
                        style={{ borderLeftColor: accentColor, borderLeftWidth: '3px' }}>
                        <span className="heatmap-skill">{row.skill}</span>
                        <span className="heatmap-score">
                            {row.avgScore}%
                        </span>
                        <span className="heatmap-count">{row.count} resume{row.count !== 1 ? 's' : ''}</span>
                    </div>
                );
            })}
        </div>
    );
}

/* ── Custom Funnel (CSS bars) ── */
function FunnelViz({ data }) {
    if (!data?.length) return <EmptyState />;
    const maxCount = Math.max(...data.map(d => d.count), 1);
    return (
        <div className="funnel-viz">
            {data.map((stage, i) => {
                const pct = (stage.count / maxCount) * 100;
                return (
                    <div key={i} className="funnel-stage">
                        <div className="funnel-bar-wrap">
                            <div className="funnel-bar-fill"
                                style={{ width: `${pct}%`, background: PALETTE[i] }} />
                        </div>
                        <div className="funnel-meta">
                            <span className="funnel-label">{stage.stage}</span>
                            <span className="funnel-count" style={{ color: PALETTE[i] }}>{stage.count}</span>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

/* ── Data Metrics strip ── */
function MetaStrip({ meta, source }) {
    if (!meta) return null;
    const items = [
        { label: 'Total Rows',    value: meta.totalRows },
        { label: 'Columns',       value: meta.totalColumns },
        { label: 'Dataset Size',  value: `${meta.datasetKB} KB` },
        { label: 'Unique Roles',  value: meta.uniqueRoles },
        { label: 'Unique Depts',  value: meta.uniqueDepts },
        { label: 'Source',        value: source === 'mongodb' ? '🍃 MongoDB' : '📄 Local JSON' },
    ];
    return (
        <div className="meta-strip">
            {items.map((item, i) => (
                <div key={i} className="meta-chip">
                    <span className="meta-value">{item.value}</span>
                    <span className="meta-label">{item.label}</span>
                </div>
            ))}
        </div>
    );
}

function EmptyState() {
    return <div className="chart-empty"><p>Upload resumes to see data</p></div>;
}

function ChartTooltip({ active, payload, label }) {
    if (!active || !payload?.length) return null;
    return (
        <div className="chart-tooltip">
            {label && <p className="tooltip-label">{label}</p>}
            {payload.map((p, i) => (
                <p key={i} style={{ color: p.color || ACCENT }}>
                    {p.name || p.dataKey}: <strong>{p.value}</strong>
                </p>
            ))}
        </div>
    );
}

/* ── Live indicator dot ── */
function LiveDot({ source }) {
    return (
        <span className="live-dot-wrap">
            <span className={`live-dot ${source === 'mongodb' ? 'live-dot-green' : 'live-dot-amber'}`} />
            {source === 'mongodb' ? 'Live · MongoDB' : 'Local JSON'}
        </span>
    );
}

/* ══════════════════════════════════════════════════════
   MAIN PAGE
══════════════════════════════════════════════════════ */
export default function AnalyticsPage() {
    const { theme } = useContext(ThemeContext);
    const isDark = theme === 'dark';

    /* Theme-aware tick colours for Recharts */
    const tickMuted  = isDark ? 'rgba(255,255,255,0.30)' : 'rgba(0,0,0,0.35)';
    const tickNormal = isDark ? 'rgba(255,255,255,0.55)' : 'rgba(0,0,0,0.55)';
    const gridStroke = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.07)';
    const cursorFill = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)';

    const [data,      setData]      = useState(null);
    const [lastFetch, setLastFetch] = useState(null);
    const [countdown, setCountdown] = useState(30);

    const REFRESH_S = 30;  // only poll every 30s — reduces backend load


    const fetchData = useCallback(() => {
        fetch('http://localhost:5001/api/big-data-stats')
            .then(r => r.json())
            .then(d => {
                setData(d);
                setLastFetch(new Date().toLocaleTimeString());
                setCountdown(REFRESH_S);
            })
            .catch(() => {});
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    // Poll every 30s, but pause when tab is hidden
    useEffect(() => {
        let interval = null;
        const start  = () => { interval = setInterval(fetchData, REFRESH_S * 1000); };
        const stop   = () => { if (interval) clearInterval(interval); };
        start();
        const onVis = () => document.hidden ? stop() : (start(), fetchData());
        document.addEventListener('visibilitychange', onVis);
        return () => { stop(); document.removeEventListener('visibilitychange', onVis); };
    }, [fetchData]);

    useEffect(() => {
        const tick = setInterval(() => setCountdown(c => (c <= 1 ? REFRESH_S : c - 1)), 1000);
        return () => clearInterval(tick);
    }, []);

    // No full-screen spinner — render immediately with empty placeholders

    const empty   = !data || data.total_in_batch === 0;
    const gauge   = data?.gauge   || {};
    const hist    = data?.histogram || [];
    const funnel  = data?.funnel  || [];
    const heatmap = data?.heatmap || [];
    const radar   = data?.radar   || [];
    const skills  = data?.skills  || [];
    const meta    = data?.meta;
    const source  = data?.source  || 'json';

    return (
        <div className="analytics-page">
            <div className="analytics-dot-grid" />

            {/* ── Header ── */}
            <div className="analytics-header">
                <div>
                    <h1 className="analytics-title">Analytics</h1>
                    <p className="analytics-subtitle">
                        {gauge.totalCandidates ?? 0} candidates across all uploads
                        {lastFetch && <span className="refresh-info"> · refreshed {lastFetch} · next in {countdown}s</span>}
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <LiveDot source={source} />
                    <div className="analytics-badge">5 Vs of Big Data</div>
                </div>
            </div>

            {/* ── Data Metrics Strip ── */}
            <MetaStrip meta={meta} source={source} />

            {empty && (
                <div className="analytics-empty-banner">
                    📂 No data yet — upload resumes from the Upload page first.
                </div>
            )}

            {/* ══ ROW 1: Gauges (VALUE) ══ */}
            <section className="analytics-section">
                <h2 className="section-title">
                    <span className="section-dot" style={{ background: ACCENT }} />
                    Overview Gauges
                    <span className="section-tag">VALUE</span>
                </h2>
                <p className="section-desc">Overall pipeline health at a glance</p>
                <div className="gauges-row">
                    <GaugeArc value={gauge.avgScore ?? 0}        max={100} color="#3b7ef8" label="Avg Score"         sublabel="out of 100" />
                    <GaugeArc value={gauge.shortlistRate ?? 0}   max={100} color="#34d399" label="Shortlist Rate"    sublabel="% of total" />
                    <GaugeArc value={gauge.anomalyRate ?? 0}     max={100} color="#f87171" label="Anomaly Rate"      sublabel="% flagged" />
                    <GaugeArc value={gauge.totalCandidates ?? 0} max={Math.max(gauge.totalCandidates ?? 1, 20)} color="#a78bfa" label="Total Candidates" sublabel="in MongoDB" />
                </div>
            </section>

            {/* ══ ROW 2: Histogram + Funnel ══ */}
            <div className="analytics-row-2">
                {/* CHART 1 — Score Distribution Histogram (VOLUME) */}
                <section className="analytics-section chart-half">
                    <h2 className="section-title">
                        <span className="section-dot" style={{ background: '#6366f1' }} />
                        Score Distribution
                        <span className="section-tag">VOLUME</span>
                    </h2>
                    <p className="section-desc">Candidates per score band across all uploads</p>
                    {!hist.some(d => d.count > 0) ? <EmptyState /> : (
                        <ResponsiveContainer width="100%" height={230}>
                            <BarChart data={hist} margin={{ top: 8, right: 12, left: -14, bottom: 0 }}>
                                <XAxis dataKey="range"
                                    tick={{ fill: tickMuted, fontSize: 10 }}
                                    axisLine={false} tickLine={false} />
                                <YAxis allowDecimals={false}
                                    tick={{ fill: tickMuted, fontSize: 10 }}
                                    axisLine={false} tickLine={false} />
                                <Tooltip content={<ChartTooltip />} cursor={{ fill: cursorFill }} />
                                <Bar dataKey="count" name="Candidates" radius={[6,6,0,0]}>
                                    {hist.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </section>

                {/* CHART 2 — Hiring Funnel (VELOCITY) */}
                <section className="analytics-section chart-half">
                    <h2 className="section-title">
                        <span className="section-dot" style={{ background: '#8b5cf6' }} />
                        Hiring Funnel
                        <span className="section-tag">VELOCITY</span>
                    </h2>
                    <p className="section-desc">Candidates at each stage of the pipeline</p>
                    <FunnelViz data={funnel} />
                </section>
            </div>

            {/* ══ ROW 3: Heatmap (VARIETY) ══ */}
            <section className="analytics-section">
                <h2 className="section-title">
                    <span className="section-dot" style={{ background: '#38bdf8' }} />
                    Skill × Score Heatmap
                    <span className="section-tag">VARIETY</span>
                </h2>
                <p className="section-desc">Average score of candidates listing each skill — darker blue = stronger signal</p>
                <HeatmapGrid data={heatmap} />
            </section>

            {/* ══ ROW 4: Radar + Skill Bar ══ */}
            <div className="analytics-row-2">
                {/* CHART 4 — Radar / Spider Chart (VERACITY) */}
                <section className="analytics-section chart-half">
                    <h2 className="section-title">
                        <span className="section-dot" style={{ background: '#34d399' }} />
                        Skill Radar
                        <span className="section-tag">VERACITY</span>
                    </h2>
                    <p className="section-desc">Frequency of top skills across all candidates</p>
                    {radar.length < 3 ? <EmptyState /> : (
                        <ResponsiveContainer width="100%" height={260}>
                            <RadarChart data={radar} margin={{ top: 10, right: 30, left: 30, bottom: 10 }}>
                                <PolarGrid stroke={gridStroke} />
                                <PolarAngleAxis dataKey="subject"
                                    tick={{ fill: tickNormal, fontSize: 11 }} />
                                <PolarRadiusAxis tick={false} axisLine={false} />
                                <Radar name="Frequency" dataKey="A"
                                    stroke={ACCENT} fill={ACCENT} fillOpacity={0.18}
                                    strokeWidth={2} dot={{ fill: ACCENT, r: 3 }} />
                                <Tooltip content={<ChartTooltip />} />
                            </RadarChart>
                        </ResponsiveContainer>
                    )}
                </section>

                {/* CHART 5 — Top Skills Horizontal Bar (VALUE) */}
                <section className="analytics-section chart-half">
                    <h2 className="section-title">
                        <span className="section-dot" style={{ background: '#facc15' }} />
                        Top Skills Frequency
                        <span className="section-tag">VALUE</span>
                    </h2>
                    <p className="section-desc">Most demanded skills across all uploaded resumes</p>
                    {!skills.length ? <EmptyState /> : (
                        <ResponsiveContainer width="100%" height={260}>
                            <BarChart data={skills} layout="vertical" margin={{ top: 8, right: 40, left: 10, bottom: 0 }}>
                                <XAxis type="number"
                                    tick={{ fill: tickMuted, fontSize: 10 }}
                                    axisLine={false} tickLine={false} />
                                <YAxis type="category" dataKey="subject" width={90}
                                    tick={{ fill: tickNormal, fontSize: 12 }}
                                    axisLine={false} tickLine={false} />
                                <Tooltip content={<ChartTooltip />} cursor={{ fill: cursorFill }} />
                                <Bar dataKey="A" name="Count" radius={[0,6,6,0]}>
                                    {skills.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </section>
            </div>

            {/* ══ 5 Vs Footer ══ */}
            <div className="five-vs-strip">
                {[
                    { v: 'Volume',   desc: 'All candidates across every batch',       color: PALETTE[0] },
                    { v: 'Velocity', desc: 'Real-time refresh every 10s',              color: PALETTE[2] },
                    { v: 'Variety',  desc: 'Skills, roles, education, exp, scores',   color: PALETTE[4] },
                    { v: 'Veracity', desc: 'Anomaly detection + skill validation',     color: PALETTE[6] },
                    { v: 'Value',    desc: 'Ranked shortlist + AI scoring',            color: PALETTE[8] },
                ].map(({ v, desc, color }) => (
                    <div key={v} className="five-v-chip" style={{ borderColor: `${color}40` }}>
                        <span className="five-v-letter" style={{ color }}>{v}</span>
                        <span className="five-v-desc">{desc}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
