import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import { AlertCircle, CheckCircle, TrendingUp } from 'lucide-react';

const VolatilityTermStructurePage = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await fetch('/api/v1/analytics/volatility/term-structure');
                const json = await res.json();
                if (res.ok) {
                    setData(json);
                } else {
                    console.error("Failed to fetch VTS data");
                }
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return <div style={{ padding: '20px', color: '#ccc' }}>Loading Term Structure...</div>;
    if (!data) return <div style={{ padding: '20px', color: '#ef5350' }}>Error loading data.</div>;

    const history = data.data;
    const latest = data.latest;
    const ratio = latest.ratio;

    // Status Logic
    let statusTitle = "Normal (Contango)";
    let statusDesc = "Investors are paying more for long-term protection than short-term. The market is structurally calm.";
    let statusColor = "#4ade80"; // Green
    let implicationText = "Vol Short strategies (Carry) are statistically favored.";

    if (ratio > 1.0) {
        statusTitle = "High Stress (Backwardation)";
        statusDesc = "Fear is high right now. The market is paying a premium for immediate protection.";
        statusColor = "#ef5350"; // Red
        implicationText = "Market is fragile. Cash preservation or contrarian long buying (if extreme) is favored.";
    }

    // Chart Data
    const dates = history.map(d => d.Date);
    const ratios = history.map(d => d.ratio);

    return (
        <div style={{ padding: '20px', backgroundColor: '#0b1220', color: '#e0e0e0', minHeight: '100vh' }}>

            {/* Header */}
            <div style={{ marginBottom: '20px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <TrendingUp size={24} color="#60a5fa" />
                    Volatility Term Structure
                </h1>
                <p style={{ color: '#94a3b8', fontSize: '14px' }}>
                    Comparing Spot VIX vs 3-Month VIX (VIX3M) to identify market stress.
                </p>
            </div>

            {/* Status Cards Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '20px', marginBottom: '25px' }}>

                {/* Current Status Card */}
                <div style={{
                    backgroundColor: '#162032',
                    padding: '20px',
                    borderRadius: '8px',
                    border: '1px solid #1e293b',
                    borderLeft: `4px solid ${statusColor}`
                }}>
                    <h3 style={{ margin: '0 0 10px 0', fontSize: '12px', textTransform: 'uppercase', color: '#94a3b8', letterSpacing: '1px' }}>Current Status</h3>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: statusColor, marginBottom: '8px' }}>
                        {statusTitle}
                    </div>
                    <p style={{ fontSize: '14px', color: '#cbd5e1', lineHeight: '1.5', margin: 0 }}>
                        {statusDesc}
                    </p>
                    <div style={{ marginTop: '15px', fontSize: '28px', fontWeight: 'bold', color: '#fff' }}>
                        {ratio.toFixed(2)} <span style={{ fontSize: '14px', color: '#64748b', fontWeight: 'normal' }}>Ratio</span>
                    </div>
                </div>

                {/* Implication Card */}
                <div style={{
                    backgroundColor: '#162032',
                    padding: '20px',
                    borderRadius: '8px',
                    border: '1px solid #1e293b'
                }}>
                    <h3 style={{ margin: '0 0 10px 0', fontSize: '12px', textTransform: 'uppercase', color: '#94a3b8', letterSpacing: '1px' }}>Trading Implication</h3>
                    <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                        <AlertCircle color="#facc15" size={20} style={{ marginTop: '2px' }} />
                        <p style={{ fontSize: '15px', color: '#e2e8f0', lineHeight: '1.5', margin: 0 }}>
                            {implicationText}
                        </p>
                    </div>

                    {/* Flash Premium Mini-Stat */}
                    <div style={{ marginTop: '20px', paddingTop: '15px', borderTop: '1px solid #334155' }}>
                        <div style={{ fontSize: '12px', color: '#94a3b8' }}>Flash Crash Premium (VIX1D - VIX)</div>
                        <div style={{ fontSize: '18px', fontWeight: 'bold', color: latest.flash_premium > 0 ? '#ef5350' : '#4ade80' }}>
                            {latest.flash_premium?.toFixed(2) ?? 'N/A'}
                        </div>
                    </div>
                </div>
            </div>

            {/* Primary Chart: VIX/VIX3M Ratio */}
            <div style={{ backgroundColor: '#162032', padding: '20px', borderRadius: '8px', border: '1px solid #1e293b', height: '400px', marginBottom: '20px' }}>
                <Plot
                    // ACTUAL DATA CONSTRUCTION
                    data={[
                        // Trace 0: The Curve itself (Min Part for Contango Lower Bound)
                        // We want to fill areas where Ratio < 1.
                        // Area is between Ratio and 1.0.
                        // Let's draw properties:
                        // 0. The Ratio Line (Actual Data) - Draw this LAST for visibility.

                        // SHADING STRATEGY:
                        // Green Area: Between Ratio and 1.0, where Ratio < 1.0.
                        // Red Area: Between Ratio and 1.0, where Ratio > 1.0.

                        // Green Fill Trace:
                        // y = min(ratio, 1.0).
                        // Fill to y=1.0?
                        // Plotly 'tozeroy' fills to 0.
                        // 'tonexty' fills to previous trace.

                        // Trace 0: y = min(ratio, 1.0). (The bottom of the green area)
                        {
                            x: dates,
                            y: ratios.map(r => Math.min(r, 1.0)),
                            type: 'scatter',
                            mode: 'lines',
                            line: { width: 0 },
                            showlegend: false,
                            hoverinfo: 'skip'
                        },
                        // Trace 1: y = 1.0 (The top of the green area / bottom of red area).
                        // Fill 'tonexty' -> Fills from Trace 0 up to 1.0 (GREEN AREA).
                        {
                            x: dates,
                            y: dates.map(() => 1.0),
                            type: 'scatter',
                            mode: 'lines',
                            line: { color: '#ef5350', width: 1, dash: 'dash' }, // This is also our visual threshold line
                            fill: 'tonexty',
                            fillcolor: 'rgba(74, 222, 128, 0.1)', // Green
                            name: 'Panic Threshold (1.0)',
                            hoverinfo: 'skip'
                        },
                        // Trace 2: y = max(ratio, 1.0). (The top of the red area).
                        // Fill 'tonexty' -> Fills from Trace 1 (y=1.0) up to this trace (RED AREA).
                        {
                            x: dates,
                            y: ratios.map(r => Math.max(r, 1.0)),
                            type: 'scatter',
                            mode: 'lines',
                            line: { width: 0 },
                            fill: 'tonexty',
                            fillcolor: 'rgba(239, 83, 80, 0.3)', // Red
                            showlegend: false,
                            hoverinfo: 'skip'
                        },

                        // Trace 3: The Actual Line Overlay
                        {
                            x: dates,
                            y: ratios,
                            type: 'scatter',
                            mode: 'lines',
                            name: 'VIX / VIX3M Ratio',
                            line: { color: '#ffffff', width: 2 } // White for contrast against dark bg
                        },
                        // Trace 4: SPY Overlay (Right Axis)
                        {
                            x: dates,
                            y: history.map(d => d.SPY),
                            type: 'scatter',
                            mode: 'lines',
                            name: 'SPY Price',
                            yaxis: 'y2',
                            line: { color: '#22d3ee', width: 1, dash: 'dot', opacity: 0.7 } // Cyan
                        }
                    ]}
                    layout={{
                        autosize: true,
                        title: `VIX / VIX3M Ratio | Data as of: ${data.data_as_of || latest.Date}`,
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        font: { color: '#94a3b8', family: 'Inter, sans-serif' },
                        xaxis: {
                            gridcolor: '#334155',
                            type: 'date',
                            matches: 'x' // Prepare for shared axis if we merged, but here it's separate
                        },
                        yaxis: {
                            gridcolor: '#334155',
                            title: 'Ratio (>1.0 = Fear)'
                        },
                        yaxis2: {
                            title: 'SPY Price',
                            overlaying: 'y',
                            side: 'right',
                            gridcolor: 'rgba(255,255,255,0.05)',
                            showgrid: false,
                            tickfont: { color: '#22d3ee' },
                            titlefont: { color: '#22d3ee' }
                        },
                        margin: { l: 50, r: 20, t: 40, b: 40 },
                        showlegend: true,
                        legend: { x: 0, y: 1 },
                        shapes: [
                            {
                                type: 'line',
                                xref: 'paper', x0: 0, x1: 1,
                                yref: 'y', y0: 1.15, y1: 1.15,
                                line: { color: '#991b1b', width: 1, dash: 'dot' }
                            }
                        ]
                    }}
                    style={{ width: '100%', height: '100%' }}
                    useResizeHandler={true}
                    config={{ responsive: true, displayModeBar: false }}
                />
            </div>

            {/* Secondary Chart: Underlying Indices */}
            <div style={{ backgroundColor: '#162032', padding: '20px', borderRadius: '8px', border: '1px solid #1e293b', height: '400px' }}>
                <Plot
                    data={[
                        {
                            x: dates,
                            y: history.map(d => d.VIX),
                            type: 'scatter',
                            mode: 'lines',
                            name: 'Spot VIX',
                            line: { color: '#60a5fa', width: 1.5 }
                        },
                        {
                            x: dates,
                            y: history.map(d => d.VIX3M),
                            type: 'scatter',
                            mode: 'lines',
                            name: 'VIX 3-Month',
                            line: { color: '#f59e0b', width: 1.5 }
                        },
                        // Conditionally add VIX1D (Check if any data point has it, or just latest)
                        ...(history.some(d => d.VIX1D) ? [{
                            x: dates,
                            y: history.map(d => d.VIX1D),
                            type: 'scatter',
                            mode: 'lines',
                            name: 'VIX 1-Day (Flash)',
                            line: { color: '#c084fc', width: 1, dash: 'dot' }
                        }] : []),

                        // Trace 3: SPY Overlay (Right Axis)
                        {
                            x: dates,
                            y: history.map(d => d.SPY),
                            type: 'scatter',
                            mode: 'lines',
                            name: 'SPY Price',
                            yaxis: 'y2',
                            line: { color: '#22d3ee', width: 1, dash: 'dot', opacity: 0.7 }
                        }
                    ]}
                    layout={{
                        autosize: true,
                        title: 'Underlying Volatility Indices',
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        font: { color: '#94a3b8', family: 'Inter, sans-serif' },
                        xaxis: {
                            gridcolor: '#334155',
                            type: 'date',
                            rangeslider: {
                                visible: false // Range slider on bottom one only? Or usage preference. Script had headers.
                            }
                        },
                        yaxis: {
                            gridcolor: '#334155',
                            title: 'Price'
                        },
                        yaxis2: {
                            title: 'SPY Price',
                            overlaying: 'y',
                            side: 'right',
                            gridcolor: 'rgba(255,255,255,0.05)',
                            showgrid: false,
                            tickfont: { color: '#22d3ee' },
                            titlefont: { color: '#22d3ee' }
                        },
                        margin: { l: 50, r: 20, t: 40, b: 40 },
                        showlegend: true,
                        legend: { x: 0, y: 1 }
                    }}
                    style={{ width: '100%', height: '100%' }}
                    useResizeHandler={true}
                    config={{ responsive: true, displayModeBar: false }}
                />
            </div>

        </div>
    );
};

export default VolatilityTermStructurePage;
