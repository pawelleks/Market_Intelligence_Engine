import React, { useState, useEffect, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Loader2, Activity, RefreshCw, Trophy, Info, Filter } from "lucide-react";

import { usePageTitle } from '../hooks/usePageTitle';

const HMMBacktestPage = () => {
    usePageTitle('HMM Backtest Analysis');
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    const [selectedConfig, setSelectedConfig] = useState(null); // Key like "3_10"
    const [ticker, setTicker] = useState("SPY");
    const [windowFilter, setWindowFilter] = useState("All"); // "All", "5", "10", "20", "Max"

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`/api/v1/hmm/backtest/${ticker}`);
            if (res.status === 404) throw new Error(`Analysis not found for ${ticker}. Run Backtest first.`);
            if (!res.ok) throw new Error("API Error");

            const json = await res.json();
            setData(json);

            // Auto-select winner if not already selected
            if (!selectedConfig && json.summary && json.summary.length > 0) {
                const sorted = [...json.summary].sort((a, b) => b.strat_sharpe - a.strat_sharpe);
                const winner = sorted[0];
                setSelectedConfig(`${winner.n_states}_${winner.train_window_years}`);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [ticker]);

    // --- Styling Constants ---
    const colors = {
        bg: '#0b1220',
        panelBg: '#0e1525',
        border: '#203049',
        text: '#d7e3f3',
        textMuted: '#9e9e9e',
        headerText: '#9ec4ff',
        accent: '#2196f3',
        success: '#4caf50',
        danger: '#f44336',
        warning: '#ff9800',
    };

    // --- Helpers & Computed ---
    const getChartData = () => {
        if (!data || !selectedConfig) return [];
        return data.curves[selectedConfig] || [];
    };

    const getMatrixData = () => {
        if (!data) return {};
        const matrix = {};
        data.summary.forEach(row => {
            const s = row.n_states;
            const w = row.train_window_years;
            if (!matrix[s]) matrix[s] = {};
            matrix[s][w] = row.strat_sharpe;
        });
        return matrix;
    };

    const matrix = getMatrixData();
    const allWindows = [1, 5, 10, 15, 20, 25, 50, "Max"];

    // Filter logic
    const filteredSummary = useMemo(() => {
        if (!data) return [];
        if (windowFilter === "All") return data.summary;
        return data.summary.filter(r => String(r.train_window_years) === windowFilter || (windowFilter === "Max" && r.train_window_years === "Max"));
    }, [data, windowFilter]);

    // Best Performers Logic
    const bestSharpe = useMemo(() => {
        if (!data || data.summary.length === 0) return null;
        return [...data.summary].sort((a, b) => b.strat_sharpe - a.strat_sharpe)[0];
    }, [data]);

    const bestReturn = useMemo(() => {
        if (!data || data.summary.length === 0) return null;
        return [...data.summary].sort((a, b) => b.strat_total_ret - a.strat_total_ret)[0];
    }, [data]);


    // --- Render ---

    if (loading) return (
        <div style={{ padding: '40px', textAlign: 'center', color: colors.textMuted }}>
            <Loader2 style={{ width: 24, height: 24, animation: 'spin 1s linear infinite', marginRight: 10, verticalAlign: 'middle' }} />
            Loading Analysis...
        </div>
    );

    if (error) return (
        <div style={{ padding: '20px', color: colors.text }}>
            <div style={{ backgroundColor: '#2a1215', border: `1px solid ${colors.danger}`, padding: '20px', borderRadius: '8px' }}>
                <h3 style={{ margin: 0, color: colors.danger }}>Analysis Missing</h3>
                <p>{error}</p>
                <div style={{ backgroundColor: '#000', padding: '15px', fontFamily: 'monospace', borderRadius: '4px', marginTop: '10px' }}>
                    <span style={{ color: '#888' }}># Run this command in terminal:</span><br />
                    <span style={{ color: colors.success }}>mie backtest-hmm --ticker {ticker}</span>
                </div>
                <button
                    onClick={fetchData}
                    style={{ marginTop: '20px', padding: '8px 16px', backgroundColor: colors.accent, color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                >
                    <RefreshCw size={16} style={{ marginRight: 8 }} /> Retry
                </button>
            </div>
        </div>
    );

    return (
        <div style={{ padding: '20px', backgroundColor: colors.bg, minHeight: '100vh', boxSizing: 'border-box' }}>
            {/* Header */}
            <div style={{ marginBottom: '20px', borderBottom: `1px solid ${colors.border}`, paddingBottom: '20px' }}>
                <h1 style={{ margin: 0, fontSize: '24px', color: 'white', display: 'flex', alignItems: 'center' }}>
                    <Activity size={28} color={colors.accent} style={{ marginRight: 15 }} />
                    HMM Backtest Strategy Lab: {ticker}
                </h1>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: 10 }}>
                    <p style={{ margin: '0 0 0 43px', color: colors.textMuted, fontSize: '14px' }}>
                        Grid Search Optimization & Walk-Forward Simulation
                    </p>
                    <div style={{ fontSize: '12px', color: '#555', fontFamily: 'monospace' }}>
                        Generated: {new Date(data.generated_at).toLocaleString()}
                    </div>
                </div>
            </div>

            {/* Top Section: Conclusion & Explanations */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px', marginBottom: '20px' }}>

                {/* 1. Strategy Logic */}
                <div style={{ backgroundColor: colors.panelBg, border: `1px solid ${colors.border}`, borderRadius: '8px', padding: '20px' }}>
                    <h3 style={{ margin: '0 0 10px', fontSize: '14px', color: colors.headerText, display: 'flex', alignItems: 'center' }}>
                        <Info size={16} style={{ marginRight: 8 }} /> Strategy Logic
                    </h3>
                    <div style={{ fontSize: '13px', color: colors.text, lineHeight: '1.5' }}>
                        <p style={{ margin: '0 0 8px' }}>
                            <strong>Long-Only Strategy:</strong> Uses Hidden Markov Models to detect market regimes.
                        </p>
                        <ul style={{ paddingLeft: '20px', margin: 0 }}>
                            <li><span style={{ color: colors.success }}>Bull Regime</span>: Buy / Hold Long Position.</li>
                            <li><span style={{ color: colors.danger }}>Bear/Neutral Regime</span>: Exit to Cash (0% Return).</li>
                        </ul>
                        <p style={{ margin: '8px 0 0', fontSize: '11px', color: colors.textMuted }}>
                            *No short selling. No transaction costs simulated.
                        </p>
                    </div>
                </div>

                {/* 2. Best Sharpe Winner */}
                <div style={{ backgroundColor: 'rgba(76, 175, 80, 0.05)', border: `1px solid ${colors.success}`, borderRadius: '8px', padding: '20px' }}>
                    <h3 style={{ margin: '0 0 10px', fontSize: '14px', color: colors.success, display: 'flex', alignItems: 'center' }}>
                        <Trophy size={16} style={{ marginRight: 8 }} /> Best Risk-Adjusted (Sharpe)
                    </h3>
                    {bestSharpe && (
                        <div>
                            <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'white' }}>
                                {bestSharpe.strat_sharpe.toFixed(2)} Sharpe
                            </div>
                            <div style={{ fontSize: '13px', color: colors.text, marginTop: '5px' }}>
                                {bestSharpe.n_states} States / {bestSharpe.train_window_years} Years
                            </div>
                            <div style={{ fontSize: '12px', color: colors.success, marginTop: '5px' }}>
                                +{bestSharpe.outperformance_sharpe.toFixed(2)} vs Benchmark
                            </div>
                        </div>
                    )}
                </div>

                {/* 3. Best Return Winner */}
                <div style={{ backgroundColor: 'rgba(33, 150, 243, 0.05)', border: `1px solid ${colors.accent}`, borderRadius: '8px', padding: '20px' }}>
                    <h3 style={{ margin: '0 0 10px', fontSize: '14px', color: colors.accent, display: 'flex', alignItems: 'center' }}>
                        <Activity size={16} style={{ marginRight: 8 }} /> Best Total Return
                    </h3>
                    {bestReturn && (
                        <div>
                            <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'white' }}>
                                {(bestReturn.strat_total_ret * 100).toFixed(0)}% Return
                            </div>
                            <div style={{ fontSize: '13px', color: colors.text, marginTop: '5px' }}>
                                {bestReturn.n_states} States / {bestReturn.train_window_years} Years
                            </div>
                            <div style={{ fontSize: '12px', color: bestReturn.strat_total_ret > bestReturn.bh_total_ret ? colors.success : colors.danger, marginTop: '5px' }}>
                                {((bestReturn.strat_total_ret - bestReturn.bh_total_ret) * 100).toFixed(0)}% vs Benchmark
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>

                {/* 1. Leaderboard Table */}
                <div style={{ flex: '1 1 600px', backgroundColor: colors.panelBg, border: `1px solid ${colors.border}`, borderRadius: '8px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>

                    {/* Controls Row */}
                    <div style={{ padding: '15px 20px', borderBottom: `1px solid ${colors.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <h3 style={{ margin: 0, fontSize: '16px', color: colors.headerText, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Optimization Leaderboard</h3>
                            <p style={{ margin: '5px 0 0', fontSize: '12px', color: colors.textMuted }}>Ranked by Strategy Sharpe Ratio</p>
                        </div>
                        {/* Filter Toggle */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', backgroundColor: colors.bg, padding: '4px', borderRadius: '4px', border: `1px solid ${colors.border}` }}>
                            <Filter size={14} color={colors.textMuted} style={{ marginLeft: 5, marginRight: 5 }} />
                            {['All', '5', '10', '20'].map(opt => (
                                <button
                                    key={opt}
                                    onClick={() => setWindowFilter(opt)}
                                    style={{
                                        padding: '4px 8px',
                                        fontSize: '11px',
                                        backgroundColor: windowFilter === opt ? colors.accent : 'transparent',
                                        color: windowFilter === opt ? 'white' : colors.textMuted,
                                        border: 'none',
                                        borderRadius: '3px',
                                        cursor: 'pointer'
                                    }}
                                >
                                    {opt === 'All' ? 'All' : `${opt}Y`}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div style={{ flexGrow: 1, overflow: 'auto', maxHeight: '500px' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                            <thead style={{ position: 'sticky', top: 0, backgroundColor: colors.panelBg, zIndex: 1 }}>
                                <tr>
                                    <th style={{ padding: '12px 15px', textAlign: 'left', color: colors.textMuted, borderBottom: `2px solid ${colors.border}`, cursor: 'help' }} title="Number of Hidden States (Regimes)">Config</th>
                                    <th style={{ padding: '12px 15px', textAlign: 'right', color: colors.headerText, borderBottom: `2px solid ${colors.border}`, cursor: 'help' }} title="Annualized Sharpe Ratio of the HMM Strategy">Sharpe</th>
                                    <th style={{ padding: '12px 15px', textAlign: 'right', color: colors.textMuted, borderBottom: `2px solid ${colors.border}`, cursor: 'help' }} title="Annualized Sharpe Ratio of the Buy & Hold Benchmark">Benchmark Sharpe</th>
                                    <th style={{ padding: '12px 15px', textAlign: 'right', color: colors.textMuted, borderBottom: `2px solid ${colors.border}`, cursor: 'help' }} title="Total Return of HMM Strategy">Total Ret</th>
                                    <th style={{ padding: '12px 15px', textAlign: 'right', color: colors.textMuted, borderBottom: `2px solid ${colors.border}`, cursor: 'help' }} title="Total Return of Buy & Hold Benchmark">Benchmark Ret</th>
                                    <th style={{ padding: '12px 15px', textAlign: 'right', color: colors.textMuted, borderBottom: `2px solid ${colors.border}`, cursor: 'help' }} title="Maximum Drawdown (Peak to Trough)">Max DD</th>
                                </tr>
                            </thead>
                            <tbody>
                                {[...filteredSummary].sort((a, b) => b.strat_sharpe - a.strat_sharpe).map((row) => {
                                    const key = `${row.n_states}_${row.train_window_years}`;
                                    const isSelected = selectedConfig === key;
                                    const isPositive = row.outperformance_sharpe > 0;

                                    return (
                                        <tr
                                            key={key}
                                            onClick={() => setSelectedConfig(key)}
                                            style={{
                                                cursor: 'pointer',
                                                backgroundColor: isSelected ? 'rgba(33, 150, 243, 0.1)' : 'transparent',
                                                borderBottom: `1px solid ${colors.border}`
                                            }}
                                            onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.03)' }}
                                            onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent' }}
                                        >
                                            <td style={{ padding: '10px 15px', color: colors.text }}>
                                                <span style={{ fontWeight: 'bold', color: 'white' }}>{row.n_states} States</span>
                                                <span style={{ margin: '0 8px', color: colors.border }}>|</span>
                                                <span style={{ color: colors.textMuted }}>{row.train_window_years}Y</span>
                                            </td>
                                            <td style={{ padding: '10px 15px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 'bold', fontSize: '14px', color: isPositive ? colors.success : colors.text }}>
                                                {row.strat_sharpe.toFixed(2)}
                                            </td>
                                            <td style={{ padding: '10px 15px', textAlign: 'right', fontFamily: 'monospace', color: colors.textMuted }}>
                                                {row.bh_sharpe.toFixed(2)}
                                            </td>
                                            <td style={{ padding: '10px 15px', textAlign: 'right', fontFamily: 'monospace', color: colors.text }}>
                                                {(row.strat_total_ret * 100).toFixed(0)}%
                                            </td>
                                            <td style={{ padding: '10px 15px', textAlign: 'right', fontFamily: 'monospace', color: colors.textMuted }}>
                                                {(row.bh_total_ret * 100).toFixed(0)}%
                                            </td>
                                            <td style={{ padding: '10px 15px', textAlign: 'right', fontFamily: 'monospace', color: colors.danger }}>
                                                {(row.strat_dd * 100).toFixed(1)}%
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* 2. Heatmap Matrix */}
                <div style={{ flex: '1 1 400px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <div style={{ backgroundColor: colors.panelBg, border: `1px solid ${colors.border}`, borderRadius: '8px', padding: '20px' }}>
                        <h3 style={{ margin: '0 0 15px', fontSize: '16px', color: colors.headerText, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Sharpe Matrix</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                            {[2, 3].map(states => (
                                <div key={states}>
                                    <div style={{ marginBottom: '8px', fontSize: '12px', fontWeight: 'bold', color: 'white' }}>{states} STATES</div>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: '4px' }}>
                                        {allWindows.map(win => {
                                            const val = matrix[states]?.[win];
                                            const isSel = selectedConfig === `${states}_${win}`;

                                            // Color Logic
                                            let bg = '#1e293b';
                                            let text = '#475569';
                                            if (val !== undefined) {
                                                text = 'white';
                                                if (val > 1.5) bg = '#15803d'; // Strong Green
                                                else if (val > 1.0) bg = '#166534'; // Green
                                                else if (val > 0.5) bg = '#1e40af'; // Blue
                                                else bg = '#334155'; // Grey/Blue
                                            }

                                            return (
                                                <div
                                                    key={win}
                                                    onClick={() => val !== undefined && setSelectedConfig(`${states}_${win}`)}
                                                    title={val ? `Sharpe: ${val.toFixed(2)}` : 'No Data'}
                                                    style={{
                                                        height: '40px',
                                                        backgroundColor: bg,
                                                        borderRadius: '4px',
                                                        display: 'flex',
                                                        flexDirection: 'column',
                                                        alignItems: 'center',
                                                        justifyContent: 'center',
                                                        cursor: val !== undefined ? 'pointer' : 'default',
                                                        border: isSel ? '2px solid white' : 'none',
                                                        opacity: val !== undefined ? 1 : 0.3
                                                    }}
                                                >
                                                    <span style={{ fontSize: '9px', color: 'rgba(255,255,255,0.6)' }}>{win}</span>
                                                    {val !== undefined && <span style={{ fontSize: '11px', fontWeight: 'bold', color: text }}>{val.toFixed(1)}</span>}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Selected Summary Card (Compact) */}
                    {selectedConfig && data.summary.find(s => `${s.n_states}_${s.train_window_years}` === selectedConfig) && (
                        <div style={{ backgroundColor: colors.panelBg, border: `1px solid ${colors.border}`, borderRadius: '8px', padding: '20px' }}>
                            {(() => {
                                const sel = data.summary.find(s => `${s.n_states}_${s.train_window_years}` === selectedConfig);
                                return (
                                    <>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                                            <span style={{ fontSize: '12px', color: colors.textMuted }}>SELECTED CONFIG</span>
                                            <span style={{ fontSize: '14px', fontWeight: 'bold', color: colors.accent }}>{sel.n_states} States / {sel.train_window_years} Years</span>
                                        </div>
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                                            <div style={{ padding: '10px', backgroundColor: 'rgba(76, 175, 80, 0.1)', borderRadius: '4px' }}>
                                                <div style={{ fontSize: '11px', color: colors.success }}>Outperformance</div>
                                                <div style={{ fontSize: '18px', fontWeight: 'bold', color: colors.success }}>+{sel.outperformance_sharpe.toFixed(2)}</div>
                                            </div>
                                            <div style={{ padding: '10px', backgroundColor: 'rgba(33, 150, 243, 0.1)', borderRadius: '4px' }}>
                                                <div style={{ fontSize: '11px', color: colors.accent }}>DD Savings</div>
                                                <div style={{ fontSize: '18px', fontWeight: 'bold', color: colors.accent }}>{((sel.strat_dd - sel.bh_dd) * 100).toFixed(1)}%</div>
                                            </div>
                                        </div>
                                    </>
                                );
                            })()}
                        </div>
                    )}
                </div>

            </div>

            {/* 3. Equity Curve (Full Width) */}
            <div style={{ marginTop: '20px', backgroundColor: colors.panelBg, border: `1px solid ${colors.border}`, borderRadius: '8px', padding: '20px' }}>
                <h3 style={{ margin: '0 0 20px', fontSize: '16px', color: colors.headerText, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Equity Curve Comparison (Log Scale)</h3>
                <div style={{ width: '100%', height: '400px' }}>
                    <ResponsiveContainer>
                        <LineChart data={getChartData()}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#2a3a50" />
                            <XAxis
                                dataKey="date"
                                tick={{ fill: '#64748b', fontSize: 12 }}
                                tickFormatter={(val) => val.slice(0, 4)}
                                minTickGap={50}
                                stroke="#2a3a50"
                            />
                            <YAxis
                                scale="log"
                                domain={['auto', 'auto']}
                                tick={{ fill: '#64748b', fontSize: 12 }}
                                stroke="#2a3a50"
                                tickFormatter={(val) => val.toFixed(1)}
                            />
                            <Tooltip
                                contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f1f5f9' }}
                                itemStyle={{ color: '#f1f5f9' }}
                                formatter={(value) => value.toFixed(2)}
                            />
                            <Legend wrapperStyle={{ paddingTop: '10px' }} />
                            <Line
                                type="monotone"
                                dataKey="strategy"
                                name="HMM Strategy"
                                stroke="#4caf50"
                                strokeWidth={2}
                                dot={false}
                                activeDot={{ r: 6 }}
                            />
                            <Line
                                type="monotone"
                                dataKey="benchmark"
                                name={`Buy & Hold (${ticker})`}
                                stroke="#94a3b8"
                                strokeWidth={1}
                                strokeDasharray="4 4"
                                dot={false}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
};

export default HMMBacktestPage;
