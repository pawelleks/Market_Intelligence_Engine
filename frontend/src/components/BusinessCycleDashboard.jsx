import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
    ResponsiveContainer, ReferenceLine, Area, ComposedChart, Brush
} from 'recharts';
import { Activity, TrendingUp, TrendingDown, AlertTriangle, Info } from 'lucide-react';
import RecessionOverlay from './common/RecessionOverlay';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const formatNumber = (val, decimals = 2) => {
    if (val === null || val === undefined || isNaN(val)) return '-';
    return Number(val).toFixed(decimals);
};

const BusinessCycleDashboard = () => {
    const [data, setData] = useState([]);
    const [latest, setLatest] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [startIndex, setStartIndex] = useState(0);
    const [endIndex, setEndIndex] = useState(0);
    const [recessionData, setRecessionData] = useState([]);

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            setLoading(true);
            const res = await axios.get(`${API_BASE_URL}/macro/business-cycle`);
            const fullData = res.data.data;

            // Calculate 12M moving averages for each indicator
            const dataWithMA = fullData.map((row, idx, arr) => {
                const window = 12;
                const start = Math.max(0, idx - window + 1);
                const slice = arr.slice(start, idx + 1);

                const lei_ma12 = slice.reduce((sum, r) => sum + (r.lei_final || 0), 0) / slice.length;
                const coi_ma12 = slice.reduce((sum, r) => sum + (r.coi_final || 0), 0) / slice.length;
                const lag_ma12 = slice.reduce((sum, r) => sum + (r.lag_composite || 0), 0) / slice.length;

                return {
                    ...row,
                    lei_ma12,
                    coi_ma12,
                    lag_ma12
                };
            });

            setData(dataWithMA);
            setLatest(res.data.latest);

            // Set initial range to 50 years
            const fiftyYearsAgo = Math.max(0, dataWithMA.length - 600); // 50 years * 12 months
            setStartIndex(fiftyYearsAgo);
            setEndIndex(dataWithMA.length - 1);

            // Fetch recession data (now embedded in main response)
            if (res.data.recessions) {
                setRecessionData(res.data.recessions);
            }

            setError(null);
        } catch (err) {
            console.error('Failed to fetch business cycle data:', err);
            setError('Failed to load business cycle data. Please ensure the Economic Pipeline has been run.');
        } finally {
            setLoading(false);
        }
    };

    const setRange = (years) => {
        if (data.length === 0) return;
        const months = years * 12;
        const newStart = Math.max(0, data.length - months);
        setStartIndex(newStart);
        setEndIndex(data.length - 1);
    };

    const getCyclePhaseColor = (phase) => {
        switch (phase) {
            case 'Recovery': return '#10b981'; // green
            case 'Expansion': return '#3b82f6'; // blue
            case 'Slowdown': return '#f59e0b'; // yellow/orange
            case 'Recession': return '#ef4444'; // red
            default: return '#6b7280'; // gray
        }
    };

    const getCyclePhaseIcon = (phase) => {
        switch (phase) {
            case 'Recovery': return TrendingUp;
            case 'Expansion': return Activity;
            case 'Slowdown': return TrendingDown;
            case 'Recession': return AlertTriangle;
            default: return Info;
        }
    };

    const getCycleDescription = (phase) => {
        switch (phase) {
            case 'Recovery':
                return 'Relative positioning shows recovery pattern (LEI > COI > LAG). See signal strength below for absolute assessment.';
            case 'Expansion':
                return 'Broad-based growth pattern. All indicators positive. Check signal strength for momentum assessment.';
            case 'Slowdown':
                return 'Late cycle pattern detected (LAG > LEI). Monitor signal strength for severity.';
            case 'Recession':
                return 'Contraction pattern confirmed (deeply negative LEI). Signal strength shows recession depth.';
            default:
                return 'Unknown cycle phase.';
        }
    };

    const getSignalStrength = (lei, coi) => {
        // Using thresholds from Signal Definitions:
        // STRONG: > 0.4
        // MODERATE: -0.4 to 0.4
        // WEAK: < -0.4

        const leiStrength = lei > 0.4 ? 'STRONG' : lei < -0.4 ? 'WEAK' : 'MODERATE';
        const coiStrength = coi > 0.4 ? 'STRONG' : coi < -0.4 ? 'WEAK' : 'MODERATE';

        // Overall strength (worst of the two)
        if (leiStrength === 'WEAK' || coiStrength === 'WEAK') {
            return {
                level: 'WEAK',
                color: '#ef4444',
                bgColor: '#fef2f2',
                icon: AlertTriangle,
                description: 'Both LEI and COI are near zero or negative. While cycle phase shows relative positioning, absolute values indicate cautious conditions.'
            };
        } else if (leiStrength === 'MODERATE' || coiStrength === 'MODERATE') {
            return {
                level: 'MODERATE',
                color: '#f59e0b',
                bgColor: '#fffbeb',
                icon: Info,
                description: 'LEI and COI are in moderate territory. Cycle phase is developing but not yet strong.'
            };
        } else {
            return {
                level: 'STRONG',
                color: '#22c55e',
                bgColor: '#f0fdf4',
                icon: TrendingUp,
                description: 'Both LEI and COI are positive and healthy. Cycle phase is well-established.'
            };
        }
    };

    if (loading) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px', color: '#9ca3af' }}>
                <div>Loading business cycle data...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div style={{ padding: '40px', textAlign: 'center' }}>
                <AlertTriangle size={48} style={{ color: '#ef4444', margin: '0 auto 20px' }} />
                <h2 style={{ color: '#ef4444', marginBottom: '10px' }}>Error Loading Data</h2>
                <p style={{ color: '#9ca3af' }}>{error}</p>
                <p style={{ color: '#6b7280', marginTop: '20px', fontSize: '14px' }}>
                    Go to <strong>Data Management → Economic Pipeline</strong> and click "Run Pipeline"
                </p>
            </div>
        );
    }

    const displayData = data.slice(startIndex, endIndex + 1);
    const currentPhase = latest?.cycle_phase || 'Unknown';
    const phaseColor = getCyclePhaseColor(currentPhase);
    const PhaseIcon = getCyclePhaseIcon(currentPhase);

    // Calculate signal strength
    const signalStrength = getSignalStrength(latest?.lei_final || 0, latest?.coi_final || 0);
    const StrengthIcon = signalStrength.icon;

    return (
        <div style={{ padding: '20px', color: '#e0e0e0' }}>
            {/* Header */}
            <div style={{ marginBottom: '30px' }}>
                <h1 style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '8px', color: '#fff' }}>
                    Business Cycle Analysis
                </h1>
                <p style={{ color: '#9ca3af', fontSize: '16px' }}>
                    Tracks economic cycle phases using LEI, COI, and LAG indicators
                </p>
            </div>

            {/* Current Cycle Phase Badge */}
            <div style={{
                backgroundColor: '#162032',
                border: `2px solid ${phaseColor}`,
                borderRadius: '12px',
                padding: '24px',
                marginBottom: '16px'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
                    <div style={{
                        padding: '12px',
                        borderRadius: '8px',
                        backgroundColor: `${phaseColor}20`,
                        color: phaseColor
                    }}>
                        <PhaseIcon size={32} />
                    </div>
                    <div style={{ flex: 1 }}>
                        <div style={{ color: '#9ca3af', fontSize: '14px', marginBottom: '4px' }}>CURRENT CYCLE PHASE</div>
                        <div style={{ fontSize: '28px', fontWeight: 'bold', color: phaseColor }}>{currentPhase}</div>
                    </div>
                </div>
                <p style={{ color: '#cbd5e1', fontSize: '15px', lineHeight: '1.6', margin: 0 }}>
                    {getCycleDescription(currentPhase)}
                </p>
            </div>

            {/* Signal Strength Badge */}
            <div style={{
                backgroundColor: signalStrength.bgColor,
                border: `2px solid ${signalStrength.color}`,
                borderRadius: '12px',
                padding: '20px',
                marginBottom: '30px'
            }}>
                <div style={{ display: 'flex', alignItems: 'start', gap: '16px' }}>
                    <div style={{
                        padding: '10px',
                        borderRadius: '8px',
                        backgroundColor: `${signalStrength.color}20`,
                        color: signalStrength.color
                    }}>
                        <StrengthIcon size={24} />
                    </div>
                    <div style={{ flex: 1 }}>
                        <h3 style={{
                            color: signalStrength.color,
                            margin: 0,
                            fontSize: '18px',
                            fontWeight: 'bold',
                            marginBottom: '8px'
                        }}>
                            SIGNAL STRENGTH: {signalStrength.level}
                        </h3>
                        <p style={{
                            fontSize: '14px',
                            color: '#1f2937',
                            margin: '0 0 12px 0',
                            lineHeight: '1.6'
                        }}>
                            {signalStrength.description}
                        </p>
                        <div style={{
                            fontSize: '13px',
                            color: '#4b5563',
                            fontFamily: 'monospace',
                            backgroundColor: 'rgba(0,0,0,0.05)',
                            padding: '8px 12px',
                            borderRadius: '6px',
                            display: 'inline-block'
                        }}>
                            LEI: {formatNumber(latest?.lei_final, 2)} | COI: {formatNumber(latest?.coi_final, 2)}
                        </div>
                    </div>
                </div>
            </div>

            {/* Key Metrics Grid */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '16px',
                marginBottom: '30px'
            }}>
                <div style={{ backgroundColor: '#162032', padding: '16px', borderRadius: '8px', border: '1px solid #1e293b' }}>
                    <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '4px' }}>LEI (Leading)</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: latest?.lei_final > 0 ? '#10b981' : '#ef4444' }}>
                        {formatNumber(latest?.lei_final, 2)}
                    </div>
                </div>
                <div style={{ backgroundColor: '#162032', padding: '16px', borderRadius: '8px', border: '1px solid #1e293b' }}>
                    <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '4px' }}>COI (Coincident)</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: latest?.coi_final > 0 ? '#10b981' : '#ef4444' }}>
                        {formatNumber(latest?.coi_final, 2)}
                    </div>
                </div>
                <div style={{ backgroundColor: '#162032', padding: '16px', borderRadius: '8px', border: '1px solid #1e293b' }}>
                    <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '4px' }}>LAG (Lagging)</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: latest?.lag_composite > 0 ? '#ef4444' : '#10b981' }}>
                        {formatNumber(latest?.lag_composite, 2)}
                    </div>
                </div>
                <div style={{ backgroundColor: '#162032', padding: '16px', borderRadius: '8px', border: '1px solid #1e293b' }}>
                    <div style={{ color: '#9ca3af', fontSize: '12px', marginBottom: '4px' }}>Recession Probability</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ef4444' }}>
                        {formatNumber((latest?.recession_prob || 0) * 100, 0)}%
                    </div>
                </div>
            </div>

            {/* Time Range Selector */}
            <div style={{ marginBottom: '20px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {[5, 10, 20, 50].map(years => (
                    <button
                        key={years}
                        onClick={() => setRange(years)}
                        style={{
                            padding: '8px 16px',
                            backgroundColor: '#1e293b',
                            color: '#e2e8f0',
                            border: '1px solid #334155',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            fontSize: '14px'
                        }}
                    >
                        {years}Y
                    </button>
                ))}
                <button
                    onClick={() => { setStartIndex(0); setEndIndex(data.length - 1); }}
                    style={{
                        padding: '8px 16px',
                        backgroundColor: '#1e293b',
                        color: '#e2e8f0',
                        border: '1px solid #334155',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '14px'
                    }}
                >
                    All
                </button>
            </div>

            {/* LEI Chart */}
            <div style={{
                backgroundColor: '#0f172a',
                padding: '24px',
                borderRadius: '12px',
                marginBottom: '16px',
                border: '1px solid #1e293b'
            }}>
                <h2 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '16px', color: '#f1f5f9' }}>
                    Leading Economic Indicator (LEI)
                </h2>
                <ResponsiveContainer width="100%" height={250}>
                    <ComposedChart data={displayData} syncId="businessCycle">
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis
                            dataKey="date"
                            stroke="#94a3b8"
                            tick={{ fill: '#94a3b8', fontSize: 12 }}
                        />
                        <YAxis stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: '#1e293b',
                                border: '1px solid #334155',
                                borderRadius: '8px',
                                color: '#e2e8f0'
                            }}
                        />
                        <Legend wrapperStyle={{ color: '#cbd5e1' }} />
                        <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" />

                        <RecessionOverlay data={displayData} recessionData={recessionData} />

                        <Line
                            type="monotone"
                            dataKey="lei_final"
                            name="LEI"
                            stroke="#10b981"
                            strokeWidth={2}
                            dot={false}
                        />
                        <Line
                            type="monotone"
                            dataKey="lei_ma12"
                            name="LEI 12M Avg"
                            stroke="#fbbf24"
                            strokeWidth={2}
                            strokeDasharray="5 5"
                            dot={false}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>

            {/* COI Chart */}
            <div style={{
                backgroundColor: '#0f172a',
                padding: '24px',
                borderRadius: '12px',
                marginBottom: '16px',
                border: '1px solid #1e293b'
            }}>
                <h2 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '16px', color: '#f1f5f9' }}>
                    Coincident Indicator (COI)
                </h2>
                <ResponsiveContainer width="100%" height={250}>
                    <ComposedChart data={displayData} syncId="businessCycle">
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis
                            dataKey="date"
                            stroke="#94a3b8"
                            tick={{ fill: '#94a3b8', fontSize: 12 }}
                        />
                        <YAxis stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: '#1e293b',
                                border: '1px solid #334155',
                                borderRadius: '8px',
                                color: '#e2e8f0'
                            }}
                        />
                        <Legend wrapperStyle={{ color: '#cbd5e1' }} />
                        <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" />

                        <RecessionOverlay data={displayData} recessionData={recessionData} />

                        <Line
                            type="monotone"
                            dataKey="coi_final"
                            name="COI"
                            stroke="#3b82f6"
                            strokeWidth={2}
                            dot={false}
                        />
                        <Line
                            type="monotone"
                            dataKey="coi_ma12"
                            name="COI 12M Avg"
                            stroke="#a78bfa"
                            strokeWidth={2}
                            strokeDasharray="5 5"
                            dot={false}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>

            {/* LAG Chart */}
            <div style={{
                backgroundColor: '#0f172a',
                padding: '24px',
                borderRadius: '12px',
                marginBottom: '24px',
                border: '1px solid #1e293b'
            }}>
                <h2 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '16px', color: '#f1f5f9' }}>
                    Lagging Indicator (LAG)
                </h2>
                <ResponsiveContainer width="100%" height={250}>
                    <ComposedChart data={displayData} syncId="businessCycle">
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis
                            dataKey="date"
                            stroke="#94a3b8"
                            tick={{ fill: '#94a3b8', fontSize: 12 }}
                        />
                        <YAxis stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: '#1e293b',
                                border: '1px solid #334155',
                                borderRadius: '8px',
                                color: '#e2e8f0'
                            }}
                        />
                        <Legend wrapperStyle={{ color: '#cbd5e1' }} />
                        <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" />

                        <RecessionOverlay data={displayData} recessionData={recessionData} />

                        <Line
                            type="monotone"
                            dataKey="lag_composite"
                            name="LAG"
                            stroke="#ef4444"
                            strokeWidth={2}
                            dot={false}
                        />
                        <Line
                            type="monotone"
                            dataKey="lag_ma12"
                            name="LAG 12M Avg"
                            stroke="#fb923c"
                            strokeWidth={2}
                            strokeDasharray="5 5"
                            dot={false}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>

            {/* Cycle Phase Interpretation */}
            <div style={{
                backgroundColor: '#0f172a',
                padding: '24px',
                borderRadius: '12px',
                marginBottom: '24px',
                border: '1px solid #1e293b'
            }}>
                <h2 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '16px', color: '#f1f5f9' }}>
                    Understanding Business Cycle Phases
                </h2>
                <div style={{ display: 'grid', gap: '16px' }}>
                    {['Recovery', 'Expansion', 'Slowdown', 'Recession'].map(phase => {
                        const Icon = getCyclePhaseIcon(phase);
                        const color = getCyclePhaseColor(phase);
                        return (
                            <div
                                key={phase}
                                style={{
                                    display: 'flex',
                                    alignItems: 'start',
                                    gap: '12px',
                                    padding: '16px',
                                    backgroundColor: '#162032',
                                    borderRadius: '8px',
                                    border: `1px solid ${phase === currentPhase ? color : '#1e293b'}`,
                                    opacity: phase === currentPhase ? 1 : 0.6
                                }}
                            >
                                <div style={{ padding: '8px', borderRadius: '6px', backgroundColor: `${color}20`, color }}>
                                    <Icon size={20} />
                                </div>
                                <div style={{ flex: 1 }}>
                                    <div style={{ fontSize: '16px', fontWeight: 'bold', color, marginBottom: '4px' }}>
                                        {phase}
                                        {phase === currentPhase && <span style={{ marginLeft: '8px', fontSize: '12px', color: '#10b981' }}>(Current)</span>}
                                    </div>
                                    <div style={{ color: '#cbd5e1', fontSize: '14px', lineHeight: '1.6' }}>
                                        {getCycleDescription(phase)}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* About Section */}
            <div style={{
                backgroundColor: '#0f172a',
                padding: '24px',
                borderRadius: '12px',
                border: '1px solid #1e293b'
            }}>
                <h2 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '12px', color: '#f1f5f9' }}>
                    About Business Cycle Analysis
                </h2>
                <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: '1.8', marginBottom: '12px' }}>
                    This model combines Leading (LEI), Coincident (COI), and Lagging (LAG) economic indicators to identify
                    the current phase of the business cycle. The methodology tracks the relative positions of these three
                    indicator categories to determine whether the economy is in Recovery, Expansion, Slowdown, or Recession.
                </p>
                <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: '1.8' }}>
                    <strong style={{ color: '#cbd5e1' }}>Phase Logic:</strong> When LEI rises first (leading recovery),
                    followed by COI catching up, we're in Recovery. When all three are positive and aligned, it's Expansion.
                    When LAG indicators oversheat while LEI cools, it signals Slowdown. A deep negative LEI confirms Recession.
                </p>
            </div>
        </div>
    );
};

export default BusinessCycleDashboard;
