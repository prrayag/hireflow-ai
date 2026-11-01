// Navbar.jsx — HireFlow AI clean navbar (light mode, no toggle)
import { Link, useNavigate, useLocation } from 'react-router-dom';
import '../styles/landing.css';

function Navbar() {
    const navigate = useNavigate();
    const location = useLocation();
    const queryParams = new URLSearchParams(location.search);
    const currentTab = queryParams.get('tab');
    const isOnDashboard = location.pathname === '/dashboard';

    return (
        <nav className="navbar" style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center' }}>
            {/* Left: Logo */}
            <Link to="/" className="navbar-logo"
                style={{ fontFamily: 'var(--sans)', fontSize: '1.2rem', fontWeight: 800,
                         letterSpacing: '-0.04em', display: 'flex', alignItems: 'center',
                         gap: '10px', textDecoration: 'none', color: 'var(--ink)' }}>
                <svg width="26" height="18" viewBox="0 0 26 18" fill="none"
                     style={{ flexShrink: 0, color: 'var(--ink)' }}>
                    <rect x="0"  y="0"    width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="10" y="0"    width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="0"  y="7.5"  width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="10" y="7.5"  width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="20" y="7.5"  width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="0"  y="15"   width="6" height="3" rx="1" fill="currentColor"/>
                    <rect x="10" y="15"   width="6" height="3" rx="1" fill="currentColor"/>
                </svg>
                hireflow
            </Link>

            {/* Center: Nav Buttons */}
            <div style={{
                display: 'flex', alignItems: 'center', gap: '4px',
                background: '#f3f4f6', borderRadius: '10px', padding: '4px'
            }}>
                <button 
                    onClick={() => navigate('/dashboard')}
                    style={{
                        padding: '8px 22px', borderRadius: '8px', border: 'none',
                        background: (isOnDashboard && currentTab !== 'analytics') ? 'var(--ink)' : 'transparent',
                        color: (isOnDashboard && currentTab !== 'analytics') ? '#fff' : 'var(--ink)',
                        fontWeight: 600, fontSize: '0.88rem', cursor: 'pointer',
                        fontFamily: 'inherit', transition: 'all 0.25s ease'
                    }}
                >
                    Dashboard
                </button>
                <button 
                    onClick={() => navigate('/dashboard?tab=analytics')}
                    style={{
                        padding: '8px 22px', borderRadius: '8px', border: 'none',
                        background: currentTab === 'analytics' ? 'var(--ink)' : 'transparent',
                        color: currentTab === 'analytics' ? '#fff' : 'var(--ink)',
                        fontWeight: 600, fontSize: '0.88rem', cursor: 'pointer',
                        fontFamily: 'inherit', transition: 'all 0.25s ease'
                    }}
                >
                    Analytics
                </button>
            </div>

            {/* Right: empty spacer for symmetry */}
            <div />
        </nav>
    );
}

export default Navbar;
