
import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import { useParams, useNavigate } from 'react-router-dom';
import { Search, ArrowRight, TrendingUp, TrendingDown, Minus, AlertCircle, CheckCircle, Activity, Zap, Target } from 'lucide-react';

const PsarReport = () => {
    const { ticker: urlTicker } = useParams();
    const navigate = useNavigate();
    const [ticker, setTicker] = useState(urlTicker || 'SPY');
    const [tickerList, setTickerList] = useState([]);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Initial Ticker Fetch
    useEffect(() => {
        fetch('/api/v1/tickers')
            .then(res => res.json())
            .then(data => {
                if (data.tickers) setTickerList(data.tickers);
            })
            .catch(err => console.error("Error fetching ticker list:", err));
    }, []);

    // Sync URL param to state
    useEffect(() => {
        if (urlTicker) {
            setTicker(urlTicker);
        }
    }, [urlTicker]);

    // Fetch Report Data
    useEffect(() => {
        fetchData(ticker);
    }, [ticker]);

    const fetchData = async (t) => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(`/api/v1/analytics/psar/${t}`);
            if (!response.ok) {
                throw new Error('Failed to fetch PSAR data');
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
        navigate(`/analysis/psar/${t}`);
    };

    // --- Chart Logic ---
    const getChartData = () => {
        if (!data || !data.history) return [];

        const dates = data.history.map(d => d.date);
        const opens = data.history.map(d => d.open);
        const highs = data.history.map(d => d.high);
        const lows = data.history.map(d => d.low);
        const closes = data.history.map(d => d.close);
        const psar = data.history.map(d => d.psar);

        // Determine Color for PSAR Dots
        // If PSAR < Close (Bullish) -> Green
        // If PSAR > Close (Bearish) -> Red
        // We can do this per point or just use logic. Standard convention:
        // Dots below usually green (support), dots above red (resistance).

        const psarColors = data.history.map(d => (d.psar < d.close ? '#4ade80' : '#f87171'));

        return [
            // Candlestick Trace
            {
                x: dates,
                close: closes,
                decreasing: { line: { color: '#f87171' } },
                high: highs,
                increasing: { line: { color: '#4ade80' } },
                line: { color: 'rgba(31,119,180,1)' },
                low: lows,
                open: opens,
                type: 'candlestick',
                xaxis: 'x',
                yaxis: 'y',
                name: 'Price'
            },
            // PSAR Scatter Trace
            {
                x: dates,
                y: psar,
                type: 'scatter',
                mode: 'markers',
                name: 'PSAR',
                marker: {
                    color: psarColors,
                    size: 4,
                    symbol: 'circle'
                }
            }
        ];
    };

    const getLayout = () => {
        return {
            autosize: true,
            title: `${ticker} - PSAR (0.02, 0.20)`,
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#cbd5e1' },
            xaxis: {
                gridcolor: '#334155',
                showgrid: true,
                rangeslider: { visible: false }
            },
            yaxis: {
                gridcolor: '#334155',
                showgrid: true,
                title: 'Price'
            },
            margin: { l: 50, r: 20, t: 40, b: 40 },
            showlegend: false
        };
    };

    // --- Conclusion Logic ---
    const getConclusion = () => {
        if (!data || !data.latest) return { title: 'Loading...', text: '', type: 'neutral' };

        const { is_bullish, psar } = data.latest;

        // Format PSAR for display
        const psarDisplay = psar ? psar.toFixed(2) : "N/A";

        if (is_bullish) {
            return {
                title: 'CONFIRMED MOMENTUM UP',
                text: `The PSAR dots are currently plotted below the price, indicating that momentum remains strongly bullish. The current PSAR value ($${psarDisplay}) should be used as the dynamic stop-loss or reversal trigger.`,
                type: 'bullish',
                icon: TrendingUp
            };
        } else {
            return {
                title: 'MOMENTUM SHIFTED BEARISH',
                text: `The PSAR dots are currently plotted above the price, indicating that the short-term momentum has flipped or the asset is in a consolidation phase. The trend is currently unfavorable for long positions until price reclaims the PSAR level.`,
                type: 'bearish',
                icon: TrendingDown
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

    const statusBadge = (val, labelTrue = 'BULLISH', labelFalse = 'BEARISH') => (
        <span style={{
            color: val ? '#4ade80' : '#f87171',
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            gap: '5px'
        }}>
            {val ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
            {val ? labelTrue : labelFalse}
        </span>
    );

    return (
        <div style={containerStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>PSAR Momentum Report</h1>
                    <span style={{ backgroundColor: '#334155', padding: '4px 8px', borderRadius: '4px', fontSize: '0.8rem', color: '#94a3b8' }}>
                        Step 0.02 / Max 0.20
                    </span>
                </div>

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
                        borderLeft: `4px solid ${conclusion.type === 'bullish' ? '#4ade80' : '#f87171'}`,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '30px'
                    }}>
                        {/* Left: Large Ticker */}
                        <div style={{
                            fontSize: '4rem',
                            fontWeight: '900',
                            color: conclusion.type === 'bullish' ? '#4ade80' : '#f87171',
                            opacity: 0.2,
                            userSelect: 'none',
                            lineHeight: 1
                        }}>
                            {ticker}
                        </div>

                        {/* Right: Content */}
                        <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                                <conclusion.icon size={24} color={conclusion.type === 'bullish' ? '#4ade80' : '#f87171'} />
                                <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>{conclusion.title}</h2>
                            </div>
                            <p style={{ lineHeight: '1.5', color: '#cbd5e1' }}>{conclusion.text}</p>
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

                        {/* Detail Stats */}
                        <div style={cardStyle}>
                            <h3 style={{ borderBottom: '1px solid #334155', paddingBottom: '10px', marginBottom: '15px', fontWeight: 'bold' }}>Market Data</h3>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '15px' }}>
                                <span>Current Price:</span>
                                <span style={{ fontFamily: 'monospace', fontSize: '1.1em', fontWeight: 'bold' }}>${l.close?.toFixed(2)}</span>

                                <span>PSAR Value (Stop):</span>
                                <span style={{ fontFamily: 'monospace', color: '#94a3b8' }}>${l.psar?.toFixed(2)}</span>

                                <div style={{ height: '1px', backgroundColor: '#334155', gridColumn: 'span 2', margin: '5px 0' }}></div>

                                <span>Momentum Status:</span>
                                {statusBadge(l.is_bullish)}
                            </div>
                        </div>

                        {/* Description / Rules */}
                        <div style={cardStyle}>
                            <h3 style={{ borderBottom: '1px solid #334155', paddingBottom: '10px', marginBottom: '15px', fontWeight: 'bold' }}>Indicator Logic</h3>
                            <ul style={{ listStyleType: 'disc', paddingLeft: '20px', spaceY: '10px', color: '#94a3b8' }}>
                                <li style={{ marginBottom: '8px' }}><b>Below Price:</b> Bullish Trend. Acts as trailing support.</li>
                                <li style={{ marginBottom: '8px' }}><b>Above Price:</b> Bearish Trend. Acts as trailing resistance.</li>
                                <li style={{ marginBottom: '8px' }}><b>Reversal:</b> Occurs when price crosses the dots. The dots flip to the other side.</li>
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
                            config={{ responsive: true }}
                        />
                    </div>
                </>
            )}
        </div>
    );
};

export default PsarReport;
