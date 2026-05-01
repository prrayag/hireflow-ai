// App.jsx - main app component with routing + global theme context
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import AnimatedBackground from './components/AnimatedBackground';
import LandingPage from './pages/LandingPage';
import UploadPage from './pages/UploadPage';
import Dashboard from './pages/Dashboard';
import AnalyticsPage from './pages/AnalyticsPage';
import { ThemeContext, useThemeProvider } from './hooks/useTheme';

function App() {
    const themeValue = useThemeProvider();

    return (
        <ThemeContext.Provider value={themeValue}>
            <Router>
                {/* navbar + background show on every page */}
                <Navbar />
                <AnimatedBackground />
                <Routes>
                    <Route path="/"          element={<LandingPage />} />
                    <Route path="/upload"    element={<UploadPage />} />
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/analytics" element={<AnalyticsPage />} />
                </Routes>
            </Router>
        </ThemeContext.Provider>
    );
}

export default App;
