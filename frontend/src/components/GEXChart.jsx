import React from 'react';
import Plot from 'react-plotly.js';

const GEXChart = ({ data, spotPrice, emRange, title, height = 500, viewMode = 'split', yAxisRange, horizonLabel = 'W' }) => {
    if (!data || data.length === 0) {
        return <div style={{ color: '#888', textAlign: 'center', padding: '20px' }}>No GEX data available.</div>;
    }

    // Prepare Data
    const strikes = data.map(d => d.strike);
    const callGex = data.map(d => d.call_gex);
    // Ensure Puts are negative for logic, but for display we might want them on left
    const putGex = data.map(d => d.put_gex);

    let traces = [];

    if (viewMode === 'split') {
        traces = [
            {
                y: strikes, // Horizontal: Strikes on Y
                x: callGex, // GEX on X
                type: 'bar',
                name: 'Calls',
                orientation: 'h',
                marker: { color: '#4caf50' }, // Green
                hovertemplate: 'Strike: %{y}<br>Call GEX: $%{x:.2s}<extra></extra>'
            },
            {
                y: strikes,
                x: putGex, // Ensure these are negative in data for left-side plotting
                type: 'bar',
                name: 'Puts',
                orientation: 'h',
                marker: { color: '#f44336' }, // Red
                hovertemplate: 'Strike: %{y}<br>Put GEX: $%{x:.2s}<extra></extra>'
            }
        ];
    } else {
        // NET VIEW
        const netGex = data.map(d => d.call_gex + d.put_gex);

        // Color based on value
        const colors = netGex.map(v => v >= 0 ? '#4caf50' : '#f44336');

        traces = [
            {
                y: strikes,
                x: netGex,
                type: 'bar',
                name: 'Net GEX',
                orientation: 'h',
                marker: { color: colors },
                hovertemplate: 'Strike: %{y}<br>Net GEX: $%{x:.2s}<extra></extra>'
            }
        ];
    }

    // Shapes: Spot Line + EM Range
    const shapes = [];

    if (emRange && emRange.low !== undefined && emRange.high !== undefined) {
        // Expected Move Shaded Region
        shapes.push({
            type: 'rect',
            xref: 'paper',
            yref: 'y',
            x0: 0,
            x1: 1,
            y0: emRange.low,
            y1: emRange.high,
            fillcolor: 'rgba(255, 255, 255, 0.05)',
            line: { width: 0 },
            layer: 'below'
        });

        // Bounds Lines
        shapes.push({
            type: 'line',
            xref: 'paper', yref: 'y',
            x0: 0, x1: 1,
            y0: emRange.low, y1: emRange.low,
            line: { color: '#888', width: 1, dash: 'dot' }
        });
        shapes.push({
            type: 'line',
            xref: 'paper', yref: 'y',
            x0: 0, x1: 1,
            y0: emRange.high, y1: emRange.high,
            line: { color: '#888', width: 1, dash: 'dot' }
        });
    }

    if (spotPrice) {
        shapes.push({
            type: 'line',
            x0: 0,
            y0: spotPrice,
            x1: 1,
            y1: spotPrice,
            xref: 'paper',
            yref: 'y',
            line: {
                color: '#FFD700', // Gold/Yellow for Spot
                width: 1, // Thinner
                dash: 'dash'
            }
        });
    }

    // Find Max GEX Bar for Annotation
    let maxGexStrike = 0;
    let maxGexVal = 0;
    let maxGexType = 'net';
    data.forEach(d => {
        const c = Math.abs(d.call_gex);
        const p = Math.abs(d.put_gex);
        const n = Math.abs(d.call_gex + d.put_gex);

        if (viewMode === 'split') {
            if (c > maxGexVal) { maxGexVal = c; maxGexStrike = d.strike; maxGexType = 'Call'; }
            if (p > maxGexVal) { maxGexVal = p; maxGexStrike = d.strike; maxGexType = 'Put'; }
        } else {
            if (n > maxGexVal) { maxGexVal = n; maxGexStrike = d.strike; maxGexType = 'Net'; }
        }
    });

    // 4. Max GEX Line
    if (maxGexVal > 0) {
        shapes.push({
            type: 'line',
            xref: 'paper', yref: 'y',
            x0: 0, x1: 1,
            y0: maxGexStrike, y1: maxGexStrike,
            line: {
                color: '#2196f3', // Blue
                width: 2,
                dash: 'dash'
            }
        });
    }

    // Annotations
    const annotations = [];

    // 1. Spot Price (Refined -> Boxed Style)
    if (spotPrice) {
        annotations.push({
            x: 1,
            y: spotPrice,
            xref: 'paper',
            yref: 'y',
            text: `Spot: ${spotPrice.toFixed(2)}`,
            showarrow: false,
            font: { color: '#FFD700', size: 12, weight: 'bold' },
            xshift: 10,  // Push out slightly more
            yshift: 0,
            yanchor: 'middle',
            xanchor: 'left',
            // Box Styling
            bgcolor: 'rgba(0,0,0,0)', // Transparent
            bordercolor: '#FFD700',   // Yellow
            borderwidth: 1,
            borderpad: 4
        });
    }

    // 2. Expected Moves (Horizon Label)
    if (emRange) {
        annotations.push({
            x: 0,
            y: emRange.high,
            xref: 'paper',
            yref: 'y',
            text: `+${horizonLabel} EM ${emRange.high.toFixed(0)}`,
            showarrow: false,
            font: { color: '#888', size: 10 },
            xshift: -5,
            yanchor: 'bottom',
            xanchor: 'right'
        });
        annotations.push({
            x: 0,
            y: emRange.low,
            xref: 'paper',
            yref: 'y',
            text: `-${horizonLabel} EM ${emRange.low.toFixed(0)}`,
            showarrow: false,
            font: { color: '#888', size: 10 },
            xshift: -5,
            yanchor: 'top',
            xanchor: 'right'
        });
    }

    // 3. Max GEX Indication
    if (maxGexVal > 0) {
        // We want to point to the strike on the Y-axis, maybe on the left side or right
        // Let's put a marker on the right Y-axis for the Key Level
        annotations.push({
            x: 1,
            y: maxGexStrike,
            xref: 'paper',
            yref: 'y',
            text: `Max GEX: ${maxGexStrike}`,
            showarrow: false,
            font: { color: '#ffffff', size: 11 }, // White font
            xshift: 10,
            xanchor: 'left',
            bgcolor: 'rgba(33, 150, 243, 0.2)',
            bordercolor: '#2196f3',
            borderwidth: 1,
            borderpad: 4,
            opacity: 0.8
        });
    }

    return (
        <Plot
            data={traces}
            layout={{
                title: { text: title, font: { color: '#fff' } },
                height: height,
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                barmode: 'relative', // Stack for split (pushes + right, - left)
                xaxis: {
                    title: 'Gamma Exposure ($)',
                    color: '#aaa',
                    gridcolor: '#333',
                    zerolinecolor: '#666',
                    tickformat: '.2s'
                },
                yaxis: {
                    title: 'Strike Price',
                    color: '#aaa',
                    gridcolor: '#333',
                    zerolinecolor: '#666',
                    range: yAxisRange || undefined, // Apply dynamic zoom safely
                    // automargin: true
                },
                legend: {
                    x: 0,
                    y: 1.1,
                    orientation: 'h',
                    font: { color: '#fff' }
                },
                margin: { r: 150, l: 100, t: 80, b: 50 }, // Increased margins for labels
                shapes: shapes,
                annotations: annotations
            }}
            config={{ responsive: true, displayModeBar: false }}
            style={{ width: '100%' }}
        />
    );
};

export default GEXChart;
