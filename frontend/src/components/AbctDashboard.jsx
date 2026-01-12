
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
    ResponsiveContainer,
    BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ReferenceLine, Cell,
    ComposedChart, Line, AreaChart, Area, CartesianGrid, Brush
} from 'recharts';
import AbctSignalHistory from './AbctSignalHistory';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const AbctDashboard = () => {
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // State for interactive legend (toggle series visibility)
    const [hiddenSeries, setHiddenSeries] = useState({});

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                // Use the new V1 endpoint
                const res = await axios.get(`${API_BASE_URL}/v1/analysis/abct`);
                const { dates, indicators } = res.data;

                if (!dates || !indicators) {
                    setData([]);
                    setLoading(false);
                    return;
                }

                const transformed = dates.map((date, i) => {
                    const row = { date };
                    Object.keys(indicators).forEach(key => {
                        row[key] = indicators[key][i];
                    });
                    return row;
                });

                setData(transformed);
            } catch (err) {
                console.error("ABCT Data Fetch Error:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    // --- Helpers ---
    const formatYear = ((tick) => {
        if (!tick) return '';
        return tick.substring(0, 4);
    });

    // Interactive Legend Handler
    const handleLegendClick = (dataKey) => {
        setHiddenSeries(prev => ({
            ...prev,
            [dataKey]: !prev[dataKey]
        }));
    };

    const CustomTooltip = ({ active, payload, label }) => {
        if (active && payload && payload.length) {
            return (
                <div style={{ backgroundColor: '#111827', border: '1px solid #374151', padding: '12px', borderRadius: '4px', fontSize: '12px' }}>
                    <p style={{ fontWeight: 'bold', color: '#d1d5db', marginBottom: '8px' }}>{label}</p>
                    {payload.map((entry, idx) => (
                        <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: entry.color }} />
                            <span style={{ color: '#9ca3af' }}>{entry.name}:</span>
                            <span style={{ color: '#e5e7eb', fontFamily: 'monospace' }}>
                                {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}
                                {entry.name.includes('%') ? '%' : ''}
                            </span>
                        </div>
                    ))}
                </div>
            );
        }
        return null;
    };

    // --- Status Badge ---
    const AbctStatusBadge = ({ data }) => {
        if (!data || data.length === 0) return null;
        const latest = data[data.length - 1];
        const gap = (latest.m2_yoy_rolling_6m || 0) - (latest.savings_rate_rolling_6m || 0);

        let status = "🟢 BALANCED";
        let color = "#22c55e"; // Green
        let desc = "Credit expansion is aligned with real savings. Growth is sustainable.";

        if (gap > 2.0) {
            status = "🔴 WARNING: Distorted";
            color = "#ef4444"; // Red
            desc = "Credit expansion significantly exceeds savings. High risk of malinvestment.";
        } else if (gap > 0.5) {
            status = "🟠 CAUTION: Mild Distortion";
            color = "#f97316"; // Orange
            desc = "Credit expansion starts to outpace savings. Watch for divergence.";
        }

        return (
            <div style={{ marginBottom: '32px', padding: '16px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', borderLeft: `4px solid ${color}` }}>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 'bold', color: color }}>{status}</h3>
                <p style={{ margin: '4px 0 0 0', color: '#9ca3af', fontSize: '14px' }}>
                    {desc}
                </p>
            </div>
        );
    };

    if (loading) return <div style={{ padding: '32px', textAlign: 'center', color: '#9ca3af' }}>Loading ABCT Model...</div>;
    if (error) return <div style={{ padding: '32px', textAlign: 'center', color: '#ef4444' }}>Error: {error}</div>;

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#0e1525', color: '#d7e3f3', padding: '24px' }}>
            <header style={{ marginBottom: '32px', borderBottom: '1px solid #1f2937', paddingBottom: '16px' }}>
                <h1 style={{ fontSize: '28px', fontWeight: 'bold', background: 'linear-gradient(to right, #fbbf24, #f59e0b)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', margin: 0 }}>
                    The Austrian Business Cycle (ABCT)
                </h1>
                <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '8px' }}>
                    Tracking the distortion of interest rates and the structure of production.
                </p>
            </header>

            <AbctStatusBadge data={data} />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '48px', maxWidth: '1280px', margin: '0 auto' }}>

                {/* SECTION 1: THE FUEL */}
                <section>
                    <div style={{ marginBottom: '16px' }}>
                        <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#34d399', margin: 0 }}>1. The Fuel (Real vs. Artificial Funding)</h2>
                        <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px', maxWidth: '800px' }}>
                            Healthy growth is funded by <span style={{ color: '#34d399' }}>Real Savings (Green)</span>.
                            Artificial booms are funded by <span style={{ color: '#f87171' }}>Credit Expansion (Red)</span>.
                        </p>
                        <div style={{ marginTop: '8px', fontSize: '13px', color: '#6b7280', fontStyle: 'italic', borderLeft: '2px solid #374151', paddingLeft: '8px' }}>
                            <strong>What to Watch:</strong> A widening gap where Money Supply spikes while Savings drop indicates an artificial boom.
                        </div>
                    </div>
                    <div style={{ height: '350px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '16px', border: '1px solid rgba(55, 65, 81, 0.5)' }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <ComposedChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 20 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />
                                <XAxis dataKey="date" tickFormatter={formatYear} stroke="#9CA3AF" minTickGap={30} />
                                <YAxis stroke="#9CA3AF" />
                                <Tooltip content={<CustomTooltip />} />
                                <Legend onClick={(e) => handleLegendClick(e.dataKey)} wrapperStyle={{ cursor: 'pointer' }} />

                                {/* Gap Visualization */}
                                <Area
                                    type="monotone"
                                    dataKey="credit_savings_gap"
                                    fill="#ef444430"
                                    stroke="none"
                                    name="Credit Expansion Gap"
                                />

                                {/* Raw Volatility (Thin, Transparent) */}
                                <Line type="monotone" dataKey="money_supply_growth" name="M2 Growth (Raw)" stroke="#F87171" strokeWidth={1} strokeOpacity={0.4} dot={false} hide={hiddenSeries['money_supply_growth']} />
                                <Line type="monotone" dataKey="savings_rate" name="Savings Rate (Raw)" stroke="#34D399" strokeWidth={1} strokeOpacity={0.4} dot={false} hide={hiddenSeries['savings_rate']} />

                                {/* Rolling Trend (Thick, Solid) */}
                                <Line type="monotone" dataKey="m2_yoy_rolling_6m" name="M2 Growth (6m Trend)" stroke="#F87171" strokeWidth={3} dot={false} hide={hiddenSeries['m2_yoy_rolling_6m']} />
                                <Line type="monotone" dataKey="savings_rate_rolling_6m" name="Savings Rate (6m Trend)" stroke="#34D399" strokeWidth={3} dot={false} hide={hiddenSeries['savings_rate_rolling_6m']} />

                                <Brush dataKey="date" height={30} stroke="#4B5563" tickFormatter={formatYear} />
                            </ComposedChart>
                        </ResponsiveContainer>
                    </div>
                </section>

                {/* SECTION 2: THE DISTORTION */}
                <section>
                    <div style={{ marginBottom: '16px' }}>
                        <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#60a5fa', margin: 0 }}>2. The Distortion (Malinvestment Monitor)</h2>
                        <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px', maxWidth: '800px' }}>
                            When rates are artificially low, capital flows into long-term projects (Capital Goods) that consumers don't actually want yet.
                        </p>
                        <div style={{ marginTop: '8px', fontSize: '13px', color: '#6b7280', fontStyle: 'italic', borderLeft: '2px solid #374151', paddingLeft: '8px' }}>
                            <strong>What to Watch:</strong> A rising trend means production is shifting away from consumption (Boom). A sharp crash indicates the liquidation of malinvestment (Bust).
                        </div>
                    </div>
                    <div style={{ height: '300px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '16px', border: '1px solid rgba(55, 65, 81, 0.5)' }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 20 }}>
                                <defs>
                                    <linearGradient id="colorRatio" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#60A5FA" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#60A5FA" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />
                                <XAxis dataKey="date" tickFormatter={formatYear} stroke="#9CA3AF" minTickGap={30} />
                                <YAxis stroke="#60A5FA" domain={['auto', 'auto']} />
                                <Tooltip content={<CustomTooltip />} />
                                <Legend />
                                <Area type="monotone" dataKey="malinvestment_ratio" name="Malinvestment Ratio (PPI Cap / CPI)" stroke="#60A5FA" fill="url(#colorRatio)" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </section>

                {/* SECTION 3: THE CYCLE SIGNAL */}
                <section>
                    <div style={{ marginBottom: '16px' }}>
                        <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#f472b6', margin: 0 }}>3. The Cycle Signal (Composite Score)</h2>
                        <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px' }}>
                            The aggregate pressure on the economy. High scores indicate an unstable boom.
                        </p>
                    </div>
                    <div style={{ height: '300px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '16px', border: '1px solid rgba(55, 65, 81, 0.5)' }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 20 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />
                                <XAxis dataKey="date" tickFormatter={formatYear} stroke="#9CA3AF" minTickGap={30} />
                                <YAxis stroke="#F472B6" />
                                <Tooltip content={<CustomTooltip />} />
                                <ReferenceLine y={0} stroke="#9CA3AF" />
                                <ReferenceLine y={2} stroke="#EF4444" strokeDasharray="3 3" label={{ value: 'Danger', fill: '#EF4444', position: 'insideTopLeft' }} />
                                <Legend />
                                <Bar dataKey="boom_score" name="Boom Intensity Score (Z-Score)" radius={[2, 2, 0, 0]}>
                                    {data.map((entry, index) => (
                                        <Cell
                                            key={`cell-${index}`}
                                            fill={entry.boom_score > 0 ? (entry.boom_score > 2 ? '#ef4444' : '#f472b6') : '#22c55e'}
                                            fillOpacity={entry.boom_score <= 0 ? 0.2 : 1}
                                            stroke={entry.boom_score <= 0 ? '#22c55e' : 'none'}
                                        />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </section>

                <AbctSignalHistory data={data} />

            </div>
        </div>
    );
};

export default AbctDashboard;
