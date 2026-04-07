// App.jsx - main app component that sets up routing
// we have three pages: landing, upload, and dashboard

import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import LandingPage from './pages/LandingPage';
import UploadPage from './pages/UploadPage';
import Dashboard from './pages/Dashboard';

function App() {
    return (
        <Router>
            {/* navbar shows on every page */}
            <Navbar />
            <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/upload" element={<UploadPage />} />
                <Route path="/dashboard" element={<Dashboard />} />
            </Routes>
        </Router>
    );
}

export default App;
