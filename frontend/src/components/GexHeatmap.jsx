
import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';

const GexHeatmap = ({ ticker }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [visibleRange, setVisibleRange] = useState(null);

    // Fetch Heatmap Data
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
            type: 'heatmap',
            colorscale: [
                [0, '#FF4136'],    // Negative (Red)
                [0.5, '#111111'],  // Zero (Very Dark Grey - High Contrast against Blue/Red)
                [1, '#00B5F5']     // Positive (Bright Cyan/Blue)
            ],
            zmid: 0,
            colorbar: {
                title: 'Net GEX ($M)',
                titleside: 'right',
                tickfont: { color: '#ccc' },
                titlefont: { color: '#ccc' }
            },
            hovertemplate: 'Date: %{x}<br>Strike: %{y}<br>GEX: %{z:.2f} M<extra></extra>'
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
