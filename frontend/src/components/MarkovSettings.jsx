import React from 'react';

const MarkovSettings = ({ settings, onSettingsChange }) => {
    const handleChange = (e) => {
        const { name, value } = e.target;
        onSettingsChange(prev => ({
            ...prev,
            [name]: name === 'ticker' ? value.toUpperCase() : Number(value)
        }));
    };

    return (
        <div style={{ padding: '20px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049', marginBottom: '20px', color: '#d7e3f3' }}>
            <h3 style={{ marginTop: 0, color: '#9ec4ff', borderBottom: '1px solid #203049', paddingBottom: '10px' }}>
                Markov Configuration
            </h3>

            <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.9rem', color: '#9ec4ff' }}>Ticker Symbol</label>
                <input
                    type="text"
                    name="ticker"
                    value={settings.ticker}
                    onChange={handleChange}
                    style={{ width: '100%', padding: '8px', backgroundColor: '#1c2635', border: '1px solid #203049', borderRadius: '4px', color: '#fff' }}
                />
            </div>

            <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.9rem', color: '#9ec4ff' }}>State Mode</label>
                <select
                    name="nStates"
                    value={settings.nStates}
                    onChange={handleChange}
                    style={{ width: '100%', padding: '8px', backgroundColor: '#1c2635', border: '1px solid #203049', borderRadius: '4px', color: '#fff' }}
                >
                    <option value={2}>Binary (Bull/Bear)</option>
                    <option value={3}>Ternary (Bull/Neutral/Bear)</option>
                </select>
            </div>

            <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.9rem', color: '#9ec4ff' }}>Lookback Window (Years)</label>
                <select
                    name="windowYears"
                    value={settings.windowYears}
                    onChange={handleChange}
                    style={{ width: '100%', padding: '8px', backgroundColor: '#1c2635', border: '1px solid #203049', borderRadius: '4px', color: '#fff' }}
                >
                    <option value={1}>1 Year</option>
                    <option value={2}>2 Years</option>
                    <option value={5}>5 Years</option>
                    <option value={10}>10 Years</option>
                    <option value={20}>20 Years</option>
                    <option value="Max">Max History</option>
                </select>
            </div>

            <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.9rem', color: '#9ec4ff' }}>
                    Return Threshold (BPS): {settings.thresholdBPS} BPS
                </label>
                <input
                    type="range"
                    name="thresholdBPS"
                    min="0"
                    max="50"
                    step="5"
                    value={settings.thresholdBPS}
                    onChange={handleChange}
                    style={{ width: '100%', margin: '0 auto', display: 'block', cursor: 'pointer' }}
                />
                <p style={{ fontSize: '11px', color: '#6c757d', margin: '3px 0 0 0', textAlign: 'center' }}>
                    ({(settings.thresholdBPS / 100).toFixed(2)}%) daily change
                </p>
            </div>

            <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px', fontSize: '0.9rem', color: '#9ec4ff' }}>Markov Order</label>
                <select
                    name="markovOrder"
                    value={settings.markovOrder}
                    onChange={handleChange}
                    style={{ width: '100%', padding: '8px', backgroundColor: '#1c2635', border: '1px solid #203049', borderRadius: '4px', color: '#fff' }}
                >
                    <option value={1}>Order 1 (Memoryless)</option>
                    <option value={2}>Order 2</option>
                    <option value={3}>Order 3</option>
                    <option value={4}>Order 4</option>
                </select>
            </div>
        </div>
    );
};

export default MarkovSettings;
