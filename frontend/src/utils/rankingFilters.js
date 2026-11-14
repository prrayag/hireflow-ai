export function filterRankings(rankings, { query = '', minScore = '', minExperience = '', skill = '' } = {}) {
    const needle = query.trim().toLowerCase();
    return rankings.filter(candidate => {
        const skills = candidate.skills || [];
        const text = [candidate.name, candidate.email, ...skills].filter(Boolean).join(' ').toLowerCase();
        return (!needle || text.includes(needle))
            && (minScore === '' || Number(candidate.ai_score) >= Number(minScore))
            && (minExperience === '' || Number(candidate.experience) >= Number(minExperience))
            && (!skill || skills.includes(skill));
    });
}
