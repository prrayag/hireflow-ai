// Navbar.jsx — HireFlow AI clean navbar (light mode, no toggle)
import { Link, useNavigate } from 'react-router-dom';
import '../styles/landing.css';

function Navbar() {
    const navigate = useNavigate();

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

            <div className="navbar-buttons">
                <button className="btn-nav-primary" onClick={() => navigate('/dashboard')}>
                    Get started
                </button>
            </div>
        </nav>
    );
}

export default Navbar;
