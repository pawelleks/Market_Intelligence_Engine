
import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import { useParams, useNavigate } from 'react-router-dom';
import { Search, ArrowRight, TrendingUp, TrendingDown, Minus, AlertCircle, CheckCircle, Activity, Zap } from 'lucide-react';

const AdxReport = () => {
    const { ticker: urlTicker } = useParams();
    const navigate = useNavigate();
    const [ticker, setTicker] = useState(urlTicker || 'SPY');
    const [tickerList, setTickerList] = useState([]);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

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
            const response = await fetch(`/api/v1/analytics/adx/${t}`);
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
        navigate(`/analysis/adx/${t}`);
    };

    // --- Chart Logic ---
    const getChartData = () => {
        if (!data || !data.history) return [];

        const dates = data.history.map(d => d.date);
        const closes = data.history.map(d => d.close);
        const adx = data.history.map(d => d.adx);
        const pdi = data.history.map(d => d.plus_di);
        const mdi = data.history.map(d => d.minus_di);

        return [
            // Pane 1: Price
            {
                x: dates,
                y: closes,
                type: 'scatter',
                mode: 'lines',
                name: 'Price',
                line: { color: '#ffffff', width: 2 },
                xaxis: 'x',
                yaxis: 'y'
            },
            // Pane 2: ADX
            {
                x: dates,
                y: adx,
                type: 'scatter',
                mode: 'lines',
                name: 'ADX',
                line: { color: '#ffffff', width: 2 },
                xaxis: 'x', // Shared X axis
                yaxis: 'y2'
            },
            {
                x: dates,
                y: pdi,
                type: 'scatter',
                mode: 'lines',
                name: '+DI',
                line: { color: '#4ade80', width: 1.5 }, // Green
                xaxis: 'x',
                yaxis: 'y2'
            },
            {
                x: dates,
                y: mdi,
                type: 'scatter',
                mode: 'lines',
                name: '-DI',
                line: { color: '#f87171', width: 1.5 }, // Red
                xaxis: 'x',
                yaxis: 'y2'
            }
        ];
    };

    const getLayout = () => {
        return {
            autosize: true,
            title: `${ticker} - Price vs ADX/DMI`,
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#cbd5e1' },
            grid: { rows: 2, columns: 1, pattern: 'independent' },
            xaxis: {
                gridcolor: '#334155',
                showgrid: true,
                domain: [0, 1],
                anchor: 'y2'
                // Creating standard stacked subplots manually via axis domains:
            },
            // Top Plot (Price)
            yaxis: {
                domain: [0.6, 1], // Top 40%
                gridcolor: '#334155',
                showgrid: true,
                title: 'Price'
            },
            // Bottom Plot (ADX)
            yaxis2: {
                domain: [0, 0.5], // Bottom 50%
                gridcolor: '#334155',
                showgrid: true,
                title: 'ADX/DMI'
            },
            margin: { l: 50, r: 20, t: 40, b: 40 },
            shapes: [
                // Horizontal Line at ADX=25
                {
                    type: 'line',
                    xref: 'paper',
                    x0: 0,
                    x1: 1,
                    yref: 'y2', // Refer to bottom plot axis
                    y0: 25,
                    y1: 25,
                    line: {
                        color: '#94a3b8',
                        width: 1,
                        dash: 'dash'
                    }
                }
            ]
        };
    };

    // --- Conclusion Logic ---
    const getConclusion = () => {
        if (!data || !data.latest) return { title: 'Loading...', text: '', type: 'neutral' };

        const { is_adx_strong, is_adx_uptrend } = data.latest;

        if (is_adx_strong && is_adx_uptrend) {
            return {
                title: 'STRONG, CONFIRMED UPTREND',
                text: 'The ADX value is above the 25 threshold, and the positive directional movement is dominant (+DI > -DI). This is a high-confidence trend environment.',
                type: 'bullish',
                icon: TrendingUp
            };
        } else if (is_adx_strong && !is_adx_uptrend) {
            return {
                title: 'STRONG DOWNTREND',
                text: 'The trend is strong (ADX > 25), but the negative directional movement is dominant (-DI > +DI). This is a strong environment for short-selling or an avoid signal for long-term investing.',
                type: 'bearish',
                icon: TrendingDown
            };
        } else if (!is_adx_strong && is_adx_uptrend) {
            return {
                title: 'WEAK/EARLY UPTREND',
                text: 'Positive directional movement is dominant, but the ADX is below 25. The asset is either consolidating or just beginning a new trend. Confirmation from other indicators is vital.',
                type: 'warning',
                icon: Activity
            };
        } else {
            // Catch-all: Else (Range Bound)
            return {
                title: 'RANGE BOUND / NO TREND',
                text: 'The ADX is low and the +DI and -DI lines are close, indicating a choppy, directionless market. Avoid positions until a clear trend emerges.',
                type: 'neutral',
                icon: Minus
            };
        }
    };

    const conclusion = getConclusion();
    const l = data?.latest || {};

    // Styles
    const containerStyle = { padding: '20px', color: '#e2e8f0', minHeight: '100vh', backgroundColor: '#0f172a' };
    const cardStyle = { backgroundColor: '#1e293b', borderRadius: '8px', padding: '20px', marginBottom: '20px', border: '1px solid #334155' };
    const selectStyle = {
        backgroundColor: '#0f172a',
        border: '1px solid #334155',
        color: 'white',
        padding: '8px 32px 8px 12px',
        borderRadius: '4px',
        cursor: 'pointer',
        fontSize: '0.9rem',
        minWidth: '150px'
    };
    const buttonStyle = { backgroundColor: '#3b82f6', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '4px', cursor: 'pointer' };

    const statusBadge = (val, trueColor = '#4ade80', falseColor = '#f87171') => (
        <span style={{
            color: val ? trueColor : falseColor,
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            gap: '5px'
        }}>
            {val ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
            {val ? 'TRUE' : 'FALSE'}
        </span>
    );

    return (
        <div style={containerStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>ADX Trend Strength Report</h1>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ color: '#94a3b8', fontSize: '0.9rem' }}>Ticker:</span>
                    <select
                        value={ticker}
                        onChange={handleTickerChange}
                        style={selectStyle}
                    >
                        {tickerList.length === 0 && <option value={ticker}>{ticker}</option>}
                        {tickerList.map(t => (
                            <option key={t} value={t}>{t}</option>
                        ))}
                    </select>
                </div>
            </div>

            {error && <div style={{ ...cardStyle, borderColor: '#ef4444', color: '#ef4444' }}>Error: {error}</div>}
            {loading && <div style={cardStyle}>Loading data for {ticker}...</div>}

            {data && !loading && (
                <>
                    {/* Conclusion Box */}
                    <div style={{
                        ...cardStyle,
                        borderLeft: `4px solid ${conclusion.type === 'bullish' ? '#4ade80' :
                            conclusion.type === 'bearish' ? '#f87171' :
                                conclusion.type === 'warning' ? '#facc15' : '#94a3b8'
                            }`,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '30px'
                    }}>
                        {/* Left: Large Ticker */}
                        <div style={{
                            fontSize: '4rem',
                            fontWeight: '900',
                            color: conclusion.type === 'bullish' ? '#4ade80' :
                                conclusion.type === 'bearish' ? '#f87171' :
                                    conclusion.type === 'warning' ? '#facc15' : '#94a3b8',
                            opacity: 0.2,
                            userSelect: 'none',
                            lineHeight: 1
                        }}>
                            {ticker}
                        </div>

                        {/* Right: Content */}
                        <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                                <conclusion.icon size={24} color={
                                    conclusion.type === 'bullish' ? '#4ade80' :
                                        conclusion.type === 'bearish' ? '#f87171' :
                                            conclusion.type === 'warning' ? '#facc15' : '#94a3b8'
                                } />
                                <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>{conclusion.title}</h2>
                            </div>
                            <p style={{ lineHeight: '1.5', color: '#cbd5e1' }}>{conclusion.text}</p>
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

                        {/* Detail Stats */}
                        <div style={cardStyle}>
                            <h3 style={{ borderBottom: '1px solid #334155', paddingBottom: '10px', marginBottom: '15px', fontWeight: 'bold' }}>ADX Analysis</h3>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '15px' }}>
                                <span>ADX Value:</span>
                                <span style={{ fontFamily: 'monospace', fontSize: '1.1em', fontWeight: 'bold' }}>{l.adx?.toFixed(2)}</span>

                                <span>+DI (Green):</span>
                                <span style={{ fontFamily: 'monospace', color: '#4ade80' }}>{l.plus_di?.toFixed(2)}</span>

                                <span>-DI (Red):</span>
                                <span style={{ fontFamily: 'monospace', color: '#f87171' }}>{l.minus_di?.toFixed(2)}</span>

                                <div style={{ height: '1px', backgroundColor: '#334155', gridColumn: 'span 2', margin: '5px 0' }}></div>

                                <span>Status: Trend Strong ({'>'}25):</span>
                                {statusBadge(l.is_adx_strong)}

                                <span>Status: Uptrend (+DI{'>'}-DI):</span>
                                {statusBadge(l.is_adx_uptrend)}

                                <span>Status: Accelerating:</span>
                                {statusBadge(l.is_adx_accelerating, '#4ade80', '#94a3b8')}
                            </div>
                        </div>

                        {/* Description / Rules */}
                        <div style={cardStyle}>
                            <h3 style={{ borderBottom: '1px solid #334155', paddingBottom: '10px', marginBottom: '15px', fontWeight: 'bold' }}>Strategy Logic</h3>
                            <ul style={{ listStyleType: 'disc', paddingLeft: '20px', spaceY: '10px', color: '#94a3b8' }}>
                                <li style={{ marginBottom: '8px' }}><b>ADX {'>'} 25:</b> The primary filter for trend existence. Below 25 = choppy/sideways.</li>
                                <li style={{ marginBottom: '8px' }}><b>+DI vs -DI:</b> Determines trend direction (Up vs Down).</li>
                                <li style={{ marginBottom: '8px' }}><b>Accelerating:</b> If ADX is rising, the trend is gaining strength. If falling, the trend is losing momentum (even if still {'>'} 25).</li>
                            </ul>
                        </div>
                    </div>

                    {/* Chart */}
                    <div style={{ ...cardStyle, height: '600px' }}>
                        <Plot
                            data={getChartData()}
                            layout={getLayout()}
                            useResizeHandler={true}
                            style={{ width: '100%', height: '100%' }}
                        />
                    </div>
                </>
            )}
        </div>
    );
};

export default AdxReport;
