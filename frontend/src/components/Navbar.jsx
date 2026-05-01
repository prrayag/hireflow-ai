// Navbar.jsx — HireFlow AI global navbar with dark/light toggle
import { Link, useNavigate } from 'react-router-dom';
import { useTheme } from '../hooks/useTheme';
import '../styles/landing.css';

function Navbar() {
    const navigate = useNavigate();
    const { theme, toggleTheme } = useTheme();
    const isDark = theme === 'dark';

    return (
        <nav className="navbar">
            <Link to="/" className="navbar-logo"
                style={{ fontFamily: 'var(--sans)', fontSize: '1.2rem', fontWeight: 800,
                         letterSpacing: '-0.04em', display: 'flex', alignItems: 'center',
                         gap: '10px', textDecoration: 'none', color: 'var(--ink)' }}>
                <svg width="26" height="18" viewBox="0 0 26 18" fill="none"
                     style={{ flexShrink: 0, color: 'var(--ink)' }}>
                    {/* Row 1 */}
                    <rect x="0"  y="0"    width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="10" y="0"    width="6" height="3" rx="1" fill="currentColor"/>
                    {/* Row 2 */}
                    <rect x="0"  y="7.5"  width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="10" y="7.5"  width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="20" y="7.5"  width="6" height="3" rx="1" fill="currentColor"/>
                    {/* Row 3 */}
                    <rect x="0"  y="15"   width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="10" y="15"   width="6" height="3" rx="1" fill="currentColor"/>
                </svg>
                hireflow
            </Link>

            <div className="navbar-links">
                <Link to="/dashboard" className="navbar-link">Dashboard</Link>
                <Link to="/analytics" className="navbar-link navbar-link-accent">Analytics ✦</Link>
            </div>

            <div className="navbar-buttons">
                {/* ── Theme toggle ── */}
                <button
                    className="theme-toggle"
                    onClick={toggleTheme}
                    aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                    title={isDark ? 'Light mode' : 'Dark mode'}
                >
                    <span className="theme-toggle-track">
                        <span className="theme-toggle-thumb">
                            {/* Sun icon (light) */}
                            {!isDark && (
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                                    <circle cx="12" cy="12" r="4"/>
                                    <line x1="12" y1="2"  x2="12" y2="5"/>
                                    <line x1="12" y1="19" x2="12" y2="22"/>
                                    <line x1="2"  y1="12" x2="5"  y2="12"/>
                                    <line x1="19" y1="12" x2="22" y2="12"/>
                                    <line x1="4.22" y1="4.22"  x2="6.34" y2="6.34"/>
                                    <line x1="17.66" y1="17.66" x2="19.78" y2="19.78"/>
                                    <line x1="4.22" y1="19.78" x2="6.34" y2="17.66"/>
                                    <line x1="17.66" y1="6.34" x2="19.78" y2="4.22"/>
                                </svg>
                            )}
                            {/* Moon icon (dark) */}
                            {isDark && (
                                <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                                </svg>
                            )}
                        </span>
                    </span>
                </button>


                <button className="btn-nav-primary" onClick={() => navigate('/upload')}>
                    Get started
                </button>
            </div>
        </nav>
    );
}

export default Navbar;
