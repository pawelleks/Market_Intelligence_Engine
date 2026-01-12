import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
    ResponsiveContainer,
    ComposedChart, Line, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ReferenceLine
} from 'recharts';
import RecessionOverlay from './common/RecessionOverlay';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const HPFilterDashboard = () => {
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [hiddenSeries, setHiddenSeries] = useState({});
    const [timeRange, setTimeRange] = useState('10Y'); // Default to 10 years for better bar visibility
    const [recessionData, setRecessionData] = useState([]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const res = await axios.get(`${API_BASE_URL}/v1/analysis/hp-filter`);

                // Transform Columnar JSON to Row-based for Recharts
                const { dates, indicators } = res.data;

                if (!dates || !indicators) {
                    throw new Error("Invalid data format received from API");
                }

                const transformed = dates.map((date, i) => {
                    const row = { date };
                    Object.keys(indicators).forEach(key => {
                        row[key] = indicators[key][i];
                    });
                    return row;
                });

                setData(transformed);

                // Fetch USREC recession data
                try {
                    const recRes = await axios.get(`${API_BASE_URL}/macro/fred/USREC`);
                    if (recRes.data && Array.isArray(recRes.data)) {
                        setRecessionData(recRes.data);
                    }
                } catch (recErr) {
                    console.warn('Failed to load recession data:', recErr);
                }
            } catch (err) {
                console.error("HP Filter Data Fetch Error:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    // Helper: Format Year for X-Axis
    const formatYear = (tick) => {
        if (!tick) return '';
        return tick.substring(0, 4);
    };

    // Interactive Legend Handler
    const handleLegendClick = (dataKey) => {
        setHiddenSeries(prev => ({
            ...prev,
            [dataKey]: !prev[dataKey]
        }));
    };

    // Filter data based on selected time range
    const getFilteredData = () => {
        if (!data || data.length === 0) return [];

        if (timeRange === 'MAX') return data;

        const yearsMap = {
            '1Y': 1,
            '5Y': 5,
            '10Y': 10,
            '20Y': 20
        };

        const years = yearsMap[timeRange] || 10;
        const cutoffDate = new Date();
        cutoffDate.setFullYear(cutoffDate.getFullYear() - years);

        return data.filter(d => new Date(d.date) >= cutoffDate);
    };

    const filteredData = getFilteredData();

    // Custom Tooltip
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
                                {entry.name.includes('Gap') ? '%' : ''}
                            </span>
                        </div>
                    ))}
                </div>
            );
        }
        return null;
    };

    // Business Cycle Regime Detection
    const determineRegime = (data) => {
        if (!data || data.length < 2) return null;

        const latest = data[data.length - 1];
        const previous = data[data.length - 2];

        const outputGap = latest.output_gap ?? 0;
        const previousOutputGap = previous.output_gap ?? 0;
        const creditGap = latest.credit_gap ?? 0;
        const previousCreditGap = previous.credit_gap ?? 0;

        // Early Cycle (Recovery): Output Gap < -0.5% but rising AND Credit Gap < 1.5%
        if (outputGap < -0.5 && outputGap > previousOutputGap && creditGap < 1.5) {
            return {
                name: "Early Cycle (Recovery)",
                message: "Room to run. Buy risk.",
                color: "#22c55e", // Green
                icon: "📈"
            };
        }

        // Mid Cycle (Boom): Output Gap > 0.5% AND Credit Gap > 0%
        if (outputGap > 0.5 && creditGap > 0) {
            return {
                name: "Mid Cycle (Boom)",
                message: "Goldilocks zone. Growth is robust.",
                color: "#22c55e", // Green
                icon: "🟢"
            };
        }

        // Late Cycle: Output Gap between -1.0% and +0.5% AND Credit Gap > 1.5%
        if (outputGap >= -1.0 && outputGap <= 0.5 && creditGap > 1.5) {
            return {
                name: "Late Cycle",
                message: "Economy slowing, but debt still high. Risk of correction.",
                color: "#f59e0b", // Amber/Orange
                icon: "⚠️"
            };
        }

        // Recession (Bust): Output Gap < -1.0% AND Credit Gap contracting
        if (outputGap < -1.0 && creditGap < previousCreditGap) {
            return {
                name: "Recession (Bust)",
                message: "Deleveraging in progress.",
                color: "#ef4444", // Red
                icon: "🔴"
            };
        }

        // Default fallback
        return {
            name: "Transitional",
            message: "Mixed signals. Monitor closely.",
            color: "#9ca3af", // Gray
            icon: "⚪"
        };
    };

    // Regime Banner Component
    const RegimeBanner = ({ data }) => {
        if (!data || data.length === 0) return null;

        const regime = determineRegime(data);
        if (!regime) return null;

        return (
            <div style={{
                marginBottom: '24px',
                padding: '20px',
                backgroundColor: 'rgba(31, 41, 55, 0.5)',
                borderRadius: '8px',
                border: `2px solid ${regime.color}`,
                borderLeft: `6px solid ${regime.color}`
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                    <span style={{ fontSize: '24px' }}>{regime.icon}</span>
                    <h2 style={{
                        margin: 0,
                        fontSize: '20px',
                        fontWeight: 'bold',
                        color: regime.color
                    }}>
                        Current Regime: {regime.name}
                    </h2>
                </div>
                <p style={{
                    margin: 0,
                    color: '#d1d5db',
                    fontSize: '15px',
                    lineHeight: '1.5'
                }}>
                    {regime.message}
                </p>
            </div>
        );
    };


    // Summary Cards
    const SummaryCards = ({ data }) => {
        if (!data || data.length === 0) return null;
        const latest = data[data.length - 1];

        const outputGap = latest.output_gap ?? 0;
        const creditGap = latest.credit_gap ?? 0;

        // Determine status based on gaps
        let outputStatus = "Neutral";
        let outputColor = "#9ca3af";
        if (outputGap > 2) {
            outputStatus = "Overheating";
            outputColor = "#ef4444"; // Red
        } else if (outputGap < -2) {
            outputStatus = "Recessionary";
            outputColor = "#3b82f6"; // Blue
        } else if (Math.abs(outputGap) <= 1) {
            outputStatus = "At Trend";
            outputColor = "#22c55e"; // Green
        }

        let creditStatus = "Neutral";
        let creditColor = "#9ca3af";
        if (creditGap > 5) {
            creditStatus = "High Credit Risk";
            creditColor = "#ef4444";
        } else if (creditGap < -5) {
            creditStatus = "Credit Crunch";
            creditColor = "#3b82f6";
        } else if (creditGap > 1.5) {
            creditStatus = "Elevated"; // Changed threshold from 1% to 1.5%
            creditColor = "#f59e0b"; // Orange for elevated
        } else if (Math.abs(creditGap) <= 1.5) {
            creditStatus = "Stable";
            creditColor = "#22c55e";
        }

        return (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '32px' }}>
                {/* Output Gap Card */}
                <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '20px', border: `2px solid ${outputColor}` }}>
                    <div style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '8px', fontWeight: '500' }}>Output Gap</div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: outputColor, marginBottom: '8px' }}>
                        {outputGap >= 0 ? '+' : ''}{outputGap.toFixed(2)}%
                    </div>
                    <div style={{ fontSize: '13px', color: '#d1d5db' }}>{outputStatus}</div>
                </div>

                {/* Credit Gap Card */}
                <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '20px', border: `2px solid ${creditColor}` }}>
                    <div style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '8px', fontWeight: '500' }}>Credit Gap</div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: creditColor, marginBottom: '8px' }}>
                        {creditGap >= 0 ? '+' : ''}{creditGap.toFixed(2)}%
                    </div>
                    <div style={{ fontSize: '13px', color: '#d1d5db' }}>{creditStatus}</div>
                </div>

                {/* Real GDP Card */}
                <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '20px', border: '2px solid #6366f1' }}>
                    <div style={{ fontSize: '14px', color: '#9ca3af', marginBottom: '8px', fontWeight: '500' }}>Real GDP (Billions)</div>
                    <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#6366f1', marginBottom: '8px' }}>
                        ${(latest.real_gdp ?? 0).toLocaleString()}
                    </div>
                    <div style={{ fontSize: '13px', color: '#d1d5db' }}>
                        Trend: ${(latest.gdp_trend ?? 0).toLocaleString()}
                    </div>
                </div>
            </div>
        );
    };

    if (loading) return <div style={{ padding: '32px', textAlign: 'center', color: '#9ca3af' }}>Loading HP Filter Model...</div>;
    if (error) return <div style={{ padding: '32px', textAlign: 'center', color: '#ef4444' }}>Error: {error}</div>;

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#0e1525', color: '#d7e3f3', padding: '24px' }}>
            {/* Header */}
            <header style={{ marginBottom: '32px', borderBottom: '1px solid #1f2937', paddingBottom: '16px' }}>
                <h1 style={{
                    fontSize: '28px',
                    fontWeight: 'bold',
                    background: 'linear-gradient(to right, #6366f1, #8b5cf6)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    margin: 0
                }}>
                    Hodrick-Prescott (HP) Filter Analysis
                </h1>
                <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '8px' }}>
                    Decomposing GDP and Credit into Trend and Cyclical Components
                </p>
            </header>

            {/* Summary Cards */}
            <SummaryCards data={data} />

            {/* Regime Banner */}
            <RegimeBanner data={data} />

            {/* Main Chart Section */}
            <div style={{ marginBottom: '48px' }}>
                <div style={{ marginBottom: '16px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#6366f1', margin: 0 }}>
                        Economic Cycles: Output Gap & Credit Gap
                    </h2>
                    <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px', maxWidth: '800px' }}>
                        The <span style={{ color: '#60a5fa' }}>Output Gap</span> measures deviations of Real GDP from its potential trend.
                        The <span style={{ color: '#f59e0b' }}>Credit Gap</span> (Basel III proxy) tracks credit cycle excesses.
                    </p>
                    <div style={{ marginTop: '8px', fontSize: '13px', color: '#6b7280', fontStyle: 'italic', borderLeft: '2px solid #374151', paddingLeft: '8px' }}>
                        <strong>Interpretation:</strong> Positive gaps indicate overheating/excess. Negative gaps signal recession/deleveraging.
                    </div>
                </div>

                {/* Time Range Selector */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginBottom: '12px' }}>
                    {['1Y', '5Y', '10Y', '20Y', 'MAX'].map(range => (
                        <button
                            key={range}
                            onClick={() => setTimeRange(range)}
                            style={{
                                padding: '6px 12px',
                                fontSize: '12px',
                                fontWeight: '500',
                                border: timeRange === range ? '2px solid #6366f1' : '1px solid #374151',
                                backgroundColor: timeRange === range ? 'rgba(99, 102, 241, 0.2)' : 'rgba(31, 41, 55, 0.5)',
                                color: timeRange === range ? '#6366f1' : '#9ca3af',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                transition: 'all 0.2s'
                            }}
                        >
                            {range}
                        </button>
                    ))}
                </div>

                {/* Dual-Axis Chart */}
                <div style={{ height: '500px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '16px', border: '1px solid rgba(55, 65, 81, 0.5)' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={filteredData} margin={{ top: 20, right: 80, left: 20, bottom: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />

                            {/* NBER Recession Shading */}
                            <RecessionOverlay data={filteredData} recessionData={recessionData} />

                            <XAxis dataKey="date" tickFormatter={formatYear} stroke="#9CA3AF" minTickGap={30} />

                            {/* Left Y-Axis: GDP (Billions) */}
                            <YAxis
                                yAxisId="left"
                                stroke="#6366f1"
                                label={{ value: 'GDP (Billions $)', angle: -90, position: 'insideLeft', style: { fill: '#6366f1' } }}
                            />

                            {/* Right Y-Axis: Gaps (%) */}
                            <YAxis
                                yAxisId="right"
                                orientation="right"
                                stroke="#f59e0b"
                                label={{ value: 'Gap (%)', angle: 90, position: 'insideRight', style: { fill: '#f59e0b' } }}
                            />

                            <Tooltip content={<CustomTooltip />} />
                            <Legend
                                onClick={(e) => handleLegendClick(e.dataKey)}
                                wrapperStyle={{ paddingTop: '20px', cursor: 'pointer' }}
                            />

                            {/* Reference Line at 0 on Right Axis */}
                            <ReferenceLine yAxisId="right" y={0} stroke="#9ca3af" strokeDasharray="5 5" strokeWidth={2} />

                            {/* Lines: GDP & Trend (Left Axis) */}
                            <Line
                                yAxisId="left"
                                type="monotone"
                                dataKey="real_gdp"
                                name="Real GDP"
                                stroke="#6366f1"
                                strokeWidth={2}
                                dot={false}
                                connectNulls
                                hide={hiddenSeries['real_gdp']}
                            />
                            <Line
                                yAxisId="left"
                                type="monotone"
                                dataKey="gdp_trend"
                                name="Potential Trend"
                                stroke="#9ca3af"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                dot={false}
                                connectNulls
                                hide={hiddenSeries['gdp_trend']}
                            />

                            {/* Bars: Output Gap & Credit Gap (Right Axis) */}
                            <Bar
                                yAxisId="right"
                                dataKey="output_gap"
                                name="Output Gap"
                                fill="#60a5fa"
                                opacity={0.7}
                                hide={hiddenSeries['output_gap']}
                            />
                            <Bar
                                yAxisId="right"
                                dataKey="credit_gap"
                                name="Credit Gap"
                                fill="#f59e0b"
                                opacity={0.7}
                                hide={hiddenSeries['credit_gap']}
                            />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Educational Section */}
            <div style={{ marginTop: '48px', padding: '24px', backgroundColor: 'rgba(31, 41, 55, 0.3)', borderRadius: '8px', border: '1px solid #374151' }}>
                <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#6366f1', marginBottom: '16px' }}>
                    About the Hodrick-Prescott Filter
                </h3>
                <div style={{ color: '#9ca3af', fontSize: '14px', lineHeight: '1.6' }}>
                    <p style={{ marginBottom: '12px' }}>
                        The HP Filter decomposes a time series into a <strong style={{ color: '#d1d5db' }}>trend component</strong> and a <strong style={{ color: '#d1d5db' }}>cyclical component</strong>.
                        It&#39;s widely used by central banks (including the BIS for Credit-to-GDP gaps) to identify economic cycles.
                    </p>
                    <ul style={{ marginLeft: '20px', marginBottom: '12px' }}>
                        <li><strong style={{ color: '#60a5fa' }}>Output Gap</strong>: When positive, the economy is producing above its sustainable capacity (overheating). When negative, there is slack (recession).</li>
                        <li><strong style={{ color: '#f59e0b' }}>Credit Gap</strong>: A Basel III early warning indicator. Credit gaps above 2% historically precede financial crises.</li>
                    </ul>
                    <p style={{ fontSize: '13px', fontStyle: 'italic', color: '#6b7280' }}>
                        Smoothing Parameter (λ): 1600 for quarterly data (standard macro convention).
                    </p>
                </div>
            </div>
        </div>
    );
};

export default HPFilterDashboard;
