import React from 'react';
import Plot from 'react-plotly.js';

const VolatilityChart = ({ data, ticker }) => {
    if (!data || data.length === 0) {
        return <div style={{ color: '#9e9e9e', padding: '20px' }}>No Chart Data Available</div>;
    }

    const dates = data.map(d => d.date);
    const close = data.map(d => d.close);
    const atr = data.map(d => d.atr);

    // Filter nulls just in case
    const validData = data.filter(d => d.close !== undefined && d.atr !== undefined && d.date);
    const validDates = validData.map(d => d.date);
    const validClose = validData.map(d => d.close);
    const validAtr = validData.map(d => d.atr);
    const validRegime = validData.map(d => d.regime);

    // --- Price Trace ---
    const priceTrace = {
        x: validDates,
        y: validClose,
        name: 'Price',
        type: 'scatter',
        mode: 'lines',
        line: { color: '#9ec4ff', width: 2 },
        yaxis: 'y1'
    };

    // --- ATR Trace ---
    const atrTrace = {
        x: validDates,
        y: validAtr,
        name: 'ATR (14)',
        type: 'scatter',
        mode: 'lines',
        line: { color: '#ffab40', width: 2 },
        yaxis: 'y2',
        fill: 'tozeroy', // Optional: Fill area under ATR
        fillcolor: 'rgba(255, 171, 64, 0.1)'
    };

    // --- Layout ---
    const layout = {
        autosize: true,
        height: 600,
        margin: { t: 50, b: 50, l: 50, r: 50 },
        font: { color: '#d7e3f3', family: 'Arial, sans-serif' },
        plot_bgcolor: '#0e1525',
        paper_bgcolor: '#0b1220',
        showlegend: true,
        legend: { orientation: 'h', y: 1.02, x: 0 },

        // X-Axis
        xaxis: {
            title: 'Date',
            showgrid: true,
            gridcolor: '#203049',
            range: [
                validDates.length > 252 ? validDates[validDates.length - 252] : validDates[0],
                validDates[validDates.length - 1]
            ],
            rangeslider: { visible: false }
        },

        // Y-Axis 1 (Price) - Top 70%
        yaxis: {
            title: 'Price ($)',
            domain: [0.35, 1],
            showgrid: true,
            gridcolor: '#203049'
        },

        // Y-Axis 2 (ATR) - Bottom 25%
        yaxis2: {
            title: 'ATR',
            domain: [0, 0.25],
            showgrid: true,
            gridcolor: '#203049'
        },

        // Shapes for Regimes (Optional visual candy)
        // Highlighting Squeezes?
        shapes: validData.map((d, i) => {
            if (d.regime === 'Squeeze') {
                return {
                    type: 'rect',
                    xref: 'x',
                    yref: 'paper',
                    x0: d.date,
                    x1: d.date, // Single day width needs careful handling or bar chart. 
                    // Shapes for single points are tricky. Let's skip for simple chart first.
                }
            }
            return null;
        }).filter(s => s)
    };

    return (
        <div style={{ width: '100%', height: '100%' }}>
            <Plot
                data={[priceTrace, atrTrace]}
                layout={layout}
                style={{ width: '100%', height: '100%' }}
                config={{ responsive: true, displayModeBar: true }}
            />
        </div>
    );
};

export default VolatilityChart;
