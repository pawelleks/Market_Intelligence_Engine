import React from 'react';
import Plot from 'react-plotly.js';

const STATE_INFO_MAP = {
    'U': { name: 'Green', color: '#4caf50' },
    'N': { name: 'Neutral', color: '#9e9e9e' },
    'D': { name: 'Red', color: '#f44336' },
    'Up': { name: 'Green', color: '#4caf50' },
    'Neutral': { name: 'Neutral', color: '#9e9e9e' },
    'Down': { name: 'Red', color: '#f44336' },
};



// Helper to format context string
const formatContext = (context, order) => {
    const parts = context.split('-');
    if (order === 1) {
        // Full names for Order 1
        return parts.map(p => STATE_INFO_MAP[p]?.name || p).join('-');
    } else {
        // Short names (G, N, R) for Order > 1
        const shortMap = { 'U': 'G', 'N': 'N', 'D': 'R' };
        return parts.map(p => shortMap[p] || p).join('-');
    }
};

// Helper to render colored context
const renderContext = (context, order) => {
    const parts = context.split('-');
    const shortMap = { 'U': 'G', 'N': 'N', 'D': 'R' };
    const colorMap = { 'U': '#4caf50', 'N': '#9e9e9e', 'D': '#f44336' }; // Green, Grey, Red

    return (
        <span>
            {parts.map((p, i) => {
                const text = order === 1 ? (STATE_INFO_MAP[p]?.name || p) : (shortMap[p] || p);
                const color = STATE_INFO_MAP[p]?.color || '#d7e3f3';
                return (
                    <span key={i}>
                        <span style={{ color: color, fontWeight: 'bold' }}>{text}</span>
                        {i < parts.length - 1 && <span style={{ color: '#666' }}>-</span>}
                    </span>
                );
            })}
        </span>
    );
};

const MarkovTransitionMatrix = ({ data, settings }) => {
    if (!data || data.length === 0) {
        return <p style={{ color: '#9e9e9e', padding: '20px' }}>No Markov data available for the current configuration.</p>;
    }

    // 1. Prepare Data for Table and Heatmap
    // Extract contexts and probabilities from the data array
    const contexts = data.map(d => d.context);

    // Determine the state columns dynamically (e.g., mc_prob_up, mc_prob_neutral, mc_prob_down)
    const probKeys = Object.keys(data[0]).filter(key => key.startsWith('mc_prob_'));
    const stateNames = probKeys.map(key => key.split('_').pop()); // e.g., ['up', 'neutral', 'down']

    // Create a matrix of probability values (rows=contexts, cols=states)
    const probMatrix = contexts.map(context => probKeys.map(key => data.find(d => d.context === context)?.[key] * 100 || 0));

    // 2. Prepare Data for Heatmap (Plotly)
    const heatmapData = [{
        z: probMatrix,
        x: stateNames.map(name => STATE_INFO_MAP[name.charAt(0).toUpperCase()]?.name || name), // Labels: Up, Neutral, Down
        y: contexts.map(c => formatContext(c, settings.markovOrder)), // Translate based on order
        type: 'heatmap',
        colorscale: [
            ['0.0', 'rgb(244, 67, 54)'],   // Red for Low Prob
            ['0.5', 'rgb(158, 158, 158)'], // Gray for Mid Prob
            ['1.0', 'rgb(76, 175, 80)']   // Green for High Prob
        ],
        showscale: false, // Hide the side scale bar
        hoverongaps: false,
        text: probMatrix.map(row => row.map(val => `${val.toFixed(1)}%`)), // Display percentage in hover text
        texttemplate: "%{text}", // Show text on the heatmap cells
        hoverinfo: 'text',
        hovertemplate: 'Context: %{y}<br>Next State: %{x}<br>Probability: %{text}<extra></extra>'
    }];

    // 3. Prepare Data for Table Display
    // 3. Prepare Data for Table Display
    const tableHeaders = ['Context', ...probKeys.map(key => STATE_INFO_MAP[key.split('_').pop().charAt(0).toUpperCase()]?.name + ' Prob (%)' || key)];

    const tableRows = contexts.map((context, i) => {
        const row = {
            Context: renderContext(context, settings.markovOrder)
        };

        probKeys.forEach((key, j) => {
            // Use the translated header name as the key
            const translatedHeader = STATE_INFO_MAP[key.split('_').pop().charAt(0).toUpperCase()]?.name + ' Prob (%)' || key;
            row[translatedHeader] = probMatrix[i][j].toFixed(2) + '%';
        });
        return row;
    });


    // 4. Define Layout and Component
    const layout = {
        title: { text: `Transition Matrix: Order 1 (${settings.nStates} States)`, font: { size: 16, color: '#d7e3f3', align: 'left' } },
        height: 400,
        autosize: true,
        margin: { t: 50, b: 50, l: 80, r: 20 },
        plot_bgcolor: '#0e1525',
        paper_bgcolor: '#0b1220',
        font: { color: '#d7e3f3', family: 'Arial, sans-serif' },
        xaxis: { linecolor: '#203049', ticks: '', side: 'top', zeroline: false },
        yaxis: { linecolor: '#203049', ticks: '', automargin: true, zeroline: false },
        modebar: { bgcolor: '#203049', color: '#d7e3f3', activecolor: '#9ec4ff' }
    };


    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', width: '100%' }}>

            {/* Heatmap Visualization (Moved to Top) */}
            <div style={{ border: '1px solid #203049', borderRadius: '8px', overflow: 'hidden', height: '450px' }}>
                <Plot
                    data={heatmapData}
                    layout={layout}
                    config={{ responsive: true, displayModeBar: false }}
                    style={{ width: '100%', height: '100%' }}
                />
            </div>

            {/* Matrix Table */}
            <div style={{ border: '1px solid #203049', borderRadius: '8px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                <h4 style={{ margin: '10px', color: '#9ec4ff' }}>Probability Table</h4>
                <div style={{ overflowY: 'auto', padding: '0 10px 10px 10px' }}>
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

export default MarkovTransitionMatrix;
