
import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import { useParams, useNavigate } from 'react-router-dom';
import { Search, ArrowRight, TrendingUp, TrendingDown, Minus, AlertCircle, CheckCircle } from 'lucide-react';

const EmaStackReport = () => {
    const { ticker: urlTicker } = useParams();
    const navigate = useNavigate();
    const [ticker, setTicker] = useState(urlTicker || 'SPY');
    const [tickerList, setTickerList] = useState([]);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [xaxisRange, setXaxisRange] = useState(null);
    const [yaxisRange, setYaxisRange] = useState(null);

    useEffect(() => {
        // Fetch tickers
        fetch('/api/v1/tickers')
            .then(res => res.json())
            .then(data => {
                if (data.tickers) setTickerList(data.tickers);
            })
            .catch(err => console.error("Error fetching ticker list:", err));
    }, []);

    useEffect(() => {
        if (urlTicker) {
            setTicker(urlTicker);
        }
    }, [urlTicker]);

    useEffect(() => {
        fetchData(ticker);
    }, [ticker]);

    const fetchData = async (t) => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(`/api/v1/analytics/sma-stack/${t}`);
            if (!response.ok) {
                throw new Error('Failed to fetch data');
            }
            const result = await response.json();
            setData(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleTickerChange = (e) => {
        const t = e.target.value;
        setTicker(t);
        navigate(`/analysis/ema-stack/${t}`);
    };

    // Default Zoom Range (Last 10 Months)
    const zoomStartDate = new Date();
    zoomStartDate.setMonth(zoomStartDate.getMonth() - 10);
    const zoomStartStr = zoomStartDate.toISOString().split('T')[0];
    const todayStr = new Date().toISOString().split('T')[0];

    // Initialize xaxisRange if null
    useEffect(() => {
        if (!xaxisRange && data) {
            setXaxisRange([zoomStartStr, todayStr]);
        }
    }, [data, xaxisRange, zoomStartStr, todayStr]);

    // Dynamic Y-Axis Scaling Effect
    useEffect(() => {
        if (!data || !data.history || !xaxisRange) return;

        const visibleData = data.history.filter(d => d.date >= xaxisRange[0] && d.date <= xaxisRange[1]);
        if (visibleData.length === 0) return;

        let minV = Infinity;
        let maxV = -Infinity;

        visibleData.forEach(d => {
            const vals = [d.close, d.ema_20, d.ema_50, d.ema_200].filter(v => v != null);
            if (vals.length > 0) {
                const localMin = Math.min(...vals);
                const localMax = Math.max(...vals);
                if (localMin < minV) minV = localMin;
                if (localMax > maxV) maxV = localMax;
            }
        });

        if (minV !== Infinity && maxV !== -Infinity) {
            const padding = Math.max((maxV - minV) * 0.05, 1); // 5% padding, min 1pt
            setYaxisRange([minV - padding, maxV + padding]);
        }
    }, [xaxisRange, data]);

    if (loading) return <div style={{ padding: 20, color: '#fff' }}>Loading Data...</div>;
    if (error) return <div style={{ padding: 20, color: '#ff6b6b' }}>Error: {error}</div>;
    if (!data) return null;

    // --- LOGIC CALCULATIONS ---
    const l = data.latest || {};
    const history = data.history || [];

    // 1. Days in Stage 2 (Consecutive Days Stacked Up)
    let daysInStage2 = 0;
    if (l.is_ema_stacked_up) {
        // Count backwards
        for (let i = history.length - 1; i >= 0; i--) {
            if (history[i].is_ema_stacked_up) {
                daysInStage2++;
            } else {
                break;
            }
        }
    } else {
        // Determine days NOT stacked if needed, or just 0
        daysInStage2 = 0;
    }

    // 2. Trend Maturity
    let maturityLabel = "N/A";
    let maturityColor = "#94a3b8"; // Grey

    if (l.is_ema_stacked_up) {
        if (daysInStage2 <= 20) {
            maturityLabel = "FRESH BREAKOUT";
            maturityColor = "#4ade80"; // Bright Green
        } else if (daysInStage2 <= 100) {
            maturityLabel = "ESTABLISHED TREND";
            maturityColor = "#22c55e"; // Green
        } else if (daysInStage2 <= 250) {
            maturityLabel = "MATURE TREND";
            maturityColor = "#3b82f6"; // Blue
        } else {
            maturityLabel = "EXTENDED / LATE STAGE";
            maturityColor = "#f97316"; // Orange
        }
    }

    // 3. Verdict Logic
    let verdictTitle = "NEUTRAL / BEARISH";
    let verdictText = "The EMA stack is broken or inverted. The asset is not in a defined uptrend state.";
    let verdictColor = "#ef5350"; // Red

    if (l.is_ema_stacked_up) {
        if (l.is_price_above_stack) {
            verdictTitle = "STRONG BULLISH";
            verdictText = "Full alignment: EMAs are stacked (20>50>200) and Price is trading above the stack. Momentum is strong.";
            verdictColor = "#4caf50"; // Green
        } else {
            // Stacked but Price inside/below stack (Pullback)
            verdictTitle = "BULLISH (MEAN REVERSION)";
            verdictText = "The long-term Trend Structure (Stacked EMAs) is intact, but Price has pulled back into or below the averages. Watch for support.";
            verdictColor = "#ff9800"; // Orange
        }
    }

    // Chart Data
    // Filter to last 24 months (~500 trading days)
    const cutoffDate = new Date();
    cutoffDate.setMonth(cutoffDate.getMonth() - 24);
    const cutoffStr = cutoffDate.toISOString().split('T')[0];

    const filteredHistory = history.filter(d => d.date >= cutoffStr);

    const dates = filteredHistory.map(d => d.date);
    const closes = filteredHistory.map(d => d.close);
    const ema20 = filteredHistory.map(d => d.ema_20);
    const ema50 = filteredHistory.map(d => d.ema_50);
    const ema200 = filteredHistory.map(d => d.ema_200);

    const handleRelayout = (event) => {
        // Use timeout to prevent React state update loops reacting to Plotly's internal syncs
        setTimeout(() => {
            if (event['xaxis.range[0]'] && event['xaxis.range[1]']) {
                setXaxisRange([event['xaxis.range[0]'], event['xaxis.range[1]']]);
            } else if (event['xaxis.range']) {
                setXaxisRange(event['xaxis.range']);
            } else if (event['xaxis.autorange'] === true) {
                setXaxisRange([zoomStartStr, todayStr]);
            }
        }, 0);
    };

    return (
        <div style={{ padding: '20px', color: '#e0e0e0', backgroundColor: '#0b1220', minHeight: '100vh', display: 'flex', flexDirection: 'column', gap: '15px' }}>

            {/* Header & Verdict Section */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '15px' }}>

                {/* Title Card */}
                <div style={{ backgroundColor: '#162032', padding: '15px 20px', borderRadius: '6px', border: '1px solid #1e293b', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <h1 style={{ margin: 0, fontSize: '20px', color: '#94a3b8' }}>EMA Trend Stack</h1>
                            <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                                <h2 style={{ margin: '5px 0 0 0', fontSize: '28px', color: '#fff', fontWeight: 'bold' }}>{ticker}</h2>
                                {l.date && <span style={{ fontSize: '11px', color: '#64748b' }}>Data as of: {l.date}</span>}
                            </div>
                        </div>

                        {/* Selector */}
                        <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '4px' }}>SELECT ASSET</div>
                            <select
                                value={ticker}
                                onChange={handleTickerChange}
                                style={{
                                    backgroundColor: '#0f172a',
                                    border: '1px solid #334155',
                                    color: 'white',
                                    padding: '6px 10px',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontSize: '0.9rem',
                                    minWidth: '120px',
                                    outline: 'none'
                                }}
                            >
                                {tickerList.length === 0 && <option value={ticker}>{ticker}</option>}
                                {tickerList.map(t => <option key={t} value={t}>{t}</option>)}
                            </select>
                        </div>
                    </div>

                    <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '10px' }}>
                        Multiple Moving Average alignment analysis (Stage 2 identification).
                    </div>

                    {/* Duration Counter */}
                    {l.is_ema_stacked_up && (
                        <div style={{ marginTop: '15px', padding: '10px', backgroundColor: '#0f172a', borderRadius: '4px', border: '1px solid #334155', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <div>
                                <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>Consecutive Days in Stage 2</div>
                                <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#e2e8f0' }}>
                                    {daysInStage2} <span style={{ fontSize: '12px', fontWeight: 'normal', color: '#64748b' }}>Days</span>
                                </div>
                            </div>

                            {/* Maturity Badge */}
                            <div style={{
                                backgroundColor: `${maturityColor}20`,
                                border: `1px solid ${maturityColor}`,
                                color: maturityColor,
                                padding: '4px 8px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontWeight: 'bold',
                                textTransform: 'uppercase'
                            }}>
                                {maturityLabel}
                            </div>
                        </div>
                    )}
                </div>

                {/* Verdict Card */}
                <div style={{ backgroundColor: '#162032', padding: '15px 20px', borderRadius: '6px', border: `1px solid ${verdictColor}`, borderLeft: `4px solid ${verdictColor}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                            <h2 style={{ margin: 0, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '1px', color: '#94a3b8' }}>Trend Verdict</h2>
                            <div style={{ fontSize: '22px', fontWeight: 'bold', color: verdictColor, marginTop: '4px' }}>
                                {verdictTitle}
                            </div>
                        </div>
                    </div>

                    <p style={{ margin: '12px 0 0 0', fontSize: '13px', color: '#cbd5e1', lineHeight: '1.4' }}>
                        {verdictText}
                    </p>

                    {/* Flags */}
                    <div style={{ display: 'flex', gap: '8px', marginTop: '15px', flexWrap: 'wrap' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: l.is_ema_stacked_up ? '#4ade80' : '#ef5350' }}>
                            {l.is_ema_stacked_up ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                            Stack Aligned (20{'>'}50{'>'}200)
                        </div>
                        <div style={{ width: '1px', height: '16px', backgroundColor: '#334155' }}></div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: l.is_price_above_stack ? '#4ade80' : '#facc15' }}>
                            {l.is_price_above_stack ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                            Price {'>'} Stack
                        </div>
                        <div style={{ width: '1px', height: '16px', backgroundColor: '#334155' }}></div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: l.is_200_ema_up ? '#4ade80' : '#ef5350' }}>
                            {l.is_200_ema_up ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
                            200 EMA Rising
                        </div>
                    </div>
                </div>
            </div>

            {/* Chart Section */}
            <div style={{ backgroundColor: '#162032', padding: '0', borderRadius: '6px', border: '1px solid #1e293b', overflow: 'hidden', minHeight: '550px', display: 'flex', flexDirection: 'column' }}>
                <div style={{ flex: 1, position: 'relative' }}>
                    <Plot
                        data={[
                            { x: dates, y: closes, type: 'scatter', mode: 'lines', name: 'Price', line: { color: '#ffffff', width: 2 } },
                            { x: dates, y: ema20, type: 'scatter', mode: 'lines', name: 'EMA 20', line: { color: '#4ade80', width: 1.5 } },
                            { x: dates, y: ema50, type: 'scatter', mode: 'lines', name: 'EMA 50', line: { color: '#facc15', width: 1.5 } },
                            { x: dates, y: ema200, type: 'scatter', mode: 'lines', name: 'EMA 200', line: { color: '#ef5350', width: 2 } }
                        ]}
                        layout={{
                            autosize: true,
                            paper_bgcolor: 'rgba(0,0,0,0)',
                            plot_bgcolor: 'rgba(0,0,0,0)',
                            font: { color: '#94a3b8', family: 'Inter, sans-serif' },
                            xaxis: {
                                gridcolor: '#1e293b',
                                tickfont: { size: 11 },
                                autorange: false,
                                range: xaxisRange || [zoomStartStr, todayStr],
                                rangeslider: { visible: true, thickness: 0.1, bgcolor: '#0f172a' },
                                type: 'date'
                            },
                            yaxis: {
                                gridcolor: '#1e293b',
                                tickfont: { size: 11 },
                                autorange: yaxisRange ? false : true,
                                range: yaxisRange
                            },
                            margin: { l: 40, r: 20, t: 40, b: 30 },
                            showlegend: true,
                            legend: { orientation: 'h', x: 0, y: 1.02, bgcolor: 'rgba(0,0,0,0)', font: { size: 10 } }
                        }}
                        useResizeHandler={true}
                        style={{ width: '100%', height: '100%' }}
                        config={{ responsive: true, displayModeBar: false }}
                        onRelayout={handleRelayout}
                    />
                </div>

                {/* Footer Stats */}
                <div style={{ borderTop: '1px solid #1e293b', padding: '15px', display: 'flex', gap: '30px', fontSize: '12px', color: '#94a3b8', backgroundColor: '#0f172a' }}>
                    <div>
                        <span style={{ display: 'block', marginBottom: '2px', fontSize: '10px', textTransform: 'uppercase' }}>Current Price</span>
                        <span style={{ color: '#e2e8f0', fontWeight: 'bold' }}>${l.close?.toFixed(2)}</span>
                    </div>
                    <div>
                        <span style={{ display: 'block', marginBottom: '2px', fontSize: '10px', textTransform: 'uppercase', color: '#4ade80' }}>EMA 20</span>
                        <span style={{ color: '#4ade80', fontWeight: 'bold' }}>${l.ema_20?.toFixed(2)}</span>
                    </div>
                    <div>
                        <span style={{ display: 'block', marginBottom: '2px', fontSize: '10px', textTransform: 'uppercase', color: '#facc15' }}>EMA 50</span>
                        <span style={{ color: '#facc15', fontWeight: 'bold' }}>${l.ema_50?.toFixed(2)}</span>
                    </div>
                    <div>
                        <span style={{ display: 'block', marginBottom: '2px', fontSize: '10px', textTransform: 'uppercase', color: '#ef5350' }}>EMA 200</span>
                        <span style={{ color: '#ef5350', fontWeight: 'bold' }}>${l.ema_200?.toFixed(2)}</span>
                    </div>
                </div>
            </div>

            {/* NEW: SMA/EMA Analysis Tables */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))', gap: '20px' }}>

                {/* SMA Table */}
                <div style={{ backgroundColor: '#162032', padding: '20px', borderRadius: '6px', border: '1px solid #1e293b' }}>
                    <h3 style={{ margin: '0 0 15px 0', fontSize: '14px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '1px' }}>
                        Simple Moving Averages (SMA)
                    </h3>
                    <MATable type="sma" data={l} price={l.close} />
                </div>

                {/* EMA Table */}
                <div style={{ backgroundColor: '#162032', padding: '20px', borderRadius: '6px', border: '1px solid #1e293b' }}>
                    <h3 style={{ margin: '0 0 15px 0', fontSize: '14px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '1px' }}>
                        Exponential Moving Averages (EMA)
                    </h3>
                    <MATable type="ema" data={l} price={l.close} />
                </div>

            </div>
        </div>
    );
};

// Reusable Table Component
const MATable = ({ type, data, price }) => {
    if (!price) return <div style={{ fontSize: '12px', color: '#64748b' }}>No Price Data</div>;

    const periods = [20, 50, 100, 200];

    return (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
                <tr style={{ borderBottom: '1px solid #334155', color: '#64748b', textAlign: 'left' }}>
                    <th style={{ padding: '8px', fontWeight: 'normal' }}>Period</th>
                    <th style={{ padding: '8px', fontWeight: 'normal', textAlign: 'right' }}>Value</th>
                    <th style={{ padding: '8px', fontWeight: 'normal', textAlign: 'center' }}>Signal</th>
                    <th style={{ padding: '8px', fontWeight: 'normal', textAlign: 'right' }}>Dist %</th>
                </tr>
            </thead>
            <tbody>
                {periods.map(p => {
                    const key = `${type}_${p}`;
                    const val = data[key];

                    if (val === undefined || val === null) {
                        return (
                            <tr key={p} style={{ borderBottom: '1px solid #1e293b' }}>
                                <td style={{ padding: '10px 8px', color: '#cbd5e1' }}>{type.toUpperCase()} {p}</td>
                                <td style={{ padding: '10px 8px', textAlign: 'right', color: '#64748b' }}>N/A</td>
                                <td colSpan={2}></td>
                            </tr>
                        );
                    }

                    const isAbove = price >= val;
                    const color = isAbove ? '#4ade80' : '#ef5350';
                    const diffPct = ((price - val) / val) * 100;

                    return (
                        <tr key={p} style={{ borderBottom: '1px solid #1e293b' }}>
                            <td style={{ padding: '10px 8px', color: '#cbd5e1', fontWeight: '500' }}>
                                {type.toUpperCase()} {p}
                            </td>
                            <td style={{ padding: '10px 8px', textAlign: 'right', color: '#e2e8f0', fontFamily: 'monospace' }}>
                                {val.toFixed(2)}
                            </td>
                            <td style={{ padding: '10px 8px', textAlign: 'center' }}>
                                <span style={{
                                    backgroundColor: `${color}20`,
                                    color: color,
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                    fontSize: '11px',
                                    fontWeight: 'bold'
                                }}>
                                    {isAbove ? 'PRICE > MA' : 'PRICE < MA'}
                                </span>
                            </td>
                            <td style={{ padding: '10px 8px', textAlign: 'right', color: color, fontWeight: 'bold', fontFamily: 'monospace' }}>
                                {diffPct > 0 ? '+' : ''}{diffPct.toFixed(2)}%
                            </td>
                        </tr>
                    );
                })}
            </tbody>
        </table>
    );
};

export default EmaStackReport;
