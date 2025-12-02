import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';

// Utility to map state codes to user-friendly names (Green/Red)
const STATE_NAME_MAP = {
    'up': 'Green',
    'neutral': 'Neutral',
    'down': 'Red'
};

const MarkovMultiStepForecast = ({ settings }) => {
    const [forecastData, setForecastData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Construct API URL dynamically from settings
    const API_BASE = "/api/v1";
    // NOTE: Order 1 is assumed for Multi-Step Forecasts (1st-Order Approximation)
    const mode = settings.nStates === 2 ? 'binary' : 'tri';
    const MULTISTEP_URL = `${API_BASE}/markov/multistep/${settings.ticker}/${mode}`;

    useEffect(() => {
        async function fetchData() {
            setLoading(true);
            setError(null);
            try {
                const response = await fetch(MULTISTEP_URL);
                const json = await response.json();

                if (!response.ok) {
                    throw new Error(`Forecast API Error: ${json.detail}`);
                }
                setForecastData(json.data);
            } catch (err) {
                console.error("Multi-Step Fetch Error:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        }
        // Only fetch when ticker or state mode (which defines the forecast file) changes
        fetchData();
    }, [settings.ticker, settings.nStates]);

    if (loading) {
        return <p style={{ color: '#9e9e9e', padding: '20px' }}>Calculating forecasts...</p>;
    }
    if (error) {
        return <p style={{ color: '#f44336', padding: '20px' }}>Error loading forecasts: {error}</p>;
    }
    if (!forecastData || forecastData.length === 0) {
        return <p style={{ color: '#9e9e9e', padding: '20px' }}>No multi-step forecast data available for this configuration.</p>;
    }

    // Filter data based on user-selected horizons (settings.forecastHorizons)
    // NOTE: Multi-select output is an array of strings/numbers; ensure consistency
    const horizons = settings.forecastHorizons || [1, 2, 3, 4]; // Default to 1-4 if none selected
    const filteredData = forecastData.filter(d => horizons.includes(d.horizon));

    if (filteredData.length === 0) {
        return <p style={{ color: '#9e9e9e', padding: '20px' }}>Select forecast horizons (1, 2, 3, 4 days, etc.) in the config panel.</p>;
    }

    // --- Prepare Plotly Chart Data ---
    const probKeys = Object.keys(filteredData[0]).filter(key => key.startsWith('mc_prob_'));
    const stateTraces = probKeys.map(key => {
        const stateCode = key.split('_').pop();
        const stateName = STATE_NAME_MAP[stateCode] || stateCode;

        return {
            x: filteredData.map(d => d.horizon),
            y: filteredData.map(d => d[key] * 100),
            name: stateName,
            type: 'bar',
            marker: {
                color: stateName === 'Green' ? '#4caf50' : stateName === 'Red' ? '#f44336' : '#9e9e9e'
            }
        };
    });

    // --- Plotly Layout ---
    const layout = {
        title: { text: 'Next-Day State Probability by Horizon', font: { size: 14, color: '#d7e3f3' } },
        barmode: 'group', // Display bars side-by-side
        height: 350,
        margin: { t: 40, b: 50, l: 40, r: 20 },
        plot_bgcolor: '#0e1525',
        paper_bgcolor: '#0b1220',
        font: { color: '#d7e3f3' },
        xaxis: { title: 'Horizon (days)', tickmode: 'linear', dtick: 1, gridcolor: '#203049' },
        yaxis: { title: 'Probability (%)', range: [0, 100], gridcolor: '#203049' },
        legend: { orientation: 'h', y: 1.1, x: 0.1, bgcolor: 'rgba(0,0,0,0)' }
    };

    // --- Prepare Table Data ---
    const tableHeaders = ['Horizon (Days)', ...probKeys.map(key => STATE_NAME_MAP[key.split('_').pop()] + ' (%)')];
    const tableRows = filteredData.map(d => {
        const row = { 'Horizon (Days)': d.horizon };
        probKeys.forEach(key => {
            const header = STATE_NAME_MAP[key.split('_').pop()] + ' (%)';
            row[header] = (d[key] * 100).toFixed(2) + '%';
        });
        return row;
    });

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', width: '100%' }}>

            {/* Chart Visualization */}
            <div style={{ border: '1px solid #203049', borderRadius: '8px', overflow: 'hidden' }}>
                <Plot data={stateTraces} layout={layout} config={{ responsive: true, displayModeBar: false }} style={{ width: '100%', height: '100%' }} />
            </div>

            {/* Matrix Table */}
            <div style={{ border: '1px solid #203049', borderRadius: '8px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                <h4 style={{ margin: '10px', color: '#9ec4ff' }}>Multi-Step Probabilities Table</h4>
                <div style={{ overflowY: 'auto', flexGrow: 1, padding: '0 10px 10px 10px' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                        <thead>
                            <tr>
                                {tableHeaders.map(header => (
                                    <th key={header} style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #203049', color: '#9ec4ff', backgroundColor: '#151d30' }}>{header}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {tableRows.map((row, i) => (
                                <tr key={i}>
                                    {tableHeaders.map(header => (
                                        <td key={header} style={{ padding: '8px', borderBottom: '1px solid #203049', color: '#d7e3f3' }}>
                                            {row[header]}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default MarkovMultiStepForecast;
