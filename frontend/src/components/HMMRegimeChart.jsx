import React from 'react';
import Plot from 'react-plotly.js';

const getTenYearRange = (dates) => {
    if (dates.length < 2) return null;
    const endDate = dates[dates.length - 1];
    const endYear = parseInt(endDate.substring(0, 4));
    const tenYearStartYear = (endYear - 10);
    // Construct start date string YYYY-MM-DD
    const tenYearStart = tenYearStartYear + endDate.substring(4);
    return [tenYearStart, endDate];
};

const HMMRegimeChart = ({ data, priceData, windowYears, nStates, bullThreshold, bearThreshold, ticker }) => {
    if (!data || data.length === 0) {
        return <div style={{ color: '#9e9e9e', padding: '20px' }}>No HMM probability data available.</div>;
    }

    // --- 1. Prepare Data ---
    const dates = data.map(d => d.date);

    // Add the zoom calculation inside the component:
    const tenYearRange = getTenYearRange(dates);

    // --- Price Trace (Main Line) ---
    let priceTrace = [];
    if (priceData && priceData.length > 0) {
        const priceDates = priceData.map(d => d.date);
        const priceColumn = priceData[0]?.adj_close !== undefined ? 'adj_close' :
            priceData[0]?.close !== undefined ? 'close' :
                priceData[0]?.adj_close_x !== undefined ? 'adj_close_x' :
                    priceData[0]?.close_x !== undefined ? 'close_x' :
                        priceData[0]?.Adj_Close !== undefined ? 'Adj_Close' : null;

        if (priceColumn) {
            const prices = priceData.map(d => d[priceColumn]);
            priceTrace = [{
                x: priceDates,
                y: prices,
                mode: 'lines',
                name: 'Asset Price',
                line: { color: '#9ec4ff', width: 2 }, // Light blue line
                hoverinfo: 'x+y+name',
                hovertemplate: 'Price: $%{y:.2f}'
            }];
        }
    }

    // --- Regime Background Shapes ---
    // We need to create rectangular shapes for periods where a regime is dominant.
    // This is computationally heavier but gives the "background band" look.
    // Algorithm: Iterate through data, find contiguous blocks where prob > threshold.

    const shapes = [];
    let currentRegime = null;
    let startIndex = null;

    // Helper to add shape
    const addShape = (regime, start, end) => {
        let color = 'rgba(0,0,0,0)';
        if (regime === 'Bull') color = 'rgba(76, 175, 80, 0.2)'; // Green low opacity
        if (regime === 'Bear') color = 'rgba(244, 67, 54, 0.2)'; // Red low opacity
        // Neutral is usually transparent or gray, let's skip for clarity or add if needed

        if (color !== 'rgba(0,0,0,0)') {
            shapes.push({
                type: 'rect',
                xref: 'x',
                yref: 'paper',
                x0: dates[start],
                x1: dates[end],
                y0: 0,
                y1: 1,
                fillcolor: color,
                line: { width: 0 },
                layer: 'below'
            });
        }
    };

    data.forEach((d, i) => {
        let dominant = null;
        // Simple logic: if Bull > threshold -> Bull, if Bear > threshold -> Bear
        // Priority to Bear if both (unlikely with high thresholds)
        if (d.hmm_prob_bear * 100 >= bearThreshold) dominant = 'Bear';
        else if (d.hmm_prob_bull * 100 >= bullThreshold) dominant = 'Bull';

        if (dominant !== currentRegime) {
            // Regime change
            if (currentRegime !== null) {
                addShape(currentRegime, startIndex, i - 1);
            }
            currentRegime = dominant;
            startIndex = i;
        }
    });
    // Add last segment
    if (currentRegime !== null && startIndex !== null) {
        addShape(currentRegime, startIndex, data.length - 1);
    }

    // --- Legend Traces (Dummy traces for background colors) ---
    // We add these so the user knows what the background colors mean.
    const legendTraces = [
        {
            x: [null],
            y: [null],
            name: 'Bull Regime',
            mode: 'markers',
            marker: { color: 'rgba(76, 175, 80, 1)', size: 10, symbol: 'square' }, // Solid green for legend
            showlegend: true,
            hoverinfo: 'none'
        },
        {
            x: [null],
            y: [null],
            name: 'Bear Regime',
            mode: 'markers',
            marker: { color: 'rgba(244, 67, 54, 1)', size: 10, symbol: 'square' }, // Solid red for legend
            showlegend: true,
            hoverinfo: 'none'
        }
    ];

    const traces = [...priceTrace, ...legendTraces];


    // --- 2. Define Layout (Single Axis with Background Shapes) ---
    const layout = {
        height: 500,
        autosize: true,
        margin: { t: 60, b: 50, l: 50, r: 50 },
        font: { color: '#d7e3f3', family: 'Arial, sans-serif' },
        plot_bgcolor: '#0e1525',
        paper_bgcolor: '#0b1220',

        // Add shapes for regimes
        shapes: shapes,

        xaxis: {
            title: 'Date',
            // Set default range to last 5 years
            range: [
                dates.length > 0 ? new Date(new Date(dates[dates.length - 1]).setFullYear(new Date(dates[dates.length - 1]).getFullYear() - 5)).toISOString().split('T')[0] : undefined,
                dates.length > 0 ? dates[dates.length - 1] : undefined
            ],
            autorange: false,
            showgrid: true,
            gridcolor: '#203049',
            linecolor: '#203049',
            zerolinecolor: '#203049',
            rangeslider: {
                visible: true,
                bgcolor: '#203049',
                bordercolor: '#203049'
            },
            rangeselector: {
                buttons: [
                    { step: 'year', stepmode: 'backward', count: 1, label: '1Y' },
                    { step: 'year', stepmode: 'backward', count: 5, label: '5Y' },
                    { step: 'year', stepmode: 'backward', count: 10, label: '10Y' },
                    { step: 'year', stepmode: 'backward', count: 15, label: '15Y' },
                    { step: 'year', stepmode: 'backward', count: 20, label: '20Y' },
                    { step: 'all', label: 'Max' },
                ],
                bgcolor: '#203049',
                font: { size: 10, color: '#d7e3f3' }
            },
        },

        // Primary Y-Axis (Price)
        yaxis: {
            title: 'Asset Price (USD)',
            showgrid: true,
            gridcolor: '#203049',
            linecolor: '#203049',
            zerolinecolor: '#203049',
            fixedrange: false // Allow zoom on Y
        },

        legend: {
            orientation: 'h',
            y: 1.02,
            x: 1,
            xanchor: 'right',
            bgcolor: 'rgba(0,0,0,0)',
            font: { size: 12, color: '#d7e3f3' }
        },
        modebar: { bgcolor: '#203049', color: '#d7e3f3', activecolor: '#9ec4ff' }
    };

    return (
        <div style={{ width: '100%', height: '100%' }}>
            <h3 style={{ margin: '0 0 15px 0', fontSize: '1.2rem', color: '#d7e3f3', textAlign: 'left', fontWeight: 'bold' }}>
                {ticker}: Regime Probabilities (Trained on {windowYears}Y)
            </h3>
            <Plot
                data={traces}
                layout={layout}
                config={{ responsive: true, displayModeBar: true, scrollZoom: true }}
                style={{ width: '100%', height: '100%' }}
            />
        </div>
    );
};

export default HMMRegimeChart;
