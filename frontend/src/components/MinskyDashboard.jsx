import React, { useState, useEffect } from 'react';
import axios from 'axios';
import MinskyExplainer from './MinskyExplainer';
import MinskySignals from './MinskySignals';
import MinskyMarketChart from './MinskyMarketChart';
import MinskySignalHistory from './MinskySignalHistory';
import {
    ResponsiveContainer,
    BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ReferenceLine, Cell,
    ComposedChart, Line, AreaChart, Area, CartesianGrid
} from 'recharts';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const MinskyDashboard = () => {
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                // Direct endpoint as per verification
                const res = await axios.get(`${API_BASE_URL}/minsky-data`);

                // Transform "Columnar" JSON to "Row-based" for Recharts
                // Structure: { dates: [], indicators: { key: [] } }
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
            } catch (err) {
                console.error("Minsky Data Fetch Error:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    if (loading) return <div style={{ padding: '32px', textAlign: 'center', color: '#9ca3af' }}>Loading Minsky Models...</div>;
    if (error) return <div style={{ padding: '32px', textAlign: 'center', color: '#ef4444' }}>Error loading data: {error}</div>;

    // Render Helpers
    const CustomTooltip = ({ active, payload, label }) => {
        if (active && payload && payload.length) {
            return (
                <div style={{ backgroundColor: '#111827', border: '1px solid #374151', padding: '12px', borderRadius: '4px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)', fontSize: '12px' }}>
                    <p style={{ fontWeight: 'bold', color: '#d1d5db', marginBottom: '8px', margin: 0 }}>{label}</p>
                    {payload.map((entry, idx) => (
                        <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: entry.color }} />
                            <span style={{ color: '#9ca3af', textTransform: 'capitalize' }}>{entry.name}:</span>
                            <span style={{ color: '#e5e7eb', fontFamily: 'monospace' }}>
                                {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}
                            </span>
                        </div>
                    ))}
                </div>
            );
        }
        return null;
    };

    // New Minsky Status Badge
    const MinskyStatusBadge = ({ data }) => {
        if (!data || data.length === 0) return null;
        const latest = data[data.length - 1];
        const gap = latest.minsky_instability_gap;
        const risk = latest.risk_complacency_index;

        let status = "🟢 STABLE: Hedge Finance";
        let color = "#22c55e"; // Green
        let leverageText = "Current leverage is manageable";
        let profitText = "profit margins are stable";

        if (gap > 0) {
            if (risk > 0.8) {
                status = "🔴 CRITICAL: Ponzi Finance (Bubble)";
                color = "#ef4444";
                leverageText = "Current leverage is HIGH";
            } else {
                status = "🟠 WARNING: Speculative Finance";
                color = "#f97316"; // Orange
                leverageText = "Current leverage is rising";
            }
            profitText = "profit margins are contracting";
        } else {
            profitText = "profit margins are expanding";
        }

        return (
            <div style={{ marginBottom: '24px', padding: '16px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', borderLeft: `4px solid ${color}` }}>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 'bold', color: color }}>{status}</h3>
                <p style={{ margin: '4px 0 0 0', color: '#9ca3af', fontSize: '14px' }}>
                    {leverageText} while {profitText}.
                </p>
            </div>
        );
    };

    const formatYear = ((tick) => {
        if (!tick) return '';
        // Assuming date is 'YYYY-MM-DD'
        return tick.substring(0, 4);
    });

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#0e1525', color: '#d7e3f3', padding: '24px' }}>
            <header style={{ marginBottom: '32px', borderBottom: '1px solid #1f2937', paddingBottom: '16px' }}>
                <h1 style={{ fontSize: '28px', fontWeight: 'bold', background: 'linear-gradient(to right, #60a5fa, #a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', margin: 0 }}>
                    Minsky Financial Instability Dashboard
                </h1>
                <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '8px' }}>
                    Tracking the cycle from Hedge to Speculative to Ponzi Finance.
                </p>
            </header>

            <MinskyExplainer />
            <MinskyStatusBadge data={data} />
            <MinskySignals data={data} />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '48px', maxWidth: '1280px', margin: '0 auto' }}>

                {/* SECTION 1: THE MINSKY MOMENT */}
                <section>
                    <div style={{ marginBottom: '16px' }}>
                        <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#f87171', margin: 0 }}>1. The Minsky Moment (Crisis Signal)</h2>
                        <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px', maxWidth: '672px' }}>
                            When the red bars are high, <span style={{ color: '#fca5a5' }}>Debt is growing faster than Profits</span>.
                            This is the definition of Ponzi Finance—borrowing just to pay interest.
                        </p>
                    </div>

                    <div style={{ height: '320px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '16px', border: '1px solid rgba(55, 65, 81, 0.5)' }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 20 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />
                                <XAxis dataKey="date" tickFormatter={formatYear} stroke="#9CA3AF" fontSize={12} minTickGap={30} />
                                <YAxis stroke="#9CA3AF" fontSize={12} tickFormatter={(val) => val.toFixed(1)} />
                                <Tooltip content={<CustomTooltip />} />
                                <ReferenceLine y={0} stroke="#6B7280" />
                                <Legend wrapperStyle={{ paddingTop: '10px' }} />
                                <Bar dataKey="minsky_instability_gap" name="Instability Gap" radius={[2, 2, 0, 0]}>
                                    {data.map((entry, index) => (
                                        <Cell
                                            key={`cell-${index}`}
                                            fill={entry.minsky_instability_gap > 0 ? "#ef4444" : "#22c55e"}
                                            stroke={entry.minsky_instability_gap > 0 ? "#ef4444" : "#22c55e"}
                                        />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </section>

                {/* SECTION 2: THE FUEL */}
                <section>
                    <div style={{ marginBottom: '16px' }}>
                        <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#60a5fa', margin: 0 }}>2. The Fuel (Leverage vs. Service)</h2>
                        <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px' }}>
                            Rising leverage (Blue) is manageable until interest payments (Orange) spike.
                            <span style={{ color: '#fdba74' }}> Divergence here signals acute financial stress.</span>
                        </p>
                    </div>

                    <div style={{ height: '320px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '16px', border: '1px solid rgba(55, 65, 81, 0.5)' }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <ComposedChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 20 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />
                                <XAxis dataKey="date" tickFormatter={formatYear} stroke="#9CA3AF" fontSize={12} minTickGap={30} />
                                <YAxis yAxisId="left" stroke="#60A5FA" fontSize={12} label={{ value: 'Leverage Ratio', angle: -90, position: 'insideLeft', fill: '#60A5FA' }} />
                                <YAxis yAxisId="right" orientation="right" stroke="#FBBF24" fontSize={12} label={{ value: 'Debt Service %', angle: 90, position: 'insideRight', fill: '#FBBF24' }} />
                                <Tooltip content={<CustomTooltip />} />
                                <Legend wrapperStyle={{ paddingTop: '10px' }} />
                                <Line yAxisId="left" type="monotone" dataKey="leverage_ratio" name="Leverage Ratio" stroke="#60A5FA" strokeWidth={2} dot={false} />
                                <Line yAxisId="right" type="monotone" dataKey="debt_service_proxy" name="Debt Service Burden" stroke="#FBBF24" strokeWidth={2} dot={false} />
                            </ComposedChart>
                        </ResponsiveContainer>
                    </div>
                </section>

                {/* SECTION 3: SENTIMENT */}
                <section>
                    <div style={{ marginBottom: '16px' }}>
                        <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#a78bfa', margin: 0 }}>3. Market Sentiment (The Trigger)</h2>
                        <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px' }}>
                            High peaks mean investors are euphoric and ignoring risk (tight spreads).
                            <span style={{ color: '#d8b4fe' }}> Sudden drops usually mark the onset of a crash.</span>
                        </p>
                    </div>

                    <div style={{ height: '320px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '16px', border: '1px solid rgba(55, 65, 81, 0.5)' }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 20 }}>
                                <defs>
                                    <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#A78BFA" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#A78BFA" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.5} />
                                <XAxis dataKey="date" tickFormatter={formatYear} stroke="#9CA3AF" fontSize={12} minTickGap={30} />
                                <YAxis stroke="#A78BFA" fontSize={12} />
                                <Tooltip content={<CustomTooltip />} />
                                <Legend wrapperStyle={{ paddingTop: '10px' }} />
                                <Area
                                    type="monotone"
                                    dataKey="risk_complacency_index"
                                    name="Risk Complacency (Euphoria)"
                                    stroke="#8B5CF6"
                                    fillOpacity={1}
                                    fill="url(#colorRisk)"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                    <div style={{ textAlign: 'right', fontSize: '12px', color: '#4b5563', fontStyle: 'italic', marginTop: '8px' }}>
                        Data Source: St. Louis FED (FRED) • Minsky Model v1.0
                    </div>
                </section>

                <MinskyMarketChart />
                <MinskySignalHistory />

            </div>
        </div>
    );
};

export default MinskyDashboard;
