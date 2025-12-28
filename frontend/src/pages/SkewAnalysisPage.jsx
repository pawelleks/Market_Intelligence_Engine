import React, { useState, useEffect, useMemo } from 'react';
import {
    ComposedChart, Line, Area, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, Cell
} from 'recharts';
import { Activity, TrendingUp, TrendingDown, AlertTriangle, Info } from 'lucide-react';

// --- Utility: Moving Average ---
const calculateSMA = (data, window = 5, key = 'value') => {
    return data.map((entry, index, arr) => {
        if (index < window - 1) return { ...entry, [`${key}_sma`]: null };
        const slice = arr.slice(index - window + 1, index + 1);
        const sum = slice.reduce((acc, curr) => acc + (curr[key] || 0), 0);
        return { ...entry, [`${key}_sma`]: sum / window };
    });
};

// --- Component: Insight Card ---
const InsightCard = ({ title, value, subtext, type = 'neutral' }) => {
    const colors = {
        bullish: '#4caf50',
        bearish: '#ef5350',
        neutral: '#29b6f6',
        warning: '#ff9800'
    };
    const color = colors[type] || colors.neutral;

    return (
        <div style={{
            backgroundColor: '#1e293b',
            padding: '20px',
            borderRadius: '8px',
            borderLeft: `4px solid ${color}`,
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
            flex: 1
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                {type === 'warning' ? <AlertTriangle size={18} color={color} /> : <Activity size={18} color={color} />}
                <span style={{ color: '#94a3b8', fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase' }}>{title}</span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#e2e8f0', marginBottom: '4px' }}>
                {value}
            </div>
            <div style={{ fontSize: '0.85rem', color: '#64748b' }}>
                {subtext}
            </div>
        </div>
    );
};

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <div style={{ backgroundColor: '#0f172a', border: '1px solid #334155', padding: '10px', borderRadius: '4px' }}>
                <p style={{ color: '#e2e8f0', marginBottom: '5px' }}>{label}</p>
                {payload.map((entry, index) => (
                    <p key={index} style={{ color: entry.color, fontSize: '0.9rem', margin: 0 }}>
                        {entry.name}: {typeof entry.value === 'number' ? entry.value.toFixed(4) : entry.value}
                    </p>
                ))}
            </div>
        );
    }
    return null;
};

const SkewAnalysisPage = () => {
    const [ticker, setTicker] = useState('SPY');
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const availableTickers = ['SPY', 'QQQ', 'IWM', 'DIA'];

    useEffect(() => {
        fetchData();
    }, [ticker]);

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(`/api/v1/analytics/skew/${ticker}/history`);
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Failed to fetch data');
            }
            const data = await response.json();
            setHistory(data);
        } catch (err) {
            console.error(err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const triggerRefresh = async () => {
        setLoading(true);
        try {
            await fetch(`/api/v1/analytics/skew/${ticker}/refresh`, { method: 'POST' });
            setTimeout(fetchData, 2000);
        } catch (e) {
            alert("Refresh failed");
            setLoading(false);
        }
    }

    // --- Data Processing for Visualization ---
    const processedData = useMemo(() => {
        if (!history.length) return [];

        // Determine what PCR to show. User asked for Volume, but fallback to OI if all Vol is missing/0.
        const hasVolumePCR = history.some(d => d.pcr_metrics?.total_volume_pcr > 0);
        const pcrKey = hasVolumePCR ? 'total_volume_pcr' : 'total_oi_pcr';

        let data = history.map(d => ({
            date: d.date,
            price: d.underlying_price || d.price || 0, // Fallback if schema varies
            skew: d.skew_metrics?.skew_25d_1m || 0,
            pcr: d.pcr_metrics?.[pcrKey] || 0,
            pcrType: hasVolumePCR ? 'Volume' : 'Open Interest', // For Label
        }));

        // Add SMA for PCR
        data = calculateSMA(data, 5, 'pcr');

        return data;
    }, [history]);

    // --- Actionable Insights (NLP Logic) ---
    const insights = useMemo(() => {
        if (!processedData.length || processedData.length < 2) return null;

        const latest = processedData[processedData.length - 1];
        const prev = processedData[processedData.length - 2];

        const skewChange = latest.skew - prev.skew;
        const priceChange = latest.price - prev.price;
        const pcr = latest.pcr;
        const skew = latest.skew;

        let sentiment = {
            scanResults: [],
            primaryState: "Neutral"
        };

        // Scenario A: Skew Rising + Price Falling (Hedging)
        if (skewChange > 0.005 && priceChange < 0) {
            sentiment.scanResults.push({
                msg: "Defensive Hedging Detected",
                detail: "Investors are paying up for downside puts while price drops.",
                type: "bearish"
            });
            sentiment.primaryState = "Defensive";
        }

        // Scenario B: PCR < 0.7 (Complacency)
        if (pcr < 0.7) {
            sentiment.scanResults.push({
                msg: "Complacency Warning",
                detail: "Extreme bullish sentiment (Low PCR) often precedes a pullback.",
                type: "warning"
            });
            if (sentiment.primaryState === "Neutral") sentiment.primaryState = "Overbought";
        }

        // Scenario C: Skew Near 0
        if (Math.abs(skew) < 0.02) {
            sentiment.scanResults.push({
                msg: "Balanced Market",
                detail: "No strong directional bias in 25-delta options pricing.",
                type: "neutral"
            });
        }

        // Additional: High PCR
        if (pcr > 1.2) {
            sentiment.scanResults.push({
                msg: "Bearish Sentiment / Capitulation",
                detail: "High Put volume relative to Calls.",
                type: "bearish"
            });
        }

        return {
            ...latest,
            sentiment
        };
    }, [processedData]);

    if (loading && history.length === 0) {
        return <div style={{ color: '#fff', padding: '40px', textAlign: 'center' }}>Loading Option Sentiment Dashboard...</div>;
    }

    return (
        <div style={{ padding: '24px', backgroundColor: '#0b1220', minHeight: '100vh', color: '#e2e8f0', fontFamily: 'Inter, sans-serif' }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: '1.8rem', fontWeight: 700 }}>Option Sentiment Dashboard</h1>
                    <p style={{ margin: '4px 0 0 0', color: '#64748b', fontSize: '0.9rem' }}>
                        Skew & PCR Analysis for <strong>{ticker}</strong>
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <select
                        value={ticker}
                        onChange={e => setTicker(e.target.value)}
                        style={{ padding: '8px 12px', backgroundColor: '#1e293b', color: '#fff', border: '1px solid #334155', borderRadius: '6px' }}
                    >
                        {availableTickers.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                    <button
                        onClick={triggerRefresh}
                        style={{ padding: '8px 16px', backgroundColor: '#3b82f6', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 500 }}
                    >
                        Refresh Data
                    </button>
                </div>
            </div>

            {/* Summary Cards */}
            {insights && (
                <div style={{ display: 'flex', gap: '20px', marginBottom: '24px', flexWrap: 'wrap' }}>
                    <InsightCard
                        title="Market State"
                        value={insights.sentiment.primaryState}
                        subtext={insights.sentiment.scanResults[0]?.msg || "Awaiting Signal"}
                        type={insights.sentiment.scanResults[0]?.type || 'neutral'}
                    />
                    <InsightCard
                        title={`PCR (${insights.pcrType})`}
                        value={insights.pcr?.toFixed(2)}
                        subtext={`5-Day Avg: ${insights.pcr_sma?.toFixed(2)}`}
                        type={insights.pcr > 1.0 ? 'bearish' : (insights.pcr < 0.7 ? 'warning' : 'neutral')}
                    />
                    <InsightCard
                        title="25d Skew"
                        value={`${(insights.skew * 100).toFixed(1)}%`}
                        subtext={insights.skew > 0.05 ? "Put Premium High (Fear)" : (insights.skew < -0.05 ? "Call Premium High (Greed)" : "Balanced")}
                        type={Math.abs(insights.skew) > 0.05 ? 'warning' : 'neutral'}
                    />
                </div>
            )}

            {/* Actionable Insight Text */}
            {insights?.sentiment?.scanResults?.length > 0 && (
                <div style={{ marginBottom: '24px', padding: '16px', backgroundColor: 'rgba(59, 130, 246, 0.1)', border: '1px solid #3b82f6', borderRadius: '8px' }}>
                    {insights.sentiment.scanResults.map((res, idx) => (
                        <div key={idx} style={{ display: 'flex', gap: '8px', marginBottom: idx < insights.sentiment.scanResults.length - 1 ? '8px' : '0' }}>
                            <Info size={16} color="#3b82f6" style={{ marginTop: '3px' }} />
                            <div>
                                <strong style={{ color: '#93c5fd' }}>{res.msg}:</strong> <span style={{ color: '#cbd5e1' }}>{res.detail}</span>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Chart 1: Price vs Skew */}
            <div style={{ backgroundColor: '#1e293b', padding: '20px', borderRadius: '8px', marginBottom: '24px', border: '1px solid #334155' }}>
                <h3 style={{ margin: '0 0 16px 0', fontSize: '1.1rem', color: '#e2e8f0' }}>Price (Area) vs. Option Skew (Line)</h3>
                <div style={{ height: 400 }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={processedData}>
                            <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
                            <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 12 }} tickFormatter={str => str.slice(5)} />
                            <YAxis yAxisId="left" stroke="#f43f5e" tick={{ fontSize: 12 }} label={{ value: 'Skew', angle: -90, position: 'insideLeft', fill: '#f43f5e' }} />
                            <YAxis yAxisId="right" orientation="right" stroke="#3b82f6" tick={{ fontSize: 12 }} domain={['auto', 'auto']} label={{ value: 'Price', angle: 90, position: 'insideRight', fill: '#3b82f6' }} />
                            <Tooltip content={<CustomTooltip />} />
                            <Legend />
                            <ReferenceLine y={0} yAxisId="left" stroke="#fff" strokeDasharray="3 3" />

                            <Area yAxisId="right" type="monotone" dataKey="price" name="Underlying Price" fillOpacity={0.1} fill="#3b82f6" stroke="#3b82f6" strokeWidth={2} />
                            <Line yAxisId="left" type="monotone" dataKey="skew" name="25d Skew" stroke="#f43f5e" strokeWidth={2} dot={false} />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Chart 2: PCR */}
            <div style={{ backgroundColor: '#1e293b', padding: '20px', borderRadius: '8px', border: '1px solid #334155' }}>
                <h3 style={{ margin: '0 0 16px 0', fontSize: '1.1rem', color: '#e2e8f0' }}>Put/Call Ratio ({processedData[0]?.pcrType}) & 5-Day Trend</h3>
                <div style={{ height: 350 }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={processedData}>
                            <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
                            <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 12 }} tickFormatter={str => str.slice(5)} />
                            <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} />
                            <Tooltip content={<CustomTooltip />} />
                            <Legend />
                            <ReferenceLine y={1.0} stroke="#64748b" strokeDasharray="3 3" />
                            <ReferenceLine y={0.7} stroke="#fbbf24" strokeDasharray="3 3" label={{ position: 'right', value: 'Complacency (0.7)', fill: '#fbbf24', fontSize: 10 }} />

                            <Bar dataKey="pcr" name="Daily PCR" fill="#475569" barSize={20}>
                                {processedData.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.pcr > 1.2 ? '#ef5350' : (entry.pcr < 0.7 ? '#fbbf24' : '#475569')} />
                                ))}
                            </Bar>
                            <Line type="monotone" dataKey="pcr_sma" name="5-Day MA" stroke="#34d399" strokeWidth={2} dot={false} />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </div>

        </div>
    );
};

export default SkewAnalysisPage;
