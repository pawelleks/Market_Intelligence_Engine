import React, { useMemo } from 'react';
import Plot from 'react-plotly.js';
import { ChartExplainer } from './ChartExplainer';

interface HistoryBar {
    x: number;
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
}

interface HeatmapGrid {
    days: number[];
    strikes: number[];
    prob_above: number[][];
}

interface PriceHistoryHeatmapProps {
    data: {
        ticker: string;
        spot_price: number;
        history: HistoryBar[];
        heatmap: HeatmapGrid;
    } | null;
    ticker: string;
}

const COLORSCALE: [number, string][] = [
    [0, '#7f1d1d'],
    [0.1, '#dc2626'],
    [0.25, '#f97316'],
    [0.5, '#fef08a'],
    [0.75, '#3b82f6'],
    [0.9, '#1d4ed8'],
    [1, '#1e3a8a'],
];

const CONTOUR_LEVELS = [
    { level: 0.10, label: '10%', width: 1, dash: 'solid' as const },
    { level: 0.25, label: '25%', width: 1, dash: 'solid' as const },
    { level: 0.50, label: '50%', width: 2.5, dash: 'dash' as const },
    { level: 0.75, label: '75%', width: 1, dash: 'solid' as const },
    { level: 0.90, label: '90%', width: 1, dash: 'solid' as const },
];

export const PriceHistoryHeatmap: React.FC<PriceHistoryHeatmapProps> = ({ data, ticker }) => {
    const { traces, candleShapes } = useMemo(() => {
        if (!data?.heatmap?.prob_above || !data?.history) return { traces: null, candleShapes: [] };

        const { history, heatmap, spot_price } = data;
        const { days, strikes, prob_above } = heatmap;

        const traceList: any[] = [];
        const shapes: any[] = [];

        // 1. Heatmap trace
        traceList.push({
            type: 'heatmap',
            x: days,
            y: strikes,
            z: prob_above,
            colorscale: COLORSCALE,
            zsmooth: 'best',
            zmin: 0,
            zmax: 1,
            showscale: true,
            hovertemplate: 'Day +%{x}<br>Price: $%{y:.0f}<br>P(Above): %{z:.1%}<extra></extra>',
            colorbar: {
                title: { text: 'Probability (%)', side: 'right', font: { size: 12, color: '#94a3b8' } },
                tickvals: [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0],
                ticktext: ['0%', '10%', '25%', '50%', '75%', '90%', '100%'],
                tickfont: { color: '#94a3b8', size: 10 },
                len: 0.8,
                thickness: 15,
                x: 1.02,
            },
        });

        // 2-6. Contour lines at 10%, 25%, 50%, 75%, 90%
        for (const c of CONTOUR_LEVELS) {
            traceList.push({
                type: 'contour',
                x: days,
                y: strikes,
                z: prob_above,
                autocontour: false,
                contours: {
                    start: c.level,
                    end: c.level,
                    size: 0.01,
                    coloring: 'none',
                    showlabels: true,
                    labelfont: { size: 11, color: 'rgba(0,0,0,0.9)' },
                },
                line: {
                    color: 'rgba(0,0,0,0.85)',
                    width: c.width,
                    dash: c.dash,
                },
                showscale: false,
                showlegend: false,
                hoverinfo: 'skip',
                name: c.label,
            });
        }

        // 7. Manual candles (Plotly candlestick type doesn't render on numeric x-axes)
        if (history.length > 0) {
            // Wick lines (high-low vertical segments)
            const wickX: (number | null)[] = [];
            const wickY: (number | null)[] = [];
            for (const h of history) {
                wickX.push(h.x, h.x, null);
                wickY.push(h.low, h.high, null);
            }
            traceList.push({
                type: 'scatter',
                mode: 'lines',
                x: wickX,
                y: wickY,
                line: { color: '#d1d5db', width: 1 },
                showlegend: false,
                hoverinfo: 'skip',
            });

            // Hover points at close prices for tooltip
            traceList.push({
                type: 'scatter',
                mode: 'markers',
                x: history.map(h => h.x),
                y: history.map(h => h.close),
                marker: { size: 0.1, color: 'rgba(0,0,0,0)' },
                text: history.map(h =>
                    `${h.date}<br>O: $${h.open.toFixed(2)}<br>H: $${h.high.toFixed(2)}<br>L: $${h.low.toFixed(2)}<br>C: $${h.close.toFixed(2)}`
                ),
                hoverinfo: 'text',
                name: 'OHLC',
                showlegend: true,
            });

            // Candle body shapes
            for (const h of history) {
                const isUp = h.close >= h.open;
                shapes.push({
                    type: 'rect',
                    x0: h.x - 0.35,
                    x1: h.x + 0.35,
                    y0: Math.min(h.open, h.close),
                    y1: Math.max(h.open, h.close),
                    fillcolor: isUp ? '#d1d5db' : '#6b7280',
                    line: { color: '#d1d5db', width: 1 },
                    xref: 'x',
                    yref: 'y',
                });
            }
        }

        // 8. Spot price horizontal line
        const xMin = history.length > 0 ? Math.min(...history.map(h => h.x)) : -20;
        const xMax = days.length > 0 ? Math.max(...days) : 45;
        traceList.push({
            type: 'scatter',
            mode: 'lines',
            x: [xMin, xMax],
            y: [spot_price, spot_price],
            line: { color: '#22d3ee', width: 1.5, dash: 'dash' },
            name: `Spot $${spot_price.toLocaleString(undefined, { minimumFractionDigits: 0 })}`,
            showlegend: true,
            hoverinfo: 'skip',
        });

        return { traces: traceList, candleShapes: shapes };
    }, [data]);

    // Build x-axis tick labels
    const tickConfig = useMemo(() => {
        if (!data) return { tickvals: [], ticktext: [] };

        const vals: number[] = [];
        const text: string[] = [];

        // History dates (every 5th bar)
        if (data.history) {
            for (let i = 0; i < data.history.length; i++) {
                if (i % 5 === 0 || i === data.history.length - 1) {
                    vals.push(data.history[i].x);
                    text.push(data.history[i].date);
                }
            }
        }

        // Future days
        if (data.heatmap?.days) {
            const futureTicks = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45];
            for (const d of futureTicks) {
                if (data.heatmap.days.includes(d)) {
                    vals.push(d);
                    text.push(d === 0 ? 'Today' : `+${d}d`);
                }
            }
        }

        return { tickvals: vals, ticktext: text };
    }, [data]);

    // Y-axis range
    const yRange = useMemo(() => {
        if (!data?.heatmap?.strikes) return undefined;
        const s = data.heatmap.strikes;
        return [s[0], s[s.length - 1]];
    }, [data]);

    // X-axis range
    const xRange = useMemo(() => {
        if (!data) return [-20, 46];
        const xMin = data.history?.length > 0 ? Math.min(...data.history.map(h => h.x)) - 1 : -20;
        const xMax = data.heatmap?.days?.length > 0 ? Math.max(...data.heatmap.days) + 1 : 46;
        return [xMin, xMax];
    }, [data]);

    if (!traces || traces.length === 0) {
        return (
            <div className="w-full h-[650px] bg-[#0e1525] rounded-xl border border-slate-700 p-4 flex items-center justify-center text-slate-500">
                No Heatmap Data Available — Run the probability pipeline
            </div>
        );
    }

    return (
        <div className="w-full bg-[#0e1525] rounded-xl border border-slate-700 p-4">
            <Plot
                data={traces}
                layout={{
                    title: {
                        text: `${ticker} Price History + Probability of Being ABOVE Each Price Level`,
                        font: { color: '#e2e8f0', size: 16 },
                        x: 0.5,
                    },
                    paper_bgcolor: '#0b1220',
                    plot_bgcolor: '#0b1220',
                    xaxis: {
                        title: { text: '', font: { color: '#94a3b8' } },
                        color: '#94a3b8',
                        gridcolor: '#1e293b',
                        range: xRange,
                        tickvals: tickConfig.tickvals,
                        ticktext: tickConfig.ticktext,
                        tickangle: -45,
                        tickfont: { size: 10, color: '#94a3b8' },
                        rangeslider: { visible: false },
                        zeroline: true,
                        zerolinecolor: 'rgba(255,255,255,0.3)',
                        zerolinewidth: 1,
                    },
                    yaxis: {
                        title: { text: 'Price ($)', font: { color: '#94a3b8' } },
                        color: '#94a3b8',
                        gridcolor: '#1e293b',
                        range: yRange,
                        side: 'left',
                        tickformat: '$,.0f',
                        tickfont: { size: 11, color: '#94a3b8' },
                    },
                    yaxis2: {
                        overlaying: 'y',
                        side: 'right',
                        range: yRange,
                        tickformat: '$,.0f',
                        tickfont: { size: 11, color: '#94a3b8' },
                        showgrid: false,
                    },
                    shapes: candleShapes,
                    margin: { l: 70, r: 80, b: 60, t: 50 },
                    height: 650,
                    showlegend: true,
                    legend: {
                        font: { color: '#cbd5e1', size: 11 },
                        bgcolor: 'rgba(0,0,0,0.3)',
                        x: 0,
                        y: 1,
                    },
                }}
                config={{ responsive: true, displayModeBar: false }}
                style={{ width: '100%', height: '100%' }}
            />
            <ChartExplainer>
                <p className="pt-2"><strong className="text-slate-300">What this shows:</strong> The left side displays recent price history as candlesticks. The right side is a probability heatmap showing the market's implied probability that price will be <em>above</em> each price level on each future date, derived from current options pricing via Breeden-Litzenberger.</p>
                <p><strong className="text-slate-300">Color scale:</strong> <span className="text-red-400">Deep red</span> = very high probability (&gt;90%) price stays above this level. <span className="text-blue-400">Deep blue</span> = very low probability (&lt;10%) price reaches this level.</p>
                <p><strong className="text-slate-300">Contour lines (support &amp; resistance):</strong></p>
                <ul className="list-disc list-inside ml-2 space-y-1">
                    <li><strong>90% line</strong> (bottom): Market-implied support. 90% chance price stays above. Breaking below is an extreme outlier.</li>
                    <li><strong>50% line</strong> (dashed, middle): The forward median. The market's best estimate of where price settles.</li>
                    <li><strong>10% line</strong> (top): Market-implied resistance. Only 10% chance price exceeds this level.</li>
                </ul>
                <p><strong className="text-slate-300">The cone shape:</strong> Lines fan out further into the future because uncertainty grows with time. A wide cone means the market is pricing high volatility; a narrow cone means low expected movement.</p>
                <p><strong className="text-slate-300">Spot line:</strong> The dashed cyan horizontal line marks the current closing price.</p>
            </ChartExplainer>
        </div>
    );
};

export default PriceHistoryHeatmap;
