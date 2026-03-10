// LandingPage.jsx - the main landing page with hero section and features
// this is what visitors see first when they open the app

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import FeatureCard from '../components/FeatureCard';
import { API_BASE_URL } from '../config';
import '../styles/landing.css';

function LandingPage() {
    const navigate = useNavigate();

    // the three features we want to highlight on the landing page
    const features = [
        {
            icon: '📄',
            title: 'Multimodal Resume Parsing',
            description:
                'Upload PDFs, DOCX files, or ZIP archives. Our pipeline extracts and structures every piece of candidate data automatically.',
        },
        {
            icon: '🎯',
            title: 'Smart Candidate Scoring',
            description:
                'Each resume is scored against a keyword model trained on real job market data. No more manual shortlisting.',
        },
        {
            icon: '📊',
            title: 'Anomaly Detection',
            description:
                'We flag resumes with keyword stuffing and suspicious patterns so your HR team only sees genuine candidates.',
        },
    ];

    // state for real pipeline stats replacing hardcoded fake data
    const [stats, setStats] = useState({ total: '—', avgScore: '—', anomalies: '—' });
    const [loadingStats, setLoadingStats] = useState(true);

    // fetch the latest batch results from the API when component mounts
    useEffect(() => {
        const fetchStats = async () => {
            try {
                const response = await axios.get(`${API_BASE_URL}/results`);
                const candidates = response.data.candidates || [];

                if (candidates.length > 0) {
                    const total = candidates.length;
                    const avgScore = (candidates.reduce((sum, c) => sum + c.score, 0) / total).toFixed(1);
                    const anomalies = candidates.filter(c => c.is_anomaly).length;

                    setStats({ total, avgScore, anomalies });
                }
            } catch (err) {
                console.error('Failed to fetch stats for landing page:', err);
            } finally {
                setLoadingStats(false);
            }
        };

        fetchStats();
    }, []);

    return (
        <div className="landing-page">
            {/* hero section - split layout with text on left and card on right */}
            <section className="hero">
                <div className="hero-left">
                    <span className="hero-badge">AI-Powered Recruitment Analytics</span>
                    <h1 className="hero-heading">
                        Find the right talent, faster.
                    </h1>
                    <p className="hero-subtext">
                        HireFlow AI is a Big Data analytics pipeline built for modern HR teams.
                        Upload resumes, score candidates, and make data-driven hiring decisions
                        — all in one place.
                    </p>
                    <div className="hero-buttons">
                        <button
                            className="btn-primary"
                            onClick={() => navigate('/upload')}
                        >
                            Get Started →
                        </button>
                        <button
                            className="btn-secondary"
                            onClick={() => navigate('/dashboard')}
                        >
                            View Demo
                        </button>
                    </div>
                </div>

                {/* floating preview card on the right side */}
                <div className="hero-right">
                    <div className="hero-preview-card">
                        <div className="preview-card-header">Live Pipeline Stats</div>
                        {/* using real data fetched from the backend so marketing site matches reality */}
                        <div className="preview-stat">
                            <span className="preview-stat-label">Candidates Ranked</span>
                            <span className="preview-stat-value highlight">
                                {loadingStats ? 'Loading...' : stats.total}
                            </span>
                        </div>
                        <div className="preview-stat">
                            <span className="preview-stat-label">Avg. Score</span>
                            <span className="preview-stat-value">
                                {loadingStats ? 'Loading...' : stats.avgScore}
                            </span>
                        </div>
                        <div className="preview-stat">
                            <span className="preview-stat-label">Anomalies Detected</span>
                            <span className="preview-stat-value">
                                {loadingStats ? 'Loading...' : stats.anomalies}
                            </span>
                        </div>
                    </div>
                    <p style={{ textAlign: 'center', color: 'var(--sage)', fontSize: '0.85rem', marginTop: '12px' }}>
                        Live data from last processed batch.
                    </p>
                </div>
            </section>

            {/* features section - three cards in a row */}
            <section className="features-section">
                <h2 className="features-section-title">How It Works</h2>
                <p className="features-section-subtitle">
                    From upload to insight — our pipeline handles it all.
                </p>
                <div className="features-grid">
                    {features.map((feature, index) => (
                        <FeatureCard
                            key={index}
                            icon={feature.icon}
                            title={feature.title}
                            description={feature.description}
                        />
                    ))}
                </div>
            </section>

            {/* footer */}
            <footer className="footer">
                <p>HireFlow AI © 2025 — Built for HR teams that move fast</p>
            </footer>
        </div>
    );
}

export default LandingPage;
