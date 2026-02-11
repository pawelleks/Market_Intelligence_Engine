import React, { useMemo } from 'react';
import Plot from 'react-plotly.js';

interface ProbabilityAboveHeatmapProps {
    surfaceData: any; // { dte_axis, strike_axis, prob_above_surface }
    currentPrice: number;
}

export const ProbabilityAboveHeatmap: React.FC<ProbabilityAboveHeatmapProps> = ({ surfaceData, currentPrice }) => {

    // Check if surface data is available
    const isValid = surfaceData && surfaceData.dte_axis && surfaceData.prob_above_surface;

    return (
        <div className="w-full h-[600px] bg-[#0e1525] rounded-xl border border-slate-700 p-4">
            {isValid ? (
                <Plot
                    data={[
                        {
                            type: 'contour',
                            x: surfaceData.dte_axis,
                            y: surfaceData.strike_axis,
                            z: surfaceData.prob_above_surface, // Row=Strike, Col=DTE ?? Check backend.
                            // Backend returns [Strike][DTE] usually for Heatmap in Plotly if x is DTE
                            // Let's assume standard Plotly shape.
                            transpose: false, // Verify orientation
                            colorscale: [
                                [0, '#7f1d1d'],   // 0% -> Dark Red
                                [0.25, '#ef4444'], // 25% -> Red
                                [0.5, '#fef08a'],  // 50% -> Yellow
                                [0.75, '#3b82f6'], // 75% -> Blue
                                [1, '#1e3a8a']    // 100% -> Dark Blue
                            ],
                            autocontour: false,
                            contours: {
                                start: 0.1,
                                end: 0.9,
                                size: 0.1, // Steps of 10%
                                coloring: 'fill',
                                showlabels: true,
                                labelfont: {
                                    size: 12,
                                    color: 'white',
                                }
                            },
                            colorbar: {
                                title: 'Prob > X',
                                titleside: 'right',
                                titlefont: { size: 14, color: '#e2e8f0' },
                                tickfont: { color: '#94a3b8' }
                            }
                        },
                        // Reference Line: Current Spot
                        {
                            type: 'scatter',
                            mode: 'lines',
                            x: [0, 45],
                            y: [currentPrice, currentPrice],
                            line: {
                                color: 'white',
                                width: 2,
                                dash: 'dash'
                            },
                            name: 'Current Spot',
                            showlegend: true
                        }
                    ]}
                    layout={{
                        title: { text: 'Probability of Price > Strike (Backend Interpolated)', font: { color: '#e2e8f0' } },
                        paper_bgcolor: '#0e1525',
                        plot_bgcolor: '#0e1525',
                        xaxis: {
                            title: 'Days to Expiration',
                            color: '#94a3b8',
                            gridcolor: '#1e293b',
                            range: [0, 45]
                        },
                        yaxis: {
                            title: 'Strike Price',
                            color: '#94a3b8',
                            gridcolor: '#1e293b'
                        },
                        margin: { l: 60, r: 20, b: 50, t: 40 },
                        height: 550,
                        showlegend: true,
                        legend: { font: { color: '#cbd5e1' }, x: 0, y: 1 }
                    }}
                    config={{ responsive: true, displayModeBar: false }}
                    style={{ width: '100%', height: '100%' }}
                />
            ) : (
                <div className="flex items-center justify-center h-full text-slate-500">
                    No Surface Data Available
                </div>
            )}
        </div>
    );
};
