import React, { useState, useEffect } from 'react';
import GEXChart from '../components/GEXChart';

const GammaExposurePage = () => {
    const [ticker, setTicker] = useState('SPY');
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [emData, setEmData] = useState(null);
    const [viewMode, setViewMode] = useState('split');
    const [horizon, setHorizon] = useState('eow'); // 'eow', 'eom', 'eoq', 'next5', 'next30'
    const [availableTickers, setAvailableTickers] = useState([]); // Restore missing state
    const [refreshTrigger, setRefreshTrigger] = useState(0);      // Restore missing state

    const fetchGEX = async (force = false) => {
        setLoading(true);
        setError(null);
        try {
            // Fetch GEX
            const res = await fetch(`/api/v1/gex/latest/${ticker}${force ? '?force_refresh=true' : ''}`);
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to fetch GEX data');
            }
            const json = await res.json();
            setData(json);

            // Fetch Expected Moves for Ranges
            const resEM = await fetch('/api/v1/expected_moves/massive/latest');
            if (resEM.ok) {
                const jsonEM = await resEM.json();
                if (jsonEM.tickers && jsonEM.tickers[ticker]) {
                    setEmData(jsonEM.tickers[ticker]);
                } else {
                    setEmData(null);
                }
            }
        } catch (err) {
            console.error(err);
            setError(err.message);
            setData(null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        // Fetch allowed tickers
        const fetchTickers = async () => {
            try {
                const response = await fetch('/api/v1/tickers/Gamma_Exposure');
                const data = await response.json();
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

    useEffect(() => {
        // Fetch GEX data whenever ticker or horizon changes (or refresh trigger)
        fetchGEX();
    }, [ticker, horizon, refreshTrigger]); // We will trigger refresh when SELECT changes manually

    // Prepare Data based on Horizon
    const getChartData = () => {
        if (!data?.profile) return [];

        return data.profile.map(p => {
            let call = 0;
            let put = 0;

            if (horizon === 'eow') {
                call = p.eow_call_gex || 0;
                put = p.eow_put_gex || 0;
            } else if (horizon === 'eom') {
                call = p.eom_call_gex || 0;
                put = p.eom_put_gex || 0;
            } else if (horizon === 'eoq') {
                call = p.eoq_call_gex || 0;
                put = p.eoq_put_gex || 0;
            } else if (horizon === 'next5') {
                call = p.next5_call_gex || 0;
                put = p.next5_put_gex || 0;
            } else if (horizon === 'next30') {
                call = p.next30_call_gex || 0;
                put = p.next30_put_gex || 0;
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
        if (horizon === 'eow') return data.group_dates.eow;
        if (horizon === 'eom') return data.group_dates.eom;
        if (horizon === 'eoq') return data.group_dates.eoq;
        if (horizon === 'next5') return data.group_dates.next5;
        if (horizon === 'next30') return data.group_dates.next30;
        return null;
    };
    const validTill = getValidTill();

    // Helper for display name
    const horizonDisplay = {
        'eow': 'EOW', 'eom': 'EOM', 'eoq': 'EOQ', 'next5': '+5 Days', 'next30': '+30 Days'
    };
    const chartTitle = `${horizonDisplay[horizon]} GEX - ${ticker}${validTill ? ` (til ${validTill})` : ''} - ${viewMode === 'split' ? '(Split View)' : '(Net View)'}`;

    // Calculate Zoom Range (Monthly EM + 10%)
    const getZoomRange = () => {
        // Prefer Monthly EM for consistent scale, even if viewing Weekly
        if (!emData?.expirations?.MONTHLY) return null;
        const m = emData.expirations.MONTHLY;
        const width = m.upper_range - m.lower_range;
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
                                // Trigger refresh immediately on change
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
                {/* Existing Cards... */}
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

                {/* Max GEX Strike Card */}
                <div style={{ backgroundColor: '#1e1e1e', padding: '20px', borderRadius: '8px', border: '1px solid #333' }}>
                    <div style={{ color: '#888', fontSize: '14px', marginBottom: '5px' }}>Max GEX Strike</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#2196f3' }}>
                        ${maxGexStrike}
                    </div>
                </div>

                {/* Last Updated Card */}
                <div style={{ backgroundColor: '#1e1e1e', padding: '20px', borderRadius: '8px', border: '1px solid #333' }}>
                    <div style={{ color: '#888', fontSize: '14px', marginBottom: '5px' }}>Last Updated</div>
                    <div style={{ fontSize: '16px', fontWeight: 'bold', color: '#e0e0e0' }}>
                        {data && data.timestamp ? new Date(data.timestamp).toLocaleString() : '---'}
                    </div>
                </div>

                {/* View Mode Toggle Card */}
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

            {/* ERROR */}
            {
                error && (
                    <div style={{ backgroundColor: 'rgba(244, 67, 54, 0.1)', border: '1px solid #f44336', color: '#f44336', padding: '15px', borderRadius: '4px', marginBottom: '20px' }}>
                        {error}
                    </div>
                )
            }

            {/* CONTENT */}
            {
                data && (
                    <div>
                        {/* MAIN CHART */}
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
                    </div>
                )
            }
        </div >
    );
};

export default GammaExposurePage;
