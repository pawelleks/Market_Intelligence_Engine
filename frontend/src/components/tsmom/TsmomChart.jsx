import React from 'react';
import Plot from 'react-plotly.js';

const TsmomChart = ({ chartData, ticker }) => {
    if (!chartData) return <div style={{ color: '#68778d' }}>Select a ticker to view chart.</div>;

    // Unwrap data
    // Expected: { ohlc: [...], signals: [...] }
    const { ohlc, signals } = chartData;

    if (!ohlc || ohlc.length === 0) return <div>No price data available.</div>;

    // Prepare traces
    const dates = ohlc.map(d => d.date_str || d.date);
    const prices = ohlc.map(d => d.price || d.close);

    const priceTrace = {
        x: dates,
        y: prices,
        type: 'scatter',
        mode: 'lines',
        name: 'Price',
        line: { color: '#64b5f6', width: 1.5 }
    };

    const traces = [priceTrace];

    // Annotations/Markers for Signals
    // Annotations/Markers for Signals
    const shapes = [];

    if (signals && signals.length > 0) {
        // Sort signals by date
        const sortedSignals = [...signals].sort((a, b) => new Date(a.event_date) - new Date(b.event_date));

        // Generate Shapes for Regimes
        // We assume the regime starts at signal date and lasts until next signal or end of data
        const lastDate = dates[dates.length - 1]; // End of chart

        sortedSignals.forEach((sig, idx) => {
            const nextSig = sortedSignals[idx + 1];
            const end = nextSig ? nextSig.event_date : lastDate;

            const color = sig.signal === 'BUY' ? 'rgba(76, 175, 80, 0.1)' : 'rgba(244, 67, 54, 0.1)';

            shapes.push({
                type: 'rect',
                xref: 'x',
                yref: 'paper',
                x0: sig.event_date,
                x1: end,
                y0: 0,
                y1: 1,
                fillcolor: color,
                line: { width: 0 },
                layer: 'below'
            });
        });

        // Separate BUY and SELL for Markers
        const buyst = signals.filter(s => s.signal === 'BUY');
        const sellst = signals.filter(s => s.signal === 'SELL');

        if (buyst.length > 0) {
            traces.push({
                x: buyst.map(s => s.event_date),
                y: buyst.map(s => s.close),
                type: 'scatter',
                mode: 'markers',
                name: 'BUY',
                marker: { symbol: 'triangle-up', size: 10, color: '#4caf50' }
            });
        }

        if (sellst.length > 0) {
            traces.push({
                x: sellst.map(s => s.event_date),
                y: sellst.map(s => s.close),
                type: 'scatter',
                mode: 'markers',
                name: 'SELL',
                marker: { symbol: 'triangle-down', size: 10, color: '#f44336' }
            });
        }
    }

    return (
        <div style={{ padding: '20px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049' }}>
            <h3 style={{ margin: '0 0 10px 0', color: '#d7e3f3' }}>{ticker} Performance & Signals</h3>
            <Plot
                data={traces}
                layout={{
                    autosize: true,
                    height: 400,
                    margin: { l: 50, r: 20, t: 20, b: 40 },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    showlegend: true,
                    legend: { x: 0, y: 1, font: { color: '#d7e3f3' } },
                    xaxis: {
                        gridcolor: '#203049',
                        tickfont: { color: '#68778d' }
                    },
                    yaxis: {
                        gridcolor: '#203049',
                        tickfont: { color: '#68778d' },
                        title: { text: 'Price', font: { color: '#68778d' } }
                    },
                    shapes: shapes
                }}
                useResizeHandler={true}
                style={{ width: '100%' }}
            />
        </div>
    );
};

export default TsmomChart;
