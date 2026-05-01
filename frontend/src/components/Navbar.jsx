// Navbar.jsx - clean navbar with dark/light mode toggle
// logo + theme toggle + 2 action buttons

import { Link, useNavigate } from 'react-router-dom';
import { useTheme } from '../hooks/useTheme';
import '../styles/landing.css';

function Navbar() {
    const navigate = useNavigate();
    const { theme, toggleTheme } = useTheme();

    return (
        <nav className="navbar">
            <Link to="/" className="navbar-logo" style={{ fontFamily: 'var(--serif)', fontSize: '1.75rem', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '10px', textDecoration: 'none', color: 'var(--ink)' }}>
                <svg width="26" height="18" viewBox="0 0 26 18" fill="none" style={{ flexShrink: 0, color: 'var(--ink)' }}>
                    {/* Row 1 */}
                    <rect x="0" y="0" width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="10" y="0" width="6" height="3" rx="1" fill="currentColor"/>
                    {/* Row 2 */}
                    <rect x="0" y="7.5" width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="10" y="7.5" width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="20" y="7.5" width="6" height="3" rx="1" fill="currentColor"/>
                    {/* Row 3 */}
                    <rect x="0" y="15" width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="10" y="15" width="6" height="3" rx="1" fill="currentColor"/>
                </svg>
                hireflow
            </Link>
            <div className="navbar-buttons">
                {/* Theme toggle */}
                <button
                    className="theme-toggle-btn"
                    onClick={toggleTheme}
                    title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                    aria-label="Toggle theme"
                >
                    {theme === 'dark' ? (
                        /* Sun icon */
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="5"/>
                            <line x1="12" y1="1" x2="12" y2="3"/>
                            <line x1="12" y1="21" x2="12" y2="23"/>
                            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                            <line x1="1" y1="12" x2="3" y2="12"/>
                            <line x1="21" y1="12" x2="23" y2="12"/>
                            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                        </svg>
                    ) : (
                        /* Moon icon */
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                        </svg>
                    )}
                </button>
                <button className="btn-ghost" onClick={() => navigate('/upload')}>Log In</button>
                <button className="btn-nav-primary" onClick={() => navigate('/upload')}>
                    Get started
                </button>
            </div>
        </nav>
    );
}

export default Navbar;
