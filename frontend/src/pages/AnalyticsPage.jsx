// AnalyticsPage.jsx — HireFlow AI
// Charts generated server-side with real matplotlib, served as base64 PNG images.

import React, { useEffect, useState, useCallback } from 'react';
import { API_BASE_URL } from '../config';
import '../styles/analytics.css';

// ── Skeleton loader while chart is fetching ──────────────────────────────────
function ChartSkeleton() {
    return (
        <div style={{
            width: '100%', height: '340px',
            background: 'linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)',
            backgroundSize: '200% 100%',
            animation: 'skeleton-shimmer 1.4s infinite',
            borderRadius: '8px',
            border: '1px solid #e5e5e5',
        }} />
    );
}

// ── Single chart card ─────────────────────────────────────────────────────────
function ChartCard({ title, description, imgSrc, loading }) {
    return (
        <div style={{
            background: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '12px',
            padding: '20px 20px 12px',
            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
        }}>
            <div style={{ marginBottom: '10px' }}>
                <h3 style={{
                    margin: 0, fontSize: '0.93rem', fontWeight: 700,
                    color: '#111827', fontFamily: 'Plus Jakarta Sans, sans-serif',
                }}>{title}</h3>
                {description && (
                    <p style={{
                        margin: '3px 0 0', fontSize: '0.78rem',
                        color: '#6b7280', fontFamily: 'Plus Jakarta Sans, sans-serif',
                    }}>{description}</p>
                )}
            </div>
            {loading ? (
                <ChartSkeleton />
            ) : imgSrc ? (
                <img
                    src={imgSrc}
                    alt={title}
                    style={{
                        width: '100%', height: 'auto',
                        display: 'block', borderRadius: '4px',
                        border: '1px solid #f0f0f0',
                    }}
                />
            ) : (
                <div style={{
                    height: '200px', display: 'flex', alignItems: 'center',
                    justifyContent: 'center', color: '#9ca3af', fontSize: '0.85rem',
                    border: '1px dashed #e5e7eb', borderRadius: '8px',
                }}>
                    No data available
                </div>
            )}
        </div>
    );
}

// ── Meta strip (key numbers) ──────────────────────────────────────────────────
function MetaStrip({ stats }) {
    const items = [
        { label: 'Total Candidates', value: stats.total ?? '—' },
        { label: 'Avg Score',        value: stats.avgScore != null ? `${stats.avgScore}%` : '—' },
        { label: 'Shortlist Rate',   value: stats.shortlistRate != null ? `${stats.shortlistRate}%` : '—' },
        { label: 'Anomaly Rate',     value: stats.anomalyRate != null ? `${stats.anomalyRate}%` : '—' },
        { label: 'Source',           value: stats.source === 'mongodb' ? '🟢 MongoDB' : '🟡 Local JSON' },
    ];
    return (
        <div style={{
            display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '24px',
        }}>
            {items.map(({ label, value }) => (
                <div key={label} style={{
                    background: '#fff', border: '1px solid #e5e7eb', borderRadius: '10px',
                    padding: '10px 18px', flex: '1 1 140px', minWidth: '120px',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                }}>
                    <div style={{ fontSize: '0.68rem', color: '#9ca3af', fontWeight: 600,
                                  textTransform: 'uppercase', letterSpacing: '0.05em',
                                  fontFamily: 'Plus Jakarta Sans, sans-serif', marginBottom: '4px' }}>
                        {label}
                    </div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#111827',
                                  fontFamily: 'Plus Jakarta Sans, sans-serif' }}>
                        {value}
                    </div>
                </div>
            ))}
        </div>
    );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
    const [charts, setCharts]   = useState({});
    const [stats,  setStats]    = useState({});
    const [loading, setLoading] = useState(true);
    const [error,   setError]   = useState(null);
    const [lastRefresh, setLastRefresh] = useState(null);

    const fetchCharts = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [chartRes, statsRes] = await Promise.all([
                fetch(`${API_BASE_URL}/api/charts`),
                fetch(`${API_BASE_URL}/api/big-data-stats`),
            ]);

            if (!chartRes.ok) throw new Error(`Charts endpoint returned ${chartRes.status}`);

            const chartData = await chartRes.json();
            const statsData = statsRes.ok ? await statsRes.json() : {};

            setCharts(chartData.charts || {});
            setStats({
                total:         chartData.total,
                source:        chartData.source,
                avgScore:      statsData.gauge?.avgScore,
                shortlistRate: statsData.gauge?.shortlistRate,
                anomalyRate:   statsData.gauge?.anomalyRate,
            });
            setLastRefresh(new Date());
        } catch (err) {
            console.error('[AnalyticsPage] fetch error:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    // Fetch on mount
    useEffect(() => { fetchCharts(); }, [fetchCharts]);

    // Poll every 60s (charts are heavier, no need to poll fast)
    useEffect(() => {
        const id = setInterval(() => {
            if (!document.hidden) fetchCharts();
        }, 60_000);
        return () => clearInterval(id);
    }, [fetchCharts]);

    return (
        <div style={{
            minHeight: '100vh',
            background: '#f9fafb',
            padding: '32px 24px 64px',
            fontFamily: 'Plus Jakarta Sans, sans-serif',
        }}>
            <div style={{ maxWidth: '1200px', margin: '0 auto' }}>

                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                              marginBottom: '8px', flexWrap: 'wrap', gap: '12px' }}>
                    <div>
                        <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800, color: '#111827' }}>
                            Analytics
                        </h1>
                        <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#6b7280' }}>
                            {stats.total != null ? `${stats.total} candidates` : 'Loading...'} ·
                            {lastRefresh ? ` Updated ${lastRefresh.toLocaleTimeString()}` : ' Fetching...'}
                        </p>
                    </div>
                    <button
                        onClick={fetchCharts}
                        disabled={loading}
                        style={{
                            padding: '8px 16px', borderRadius: '8px', border: '1px solid #e5e7eb',
                            background: '#fff', cursor: loading ? 'not-allowed' : 'pointer',
                            fontSize: '0.82rem', fontWeight: 600, color: '#374151',
                            opacity: loading ? 0.6 : 1,
                            fontFamily: 'Plus Jakarta Sans, sans-serif',
                        }}
                    >
                        {loading ? 'Generating...' : '↻ Refresh Charts'}
                    </button>
                </div>

                {/* Error banner */}
                {error && (
                    <div style={{
                        background: '#fef2f2', border: '1px solid #fecaca',
                        borderRadius: '8px', padding: '12px 16px', marginBottom: '20px',
                        color: '#dc2626', fontSize: '0.85rem',
                    }}>
                        ⚠ Could not load charts: {error}. Make sure the backend is running on port 5001.
                    </div>
                )}

                {/* Meta strip */}
                <MetaStrip stats={stats} />

                {/* ── Charts grid ── */}
                <style>{`
                    @keyframes skeleton-shimmer {
                        0%   { background-position: -200% 0; }
                        100% { background-position:  200% 0; }
                    }
                    .charts-grid {
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 20px;
                    }
                    @media (max-width: 768px) {
                        .charts-grid { grid-template-columns: 1fr; }
                    }
                `}</style>

                <div className="charts-grid">
                    <ChartCard
                        title="Score Distribution"
                        description="How many candidates fall in each 10-point score band"
                        imgSrc={charts.score_distribution}
                        loading={loading}
                    />
                    <ChartCard
                        title="Hiring Pipeline Funnel"
                        description="Candidate drop-off at each stage of the pipeline"
                        imgSrc={charts.hiring_funnel}
                        loading={loading}
                    />
                    <ChartCard
                        title="Skill × Avg Score"
                        description="Which skills correlate with higher-scoring candidates"
                        imgSrc={charts.skill_heatmap}
                        loading={loading}
                    />
                    <ChartCard
                        title="Score Components Breakdown"
                        description="Average achieved vs maximum for each scoring component"
                        imgSrc={charts.score_components}
                        loading={loading}
                    />
                </div>

                {/* Note */}
                <p style={{
                    marginTop: '28px', fontSize: '0.75rem', color: '#9ca3af', textAlign: 'center',
                }}>
                    Charts generated server-side with Python matplotlib · Data from {stats.source === 'mongodb' ? 'MongoDB Atlas' : 'local JSON'}
                </p>

            </div>
        </div>
    );
}
