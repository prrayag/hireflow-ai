<<<<<<< HEAD
// Navbar.jsx - minimal white navbar inspired by handhold.io
// clean, lightweight, no heavy background - just logo + 2 actions
=======
// Navbar.jsx - the navigation bar that shows on every page
// charcoal background with the HireFlow AI logo and login/signup buttons
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02

import { Link, useNavigate } from 'react-router-dom';
import '../styles/landing.css';

function Navbar() {
    const navigate = useNavigate();

    return (
        <nav className="navbar">
<<<<<<< HEAD
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
                <button className="btn-ghost" onClick={() => navigate('/upload')}>Log In</button>
                <button className="btn-nav-primary" onClick={() => navigate('/upload')}>
                    Get started
=======
            <Link to="/" className="navbar-logo">
                HireFlow AI <span>•</span>
            </Link>
            <div className="navbar-buttons">
                <button className="btn-ghost">Log In</button>
                <button
                    className="btn-nav-primary"
                    onClick={() => navigate('/upload')}
                >
                    Sign Up
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                </button>
            </div>
        </nav>
    );
}

export default Navbar;
