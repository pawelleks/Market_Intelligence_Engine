import React from 'react';

// Define the available pre-computed windows, matching the project's strategy
// Added 15 and 20 years to the list
const PRECOMPUTED_WINDOWS = [1, 5, 10, 15, 20, 50, 'Max'];

const HMMChartSettings = ({ settings, onSettingsChange }) => {

    const handleChange = (name, value) => {
        // Only parse as float if it's NOT windowYears (which can be 'Max')
        const val = ['nStates', 'bullThreshold', 'bearThreshold'].includes(name) ? parseFloat(value) : value;

        // Ensure windowYears is always sent as a string (the API expects 5 or 'Max')
        if (name === 'windowYears') {
            onSettingsChange({ ...settings, windowYears: value });
        } else {
            onSettingsChange({ ...settings, [name]: val });
        }
    };

    // Helper for compact spacing
    const controlStyle = { marginBottom: '10px', padding: '5px 0' };
    const labelStyle = { display: 'block', fontSize: '13px', marginBottom: '3px', color: '#9e9e9e' };
    const inputStyle = { width: '100%', padding: '8px', backgroundColor: '#0b1220', color: '#d7e3f3', border: '1px solid #203049', borderRadius: '4px' };


    return (
        <div style={{ padding: '10px', backgroundColor: '#0e1525', borderRadius: '8px', marginBottom: '25px', border: '1px solid #203049', textAlign: 'left' }}>
            <h4 style={{ color: '#9ec4ff', marginTop: '0', fontSize: '1.0rem', marginBottom: '10px', borderBottom: '1px solid #203049', paddingBottom: '5px' }}>
                HMM Configuration Panel
            </h4>

            {/* Ticker Selector */}
            <div style={controlStyle}>
                <label style={labelStyle}>Ticker</label>
                <select
                    value={settings.ticker}
                    onChange={(e) => handleChange('ticker', e.target.value)}
                    style={inputStyle}
                >
                    <option value="SPY">SPY</option>
                    <option value="QQQ">QQQ</option>
                    <option value="IWM">IWM</option>
                    <option value="AAPL">AAPL</option>
                    <option value="MSFT">MSFT</option>
                    <option value="NVDA">NVDA</option>
                    <option value="AMD">AMD</option>
                    <option value="GOOGL">GOOGL</option>
                </select>
            </div>

            {/* Training Window Selector */}
            <div style={controlStyle}>
                <label style={labelStyle}>
                    Training Window
                </label>
                <select
                    value={settings.windowYears}
                    onChange={(e) => handleChange('windowYears', e.target.value)}
                    style={inputStyle}
                >
                    {PRECOMPUTED_WINDOWS.map(w => (
                        <option key={w} value={w}>{w} {w !== 'Max' ? 'Years' : 'Max History'}</option>
                    ))}
                </select>
            </div>

            {/* Hidden States Selector */}
            <div style={controlStyle}>
                <label style={labelStyle}>Hidden States</label>
                <select
                    value={settings.nStates}
                    onChange={(e) => handleChange('nStates', e.target.value)}
                    style={inputStyle}
                >
                    <option value={2}>2 States (Bull / Bear)</option>
                    <option value={3}>3 States (Bull / Neutral / Bear)</option>
                </select>
            </div>

            {/* Threshold 1: Bull Confidence - FIX Label */}
            <div style={{ ...controlStyle, paddingTop: '10px', borderTop: '1px solid #203049' }}>
                <label style={{ display: 'block', fontSize: '14px', marginBottom: '3px', fontWeight: 'bold' }}>
                    Bull Confidence Threshold ({settings.bullThreshold}%)
                </label>
                <input
                    type="range"
                    min="50"
                    max="99"
                    step="5"
                    value={settings.bullThreshold}
                    onChange={(e) => handleChange('bullThreshold', e.target.value)}
                    style={{ width: '95%', margin: '0 auto', display: 'block' }}
                />
            </div>

            {/* Threshold 2: Bear Confidence - FIX Label */}
            <div style={controlStyle}>
                <label style={{ display: 'block', fontSize: '14px', marginBottom: '3px', fontWeight: 'bold' }}>
                    Bear Confidence Threshold ({settings.bearThreshold}%)
                </label>
                <input
                    type="range"
                    min="50"
                    max="99"
                    step="5"
                    value={settings.bearThreshold}
                    onChange={(e) => handleChange('bearThreshold', e.target.value)}
                    style={{ width: '95%', margin: '0 auto', display: 'block' }}
                />
            </div>

            <p style={{ fontSize: '11px', color: '#6c757d', margin: '10px 0 0 0', borderTop: '1px solid #203049', paddingTop: '5px' }}>
                Note: 50% = Marginal preference; 99% = High Confidence signal.
            </p>
        </div>
    );
};

export default HMMChartSettings;
