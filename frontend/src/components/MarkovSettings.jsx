import React, { useState, useEffect } from 'react';

const PRECOMPUTED_WINDOWS = [5, 10, 15, 20, 50, 'Max'];
const THRESHOLD_BPS_OPTIONS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50];
const MARKOV_ORDERS = [1, 2, 3, 4];
const FORECAST_HORIZONS = [1, 2, 3, 4, 5, 10, 20];

// The analysis key for this page (Matches the key in config/analysis_scope.yml)
const ANALYSIS_KEY = "Market_Analysis";
const API_BASE = "/api/v1";


const MarkovSettings = ({ settings, onSettingsChange }) => {
    // New state to hold the dynamically fetched list of available tickers
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
        const val = ['thresholdBPS', 'markovOrder'].includes(name) ? parseInt(value) : value;
        onSettingsChange({ ...settings, [name]: val });
    };

    const handleHorizonChange = (event) => {
        // Generate array from 1 to selected value (inclusive)
        // e.g. if 3 is selected, produce [1, 2, 3]
        const maxDay = parseInt(event.target.value);
        const horizons = Array.from({ length: maxDay }, (_, i) => i + 1);
        onSettingsChange({ ...settings, forecastHorizons: horizons });
    };

    const inputStyle = { width: '100%', padding: '8px', backgroundColor: '#0b1220', color: '#d7e3f3', border: '1px solid #203049', borderRadius: '4px' };
    const labelStyle = { display: 'block', fontSize: '13px', marginBottom: '3px', color: '#9e9e9e' };
    const controlStyle = { marginBottom: '15px', padding: '5px 0', textAlign: 'left' };

    if (loadingTickers) {
        return <p style={{ color: '#9e9e9e', padding: '10px' }}>Loading Ticker List...</p>;
    }

    return (
        <div style={{ padding: '10px', backgroundColor: '#0e1525', borderRadius: '8px', marginBottom: '25px', border: '1px solid #203049', textAlign: 'left' }}>
            <h4 style={{ color: '#9ec4ff', marginTop: '0', fontSize: '1.0rem', marginBottom: '10px', borderBottom: '1px solid #203049', paddingBottom: '5px' }}>
                Markov Configuration
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

            {/* History Window Selector (a) */}
            <div style={controlStyle}>
                <label style={labelStyle}>Lookback Window (Years)</label>
                <select value={settings.windowYears} onChange={(e) => handleChange('windowYears', e.target.value)} style={inputStyle}>
                    {PRECOMPUTED_WINDOWS.map(w => (
                        <option key={w} value={w}>{w} {w !== 'Max' ? 'Years' : 'Max History'}</option>
                    ))}
                </select>
            </div>

            {/* State Mode Selector (b) - Uses the same nStates prop for consistency */}
            <div style={controlStyle}>
                <label style={labelStyle}>State Mode</label>
                <select value={settings.nStates} onChange={(e) => handleChange('nStates', e.target.value)} style={inputStyle}>
                    <option value={2}>Binary (Bull/Bear)</option>
                    <option value={3}>Ternary (Bull/Neutral/Bear)</option>
                </select>
            </div>

            {/* Return Threshold (c) */}
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

            {/* Markov Order (d) */}
            <div style={controlStyle}>
                <label style={labelStyle}>Markov Order</label>
                <select value={settings.markovOrder} onChange={(e) => handleChange('markovOrder', e.target.value)} style={inputStyle}>
                    {MARKOV_ORDERS.map(order => (
                        <option key={order} value={order}>Order {order}</option>
                    ))}
                </select>
            </div>

            {/* Forecast Horizon (e) */}
            <div style={controlStyle}>
                <label style={labelStyle}>Forecast Horizon (Up to)</label>
                <select
                    value={settings.forecastHorizons[settings.forecastHorizons.length - 1]}
                    onChange={handleHorizonChange}
                    style={inputStyle}
                >
                    {[1, 2, 3, 4, 5].map(day => (
                        <option key={day} value={day}>+{day} Day{day > 1 ? 's' : ''}</option>
                    ))}
                </select>
            </div>

            <p style={{ fontSize: '11px', color: '#6c757d', margin: '10px 0 0 0', borderTop: '1px solid #203049', paddingTop: '5px' }}>
                Note: Check CLI documentation for necessary pre-computation jobs.
            </p>
        </div>
    );
};

export default MarkovSettings;
