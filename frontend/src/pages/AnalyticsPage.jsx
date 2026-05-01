// AnalyticsPage.jsx — HireFlow AI
// Real-time Chart.js charts. Data fetched fresh from /api/analytics-data (JSON).
// No server-side image rendering. Charts appear in <300ms.

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
    Chart as ChartJS,
    CategoryScale, LinearScale, BarElement, Title,
    Tooltip, Legend, ArcElement,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { API_BASE_URL } from '../config';
import '../styles/analytics.css';

// Register Chart.js components
ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend, ArcElement);

// ── Colour tokens ──────────────────────────────────────────────────────────────
const BLUE   = 'rgba(31,  119, 180, 0.85)';
const BLUE_B = 'rgba(31,  119, 180, 1)';
const ORG    = 'rgba(255, 127,  14, 0.85)';
const ORG_B  = 'rgba(255, 127,  14, 1)';
const GRN    = 'rgba(44,  160,  44, 0.85)';
const GRN_B  = 'rgba(44,  160,  44, 1)';
const PRP    = 'rgba(148,103, 189, 0.85)';
const GRY    = 'rgba(180, 180, 180, 0.6)';
const GRY_B  = 'rgba(180, 180, 180, 0.9)';

const FUNNEL_COLORS = [BLUE, GRN, ORG, PRP, GRN];
const FUNNEL_BORDERS = [BLUE_B, GRN_B, ORG_B, 'rgba(148,103,189,1)', GRN_B];

// Blues gradient for skill bars
const blueGradient = (n) =>
    Array.from({ length: n }, (_, i) =>
        `rgba(31, 119, 180, ${0.4 + 0.55 * (1 - i / Math.max(n - 1, 1))})`
    );

// ── Shared Chart options ───────────────────────────────────────────────────────
const baseOpts = (title) => ({
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 600, easing: 'easeOutQuart' },
    plugins: {
        legend: { display: false },
        title:  { display: false },
        tooltip: {
            backgroundColor: '#1a1a2e',
            titleColor: '#ffffff',
            bodyColor: '#cccccc',
            cornerRadius: 8,
            padding: 10,
        },
    },
    scales: {
        x: {
            grid: { color: 'rgba(0,0,0,0.05)', lineWidth: 1 },
            ticks: { color: '#6b7280', font: { size: 11, family: 'Plus Jakarta Sans, sans-serif' } },
            border: { display: false },
        },
        y: {
            grid: { color: 'rgba(0,0,0,0.05)', lineWidth: 1 },
            ticks: { color: '#6b7280', font: { size: 11, family: 'Plus Jakarta Sans, sans-serif' }, precision: 0 },
            border: { display: false },
        },
    },
});

// ── Stat card ──────────────────────────────────────────────────────────────────
function StatCard({ label, value, color }) {
    return (
        <div style={{
            background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px',
            padding: '14px 20px', flex: '1 1 130px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            borderTop: `3px solid ${color || '#1f77b4'}`,
        }}>
            <div style={{ fontSize: '0.68rem', color: '#9ca3af', fontWeight: 600,
                          textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '5px',
                          fontFamily: 'Plus Jakarta Sans, sans-serif' }}>
                {label}
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#111827',
                          fontFamily: 'Plus Jakarta Sans, sans-serif' }}>
                {value}
            </div>
        </div>
    );
}

// ── Chart card wrapper ─────────────────────────────────────────────────────────
function ChartCard({ title, subtitle, children, height = 300 }) {
    return (
        <div style={{
            background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px',
            padding: '18px 20px 14px', boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
        }}>
            <div style={{ marginBottom: '12px' }}>
                <h3 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700,
                             color: '#111827', fontFamily: 'Plus Jakarta Sans, sans-serif' }}>
                    {title}
                </h3>
                {subtitle && (
                    <p style={{ margin: '2px 0 0', fontSize: '0.75rem', color: '#9ca3af',
                                fontFamily: 'Plus Jakarta Sans, sans-serif' }}>
                        {subtitle}
                    </p>
                )}
            </div>
            <div style={{ height: `${height}px`, position: 'relative' }}>
                {children}
            </div>
        </div>
    );
}

// ── Skeleton ───────────────────────────────────────────────────────────────────
function Skeleton({ height = 300 }) {
    return (
        <div style={{
            height: `${height}px`, borderRadius: '8px',
            background: 'linear-gradient(90deg,#f3f4f6 25%,#e9eaec 50%,#f3f4f6 75%)',
            backgroundSize: '400% 100%',
            animation: 'shimmer 1.4s infinite linear',
        }} />
    );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
    const [data,    setData]    = useState(null);
    const [loading, setLoading] = useState(true);
    const [error,   setError]   = useState(null);
    const [lastUpd, setLastUpd] = useState(null);
    const timerRef = useRef(null);

    const fetchData = useCallback(async (silent = false) => {
        if (!silent) setLoading(true);
        setError(null);
        try {
            const res  = await fetch(`${API_BASE_URL}/api/analytics-data`);
            if (!res.ok) throw new Error(`Server returned ${res.status}`);
            const json = await res.json();
            setData(json);
            setLastUpd(new Date());
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, []);

    // Fetch on mount
    useEffect(() => { fetchData(); }, [fetchData]);

    // Auto-refresh every 30s
    useEffect(() => {
        timerRef.current = setInterval(() => {
            if (!document.hidden) fetchData(true);
        }, 30_000);
        return () => clearInterval(timerRef.current);
    }, [fetchData]);

    // ── Build chart datasets when data arrives ──────────────────────────────
    const distChart = data ? {
        labels:   data.score_distribution.labels,
        datasets: [{
            label: 'Candidates',
            data:  data.score_distribution.counts,
            backgroundColor: data.score_distribution.counts.map((_, i) =>
                `rgba(31, 119, 180, ${0.45 + 0.055 * i})`
            ),
            borderColor: BLUE_B,
            borderWidth: 1,
            borderRadius: 4,
        }],
    } : null;

    const funnelChart = data ? {
        labels:   data.hiring_funnel.stages,
        datasets: [{
            label: 'Candidates',
            data:  data.hiring_funnel.values,
            backgroundColor: FUNNEL_COLORS,
            borderColor:     FUNNEL_BORDERS,
            borderWidth: 1,
            borderRadius: 4,
        }],
    } : null;

    const skillChart = data && data.skill_scores.skills.length ? {
        labels:   [...data.skill_scores.skills].reverse(),
        datasets: [{
            label: 'Avg Score (%)',
            data:  [...data.skill_scores.avg_scores].reverse(),
            backgroundColor: blueGradient(data.skill_scores.skills.length).reverse(),
            borderColor: BLUE_B,
            borderWidth: 1,
            borderRadius: 4,
        }],
    } : null;

    const compChart = data ? {
        labels:   ['TabTransformer\n(max 40)', 'Vector Similarity\n(max 35)', 'TF-IDF Match\n(max 25)'],
        datasets: [
            {
                label: 'Avg Achieved',
                data:  data.score_components.achieved,
                backgroundColor: [BLUE, ORG, GRN],
                borderColor:     [BLUE_B, ORG_B, GRN_B],
                borderWidth: 1,
                borderRadius: 4,
            },
            {
                label: 'Maximum',
                data:  data.score_components.maximums,
                backgroundColor: GRY,
                borderColor:     GRY_B,
                borderWidth: 1,
                borderRadius: 4,
            },
        ],
    } : null;

    const indexAxis = 'x';

    return (
        <div style={{
            minHeight: '100vh', background: '#f9fafb',
            padding: '32px 24px 64px',
            fontFamily: 'Plus Jakarta Sans, sans-serif',
        }}>
            <style>{`
                @keyframes shimmer {
                    0%   { background-position: -400% 0 }
                    100% { background-position:  400% 0 }
                }
                .charts-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 18px;
                }
                @media (max-width: 768px) {
                    .charts-grid { grid-template-columns: 1fr; }
                }
            `}</style>

            <div style={{ maxWidth: '1200px', margin: '0 auto' }}>

                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'flex-start',
                              justifyContent: 'space-between', marginBottom: '20px',
                              flexWrap: 'wrap', gap: '12px' }}>
                    <div>
                        <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800, color: '#111827' }}>
                            Analytics
                        </h1>
                        <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#9ca3af' }}>
                            {data ? `${data.total} candidates` : '—'} ·{' '}
                            {lastUpd ? `Live · updated ${lastUpd.toLocaleTimeString()}` : 'Loading…'}
                        </p>
                    </div>
                    <button
                        onClick={() => fetchData()}
                        disabled={loading}
                        style={{
                            padding: '8px 16px', borderRadius: '8px', border: '1px solid #e5e7eb',
                            background: '#fff', cursor: loading ? 'not-allowed' : 'pointer',
                            fontSize: '0.82rem', fontWeight: 600, color: '#374151',
                            opacity: loading ? 0.55 : 1,
                            fontFamily: 'Plus Jakarta Sans, sans-serif',
                            transition: 'opacity 0.2s',
                        }}
                    >
                        {loading ? 'Refreshing…' : '↻ Refresh'}
                    </button>
                </div>

                {/* Error */}
                {error && (
                    <div style={{
                        background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px',
                        padding: '12px 16px', marginBottom: '18px',
                        color: '#dc2626', fontSize: '0.85rem',
                    }}>
                        ⚠ {error} — make sure the backend is running on port 5001.
                    </div>
                )}

                {/* Stat cards */}
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '20px' }}>
                    <StatCard label="Total Candidates" value={data?.total ?? '—'} color="#1f77b4" />
                    <StatCard label="Avg Score"        value={data ? `${data.summary.avg_score}%` : '—'} color="#ff7f0e" />
                    <StatCard label="Shortlist Rate"   value={data ? `${data.summary.shortlist_rate}%` : '—'} color="#2ca02c" />
                    <StatCard label="Anomaly Rate"     value={data ? `${data.summary.anomaly_rate}%` : '—'} color="#9467bd" />
                    <StatCard label="Source"           value={data?.source === 'mongodb' ? '🟢 MongoDB' : '🟡 Local JSON'} color="#8c8c8c" />
                </div>

                {/* Charts */}
                <div className="charts-grid">

                    {/* 1 – Score Distribution */}
                    <ChartCard
                        title="Score Distribution"
                        subtitle="Candidates in each 10-point score band"
                        height={280}
                    >
                        {loading || !distChart
                            ? <Skeleton height={280} />
                            : <Bar data={distChart} options={{
                                ...baseOpts(),
                                plugins: {
                                    ...baseOpts().plugins,
                                    tooltip: {
                                        ...baseOpts().plugins.tooltip,
                                        callbacks: {
                                            label: ctx => ` ${ctx.parsed.y} candidates`,
                                        },
                                    },
                                },
                                scales: {
                                    ...baseOpts().scales,
                                    x: { ...baseOpts().scales.x, title: { display: true, text: 'Score Band (%)', color: '#9ca3af', font: { size: 11 } } },
                                    y: { ...baseOpts().scales.y, title: { display: true, text: 'Count', color: '#9ca3af', font: { size: 11 } } },
                                },
                            }} />
                        }
                    </ChartCard>

                    {/* 2 – Hiring Funnel */}
                    <ChartCard
                        title="Hiring Pipeline Funnel"
                        subtitle="Drop-off at each stage"
                        height={280}
                    >
                        {loading || !funnelChart
                            ? <Skeleton height={280} />
                            : <Bar data={funnelChart} options={{
                                ...baseOpts(),
                                indexAxis: 'y',
                                plugins: {
                                    ...baseOpts().plugins,
                                    legend: { display: false },
                                    tooltip: {
                                        ...baseOpts().plugins.tooltip,
                                        callbacks: {
                                            label: ctx => ` ${ctx.parsed.x} candidates`,
                                        },
                                    },
                                },
                                scales: {
                                    x: { ...baseOpts().scales.x, title: { display: true, text: 'Candidates', color: '#9ca3af', font: { size: 11 } } },
                                    y: { ...baseOpts().scales.y, grid: { display: false } },
                                },
                            }} />
                        }
                    </ChartCard>

                    {/* 3 – Skill × Avg Score */}
                    <ChartCard
                        title="Skill × Avg Score"
                        subtitle="Top 12 skills by average candidate score"
                        height={320}
                    >
                        {loading
                            ? <Skeleton height={320} />
                            : !skillChart
                            ? <div style={{ display:'flex', alignItems:'center', justifyContent:'center',
                                           height:'320px', color:'#9ca3af', fontSize:'0.85rem' }}>
                                  No skill data available
                              </div>
                            : <Bar data={skillChart} options={{
                                ...baseOpts(),
                                indexAxis: 'y',
                                plugins: {
                                    ...baseOpts().plugins,
                                    tooltip: {
                                        ...baseOpts().plugins.tooltip,
                                        callbacks: {
                                            label: ctx => {
                                                const idx = skillChart.labels.length - 1 - ctx.dataIndex;
                                                const count = data.skill_scores.counts[idx] || 0;
                                                return ` ${ctx.parsed.x}%  (${count} resumes)`;
                                            },
                                        },
                                    },
                                },
                                scales: {
                                    x: {
                                        ...baseOpts().scales.x,
                                        min: 0, max: 100,
                                        title: { display: true, text: 'Avg Score (%)', color: '#9ca3af', font: { size: 11 } },
                                    },
                                    y: { ...baseOpts().scales.y, grid: { display: false },
                                         ticks: { ...baseOpts().scales.y.ticks, font: { size: 10, family: 'Plus Jakarta Sans, sans-serif' } } },
                                },
                            }} />
                        }
                    </ChartCard>

                    {/* 4 – Score Components */}
                    <ChartCard
                        title="Score Components Breakdown"
                        subtitle="Avg achieved vs maximum for each AI component"
                        height={280}
                    >
                        {loading || !compChart
                            ? <Skeleton height={280} />
                            : <Bar data={compChart} options={{
                                ...baseOpts(),
                                plugins: {
                                    ...baseOpts().plugins,
                                    legend: {
                                        display: true,
                                        position: 'top',
                                        labels: {
                                            font: { size: 11, family: 'Plus Jakarta Sans, sans-serif' },
                                            color: '#6b7280',
                                            boxWidth: 12,
                                            padding: 14,
                                        },
                                    },
                                    tooltip: {
                                        ...baseOpts().plugins.tooltip,
                                        callbacks: {
                                            label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y} pts`,
                                        },
                                    },
                                },
                                scales: {
                                    x: { ...baseOpts().scales.x, grid: { display: false } },
                                    y: { ...baseOpts().scales.y, max: 45,
                                         title: { display: true, text: 'Points', color: '#9ca3af', font: { size: 11 } } },
                                },
                            }} />
                        }
                    </ChartCard>

                </div>

                <p style={{ marginTop: '24px', fontSize: '0.72rem', color: '#d1d5db', textAlign: 'center' }}>
                    Real-time · data from {data?.source === 'mongodb' ? 'MongoDB Atlas' : 'local JSON'} · auto-refreshes every 30s
                </p>

            </div>
        </div>
    );
}
