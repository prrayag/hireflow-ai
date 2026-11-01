// FeatureCard.jsx - reusable card component for the features section
// takes an icon, title, and description as props

function FeatureCard({ title, description, illustration }) {
    return (
        <div className="feature-block">
            <div className="feature-illustration-card">
                {illustration}
            </div>
            <h3 className="feature-title">{title}</h3>
            <p className="feature-desc">{description}</p>
        </div>
    );
}

export default FeatureCard;
