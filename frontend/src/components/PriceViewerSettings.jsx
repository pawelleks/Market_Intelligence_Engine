import React, { useState, useEffect } from 'react';

// Define API URL and ANALYSIS KEY
const API_BASE = "/api/v1";
const ANALYSIS_KEY = "Market_Analysis"; // Using general market analysis scope

const ROWS_OPTIONS = [50, 100, 200];
const THRESHOLD_BPS_OPTIONS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50];


const PriceViewerSettings = ({ settings, onSettingsChange }) => {

    const [availableTickers, setAvailableTickers] = useState([]);
    const [loadingTickers, setLoadingTickers] = useState(true);

    // Fetch the list of available tickers when the component mounts
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
    }, []);

    const handleChange = (name, value) => {
        const val = ['rows', 'thresholdBPS'].includes(name) ? parseInt(value) : value;
        onSettingsChange({ ...settings, [name]: val });
    };

    const inputStyle = {
        width: '100%',
        padding: '8px',
        backgroundColor: '#0b1220',
        color: '#d7e3f3',
        border: '1px solid #203049',
        borderRadius: '4px',
        // Apply styling to the dropdown arrow for better contrast (often platform-specific)
        appearance: 'none',
        backgroundImage: "url(\"data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22white%22%3E%3Cpath%20d%3D%22M7%2010l5%205%205-5z%22%2F%3E%3C%2Fsvg%3E\")",
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right 8px top 50%',
        backgroundSize: '12px',
    };
    const labelStyle = { display: 'block', fontSize: '13px', marginBottom: '3px', color: '#9e9e9e' };
    const controlStyle = { marginBottom: '15px', padding: '5px 0', textAlign: 'left' };

    if (loadingTickers) {
        return <p style={{ color: '#9e9e9e', padding: '10px' }}>Loading Ticker List...</p>;
    }

    return (
        <div style={{ padding: '10px', backgroundColor: '#0e1525', borderRadius: '8px', marginBottom: '25px', border: '1px solid #203049', textAlign: 'left' }}>
            <h4 style={{ color: '#9ec4ff', marginTop: '0', fontSize: '1.0rem', marginBottom: '10px', borderBottom: '1px solid #203049', paddingBottom: '5px' }}>
                Viewer Configuration
            </h4>

            {/* Ticker Selector */}
            <div style={controlStyle}>
                <label style={labelStyle}>Ticker Symbol</label>
                <select value={settings.ticker} onChange={(e) => handleChange('ticker', e.target.value)} style={inputStyle}>
                    {availableTickers.map(ticker => (
                        <option key={ticker} value={ticker}>{ticker}</option>
                    ))}
                </select>
            </div>

            {/* Rows to Display */}
            <div style={controlStyle}>
                <label style={labelStyle}>Rows to Display</label>
                <select value={settings.rows} onChange={(e) => handleChange('rows', e.target.value)} style={inputStyle}>
                    {ROWS_OPTIONS.map(r => (
                        <option key={r} value={r}>{r} Rows</option>
                    ))}
                </select>
            </div>

            {/* State Mode Selector */}
            <div style={controlStyle}>
                <label style={labelStyle}>State Classification Mode</label>
                <select value={settings.stateMode} onChange={(e) => handleChange('stateMode', e.target.value)} style={inputStyle}>
                    <option value="tri">Ternary (Green/Neutral/Red)</option>
                    <option value="binary">Binary (Green/Red)</option>
                </select>
            </div>

            {/* Threshold (BPS) */}
            <div style={controlStyle}>
                <label style={labelStyle}>Return Threshold (BPS): {settings.thresholdBPS} BPS</label>
                <input
                    type="range"
                    min="0"
                    max="50"
                    step="5"
                    value={settings.thresholdBPS}
                    onChange={(e) => handleChange('thresholdBPS', e.target.value)}
                    style={{ width: '95%', margin: '0 auto', display: 'block' }}
                />
                <p style={{ fontSize: '11px', color: '#6c757d', margin: '3px 0 0 0', textAlign: 'center' }}>
                    ({(settings.thresholdBPS / 100).toFixed(2)}%) daily change
                </p>
            </div>
        </div>
    );
};

export default PriceViewerSettings;
