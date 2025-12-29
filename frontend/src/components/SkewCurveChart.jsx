import React, { useState, useEffect, useMemo } from 'react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    ReferenceLine
} from 'recharts';

const SkewCurveChart = ({ ticker }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Track which expirations are visible
    const [visibleExpirations, setVisibleExpirations] = useState({});

    useEffect(() => {
        fetchCurve();
    }, [ticker]);

    const fetchCurve = async () => {
        setLoading(true);
        try {
            const response = await fetch(`/api/v1/analytics/skew/${ticker}/curve`);
            if (!response.ok) throw new Error('Failed to fetch curve data');
            const result = await response.json();
            setData(result);

            // Initialize visibility: Show first 5 expiries by default to avoid mess
            const initialVisibility = {};
            if (result && result.expirations) {
                Object.keys(result.expirations).sort().forEach((exp, idx) => {
                    initialVisibility[exp] = idx < 5;
                });
            }
            setVisibleExpirations(initialVisibility);
            setError(null);
        } catch (err) {
            console.error('Error fetching skew curve:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const toggleExpiration = (exp) => {
        setVisibleExpirations(prev => ({
            ...prev,
            [exp]: !prev[exp]
        }));
    };

    if (loading) return <div style={{ height: '384px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>Loading Volatility Smile...</div>;
    if (error) return <div style={{ padding: '16px', color: '#ef4444', backgroundColor: 'rgba(127, 29, 29, 0.2)', borderRadius: '8px' }}>Error: {error}</div>;
    if (!data || !data.expirations || Object.keys(data.expirations).length === 0) {
        return <div style={{ height: '384px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>No multi-expiry data available for {ticker}</div>;
    }

    // Colors for different expiries
    const colors = ['#f43f5e', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#f97316', '#a855f7', '#14b8a6'];

    // Custom Tooltip
    const CustomTooltip = ({ active, payload }) => {
        if (active && payload && payload.length) {
            return (
                <div style={{ backgroundColor: '#0f172a', border: '1px solid #334155', padding: '12px', borderRadius: '4px' }}>
                    <p style={{ color: '#cbd5e1', fontWeight: 'bold', marginBottom: '4px' }}>Strike: ${payload[0].payload.strike}</p>
                    {payload.map((p, idx) => (
                        <p key={idx} style={{ color: p.color, margin: 0, fontSize: '0.9rem' }}>
                            {p.name}: {(p.value * 100).toFixed(2)}%
                        </p>
                    ))}
                </div>
            );
        }
        return null;
    };

    const sortedExpirations = Object.keys(data.expirations).sort();

    return (
        <div style={{
            width: '100%',
            height: '850px',
            marginTop: '24px',
            backgroundColor: '#1e293b',
            padding: '24px',
            borderRadius: '12px',
            border: '1px solid #334155',
            boxSizing: 'border-box'
        }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                <div style={{ flex: 1 }}>
                    <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 'bold', color: '#f8fafc' }}>Volatility Smile (Multi-Expiry)</h3>
                    <p style={{ margin: '4px 0 12px 0', fontSize: '0.875rem', color: '#94a3b8' }}>Filter: ±15% from Spot. Showing only OTM options for smooth curves.</p>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b', lineHeight: '1.5', maxWidth: '800px' }}>
                        The <strong>Volatility Smile</strong> represents the Implied Volatility (IV) for options at different strike prices.
                        A "smile" or "smirk" occurs because out-of-the-money options (especially downside puts) typically command a higher premium,
                        reflecting the market's demand for tail-risk protection. Steeper curves on the left indicate increased fear of a sharp sell-off.
                    </p>
                </div>
                <div style={{ fontSize: '0.75rem', color: '#64748b', whiteSpace: 'nowrap', marginLeft: '20px' }}>
                    As of: {data.as_of}
                </div>
            </div>

            {/* Expiration Toggles */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '20px', padding: '12px', backgroundColor: '#0f172a', borderRadius: '8px', border: '1px solid #334155' }}>
                <span style={{ fontSize: '0.8rem', color: '#94a3b8', width: '100%', marginBottom: '4px' }}>Select Expirations:</span>
                {sortedExpirations.map((exp, idx) => (
                    <div
                        key={exp}
                        onClick={() => toggleExpiration(exp)}
                        style={{
                            padding: '4px 10px',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            backgroundColor: visibleExpirations[exp] ? '#334155' : 'transparent',
                            border: `1px solid ${colors[idx % colors.length]}`,
                            color: visibleExpirations[exp] ? '#fff' : colors[idx % colors.length],
                            transition: 'all 0.2s'
                        }}
                    >
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: colors[idx % colors.length] }} />
                        {exp}
                    </div>
                ))}
            </div>

            {/* Chart Area */}
            <div style={{ width: '100%', height: '580px' }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart margin={{ top: 10, right: 10, left: 10, bottom: 40 }}>
                        <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
                        <XAxis
                            type="number"
                            dataKey="strike"
                            domain={['dataMin', 'dataMax']}
                            stroke="#94a3b8"
                            tick={{ fontSize: 10 }}
                            tickCount={20}
                            label={{ value: 'Strike Price ($)', position: 'bottom', offset: 20, fill: '#94a3b8', fontSize: 12 }}
                            allowDecimals={false}
                        />
                        <YAxis
                            stroke="#94a3b8"
                            tick={{ fontSize: 10 }}
                            tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                            label={{ value: 'IV (%)', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 12 }}
                        />
                        <Tooltip content={<CustomTooltip />} />
                        <Legend verticalAlign="top" height={0} content={() => null} /> {/* Custom legend handles visibility */}

                        {/* Reference Line for Spot Price */}
                        {data.spot && (
                            <ReferenceLine
                                x={data.spot}
                                stroke="#fbbf24"
                                strokeDasharray="5 5"
                                label={{ position: 'top', value: `Spot: ${data.spot}`, fill: '#fbbf24', fontSize: 11, fontWeight: 'bold' }}
                            />
                        )}

                        {sortedExpirations.map((exp, idx) => (
                            visibleExpirations[exp] && (
                                <Line
                                    key={exp}
                                    name={exp}
                                    data={data.expirations[exp]}
                                    type="monotone"
                                    dataKey="iv"
                                    stroke={colors[idx % colors.length]}
                                    dot={{ r: 2, fill: colors[idx % colors.length], strokeWidth: 0 }}
                                    activeDot={{ r: 4 }}
                                    strokeWidth={2}
                                    connectNulls={true}
                                    isAnimationActive={false}
                                />
                            )
                        ))}
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default SkewCurveChart;
