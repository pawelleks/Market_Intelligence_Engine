import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
    ResponsiveContainer, ComposedChart, ReferenceLine, Area
} from 'recharts';
import { Info, AlertTriangle, TrendingUp, Activity, ChevronDown, ChevronUp } from 'lucide-react';
import RecessionOverlay from './common/RecessionOverlay';


const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';
const formatNumber = (val, decimals = 3) => {
    if (val === null || val === undefined || isNaN(val)) return '—';
    return Number(val).toFixed(decimals);
};

// --- Config for Views ---
const VIEW_CONFIG = {
    LEI: {
        title: "Leading Economic Indicators (LEI)",
        description: "Predicts future economic activity (6-12 month lead).",
        mainColor: "#3b82f6", // Blue
        mainKey: "lei",
        smaKey: "lei_sma_17",
        components: [
            {
                key: "z_houst",
                title: "Housing Starts (HOUST)",
                weight: "33.3%",
                explanation: "New residential construction projects. Housing is often the first sector to turn, making it an excellent early warning signal.",
                color: "#60a5fa"
            },
            {
                key: "z_hours",
                title: "Manufacturing Hours (AWHMAN)",
                weight: "33.3%",
                explanation: "Average weekly hours worked in manufacturing. Employers cut hours before laying off staff, providing an early labor market signal.",
                color: "#818cf8"
            },
            {
                key: "z_nfci",
                title: "Financial Conditions (NFCI Inverted)",
                weight: "33.4%",
                explanation: "Credit availability and risk premiums. Inverted because tighter conditions (positive NFCI) correspond to lower growth.",
                color: "#c084fc"
            }
        ]
    },
    COI: {
        title: "Coincident Economic Indicators (COI)",
        description: "Reflects the current state of the economy (Real-time).",
        mainColor: "#22c55e", // Green
        mainKey: "coi",
        smaKey: "coi_sma_17",
        components: [
            {
                key: "z_indpro",
                title: "Industrial Production (INDPRO)",
                weight: "50.0%",
                explanation: "Real output of factories, mines, and utilities. A core measure of real economic activity.",
                color: "#4ade80"
            },
            {
                key: "z_payems",
                title: "Non-Farm Payrolls (PAYEMS)",
                weight: "50.0%",
                explanation: "Total employment. The most visible coincident indicator of economic health.",
                color: "#86efac"
            }
        ]
    }
};

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <div style={{ backgroundColor: '#111827', border: '1px solid #374151', padding: '12px', borderRadius: '4px', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.5)' }}>
                <p style={{ fontWeight: 'bold', color: '#d1d5db', marginBottom: '8px', borderBottom: '1px solid #374151', paddingBottom: '4px' }}>{label}</p>
                {payload.map((entry, idx) => (
                    <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', marginBottom: '4px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: entry.color }} />
                            <span style={{ color: '#9ca3af' }}>{entry.name}:</span>
                        </div>
                        <span style={{ color: '#e5e7eb', fontFamily: 'monospace', fontWeight: 'bold' }}>
                            {formatNumber(entry.value)}
                        </span>
                    </div>
                ))}
            </div>
        );
    }
    return null;
};

// Re-usable Accordion Component
const AccordionItem = ({ title, icon: Icon, children, explanation }) => {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div style={{ marginBottom: '16px', border: '1px solid #1f2937', borderRadius: '8px', overflow: 'hidden' }}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                style={{
                    width: '100%',
                    padding: '16px 20px',
                    backgroundColor: 'rgba(31, 41, 55, 0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    border: 'none',
                    color: '#d7e3f3',
                    cursor: 'pointer'
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Icon size={20} style={{ color: '#60a5fa' }} />
                    <span style={{ fontWeight: 'bold', fontSize: '16px' }}>{title}</span>
                </div>
                {isOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </button>

            {isOpen && (
                <div style={{ padding: '24px', backgroundColor: 'rgba(17, 24, 39, 0.2)' }}>
                    <p style={{ color: '#9ca3af', fontSize: '14px', lineHeight: '1.6', marginBottom: '20px' }}>
                        {explanation}
                    </p>
                    <div>
                        {children}
                    </div>
                </div>
            )}
        </div>
    );
};

// Accept 'mode' prop to force view
const LeiDashboard = ({ mode = 'LEI' }) => {
    const [data, setData] = useState([]);
    const [recessionData, setRecessionData] = useState([]);
    // mode prop overrides internal state logic, so we just use the prop directly
    const viewMode = mode;
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [startIndex, setStartIndex] = useState(0);
    const [endIndex, setEndIndex] = useState(0);

    const activeConfig = VIEW_CONFIG[viewMode];

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const res = await axios.get(`${API_BASE_URL}/economy/lei-coi`);

                // API now returns {data: [...], recessions: [...]}
                const chartData = res.data.data || res.data; // Fallback for backwards compat
                setData(chartData);

                // Use recession data from main API response if available
                if (res.data.recessions) {
                    setRecessionData(res.data.recessions);
                }

                // Default to Max History
                setStartIndex(0);
                setEndIndex(Array.isArray(chartData) ? chartData.length : 0);
            } catch (err) {
                console.error("Error fetching data:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const setRange = (years) => {
        if (!data.length) return;
        if (years === 'Max') {
            setStartIndex(0);
        } else {
            const months = years * 12;
            const start = Math.max(0, data.length - months);
            setStartIndex(start);
        }
        setEndIndex(data.length);
    };

    const slicedData = data.slice(startIndex, endIndex);

    if (loading) return <div className="p-8 text-center text-gray-400">Loading Analysis...</div>;
    if (error) return <div className="p-8 text-center text-red-500">Error: {error}</div>;

    // Get latest data point for signal state calculation
    const latest = data[data.length - 1] || {};

    // Three-tier signal system for LEI
    const getLeiSignalState = (leiValue) => {
        if (leiValue === null || leiValue === undefined || isNaN(leiValue)) {
            return {
                status: 'UNKNOWN',
                color: '#9ca3af',
                bgColor: '#f9fafb',
                borderColor: '#e5e7eb',
                text: 'DATA UNAVAILABLE',
                icon: '⚪',
                description: 'Insufficient data to determine signal state.'
            };
        }

        if (leiValue < -0.4) {
            return {
                status: 'TROUBLE',
                color: '#ef4444',
                bgColor: 'rgba(239, 68, 68, 0.1)',
                borderColor: '#ef4444',
                text: 'TROUBLE (Recession Risk)',
                icon: '🔴',
                description: 'Leading indicators are clearly negative. Recession is likely imminent or starting.'
            };
        } else if (leiValue <= 0.4) {
            return {
                status: 'WARNING',
                color: '#f59e0b',
                bgColor: 'rgba(245, 158, 11, 0.1)',
                borderColor: '#f59e0b',
                text: 'WARNING (Caution)',
                icon: '🟡',
                description: 'Leading indicators are hovering near zero. Economy is weakening but not collapsing. Monitor closely.'
            };
        } else {
            return {
                status: 'CLEAR',
                color: '#22c55e',
                bgColor: 'rgba(34, 197, 94, 0.1)',
                borderColor: '#22c55e',
                text: 'CLEAR (Expansion)',
                icon: '🟢',
                description: 'Leading indicators are positive. Economy has momentum and expansion is expected.'
            };
        }
    };

    // Three-tier signal system for COI
    const getCoiSignalState = (coiValue) => {
        if (coiValue === null || coiValue === undefined || isNaN(coiValue)) {
            return {
                status: 'UNKNOWN',
                color: '#9ca3af',
                bgColor: '#f9fafb',
                borderColor: '#e5e7eb',
                text: 'DATA UNAVAILABLE',
                icon: '⚪',
                description: 'Insufficient data to determine signal state.'
            };
        }

        if (coiValue < -0.4) {
            return {
                status: 'TROUBLE',
                color: '#ef4444',
                bgColor: 'rgba(239, 68, 68, 0.1)',
                borderColor: '#ef4444',
                text: 'RECESSION (Current Contraction)',
                icon: '🔴',
                description: 'Coincident indicators show the economy is currently in recession.'
            };
        } else if (coiValue <= 0.4) {
            return {
                status: 'WARNING',
                color: '#f59e0b',
                bgColor: 'rgba(245, 158, 11, 0.1)',
                borderColor: '#f59e0b',
                text: 'WEAK (Current Softness)',
                icon: '🟡',
                description: 'Current economic conditions are deteriorating but not yet recessionary.'
            };
        } else {
            return {
                status: 'CLEAR',
                color: '#22c55e',
                bgColor: 'rgba(34, 197, 94, 0.1)',
                borderColor: '#22c55e',
                text: 'STRONG (Current Expansion)',
                icon: '🟢',
                description: 'Current economic conditions are positive and expansionary.'
            };
        }
    };

    const signalState = viewMode === 'LEI'
        ? getLeiSignalState(latest[activeConfig.mainKey])
        : getCoiSignalState(latest[activeConfig.mainKey]);

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#0b0f19', color: '#e2e8f0', padding: '32px', fontFamily: 'Inter, sans-serif' }}>

            {/* Header */}
            <div style={{ marginBottom: '32px', paddingBottom: '24px', borderBottom: '1px solid #1e293b' }}>
                <h1 style={{ fontSize: '32px', fontWeight: '700', letterSpacing: '-0.02em', margin: 0, color: '#f8fafc' }}>
                    {activeConfig.title}
                </h1>
                <p style={{ color: '#94a3b8', fontSize: '14px', marginTop: '6px' }}>
                    {activeConfig.description}
                </p>
            </div>

            {/* Status Conclusion Card (Restored) */}
            <div style={{
                padding: '20px',
                borderRadius: '8px',
                backgroundColor: signalState.bgColor,
                border: `2px solid ${signalState.borderColor}`,
                display: 'flex',
                alignItems: 'start',
                gap: '16px',
                marginBottom: '32px'
            }}>
                <span style={{ fontSize: '32px', lineHeight: '1' }}>{signalState.icon}</span>
                <div style={{ flex: 1 }}>
                    <h3 style={{ margin: '0 0 4px 0', fontSize: '18px', fontWeight: 'bold', color: signalState.color }}>
                        System Status: {signalState.text}
                    </h3>
                    <p style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#f8fafc', lineHeight: '1.5' }}>
                        {signalState.description}
                    </p>
                    <div style={{ fontSize: '12px', color: '#cbd5e1' }}>
                        <strong>Current {viewMode}:</strong> {formatNumber(latest[activeConfig.mainKey])}

                        {viewMode === 'LEI' && latest[activeConfig.smaKey] && (
                            <span style={{ marginLeft: '16px' }}>
                                <strong>17-Month SMA:</strong> {formatNumber(latest[activeConfig.smaKey])}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Main Chart Section */}
            <div style={{ backgroundColor: '#151c2c', borderRadius: '12px', padding: '24px', border: '1px solid #2d3748', marginBottom: '32px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#f1f5f9' }}>Composite Index</h2>
                    <div style={{ display: 'flex', gap: '8px' }}>
                        {['10', '20', 'Max'].map(range => (
                            <button
                                key={range}
                                onClick={() => setRange(range)}
                                style={{
                                    padding: '6px 16px',
                                    backgroundColor: '#1e293b',
                                    border: '1px solid #334155',
                                    borderRadius: '6px',
                                    color: '#cbd5e1',
                                    fontSize: '12px',
                                    cursor: 'pointer',
                                    transition: 'hover 0.2s'
                                }}
                            >
                                {range === 'Max' ? 'All' : `${range}Y`}
                            </button>
                        ))}
                    </div>
                </div>

                <div style={{ height: '400px', width: '100%' }}>
                    <ResponsiveContainer>
                        <ComposedChart data={slicedData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }} syncId="economy">
                            <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" vertical={false} />
                            <XAxis dataKey="date" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} minTickGap={50} />
                            <YAxis stroke="#64748b" tick={{ fill: '#64748b', fontSize: 11 }} />
                            <Tooltip content={<CustomTooltip />} />
                            <Legend
                                wrapperStyle={{ paddingTop: '16px' }}
                                payload={[
                                    { value: 'Index Score', type: 'line', color: activeConfig.mainColor },
                                    { value: '17-Month SMA', type: 'line', color: '#f59e0b', payload: { strokeDasharray: '5 5' } },
                                    { value: 'NBER Recession', type: 'rect', color: '#374151', id: 'recession' }
                                ]}
                            />

                            <RecessionOverlay data={slicedData} recessionData={recessionData} />


                            <ReferenceLine y={0} stroke="#475569" strokeWidth={2} label={{ value: "ZERO LINE", fill: "#9ca3af", fontSize: 10, position: 'insideTopRight', dy: -10 }} />
                            {viewMode === 'LEI' && (
                                <>
                                    <ReferenceLine y={0.4} stroke="#22c55e" strokeDasharray="4 4" strokeWidth={1} label={{ value: "CLEAR (0.4)", fill: "#22c55e", fontSize: 10, position: 'insideTopRight', dy: -10 }} />
                                    <ReferenceLine y={-0.4} stroke="#ef4444" strokeDasharray="4 4" strokeWidth={1} label={{ value: "TROUBLE (-0.4)", fill: "#ef4444", fontSize: 10, position: 'insideBottomRight', dy: 10 }} />
                                </>
                            )}

                            <Line
                                type="monotone"
                                dataKey={activeConfig.mainKey}
                                name="Index Score"
                                stroke={activeConfig.mainColor}
                                strokeWidth={3}
                                dot={false}
                                activeDot={{ r: 6, strokeWidth: 0 }}
                            />

                            <Line
                                type="monotone"
                                dataKey={activeConfig.smaKey}
                                name="17-Month SMA"
                                stroke="#f59e0b"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                dot={false}
                            />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Components Stack (Vertical) */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '32px' }}>
                {activeConfig.components.map((comp) => (
                    <div key={comp.key} style={{ backgroundColor: '#151c2c', borderRadius: '12px', border: '1px solid #2d3748', padding: '24px', display: 'flex', flexDirection: 'column' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '16px' }}>
                            <div>
                                <h3 style={{ fontSize: '16px', fontWeight: '600', color: '#e2e8f0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    {comp.title}
                                </h3>
                                <div style={{ fontSize: '13px', color: '#94a3b8', marginTop: '4px', lineHeight: '1.4' }}>
                                    {comp.explanation}
                                </div>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                                <div style={{ fontSize: '20px', fontWeight: '700', color: comp.color }}>
                                    {formatNumber(latest[comp.key])}
                                </div>
                                <span style={{
                                    backgroundColor: '#1e293b',
                                    color: '#94a3b8',
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                    fontSize: '11px',
                                    fontWeight: '600',
                                    display: 'inline-block',
                                    marginTop: '4px'
                                }}>
                                    Weight: {comp.weight}
                                </span>
                            </div>
                        </div>

                        <div style={{ height: '250px', marginTop: 'auto' }}>
                            <ResponsiveContainer>
                                <ComposedChart data={slicedData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }} syncId="economy">
                                    <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" vertical={false} />
                                    <XAxis dataKey="date" hide={true} />
                                    <YAxis stroke="#64748b" tick={{ fill: '#64748b', fontSize: 10 }} />
                                    <Tooltip content={<CustomTooltip />} />
                                    <RecessionOverlay data={slicedData} recessionData={recessionData} />
                                    <ReferenceLine y={0} stroke="#475569" strokeWidth={1} />
                                    <Line
                                        type="monotone"
                                        dataKey={comp.key}
                                        name={comp.title}
                                        stroke={comp.color}
                                        strokeWidth={2}
                                        dot={false}
                                    />
                                </ComposedChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                ))}
            </div>

            {/* Educational Accordion (Restored) */}
            <div style={{ marginTop: '40px' }}>
                <AccordionItem
                    title={`About ${activeConfig.title}`}
                    icon={Info}
                    explanation={`This approach balances various ${viewMode === 'LEI' ? 'forward-looking' : 'coincident'} datasets to create a composite signal.`}
                >
                    <div style={{ color: '#d1d5db', fontSize: '14px', lineHeight: '1.6' }}>
                        {viewMode === 'LEI' ? (
                            <>
                                <p style={{ marginBottom: '12px' }}><strong>Status Logic:</strong> A "WARNING" is triggered when LEI drops below -1.0 standard deviations.</p>
                                <p style={{ marginBottom: '12px' }}><strong>LEI Components:</strong> Housing Permits, Mfg Hours, and Financial Conditions. These sectors tend to slow down before the broader economy.</p>
                            </>
                        ) : (
                            <>
                                <p style={{ marginBottom: '12px' }}><strong>Status Logic:</strong> COI confirms the current cycle state. Divergences between LEI and COI (e.g., LEI crashing while COI rises) are key turning point signals.</p>
                                <p style={{ marginBottom: '12px' }}><strong>COI Components:</strong> Industrial Production and Payrolls. These are the "hard" data points that NBER uses to define recessions.</p>
                            </>
                        )}
                    </div>
                </AccordionItem>
            </div>

            {/* Footer / Meta */}
            <div style={{ marginTop: '32px', borderTop: '1px solid #1e293b', paddingTop: '24px', textAlign: 'center', color: '#64748b', fontSize: '12px' }}>
                <p>Data updated: {latest.date || '—'}</p>
                <p>Standardized Z-Scores (Mean=0, SD=1). Shading indicates recessionary periods.</p>
            </div>
        </div>
    );
};

export default LeiDashboard;
