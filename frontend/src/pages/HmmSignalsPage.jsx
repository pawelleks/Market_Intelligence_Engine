import React, { useState, useEffect, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceDot, Brush } from 'recharts';
import { Loader2, Activity, RefreshCw, Layers, ArrowUpCircle, ArrowDownCircle, Search } from "lucide-react";

// Custom Dot Component for Signals
const CustomSignalDot = (props) => {
    const { cx, cy, payload, signals } = props;

    // Find if this data point is a signal
    // This is O(N*M) but signals are small. Can optimize with Map if needed.
    const signal = signals.find(s => s.date === payload.Date);

    if (signal) {
        const color = signal.signal_type === "BUY" ? '#4caf50' : '#f44336';
        return (
            <circle cx={cx} cy={cy} r={4} fill={color} stroke="white" strokeWidth={1} />
        );
    }

    // Return null for non-signal points (don't render dot)
    return null;
};

const HmmSignalsPage = () => {
    const [ticker, setTicker] = useState("SPY");
    const [inputTicker, setInputTicker] = useState("SPY");
    const [loading, setLoading] = useState(true);
    const [summaryData, setSummaryData] = useState(null);
    const [error, setError] = useState(null);
    const [selectedConfig, setSelectedConfig] = useState(null); // Key: "n_states-window"
    const [signalsData, setSignalsData] = useState([]);
    const [chartData, setChartData] = useState([]);
    const [loadingSignals, setLoadingSignals] = useState(false);

    // --- Fetch Summary ---
    const fetchSummary = async () => {
        setLoading(true);
        setError(null);
        setSelectedConfig(null);
        setSignalsData([]);
        setChartData([]);
        try {
            const res = await fetch(`/api/v1/hmm/backtest/${ticker}`);
            if (res.status === 404) throw new Error(`Backtest not found for ${ticker}. Please run "mie backtest-hmm --ticker ${ticker}" first.`);
            if (!res.ok) throw new Error("API Error");
            const json = await res.json();
            setSummaryData(json);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSummary();
    }, [ticker]);

    // --- Fetch Signals & Chart for Config ---
    const fetchConfigDetails = async (n_states, window) => {
        const key = `${n_states}-${window}`;
        if (selectedConfig === key) return;

        setSelectedConfig(key);
        setLoadingSignals(true);
        try {
            // 1. Fetch Signals List
            const sigRes = await fetch(`/api/v1/hmm/signals/${ticker}/${n_states}/${window}`);
            if (!sigRes.ok) throw new Error("Failed to fetch signals");
            const sigJson = await sigRes.json();
            setSignalsData(sigJson);

            // 2. Extract Chart Data from Summary (Curves are already there!)
            // The backtest endpoint returns 'curves' keyed by "states_window" (e.g. "2_5")
            // Wait, backtest_engine key is f"{n_states}_{window}".
            const curveKey = `${n_states}_${window}`;
            if (summaryData && summaryData.curves && summaryData.curves[curveKey]) {
                // The curve data has "strategy" (equity), "benchmark", "date".
                // Ideally we want PRICE + Signals.
                // But the curve data is normalized equity curves (start at 1.0).
                // User wants "chart with marked signals".
                // If we want PRICE chart, we need to fetch price history separately or overlay signals on equity curve.
                // Usually "signals on chart" implies Price Chart.
                // Let's fetch Price Data.
                const priceRes = await fetch(`/api/v1/data/prices/${ticker}?rows=5000`); // Fetch 5000 rows for context
                if (priceRes.ok) {
                    const priceJson = await priceRes.json();
                    setChartData(priceJson.data.reverse()); // Price endpoint returns desc, we want asc for chart
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoadingSignals(false);
        }
    };

    const handleSearch = (e) => {
        e.preventDefault();
        if (inputTicker.trim()) setTicker(inputTicker.trim().toUpperCase());
    };

    // --- Styling ---
    const colors = {
        bg: '#0b1220',
        panelBg: '#0e1525',
        border: '#203049',
        text: '#d7e3f3',
        textMuted: '#9e9e9e',
        accent: '#2196f3',
        success: '#4caf50',
        danger: '#f44336',
    };

    // --- Render ---

    return (
        <div style={{ padding: '20px', backgroundColor: colors.bg, minHeight: '100vh', color: colors.text }}>

            {/* Header / Search */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h1 style={{ margin: 0, display: 'flex', alignItems: 'center', fontSize: '24px' }}>
                    <Layers color={colors.accent} style={{ marginRight: 10 }} />
                    HMM Signal Scanner
                </h1>
                <form onSubmit={handleSearch} style={{ display: 'flex', gap: 10 }}>
                    <div style={{ position: 'relative' }}>
                        <Search size={16} color={colors.textMuted} style={{ position: 'absolute', left: 10, top: 10 }} />
                        <input
                            type="text"
                            value={inputTicker}
                            onChange={(e) => setInputTicker(e.target.value)}
                            style={{
                                padding: '8px 10px 8px 35px',
                                backgroundColor: colors.panelBg,
                                border: `1px solid ${colors.border}`,
                                color: 'white',
                                borderRadius: 4
                            }}
                        />
                    </div>
                    <button type="submit" style={{ padding: '8px 16px', backgroundColor: colors.accent, color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
                        Load
                    </button>
                </form>
            </div>

            {loading && !summaryData && (
                <div style={{ textAlign: 'center', padding: 50, color: colors.textMuted }}>
                    <Loader2 className="animate-spin" style={{ display: 'inline', marginRight: 10 }} /> Loading Analysis...
                </div>
            )}

            {error && (
                <div style={{ padding: 20, backgroundColor: '#2a1215', border: `1px solid ${colors.danger}`, borderRadius: 8, color: colors.text }}>
                    <h3 style={{ margin: '0 0 10px', color: colors.danger }}>Error</h3>
                    {error}
                </div>
            )}

            {summaryData && (
                <div style={{ display: 'grid', gridTemplateColumns: 'minmax(400px, 1fr) 2fr', gap: 20 }}>

                    {/* Left: Config Table */}
                    <div style={{ backgroundColor: colors.panelBg, border: `1px solid ${colors.border}`, borderRadius: 8, overflow: 'hidden', display: 'flex', flexDirection: 'column', maxHeight: 'calc(100vh - 100px)' }}>
                        <div style={{ padding: '15px', borderBottom: `1px solid ${colors.border}`, fontWeight: 'bold' }}>
                            Configurations & Latest Signals
                        </div>
                        <div style={{ flex: 1, overflowY: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                                <thead style={{ position: 'sticky', top: 0, backgroundColor: colors.panelBg }}>
                                    <tr>
                                        <th style={{ textAlign: 'left', padding: 10, color: colors.textMuted }}>Config</th>
                                        <th style={{ textAlign: 'left', padding: 10, color: colors.textMuted }}>Latest Signal</th>
                                        <th style={{ textAlign: 'right', padding: 10, color: colors.textMuted }}>Price</th>
                                        <th style={{ textAlign: 'right', padding: 10, color: colors.textMuted }}>Sharpe</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {summaryData.summary.sort((a, b) => b.matrix_sharpe - a.matrix_sharpe /* Sort by something? summary has strat_sharpe */).map(row => {
                                        const isActive = selectedConfig === `${row.n_states}-${row.train_window_years}`;
                                        const isBuy = row.last_signal_type === "BUY";
                                        return (
                                            <tr
                                                key={`${row.n_states}-${row.train_window_years}`}
                                                onClick={() => fetchConfigDetails(row.n_states, row.train_window_years)}
                                                style={{
                                                    cursor: 'pointer',
                                                    backgroundColor: isActive ? 'rgba(33, 150, 243, 0.1)' : 'transparent',
                                                    borderBottom: `1px solid ${colors.border}`
                                                }}
                                            >
                                                <td style={{ padding: 10 }}>
                                                    <span style={{ color: 'white', fontWeight: 'bold' }}>{row.n_states}S</span>
                                                    <span style={{ color: colors.textMuted, marginLeft: 5 }}>{row.train_window_years}Y</span>
                                                </td>
                                                <td style={{ padding: 10 }}>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                                                        {isBuy ? <ArrowUpCircle size={14} color={colors.success} /> : <ArrowDownCircle size={14} color={colors.danger} />}
                                                        <span style={{ color: isBuy ? colors.success : colors.danger, fontWeight: 'bold' }}>{row.last_signal_type}</span>
                                                        <span style={{ color: colors.textMuted, fontSize: '11px' }}>{row.last_signal_date}</span>
                                                    </div>
                                                </td>
                                                <td style={{ padding: 10, textAlign: 'right', fontFamily: 'monospace' }}>
                                                    {row.last_signal_price?.toFixed(2)}
                                                </td>
                                                <td style={{ padding: 10, textAlign: 'right', fontFamily: 'monospace', color: row.outperformance_sharpe > 0 ? colors.success : colors.textMuted }}>
                                                    {row.strat_sharpe.toFixed(2)}
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Right: Chart & History */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

                        {/* Chart */}
                        <div style={{ backgroundColor: colors.panelBg, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 20, minHeight: 400 }}>
                            {!selectedConfig ? (
                                <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.textMuted }}>
                                    Select a configuration to view chart
                                </div>
                            ) : loadingSignals ? (
                                <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.textMuted }}>
                                    <Loader2 className="animate-spin" /> Loading Chart...
                                </div>
                            ) : (
                                <div style={{ width: '100%', height: 400 }}>
                                    <div style={{ marginBottom: 10, fontWeight: 'bold' }}>Price & Signals: {selectedConfig.replace('-', ' States / ')} Years</div>
                                    <ResponsiveContainer>
                                        <LineChart data={chartData}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#2a3a50" />
                                            <XAxis dataKey="Date" tick={{ fontSize: 11 }} minTickGap={50} />
                                            <YAxis domain={['auto', 'auto']} scale="log" tick={{ fontSize: 11 }} />
                                            <Tooltip contentStyle={{ backgroundColor: colors.panelBg, borderColor: colors.border }} />
                                            <Line
                                                type="monotone"
                                                dataKey="Close"
                                                stroke="#64748b"
                                                strokeWidth={1}
                                                dot={<CustomSignalDot signals={signalsData} />}
                                            />
                                            <Brush
                                                dataKey="Date"
                                                height={30}
                                                stroke="#2196f3"
                                                fill="#0e1525"
                                                tickFormatter={(val) => val.slice(0, 4)}
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            )}
                        </div>

                        {/* Signals History Table */}
                        <div style={{ backgroundColor: colors.panelBg, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 20, flex: 1 }}>
                            <div style={{ marginBottom: 15, fontWeight: 'bold' }}>Signal History</div>
                            {signalsData.length === 0 ? (
                                <div style={{ color: colors.textMuted }}>No signals selected</div>
                            ) : (
                                <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                                        <thead>
                                            <tr style={{ borderBottom: `1px solid ${colors.border}` }}>
                                                <th style={{ textAlign: 'left', padding: 8, color: colors.textMuted }}>Date</th>
                                                <th style={{ textAlign: 'left', padding: 8, color: colors.textMuted }}>Signal</th>
                                                <th style={{ textAlign: 'right', padding: 8, color: colors.textMuted }}>Price</th>
                                                <th style={{ textAlign: 'left', padding: 8, color: colors.textMuted }}>Trigger</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {[...signalsData].reverse().map((sig, idx) => (
                                                <tr key={idx} style={{ borderBottom: `1px solid ${colors.border}` }}>
                                                    <td style={{ padding: 8 }}>{sig.date}</td>
                                                    <td style={{ padding: 8, fontWeight: 'bold', color: sig.signal_type === "BUY" ? colors.success : colors.danger }}>{sig.signal_type}</td>
                                                    <td style={{ padding: 8, textAlign: 'right', fontFamily: 'monospace' }}>{sig.price.toFixed(2)}</td>
                                                    <td style={{ padding: 8, color: colors.textMuted }}>{sig.description}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>

                    </div>
                </div>
            )}
        </div>
    );
};

export default HmmSignalsPage;
