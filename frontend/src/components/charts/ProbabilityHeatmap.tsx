import React from 'react';
import Plot from 'react-plotly.js';

interface ProbabilityHeatmapProps {
    data: any[];
}

export const ProbabilityHeatmap: React.FC<ProbabilityHeatmapProps> = ({ data }) => {
    if (!data || data.length === 0) return null;

    // Prepare grid
    const allStrikes = new Set<number>();
    data.forEach(d => d.distribution.strikes.forEach((k: number) => allStrikes.add(k)));
    const sortedStrikes = Array.from(allStrikes).sort((a, b) => a - b);

    // For heatmap: X = DTE, Y = Strike, Z = PDF
    // Usually standard to have Strike on Y.

    const x_dte = data.map(d => d.dte);
    const y_strikes = sortedStrikes;

    // Transpose Z for Heatmap (z[y][x]) -> z[strike_idx][date_idx]
    const z_matrix = y_strikes.map(k => {
        return x_dte.map((dte, dIdx) => {
            const d = data[dIdx];
            const idx = d.distribution.strikes.indexOf(k);
            return idx >= 0 ? d.distribution.pdf[idx] : 0;
        });
    });

    return (
        <div className="w-full h-[500px] bg-[#0e1525] rounded-xl border border-slate-700 p-4">
            <Plot
                data={[
                    {
                        type: 'heatmap',
                        x: x_dte.map(d => `+${d} Days`), // X-Axis Labels
                        y: y_strikes,
                        z: z_matrix,
                        colorscale: 'Jet', // 0 = Dark/Blue
                        zsmooth: 'best', // Interpolates between pixels
                        connectgaps: true,
                        hoverongaps: false,
                        hovertemplate: 'DTE: %{x}<br>Strike: $%{y}<br>Prob: %{z:.4f}<extra></extra>'
                    }
                ]}
                layout={{
                    title: { text: 'Probability Heatmap', font: { color: '#e2e8f0' } },
                    paper_bgcolor: '#0e1525',
                    plot_bgcolor: '#0e1525',
                    xaxis: {
                        title: 'Days to Expiration',
                        color: '#94a3b8',
                        tickfont: { color: '#94a3b8' }
                    },
                    yaxis: {
                        title: 'Strike Price',
                        color: '#94a3b8',
                        tickfont: { color: '#94a3b8' },
                        // Optional: Range logic
                    },
                    margin: { l: 50, r: 20, b: 50, t: 30 },
                    height: 450,
                }}
                config={{ responsive: true, displayModeBar: false }}
                style={{ width: '100%', height: '100%' }}
            />
        </div>
    );
};
