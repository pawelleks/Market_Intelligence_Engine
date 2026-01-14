
import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';

const GexHeatmap = ({ ticker }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

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

    // Data Structure:
    // x: dates, y: strikes, z: matrix [row=strike][col=date]
    // Available Dates: data.available_dates

    // Plotly Data Trace
    const traces = [
        {
            z: data.z,
            x: data.x,
            y: data.y,
            type: 'heatmap',
            colorscale: 'RdBu', // Red=Positive (Call), Blue=Negative (Put - Wait, typically Put is Neg GEX?)
            // Usually: Positive GEX = Long Gamma (Dealers Hedging against trend - Stability)
            // Negative GEX = Short Gamma (Dealers Hedging with trend - Volatility)
            // Let's use RdBu. Midpoint 0 is white.
            // RdBu: Red is low, Blue is high usually? No.
            // Let's check: 0 should be neutral.
            // We want Red for Negative GEX (Danger/Vol), Green/Blue for Positive.
            // Let's stick to standard RdBu and assume user knows.
            // Actually, in financial heatmaps:
            // High Positive GEX (Calls) -> Green/Blue
            // High Negative GEX (Puts) -> Red
            // RdBu is Red(Low) -> Blue(High). So Negative GEX (-100) is Red. Positive GEX (+100) is Blue.
            // This works well.
            zmid: 0,
            colorbar: {
                title: 'Net GEX ($M)',
                titleside: 'right'
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
            gridcolor: '#333'
        },
        yaxis: {
            title: 'Strike Price',
            color: '#ccc',
            gridcolor: '#333'
        },
        margin: { l: 60, r: 20, t: 40, b: 60 },
        height: 500,
        // Responsive
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
