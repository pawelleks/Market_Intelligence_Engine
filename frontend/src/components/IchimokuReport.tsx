
import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import { useParams, useNavigate } from 'react-router-dom';
import { Info } from 'lucide-react';


interface IchimokuData {
    verdict: {
        status: string;
        reason: string;
        flags: {
            is_above_cloud: boolean;
            is_cloud_green: boolean;
            is_chikou_confirmed: boolean;
        };
    };
    series: Array<{
        date: string;
        open: number;
        high: number;
        low: number;
        close: number;
        tenkan_sen: number | null;
        kijun_sen: number | null;
        senkou_span_a: number | null;
        senkou_span_b: number | null;
        chikou_plotted: number | null;
    }>;
}

const IchimokuReport = () => {
    const { ticker: urlTicker } = useParams<{ ticker: string }>();
    const navigate = useNavigate();
    const [ticker, setTicker] = useState(urlTicker || 'SPY');
    const [tickerList, setTickerList] = useState<string[]>([]);
    const [data, setData] = useState<IchimokuData | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    // Fetch Ticker List
    useEffect(() => {
        fetch('/api/v1/tickers')
            .then(res => res.json())
            .then(data => {
                if (data.tickers) setTickerList(data.tickers);
            })
            .catch(err => console.error("Error fetching ticker list:", err));
    }, []);

    // Sync state with URL
    useEffect(() => {
        if (urlTicker) {
            setTicker(urlTicker);
        }
    }, [urlTicker]);

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const response = await fetch(`/api/v1/analytics/trend/ichimoku/${ticker}`);
                if (!response.ok) {
                    throw new Error(`Error fetching data: ${response.statusText}`);
                }
                const json = await response.json();
                setData(json);
            } catch (err: any) {
                setError(err.message || 'Unknown error');
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [ticker]);

    const handleTickerChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const t = e.target.value;
        setTicker(t);
        navigate(`/investing/ichimoku/${t}`);
    };

    if (loading) return <div style={{ padding: 20, color: '#fff' }}>Loading Ichimoku Analysis...</div>;
    if (error) return <div style={{ padding: 20, color: '#ff6b6b' }}>Error: {error}</div>;
    if (!data) return null;

    // --- DERIVED LOGIC ---
    const { is_above_cloud, is_cloud_green, is_chikou_confirmed } = data.verdict.flags;

    let displayStatus = "NEUTRAL";
    let displayReason = data.verdict.reason;
    let displayColor = "#ffab00"; // Amber

    if (is_above_cloud) {
        if (is_cloud_green) {
            // Strong Bullish
            displayStatus = "STRONG BULLISH";
            displayColor = "#4caf50"; // Green
            displayReason = "Price is solidly above a rising Green Cloud. Primary trend and momentum are aligned.";
        } else {
            // Caution
            displayStatus = "BULLISH (CAUTION)";
            displayColor = "#ff9800"; // Orange
            displayReason = "Price is maintaining its uptrend, but internal momentum (Cloud Color) has shifted, suggesting a potential slowdown or range-bound behavior.";
        }
    } else {
        // Bearish (Below Cloud)
        // Check if inside? Current API says is_above_cloud = True/False.
        // Assuming False means Inside OR Below. 
        // If we want detailed 'Below', we assume False is Bearish for this high-level view.
        // Or strictly: Close < Span A AND Close < Span B.
        displayStatus = "BEARISH";
        displayColor = "#ef5350"; // Red
        displayReason = "Price is trading below the Cloud resistance zone.";
    }

    // Chart Data Prep
    const dates = data.series.map(d => d.date);
    const spanA = data.series.map(d => d.senkou_span_a);
    const spanB = data.series.map(d => d.senkou_span_b);
    // ... plotting data

    return (
        <div style={{ padding: '20px', color: '#e0e0e0', backgroundColor: '#0b1220', minHeight: '100vh', display: 'flex', flexDirection: 'column', gap: '15px' }}>

            {/* Header & Verdict Section */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '15px' }}>

                {/* Title Card */}
                <div style={{ backgroundColor: '#162032', padding: '15px 20px', borderRadius: '6px', border: '1px solid #1e293b', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <h1 style={{ margin: 0, fontSize: '20px', color: '#94a3b8' }}>Ichimoku Cloud</h1>
                            <h2 style={{ margin: '5px 0 0 0', fontSize: '28px', color: '#fff', fontWeight: 'bold' }}>{ticker}</h2>
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
                                {tickerList.map(t => <option key={t} value={t}>{t}</option>)}
                            </select>
                        </div>
                    </div>
                    <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '10px' }}>
                        High-density trend verification system using the Ichimoku Kinko Hyo equilibrium logic.
                    </div>
                </div>

                {/* Verdict Card */}
                <div style={{ backgroundColor: '#162032', padding: '15px 20px', borderRadius: '6px', border: `1px solid ${displayColor}`, borderLeft: `4px solid ${displayColor}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                            <h2 style={{ margin: 0, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '1px', color: '#94a3b8' }}>Trend Verdict</h2>
                            <div style={{ fontSize: '22px', fontWeight: 'bold', color: displayColor, marginTop: '4px' }}>
                                {displayStatus}
                            </div>
                        </div>

                        {/* Sub-Badges */}
                        <div style={{ display: 'flex', gap: '10px' }}>
                            {/* Primary Trend Badge */}
                            <div style={{
                                display: 'flex', flexDirection: 'column', alignItems: 'center',
                                backgroundColor: '#0f172a', padding: '6px 10px', borderRadius: '4px', border: '1px solid #334155'
                            }}>
                                <span style={{ fontSize: '9px', color: '#64748b', textTransform: 'uppercase' }}>Primary</span>
                                <span style={{ fontSize: '11px', fontWeight: 'bold', color: is_above_cloud ? '#4caf50' : '#ef5350' }}>
                                    {is_above_cloud ? "ABOVE CLOUD" : "BELOW CLOUD"}
                                </span>
                            </div>

                            {/* Sentiment Badge */}
                            <div style={{
                                display: 'flex', flexDirection: 'column', alignItems: 'center',
                                backgroundColor: '#0f172a', padding: '6px 10px', borderRadius: '4px', border: '1px solid #334155'
                            }}>
                                <span style={{ fontSize: '9px', color: '#64748b', textTransform: 'uppercase' }}>Sentiment</span>
                                <span style={{ fontSize: '11px', fontWeight: 'bold', color: is_cloud_green ? '#4caf50' : '#ff9800' }}>
                                    {is_cloud_green ? "UPTREND" : "WEAKENING"}
                                </span>
                            </div>
                        </div>
                    </div>

                    <p style={{ margin: '12px 0 0 0', fontSize: '13px', color: '#cbd5e1', lineHeight: '1.4' }}>
                        {displayReason}
                    </p>

                    {/* Flags */}
                    <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                        <FlagBadge
                            label="Above Cloud"
                            active={is_above_cloud}
                            description="Price trading ABOVE the Cloud (Kumo) indicates a primary Bullish trend."
                        />
                        <FlagBadge
                            label="Green Cloud"
                            active={is_cloud_green}
                            description="Future support structure. Green = Rising Support. Red = Falling/Weak Support."
                        />
                        <FlagBadge
                            label="Chikou Confirmed"
                            active={is_chikou_confirmed}
                            description="Lagging Span confirms no historical resistance."
                        />
                    </div>
                </div>
            </div>

            {/* Chart Section */}
            <div style={{ backgroundColor: '#162032', padding: '0', borderRadius: '6px', border: '1px solid #1e293b', overflow: 'hidden', minHeight: '550px', display: 'flex', flexDirection: 'column' }}>
                <div style={{ flex: 1, position: 'relative' }}>
                    <Plot
                        style={{ width: '100%', height: '100%' }}
                        useResizeHandler={true}
                        data={[
                            // Cloud
                            {
                                x: dates, y: spanA, type: 'scatter', mode: 'lines', name: 'Span A',
                                line: { color: 'rgba(46, 204, 113, 0.4)', width: 1 }, legendgroup: 'cloud', hoverinfo: 'none'
                            },
                            {
                                x: dates, y: spanB, type: 'scatter', mode: 'lines', name: 'Span B',
                                line: { color: 'rgba(239, 83, 80, 0.4)', width: 1 }, legendgroup: 'cloud', fill: 'tonexty', fillcolor: 'rgba(128, 128, 128, 0.1)', hoverinfo: 'none'
                            },
                            // Price
                            {
                                x: dates, open: data.series.map(d => d.open), high: data.series.map(d => d.high), low: data.series.map(d => d.low), close: data.series.map(d => d.close),
                                type: 'candlestick', name: 'Price', increasing: { line: { color: '#00e676' }, fillcolor: '#00e676' }, decreasing: { line: { color: '#ef5350' }, fillcolor: '#ef5350' }
                            },
                            // Lines
                            {
                                x: dates, y: data.series.map(d => d.tenkan_sen), type: 'scatter', mode: 'lines', name: 'Tenkan', line: { color: '#29b6f6', width: 1.5 }
                            },
                            {
                                x: dates, y: data.series.map(d => d.kijun_sen), type: 'scatter', mode: 'lines', name: 'Kijun', line: { color: '#ef5350', width: 1.5 }
                            },
                            {
                                x: dates, y: data.series.map(d => d.chikou_plotted), type: 'scatter', mode: 'lines', name: 'Chikou', line: { color: '#ab47bc', width: 2, dash: 'dot' }
                            }
                        ]}
                        layout={{
                            paper_bgcolor: 'rgba(0,0,0,0)',
                            plot_bgcolor: 'rgba(0,0,0,0)',
                            font: { color: '#94a3b8', family: 'Inter' },
                            xaxis: { gridcolor: '#1e293b', rangeslider: { visible: false }, type: 'date', tickfont: { size: 11 } },
                            yaxis: { gridcolor: '#1e293b', tickfont: { size: 11 } },
                            margin: { t: 40, r: 20, l: 40, b: 30 },
                            showlegend: true,
                            legend: { orientation: 'h', x: 0, y: 1.02, bgcolor: 'rgba(0,0,0,0)', font: { size: 10 } }
                        }}
                        config={{ responsive: true, displayModeBar: false }}
                    />
                </div>
                <div style={{ borderTop: '1px solid #1e293b' }}>
                    <ChartKey />
                </div>
            </div>
        </div>
    );
};

function FlagBadge({ label, active, description }: { label: string, active: boolean, description: string }) {
    const [showTooltip, setShowTooltip] = useState(false);

    return (
        <div
            style={{ position: 'relative' }}
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onClick={() => setShowTooltip(!showTooltip)}
        >
            <div style={{
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 'bold',
                backgroundColor: active ? '#00e67620' : '#2d3b55',
                color: active ? '#00e676' : '#8b9bb4',
                border: `1px solid ${active ? '#00e676' : '#2d3b55'}`,
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer',
                userSelect: 'none'
            }}>
                {label} {active ? '✓' : '✗'}
                <Info size={12} style={{ opacity: 0.7 }} />
            </div>

            {showTooltip && (
                <div style={{
                    position: 'absolute',
                    bottom: '100%',
                    marginBottom: '8px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    width: '220px',
                    backgroundColor: '#0f172a',
                    border: '1px solid #1e293b',
                    padding: '8px',
                    borderRadius: '6px',
                    fontSize: '11px',
                    color: '#cbd5e1',
                    zIndex: 50,
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.5)',
                    lineHeight: '1.4'
                }}>
                    {description}
                    {/* Arrow */}
                    <div style={{
                        position: 'absolute',
                        top: '100%',
                        left: '50%',
                        marginLeft: '-5px',
                        borderWidth: '5px',
                        borderStyle: 'solid',
                        borderColor: '#1e293b transparent transparent transparent'
                    }} />
                </div>
            )}
        </div>
    );
};

function ChartKey() {
    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px', marginTop: '15px', padding: '15px', backgroundColor: '#0f172a', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <h3 style={{ gridColumn: '1 / -1', margin: '0 0 5px 0', fontSize: '14px', color: '#94a3b8' }}>Chart Key</h3>

            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#29b6f6', marginTop: '4px', borderRadius: '2px' }} />
                <div>
                    <div style={{ color: '#e2e8f0', fontSize: '12px', fontWeight: '600' }}>Tenkan (Blue)</div>
                    <div style={{ color: '#64748b', fontSize: '11px' }}>Short-term momentum (9-day). Price often returns to this.</div>
                </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#ef5350', marginTop: '4px', borderRadius: '2px' }} />
                <div>
                    <div style={{ color: '#e2e8f0', fontSize: '12px', fontWeight: '600' }}>Kijun (Red)</div>
                    <div style={{ color: '#64748b', fontSize: '11px' }}>Medium-term baseline (26-day). The main trend indicator.</div>
                </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                <div style={{ width: '12px', height: '12px', background: 'linear-gradient(to right, rgba(46, 204, 113, 0.5), rgba(231, 76, 60, 0.5))', marginTop: '4px', borderRadius: '2px' }} />
                <div>
                    <div style={{ color: '#e2e8f0', fontSize: '12px', fontWeight: '600' }}>The Cloud (Kumo)</div>
                    <div style={{ color: '#64748b', fontSize: '11px' }}>Future support/resistance zones. Shaded area between Span A/B.</div>
                </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#ab47bc', marginTop: '4px', borderRadius: '50%' }} />
                <div>
                    <div style={{ color: '#e2e8f0', fontSize: '12px', fontWeight: '600' }}>Chikou (Purple)</div>
                    <div style={{ color: '#64748b', fontSize: '11px' }}>Lagging span (price shifted back). Checks for overhead resistance.</div>
                </div>
            </div>
        </div>
    );
}

export default IchimokuReport;
