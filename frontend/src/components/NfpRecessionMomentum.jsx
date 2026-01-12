import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
    ResponsiveContainer, ReferenceLine, ReferenceArea
} from 'recharts';
import { Share2 } from 'lucide-react';

import useSocialExport from '../hooks/useSocialExport';
import HiddenRenderViewport from './common/SocialExport/HiddenRenderViewport';
import SocialCardTemplate from './common/SocialExport/SocialCardTemplate';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const NfpRecessionMomentum = () => {
    const [data, setData] = useState([]);
    const [metadata, setMetadata] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [scaleMode, setScaleMode] = useState('focus'); // 'focus' or 'full'

    const exportRef = useRef();
    const { exportImage, isExporting } = useSocialExport(exportRef, 'nfp-momentum-analysis.png');

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const res = await axios.get(`${API_BASE_URL}/macro/nfp-model`);
                setData(res.data.data);
                setMetadata(res.data.metadata);
            } catch (err) {
                console.error("Error fetching NFP model data:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return <div className="p-8 text-center text-gray-400">Loading Labor Momentum Model...</div>;
    if (error) return <div className="p-8 text-center text-red-500">Error: {error}</div>;

    // Logic for Interpretation Card
    const getInterpretation = () => {
        if (!data || data.length === 0) return null;
        const lastPoint = data[data.length - 1];
        const smaValue = lastPoint.nfp_sma_12m;

        if (smaValue > 120000) {
            return {
                status: "Safe",
                title: "Labor Market Robust",
                text: "The 12-month trend is safely above stall speed. No immediate recession signal.",
                color: "green",
                icon: "✅"
            };
        } else if (smaValue >= 97000) {
            return {
                status: "Caution",
                title: "Slowing Momentum",
                text: "The labor trend is deteriorating and approaching the stall speed. Caution advised.",
                color: "yellow",
                icon: "⚠️"
            };
        } else {
            return {
                status: "Danger",
                title: "RECESSION SIGNAL TRIGGERED",
                text: "The economy has breached the labor stall speed (<97k). Historically, this precedes a recession.",
                color: "red",
                icon: "🚨"
            };
        }
    };

    const interpretation = getInterpretation();

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
                                {(entry.value / 1000).toFixed(1)}k
                            </span>
                        </div>
                    ))}
                    <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #374151', fontSize: '11px' }}>
                        <span style={{ color: payload[0].payload.recession_signal ? '#ef4444' : '#22c55e' }}>
                            Status: {payload[0].payload.regime}
                        </span>
                    </div>
                </div>
            );
        }
        return null;
    };

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#0e1525', color: '#d7e3f3', padding: '24px' }}>
            {/* Header */}
            <header style={{ marginBottom: '32px', borderBottom: '1px solid #1f2937', paddingBottom: '16px' }}>
                <h1 style={{
                    fontSize: '28px',
                    fontWeight: 'bold',
                    background: 'linear-gradient(to right, #60a5fa, #ef4444)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    margin: 0
                }}>
                    NFP Macro-Momentum Recession Model
                </h1>
                <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '8px' }}>
                    Tracking Labor Market "Stall Speed" (12M SMA of Nonfarm Payrolls Change)
                </p>

                {/* Scale Toggle */}
                <div style={{ marginTop: '20px', display: 'flex', gap: '8px' }}>
                    <button
                        onClick={() => setScaleMode('focus')}
                        style={{
                            padding: '6px 12px',
                            backgroundColor: scaleMode === 'focus' ? '#3b82f6' : '#1f2937',
                            color: 'white',
                            border: '1px solid #374151',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '12px'
                        }}
                    >
                        Focus View (Clipped)
                    </button>
                    <button
                        onClick={() => setScaleMode('full')}
                        style={{
                            padding: '6px 12px',
                            backgroundColor: scaleMode === 'full' ? '#3b82f6' : '#1f2937',
                            color: 'white',
                            border: '1px solid #374151',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '12px'
                        }}
                    >
                        Full History
                    </button>

                    <button
                        onClick={exportImage}
                        disabled={isExporting}
                        style={{
                            marginLeft: 'auto',
                            padding: '6px 16px',
                            backgroundColor: '#3b82f6',
                            color: 'white',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: isExporting ? 'not-allowed' : 'pointer',
                            fontSize: '13px',
                            fontWeight: 'bold',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            opacity: isExporting ? 0.6 : 1,
                            transition: 'all 0.2s'
                        }}
                    >
                        <Share2 size={16} />
                        {isExporting ? 'Generating...' : 'Export to X'}
                    </button>
                </div>
            </header>

            {/* Analysis Card */}
            {interpretation && (
                <div style={{
                    marginBottom: '32px',
                    padding: '24px',
                    backgroundColor: 'rgba(31, 41, 55, 0.4)',
                    borderRadius: '8px',
                    border: `2px solid ${interpretation.color === 'green' ? '#22c55e' : interpretation.color === 'yellow' ? '#f59e0b' : '#ef4444'}`,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '20px'
                }}>
                    <div style={{ fontSize: '40px' }}>{interpretation.icon}</div>
                    <div>
                        <h2 style={{
                            fontSize: '20px',
                            fontWeight: 'bold',
                            color: interpretation.color === 'green' ? '#22c55e' : interpretation.color === 'yellow' ? '#f59e0b' : '#ef4444',
                            margin: '0 0 4px 0'
                        }}>
                            {interpretation.title}
                        </h2>
                        <p style={{ margin: 0, color: '#d1d5db', fontSize: '15px' }}>
                            {interpretation.text}
                        </p>
                    </div>
                    {metadata && (
                        <div style={{ marginLeft: 'auto', textAlign: 'right', minWidth: '150px' }}>
                            <div style={{ fontSize: '12px', color: '#9ca3af' }}>Current 12M SMA</div>
                            <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{metadata.current_sma}</div>
                        </div>
                    )}
                </div>
            )}

            {/* Chart Container */}
            <div style={{
                height: '600px',
                backgroundColor: 'rgba(31, 41, 55, 0.3)',
                borderRadius: '8px',
                padding: '24px',
                border: '1px solid #1f2937',
                marginBottom: '48px'
            }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data} margin={{ top: 20, right: 30, left: 40, bottom: 60 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} opacity={0.5} />
                        <XAxis
                            dataKey="date"
                            stroke="#9CA3AF"
                            angle={-45}
                            textAnchor="end"
                            height={80}
                            interval={Math.floor(data.length / 20)}
                            style={{ fontSize: '11px' }}
                        />
                        <YAxis
                            stroke="#9CA3AF"
                            tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
                            style={{ fontSize: '11px' }}
                            domain={scaleMode === 'focus' ? [-800000, 1000000] : ['auto', 'auto']}
                            allowDataOverflow={scaleMode === 'focus'}
                        />
                        <Tooltip content={<CustomTooltip />} />
                        <Legend wrapperStyle={{ paddingTop: '20px' }} />

                        {/* Note on Clipping */}
                        {scaleMode === 'focus' && (
                            <ReferenceLine
                                alwaysShow
                                stroke="transparent"
                                label={{
                                    position: 'insideBottomRight',
                                    value: 'Note: Y-axis clipped. COVID-19 volatility (2020) extends beyond view.',
                                    fill: '#6b7280',
                                    fontSize: 10,
                                    offset: 20
                                }}
                            />
                        )}

                        {/* Reference Line at Stall Speed (97,000) */}
                        <ReferenceLine
                            y={97000}
                            stroke="#ffffff"
                            strokeDasharray="5 5"
                            strokeWidth={2}
                            label={{ position: 'top', value: 'Stall Speed (97k)', fill: '#ffffff', fontSize: 12 }}
                        />

                        {/* Danger Zone Highlight */}
                        <ReferenceArea
                            y1={scaleMode === 'focus' ? -800000 : undefined}
                            y2={97000}
                            fill="#ef4444"
                            fillOpacity={0.05}
                        />
                        <ReferenceLine
                            y={97000}
                            stroke="transparent"
                            label={{ position: 'insideBottomLeft', value: 'RECESSION RISK ZONE', fill: '#ef4444', fontSize: 10, opacity: 0.5, offset: 10 }}
                        />

                        {/* Recession Risk Highlight Areas */}
                        {/* We could use ReferenceArea but it needs data start/end which is complex with multiple triggers.
                            Alternatively, we can use a secondary line/area.
                            For simplicity and visual pop, let's keep it as requested: "visual marker".
                        */}

                        {/* Line A: Monthly NFP Change (Thin Blue) */}
                        <Line
                            type="monotone"
                            dataKey="nfp_mom"
                            name="Monthly NFP Change"
                            stroke="#60a5fa"
                            strokeWidth={1}
                            dot={false}
                            opacity={0.6}
                        />

                        {/* Line B: 12-Month SMA (Thick Red) */}
                        <Line
                            type="monotone"
                            dataKey="nfp_sma_12m"
                            name="12-Month Trend (SMA)"
                            stroke="#ef4444"
                            strokeWidth={3}
                            dot={false}
                        />

                    </LineChart>
                </ResponsiveContainer>
            </div>

            {/* Footer / Methodology */}
            <footer style={{
                marginTop: 'auto',
                padding: '24px',
                borderTop: '1px solid #1f2937',
                color: '#6b7280',
                fontSize: '13px',
                lineHeight: '1.6'
            }}>
                <p style={{ margin: 0 }}>
                    <strong>Methodology:</strong> Tracks the momentum of US Nonfarm Payrolls.
                    A 12-month trend (SMA) below <strong>+97k jobs/month</strong> has historically signaled a 100% probability of recession
                    due to the economy losing sufficient job-creation velocity to stay above "stall speed".
                </p>
                <p style={{ marginTop: '8px' }}>
                    Data Source: FRED (API: PAYEMS). Analysis identifies Phase Transitions in labor market dynamics.
                </p>
            </footer>

            {/* HIDDEN EXPORT VIEWPORT */}
            <HiddenRenderViewport innerRef={exportRef}>
                <SocialCardTemplate
                    title="NFP Macro-Momentum Analysis"
                    subtitle={`${new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })} • Labor Market Stall Speed Model`}
                >
                    <div className="flex flex-col h-full gap-6">
                        {/* 1. Conclusion Badge for Export */}
                        {interpretation && (
                            <div className="bg-slate-800/60 p-6 rounded-2xl border-2 flex items-center gap-6"
                                style={{ borderColor: interpretation.color === 'green' ? '#22c55e' : interpretation.color === 'yellow' ? '#f59e0b' : '#ef4444' }}
                            >
                                <div className="text-6xl">{interpretation.icon}</div>
                                <div>
                                    <div className="text-sm uppercase tracking-widest text-slate-400 font-bold mb-1">Model Consensus</div>
                                    <h2 className="text-4xl font-extrabold"
                                        style={{ color: interpretation.color === 'green' ? '#22c55e' : interpretation.color === 'yellow' ? '#f59e0b' : '#ef4444' }}
                                    >
                                        {interpretation.status.toUpperCase()}: {interpretation.title}
                                    </h2>
                                </div>
                                {metadata && (
                                    <div className="ml-auto text-right">
                                        <div className="text-xs text-slate-500 uppercase font-bold">12M SMA Velocity</div>
                                        <div className="text-4xl font-black text-white">{metadata.current_sma}</div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* 2. Optimized Chart for Export */}
                        <div className="flex-grow min-h-0 bg-slate-800/30 rounded-xl p-4 border border-slate-700/50">
                            <LineChart data={data} width={1050} height={320} margin={{ top: 10, right: 30, left: 20, bottom: 20 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                                <XAxis
                                    dataKey="date"
                                    stroke="#94a3b8"
                                    tick={{ fontSize: 16, fontWeight: '600' }}
                                    interval={Math.floor(data.length / 10)}
                                />
                                <YAxis
                                    stroke="#94a3b8"
                                    tick={{ fontSize: 16, fontWeight: '600' }}
                                    tickFormatter={(val) => `${(val / 1000).toFixed(0)}k`}
                                />

                                {/* Stall Speed Line - Much thicker for export */}
                                <ReferenceLine
                                    y={97000}
                                    stroke="#ffffff"
                                    strokeDasharray="8 8"
                                    strokeWidth={4}
                                    label={{ position: 'top', value: 'STALL SPEED (97k)', fill: '#ffffff', fontSize: 16, fontWeight: 'bold' }}
                                />

                                {/* Danger Zone */}
                                <ReferenceArea y1={-800000} y2={97000} fill="#ef4444" fillOpacity={0.1} />

                                <Line
                                    type="monotone"
                                    dataKey="nfp_mom"
                                    stroke="#3b82f6"
                                    strokeWidth={2}
                                    dot={false}
                                    opacity={0.4}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="nfp_sma_12m"
                                    stroke="#ef4444"
                                    strokeWidth={10} // Extremely thick for mobile clarity
                                    dot={false}
                                />
                            </LineChart>
                        </div>
                    </div>
                </SocialCardTemplate>
            </HiddenRenderViewport>
        </div>
    );
};

export default NfpRecessionMomentum;
