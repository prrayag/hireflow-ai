// Dashboard.jsx - shows the results of processed resumes
<<<<<<< HEAD
// fetches data from Flask backend on load and displays ranked candidates
=======
// fetches data from Flask backend on load and displays stats + candidate table
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import CandidateTable from '../components/CandidateTable';
<<<<<<< HEAD
=======
import DashboardChart from '../components/DashboardChart';
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
import { useScrollReveal } from '../hooks/useScrollReveal';
import '../styles/dashboard.css';

function Dashboard() {
    const navigate = useNavigate();

<<<<<<< HEAD
=======
    // state for the candidates data from the backend
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
    const [candidates, setCandidates] = useState([]);
    const [loading, setLoading] = useState(true);
    const [jobDescription, setJobDescription] = useState('');

    useScrollReveal([candidates, loading]);

<<<<<<< HEAD
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
=======
    // frontend filter/search states
    const [searchQuery, setSearchQuery] = useState('');
    const [showFlaggedOnly, setShowFlaggedOnly] = useState(false);
    const [topN, setTopN] = useState('all'); // controls how many top candidates to show
    const [jdExpanded, setJdExpanded] = useState(true);

    // fetch results from Flask when the component mounts
    useEffect(() => {
        const fetchResults = async () => {
            try {
                const response = await axios.get(`${API_BASE_URL}/results`);
                console.log('got results:', response.data);
                setCandidates(response.data.candidates || []);
                setJobDescription(response.data.job_description || '');
            } catch (err) {
                console.error('failed to fetch results:', err);
                // if the backend isn't running or has no data, just show empty state
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                setCandidates([]);
            } finally {
                setLoading(false);
            }
        };
<<<<<<< HEAD
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
=======

        fetchResults();
    }, []);

    // calculate stats for the top bar
    const totalResumes = candidates.length;
    const avgScore =
        totalResumes > 0
            ? (candidates.reduce((sum, c) => sum + c.score, 0) / totalResumes).toFixed(1)
            : '0.0';
    const topCandidate = totalResumes > 0 ? candidates[0]?.name : '—';

    // apply our frontend filters to the loaded candidate list
    const filteredCandidates = candidates
        .filter((candidate) => {
            const searchLower = searchQuery.toLowerCase();
            const matchesSearch =
                candidate.name.toLowerCase().includes(searchLower) ||
                candidate.matched_skills.some(skill => skill.toLowerCase().includes(searchLower));
            const matchesFlagged = showFlaggedOnly ? candidate.is_anomaly === true : true;
            return matchesSearch && matchesFlagged;
        })
        // apply top-n slice. candidates are already sorted by score desc from the backend
        .slice(0, topN === 'all' ? undefined : parseInt(topN, 10));

    // loading state while we wait for the backend response
    if (loading) {
        return (
            <div className="dashboard-page">
                <div className="upload-loading" style={{ marginTop: '80px' }}>
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                    <div className="upload-spinner"></div>
                    <p className="upload-loading-text">Loading results...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="dashboard-page overflow-hidden">
<<<<<<< HEAD

            {/* Header */}
            <div className="dashboard-header animate-on-scroll">
                <h1 className="dashboard-title">Dashboard</h1>
                <button className="btn-primary" onClick={() => navigate('/upload')}>
=======
            {/* header with title and upload more button */}
            <div className="dashboard-header animate-on-scroll">
                <h1 className="dashboard-title">Dashboard</h1>
                <button
                    className="btn-primary"
                    onClick={() => navigate('/upload')}
                >
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                    Upload More
                </button>
            </div>

            {candidates.length > 0 ? (
                <>
<<<<<<< HEAD
                    {/* ── Stats bar ── */}
=======
                    {/* stats bar at the top - three boxes, no emojis */}
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
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
<<<<<<< HEAD
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
=======
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                            <div className="stat-icon-bar stat-icon-sage"></div>
                            <div className="stat-value stat-value-sm">{topCandidate}</div>
                            <div className="stat-label">Top Candidate</div>
                        </div>
                    </div>

<<<<<<< HEAD
                    {/* ── Job description panel ── */}
                    <div className="jd-panel animate-on-scroll" style={{ animationDelay: '0.15s' }}>
                        <div className="jd-panel-header" onClick={() => setJdExpanded(!jdExpanded)}>
                            <div className="jd-panel-title-area">
                                <svg className="jd-panel-icon" viewBox="0 0 24 24" fill="none"
                                    stroke="currentColor" strokeWidth="2"
                                    strokeLinecap="round" strokeLinejoin="round">
=======
                    {/* visual representation chart */}
                    {filteredCandidates.length > 0 && (
                        <DashboardChart candidates={filteredCandidates} />
                    )}

                    {/* Job Description panel */}
                    <div className="jd-panel animate-on-scroll" style={{ animationDelay: '0.2s' }}>
                        <div className="jd-panel-header" onClick={() => setJdExpanded(!jdExpanded)}>
                            <div className="jd-panel-title-area">
                                <svg className="jd-panel-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                    <polyline points="14 2 14 8 20 8" />
                                    <line x1="16" y1="13" x2="8" y2="13" />
                                    <line x1="16" y1="17" x2="8" y2="17" />
                                    <polyline points="10 9 9 9 8 9" />
                                </svg>
                                <h3 className="jd-panel-title">Job Description Used for Scoring</h3>
<<<<<<< HEAD
                                {jobDescription && <span className="jd-panel-badge">+ Active</span>}
                            </div>
                            <svg className={`jd-panel-chevron ${jdExpanded ? 'expanded' : ''}`}
                                viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" strokeWidth="2"
                                strokeLinecap="round" strokeLinejoin="round">
=======
                                {jobDescription && (
                                    <span className="jd-panel-badge">Active</span>
                                )}
                            </div>
                            <svg className={`jd-panel-chevron ${jdExpanded ? 'expanded' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                                <polyline points="6 9 12 15 18 9" />
                            </svg>
                        </div>
                        {jdExpanded && (
                            <div className="jd-panel-body">
                                {jobDescription ? (
                                    <p className="jd-panel-text">{jobDescription}</p>
                                ) : (
                                    <p className="jd-panel-empty">
<<<<<<< HEAD
                                        No job description was provided for this batch.
                                        Scoring used default semantic matching against general software engineering keywords.
=======
                                        No job description was provided for this batch. Scoring used default semantic matching against general software engineering keywords.
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                                    </p>
                                )}
                            </div>
                        )}
                    </div>

<<<<<<< HEAD
                    {/* ── Controls ── */}
                    <div className="dashboard-controls animate-on-scroll" style={{ animationDelay: '0.2s' }}>
=======
                    {/* search, filter, and top-n control bar above the table */}
                    <div className="dashboard-controls animate-on-scroll" style={{ animationDelay: '0.3s' }}>
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                        <input
                            type="text"
                            placeholder="Search by name or skill..."
                            value={searchQuery}
<<<<<<< HEAD
                            onChange={e => setSearchQuery(e.target.value)}
=======
                            onChange={(e) => setSearchQuery(e.target.value)}
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
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
<<<<<<< HEAD
                                onChange={e => setTopN(e.target.value)}
=======
                                onChange={(e) => setTopN(e.target.value)}
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
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

<<<<<<< HEAD
                    {/* ── Candidate table ── */}
                    {filteredCandidates.length > 0 ? (
                        <CandidateTable candidates={filteredCandidates} />
                    ) : (
                        <div style={{
                            textAlign: 'center', padding: '48px',
                            background: 'var(--bg-card)', borderRadius: '12px',
                            border: '1px solid var(--border)'
                        }}>
                            <p style={{ color: 'var(--text-muted)', margin: 0 }}>
=======
                    {/* determine whether to show the table or a generic 'no match' message */}
                    {filteredCandidates.length > 0 ? (
                        <CandidateTable candidates={filteredCandidates} />
                    ) : (
                        <div style={{ textAlign: 'center', padding: '40px', backgroundColor: '#fff', borderRadius: '12px', border: '1px solid #eaeaea' }}>
                            <p style={{ color: '#666', fontSize: '1.05rem', margin: 0 }}>
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                                No candidates match your filters. Try adjusting your search.
                            </p>
                        </div>
                    )}
                </>
            ) : (
<<<<<<< HEAD
                // empty state
=======
                // empty state - no results yet
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                <div className="dashboard-empty">
                    <div className="dashboard-empty-visual"></div>
                    <h2 className="dashboard-empty-title">No Results Yet</h2>
                    <p className="dashboard-empty-text">
                        Upload a ZIP file of resumes to see candidate rankings here.
                    </p>
<<<<<<< HEAD
                    <button className="btn-primary" onClick={() => navigate('/upload')}>
=======
                    <button
                        className="btn-primary"
                        onClick={() => navigate('/upload')}
                    >
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                        Upload Resumes
                    </button>
                </div>
            )}
        </div>
    );
}

export default Dashboard;
