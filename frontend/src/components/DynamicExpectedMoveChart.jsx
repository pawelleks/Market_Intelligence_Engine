import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';

const DynamicExpectedMoveChart = ({ ticker, prevClose, emHigh, emLow, currentPrice, lastUpdated, label }) => {
    const [chartData, setChartData] = useState({ times: [], opens: [], highs: [], lows: [], closes: [] });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Helper: Generate Session Times (09:30 - 16:00 ET) in Local Time strings
    // baseDateStr: "YYYY-MM-DD" (NY Time)
    const generateSessionTimes = (baseDateStr) => {
        const times = [];
        // 09:30 (570 min) to 16:00 (960 min) = 390 min duration
        const startMin = 570;
        const endMin = 960;

        for (let t = startMin; t <= endMin; t += 5) {
            const h = Math.floor(t / 60);
            const mn = t % 60;

            // Construct a timestamp for this specific time on the specific date
            // We assume baseDateStr is valid.
            // We construct an ISO string with -05:00 or -04:00?
            // Safer: Parse baseDateStr separate, then set hours/minutes.
            // But initializing Date with specific TZ is hard in vanilla JS.

            // Heuristic: Construct simple string "YYYY-MM-DDTHH:mm:00" and let Browser interpret? 
            // NO, that interprets as Local.

            // We want "2025-12-16 09:30 ET" -> Local Time String.
            // Let's assume -05:00 (EST) for simplicity as it covers Winter (Dec).
            // ( Ideally we'd calculate offset dynamic, but for this specific request fixed fits).

            const dateStr = `${baseDateStr}T${h.toString().padStart(2, '0')}:${mn.toString().padStart(2, '0')}:00-05:00`;
            const dObj = new Date(dateStr);
            const timeStr = dObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
            times.push(timeStr);
        }
        return times;
    };

    // Fetch 5-minute candles
    useEffect(() => {
        if (!ticker) return;

        const fetchCandles = async () => {
            setLoading(true);
            try {
                // Request 2 days to ensure we catch 'today' even if just opened
                const res = await fetch(`/api/v1/market/candles/${ticker}?interval=5m&range=2d`);
                if (!res.ok) throw new Error("Failed to fetch candles");

                const json = await res.json();

                if (json.length > 0) {
                    // 1. Identify "Latest Session" Date from data
                    // We assume data is sorted.
                    const lastCandle = json[json.length - 1];
                    // lastCandle.Date format expected: "YYYY-MM-DD HH:MM:SS" or similar ISO
                    const lastDateStr = lastCandle.Date.split(' ')[0];

                    // 2. Filter for only this date
                    const sessionCandles = json.filter(d => d.Date.startsWith(lastDateStr));

                    // 3. Generate Full Session Times for this date
                    const sessionLabels = generateSessionTimes(lastDateStr);

                    // 4. Map Data to Session Times (Sparse Arrays)
                    const sparseOpens = new Array(sessionLabels.length).fill(null);
                    const sparseHighs = new Array(sessionLabels.length).fill(null);
                    const sparseLows = new Array(sessionLabels.length).fill(null);
                    const sparseCloses = new Array(sessionLabels.length).fill(null);

                    // Helper to format data date same way as labels
                    const formatDataDate = (dStr) => {
                        try {
                            // Assume dStr is "YYYY-MM-DD HH:MM:SS" (UTC or TZ-naive local from backend)
                            // If backend sends NY time string, new Date(s) implies local.
                            // Currently `yfinance` usually returns datetime strings.
                            const dObj = new Date(dStr);
                            if (isNaN(dObj.getTime())) return dStr.split(' ')[1]?.substring(0, 5);
                            return dObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
                        } catch {
                            return dStr.split(' ')[1]?.substring(0, 5) || dStr;
                        }
                    };

                    sessionCandles.forEach(d => {
                        const timeLabel = formatDataDate(d.Date);
                        const idx = sessionLabels.indexOf(timeLabel);
                        if (idx !== -1) {
                            sparseOpens[idx] = d.Open;
                            sparseHighs[idx] = d.High;
                            sparseLows[idx] = d.Low;
                            sparseCloses[idx] = d.Close;
                        }
                    });

                    setChartData({
                        times: sessionLabels,
                        opens: sparseOpens,
                        highs: sparseHighs,
                        lows: sparseLows,
                        closes: sparseCloses
                    });

                } else {
                    setChartData({ times: [], opens: [], highs: [], lows: [], closes: [] });
                }
            } catch (err) {
                console.error("Error fetching intraday candles:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchCandles();
    }, [ticker, lastUpdated]);

    if (loading) return <div style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#666' }}>Loading Chart...</div>;

    if (!error && chartData.times.length === 0) {
        return (
            <div style={{ height: '300px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#888' }}>
                <div style={{ fontSize: '1.2rem', marginBottom: '10px' }}>Waiting for Market Data</div>
                <div style={{ fontSize: '0.9rem', fontStyle: 'italic', opacity: 0.7 }}>
                    (Chart starts painting after session open)
                </div>
            </div>
        );
    }

    if (error) return <div style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#666' }}>Error: {error}</div>;

    // Filter non-nulls for Range Calc
    const validHighs = chartData.highs.filter(v => v !== null);
    const validLows = chartData.lows.filter(v => v !== null);

    const pMax = validHighs.length ? Math.max(...validHighs) : -Infinity;
    const pMin = validLows.length ? Math.min(...validLows) : Infinity;

    // Explicitly include EM bounds and Current Price in Y-Axis Range
    // Safety: fallback to reasonably small range if everything is missing
    const priceMax = Math.max(pMax, emHigh || -Infinity, currentPrice || -Infinity);
    const priceMin = Math.min(pMin, emLow || Infinity, currentPrice || Infinity);

    // Fallback logic
    const robustMax = isFinite(priceMax) ? priceMax : (prevClose ? prevClose * 1.01 : 100);
    const robustMin = isFinite(priceMin) ? priceMin : (prevClose ? prevClose * 0.99 : 99);

    const padding = (robustMax - robustMin) * 0.15;

    return (
        <div style={{ height: '300px', width: '100%', position: 'relative' }}>
            <Plot
                data={[
                    {
                        x: chartData.times,
                        open: chartData.opens,
                        high: chartData.highs,
                        low: chartData.lows,
                        close: chartData.closes,
                        type: 'candlestick',
                        increasing: { line: { color: '#ffffff' }, fillcolor: '#ffffff' },
                        decreasing: { line: { color: '#ffffff' }, fillcolor: 'rgba(0,0,0,0)' },
                        name: ticker
                    }
                ]}
                layout={{
                    autosize: true,
                    margin: { l: 90, r: 50, t: 30, b: 30 },
                    showlegend: false,
                    xaxis: {
                        type: 'category',
                        rangeslider: { visible: false },
                        showgrid: true,
                        gridcolor: '#203049',
                        tickfont: { color: '#888' },
                        nticks: 8,
                        tickangle: 0
                    },
                    yaxis: {
                        autorange: false,
                        range: [robustMin - padding, robustMax + padding],
                        showgrid: true,
                        gridcolor: '#203049',
                        tickfont: { color: '#888' },
                        side: 'right'
                    },
                    paper_bgcolor: 'transparent',
                    plot_bgcolor: 'transparent',
                    shapes: [
                        prevClose && {
                            type: 'line',
                            x0: 0, x1: 1, xref: 'paper',
                            y0: prevClose, y1: prevClose,
                            line: { color: '#888', width: 1, dash: 'dash' }
                        },
                        currentPrice && {
                            type: 'line',
                            x0: 0, x1: 1, xref: 'paper',
                            y0: currentPrice, y1: currentPrice,
                            line: { color: '#fff', width: 2, dash: 'dot' }
                        },
                        emHigh && {
                            type: 'rect',
                            x0: 0, x1: 1, xref: 'paper',
                            y0: emHigh, y1: robustMax + padding, // Extend to top of chart
                            fillcolor: '#4caf50',
                            opacity: 0.15,
                            line: { width: 0 }
                        },
                        emHigh && {
                            type: 'line',
                            x0: 0, x1: 1, xref: 'paper',
                            y0: emHigh, y1: emHigh,
                            line: { color: '#4caf50', width: 1 }
                        },
                        emLow && {
                            type: 'rect',
                            x0: 0, x1: 1, xref: 'paper',
                            y0: emLow, y1: robustMin - padding, // Extend to bottom of chart
                            fillcolor: '#f44336',
                            opacity: 0.15,
                            line: { width: 0 }
                        },
                        emLow && {
                            type: 'line',
                            x0: 0, x1: 1, xref: 'paper',
                            y0: emLow, y1: emLow,
                            line: { color: '#f44336', width: 1 }
                        }
                    ].filter(Boolean),
                    annotations: [
                        prevClose && {
                            x: 0, xref: 'paper', xanchor: 'right',
                            y: prevClose, yref: 'y',
                            text: `PC $${prevClose.toFixed(2)}`,
                            showarrow: false,
                            font: { color: '#888', size: 10 },
                            xshift: -5
                        },
                        emHigh && {
                            x: 0, xref: 'paper', xanchor: 'right',
                            y: emHigh, yref: 'y',
                            text: `EMH${label === 'WEEKLY' ? ' (W)' : ''} $${emHigh.toFixed(2)}`,
                            showarrow: false,
                            font: { color: '#4caf50', size: 10 },
                            xshift: -5
                        },
                        emLow && {
                            x: 0, xref: 'paper', xanchor: 'right',
                            y: emLow, yref: 'y',
                            text: `EML${label === 'WEEKLY' ? ' (W)' : ''} $${emLow.toFixed(2)}`,
                            showarrow: false,
                            font: { color: '#f44336', size: 10 },
                            xshift: -5
                        },
                        currentPrice && {
                            x: 1, xref: 'paper', xanchor: 'left',
                            y: currentPrice, yref: 'y',
                            text: `$${currentPrice.toFixed(2)}`,
                            showarrow: false,
                            bgcolor: '#fff',
                            borderpad: 2,
                            font: { color: '#000', size: 11, weight: 'bold' },
                            xshift: 5
                        }
                    ].filter(Boolean)
                }}
                useResizeHandler={true}
                style={{ width: '100%', height: '100%' }}
                config={{ displayModeBar: false, scrollZoom: false }}
            />
        </div>
    );
};

export default DynamicExpectedMoveChart;
