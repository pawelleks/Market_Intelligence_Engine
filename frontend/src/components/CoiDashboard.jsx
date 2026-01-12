import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
    ResponsiveContainer, ReferenceLine, ComposedChart, Brush, Area
} from 'recharts';
import { ChevronDown, ChevronUp, AlertCircle, Users, Factory, Wallet, Info, AlertTriangle } from 'lucide-react';
import RecessionOverlay from './common/RecessionOverlay';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';
const formatNumber = (val, decimals = 3) => {
    if (val === null || val === undefined || isNaN(val)) return '0.000';
    return Number(val).toFixed(decimals);
};

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
                    color: '#e2e8f0',
                    cursor: 'pointer'
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Icon size={20} style={{ color: '#22c55e' }} />
                    <span style={{ fontWeight: 'bold', fontSize: '16px' }}>{title}</span>
                </div>
                {isOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </button>

            {isOpen && (
                <div style={{ padding: '24px', backgroundColor: 'rgba(17, 24, 39, 0.2)' }}>
                    <p style={{ color: '#9ca3af', fontSize: '14px', lineHeight: '1.6', marginBottom: '20px' }}>
                        {explanation}
                    </p>
                    <div style={{ height: '250px' }}>
                        {children}
                    </div>
                </div>
            )}
        </div>
    );
};

const CoiDashboard = () => {
    const [coiData, setCoiData] = useState([]);
    const [coiLatest, setCoiLatest] = useState(null);
    const [leiLatest, setLeiLatest] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [startIndex, setStartIndex] = useState(0);
    const [endIndex, setEndIndex] = useState(0);
    const [recessionData, setRecessionData] = useState([]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const [coiRes, leiRes] = await Promise.all([
                    axios.get(`${API_BASE_URL}/macro/coi-index`),
                    axios.get(`${API_BASE_URL}/macro/lei-index`)
                ]);
                const fullData = coiRes.data.data;
                setCoiData(fullData);
                setCoiLatest(coiRes.data.latest);
                setLeiLatest(leiRes.data.latest);

                // Default to Max
                setStartIndex(0);
                setEndIndex(fullData.length);

                // Use recession data from COI API response if available
                if (coiRes.data.recessions) {
                    setRecessionData(coiRes.data.recessions);
                }
            } catch (err) {
                console.error("Error fetching COI/LEI data:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const lastUpdateRef = React.useRef(0);
    const setRange = (years) => {
        if (!coiData.length) return;
        if (years === 'Max') {
            setStartIndex(0);
            setEndIndex(coiData.length);
        } else {
            const months = years * 12;
            const start = Math.max(0, coiData.length - months);
            setStartIndex(start);
            setEndIndex(coiData.length);
        }
    };

    if (loading) return <div className="p-8 text-center text-gray-400">Synchronizing Economic Triggers...</div>;
    if (error) return <div className="p-8 text-center text-red-500">Error: {error}</div>;
    if (!coiData || coiData.length === 0) return <div className="p-8 text-center text-gray-400">No data available.</div>;

    const visibleData = coiData.slice(startIndex, Math.min(endIndex + 1, coiData.length));

    const isRecessionActive = coiLatest?.score < 0 && leiLatest?.score < 0;

    // Mini Chart Component
    const MiniChart = ({ data, dataKey, name, color, recessionData }) => (
        <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 20, left: 20, bottom: 25 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} opacity={0.3} />
                <XAxis
                    dataKey="date"
                    hide={false}
                    stroke="#9CA3AF"
                    style={{ fontSize: '9px' }}
                    tick={{ fill: '#9CA3AF' }}
                    tickFormatter={(val) => val ? val.split('-')[0] : ''}
                    interval="preserveStartEnd"
                />
                <YAxis
                    stroke="#9CA3AF"
                    style={{ fontSize: '10px' }}
                    tickFormatter={(val) => formatNumber(val, 1)}
                    domain={['auto', 'auto']}
                />
                <Tooltip
                    contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', fontSize: '11px' }}
                    labelStyle={{ color: '#9ca3af' }}
                    formatter={(val) => [formatNumber(val, 2), name]}
                />
                <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="3 3" />

                {/* Recession Overlay */}
                <RecessionOverlay data={data} recessionData={recessionData} />

                <Line type="monotone" dataKey={dataKey} name={name} stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
        </ResponsiveContainer>
    );

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#0e1525', color: '#d7e3f3', padding: '24px' }}>
            {/* Recession Flashing Banner */}
            {isRecessionActive && (
                <div style={{
                    backgroundColor: '#ef4444',
                    color: 'white',
                    padding: '12px',
                    textAlign: 'center',
                    fontWeight: 'bold',
                    fontSize: '20px',
                    borderRadius: '8px',
                    marginBottom: '24px',
                    animation: 'pulse 1.5s infinite',
                    boxShadow: '0 0 20px rgba(239, 68, 68, 0.5)'
                }}>
                    <style>{`
                        @keyframes pulse {
                            0% { opacity: 1; }
                            50% { opacity: 0.7; }
                            100% { opacity: 1; }
                        }
                    `}</style>
                    ⚠️ RECESSION ACTIVE: LEI & COI CONFIRMATION ⚠️
                </div>
            )}

            {/* Header */}
            <header style={{ marginBottom: '32px', borderBottom: '1px solid #1f2937', paddingBottom: '16px' }}>
                <h1 style={{
                    fontSize: '28px',
                    fontWeight: 'bold',
                    background: 'linear-gradient(to right, #22c55e, #10b981)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    margin: 0
                }}>
                    COI Index (4-Factor Structural)
                </h1>
                <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '8px' }}>
                    NBER-Aligned Reference Model (Employment + Output + Income + GDP)
                </p>
            </header>

            {/* Beta Banner */}
            <div style={{
                padding: '12px 20px',
                backgroundColor: 'rgba(251, 191, 36, 0.1)',
                border: '1px solid #fbbf24',
                borderRadius: '8px',
                color: '#fbbf24',
                fontSize: '14px',
                fontWeight: '500',
                marginBottom: '24px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px'
            }}>
                <AlertTriangle size={18} />
                <span>BETA: This model is under construction and not yet fully calibrated. Historical values may change as the model is refined.</span>
            </div>

            {/* Conclusion Banner */}
            <div style={{
                padding: '24px',
                borderRadius: '8px',
                backgroundColor: coiLatest?.score < 0 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(34, 197, 94, 0.1)',
                border: `1px solid ${coiLatest?.score < 0 ? '#ef4444' : '#22c55e'}`,
                display: 'flex',
                alignItems: 'flex-start',
                gap: '16px',
                marginBottom: '32px'
            }}>
                <Info style={{ color: coiLatest?.score < 0 ? '#ef4444' : '#22c55e', marginTop: '4px' }} />
                <div>
                    <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: 'bold', color: coiLatest?.score < 0 ? '#ef4444' : '#22c55e' }}>Market Intelligence Conclusion</h3>
                    <p style={{ margin: 0, fontSize: '15px', color: '#d1d5db' }}>
                        {coiLatest?.score < 0
                            ? "CRITICAL: The index is signaling an active contraction in physical production and retail volume. Aggregate coincident data suggests the economy is currently in a defensive state."
                            : "STABLE: The index signals continued growth in production and consumption. Current activity remains healthy relative to the long-term trend."
                        }
                    </p>
                </div>
            </div>

            {/* Explanation Section */}
            <AccordionItem
                title="What is the COI Indicator?"
                icon={Info}
                explanation="The Coincident Economic Index (COI) tracks the current state of the economy. Unlike the LEI, which looks forward, the COI identifies what is happening right now in terms of physical production, consumption, and income."
            >
                <div style={{ color: '#d1d5db', fontSize: '14px', lineHeight: '1.6' }}>
                    <p style={{ marginBottom: '12px' }}><strong>Components:</strong> This model focuses on four hard-data pillars: Employment (PAYEMS), Industrial Production (INDPRO), Real Income (W875RX1), and Real GDP (GDPC1). These represent the 'heartbeat' of the structural economy.</p>
                    <p style={{ marginBottom: '12px' }}><strong>Importance:</strong> It serves as the final confirmation of a recession. While the LEI may signal a downturn, the COI confirms the actual start of the contraction or the peak of the cycle.</p>
                    <p><strong>How to Read:</strong> Positive readings confirm ongoing expansion. A crossover below zero, especially when confirmed by the LEI, signifies that the economy has successfully entered a recessionary phase.</p>
                </div>
            </AccordionItem>

            {/* Section 1: The Master Chart */}
            <div style={{
                backgroundColor: 'rgba(31, 41, 55, 0.3)',
                borderRadius: '8px',
                padding: '24px',
                border: '1px solid #1f2937',
                marginBottom: '32px'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                    <div>
                        <h2 style={{ fontSize: '18px', fontWeight: 'bold' }}>Economic Vitality Signal</h2>
                        <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                            {['10', '20', 'Max'].map(range => (
                                <button
                                    key={range}
                                    onClick={() => setRange(range === 'Max' ? 'Max' : parseInt(range))}
                                    style={{
                                        padding: '4px 12px',
                                        backgroundColor: '#1f2937',
                                        border: '1px solid #374151',
                                        borderRadius: '4px',
                                        color: '#9ca3af',
                                        fontSize: '11px',
                                        cursor: 'pointer'
                                    }}
                                >
                                    {range === 'Max' ? 'Full History' : `${range}Y`}
                                </button>
                            ))}
                        </div>
                    </div>
                    {coiLatest && (
                        <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: '11px', color: '#9ca3af' }}>Composite Score</div>
                            <div style={{ fontSize: '20px', fontWeight: 'bold', color: coiLatest.score > 0 ? '#22c55e' : '#ef4444' }}>
                                {formatNumber(coiLatest.score)}
                            </div>
                        </div>
                    )}
                </div>

                <div style={{ height: '500px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart
                            data={coiData}
                            margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                            syncId="coi_dashboard"
                        >
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} opacity={0.5} />
                            <XAxis
                                dataKey="date"
                                stroke="#9CA3AF"
                                style={{ fontSize: '11px' }}
                            />
                            <YAxis domain={['auto', 'auto']} stroke="#9CA3AF" style={{ fontSize: '11px' }} />
                            <Tooltip
                                contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151' }}
                                itemStyle={{ fontSize: '12px' }}
                            />
                            <Legend verticalAlign="top" height={36} />

                            {/* Dummy area for Legend representation of Recession */}
                            <Area
                                name="US Recession (NBER)"
                                dataKey={() => null}
                                stroke="none"
                                fill="#374151"
                                fillOpacity={0.4}
                                legendType="rect"
                            />

                            <ReferenceLine y={0} stroke="#9ca3af" strokeWidth={1} strokeDasharray="3 3" />

                            {/* Recession Overlay */}
                            <RecessionOverlay data={coiData} recessionData={recessionData} />

                            <Line
                                type="monotone"
                                dataKey="coi_composite"
                                name="COI Composite"
                                stroke="#22c55e"
                                strokeWidth={4}
                                dot={false}
                                isAnimationActive={false}
                            />
                            <Line
                                type="monotone"
                                dataKey="signal_line"
                                name="Signal Line (24M SMA)"
                                stroke="#fbbf24"
                                strokeWidth={1.5}
                                dot={false}
                                isAnimationActive={false}
                            />
                            <Brush
                                dataKey="date"
                                height={30}
                                stroke="#374151"
                                fill="#0e1525"
                                onChange={(e) => {
                                    if (e.startIndex !== undefined && e.endIndex !== undefined) {
                                        const now = Date.now();
                                        if (now - lastUpdateRef.current > 30) {
                                            setStartIndex(e.startIndex);
                                            setEndIndex(e.endIndex);
                                            lastUpdateRef.current = now;
                                        }
                                    }
                                }}
                            />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Section 2: Component Breakdown */}
            <div style={{ marginBottom: '32px' }}>
                <h2 style={{ fontSize: '20px', fontWeight: 'bold', marginBottom: '20px' }}>
                    Component Breakdown - Reference 4-Factor Model (10Y Rolling Z-Scores)
                </h2>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '20px' }}>
                    {/* Employment - 35% */}
                    <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.4)', borderRadius: '8px', border: '1px solid #1f2937', padding: '16px 20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <h3 style={{ fontSize: '14px', fontWeight: 'bold', margin: 0 }}>The Labor Market</h3>
                            <span style={{ fontSize: '12px', color: '#6b7280' }}>Weight: 35%</span>
                        </div>
                        <div style={{ height: '120px' }}>
                            <MiniChart data={visibleData} dataKey="z_employment" name="Employment Z-Score" color="#3b82f6" recessionData={recessionData} />
                        </div>
                        <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '15px', lineHeight: '1.4' }}>
                            <strong>Source:</strong> PAYEMS (Total Nonfarm Payrolls). The backbone of economic activity - when people have jobs, they spend.
                        </p>
                    </div>

                    {/* Production - 25% */}
                    <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.4)', borderRadius: '8px', border: '1px solid #1f2937', padding: '16px 20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <h3 style={{ fontSize: '14px', fontWeight: 'bold', margin: 0 }}>Industrial Output</h3>
                            <span style={{ fontSize: '12px', color: '#6b7280' }}>Weight: 25%</span>
                        </div>
                        <div style={{ height: '120px' }}>
                            <MiniChart data={visibleData} dataKey="z_production" name="Production Z-Score" color="#22c55e" recessionData={recessionData} />
                        </div>
                        <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '15px', lineHeight: '1.4' }}>
                            <strong>Source:</strong> INDPRO (Industrial Production Index). Real output from manufacturing, mining, and utilities.
                        </p>
                    </div>

                    {/* Real Income - 20% */}
                    <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.4)', borderRadius: '8px', border: '1px solid #1f2937', padding: '16px 20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <h3 style={{ fontSize: '14px', fontWeight: 'bold', margin: 0 }}>Real Income (NBER)</h3>
                            <span style={{ fontSize: '12px', color: '#6b7280' }}>Weight: 20%</span>
                        </div>
                        <div style={{ height: '120px' }}>
                            <MiniChart data={visibleData} dataKey="z_real_income" name="Real Income Z-Score" color="#fbbf24" recessionData={recessionData} />
                        </div>
                        <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '15px', lineHeight: '1.4' }}>
                            <strong>Source:</strong> W875RX1 (Real Personal Income ex Transfers). NBER's preferred income measure - excludes government handouts.
                        </p>
                    </div>

                    {/* Real GDP - 20% */}
                    <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.4)', borderRadius: '8px', border: '1px solid #1f2937', padding: '16px 20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <h3 style={{ fontSize: '14px', fontWeight: 'bold', margin: 0 }}>Economic Output (GDP)</h3>
                            <span style={{ fontSize: '12px', color: '#6b7280' }}>Weight: 20%</span>
                        </div>
                        <div style={{ height: '120px' }}>
                            <MiniChart data={visibleData} dataKey="z_real_gdp" name="Real GDP Z-Score" color="#a855f7" recessionData={recessionData} />
                        </div>
                        <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '15px', lineHeight: '1.4' }}>
                            <strong>Source:</strong> GDPC1 (Real GDP). The official scorecard - total economic output adjusted for inflation.
                        </p>
                    </div>
                </div>
            </div>

            <footer style={{ marginTop: '48px', color: '#6b7280', fontSize: '11px', textAlign: 'center' }}>
                Coincident indicators reflect current economic activity. When COI {"<"} 0 and LEI {"<"} 0, a business cycle contraction is confirmed.
                <br />
                <span style={{ opacity: 0.7 }}>Shaded grey areas represent official US Recession periods defined by NBER.</span>
            </footer>
        </div>
    );
};

export default CoiDashboard;
