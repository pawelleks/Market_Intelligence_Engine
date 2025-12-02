import React, { useState, useEffect } from 'react';

const API_BASE = "/api/v1";
const ANALYSIS_KEY = "Minervini_Template"; // Use the specific Minervini scope

const MinerviniPage = ({ settings, onSettingsChange, priceData, loading, error }) => {
    // Note: Trend Template calculation requires full historical price data

    const [availableTickers, setAvailableTickers] = useState([]);
    const [loadingTickers, setLoadingTickers] = useState(true);

    // Fetch the list of available tickers on mount
    useEffect(() => {
        async function fetchTickers() {
            setLoadingTickers(true);
            try {
                const response = await fetch(`${API_BASE}/tickers/${ANALYSIS_KEY}`);
                const json = await response.json();
                if (response.ok) {
                    setAvailableTickers(json.tickers);
                    // Automatically set the first ticker as the default if none is selected
                    if (!settings.ticker || !json.tickers.includes(settings.ticker)) {
                        onSettingsChange({ ...settings, ticker: json.tickers[0] || 'SPY' });
                    }
                }
            } catch (error) {
                console.error("Failed to fetch available tickers:", error);
                setAvailableTickers(['SPY', 'QQQ']); // Fallback list
            } finally {
                setLoadingTickers(false);
            }
        }
        fetchTickers();
    }, []); // Depend only on mount
    return (
        <div style={{ display: 'flex', gap: '20px', padding: '20px', width: '100%' }}>

            {/* Left Panel: Configuration (Reusing price viewer settings template) */}
            <div style={{ width: '300px', flexShrink: 0, textAlign: 'left', position: 'sticky', top: '20px', maxHeight: 'calc(100vh - 40px)', overflowY: 'auto' }}>
                {/* Reusing Price Viewer settings structure for Ticker/Window */}
                <div style={{ padding: '10px', backgroundColor: '#0e1525', borderRadius: '8px', marginBottom: '25px', border: '1px solid #203049', textAlign: 'left' }}>
                    <h4 style={{ color: '#9ec4ff', marginTop: '0', fontSize: '1.0rem', marginBottom: '10px', borderBottom: '1px solid #203049', paddingBottom: '5px' }}>
                        Trend Template Filters
                    </h4>
                    <p style={{ fontSize: '13px', color: '#9e9e9e', paddingBottom: '10px' }}>
                        Note: This analysis requires fetching the full available price history.
                    </p>

                    <div style={{ marginBottom: '15px' }}>
                        <label style={{ display: 'block', fontSize: '13px', marginBottom: '5px', color: '#9e9e9e' }}>Ticker Symbol</label>
                        {loadingTickers ?
                            <p style={{ fontSize: '14px' }}>Loading list...</p> :
                            <select
                                value={settings.ticker}
                                onChange={(e) => onSettingsChange({ ...settings, ticker: e.target.value })}
                                style={{ width: '100%', padding: '8px', backgroundColor: '#0b1220', color: '#d7e3f3', border: '1px solid #203049', borderRadius: '4px' }}
                            >
                                {availableTickers.map(ticker => (
                                    <option key={ticker} value={ticker}>{ticker}</option>
                                ))}
                            </select>
                        }
                    </div>
                    <button onClick={() => alert('Future: Fetch full history here')}
                        style={{ padding: '10px', backgroundColor: '#4caf50', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                        Run Template Check
                    </button>
                </div>
            </div>

            {/* Right Panel: Template Checklist and Price Chart */}
            <div style={{ flexGrow: 1, padding: '0 10px', textAlign: 'left' }}>
                <h2 style={{ fontSize: '1.5rem', marginBottom: '0' }}>Minervini Trend Template</h2>
                <p style={{ color: '#9e9e9e', fontSize: '0.85rem', borderBottom: '1px solid #203049', paddingBottom: '10px', marginBottom: '20px' }}>
                    Checklist based on 150-day, 200-day, and 50-day moving averages.
                </p>

                {loading ? <p>Loading price data...</p> :
                    <div style={{ padding: '20px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049' }}>
                        <h3>10-Point Checklist Status (Check Date: N/A)</h3>
                        <p>Template logic will be implemented here.</p>
                    </div>
                }
            </div>
        </div>
    );
};

export default MinerviniPage;
