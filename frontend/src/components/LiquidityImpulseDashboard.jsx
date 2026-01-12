import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
    ResponsiveContainer,
    ComposedChart, AreaChart, Area, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ReferenceLine
} from 'recharts';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const LiquidityImpulseDashboard = () => {
    const [data, setData] = useState([]);
    const [latestReading, setLatestReading] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const res = await axios.get(`${API_BASE_URL}/v1/analysis/liquidity-impulse`);

                if (!res.data || !res.data.data) {
                    throw new Error("Invalid data format received from API");
                }

                setData(res.data.data);
                setLatestReading(res.data.latest_reading);
            } catch (err) {
                console.error("Liquidity Impulse Data Fetch Error:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    // Custom Tooltip
    const CustomTooltip = ({ active, payload, label }) => {
        if (active && payload && payload.length) {
            const dataPoint = payload[0].payload;
            return (
                <div style={{ backgroundColor: '#111827', border: '1px solid #374151', padding: '12px', borderRadius: '4px', fontSize: '12px' }}>
                    <p style={{ fontWeight: 'bold', color: '#d1d5db', marginBottom: '8px' }}>{label}</p>
                    {payload.map((entry, idx) => (
                        <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: entry.color }} />
                            <span style={{ color: '#9ca3af' }}>{entry.name}:</span>
                            <span style={{ color: '#e5e7eb', fontFamily: 'monospace' }}>
                                {entry.name.includes('Liquidity')
                                    ? `$${(entry.value / 1000).toFixed(2)}T`
                                    : `${entry.value?.toFixed(2)}%`
                                }
                            </span>
                        </div>
                    ))}
                </div>
            );
        }
        return null;
    };

    // Regime Banner
    const RegimeBanner = ({ latestReading }) => {
        if (!latestReading) return null;

        const impulse = latestReading.impulse ?? 0;
        const isExpanding = impulse > 0;

        const bgColor = isExpanding ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)';
        const borderColor = isExpanding ? '#22c55e' : '#ef4444';
        const textColor = isExpanding ? '#22c55e' : '#ef4444';
        const icon = isExpanding ? '🟢' : '🔴';
        const regime = isExpanding ? 'Liquidity Expansion - Risk On' : 'Liquidity Contraction - Risk Off';
        const message = isExpanding
            ? 'Central banks are expanding balance sheets. Positive for risk assets.'
            : 'Central banks are contracting balance sheets. Caution: liquidity drain in progress.';

        return (
            <div style={{
                marginBottom: '24px',
                padding: '20px',
                backgroundColor: bgColor,
                borderRadius: '8px',
                border: `2px solid ${borderColor}`,
                borderLeft: `6px solid ${borderColor}`
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                    <span style={{ fontSize: '24px' }}>{icon}</span>
                    <h2 style={{
                        margin: 0,
                        fontSize: '20px',
                        fontWeight: 'bold',
                        color: textColor
                    }}>
                        Current Regime: {regime}
                    </h2>
                </div>
                <p style={{
                    margin: 0,
                    color: '#d1d5db',
                    fontSize: '15px',
                    lineHeight: '1.5'
                }}>
                    {message}
                </p>
            </div>
        );
    };

    // Metric Cards
    const MetricCards = ({ latestReading }) => {
        if (!latestReading) return null;

        const totalLiquidity = latestReading.total_liquidity ?? 0;
        const impulse = latestReading.impulse ?? 0;
        const trend = latestReading.trend ?? "Unknown";

        const impulseColor = impulse >= 0 ? "#22c55e" : "#ef4444";

        return (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '32px' }}>
                {/* Global Liquidity Card */}
                <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '20px', border: '2px solid #06b6d4' }}>
                    <div style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '8px', fontWeight: '500' }}>Global Liquidity (G3)</div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#06b6d4', marginBottom: '8px' }}>
                        ${(totalLiquidity / 1000).toFixed(2)}T
                    </div>
                    <div style={{ fontSize: '13px', color: '#d1d5db' }}>
                        Fed + ECB + BoJ
                    </div>
                </div>

                {/* 3-Month Impulse Card */}
                <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '20px', border: `2px solid ${impulseColor}` }}>
                    <div style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '8px', fontWeight: '500' }}>3-Month Impulse</div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: impulseColor, marginBottom: '8px' }}>
                        {impulse >= 0 ? '+' : ''}{impulse.toFixed(2)}%
                    </div>
                    <div style={{ fontSize: '13px', color: '#d1d5db' }}>
                        Rate of Change
                    </div>
                </div>

                {/* Trend Card */}
                <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '20px', border: `2px solid ${impulseColor}` }}>
                    <div style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '8px', fontWeight: '500' }}>Market Regime</div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: impulseColor, marginBottom: '8px' }}>
                        {trend}
                    </div>
                    <div style={{ fontSize: '13px', color: '#d1d5db' }}>
                        {trend === "Expanding" ? "Risk On" : "Risk Off"}
                    </div>
                </div>
            </div>
        );
    };

    if (loading) return <div style={{ padding: '32px', textAlign: 'center', color: '#9ca3af' }}>Loading Global Liquidity...</div>;
    if (error) return <div style={{ padding: '32px', textAlign: 'center', color: '#ef4444' }}>Error: {error}</div>;

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#0e1525', color: '#d7e3f3', padding: '24px' }}>
            {/* Header */}
            <header style={{ marginBottom: '32px', borderBottom: '1px solid #1f2937', paddingBottom: '16px' }}>
                <h1 style={{
                    fontSize: '28px',
                    fontWeight: 'bold',
                    background: 'linear-gradient(to right, #06b6d4, #0891b2)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    margin: 0
                }}>
                    Global Liquidity Impulse
                </h1>
                <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '8px' }}>
                    Tracking Central Bank Balance Sheets (Fed + ECB + BoJ)
                </p>
            </header>

            {/* Metric Cards */}
            <MetricCards latestReading={latestReading} />

            {/* Regime Banner */}
            <RegimeBanner latestReading={latestReading} />

            {/* Main Chart: Liquidity + Impulse */}
            <div style={{ marginBottom: '48px' }}>
                <div style={{ marginBottom: '16px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#06b6d4', margin: 0 }}>
                        Global Liquidity & 3-Month Impulse
                    </h2>
                    <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px', maxWidth: '800px' }}>
                        Total central bank assets (left axis) and the 3-month rate of change (right axis).
                    </p>
                </div>

                <div style={{ height: '500px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '16px', border: '1px solid rgba(55, 65, 81, 0.5)' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={data} margin={{ top: 20, right: 80, left: 20, bottom: 60 }}>
                            <defs>
                                <linearGradient id="colorLiquidity" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.8} />
                                    <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.1} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />
                            <XAxis
                                dataKey="date"
                                stroke="#9CA3AF"
                                angle={-45}
                                textAnchor="end"
                                height={80}
                                interval={Math.floor(data.length / 15)}
                            />

                            {/* Left Y-Axis: Liquidity (Billions) */}
                            <YAxis
                                yAxisId="left"
                                stroke="#06b6d4"
                                tickFormatter={(value) => `$${(value / 1000).toFixed(0)}T`}
                                label={{ value: 'Global Liquidity', angle: -90, position: 'insideLeft', style: { fill: '#06b6d4' } }}
                            />

                            {/* Right Y-Axis: Impulse (%) */}
                            <YAxis
                                yAxisId="right"
                                orientation="right"
                                stroke="#f97316"
                                tickFormatter={(value) => `${value.toFixed(0)}%`}
                                label={{ value: 'Impulse (%)', angle: 90, position: 'insideRight', style: { fill: '#f97316' } }}
                            />

                            <Tooltip content={<CustomTooltip />} />
                            <Legend wrapperStyle={{ paddingTop: '20px' }} />

                            {/* Reference Line at 0 on Right Axis */}
                            <ReferenceLine yAxisId="right" y={0} stroke="#9ca3af" strokeDasharray="5 5" strokeWidth={2} />

                            {/* Area: Global Liquidity (Left Axis) */}
                            <Area
                                yAxisId="left"
                                type="monotone"
                                dataKey="global_liquidity_usd"
                                name="Global Liquidity"
                                stroke="#06b6d4"
                                strokeWidth={2}
                                fillOpacity={1}
                                fill="url(#colorLiquidity)"
                            />

                            {/* Line: Impulse (Right Axis) */}
                            <Line
                                yAxisId="right"
                                type="monotone"
                                dataKey="liquidity_impulse"
                                name="3M Impulse"
                                stroke="#f97316"
                                strokeWidth={2}
                                dot={false}
                                connectNulls
                            />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Component Breakdown Chart */}
            <div style={{ marginBottom: '48px' }}>
                <div style={{ marginBottom: '16px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#06b6d4', margin: 0 }}>
                        Central Bank Component Breakdown
                    </h2>
                    <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px', maxWidth: '800px' }}>
                        Stacked visualization showing the contribution of each major central bank.
                    </p>
                </div>

                <div style={{ height: '400px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '16px', border: '1px solid rgba(55, 65, 81, 0.5)' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />
                            <XAxis
                                dataKey="date"
                                stroke="#9CA3AF"
                                angle={-45}
                                textAnchor="end"
                                height={80}
                                interval={Math.floor(data.length / 15)}
                            />
                            <YAxis
                                stroke="#06b6d4"
                                tickFormatter={(value) => `$${(value / 1000).toFixed(0)}T`}
                            />
                            <Tooltip content={<CustomTooltip />} />
                            <Legend wrapperStyle={{ paddingTop: '20px' }} />

                            <Area
                                type="monotone"
                                dataKey="components.fed"
                                stackId="1"
                                name="Fed"
                                stroke="#ffffff"
                                strokeWidth={0.5}
                                fill="#6366f1"
                                fillOpacity={0.8}
                            />
                            <Area
                                type="monotone"
                                dataKey="components.ecb"
                                stackId="1"
                                name="ECB"
                                stroke="#ffffff"
                                strokeWidth={0.5}
                                fill="#d946ef"
                                fillOpacity={0.8}
                            />
                            <Area
                                type="monotone"
                                dataKey="components.boj"
                                stackId="1"
                                name="BoJ"
                                stroke="#ffffff"
                                strokeWidth={0.5}
                                fill="#06b6d4"
                                fillOpacity={0.8}
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Educational Section */}
            <div style={{ marginTop: '48px', padding: '24px', backgroundColor: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px', border: '1px solid #374151' }}>
                <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#06b6d4', marginBottom: '16px' }}>
                    About Global Liquidity
                </h3>
                <div style={{ color: '#9ca3af', fontSize: '14px', lineHeight: '1.6' }}>
                    <p style={{ marginBottom: '12px' }}>
                        Global Liquidity measures the aggregate balance sheets of major central banks (Fed, ECB, BoJ).
                        It's a <strong style={{ color: '#d1d5db' }}>leading indicator</strong> for risk asset performance.
                    </p>
                    <ul style={{ marginLeft: '20px', marginBottom: '12px' }}>
                        <li>
                            <strong style={{ color: '#22c55e' }}>Positive Impulse (Expansion)</strong>:
                            Central banks are adding liquidity. Historically bullish for equities, crypto, and credit.
                        </li>
                        <li>
                            <strong style={{ color: '#ef4444' }}>Negative Impulse (Contraction)</strong>:
                            Central banks are draining liquidity. Risk-off environment expected.
                        </li>
                    </ul>
                    <p style={{ fontSize: '13px', fontStyle: 'italic', color: '#6b7280' }}>
                        Current composition: Fed (~$6.6T), ECB (~$5.5T), BoJ (~$4.3T).
                        The BoJ's balance sheet is significant relative to Japan's GDP.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default LiquidityImpulseDashboard;
