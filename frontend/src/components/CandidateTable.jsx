// CandidateTable.jsx — HireFlow AI  
// Redesigned: expandable rows, score breakdown, dark but readable.

import { useState } from 'react';
import '../styles/dashboard.css';

function cleanFilename(raw) {
    if (!raw) return '—';
    let name = raw.replace(/^[0-9a-f]{8}_/i, '');
    name = name.replace(/\.[a-z]{2,5}$/i, '');
    name = name.replace(/[-_]+/g, ' ');
    return name.trim();
}

function scoreClass(score) {
    if (score >= 60) return 'score-high';
    if (score >= 35) return 'score-mid';
    return 'score-low';
}

// ── Inline mini bar for Score Breakdown ──────────────────────────────────────
function BreakdownBar({ value, max, color }) {
    const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
    return (
        <div className="score-breakdown-bar-wrap">
            <div className="score-breakdown-bar-track">
                <div
                    className="score-breakdown-bar-fill"
                    style={{ width: `${pct}%`, background: color }}
                />
            </div>
            <span className="score-breakdown-val">{value.toFixed(1)}</span>
        </div>
    );
}

// ── Skill pills ───────────────────────────────────────────────────────────────
function SkillPills({ skills, jdMatched = [], limit = 8 }) {
    const [expanded, setExpanded] = useState(false);
    const list = skills || [];
    if (list.length === 0) return <span style={{ color: 'var(--ink-faint)', fontSize: '0.82rem' }}>No skills extracted</span>;

    // normalise for comparison
    const matchedSet = new Set((jdMatched || []).map(s => s.toLowerCase().trim()));

    const visible   = expanded ? list : list.slice(0, limit);
    const remaining = list.length - limit;

    return (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
            {visible.map((skill, i) => {
                const isMatch = matchedSet.has(skill.toLowerCase().trim());
                return (
                    <span key={i} className={`skill-pill ${isMatch ? 'skill-pill-match' : ''}`}>
                        {isMatch && <span style={{ marginRight: '3px', fontSize: '0.7em' }}>✓</span>}
                        {skill}
                    </span>
                );
            })}
            {!expanded && remaining > 0 && (
                <span className="skill-pill" style={{ cursor: 'pointer', opacity: 0.6 }}
                    onClick={() => setExpanded(true)}>
                    +{remaining} more
                </span>
            )}
            {expanded && (
                <span className="skill-pill" style={{ cursor: 'pointer', opacity: 0.6 }}
                    onClick={() => setExpanded(false)}>
                    show less
                </span>
            )}
        </div>
    );
}

// ── Expanded detail card ──────────────────────────────────────────────────────
function CandidateDetail({ candidate, jobDescription }) {
    const tabScore   = candidate.tab_transformer_score   ?? null;
    const vecScore   = candidate.vector_similarity_score ?? null;
    const tfidfScore = candidate.tfidf_score             ?? null;

    // detect stale data (old scorer results that don't have breakdown fields)
    const hasBreakdown = tabScore !== null && vecScore !== null && tfidfScore !== null;
    const allZero = hasBreakdown && tabScore === 0 && vecScore === 0 && tfidfScore === 0;
    const hasJD   = !!(jobDescription && jobDescription.trim());

    const skills = candidate.skills || candidate.matched_skills || [];
    const jdMatchedSkills = candidate.jd_matched_skills || [];

    return (
        <div className="candidate-detail-card">

            {/* ── Info grid ── */}
            <div className="detail-grid">
                <div className="detail-cell">
                    <span className="detail-label">Email</span>
                    <span className="detail-value">
                        {candidate.email
                            ? <a href={`mailto:${candidate.email}`} style={{ color: '#7bb4fd', textDecoration: 'none' }}>{candidate.email}</a>
                            : <span style={{ color: '#3a3a50' }}>—</span>}
                    </span>
                </div>
                <div className="detail-cell">
                    <span className="detail-label">Phone</span>
                    <span className="detail-value">{candidate.phone || <span style={{ color: '#3a3a50' }}>—</span>}</span>
                </div>
                <div className="detail-cell">
                    <span className="detail-label">Experience</span>
                    <span className="detail-value">
                        {candidate.experience_years > 0
                            ? `${candidate.experience_years} yr${candidate.experience_years !== 1 ? 's' : ''}`
                            : <span style={{ color: '#3a3a50' }}>—</span>}
                    </span>
                </div>
                <div className="detail-cell">
                    <span className="detail-label">Education</span>
                    <span className="detail-value">
                        {candidate.education || <span style={{ color: '#3a3a50' }}>—</span>}
                    </span>
                </div>
                <div className="detail-cell">
                    <span className="detail-label">Department</span>
                    <span className="detail-value">
                        {candidate.department && candidate.department !== 'Unknown'
                            ? candidate.department
                            : <span style={{ color: '#3a3a50' }}>—</span>}
                    </span>
                </div>
                <div className="detail-cell">
                    <span className="detail-label">Job Role</span>
                    <span className="detail-value">
                        {candidate.job_role || <span style={{ color: '#3a3a50' }}>—</span>}
                    </span>
                </div>
            </div>

            {/* ── Skills ── */}
            <div className="detail-skills-row">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <span className="detail-label">Skills</span>
                    {jdMatchedSkills.length > 0 && (
                        <span style={{
                            fontSize: '0.68rem', color: '#3b7ef8', fontWeight: 700,
                            background: 'rgba(59,126,248,0.1)', border: '1px solid rgba(59,126,248,0.2)',
                            padding: '2px 8px', borderRadius: '20px'
                        }}>
                            ✓ {jdMatchedSkills.length} match{jdMatchedSkills.length !== 1 ? 'es' : ''} JD
                        </span>
                    )}
                </div>
                <SkillPills skills={skills} jdMatched={jdMatchedSkills} limit={10} />
            </div>

            {/* ── Score Breakdown ── */}
            <div className="detail-score-breakdown">
                <span className="detail-label" style={{ display: 'block', marginBottom: '14px', fontSize: '0.68rem' }}>
                    AI Score Breakdown
                    {!hasJD && (
                        <span style={{ marginLeft: '8px', color: 'var(--ink-faint)', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>
                            (no JD provided — scored on profile richness)
                        </span>
                    )}
                </span>

                <div className="score-breakdown-row">
                    <div className="score-breakdown-label">
                        <span>TabTransformer</span>
                        <span className="score-breakdown-max">/ 40</span>
                    </div>
                    <BreakdownBar value={hasBreakdown ? tabScore : 0} max={40} color="#3b7ef8" />
                </div>

                <div className="score-breakdown-row">
                    <div className="score-breakdown-label">
                        <span>{hasJD ? 'Vector Similarity' : 'Profile Depth'}</span>
                        <span className="score-breakdown-max">/ 35</span>
                    </div>
                    <BreakdownBar value={hasBreakdown ? vecScore : 0} max={35} color="#8b5cf6" />
                </div>

                <div className="score-breakdown-row">
                    <div className="score-breakdown-label">
                        <span>{hasJD ? 'TF-IDF Match' : 'Keyword Match'}</span>
                        <span className="score-breakdown-max">/ 25</span>
                    </div>
                    <BreakdownBar value={hasBreakdown ? tfidfScore : 0} max={25} color="#34d399" />
                </div>

                <div className="score-breakdown-total">
                    <span>Total score</span>
                    <strong>{candidate.score}%</strong>
                </div>

                {/* stale data notice */}
                {(allZero || !hasBreakdown) && (
                    <div className="score-stale-notice">
                        <span>⚠</span>
                        <span>Score breakdown not available for older results. Re-upload resumes to see the full AI breakdown.</span>
                    </div>
                )}
            </div>

            {/* ── Anomaly reason ── */}
            {candidate.is_anomaly && candidate.anomaly_reason && (
                <div className="detail-anomaly-reason">
                    ⚠ {candidate.anomaly_reason}
                </div>
            )}

            <div className="detail-meta-row">
                <span>File:</span>
                <span>{candidate.filename || '—'}</span>
            </div>
        </div>
    );
}

// ── CSV Export ────────────────────────────────────────────────────────────────
function exportToCSV(candidates) {
    const headers = [
        'Rank', 'Name', 'Email', 'Phone', 'Score',
        'TabTransformer', 'Vector Sim', 'TF-IDF',
        'Experience (Yrs)', 'Education', 'Department', 'Job Role',
        'Shortlisted', 'Anomaly', 'Skills', 'Filename'
    ];

    const rows = candidates.map(c => [
        c.rank,
        `"${(c.name || '').replace(/"/g, '""')}"`,
        c.email || '',
        c.phone || '',
        c.score,
        c.tab_transformer_score  ?? '',
        c.vector_similarity_score ?? '',
        c.tfidf_score             ?? '',
        c.experience_years        ?? 0,
        `"${(c.education   || '').replace(/"/g, '""')}"`,
        c.department  || '',
        `"${(c.job_role    || '').replace(/"/g, '""')}"`,
        c.shortlisted ? 'Yes' : 'No',
        c.is_anomaly  ? 'Flagged' : 'Clean',
        `"${(c.skills || c.matched_skills || []).join(', ')}"`,
        `"${(c.filename || '').replace(/"/g, '""')}"`,
    ]);

    const csv  = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    a.setAttribute('download', 'hireflow-results.csv');
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// ── Main table ──────────────────────────────────────────────────────────────────────────────
function CandidateTable({ candidates, jobDescription }) {
    const [expandedRow, setExpandedRow] = useState(null);
    const flaggedCount = candidates.filter(c => c.is_anomaly).length;

    const toggle = (rank) => setExpandedRow(prev => prev === rank ? null : rank);

    return (
        <div className="results-section">

            {/* Header */}
            <div className="results-section-header">
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                    <h3 className="results-section-title">Candidate Rankings</h3>
                    <span style={{ color: '#505065', fontSize: '0.88rem' }}>
                        {candidates.length} candidate{candidates.length !== 1 ? 's' : ''}
                    </span>
                </div>
                <button onClick={() => exportToCSV(candidates)} className="export-btn">
                    ↓ Export CSV
                </button>
            </div>

            {/* Anomaly banner */}
            {flaggedCount > 0 && (
                <div className="anomaly-banner">
                    ⚠ <strong>{flaggedCount}</strong> of {candidates.length} candidate{candidates.length !== 1 ? 's' : ''} flagged — review carefully before shortlisting.
                </div>
            )}

            {/* Rows */}
            <div className="candidate-list">
                {candidates.map((c) => {
                    const isExpanded = expandedRow === c.rank;
                    const cls = scoreClass(c.score);
                    const name = c.name || cleanFilename(c.filename);

                    return (
                        <div
                            key={c.rank}
                            className={`candidate-row ${isExpanded ? 'expanded' : ''} ${c.is_anomaly ? 'flagged' : ''}`}
                        >
                            {/* ── Collapsed row ── */}
                            <div
                                className="candidate-row-summary"
                                onClick={() => toggle(c.rank)}
                                role="button"
                                tabIndex={0}
                                aria-expanded={isExpanded}
                                onKeyDown={(e) => e.key === 'Enter' && toggle(c.rank)}
                            >
                                {/* Rank */}
                                <div className="col-rank">
                                    <span className={`rank-badge ${c.rank <= 3 ? 'top-3' : ''}`}>
                                        #{c.rank}
                                    </span>
                                </div>

                                {/* Name + role/dept hint */}
                                <div className="col-name">
                                    <span className="candidate-name-text">{name}</span>
                                    {(c.job_role || c.department) && (
                                        <span className="candidate-role-hint">
                                            {c.job_role || c.department}
                                        </span>
                                    )}
                                </div>

                                {/* Score bar */}
                                <div className="col-score">
                                    <div className="score-bar-wrap">
                                        <div
                                            className={`score-bar-fill ${cls}`}
                                            style={{ width: `${Math.min(c.score, 100)}%` }}
                                        />
                                    </div>
                                    <span className={`score-label ${cls}`}>{c.score}%</span>
                                </div>


                                {/* Anomaly */}
                                <div className="col-anomaly">
                                    {c.is_anomaly
                                        ? <span className="badge badge-red">⚠ Flagged</span>
                                        : <span className="badge badge-clean">✓ Clean</span>}
                                </div>

                                {/* Chevron */}
                                <div className="col-expand">
                                    <svg
                                        className={`chevron-icon ${isExpanded ? 'rotated' : ''}`}
                                        viewBox="0 0 24 24" fill="none"
                                        stroke="currentColor" strokeWidth="2.5"
                                    >
                                        <polyline points="6 9 12 15 18 9" />
                                    </svg>
                                </div>
                            </div>

                            {/* ── Expanded detail ── */}
                            {isExpanded && <CandidateDetail candidate={c} jobDescription={jobDescription} />}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export default CandidateTable;
