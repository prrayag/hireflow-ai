// FeatureCard.jsx - reusable card component for the features section
// takes an icon, title, and description as props

function FeatureCard({ icon, title, description }) {
    return (
        <div className="feature-card">
            <span className="feature-icon">{icon}</span>
            <h3 className="feature-title">{title}</h3>
            <p className="feature-desc">{description}</p>
        </div>
    );
}

export default FeatureCard;
