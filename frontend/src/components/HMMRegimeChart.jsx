import React from 'react';
import Plot from 'react-plotly.js';

const HMMRegimeChart = ({ data, priceData, windowYears, nStates, bullThreshold, bearThreshold }) => {
    if (!data || data.length === 0) {
        return <div style={{ color: '#9e9e9e', padding: '20px' }}>No HMM probability data available.</div>;
    }

    // --- 1. Prepare Data ---
    const dates = data.map(d => d.date);
    const bullProbs = data.map(d => d.hmm_prob_bull * 100);
    const bearProbs = data.map(d => d.hmm_prob_bear * 100);
    const hasNeutral = data[0]?.hmm_prob_neutral !== undefined;
    const neutralProbs = hasNeutral ? data.map(d => d.hmm_prob_neutral * 100) : [];

    // --- HMM Regime Traces (Left Y-Axis, Stacked) ---
    const hmmTraces = [
        {
            x: dates,
            y: bullProbs,
            mode: 'lines',
            name: 'P(Bull Regime)',
            line: { color: '#4caf50', width: 0 },
            fill: 'tonexty',
            stackgroup: 'one',
            hoverinfo: 'x+y+name',
            hovertemplate: '%{y:.2f}%%<extra></extra>', // FIX: Added % symbol
            yaxis: 'y1'
        },
        ...(hasNeutral ? [{
            x: dates,
            y: neutralProbs,
            mode: 'lines',
            name: 'P(Neutral Regime)',
            line: { color: '#9e9e9e', width: 0 },
            fill: 'tonexty',
            stackgroup: 'one',
            hoverinfo: 'x+y+name',
            hovertemplate: '%{y:.2f}%%<extra></extra>', // FIX: Added % symbol
            yaxis: 'y1'
        }] : []),
        {
            x: dates,
            y: bearProbs,
            mode: 'lines',
            name: 'P(Bear Regime)',
            line: { color: '#f44336', width: 0 },
            fill: 'tonexty',
            stackgroup: 'one',
            hoverinfo: 'x+y+name',
            hovertemplate: '%{y:.2f}%%<extra></extra>', // FIX: Added % symbol
            yaxis: 'y1'
        }
    ];

    // --- Price Overlay Trace (Right Secondary Y-Axis) ---
    let priceTrace = [];
    let showPriceAxis = false;

    if (priceData && priceData.length > 0) {
        const priceDates = priceData.map(d => d.date);
        const priceColumn = priceData[0]?.adj_close !== undefined ? 'adj_close' :
            priceData[0]?.close !== undefined ? 'close' :
                priceData[0]?.Adj_Close !== undefined ? 'Adj_Close' : null;

        if (priceColumn) {
            const prices = priceData.map(d => d[priceColumn]);
            showPriceAxis = true;

            priceTrace = [{
                x: priceDates,
                y: prices,
                mode: 'lines',
                name: 'Asset Price',
                line: { color: '#d7e3f3', width: 1.5, dash: 'solid' },
                yaxis: 'y2',
                hoverinfo: 'x+y+name',
                hovertemplate: '%{y:.2f}'
            }];
        }
    }

    // --- Threshold Traces ---
    const thresholdTraces = [
        // Bull Threshold Line
        {
            x: dates,
            y: Array(dates.length).fill(bullThreshold),
            mode: 'lines',
            name: `Bull Signal (${bullThreshold}%)`,
            line: { color: '#4caf50', width: 1, dash: 'dot' },
            yaxis: 'y1',
            hoverinfo: 'name'
        },
        // Bear Threshold Line
        {
            x: dates,
            y: Array(dates.length).fill(bearThreshold),
            mode: 'lines',
            name: `Bear Signal (${bearThreshold}%)`,
            line: { color: '#f44336', width: 1, dash: 'dot' },
            yaxis: 'y1',
            hoverinfo: 'name'
        }
    ];

    const traces = [...hmmTraces, ...priceTrace, ...thresholdTraces];


    // --- 2. Define Layout (Dual-Axis Configuration) ---
    const layout = {
        title: { text: `Regime Probabilities (Trained on ${windowYears}Y)`, font: { size: 16, color: '#d7e3f3', align: 'left' } },
        height: 650,
        autosize: true,
        margin: { t: 50, b: 50, l: 50, r: 50 },
        font: { color: '#d7e3f3', family: 'Arial, sans-serif' },
        plot_bgcolor: '#0e1525',
        paper_bgcolor: '#0b1220',

        xaxis: {
            title: 'Date',
            showgrid: true,
            gridcolor: '#203049',
            linecolor: '#203049',
            zerolinecolor: '#203049',
            rangeslider: {
                visible: true,
                range: [dates[0], dates[dates.length - 1]],
                bgcolor: '#203049',
                bordercolor: '#203049'
            },
            rangeselector: {
                buttons: [
                    { step: 'year', stepmode: 'backward', count: 1, label: '1Y' },
                    { step: 'year', stepmode: 'backward', count: 5, label: '5Y' },
                    { step: 'year', stepmode: 'backward', count: 10, label: '10Y' },
                    { step: 'all', label: 'Max' },
                ],
                bgcolor: '#203049',
                font: { size: 10, color: '#d7e3f3' }
            },
        },

        // Primary Y-Axis (Left) for Probabilities
        yaxis: {
            title: 'Regime Probability (%)',
            range: [0, 100],
            showgrid: true,
            gridcolor: '#203049',
            linecolor: '#203049',
            zerolinecolor: '#203049',
            domain: [0, 1],
            fixedrange: true
        },

        // Secondary Y-Axis (Right) for Asset Price (Conditional visibility)
        yaxis2: {
            title: 'Asset Price (USD)',
            overlaying: 'y',
            side: 'right',
            showgrid: showPriceAxis,
            visible: showPriceAxis,
            zeroline: false,
            anchor: 'x'
        },

        legend: { orientation: 'h', y: 1.05, x: 0, bgcolor: 'rgba(0,0,0,0)', font: { size: 11 } },
        modebar: { bgcolor: '#203049', color: '#d7e3f3', activecolor: '#9ec4ff' }
    };

    return (
        <div style={{ width: '100%', height: '100%' }}>
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
