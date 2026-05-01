// Dashboard.jsx - shows the results of processed resumes
// fetches data from Flask backend on load and displays ranked candidates

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import CandidateTable from '../components/CandidateTable';
import { useScrollReveal } from '../hooks/useScrollReveal';
import '../styles/dashboard.css';

function Dashboard() {
    const navigate = useNavigate();

    const [candidates, setCandidates] = useState([]);
    const [loading, setLoading] = useState(true);
    const [jobDescription, setJobDescription] = useState('');

    useScrollReveal([candidates, loading]);

    const [searchQuery, setSearchQuery] = useState('');
    const [showFlaggedOnly, setShowFlaggedOnly] = useState(false);
    const [topN, setTopN] = useState('all');
    const [jdExpanded, setJdExpanded] = useState(true);

    useEffect(() => {
        const fetchResults = async () => {
            try {
                const res = await axios.get(`${API_BASE_URL}/results`);
                setCandidates(res.data.candidates || []);
                setJobDescription(res.data.job_description || '');
            } catch (err) {
                console.error('failed to fetch data:', err);
                setCandidates([]);
            } finally {
                setLoading(false);
            }
        };
        fetchResults();
    }, []);

    // stats
    const totalResumes  = candidates.length;
    const shortlisted   = candidates.filter(c => c.shortlisted).length;
    const flagged       = candidates.filter(c => c.is_anomaly).length;
    const avgScore      = totalResumes > 0
        ? (candidates.reduce((s, c) => s + c.score, 0) / totalResumes).toFixed(1)
        : '—';
    const topCandidate  = totalResumes > 0 ? (candidates[0]?.name || '—') : '—';

    // filters
    const filteredCandidates = candidates
        .filter(c => {
            const q = searchQuery.toLowerCase();
            const matchesSearch =
                (c.name || '').toLowerCase().includes(q) ||
                (c.matched_skills || c.skills || []).some(s => s.toLowerCase().includes(q));
            const matchesFlagged = showFlaggedOnly ? c.is_anomaly === true : true;
            return matchesSearch && matchesFlagged;
        })
        .slice(0, topN === 'all' ? undefined : parseInt(topN, 10));

    if (loading) {
        return (
            <div className="dashboard-page">
                <div className="upload-loading" style={{ marginTop: '100px' }}>
                    <div className="upload-spinner"></div>
                    <p className="upload-loading-text">Loading results...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="dashboard-page overflow-hidden">

            {/* Header */}
            <div className="dashboard-header animate-on-scroll">
                <h1 className="dashboard-title">Dashboard</h1>
                <button className="btn-primary" onClick={() => navigate('/upload')}>
                    Upload More
                </button>
            </div>

            {candidates.length > 0 ? (
                <>
                    {/* ── Stats bar ── */}
                    <div className="stats-bar animate-on-scroll" style={{ animationDelay: '0.1s' }}>
                        <div className="stat-box">
                            <div className="stat-icon-bar stat-icon-blue"></div>
                            <div className="stat-value">{totalResumes}</div>
                            <div className="stat-label">Total Resumes</div>
                        </div>
                        <div className="stat-box">
                            <div className="stat-icon-bar stat-icon-orange"></div>
                            <div className="stat-value">{avgScore}</div>
                            <div className="stat-label">Average Score</div>
                        </div>
                        <div className="stat-box">
                            <div className="stat-icon-bar" style={{ background: '#22c55e' }}></div>
                            <div className="stat-value">{shortlisted}</div>
                            <div className="stat-label">Shortlisted</div>
                        </div>
                        <div className="stat-box">
                            <div className="stat-icon-bar" style={{ background: '#ef4444' }}></div>
                            <div className="stat-value">{flagged}</div>
                            <div className="stat-label">Flagged</div>
                        </div>
                        <div className="stat-box">
                            <div className="stat-icon-bar stat-icon-sage"></div>
                            <div className="stat-value stat-value-sm">{topCandidate}</div>
                            <div className="stat-label">Top Candidate</div>
                        </div>
                    </div>

                    {/* ── Job description panel ── */}
                    <div className="jd-panel animate-on-scroll" style={{ animationDelay: '0.15s' }}>
                        <div className="jd-panel-header" onClick={() => setJdExpanded(!jdExpanded)}>
                            <div className="jd-panel-title-area">
                                <svg className="jd-panel-icon" viewBox="0 0 24 24" fill="none"
                                    stroke="currentColor" strokeWidth="2"
                                    strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                    <polyline points="14 2 14 8 20 8" />
                                    <line x1="16" y1="13" x2="8" y2="13" />
                                    <line x1="16" y1="17" x2="8" y2="17" />
                                    <polyline points="10 9 9 9 8 9" />
                                </svg>
                                <h3 className="jd-panel-title">Job Description Used for Scoring</h3>
                                {jobDescription && <span className="jd-panel-badge">+ Active</span>}
                            </div>
                            <svg className={`jd-panel-chevron ${jdExpanded ? 'expanded' : ''}`}
                                viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" strokeWidth="2"
                                strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="6 9 12 15 18 9" />
                            </svg>
                        </div>
                        {jdExpanded && (
                            <div className="jd-panel-body">
                                {jobDescription ? (
                                    <p className="jd-panel-text">{jobDescription}</p>
                                ) : (
                                    <p className="jd-panel-empty">
                                        No job description was provided for this batch.
                                        Scoring used default semantic matching against general software engineering keywords.
                                    </p>
                                )}
                            </div>
                        )}
                    </div>

                    {/* ── Controls ── */}
                    <div className="dashboard-controls animate-on-scroll" style={{ animationDelay: '0.2s' }}>
                        <input
                            type="text"
                            placeholder="Search by name or skill..."
                            value={searchQuery}
                            onChange={e => setSearchQuery(e.target.value)}
                            className="search-input"
                        />
                        <button
                            onClick={() => setShowFlaggedOnly(!showFlaggedOnly)}
                            className={`flagged-btn ${showFlaggedOnly ? 'active' : ''}`}
                        >
                            {showFlaggedOnly ? 'Showing Flagged' : 'Show Flagged Only'}
                        </button>
                        <div className="topn-control">
                            <label htmlFor="topn-select" className="topn-label">View:</label>
                            <select
                                id="topn-select"
                                value={topN}
                                onChange={e => setTopN(e.target.value)}
                                className="topn-select"
                            >
                                <option value="5">Top 5</option>
                                <option value="10">Top 10</option>
                                <option value="20">Top 20</option>
                                <option value="50">Top 50</option>
                                <option value="all">All</option>
                            </select>
                        </div>
                    </div>

                    {/* ── Candidate table ── */}
                    {filteredCandidates.length > 0 ? (
                        <CandidateTable candidates={filteredCandidates} jobDescription={jobDescription} />
                    ) : (
                        <div style={{
                            textAlign: 'center', padding: '48px',
                            background: 'var(--bg-card)', borderRadius: '12px',
                            border: '1px solid var(--border)'
                        }}>
                            <p style={{ color: 'var(--text-muted)', margin: 0 }}>
                                No candidates match your filters. Try adjusting your search.
                            </p>
                        </div>
                    )}
                </>
            ) : (
                // empty state
                <div className="dashboard-empty">
                    <div className="dashboard-empty-visual"></div>
                    <h2 className="dashboard-empty-title">No Results Yet</h2>
                    <p className="dashboard-empty-text">
                        Upload a ZIP file of resumes to see candidate rankings here.
                    </p>
                    <button className="btn-primary" onClick={() => navigate('/upload')}>
                        Upload Resumes
                    </button>
                </div>
            )}
        </div>
    );
}

export default Dashboard;
