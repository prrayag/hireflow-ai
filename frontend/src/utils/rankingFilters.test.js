import test from 'node:test';
import assert from 'node:assert/strict';
import { filterRankings } from './rankingFilters.js';

const rows = [
    { name: 'Asha', email: 'asha@example.com', skills: ['Python', 'AWS'], ai_score: 90, experience: 5 },
    { name: 'Ravi', skills: ['React'], ai_score: 40, experience: 2 },
    { name: 'Junior', skills: [], ai_score: 0, experience: 0 },
];
test('default filters retain every candidate, including zero scores', () => {
    assert.equal(filterRankings(rows).length, 3);
    assert.equal(filterRankings(Array.from({length: 150}, () => rows[0])).length, 150);
});
test('search ignores case and matches skills and email', () => {
    assert.equal(filterRankings(rows, { query: ' PYTHON ' })[0].name, 'Asha');
    assert.equal(filterRankings(rows, { query: '@example.com' }).length, 1);
});
test('filters combine and can produce an empty result', () => {
    assert.deepEqual(filterRankings(rows, { minScore: '80', minExperience: '3', skill: 'AWS' }), [rows[0]]);
    assert.equal(filterRankings(rows, { minScore: '80', skill: 'React' }).length, 0);
});
