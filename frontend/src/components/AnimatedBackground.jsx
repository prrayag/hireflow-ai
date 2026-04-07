// components/AnimatedBackground.jsx
import React from 'react';
import '../styles/animated-background.css';

const AnimatedBackground = () => {
    return (
        <div className="animated-bg-container">
            <div className="bg-shape shape-1"></div>
            <div className="bg-shape shape-2"></div>
            <div className="bg-shape shape-3"></div>
            <div className="bg-texture-overlay"></div>
        </div>
    );
};

export default AnimatedBackground;
