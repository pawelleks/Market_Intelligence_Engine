import React from 'react';

const ROWS_OPTIONS = [50, 100, 200];
const THRESHOLD_BPS_OPTIONS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50];


const PriceViewerSettings = ({ settings, onSettingsChange }) => {

    const handleChange = (name, value) => {
        const val = ['rows', 'thresholdBPS'].includes(name) ? parseInt(value) : value;
        onSettingsChange({ ...settings, [name]: val });
    };

    const inputStyle = { width: '100%', padding: '8px', backgroundColor: '#0b1220', color: '#d7e3f3', border: '1px solid #203049', borderRadius: '4px' };
    const labelStyle = { display: 'block', fontSize: '13px', marginBottom: '3px', color: '#9e9e9e' };
    const controlStyle = { marginBottom: '15px', padding: '5px 0', textAlign: 'left' };

    return (
        <div style={{ padding: '10px', backgroundColor: '#0e1525', borderRadius: '8px', marginBottom: '25px', border: '1px solid #203049', textAlign: 'left' }}>
            <h4 style={{ color: '#9ec4ff', marginTop: '0', fontSize: '1.0rem', marginBottom: '10px', borderBottom: '1px solid #203049', paddingBottom: '5px' }}>
                Viewer Configuration
            </h4>

            {/* Ticker Selector */}
            <div style={controlStyle}>
                <label style={labelStyle}>Ticker Symbol</label>
                <select value={settings.ticker} onChange={(e) => handleChange('ticker', e.target.value)} style={inputStyle}>
                    <option value="SPY">SPY</option>
                    <option value="QQQ">QQQ</option>
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
