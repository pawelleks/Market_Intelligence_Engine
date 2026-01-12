import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
    ResponsiveContainer,
    AreaChart, Area, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ReferenceLine
} from 'recharts';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const HamiltonDashboard = () => {
    const [data, setData] = useState([]);
    const [latestReading, setLatestReading] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const res = await axios.get(`${API_BASE_URL}/v1/analysis/hamilton-filter`);

                if (!res.data || !res.data.data) {
                    throw new Error("Invalid data format received from API");
                }

                setData(res.data.data);
                setLatestReading(res.data.latest_reading);
            } catch (err) {
                console.error("Hamilton Filter Data Fetch Error:", err);
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
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#ef4444' }} />
                        <span style={{ color: '#9ca3af' }}>Recession Probability:</span>
                        <span style={{ color: '#e5e7eb', fontFamily: 'monospace' }}>
                            {(dataPoint.recession_prob * 100).toFixed(2)}%
                        </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#6366f1' }} />
                        <span style={{ color: '#9ca3af' }}>GDP Growth:</span>
                        <span style={{ color: '#e5e7eb', fontFamily: 'monospace' }}>
                            {dataPoint.growth_rate?.toFixed(2)}%
                        </span>
                    </div>
                </div>
            );
        }
        return null;
    };

    // Metric Cards
    const MetricCards = ({ latestReading, data }) => {
        if (!latestReading || !data || data.length === 0) return null;

        const probability = latestReading.probability ?? 0;
        const regime = latestReading.regime ?? "Unknown";
        const latestGrowth = data[data.length - 1]?.growth_rate ?? 0;

        // Color logic: Green if < 50%, Red if >= 50%
        const probColor = probability < 0.5 ? "#22c55e" : "#ef4444";
        const regimeColor = regime === "Expansion" ? "#22c55e" : "#ef4444";

        return (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '32px' }}>
                {/* Recession Probability Card */}
                <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '20px', border: `2px solid ${probColor}` }}>
                    <div style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '8px', fontWeight: '500' }}>Recession Probability</div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: probColor, marginBottom: '8px' }}>
                        {(probability * 100).toFixed(2)}%
                    </div>
                    <div style={{ fontSize: '13px', color: '#d1d5db' }}>
                        {probability < 0.5 ? "Low Risk" : "High Risk"}
                    </div>
                </div>

                {/* Current Regime Card */}
                <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '20px', border: `2px solid ${regimeColor}` }}>
                    <div style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '8px', fontWeight: '500' }}>Current Regime</div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: regimeColor, marginBottom: '8px' }}>
                        {regime}
                    </div>
                    <div style={{ fontSize: '13px', color: '#d1d5db' }}>
                        Model Classification
                    </div>
                </div>

                {/* GDP Growth Card */}
                <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '20px', border: '2px solid #6366f1' }}>
                    <div style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '8px', fontWeight: '500' }}>GDP Growth (Latest)</div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#6366f1', marginBottom: '8px' }}>
                        {latestGrowth >= 0 ? '+' : ''}{latestGrowth.toFixed(2)}%
                    </div>
                    <div style={{ fontSize: '13px', color: '#d1d5db' }}>
                        Quarterly Change
                    </div>
                </div>
            </div>
        );
    };

    if (loading) return <div style={{ padding: '32px', textAlign: 'center', color: '#9ca3af' }}>Loading Hamilton Model...</div>;
    if (error) return <div style={{ padding: '32px', textAlign: 'center', color: '#ef4444' }}>Error: {error}</div>;

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#0e1525', color: '#d7e3f3', padding: '24px' }}>
            {/* Header */}
            <header style={{ marginBottom: '32px', borderBottom: '1px solid #1f2937', paddingBottom: '16px' }}>
                <h1 style={{
                    fontSize: '28px',
                    fontWeight: 'bold',
                    background: 'linear-gradient(to right, #ef4444, #dc2626)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    margin: 0
                }}>
                    Hamilton Markov Switching Model
                </h1>
                <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '8px' }}>
                    Regime-Switching Analysis for Recession Probability Detection
                </p>
            </header>

            {/* Metric Cards */}
            <MetricCards latestReading={latestReading} data={data} />

            {/* Main Chart Section */}
            <div style={{ marginBottom: '48px' }}>
                <div style={{ marginBottom: '16px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#ef4444', margin: 0 }}>
                        Recession Probability Over Time
                    </h2>
                    <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px', maxWidth: '800px' }}>
                        This chart shows the probability that the economy is in a recession state.
                        Spikes above <span style={{ color: '#ef4444', fontWeight: 'bold' }}>50%</span> indicate high recession likelihood.
                    </p>
                </div>

                {/* Area Chart */}
                <div style={{ height: '500px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '16px', border: '1px solid rgba(55, 65, 81, 0.5)' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                            <defs>
                                <linearGradient id="colorRecession" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.8} />
                                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0.1} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />
                            <XAxis
                                dataKey="date"
                                stroke="#9CA3AF"
                                minTickGap={30}
                                angle={-45}
                                textAnchor="end"
                                height={60}
                            />

                            {/* Y-Axis: Hard-coded domain [0, 1] */}
                            <YAxis
                                stroke="#ef4444"
                                domain={[0, 1]}
                                tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                                label={{ value: 'Recession Probability', angle: -90, position: 'insideLeft', style: { fill: '#ef4444' } }}
                            />

                            <Tooltip content={<CustomTooltip />} />
                            <Legend wrapperStyle={{ paddingTop: '20px' }} />

                            {/* Reference Line at 50% */}
                            <ReferenceLine
                                y={0.5}
                                stroke="#fbbf24"
                                strokeDasharray="5 5"
                                strokeWidth={2}
                                label={{ value: '50% Threshold', position: 'right', fill: '#fbbf24' }}
                            />

                            {/* Area: Recession Probability */}
                            <Area
                                type="monotone"
                                dataKey="recession_prob"
                                name="Recession Probability"
                                stroke="#ef4444"
                                strokeWidth={2}
                                fillOpacity={1}
                                fill="url(#colorRecession)"
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Educational Section */}
            <div style={{ marginTop: '48px', padding: '24px', backgroundColor: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px', border: '1px solid #374151' }}>
                <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#ef4444', marginBottom: '16px' }}>
                    About Hamilton's Regime-Switching Model
                </h3>
                <div style={{ color: '#9ca3af', fontSize: '14px', lineHeight: '1.6' }}>
                    <p style={{ marginBottom: '12px' }}>
                        Hamilton's Markov-switching model (1989) detects <strong style={{ color: '#d1d5db' }}>structural breaks</strong> in economic data
                        by identifying different "regimes" (Growth vs. Recession) with distinct statistical properties.
                    </p>
                    <ul style={{ marginLeft: '20px', marginBottom: '12px' }}>
                        <li>
                            <strong style={{ color: '#ef4444' }}>Recession Probability</strong>:
                            A probability above 50% signals a high likelihood that the economy has shifted to a recession state.
                        </li>
                        <li>
                            <strong style={{ color: '#22c55e' }}>Growth Regime</strong>:
                            Mean growth = 0.62%, low volatility (σ² = 0.19).
                        </li>
                        <li>
                            <strong style={{ color: '#ef4444' }}>Recession Regime</strong>:
                            Mean growth = -1.75%, high volatility (σ² = 7.98).
                        </li>
                    </ul>
                    <p style={{ fontSize: '13px', fontStyle: 'italic', color: '#6b7280' }}>
                        This model successfully identified the 2008 Financial Crisis and 2020 COVID recession,
                        with probabilities spiking near 100% during those periods.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default HamiltonDashboard;
