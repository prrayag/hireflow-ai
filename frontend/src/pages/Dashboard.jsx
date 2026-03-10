// Dashboard.jsx - shows the results of processed resumes
// fetches data from Flask backend on load and displays stats + candidate table

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import CandidateTable from '../components/CandidateTable';
import '../styles/dashboard.css';

function Dashboard() {
    const navigate = useNavigate();

    // state for the candidates data from the backend
    const [candidates, setCandidates] = useState([]);
    const [loading, setLoading] = useState(true);

    // new states for the frontend search and filter functionality
    const [searchQuery, setSearchQuery] = useState('');
    const [showFlaggedOnly, setShowFlaggedOnly] = useState(false);

    // fetch results from Flask when the component mounts
    useEffect(() => {
        const fetchResults = async () => {
            try {
                const response = await axios.get(`${API_BASE_URL}/results`);
                console.log('got results:', response.data);
                setCandidates(response.data.candidates || []);
            } catch (err) {
                console.error('failed to fetch results:', err);
                // if the backend isn't running or has no data, just show empty state
                setCandidates([]);
            } finally {
                setLoading(false);
            }
        };

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
    // this avoids making a new API call every time the user types a letter
    const filteredCandidates = candidates.filter((candidate) => {
        // filter 1: search matching on name or skills array
        const searchLower = searchQuery.toLowerCase();
        const matchesSearch =
            candidate.name.toLowerCase().includes(searchLower) ||
            candidate.matched_skills.some(skill => skill.toLowerCase().includes(searchLower));

        // filter 2: the flagged toggle
        const matchesFlagged = showFlaggedOnly ? candidate.is_anomaly === true : true;

        // candidate must pass both filters to appear
        return matchesSearch && matchesFlagged;
    });

    // loading state while we wait for the backend response
    if (loading) {
        return (
            <div className="dashboard-page">
                <div className="upload-loading" style={{ marginTop: '80px' }}>
                    <div className="upload-spinner"></div>
                    <p className="upload-loading-text">Loading results...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="dashboard-page">
            {/* header with title and upload more button */}
            <div className="dashboard-header">
                <h1 className="dashboard-title">Dashboard</h1>
                <button
                    className="btn-primary"
                    onClick={() => navigate('/upload')}
                >
                    Upload More
                </button>
            </div>

            {candidates.length > 0 ? (
                <>
                    {/* stats bar at the top - three boxes */}
                    <div className="stats-bar">
                        <div className="stat-box">
                            <span className="stat-icon">📄</span>
                            <div className="stat-value">{totalResumes}</div>
                            <div className="stat-label">Total Resumes</div>
                        </div>
                        <div className="stat-box">
                            <span className="stat-icon">🎯</span>
                            <div className="stat-value">{avgScore}</div>
                            <div className="stat-label">Average Score</div>
                        </div>
                        <div className="stat-box">
                            <span className="stat-icon">🏆</span>
                            <div className="stat-value">{topCandidate}</div>
                            <div className="stat-label">Top Candidate</div>
                        </div>
                    </div>

                    {/* new search and filter bar right above the table */}
                    <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', alignItems: 'center', flexWrap: 'wrap' }}>
                        <input
                            type="text"
                            placeholder="Search by name or skill..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            style={{
                                flex: 1, minWidth: '250px', padding: '12px 16px',
                                border: '1px solid #ddd', borderRadius: '8px',
                                fontSize: '0.95rem'
                            }}
                        />
                        <button
                            onClick={() => setShowFlaggedOnly(!showFlaggedOnly)}
                            style={{
                                padding: '12px 20px', borderRadius: '8px',
                                border: '1px solid', fontWeight: 600, cursor: 'pointer',
                                transition: 'all 0.2s',
                                // style it amber/red if active, subtle grey if inactive
                                backgroundColor: showFlaggedOnly ? '#fef3c7' : '#f8f9fa',
                                borderColor: showFlaggedOnly ? '#d97706' : '#ddd',
                                color: showFlaggedOnly ? '#92400e' : '#555'
                            }}
                        >
                            {showFlaggedOnly ? '✓ Showing Flagged Only' : 'Show Flagged Only'}
                        </button>
                    </div>

                    {/* determine whether to show the table or a generic 'no match' message */}
                    {filteredCandidates.length > 0 ? (
                        <CandidateTable candidates={filteredCandidates} />
                    ) : (
                        <div style={{ textAlign: 'center', padding: '40px', backgroundColor: '#fff', borderRadius: '12px', border: '1px solid #eaeaea' }}>
                            <p style={{ color: '#666', fontSize: '1.05rem', margin: 0 }}>
                                No candidates match your filters. Try adjusting your search.
                            </p>
                        </div>
                    )}
                </>
            ) : (
                // empty state - no results yet
                <div className="dashboard-empty">
                    <span className="dashboard-empty-icon">📭</span>
                    <h2 className="dashboard-empty-title">No Results Yet</h2>
                    <p className="dashboard-empty-text">
                        Upload a ZIP file of resumes to see candidate rankings here.
                    </p>
                    <button
                        className="btn-primary"
                        onClick={() => navigate('/upload')}
                    >
                        Upload Resumes
                    </button>
                </div>
            )}
        </div>
    );
}

export default Dashboard;
