// CandidateTable.jsx - displays the ranked candidates in a table
// scores get colored badges: green for 70+, orange for 40-69, red for below 40

import '../styles/dashboard.css';

function CandidateTable({ candidates }) {
    // this function figures out what color class to use for the score badge
    const getScoreClass = (score) => {
        if (score >= 70) return 'high';
        if (score >= 40) return 'medium';
        return 'low';
    };

    return (
        <div className="results-section">
            <div className="results-section-header">
                <h3 className="results-section-title">Candidate Rankings</h3>
                <span style={{ color: '#888', fontSize: '0.9rem' }}>
                    {candidates.length} candidate{candidates.length !== 1 ? 's' : ''}
                </span>
            </div>
            <table className="candidate-table">
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>Candidate Name</th>
                        <th>Score</th>
                        <th>Matched Skills</th>
                        <th>File Name</th>
                    </tr>
                </thead>
                <tbody>
                    {candidates.map((candidate) => (
                        <tr key={candidate.rank}>
                            <td>
                                <span className={`rank-badge ${candidate.rank <= 3 ? 'top-3' : ''}`}>
                                    {candidate.rank}
                                </span>
                            </td>
                            <td className="candidate-name">{candidate.name}</td>
                            <td>
                                <span className={`score-badge ${getScoreClass(candidate.score)}`}>
                                    {candidate.score}%
                                </span>
                            </td>
                            <td>
                                <div className="skills-list">
                                    {candidate.matched_skills.length > 0 ? (
                                        candidate.matched_skills.map((skill, index) => (
                                            <span className="skill-pill" key={index}>
                                                {skill}
                                            </span>
                                        ))
                                    ) : (
                                        <span style={{ color: '#999', fontSize: '0.85rem' }}>
                                            No matches
                                        </span>
                                    )}
                                </div>
                            </td>
                            <td className="file-name">{candidate.filename}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export default CandidateTable;
