import React from 'react';
import Plot from 'react-plotly.js';
import { ChartExplainer } from './ChartExplainer';

interface ProbabilitySurface3DProps {
    data: any[]; // Expecting list of { dte, distribution: { strikes, pdf, T } }
    forwardPrice: number;
    ticker: string;
}

export const ProbabilitySurface3D: React.FC<ProbabilitySurface3DProps> = ({ data, forwardPrice, ticker }) => {
    // Prepare Data for Surface Plot
    // X: Price (Strikes)
    // Y: DTE (Days to Expiration)
    // Z: Probability Density

    // We need a grid. Since strikes might differ per expiration, we might need to interpolation or just use flattened scatter3d if surface is tricky.
    // However, Surface plots require a 2D grid (z[y][x]).

    // Simplification for robust rendering: use multiple Scatter3d lines (ribbons) or Mesh3d.
    // Or, construct a common union of strikes and interpolate Z values.

    // Let's try Mesh3d or just Scatter3d lines for each expiration for the "Vol Surface" look.
    // Actually, Plotly Surface requires a strict grid. 
    // Let's stick to "Ribbon" style using multiple Scatter3d traces if grid is hard, or Mesh3d.
    // Better yet: User asked for "3D Volatility Surface" style.

    // Let's build a grid.
    if (!data || data.length === 0) return null;

    const allStrikes = new Set<number>();
    data.forEach(d => d.distribution.strikes.forEach((k: number) => allStrikes.add(k)));
    const sortedStrikes = Array.from(allStrikes).sort((a, b) => a - b);

    // Filter strikes to relevant range (e.g. +/- 30% of Forward) to avoid huge empty grid
    // But for now, use all.

    const x_axis = sortedStrikes; // Strikes
    const y_axis = data.map(d => d.dte); // DTEs

    // Generate Interpolated Grid (DTE Axis) for Smoother Surface
    // We want 5-10 intermediate steps between each expiration
    const stepsPerGap = 5;
    const interpolatedY: number[] = [];
    const interpolatedZ: number[][] = [];

    // Helper: Linear Interpolation for Arrays
    const lerpArray = (arr1: number[], arr2: number[], t: number) => {
        return arr1.map((v, i) => v * (1 - t) + arr2[i] * t);
    };

    // First, build the raw Z matrix for known DTEs
    const rawZMatrix = y_axis.map((dte, yIdx) => {
        const d = data[yIdx];
        const pdfMap = new Map();
        d.distribution.strikes.forEach((k: number, i: number) => pdfMap.set(k, d.distribution.pdf[i]));
        return x_axis.map(k => pdfMap.get(k) || 0);
    });

    // Now Interpolate Y (DTE) and Z (PDF Rows)
    for (let i = 0; i < y_axis.length - 1; i++) {
        const dteStart = y_axis[i];
        const dteEnd = y_axis[i + 1];
        const zStart = rawZMatrix[i];
        const zEnd = rawZMatrix[i + 1];

        // Add Start
        interpolatedY.push(dteStart);
        interpolatedZ.push(zStart);

        // Add Intermediates
        for (let j = 1; j <= stepsPerGap; j++) {
            const t = j / (stepsPerGap + 1);
            const dteInterp = dteStart + (dteEnd - dteStart) * t;
            const zInterp = lerpArray(zStart, zEnd, t);

            interpolatedY.push(dteInterp);
            interpolatedZ.push(zInterp);
        }
    }
    // Add Final
    interpolatedY.push(y_axis[y_axis.length - 1]);
    interpolatedZ.push(rawZMatrix[rawZMatrix.length - 1]);


    // Use Interpolated Data
    const displayY = interpolatedY;
    const displayZ = interpolatedZ;

    // 4. SMART ZOOM (Tail Trimming)
    // Find absolute peak probability in the matrix
    let maxZ = 0;
    displayZ.forEach(row => {
        row.forEach(p => { if (p > maxZ) maxZ = p; });
    });
    const threshold = maxZ * 0.001; // 0.1% filter for full visibility

    let minStrikeIdx = 0;
    let maxStrikeIdx = x_axis.length - 1;

    // Find union of "active" indices where probability is significant
    const activeIndices = new Set<number>();
    displayZ.forEach(row => {
        row.forEach((p, idx) => {
            if (p > threshold) activeIndices.add(idx);
        });
    });

    if (activeIndices.size > 0) {
        minStrikeIdx = Math.min(...Array.from(activeIndices));
        maxStrikeIdx = Math.max(...Array.from(activeIndices));

        // Note: No padding for 3D surface to keep it sharp
    }

    // Slice data
    const slicedX = x_axis.slice(minStrikeIdx, maxStrikeIdx + 1);
    const slicedZ = displayZ.map(row => row.slice(minStrikeIdx, maxStrikeIdx + 1));

    return (
        <div className="w-full h-full bg-slate-900 rounded-lg border border-slate-800 flex flex-col p-4">
            {/* 1. INTERNAL TITLE */}
            <div className="mb-4">
                <h3 className="text-slate-100 text-lg font-bold">{ticker} Volatility Surface</h3>
            </div>

            {/* 2. THE CHART (Flex Grow to fill space) */}
            <div className="flex-grow min-h-[500px]">
                <Plot
                    data={[
                        {
                            type: 'surface',
                            x: slicedX, // Strikes (Filtered)
                            y: displayY, // DTE (Interpolated)
                            z: slicedZ, // PDF (Interpolated & Filtered)
                            colorscale: 'Viridis',
                            contours: {
                                z: {
                                    show: true,
                                    usecolormap: true,
                                    highlightcolor: "#42f5e6",
                                    project: { z: true }
                                }
                            },
                            showscale: false
                        }
                    ]}
                    layout={{
                        paper_bgcolor: '#0f172a', // Matches slate-900
                        plot_bgcolor: '#0f172a',
                        autosize: true,
                        scene: {
                            xaxis: { title: 'Strike ($)', color: '#94a3b8', autorange: 'reversed' },
                            yaxis: { title: 'DTE (Days)', color: '#94a3b8', autorange: 'reversed' },
                            zaxis: { title: 'Probability', color: '#94a3b8', autorange: true },
                            camera: {
                                eye: { x: 1.5, y: 1.5, z: 0.5 }
                            }
                        },
                        margin: { l: 0, r: 0, b: 0, t: 0 },
                    }}
                    config={{ responsive: true, displayModeBar: false }}
                    style={{ width: '100%', height: '100%' }}
                />
            </div>

            <ChartExplainer>
                <p className="pt-2"><strong className="text-slate-300">What this shows:</strong> A 3D map of how probability density evolves across prices (Strike) and time (DTE). Each "slice" along the DTE axis is a bell curve showing the market's implied probability distribution for that expiration.</p>
                <p><strong className="text-slate-300">Reading the peaks:</strong> <span className="text-emerald-400 font-semibold">Higher peaks</span> indicate where the market expects price to "pin" or settle at expiration. The peak of each slice is the most likely closing price for that date.</p>
                <p><strong className="text-slate-300">Reading the width:</strong> Wider bell curves (further DTE) mean more uncertainty. Narrower curves (near-term) mean the market is more confident about where price will land.</p>
                <p><strong className="text-slate-300">Flat plains:</strong> <span className="text-blue-400 font-semibold">Flat areas</span> near zero indicate price levels the market considers very unlikely. Flat elevated areas indicate high uncertainty with no clear directional consensus.</p>
                <p><strong className="text-slate-300">Interaction:</strong> Click and drag to rotate the surface. Scroll to zoom. This helps you see how the distribution shape changes across expirations.</p>
            </ChartExplainer>
        </div>
    );
};
