// Navbar.jsx - the navigation bar that shows on every page
// charcoal background with the HireFlow AI logo and login/signup buttons

import { Link, useNavigate } from 'react-router-dom';
import '../styles/landing.css';

function Navbar() {
    const navigate = useNavigate();

    return (
        <nav className="navbar">
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
                </button>
            </div>
        </nav>
    );
}

export default Navbar;
