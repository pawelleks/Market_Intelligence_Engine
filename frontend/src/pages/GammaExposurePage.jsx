import React, { useState, useEffect } from 'react';
import GEXChart from '../components/GEXChart';

const GammaExposurePage = () => {
    const [ticker, setTicker] = useState('SPY');
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [loadingStatus, setLoadingStatus] = useState(''); // Granular Loading Status
    const [error, setError] = useState(null);
    const [emData, setEmData] = useState(null);
    const [viewMode, setViewMode] = useState('split');
    const [horizon, setHorizon] = useState('eow'); // 'eow', 'eom', 'eoq', 'next5', 'next30'
    const [availableTickers, setAvailableTickers] = useState([]);
    const [refreshTrigger, setRefreshTrigger] = useState(0);

    // Initial Ticker Fetch
    useEffect(() => {
        const fetchTickers = async () => {
            try {
                console.log("Fetching allowed tickers...");
                const response = await fetch('/api/v1/tickers/Gamma_Exposure');
                const data = await response.json();
                console.log("Tickers fetched:", data);
                if (data.tickers) {
                    setAvailableTickers(data.tickers);
                    if (!ticker && data.tickers.length > 0) {
                        setTicker(data.tickers[0]);
                    }
                }
            } catch (error) {
                console.error("Error fetching tickers:", error);
            }
        };
        fetchTickers();
    }, []);

    // Main Data Fetch
    useEffect(() => {
        let active = true;
        let timeoutId = null;

        const fetchData = async () => {
            setLoading(true);
            setError(null);
            setLoadingStatus('Initializing Request...');
            console.log(`[${ticker}] Starting fetch sequence...`);

            try {
                // Safety Timeout (15s)
                timeoutId = setTimeout(() => {
                    if (active) {
                        console.error("Fetch timed out!");
                        setError("Request Timed Out (15s). Server might be slow or unreachable.");
                        setLoading(false);
                    }
                }, 15000);

                // 1. Fetch GEX
                const gexUrl = `/api/v1/gex/latest/${ticker}?_t=${Date.now()}`;
                setLoadingStatus(`Fetching GEX for ${ticker}...`);
                console.log(`Fetching: ${gexUrl}`);

                const res = await fetch(gexUrl);
                console.log(`GEX Response Status: ${res.status}`);

                if (!res.ok) {
                    const errText = await res.text();
                    throw new Error(`Failed to fetch GEX (${res.status}): ${errText}`);
                }

                setLoadingStatus('Parsing GEX Data...');
                const json = await res.json();
                console.log("GEX Data Parsed:", json ? "Valid JSON" : "Empty");

                // 2. Fetch Expected Moves
                setLoadingStatus('Fetching Expected Moves...');
                const emUrl = `/api/v1/expected_moves/latest?_t=${Date.now()}`;
                const resEM = await fetch(emUrl);
                console.log(`EM Response Status: ${resEM.status}`);

                let emJson = null;
                if (resEM.ok) {
                    try {
                        emJson = await resEM.json();
                    } catch (e) {
                        console.warn("Expected Moves JSON parse failed", e);
                    }
                }

                // Update State
                if (active) {
                    setLoadingStatus('Finalizing...');
                    setData(json);

                    if (emJson && emJson.tickers && emJson.tickers[ticker]) {
                        setEmData(emJson.tickers[ticker]);
                    } else {
                        setEmData(null);
                    }
                    console.log("Data successfully set.");
                }

            } catch (err) {
                if (active) {
                    console.error("Fetch Error caught:", err);
                    setError(err.message);
                    setData(null);
                    setLoadingStatus('Error');
                }
            } finally {
                if (active) {
                    clearTimeout(timeoutId);
                    setLoading(false);
                    console.log("Loading state cleared.");
                }
            }
        };

        fetchData();

        return () => {
            active = false;
            if (timeoutId) clearTimeout(timeoutId);
        };
    }, [ticker, horizon, refreshTrigger]);

    // Prepare Data based on Horizon
    const getChartData = () => {
        if (!data?.profile) return [];

        return data.profile.map(p => {
            let call = 0;
            let put = 0;

            if (horizon === 'eow') {
                call = p.eow_call_gex || p.weekly_call_gex || 0;
                put = p.eow_put_gex || p.weekly_put_gex || 0;
            } else if (horizon === 'eom') {
                call = p.eom_call_gex || p.monthly_call_gex || 0;
                put = p.eom_put_gex || p.monthly_put_gex || 0;
            } else if (horizon === 'eoq') {
                call = p.eoq_call_gex || p.quarterly_call_gex || 0;
                put = p.eoq_put_gex || p.quarterly_put_gex || 0;
            } else if (horizon === 'next5') {
                call = p.next5_call_gex || p.weekly_call_gex || 0;
                put = p.next5_put_gex || p.weekly_put_gex || 0;
            } else if (horizon === 'next30') {
                call = p.next30_call_gex || p.monthly_call_gex || 0;
                put = p.next30_put_gex || p.monthly_put_gex || 0;
            }

            return {
                strike: p.strike,
                call_gex: call,
                put_gex: put
            };
        }).filter(d => d.call_gex !== 0 || d.put_gex !== 0);
    };

    // Get EM Range for current Horizon
    const getEmRange = () => {
        if (!emData?.expirations) return null;

        let key = 'WEEKLY'; // Default mapping
        if (horizon === 'eow' || horizon === 'next5') key = 'WEEKLY';
        if (horizon === 'eom' || horizon === 'next30' || horizon === 'eoq') key = 'MONTHLY';

        const exp = emData.expirations[key];
        if (exp) {
            return { low: exp.lower_range, high: exp.upper_range };
        }
        return null;
    };

    const chartData = getChartData();
    const emRange = getEmRange();

    // Calculate Dynamic Title with Date
    const getValidTill = () => {
        if (!data?.group_dates) return null;
        if (horizon === 'eow') return data.group_dates.eow || data.group_dates.Weekly;
        if (horizon === 'eom') return data.group_dates.eom || data.group_dates.Monthly;
        if (horizon === 'eoq') return data.group_dates.eoq || data.group_dates.Quarterly;
        if (horizon === 'next5') return data.group_dates.next5 || data.group_dates.Next5;
        if (horizon === 'next30') return data.group_dates.next30 || data.group_dates.Next30;
        return null; // Fallback
    };
    const validTill = getValidTill();

    // Helper for display name
    const horizonDisplay = {
        'eow': 'EOW', 'eom': 'EOM', 'eoq': 'EOQ', 'next5': '+5 Days', 'next30': '+30 Days'
    };
    const chartTitle = `${horizonDisplay[horizon]} GEX - ${ticker}${validTill ? ` (til ${validTill})` : ''} - ${viewMode === 'split' ? '(Split View)' : '(Net View)'}`;

    // Calculate Zoom Range (Monthly EM + 10%)
    const getZoomRange = () => {
        // Fallback strategy: Monthly -> Weekly -> ODTE
        const m = emData?.expirations?.MONTHLY || emData?.expirations?.WEEKLY || emData?.expirations?.ODTE;

        // Strict safety check: Need m object AND defined numeric ranges
        if (!m || typeof m.upper_range !== 'number' || typeof m.lower_range !== 'number') {
            return null;
        }

        const width = m.upper_range - m.lower_range;

        // Safety against zero/negative width or tiny width
        if (width < 0.1) {
            if (data?.spot_price && typeof data.spot_price === 'number') {
                return [data.spot_price * 0.95, data.spot_price * 1.05];
            }
            return null;
        }

        const buffer = width * 0.10;
        return [m.lower_range - buffer, m.upper_range + buffer];
    };
    const zoomRange = getZoomRange();

    // Calculate Net GEX for the active horizon
    const activeNetGex = chartData.reduce((sum, d) => sum + d.call_gex + d.put_gex, 0);

    // Calculate Max GEX Strike
    let maxGexStrike = 0;
    let maxGexVal = 0;
    chartData.forEach(d => {
        const net = Math.abs(d.call_gex + d.put_gex);
        if (net > maxGexVal) {
            maxGexVal = net;
            maxGexStrike = d.strike;
        }
    });

    return (
        <div style={{ padding: '20px', backgroundColor: '#121212', minHeight: '100vh', color: '#e0e0e0', fontFamily: 'Inter, sans-serif' }}>
            {/* Top Header Row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                    {/* Big Ticker Name */}
                    <div style={{ fontSize: '48px', fontWeight: '900', color: '#fff', letterSpacing: '-2px' }}>
                        {ticker}
                    </div>

                    {/* Ticker Selector */}
                    <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                        <select
                            value={ticker}
                            onChange={(e) => {
                                setTicker(e.target.value);
                                // Trigger refresh immediately
                                setTimeout(() => setRefreshTrigger(prev => prev + 1), 0);
                            }}
                            style={{
                                padding: '10px',
                                borderRadius: '4px',
                                border: '1px solid #333',
                                backgroundColor: '#1e1e1e',
                                color: '#fff',
                                fontSize: '16px'
                            }}
                        >
                            {availableTickers.map(t => (
                                <option key={t} value={t}>{t}</option>
                            ))}
                        </select>
                        <button
                            onClick={() => setRefreshTrigger(prev => prev + 1)}
                            style={{ padding: '10px 20px', backgroundColor: '#333', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                        >
                            Refresh
                        </button>
                    </div>
                </div>

                {/* Horizon Selector */}
                <div style={{ display: 'flex', backgroundColor: '#1e1e1e', borderRadius: '8px', padding: '4px' }}>
                    {[
                        { id: 'eow', label: 'EOW' },
                        { id: 'eom', label: 'EOM' },
                        { id: 'eoq', label: 'EOQ' },
                        { id: 'next5', label: '+5 Days' },
                        { id: 'next30', label: '+30 Days' }
                    ].map(h => (
                        <button
                            key={h.id}
                            onClick={() => setHorizon(h.id)}
                            style={{
                                padding: '8px 16px',
                                backgroundColor: horizon === h.id ? '#333' : 'transparent',
                                color: horizon === h.id ? '#fff' : '#888',
                                border: 'none',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                fontWeight: horizon === h.id ? 'bold' : 'normal',
                                transition: 'all 0.2s',
                                fontSize: '14px'
                            }}
                        >
                            {h.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Metrics Row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '20px' }}>
                <div style={{ backgroundColor: '#1e1e1e', padding: '20px', borderRadius: '8px', border: '1px solid #333' }}>
                    <div style={{ color: '#888', fontSize: '14px', marginBottom: '5px' }}>Spot Price</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold' }}>
                        ${data && data.spot_price ? data.spot_price.toFixed(2) : '---'}
                    </div>
                    {data && data.timestamp && (
                        <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                            {new Date(data.timestamp).toLocaleDateString()}
                        </div>
                    )}
                </div>
                <div style={{ backgroundColor: '#1e1e1e', padding: '20px', borderRadius: '8px', border: '1px solid #333' }}>
                    <div style={{ color: '#888', fontSize: '14px', marginBottom: '5px' }}>Net GEX ($)</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: activeNetGex >= 0 ? '#4caf50' : '#f44336' }}>
                        ${activeNetGex?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </div>
                </div>

                <div style={{ backgroundColor: '#1e1e1e', padding: '20px', borderRadius: '8px', border: '1px solid #333' }}>
                    <div style={{ color: '#888', fontSize: '14px', marginBottom: '5px' }}>Max GEX Strike</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#2196f3' }}>
                        ${maxGexStrike}
                    </div>
                </div>

                <div style={{ backgroundColor: '#1e1e1e', padding: '20px', borderRadius: '8px', border: '1px solid #333' }}>
                    <div style={{ color: '#888', fontSize: '14px', marginBottom: '5px' }}>Last Updated</div>
                    <div style={{ fontSize: '16px', fontWeight: 'bold', color: '#e0e0e0' }}>
                        {data && data.timestamp ? new Date(data.timestamp).toLocaleString() : '---'}
                    </div>
                </div>

                <div style={{ backgroundColor: '#1e1e1e', padding: '20px', borderRadius: '8px', border: '1px solid #333', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ display: 'flex', gap: '10px' }}>
                        <button
                            onClick={() => setViewMode('split')}
                            style={{
                                padding: '8px 12px',
                                borderRadius: '4px',
                                border: '1px solid #333',
                                backgroundColor: viewMode === 'split' ? '#2196F3' : 'transparent',
                                color: '#fff',
                                cursor: 'pointer'
                            }}
                        >
                            Split
                        </button>
                        <button
                            onClick={() => setViewMode('net')}
                            style={{
                                padding: '8px 12px',
                                borderRadius: '4px',
                                border: '1px solid #333',
                                backgroundColor: viewMode === 'net' ? '#2196F3' : 'transparent',
                                color: '#fff',
                                cursor: 'pointer'
                            }}
                        >
                            Net
                        </button>
                    </div>
                </div>
            </div>

            {/* NEW: GEX WALLS SUMMARY TABLE */}
            {!loading && data && data.profile && (
                <div style={{ marginBottom: '20px', backgroundColor: '#1e1e1e', padding: '20px', borderRadius: '8px', border: '1px solid #333' }}>
                    <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#e0e0e0' }}>Key Gamma Walls by Timeframe</h3>
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', color: '#e0e0e0' }}>
                            <thead>
                                <tr style={{ borderBottom: '1px solid #333' }}>
                                    <th style={{ padding: '10px', textAlign: 'left', color: '#888' }}>Timeframe</th>
                                    <th style={{ padding: '10px', textAlign: 'right', color: '#4caf50' }}>Call Wall (Strike)</th>
                                    <th style={{ padding: '10px', textAlign: 'right', color: '#4caf50' }}>Call GEX ($)</th>
                                    <th style={{ padding: '10px', textAlign: 'right', color: '#f44336' }}>Put Wall (Strike)</th>
                                    <th style={{ padding: '10px', textAlign: 'right', color: '#f44336' }}>Put GEX ($)</th>
                                    <th style={{ padding: '10px', textAlign: 'right', color: '#2196f3' }}>Zero GEX</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(() => {
                                    const horizons = [
                                        { key: 'eow', label: 'EOW' },
                                        { key: 'eom', label: 'EOM' },
                                        { key: 'eoq', label: 'EOQ' },
                                        { key: 'next5', label: '+5 Days' },
                                        { key: 'next30', label: '+30 Days' },
                                    ];

                                    return horizons.map(h => {
                                        // Calculate Walls Logic Per Horizon (Inline or Helper)
                                        // We iterate the profile to find max Call and min Put for THIS horizon
                                        let maxCallGex = -1;
                                        let maxCallStrike = 0;
                                        let minPutGex = 1; // Put GEX is negative
                                        let minPutStrike = 0;

                                        // Column mapping based on horizon
                                        const callKey = h.key === 'next5' ? 'next5_call_gex' :
                                            h.key === 'next30' ? 'next30_call_gex' :
                                                `${h.key}_call_gex`;
                                        const putKey = h.key === 'next5' ? 'next5_put_gex' :
                                            h.key === 'next30' ? 'next30_put_gex' :
                                                `${h.key}_put_gex`;

                                        // Fallback keys for legacy data
                                        const callKeyLegacy = h.key === 'eow' ? 'weekly_call_gex' :
                                            h.key === 'eom' ? 'monthly_call_gex' :
                                                h.key === 'eoq' ? 'quarterly_call_gex' : callKey;
                                        const putKeyLegacy = h.key === 'eow' ? 'weekly_put_gex' :
                                            h.key === 'eom' ? 'monthly_put_gex' :
                                                h.key === 'eoq' ? 'quarterly_put_gex' : putKey;

                                        data.profile.forEach(p => {
                                            const cVol = p[callKey] || p[callKeyLegacy] || 0;
                                            const pVol = p[putKey] || p[putKeyLegacy] || 0;

                                            if (cVol > maxCallGex) {
                                                maxCallGex = cVol;
                                                maxCallStrike = p.strike;
                                            }
                                            // Put GEX is usually negative, we want the "Largest Negative" (Scanning for min)
                                            if (pVol < minPutGex) {
                                                minPutGex = pVol;
                                                minPutStrike = p.strike;
                                            }
                                        });

                                        if (maxCallGex === -1 && minPutGex === 1) return null; // No data for this timeframe

                                        return (
                                            <tr key={h.key} style={{ borderBottom: '1px solid #222' }}>
                                                <td style={{ padding: '10px', fontWeight: 'bold' }}>{h.label}</td>
                                                <td style={{ padding: '10px', textAlign: 'right', fontWeight: 'bold' }}>${maxCallStrike}</td>
                                                <td style={{ padding: '10px', textAlign: 'right', fontFamily: 'monospace' }}>${maxCallGex.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                                                <td style={{ padding: '10px', textAlign: 'right', fontWeight: 'bold' }}>${minPutStrike}</td>
                                                <td style={{ padding: '10px', textAlign: 'right', fontFamily: 'monospace' }}>${minPutGex.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                                                <td style={{ padding: '10px', textAlign: 'right', color: '#666' }}>-</td>
                                            </tr>
                                        );
                                    });
                                })()}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* LOADING INDICATOR */}
            {loading && (
                <div style={{ textAlign: 'center', padding: '50px', color: '#aaa' }}>
                    <h2>{loadingStatus || 'Loading GEX Data...'}</h2>
                </div>
            )}

            {/* ERROR */}
            {error && (
                <div style={{ backgroundColor: 'rgba(244, 67, 54, 0.1)', border: '1px solid #f44336', color: '#f44336', padding: '15px', borderRadius: '4px', marginBottom: '20px' }}>
                    <strong>Error:</strong> {error}
                </div>
            )}

            {/* CONTENT */}
            {!loading && data && (
                <div>
                    {/* Check for empty chart data */}
                    {chartData.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '40px', color: '#888' }}>
                            <h3>No Options Data Available for this Horizon</h3>
                            <p>Try selecting a different horizon or ticker.</p>
                        </div>
                    ) : (
                        <div style={{ backgroundColor: '#1e1e1e', padding: '20px', borderRadius: '8px', border: '1px solid #333' }}>
                            <GEXChart
                                data={chartData}
                                spotPrice={data.spot_price}
                                emRange={emRange}
                                title={chartTitle}
                                viewMode={viewMode}
                                yAxisRange={zoomRange}
                                height={600}
                                horizonLabel={horizon.charAt(0).toUpperCase()}
                            />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error("GEX Page Error:", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: '20px', color: '#f44336', backgroundColor: '#0e1525', minHeight: '100vh' }}>
                    <h2>Something went wrong displaying GEX.</h2>
                    <pre style={{ whiteSpace: 'pre-wrap' }}>{this.state.error && this.state.error.toString()}</pre>
                </div>
            );
        }
        return this.props.children;
    }
}

const GammaExposurePageWrapper = () => {
    return (
        <ErrorBoundary>
            <GammaExposurePage />
        </ErrorBoundary>
    );
};

export default GammaExposurePageWrapper;
