// Dashboard.jsx - shows the results of processed resumes
// fetches data from Flask backend on load and displays stats + candidate table

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import CandidateTable from '../components/CandidateTable';
import '../styles/dashboard.css';

function Dashboard() {
    const navigate = useNavigate();

    // state for the candidates data from the backend
    const [candidates, setCandidates] = useState([]);
    const [loading, setLoading] = useState(true);

    // fetch results from Flask when the component mounts
    useEffect(() => {
        const fetchResults = async () => {
            try {
                const response = await axios.get('http://localhost:5001/results');
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

                    {/* candidate results table */}
                    <CandidateTable candidates={candidates} />
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
