import React, { useState, useEffect } from 'react';
import GEXChart from '../components/GEXChart';
import GexHeatmap from '../components/GexHeatmap';
import { usePageTitle } from '../hooks/usePageTitle';

const GammaExposurePage = () => {
    usePageTitle('Gamma Exposure');
    const [ticker, setTicker] = useState('SPY');
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [loadingStatus, setLoadingStatus] = useState(''); // Granular Loading Status
    const [error, setError] = useState(null);
    const [emData, setEmData] = useState(null);
    const [viewMode, setViewMode] = useState('split');
    const [horizon, setHorizon] = useState('total'); // 'total', 'eow', 'eom', 'eoq', 'next5', 'next30'
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

            if (horizon === 'total') {
                call = p.total_call_gex || 0;
                put = p.total_put_gex || 0;
            } else if (horizon === 'eow') {
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

        let key = 'MONTHLY'; // Default mapping
        if (horizon === 'eow' || horizon === 'next5') key = 'WEEKLY';
        if (horizon === 'eom' || horizon === 'next30' || horizon === 'eoq' || horizon === 'total') key = 'MONTHLY';

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
        if (horizon === 'total') return 'All Expirations';
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
        'total': 'Total', 'eow': 'EOW', 'eom': 'EOM', 'eoq': 'EOQ', 'next5': '+5 Days', 'next30': '+30 Days'
    };
    const chartTitle = `${horizonDisplay[horizon]} GEX - ${ticker}${validTill ? ` (til ${validTill})` : ''} - ${viewMode === 'split' ? '(Split View)' : '(Net View)'}`;

    // Calculate Zoom Range (Active Horizon EM + Buffer)
    const getZoomRange = () => {
        const spot = data?.spot_price;
        // Minimum sensible zoom width: 3% of spot price (e.g., ~$20 for SPY at $690)
        const minWidth = (spot && typeof spot === 'number') ? spot * 0.03 : 10;

        // 1. Prioritize Valid EM for the CURRENT horizon so it's always visible
        if (emRange && typeof emRange.low === 'number' && typeof emRange.high === 'number') {
            const width = emRange.high - emRange.low;
            if (width >= minWidth) {
                const buffer = width * 0.15; // 15% buffer
                return [emRange.low - buffer, emRange.high + buffer];
            }
        }

        // 2. Fallback strategy: Monthly -> Weekly -> ODTE
        const m = emData?.expirations?.MONTHLY || emData?.expirations?.WEEKLY || emData?.expirations?.ODTE;

        if (m && typeof m.upper_range === 'number' && typeof m.lower_range === 'number') {
            const width = m.upper_range - m.lower_range;
            if (width >= minWidth) {
                const buffer = width * 0.10;
                return [m.lower_range - buffer, m.upper_range + buffer];
            }
        }

        // 3. Fallback to spot ± 5% when EM range is missing or too narrow
        if (spot && typeof spot === 'number') {
            return [spot * 0.95, spot * 1.05];
        }
        return null;
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
        <div style={{ padding: '20px', backgroundColor: '#0b1220', minHeight: '100vh', color: '#d7e3f3', fontFamily: 'Inter, sans-serif' }}>
            {/* Standard Header Layout */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid #203049', paddingBottom: '15px' }}>
                <h2 style={{ fontSize: '1.5rem', margin: 0, color: '#d7e3f3' }}>
                    Gamma Exposure Analysis <span style={{ color: '#9e9e9e', fontSize: '1rem', marginLeft: '10px' }}>{'>'} {ticker}</span>
                </h2>

                <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
                    {/* Horizon Selector (Moved to right with ticker) */}
                    <div style={{ display: 'flex', backgroundColor: '#0e1525', borderRadius: '6px', padding: '2px', border: '1px solid #203049' }}>
                        {[
                            { id: 'total', label: 'Total' },
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
                                    padding: '6px 12px',
                                    backgroundColor: horizon === h.id ? '#203049' : 'transparent',
                                    color: horizon === h.id ? '#fff' : '#888',
                                    border: 'none',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontWeight: horizon === h.id ? 'bold' : 'normal',
                                    fontSize: '13px'
                                }}
                            >
                                {h.label}
                            </button>
                        ))}
                    </div>

                    {/* Ticker Selector */}
                    <div style={{ display: 'flex', gap: '5px' }}>
                        <select
                            value={ticker}
                            onChange={(e) => {
                                setTicker(e.target.value);
                                // Trigger refresh immediately
                                setTimeout(() => setRefreshTrigger(prev => prev + 1), 0);
                            }}
                            style={{
                                padding: '8px',
                                borderRadius: '4px',
                                border: '1px solid #203049',
                                backgroundColor: '#0e1525',
                                color: '#d7e3f3',
                                fontSize: '14px',
                                cursor: 'pointer'
                            }}
                        >
                            {availableTickers.map(t => (
                                <option key={t} value={t}>{t}</option>
                            ))}
                        </select>
                        <button
                            onClick={() => setRefreshTrigger(prev => prev + 1)}
                            style={{
                                padding: '8px 12px',
                                backgroundColor: '#203049',
                                color: '#d7e3f3',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '14px'
                            }}
                        >
                            Refresh
                        </button>
                    </div>
                </div>
            </div>

            {/* Metrics Row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '20px' }}>
                <div style={{ backgroundColor: '#0e1525', padding: '15px', borderRadius: '8px', border: '1px solid #203049' }}>
                    <div style={{ color: '#9e9e9e', fontSize: '12px', marginBottom: '5px', textTransform: 'uppercase' }}>Spot Price</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold' }}>
                        ${data && data.spot_price ? data.spot_price.toFixed(2) : '---'}
                    </div>
                    {data && data.timestamp && (
                        <div style={{ fontSize: '11px', color: '#666', marginTop: '4px' }}>
                            {new Date(data.timestamp).toLocaleDateString()}
                        </div>
                    )}
                </div>
                <div style={{ backgroundColor: '#0e1525', padding: '15px', borderRadius: '8px', border: '1px solid #203049' }}>
                    <div style={{ color: '#9e9e9e', fontSize: '12px', marginBottom: '5px', textTransform: 'uppercase' }}>Net GEX ($)</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: activeNetGex >= 0 ? '#4caf50' : '#f44336' }}>
                        ${activeNetGex?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </div>
                </div>

                <div style={{ backgroundColor: '#0e1525', padding: '15px', borderRadius: '8px', border: '1px solid #203049' }}>
                    <div style={{ color: '#9e9e9e', fontSize: '12px', marginBottom: '5px', textTransform: 'uppercase' }}>Max GEX Strike</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#2196f3' }}>
                        ${maxGexStrike}
                    </div>
                </div>

                <div style={{ backgroundColor: '#0e1525', padding: '15px', borderRadius: '8px', border: '1px solid #203049', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '10px' }}>
                    <div style={{ display: 'flex', gap: '5px', width: '100%' }}>
                        <button
                            onClick={() => setViewMode('split')}
                            style={{
                                flex: 1,
                                padding: '6px',
                                borderRadius: '4px',
                                border: '1px solid #203049',
                                backgroundColor: viewMode === 'split' ? '#2196F3' : 'transparent',
                                color: '#d7e3f3',
                                cursor: 'pointer',
                                fontSize: '12px'
                            }}
                        >
                            Split
                        </button>
                        <button
                            onClick={() => setViewMode('net')}
                            style={{
                                flex: 1,
                                padding: '6px',
                                borderRadius: '4px',
                                border: '1px solid #203049',
                                backgroundColor: viewMode === 'net' ? '#2196F3' : 'transparent',
                                color: '#d7e3f3',
                                cursor: 'pointer',
                                fontSize: '12px'
                            }}
                        >
                            Net
                        </button>
                    </div>
                </div>
            </div>

            {/* ERROR */}
            {error && (
                <div style={{ backgroundColor: 'rgba(244, 67, 54, 0.1)', border: '1px solid #f44336', color: '#f44336', padding: '15px', borderRadius: '4px', marginBottom: '20px' }}>
                    <strong>Error:</strong> {error}
                </div>
            )}

            {/* LOADING INDICATOR */}
            {loading && (
                <div style={{ textAlign: 'center', padding: '50px', color: '#9e9e9e' }}>
                    <h2>{loadingStatus || 'Loading GEX Data...'}</h2>
                </div>
            )}

            {/* CHART CONTENT */}
            {!loading && data && (
                <div>
                    {/* Check for empty chart data */}
                    {chartData.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '40px', color: '#888' }}>
                            <h3>No Options Data / Zero GEX</h3>
                            <p style={{ maxWidth: '400px', margin: '10px auto', lineHeight: '1.5' }}>
                                The GEX profile is empty. This usually happens when the data provider (Yahoo Finance)
                                returns <strong>0 Open Interest</strong> for the selected horizon.
                                <br /><br />
                                This can occur during pre-market hours (Monday morning) or data outages.
                                Try selecting a different ticker or checking back after market open.
                            </p>
                        </div>
                    ) : (
                        <div style={{ backgroundColor: '#0e1525', padding: '20px', borderRadius: '8px', border: '1px solid #203049', marginBottom: '20px' }}>
                            <GEXChart
                                data={chartData}
                                spotPrice={data.spot_price}
                                emRange={emRange}
                                title={chartTitle}
                                viewMode={viewMode}
                                yAxisRange={zoomRange}
                                height={800}
                                horizonLabel={horizon.charAt(0).toUpperCase()}
                            />
                        </div>
                    )}

                    {/* HEATMAP COMPONENT */}
                    <div style={{ marginBottom: '20px' }}>
                        <GexHeatmap ticker={ticker} />
                    </div>
                </div>
            )}

            {/* GEX WALLS SUMMARY TABLE (Moved to Bottom) */}
            {!loading && data && data.profile && (
                <div style={{ marginBottom: '20px', backgroundColor: '#0e1525', padding: '20px', borderRadius: '8px', border: '1px solid #203049' }}>
                    <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#d7e3f3', fontSize: '1.1rem' }}>Key Gamma Walls by Timeframe</h3>
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', color: '#d7e3f3', fontSize: '13px' }}>
                            <thead>
                                <tr style={{ borderBottom: '1px solid #203049' }}>
                                    <th style={{ padding: '10px', textAlign: 'left', color: '#9ec4ff' }}>Timeframe</th>
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
                                        { key: 'total', label: 'Total' },
                                        { key: 'eow', label: 'EOW' },
                                        { key: 'eom', label: 'EOM' },
                                        { key: 'eoq', label: 'EOQ' },
                                        { key: 'next5', label: '+5 Days' },
                                        { key: 'next30', label: '+30 Days' },
                                    ];

                                    return horizons.map(h => {
                                        // 1. Get Date Label
                                        let dateLabel = '';
                                        if (data.group_dates && data.group_dates[h.key]) {
                                            // Format YYYY-MM-DD to cleaner format if needed, or just use as is
                                            dateLabel = ` (${data.group_dates[h.key]})`;
                                        }

                                        // 2. Variable Keys
                                        // Column mapping based on horizon
                                        const callKey = h.key === 'next5' ? 'next5_call_gex' :
                                            h.key === 'next30' ? 'next30_call_gex' :
                                                `${h.key}_call_gex`;
                                        const putKey = h.key === 'next5' ? 'next5_put_gex' :
                                            h.key === 'next30' ? 'next30_put_gex' :
                                                `${h.key}_put_gex`;
                                        const netKey = h.key === 'next5' ? 'next5_net_gex' :
                                            h.key === 'next30' ? 'next30_net_gex' :
                                                `${h.key}_net_gex`;

                                        // Fallback keys for legacy data
                                        const callKeyLegacy = h.key === 'eow' ? 'weekly_call_gex' :
                                            h.key === 'eom' ? 'monthly_call_gex' :
                                                h.key === 'eoq' ? 'quarterly_call_gex' : callKey;
                                        const putKeyLegacy = h.key === 'eow' ? 'weekly_put_gex' :
                                            h.key === 'eom' ? 'monthly_put_gex' :
                                                h.key === 'eoq' ? 'quarterly_put_gex' : putKey;
                                        const netKeyLegacy = h.key === 'eow' ? 'weekly_net_gex' :
                                            h.key === 'eom' ? 'monthly_net_gex' :
                                                h.key === 'eoq' ? 'quarterly_net_gex' : netKey;


                                        // 3. Find Walls
                                        let maxCallGex = -1;
                                        let maxCallStrike = 0;
                                        let minPutGex = 1; // Put GEX is negative
                                        let minPutStrike = 0;

                                        // For Zero GEX Calculation
                                        let zeroGexLevel = null;
                                        let minFlipDist = Infinity;
                                        const spot = data.spot_price || 0;

                                        // Retrieve sorted profile for linear scan (Zero GEX)
                                        // Assuming data.profile is sorted by strike ascending (GEXEngine usually does this)
                                        const sortedProfile = [...data.profile].sort((a, b) => a.strike - b.strike);

                                        // Track previous net gex for sign flip check
                                        let prevNetGex = null;
                                        let prevStrike = null;

                                        sortedProfile.forEach(p => {
                                            const cVol = p[callKey] || p[callKeyLegacy] || 0;
                                            const pVol = p[putKey] || p[putKeyLegacy] || 0;
                                            const nVol = p[netKey] || p[netKeyLegacy] || (cVol + pVol);

                                            // Max Call
                                            if (cVol > maxCallGex) {
                                                maxCallGex = cVol;
                                                maxCallStrike = p.strike;
                                            }
                                            // Min Put (Max Magnitude Negative)
                                            if (pVol < minPutGex) {
                                                minPutGex = pVol;
                                                minPutStrike = p.strike;
                                            }

                                            // Zero GEX Check (Sign Flip)
                                            if (prevNetGex !== null) {
                                                if ((prevNetGex > 0 && nVol < 0) || (prevNetGex < 0 && nVol > 0)) {
                                                    // Flip detected between prevStrike and current p.strike
                                                    const flipStrike = (Math.abs(nVol) < Math.abs(prevNetGex)) ? p.strike : prevStrike;

                                                    // Distance to spot
                                                    const dist = Math.abs(flipStrike - spot);

                                                    // We prioritize the flip closest to SPOT Price as the "Active" zero gamma level
                                                    if (dist < minFlipDist) {
                                                        minFlipDist = dist;
                                                        zeroGexLevel = flipStrike;
                                                    }
                                                }
                                            }

                                            // Handle exact zero (rare)
                                            if (nVol === 0 && prevNetGex !== 0) {
                                                const dist = Math.abs(p.strike - spot);
                                                if (dist < minFlipDist) {
                                                    minFlipDist = dist;
                                                    zeroGexLevel = p.strike;
                                                }
                                            }

                                            prevNetGex = nVol;
                                            prevStrike = p.strike;
                                        });

                                        if (maxCallGex === -1 && minPutGex === 1) return null; // No data for this timeframe

                                        return (
                                            <tr key={h.key} style={{ borderBottom: '1px solid #203049' }}>
                                                <td style={{ padding: '10px', fontWeight: 'bold' }}>
                                                    {h.label}<span style={{ fontSize: '11px', color: '#666', fontWeight: 'normal' }}>{dateLabel}</span>
                                                </td>
                                                <td style={{ padding: '10px', textAlign: 'right', fontWeight: 'bold' }}>${maxCallStrike}</td>
                                                <td style={{ padding: '10px', textAlign: 'right', fontFamily: 'monospace' }}>${maxCallGex.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                                                <td style={{ padding: '10px', textAlign: 'right', fontWeight: 'bold' }}>${minPutStrike}</td>
                                                <td style={{ padding: '10px', textAlign: 'right', fontFamily: 'monospace' }}>${minPutGex.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                                                <td style={{ padding: '10px', textAlign: 'right', color: '#2196f3', fontWeight: 'bold' }}>
                                                    {zeroGexLevel ? `$${zeroGexLevel}` : '-'}
                                                </td>
                                            </tr>
                                        );
                                    });
                                })()}
                            </tbody>
                        </table>
                    </div>
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
                <div style={{ padding: '20px', color: '#f44336', backgroundColor: '#0b1220', minHeight: '100vh' }}>
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
