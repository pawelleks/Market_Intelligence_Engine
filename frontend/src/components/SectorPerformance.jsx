import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid, LabelList } from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        const data = payload[0].payload;
        return (
            <div style={{ backgroundColor: '#1e293b', border: '1px solid #334155', padding: '10px', color: '#fff' }}>
                <p style={{ margin: '0 0 5px 0', fontWeight: 'bold', fontSize: '14px' }}>{data.ticker}</p>
                <p style={{ margin: '0 0 5px 0', fontSize: '12px', color: '#9ec4ff' }}>{data.name}</p>
                <p style={{ margin: '0', fontSize: '13px', color: '#fff' }}>
                    Return: {payload[0].value.toFixed(2)}%
                </p>
            </div>
        );
    }
    return null;
};

const SectorPerformance = () => {
    const [data, setData] = useState([]);
    const [asOfDate, setAsOfDate] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await fetch('/api/v1/performance/snapshot');
                if (res.ok) {
                    const json = await res.json();
                    const sectors = json.filter(d => d.group === 'Sector ETFs');
                    setData(sectors);
                    if (sectors.length > 0) {
                        setAsOfDate(sectors[0].asof_date);
                    }
                }
            } catch (err) {
                console.error("Error fetching sector performance:", err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return <div style={{ color: '#888', padding: '20px' }}>Loading sector data...</div>;
    if (data.length === 0) return <div style={{ color: '#888', padding: '20px' }}>No sector data available.</div>;

    const tickerNames = {
        'XLC': 'Communication Services',
        'XLY': 'Consumer Cyclical',
        'XLP': 'Consumer Defensive',
        'XLE': 'Energy',
        'XLF': 'Financial',
        'XLV': 'Healthcare',
        'XLI': 'Industrials',
        'XLB': 'Basic Materials',
        'XLRE': 'Real Estate',
        'XLK': 'Technology',
        'XLU': 'Utilities'
    };

    const metrics = [
        { key: 'ret_1d', label: '1 DAY PERFORMANCE' },
        { key: 'ret_1w', label: '1 WEEK PERFORMANCE' },
        { key: 'ret_1m', label: '1 MONTH PERFORMANCE' },
        { key: 'ret_3m', label: '3 MONTH PERFORMANCE' },
        { key: 'ret_6m', label: 'HALF YEAR PERFORMANCE' },
        { key: 'ret_1y', label: '1 YEAR PERFORMANCE' },
        { key: 'ret_ytd', label: 'YEAR TO DATE PERFORMANCE' }
    ];

    const renderChart = (metric) => {
        const chartData = data.map(item => ({
            name: tickerNames[item.ticker] || item.ticker,
            value: (item[metric.key] || 0) * 100,
            ticker: item.ticker
        })).sort((a, b) => b.value - a.value);

        return (
            <div key={metric.key} style={{ marginBottom: '60px' }}>
                <h3 style={{
                    color: '#e0e0e0',
                    fontSize: '14px',
                    fontWeight: '600',
                    textAlign: 'center',
                    textTransform: 'uppercase',
                    marginBottom: '20px'
                }}>
                    {metric.label}
                </h3>
                <div style={{ width: '100%', height: '350px' }}>
                    <ResponsiveContainer>
                        <BarChart
                            layout="vertical"
                            data={chartData}
                            margin={{ top: 5, right: 60, left: 140, bottom: 5 }}
                        >
                            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#333" />
                            <XAxis type="number" hide />
                            <YAxis
                                type="category"
                                dataKey="name"
                                stroke="#ccc"
                                fontSize={11}
                                tickLine={false}
                                width={150}
                            />
                            <Tooltip
                                content={<CustomTooltip />}
                                cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                            />
                            <Bar dataKey="value" barSize={24} radius={[0, 4, 4, 0]}>
                                {chartData.map((entry, index) => (
                                    <Cell
                                        key={`cell-${index}`}
                                        fill={entry.value >= 0 ? '#4caf50' : '#ef5350'}
                                    />
                                ))}
                                <LabelList
                                    dataKey="value"
                                    position="right"
                                    formatter={(val) => `${val > 0 ? '+' : ''}${val.toFixed(2)}%`}
                                    style={{ fill: '#e0e0e0', fontSize: '11px', fontWeight: 'bold' }}
                                />
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>
        );
    };

    return (
        <div style={{ maxWidth: '900px', margin: '0 auto', padding: '20px' }}>
            {asOfDate && (
                <div style={{ textAlign: 'center', marginBottom: '30px', color: '#9ec4ff', fontSize: '13px' }}>
                    Data as of: <span style={{ fontWeight: 'bold', color: '#fff' }}>{asOfDate}</span>
                </div>
            )}
            {metrics.map(m => renderChart(m))}
        </div>
    );
};

export default SectorPerformance;
