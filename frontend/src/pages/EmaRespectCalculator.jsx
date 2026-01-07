import React, { useState, useEffect, useRef } from 'react';
import { usePageTitle } from '../hooks/usePageTitle';
import { useAuth } from '../context/AuthContext';
import { createChart, ColorType, CrosshairMode, CandlestickSeries, LineSeries } from 'lightweight-charts';
import { Search, Info, Settings, ArrowUp, ArrowDown } from 'lucide-react';

// Error Boundary Component
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error("ErrorBoundary caught an error", error, errorInfo);
        this.setState({ errorInfo });
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: '20px', color: '#f44336', backgroundColor: '#1b2a40', minHeight: '100vh' }}>
                    <h2>Something went wrong.</h2>
                    <details style={{ whiteSpace: 'pre-wrap' }}>
                        {this.state.error && this.state.error.toString()}
                        <br />
                        {this.state.errorInfo && this.state.errorInfo.componentStack}
                    </details>
                </div>
            );
        }
        return this.props.children;
    }
}

const EmaRespectCalculator = () => {
    usePageTitle('EMA Respect Calculator');
    const { token } = useAuth();

    // Inputs
    const [ticker, setTicker] = useState('SPY');
    const [availableTickers, setAvailableTickers] = useState([]);
    const [tolerance, setTolerance] = useState(0.5);
    const [proximity, setProximity] = useState(1.5);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [maType, setMaType] = useState('EMA');

    // Ranges
    const [ranges, setRanges] = useState({
        short: { min: 10, max: 60 },
        medium: { min: 61, max: 140 },
        long: { min: 141, max: 300 }
    });
    const [showAdvanced, setShowAdvanced] = useState(false);

    // Results
    const [results, setResults] = useState(null);
    const [error, setError] = useState(null);

    // Chart Ref
    const chartContainerRef = useRef();

    // Fetch tickers
    useEffect(() => {
        const fetchTickers = async () => {
            try {
                const res = await fetch('/api/v1/tickers', {
                    headers: { "Authorization": `Bearer ${token}` }
                });
                const json = await res.json();
                if (json.tickers) {
                    setAvailableTickers(json.tickers.sort());
                    if (!json.tickers.includes(ticker) && json.tickers.length > 0) {
                        setTicker(json.tickers[0]);
                    }
                }
            } catch (e) {
                console.error("Failed to fetch tickers", e);
            }
        };
        fetchTickers();
    }, [token]);

    const colors = {
        bg: '#0e1525',
        cardBg: '#1b2a40',
        text: '#d7e3f3',
        textMuted: '#9e9e9e',
        border: '#203049',
        accent: '#3b82f6',
        success: '#4caf50',
        danger: '#f44336',
        ema_short: '#00bcd4', // Cyan
        ema_med: '#ff9800',  // Orange
        ema_long: '#9c27b0',   // Purple
        white: '#ffffff',
        transparent: 'transparent'
    };

    // Initialize Chart when results change
    useEffect(() => {
        if (!results || !results.chart_data || !chartContainerRef.current) return;

        console.log("Initializing Chart with results:", results);
        let chart = null;

        try {
            // Deduplicate and Sort Data
            const uniqueDataMap = new Map();
            results.chart_data.forEach(item => {
                if (item.date && !uniqueDataMap.has(item.date)) {
                    uniqueDataMap.set(item.date, item);
                }
            });
            const processData = Array.from(uniqueDataMap.values()).sort((a, b) => new Date(a.date) - new Date(b.date));

            if (processData.length === 0) {
                console.warn("No valid chart data to render.");
                return;
            }

            const chart = createChart(chartContainerRef.current, {
                layout: {
                    background: { type: ColorType.Solid, color: colors.cardBg },
                    textColor: colors.text
                },
                grid: {
                    vertLines: { color: colors.border },
                    horzLines: { color: colors.border }
                },
                width: chartContainerRef.current.clientWidth,
                height: 500,
                crosshair: { mode: CrosshairMode.Normal },
                timeScale: {
                    borderColor: colors.border,
                    timeVisible: true,
                    tickMarkFormatter: (time, tickMarkType, locale) => {
                        // Fallback safety if time is not object
                        if (typeof time === 'string') return time;
                        if (!time || !time.year) return "";
                        if (tickMarkType === 0) return String(time.year);
                        if (tickMarkType === 1) {
                            const date = new Date(time.year, time.month - 1, time.day);
                            return date.toLocaleDateString(locale, { month: 'short', year: '2-digit' });
                        }
                        if (tickMarkType === 2) return String(time.day);
                        return String(time.year);
                    }
                },
                rightPriceScale: { borderColor: colors.border }
            });

            // 1. Candlestick Series - v5 API
            const candleSeries = chart.addSeries(CandlestickSeries, {
                upColor: '#ffffff',              // White Fill
                downColor: colors.cardBg,        // Match Background (Safe Hollow)
                borderUpColor: '#ffffff',        // White Border
                borderDownColor: colors.danger,  // Red Border
                wickUpColor: '#ffffff',          // White Wick
                wickDownColor: colors.danger     // Red Wick
            });

            const candleData = processData
                .filter(d => d.open != null && d.close != null) // Filter out missing data
                .map(d => ({
                    time: d.date,
                    open: Number(d.open),
                    high: Number(d.high),
                    low: Number(d.low),
                    close: Number(d.close)
                }));

            if (candleData.length > 0) {
                candleSeries.setData(candleData);
            }

            // 2. EMA Series & Markers
            const seriesColors = { short: colors.ema_short, medium: colors.ema_med, long: colors.ema_long };

            ['short', 'medium', 'long'].forEach(range => {
                const winner = results.winners[range];
                if (winner) {
                    const p = winner.period;
                    const color = seriesColors[range];
                    // v5 API: addSeries(LineSeries, options)
                    const lineSeries = chart.addSeries(LineSeries, {
                        color: color, lineWidth: 2, title: `EMA ${p} (${range})`
                    });

                    const lineData = processData
                        .filter(d => d[`ema_${p}`] != null)
                        .map(d => ({
                            time: d.date,
                            value: Number(d[`ema_${p}`])
                        }));

                    if (lineData.length > 0) {
                        lineSeries.setData(lineData);

                        // Markers
                        const validDates = new Set(lineData.map(d => d.time));
                        const markers = [];
                        processData.forEach(d => {
                            if (!validDates.has(d.date)) return;
                            const type = d[`bounce_${p}`];
                            if (type) {
                                markers.push({
                                    time: d.date,
                                    position: type === 'bullish' ? 'belowBar' : 'aboveBar',
                                    color: type === 'bullish' ? colors.success : colors.danger,
                                    shape: type === 'bullish' ? 'arrowUp' : 'arrowDown',
                                    text: type === 'bullish' ? 'B' : 'S',
                                    size: 1
                                });
                            }
                        });

                        if (typeof lineSeries.setMarkers === 'function') {
                            lineSeries.setMarkers(markers);
                        } else {
                            console.warn("setMarkers is not available on lineSeries");
                        }
                    }
                }
            });

            chart.timeScale().fitContent();

            // Handle Resize
            const handleResize = () => {
                if (chartContainerRef.current) {
                    chart.applyOptions({ width: chartContainerRef.current.clientWidth });
                }
            };
            window.addEventListener('resize', handleResize);

            // Cleanup
            return () => {
                window.removeEventListener('resize', handleResize);
                if (chart) {
                    try {
                        chart.remove();
                    } catch (e) {
                        console.warn("Chart removal error:", e);
                    }
                }
            };
        } catch (err) {
            console.error("Chart Render Error:", err);
            setError(`Chart Render Error: ${err.message}`);
            if (chart) {
                try { chart.remove(); } catch (e) { }
            }
        }
    }, [results, maType]);


    const handleAnalyze = async (e) => {
        e.preventDefault();
        setIsAnalyzing(true);
        setError(null);
        setResults(null);

        try {
            const query = new URLSearchParams({
                ticker,
                min_period: 10,
                max_period: 300,
                tolerance,
                proximity,
                short_min: ranges.short.min,
                short_max: ranges.short.max,
                medium_min: ranges.medium.min,
                medium_max: ranges.medium.max,
                long_min: ranges.long.min,
                long_max: ranges.long.max,
                ma_type: maType,
            });

            const res = await fetch(
                `/api/v1/tools/ema-respect?${query.toString()}`,
                { headers: { "Authorization": `Bearer ${token}` } }
            );
            const json = await res.json();

            if (json.status === 'ok') {
                setResults(json.data);
            } else {
                let errorMsg = json.detail || 'Analysis failed';
                if (typeof errorMsg === 'object') {
                    errorMsg = JSON.stringify(errorMsg);
                }
                setError(errorMsg);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setIsAnalyzing(false);
        }
    };

    return (
        <ErrorBoundary>
            <div style={{ padding: '20px', minHeight: '100vh', color: colors.text }}>
                <h1 style={{ fontSize: '28px', marginBottom: '20px' }}>EMA Respect Calculator</h1>

                {/* Input Card */}
                <div style={{
                    backgroundColor: colors.cardBg,
                    padding: '20px',
                    borderRadius: '8px',
                    border: `1px solid ${colors.border}`,
                    marginBottom: '20px'
                }}>
                    <div style={{ display: 'flex', gap: '20px', alignItems: 'end', flexWrap: 'wrap' }}>
                        <div style={{ flex: 1, minWidth: '200px' }}>
                            <label style={{ display: 'block', marginBottom: '8px', color: colors.textMuted }}>Ticker</label>
                            <div style={{ position: 'relative' }}>
                                <select
                                    value={ticker}
                                    onChange={(e) => setTicker(e.target.value)}
                                    style={{
                                        width: '100%',
                                        padding: '10px 10px 10px 35px',
                                        backgroundColor: colors.bg,
                                        border: `1px solid ${colors.border}`,
                                        borderRadius: '4px',
                                        color: colors.text,
                                        appearance: 'none',
                                        cursor: 'pointer'
                                    }}
                                >
                                    {availableTickers.map(t => (
                                        <option key={t} value={t}>{t}</option>
                                    ))}
                                </select>
                                <Search size={18} style={{ position: 'absolute', left: '10px', top: '12px', color: colors.textMuted, pointerEvents: 'none' }} />
                                <ArrowDown size={14} style={{ position: 'absolute', right: '10px', top: '14px', color: colors.textMuted, pointerEvents: 'none' }} />
                            </div>
                        </div>

                        <div style={{ flex: 1, minWidth: '150px' }}>
                            <label style={{ display: 'block', marginBottom: '8px', color: colors.textMuted }}>Analysis Type</label>
                            <div style={{ position: 'relative' }}>
                                <select
                                    value={maType}
                                    onChange={(e) => setMaType(e.target.value)}
                                    style={{
                                        width: '100%',
                                        padding: '10px 10px 10px 10px',
                                        backgroundColor: colors.bg,
                                        border: `1px solid ${colors.border}`,
                                        borderRadius: '4px',
                                        color: colors.text,
                                        appearance: 'none',
                                        cursor: 'pointer'
                                    }}
                                >
                                    <option value="EMA">Exponential (EMA)</option>
                                    <option value="SMA">Simple (SMA)</option>
                                    <option value="WMA">Weighted (WMA)</option>
                                    <option value="VWMA">Volume Weighted (VWMA)</option>
                                </select>
                                <ArrowDown size={14} style={{ position: 'absolute', right: '10px', top: '14px', color: colors.textMuted, pointerEvents: 'none' }} />
                            </div>
                        </div>

                        <div style={{ flex: 1, minWidth: '150px' }}>
                            <label style={{ display: 'block', marginBottom: '8px', color: colors.textMuted }}>
                                Penetration Tolerance (%)
                            </label>
                            <input
                                type="number"
                                step="0.1"
                                value={tolerance}
                                onChange={(e) => setTolerance(parseFloat(e.target.value))}
                                style={{ width: '100%', padding: '10px', backgroundColor: colors.bg, border: `1px solid ${colors.border}`, borderRadius: '4px', color: colors.text }}
                            />
                        </div>

                        <div style={{ flex: 1, minWidth: '150px' }}>
                            <label style={{ display: 'block', marginBottom: '8px', color: colors.textMuted }}>
                                Proximity Threshold (%)
                            </label>
                            <input
                                type="number"
                                step="0.1"
                                value={proximity}
                                onChange={(e) => setProximity(parseFloat(e.target.value))}
                                style={{ width: '100%', padding: '10px', backgroundColor: colors.bg, border: `1px solid ${colors.border}`, borderRadius: '4px', color: colors.text }}
                            />
                        </div>

                        <button
                            onClick={handleAnalyze}
                            disabled={isAnalyzing}
                            style={{
                                padding: '10px 24px',
                                backgroundColor: colors.accent,
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: isAnalyzing ? 'not-allowed' : 'pointer',
                                opacity: isAnalyzing ? 0.7 : 1,
                                height: '42px',
                                fontWeight: 'bold'
                            }}
                        >
                            {isAnalyzing ? 'Analyzing...' : 'Run Analysis'}
                        </button>

                        <button
                            onClick={() => setShowAdvanced(!showAdvanced)}
                            style={{
                                padding: '10px',
                                backgroundColor: 'transparent',
                                color: colors.textMuted,
                                border: `1px solid ${colors.border}`,
                                borderRadius: '4px',
                                cursor: 'pointer',
                                height: '42px',
                                display: 'flex', alignItems: 'center', gap: '5px'
                            }}
                        >
                            <Settings size={16} /> {showAdvanced ? 'Hide Advanced' : 'Advanced'}
                        </button>
                    </div>

                    {showAdvanced && (
                        <div style={{ marginTop: '20px', paddingTop: '20px', borderTop: `1px solid ${colors.border}`, display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
                            <div>
                                <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', color: colors.textMuted }}>Short Range (Min-Max)</label>
                                <div style={{ display: 'flex', gap: '5px' }}>
                                    <input type="number" value={ranges.short.min} onChange={e => setRanges({ ...ranges, short: { ...ranges.short, min: parseInt(e.target.value) } })} style={{ width: '60px', padding: '5px', backgroundColor: colors.bg, border: `1px solid ${colors.border}`, color: colors.text }} />
                                    <input type="number" value={ranges.short.max} onChange={e => setRanges({ ...ranges, short: { ...ranges.short, max: parseInt(e.target.value) } })} style={{ width: '60px', padding: '5px', backgroundColor: colors.bg, border: `1px solid ${colors.border}`, color: colors.text }} />
                                </div>
                            </div>
                            <div>
                                <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', color: colors.textMuted }}>Medium Range</label>
                                <div style={{ display: 'flex', gap: '5px' }}>
                                    <input type="number" value={ranges.medium.min} onChange={e => setRanges({ ...ranges, medium: { ...ranges.medium, min: parseInt(e.target.value) } })} style={{ width: '60px', padding: '5px', backgroundColor: colors.bg, border: `1px solid ${colors.border}`, color: colors.text }} />
                                    <input type="number" value={ranges.medium.max} onChange={e => setRanges({ ...ranges, medium: { ...ranges.medium, max: parseInt(e.target.value) } })} style={{ width: '60px', padding: '5px', backgroundColor: colors.bg, border: `1px solid ${colors.border}`, color: colors.text }} />
                                </div>
                            </div>
                            <div>
                                <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', color: colors.textMuted }}>Long Range</label>
                                <div style={{ display: 'flex', gap: '5px' }}>
                                    <input type="number" value={ranges.long.min} onChange={e => setRanges({ ...ranges, long: { ...ranges.long, min: parseInt(e.target.value) } })} style={{ width: '60px', padding: '5px', backgroundColor: colors.bg, border: `1px solid ${colors.border}`, color: colors.text }} />
                                    <input type="number" value={ranges.long.max} onChange={e => setRanges({ ...ranges, long: { ...ranges.long, max: parseInt(e.target.value) } })} style={{ width: '60px', padding: '5px', backgroundColor: colors.bg, border: `1px solid ${colors.border}`, color: colors.text }} />
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {error && (
                    <div style={{ padding: '15px', backgroundColor: 'rgba(244, 67, 54, 0.1)', color: colors.danger, borderRadius: '4px', marginBottom: '20px' }}>
                        Error: {error}
                    </div>
                )}

                {results && results.winners && (
                    <>
                        {/* Winners Cards */}
                        <div style={{ display: 'flex', gap: '20px', marginBottom: '30px' }}>
                            {['short', 'medium', 'long'].map((key) => {
                                const item = results.winners ? results.winners[key] : null;
                                if (!item) return null;
                                const color = key === 'short' ? colors.ema_short : (key === 'medium' ? colors.ema_med : colors.ema_long);
                                return (
                                    <div key={key} style={{
                                        flex: 1,
                                        backgroundColor: colors.cardBg,
                                        padding: '20px',
                                        borderRadius: '8px',
                                        border: `1px solid ${color}`,
                                    }}>
                                        <div style={{ fontSize: '14px', color: colors.textMuted, textTransform: 'capitalize' }}>
                                            {key} Term Winner ({ranges[key].min}-{ranges[key].max})
                                        </div>
                                        <div style={{ fontSize: '32px', fontWeight: 'bold', color: color }}>EMA {item.period}</div>
                                        <div style={{ marginTop: '10px', display: 'flex', justifyContent: 'space-between' }}>
                                            <span>Score:</span>
                                            <span style={{ fontWeight: 'bold' }}>{item.score}</span>
                                        </div>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: colors.textMuted }}>
                                            <span>Rate:</span>
                                            <span>{item.bounce_rate}%</span>
                                        </div>
                                        <div style={{ fontSize: '12px', color: colors.textMuted, marginTop: '5px' }}>
                                            <span style={{ color: colors.success }}>{item.bullish} Bull</span> • <span style={{ color: colors.danger }}>{item.bearish} Bear</span>
                                        </div>
                                    </div>
                                )
                            })}
                        </div>

                        {/* CHART */}
                        {results.chart_data && (
                            <div style={{ backgroundColor: colors.cardBg, borderRadius: '8px', border: `1px solid ${colors.border}`, padding: '20px', marginBottom: '30px', height: '500px' }}>
                                <h3 style={{ margin: '0 0 20px 0', fontSize: '18px' }}>History & Bounces</h3>
                                {/* Lightweight Chart Container */}
                                <div ref={chartContainerRef} style={{ width: '100%', height: '440px' }} />
                            </div>
                        )}

                        {/* Full Table */}
                        <div style={{ backgroundColor: colors.cardBg, borderRadius: '8px', border: `1px solid ${colors.border}`, overflow: 'hidden' }}>
                            <div style={{ padding: '15px 20px', borderBottom: `1px solid ${colors.border}`, fontWeight: 'bold' }}>
                                Full Rankings (Top 50)
                            </div>
                            <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                                    <thead style={{ backgroundColor: colors.bg, position: 'sticky', top: 0 }}>
                                        <tr>
                                            <th style={{ padding: '12px 20px', textAlign: 'left', color: colors.textMuted }}>Rank</th>
                                            <th style={{ padding: '12px 20px', textAlign: 'left', color: colors.textMuted }}>Range</th>
                                            <th style={{ padding: '12px 20px', textAlign: 'left', color: colors.textMuted }}>Period</th>
                                            <th style={{ padding: '12px 20px', textAlign: 'right', color: colors.textMuted }}>Total Bounces</th>
                                            <th style={{ padding: '12px 20px', textAlign: 'right', color: colors.textMuted }}>Rate</th>
                                            <th style={{ padding: '12px 20px', textAlign: 'right', color: colors.textMuted }}>Bull/Bear</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {results.rankings && results.rankings.slice(0, 50).map((row, i) => (
                                            <tr key={row.period} style={{ borderBottom: `1px solid ${colors.border}` }}>
                                                <td style={{ padding: '10px 20px' }}>#{i + 1}</td>
                                                <td style={{ padding: '10px 20px', color: colors.textMuted, textTransform: 'capitalize' }}>{row.range}</td>
                                                <td style={{ padding: '10px 20px', fontWeight: 'bold', color: colors.accent }}>{row.period}</td>
                                                <td style={{ padding: '10px 20px', textAlign: 'right', fontWeight: 'bold' }}>{row.bounces}</td>
                                                <td style={{ padding: '10px 20px', textAlign: 'right' }}>{row.bounce_rate}%</td>
                                                <td style={{ padding: '10px 20px', textAlign: 'right' }}>
                                                    <span style={{ color: colors.success }}>{row.bullish}</span> / <span style={{ color: colors.danger }}>{row.bearish}</span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </ErrorBoundary>
    );
};

export default EmaRespectCalculator;
