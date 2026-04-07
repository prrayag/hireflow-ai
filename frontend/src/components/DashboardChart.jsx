// components/DashboardChart.jsx
import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const DashboardChart = ({ candidates }) => {
    // Take top 10 candidates for the chart
    const data = candidates.slice(0, 10).map(c => ({
        name: c.name.split(' ')[0], // Use first name for compactness
        score: c.score
    }));

    if (data.length === 0) return null;

    return (
        <div style={{ background: 'var(--white)', padding: '24px', borderRadius: '12px', boxShadow: 'var(--shadow)', marginBottom: '24px' }}>
            <h3 style={{ fontFamily: '"Sora", sans-serif', fontSize: '1.2rem', marginBottom: '16px', color: 'var(--charcoal)' }}>Top Candidate Scores</h3>
            <div style={{ width: '100%', height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E8EAD8" />
                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#888' }} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#888' }} domain={[0, 100]} />
                        <Tooltip 
                            contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: 'var(--shadow-hover)' }}
                            cursor={{ fill: 'rgba(143, 168, 150, 0.1)' }}
                        />
                        <Bar dataKey="score" fill="var(--orange)" radius={[4, 4, 0, 0]} barSize={40} />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default DashboardChart;
