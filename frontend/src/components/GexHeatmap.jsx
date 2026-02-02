
import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';

const GexHeatmap = ({ ticker }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [visibleRange, setVisibleRange] = useState(null);

    // Helper: Format GEX Value
    const formatGexValue = (val) => {
        if (!val && val !== 0) return 'N/A';
        const absVal = Math.abs(val);
        if (absVal >= 1e9) return `$${(val / 1e9).toFixed(2)}B`;
        if (absVal >= 1e6) return `$${(val / 1e6).toFixed(1)}M`;
        if (absVal >= 1e3) return `$${(val / 1e3).toFixed(0)}K`;
        return val.toFixed(0);
    };

    // Helper: Calculate robust range (1st and 99th percentile) to ignore outliers
    const calculateRobustRange = (matrix) => {
        const flat = matrix.flat().filter(v => v !== null && v !== undefined).sort((a, b) => a - b);
        if (flat.length === 0) return [-1e9, 1e9]; // Fallback

        const p1 = flat[Math.floor(flat.length * 0.01)];
        const p99 = flat[Math.floor(flat.length * 0.99)];

        // Ensure symmetry around zero for GEX (Red/Blue)
        const limit = Math.max(Math.abs(p1), Math.abs(p99));
        return [-limit, limit];
    };

    // Fetch Heatmap Data
    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                const response = await fetch(`/api/v1/gex/history/heatmap/${ticker}`);
                if (!response.ok) {
                    throw new Error('Failed to fetch historical GEX data');
                }
                const result = await response.json();

                // Pre-calculate Hover Text Matrix
                if (result.z) {
                    result.text = result.z.map(row => row.map(val => formatGexValue(val)));

                    // Calculate Robust Z-Limits
                    const [zMin, zMax] = calculateRobustRange(result.z);
                    result.zMin = zMin;
                    result.zMax = zMax;
                }

                setData(result);

                // Calculate visible range based on PROXY SPOT from latest data
                // User Request: Range should be -10% to +10% from current strike.
                let proxySpot = 0;
                let totalWeight = 0;
                const lastColIndex = result.x.length - 1;

                if (result.z && result.y && result.x.length > 0) {
                    result.z.forEach((row, rowIndex) => {
                        const strike = result.y[rowIndex];
                        const val = row[lastColIndex]; // Value on latest date
                        const weight = Math.abs(val);

                        proxySpot += strike * weight;
                        totalWeight += weight;
                    });
                }

                if (totalWeight > 0) {
                    proxySpot = proxySpot / totalWeight;
                    setVisibleRange([proxySpot * 0.9, proxySpot * 1.1]);
                } else {
                    // Fallback to min/max if calculation fails
                    if (result.y && result.y.length > 0) {
                        setVisibleRange([result.y[0], result.y[result.y.length - 1]]);
                    }
                }

            } catch (err) {
                console.error(err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        if (ticker) {
            fetchData();
        }
    }, [ticker]);

    if (loading) return <div className="text-gray-400 p-4">Loading GEX Heatmap...</div>;
    if (error) return <div className="text-red-400 p-4">Error loading heatmap: {error}</div>;
    if (!data) return null;

    // Plotly Data Trace
    const traces = [
        {
            z: data.z,
            x: data.x,
            y: data.y,
            text: data.text, // Custom formatted text
            type: 'heatmap',
            colorscale: [
                [0, '#FF4136'],    // Negative (Red)
                [0.5, '#111111'],  // Zero (Very Dark Grey - High Contrast against Blue/Red)
                [1, '#00B5F5']     // Positive (Bright Cyan/Blue)
            ],
            zmid: 0,
            zmin: data.zMin, // Robust Scale Min
            zmax: data.zMax, // Robust Scale Max
            colorbar: {
                title: 'Net GEX',
                titleside: 'right',
                tickfont: { color: '#ccc' },
                titlefont: { color: '#ccc' }
            },
            hovertemplate: 'Date: %{x}<br>Strike: %{y}<br>GEX: %{text}<extra></extra>'
        }
    ];

    const layout = {
        title: {
            text: `${ticker} Historical GEX Heatmap`,
            font: { color: '#fff' }
        },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        xaxis: {
            title: 'Date',
            color: '#ccc',
            gridcolor: '#333',
            tickformat: '%b %d', // Short date format
            nticks: 10 // Reduce label density
        },
        yaxis: {
            title: 'Strike Price',
            color: '#ccc',
            gridcolor: '#333',
            range: visibleRange // Dynamic range
        },
        margin: { l: 60, r: 20, t: 40, b: 60 },
        height: 500,
        autosize: true
    };

    // Status Info
    const dateCount = data.available_dates ? data.available_dates.length : 0;
    const historyText = `${dateCount} days of history available`;

    return (
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 mt-4 shadow-lg">
            <div className="flex justify-between items-center mb-2 px-2">
                <h2 className="text-lg font-bold text-gray-100">GEX Surface Evolution</h2>
                <span className="text-xs text-blue-400 border border-blue-900 bg-blue-900/20 px-2 py-1 rounded">
                    {historyText}
                </span>
            </div>

            <div className="w-full h-[500px]">
                <Plot
                    data={traces}
                    layout={layout}
                    config={{ responsive: true, displayModeBar: false }}
                    style={{ width: '100%', height: '100%' }}
                />
            </div>

            <div className="mt-2 text-xs text-gray-500 italic">
                * Heatmap shows Net Gamma Exposure across strikes over time.
                Red indicates Negative Gamma (Volatility Risk), Blue indicates Positive Gamma (Stability).
            </div>
        </div>
    );
};

export default GexHeatmap;
