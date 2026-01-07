import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';

const COLORS = {
    'SPY': '#FFFFFF', // White for Market
    'XLC': '#E91E63', // Pink
    'XLY': '#9C27B0', // Purple
    'XLP': '#673AB7', // Deep Purple
    'XLE': '#2196F3', // Blue
    'XLF': '#00BCD4', // Cyan
    'XLV': '#009688', // Teal
    'XLI': '#4CAF50', // Green
    'XLB': '#8BC34A', // Light Green
    'XLRE': '#FFC107', // Amber
    'XLK': '#FF9800', // Orange
    'XLU': '#FF5722'  // Deep Orange
};

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <div style={{ backgroundColor: '#1e293b', border: '1px solid #334155', padding: '10px', color: '#fff' }}>
                <p style={{ margin: '0 0 5px 0', fontWeight: 'bold' }}>{label}</p>
                {payload.sort((a, b) => b.value - a.value).map((entry, index) => (
                    <div key={index} style={{ color: entry.stroke, fontSize: '12px', marginBottom: '2px' }}>
                        {entry.name}: {(entry.value * 100).toFixed(2)}%
                    </div>
                ))}
            </div>
        );
    }
    return null;
};

const SectorTrends = () => {
    const [historyData, setHistoryData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [hiddenSeries, setHiddenSeries] = useState(new Set());

    const toggleSeries = (e) => {
        const { value } = e; // Recharts passes the dataKey as value
        const newHidden = new Set(hiddenSeries);
        if (newHidden.has(value)) {
            newHidden.delete(value);
        } else {
            newHidden.add(value);
        }
        setHiddenSeries(newHidden);
    };

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await fetch('/api/v1/performance/history');
                if (res.ok) {
                    const json = await res.json();
                    setHistoryData(json);
                }
            } catch (err) {
                console.error("Error fetching sector history:", err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return <div style={{ color: '#888', padding: '20px' }}>Loading historical data...</div>;
    if (!historyData) return <div style={{ color: '#888', padding: '20px' }}>No historical data available.</div>;

    // Transform Data for Recharts
    // Recharts needs array of objects: [{date: '...', SPY: 0.1, XLE: 0.2}, ...]
    const transformData = (seriesData) => {
        return historyData.dates.map((date, index) => {
            const row = { date };
            Object.keys(seriesData).forEach(ticker => {
                const val = seriesData[ticker][index];
                if (val !== null && val !== undefined) {
                    row[ticker] = val; // Keep as decimal
                }
            });
            return row;
        });
    };

    const data1Y = transformData(historyData.normalized_1y);
    const dataRolling = transformData(historyData.rolling_12m);

    const renderChart = (title, data) => (
        <div style={{ marginBottom: '60px' }}>
            <h3 style={{ color: '#e0e0e0', fontSize: '16px', marginBottom: '20px', borderLeft: '4px solid #4CAF50', paddingLeft: '10px' }}>
                {title}
            </h3>
            <div style={{ width: '100%', height: '500px' }}>
                <ResponsiveContainer>
                    <LineChart data={data} margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                        <XAxis
                            dataKey="date"
                            stroke="#888"
                            fontSize={12}
                            tickFormatter={(str) => str.slice(5)} // Show MM-DD
                            minTickGap={30}
                        />
                        <YAxis
                            stroke="#888"
                            fontSize={12}
                            tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                        />
                        <Tooltip content={<CustomTooltip />} />
                        <Legend
                            wrapperStyle={{ paddingTop: '20px', cursor: 'pointer' }}
                            onClick={toggleSeries}
                            formatter={(value, entry) => {
                                const isHidden = hiddenSeries.has(value);
                                return <span style={{ color: isHidden ? '#666' : '#e0e0e0', textDecoration: isHidden ? 'line-through' : 'none' }}>{value}</span>;
                            }}
                        />

                        {Object.keys(COLORS).map(ticker => {
                            return (
                                <Line
                                    key={ticker}
                                    type="monotone"
                                    dataKey={ticker}
                                    stroke={COLORS[ticker]}
                                    strokeWidth={ticker === 'SPY' ? 3 : 1.5}
                                    dot={false}
                                    activeDot={{ r: 6 }}
                                    hide={hiddenSeries.has(ticker)}
                                />
                            );
                        })}
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );

    return (
        <div style={{ padding: '20px' }}>
            {renderChart("1-Year Cumulative Performance (Normalized)", data1Y)}
            {renderChart("12-Month Rolling Return", dataRolling)}
        </div>
    );
};

export default SectorTrends;
