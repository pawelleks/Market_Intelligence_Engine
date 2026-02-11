import React, { useMemo } from 'react';
import Plot from 'react-plotly.js';

interface ChartProps {
    history: any[]; // { date, open, high, low, close }
    projection: any[]; // { date, p05, p25, p50, p75, p95 }
    currentPrice: number;
}

export const ForwardProjectionChart: React.FC<ChartProps> = ({ history, projection, currentPrice }) => {

    const data = useMemo(() => {
        if (!history.length && !projection.length) return [];

        const traces: any[] = [];

        // 1. History (Candlesticks)
        if (history.length > 0) {
            traces.push({
                x: history.map(d => d.date),
                close: history.map(d => d.close),
                decreasing: { line: { color: '#ef4444' } },
                high: history.map(d => d.high),
                increasing: { line: { color: '#22c55e' } },
                line: { color: 'rgba(31,119,180,1)' },
                low: history.map(d => d.low),
                open: history.map(d => d.open),
                type: 'candlestick',
                xaxis: 'x',
                yaxis: 'y',
                name: 'SPX History'
            });
        }

        // 2. Projection Fan Chart
        if (projection.length > 0) {
            const dates = projection.map(d => d.date);

            // Outer Band (5th to 95th)
            // We draw the upper bound (p95) and lower bound (p05)
            // But for "fill", we usually trace the upper, then trace the lower in reverse?
            // Plotly "tonexty" fills between traces.

            // Trace 1: p05 (Invisible bottom of outer band)
            traces.push({
                x: dates,
                y: projection.map(d => d.p05),
                mode: 'lines',
                line: { width: 0, color: 'transparent' },
                showlegend: false,
                name: 'Lower Support (p05)'
            });

            // Trace 2: p95 (Top of outer band, fill down to p05)
            traces.push({
                x: dates,
                y: projection.map(d => d.p95),
                mode: 'lines',
                line: { width: 1, color: 'rgba(239, 68, 68, 0.4)' }, // Red boundary
                fill: 'tonexty',
                fillcolor: 'rgba(239, 68, 68, 0.1)', // Very faint red
                name: '90% Conf. Interval'
            });

            // Inner Band (25th to 75th)
            // Trace 3: p25 (Invisible bottom of inner band)
            traces.push({
                x: dates,
                y: projection.map(d => d.p25),
                mode: 'lines',
                line: { width: 0, color: 'transparent' },
                showlegend: false,
                name: 'p25'
            });

            // Trace 4: p75 (Top of inner band, fill down to p25)
            traces.push({
                x: dates,
                y: projection.map(d => d.p75),
                mode: 'lines',
                line: { width: 1, color: 'rgba(245, 158, 11, 0.4)' }, // Orange boundary
                fill: 'tonexty',
                fillcolor: 'rgba(245, 158, 11, 0.2)', // Orange/Yellow
                name: '50% Conf. Interval'
            });

            // Median Line (p50)
            traces.push({
                x: dates,
                y: projection.map(d => d.p50),
                mode: 'lines',
                line: {
                    color: 'white',
                    width: 2,
                    dash: 'dot'
                },
                name: 'Median Projection'
            });
        }

        return traces;
    }, [history, projection]);

    return (
        <div className="w-full h-[500px] bg-[#0e1525] rounded-xl border border-slate-700/50 p-4 shadow-xl relative overflow-hidden">
            <Plot
                data={data}
                layout={{
                    autosize: true,
                    margin: { t: 40, r: 20, l: 50, b: 40 },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    font: { family: 'Inter', color: '#94a3b8' },
                    showlegend: true,
                    legend: { orientation: 'h', y: 1.05, x: 0.5, xanchor: 'center' },
                    xaxis: {
                        gridcolor: '#1e293b',
                        zerolinecolor: '#334155',
                        rangeslider: { visible: false }, // Disable range slider for cleaner look
                        rangebreaks: [
                            { bounds: ["sat", "mon"] } // Optional: Hide weekends? Might break interpolation continuity visually if not careful
                        ]
                    },
                    yaxis: {
                        gridcolor: '#1e293b',
                        zerolinecolor: '#334155',
                        autoscale: true // Ensure Y-Axis scales to data
                    },
                    annotations: projection.length > 0 ? [
                        {
                            x: projection[projection.length - 1].date,
                            y: projection[projection.length - 1].p95,
                            xref: 'x', yref: 'y',
                            text: 'Upper Resistance',
                            showarrow: true,
                            ax: 20, ay: -20,
                            font: { color: '#f87171', size: 10 }
                        },
                        {
                            x: projection[projection.length - 1].date,
                            y: projection[projection.length - 1].p05,
                            xref: 'x', yref: 'y',
                            text: 'Lower Support',
                            showarrow: true,
                            ax: 20, ay: 20,
                            font: { color: '#f87171', size: 10 }
                        }
                    ] : []
                }}
                useResizeHandler={true}
                className="w-full h-full"
                config={{ displayModeBar: false }}
            />
        </div>
    );
};
