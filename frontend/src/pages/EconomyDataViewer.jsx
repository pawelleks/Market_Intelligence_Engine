import React, { useState, useEffect } from 'react';
import TradingViewLineChart from '../components/TradingViewLineChart';
import { usePageTitle } from '../hooks/usePageTitle';
import { useAuth } from '../context/AuthContext';

const EconomyDataViewer = () => {
    usePageTitle('Economy Data Viewer');
    const { token } = useAuth();

    const [structure, setStructure] = useState([]);
    const [selectedSeries, setSelectedSeries] = useState(null); // { id, name }
    const [seriesData, setSeriesData] = useState([]);
    const [recessionData, setRecessionData] = useState([]);
    const [seriesMetadata, setSeriesMetadata] = useState(null); // { latest_observation, last_updated }
    const [releaseInfo, setReleaseInfo] = useState(null); // { next_release, frequency }
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Overlay state
    const [overlayType, setOverlayType] = useState('none'); // 'none', 'stock', 'fred'
    const [overlayStock, setOverlayStock] = useState(''); // SPY, DIA, etc.
    const [overlayFred, setOverlayFred] = useState(null); // { id, name }
    const [overlayData, setOverlayData] = useState([]);
    const [overlayLoading, setOverlayLoading] = useState(false);

    // 1. Fetch Structure on Mount
    useEffect(() => {
        if (!token) return;

        fetch('/api/v1/economy/macro/structure', {
            headers: { "Authorization": `Bearer ${token}` }
        })
            .then(res => res.json())
            .then(json => {
                if (json.status === 'ok') {
                    setStructure(json.data);
                    // Select first series by default if available
                    if (json.data.length > 0 && json.data[0].series.length > 0) {
                        setSelectedSeries(json.data[0].series[0]);
                    }
                } else {
                    setError(json.message || 'Failed to load structure');
                }
            })
            .catch(err => setError(err.message));
    }, [token]);

    // 2. Fetch Series Data when Selected Changes
    useEffect(() => {
        if (!selectedSeries || !token) return;

        setLoading(true);
        fetch(`/api/v1/economy/macro/series/${selectedSeries.id}`, {
            headers: { "Authorization": `Bearer ${token}` }
        })
            .then(res => {
                if (!res.ok) throw new Error("Series data missing or API error");
                return res.json();
            })
            .then(json => {
                if (json.status === 'ok') {
                    setSeriesData(json.data.series);
                    setRecessionData(json.data.recessions);
                    setSeriesMetadata(json.data.meta || null); // Store metadata
                } else {
                    console.error(json);
                }
            })
            .catch(err => console.error(err))
            .finally(() => setLoading(false));
    }, [selectedSeries, token]); // Added token dependency to fix update bug

    // 2.5. Fetch Release Info when Series Changes
    useEffect(() => {
        if (!selectedSeries || !token) {
            setReleaseInfo(null);
            return;
        }

        fetch(`/api/v1/economy/macro/series/${selectedSeries.id}/release`, {
            headers: { "Authorization": `Bearer ${token}` }
        })
            .then(res => res.json())
            .then(json => {
                if (json.status === 'ok') {
                    setReleaseInfo(json.data);
                } else {
                    setReleaseInfo(null);
                }
            })
            .catch(err => {
                console.error("Release info fetch error:", err);
                setReleaseInfo(null);
            });
    }, [selectedSeries, token]);

    // 3. Fetch Overlay Data when Selection Changes
    useEffect(() => {
        if (!token || overlayType === 'none') {
            setOverlayData([]);
            return;
        }

        setOverlayLoading(true);

        if (overlayType === 'stock' && overlayStock) {
            // Fetch stock overlay data
            fetch(`/api/v1/economy/macro/overlay/stock/${overlayStock}`, {
                headers: { "Authorization": `Bearer ${token}` }
            })
                .then(res => {
                    if (!res.ok) throw new Error("Stock overlay data error");
                    return res.json();
                })
                .then(json => {
                    if (json.status === 'ok') {
                        setOverlayData(json.data.series);
                    } else {
                        console.error(json);
                        setOverlayData([]);
                    }
                })
                .catch(err => {
                    console.error(err);
                    setOverlayData([]);
                })
                .finally(() => setOverlayLoading(false));

        } else if (overlayType === 'fred' && overlayFred) {
            // Fetch FRED overlay data (same as main series endpoint)
            fetch(`/api/v1/economy/macro/series/${overlayFred.id}`, {
                headers: { "Authorization": `Bearer ${token}` }
            })
                .then(res => {
                    if (!res.ok) throw new Error("FRED overlay data error");
                    return res.json();
                })
                .then(json => {
                    if (json.status === 'ok') {
                        setOverlayData(json.data.series);
                    } else {
                        console.error(json);
                        setOverlayData([]);
                    }
                })
                .catch(err => {
                    console.error(err);
                    setOverlayData([]);
                })
                .finally(() => setOverlayLoading(false));
        } else {
            setOverlayLoading(false);
            setOverlayData([]);
        }
    }, [overlayType, overlayStock, overlayFred, token]);

    return (
        <div style={{ display: 'flex', gap: '20px', padding: '20px', minHeight: '100vh', width: '100%', color: '#d7e3f3' }}>

            {/* Left Panel: Selector */}
            <div style={{ width: '270px', flexShrink: 0 }}>
                <div style={{ padding: '20px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049' }}>
                    <h3 style={{ marginTop: 0, color: '#4caf50' }}>Select Series</h3>

                    {/* Single Grouped Dropdown */}
                    <select
                        style={{
                            width: '100%',
                            padding: '10px',
                            backgroundColor: '#0b1220',
                            color: '#d7e3f3',
                            border: '1px solid #203049',
                            borderRadius: '4px',
                            outline: 'none',
                            fontSize: '13px'
                        }}
                        onChange={(e) => {
                            // Find series across all categories
                            for (const cat of structure) {
                                const s = cat.series.find(x => x.id === e.target.value);
                                if (s) {
                                    setSelectedSeries(s);
                                    break;
                                }
                            }
                        }}
                        value={selectedSeries?.id || ''}
                    >
                        <option value="" disabled>Select a data series...</option>
                        {structure.map(cat => (
                            <optgroup key={cat.category} label={cat.category}>
                                {cat.series.map(s => (
                                    <option key={s.id} value={s.id}>{s.name}</option>
                                ))}
                            </optgroup>
                        ))}
                    </select>
                </div>

                {/* Overlay Controls */}
                <div style={{ padding: '20px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049', marginTop: '15px' }}>
                    <h3 style={{ marginTop: 0, color: '#ffeb3b', fontSize: '0.95rem' }}>Overlay Series</h3>

                    {/* Overlay Type Selection */}
                    <div style={{ marginBottom: '15px' }}>
                        <div style={{ fontSize: '11px', color: '#9e9e9e', marginBottom: '5px' }}>TYPE</div>
                        <select
                            style={{
                                width: '100%',
                                padding: '8px',
                                backgroundColor: '#0b1220',
                                color: '#d7e3f3',
                                border: '1px solid #203049',
                                borderRadius: '4px',
                                outline: 'none',
                                fontSize: '12px'
                            }}
                            value={overlayType}
                            onChange={(e) => {
                                setOverlayType(e.target.value);
                                if (e.target.value === 'none') {
                                    setOverlayStock('');
                                    setOverlayFred(null);
                                }
                            }}
                        >
                            <option value="none">None</option>
                            <option value="stock">Market Index</option>
                            <option value="fred">FRED Series</option>
                        </select>
                    </div>

                    {/* Conditional: Stock Ticker Selection */}
                    {overlayType === 'stock' && (
                        <div style={{ marginBottom: '10px' }}>
                            <div style={{ fontSize: '11px', color: '#9e9e9e', marginBottom: '5px' }}>TICKER</div>
                            <select
                                style={{
                                    width: '100%',
                                    padding: '8px',
                                    backgroundColor: '#0b1220',
                                    color: '#d7e3f3',
                                    border: '1px solid #203049',
                                    borderRadius: '4px',
                                    outline: 'none',
                                    fontSize: '12px'
                                }}
                                value={overlayStock}
                                onChange={(e) => setOverlayStock(e.target.value)}
                            >
                                <option value="">Select...</option>
                                <option value="SPY">SPY (S&P 500)</option>
                                <option value="DIA">DIA (Dow Jones)</option>
                                <option value="IWM">IWM (Russell 2000)</option>
                                <option value="QQQ">QQQ (Nasdaq 100)</option>
                            </select>
                        </div>
                    )}

                    {/* Conditional: FRED Series Selection */}
                    {overlayType === 'fred' && (
                        <div>
                            <div style={{ fontSize: '11px', color: '#9e9e9e', marginBottom: '5px' }}>SERIES</div>
                            <select
                                style={{
                                    width: '100%',
                                    padding: '8px',
                                    backgroundColor: '#0b1220',
                                    color: '#d7e3f3',
                                    border: '1px solid #203049',
                                    borderRadius: '4px',
                                    outline: 'none',
                                    fontSize: '12px'
                                }}
                                onChange={(e) => {
                                    // Find series across all categories
                                    for (const cat of structure) {
                                        const s = cat.series.find(x => x.id === e.target.value);
                                        if (s) {
                                            setOverlayFred(s);
                                            break;
                                        }
                                    }
                                }}
                                value={overlayFred?.id || ''}
                            >
                                <option value="" disabled>Select FRED series...</option>
                                {structure.map(cat => (
                                    <optgroup key={cat.category} label={cat.category}>
                                        {cat.series.map(s => (
                                            <option key={s.id} value={s.id}>{s.name}</option>
                                        ))}
                                    </optgroup>
                                ))}
                            </select>
                        </div>
                    )}
                </div>
            </div>

            {/* Right Panel: Chart */}
            <div style={{ flexGrow: 1, minWidth: 0 }}>
                <div style={{ marginBottom: '20px', borderBottom: '1px solid #203049', paddingBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                    <div>
                        <h2 style={{ margin: 0, fontSize: '24px' }}>
                            {selectedSeries ? selectedSeries.name : 'Select a Series'}
                        </h2>
                        <div style={{ color: '#9e9e9e', fontSize: '14px', marginTop: '5px' }}>
                            FRED ID: <span style={{ fontFamily: 'monospace', color: '#fff' }}>{selectedSeries?.id}</span>
                            {overlayType !== 'none' && overlayData.length > 0 && (
                                <span style={{ marginLeft: '20px', color: '#ffeb3b' }}>
                                    Overlay: {overlayType === 'stock' ? overlayStock : overlayFred?.name}
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                <div style={{ height: '600px', border: '1px solid #203049', borderRadius: '8px', overflow: 'hidden', position: 'relative' }}>
                    {(loading || overlayLoading) && (
                        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', backgroundColor: 'rgba(14, 21, 37, 0.8)', zIndex: 10 }}>
                            {loading ? 'Loading main series...' : 'Loading overlay...'}
                        </div>
                    )}
                    <TradingViewLineChart
                        data={seriesData}
                        recessions={recessionData}
                        overlayData={overlayData}
                        overlayLabel={overlayType === 'stock' ? overlayStock : overlayFred?.name}
                        height={600}
                    />
                </div>

                {/* Observations & Metadata Panel */}
                <div style={{ marginTop: '15px', padding: '15px', backgroundColor: '#0e1525', border: '1px solid #203049', borderRadius: '8px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '20px' }}>
                        {/* Latest Observation */}
                        {seriesMetadata?.latest_observation && (
                            <div>
                                <div style={{ fontSize: '11px', color: '#9e9e9e', marginBottom: '5px', textTransform: 'uppercase' }}>Latest Observation</div>
                                <div style={{ fontSize: '16px', color: '#fff', fontFamily: 'monospace' }}>
                                    {new Date(seriesMetadata.latest_observation.date).toLocaleDateString('en-US', { year: 'numeric', month: 'short' })}: {' '}
                                    <span style={{ fontWeight: 'bold', color: '#4caf50' }}>
                                        {typeof seriesMetadata.latest_observation.value === 'number'
                                            ? seriesMetadata.latest_observation.value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 3 })
                                            : seriesMetadata.latest_observation.value}
                                    </span>
                                </div>
                                {seriesMetadata.last_updated && (
                                    <div style={{ fontSize: '11px', color: '#666', marginTop: '3px' }}>
                                        Data as of: {seriesMetadata.last_updated}
                                    </div>
                                )}
                                {releaseInfo?.next_release && (
                                    <div style={{ fontSize: '11px', color: '#ffeb3b', marginTop: '5px', fontWeight: 'bold' }}>
                                        Next Release: {new Date(releaseInfo.next_release).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
                                    </div>
                                )}
                                {releaseInfo?.frequency && !releaseInfo?.next_release && (
                                    <div style={{ fontSize: '11px', color: '#666', marginTop: '5px' }}>
                                        Frequency: {releaseInfo.frequency}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Chart Legend */}
                        <div style={{ flex: 1 }}>
                            <div style={{ fontSize: '11px', color: '#9e9e9e', marginBottom: '5px', textTransform: 'uppercase' }}>Legend</div>
                            <div style={{ fontSize: '13px', lineHeight: '1.8' }}>
                                <div>
                                    <span style={{ display: 'inline-block', width: '20px', height: '3px', backgroundColor: '#ffffff', marginRight: '8px', verticalAlign: 'middle' }}></span>
                                    <span style={{ color: '#d7e3f3' }}>{selectedSeries?.name || 'Main Series'}</span>
                                </div>
                                {overlayType !== 'none' && overlayData.length > 0 && (
                                    <div>
                                        <span style={{ display: 'inline-block', width: '20px', height: '3px', backgroundColor: '#ffeb3b', marginRight: '8px', verticalAlign: 'middle' }}></span>
                                        <span style={{ color: '#ffeb3b' }}>{overlayType === 'stock' ? overlayStock : overlayFred?.name}</span>
                                    </div>
                                )}
                                <div>
                                    <span style={{ display: 'inline-block', width: '20px', height: '12px', backgroundColor: 'rgba(128, 128, 128, 0.3)', marginRight: '8px', verticalAlign: 'middle' }}></span>
                                    <span style={{ color: '#9e9e9e', fontStyle: 'italic' }}>U.S. Recessions (USREC)</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default EconomyDataViewer;
