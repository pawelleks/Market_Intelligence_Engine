import React, { useState, useEffect } from 'react';
import { createChart, CandlestickSeries, HistogramSeries } from 'lightweight-charts';
import ReactMarkdown from 'react-markdown';

const GAFAnalysisPage = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // --- Main Data Fetching ---
    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await fetch('/api/v1/gaf/latest');
                if (!res.ok) {
                    if (res.status === 404) throw new Error("No GAF prediction found. Please run backend training/build.");
                    throw new Error("Failed to fetch GAF data");
                }
                const json = await res.json();
                setData(json);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    // --- Backtest Data Fetching ---
    const [backtest, setBacktest] = useState(null);

    useEffect(() => {
        fetch('/api/v1/gaf/backtest')
            .then(r => r.json())
            .then(data => {
                if (data.status === 'ok') {
                    setBacktest(data);
                }
            })
            .catch(err => console.error("Backtest fetch error:", err));
    }, []);

    const pageStyle = {
        padding: '30px',
        backgroundColor: '#0d1117',
        minHeight: '100vh',
        color: '#c9d1d9',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif'
    };

    if (loading) return <div style={pageStyle}>Loading GAF Analysis...</div>;
    if (error) return (
        <div style={pageStyle}>
            <div style={{ padding: '20px', backgroundColor: '#3d1619', color: '#fa7970', borderRadius: '6px', border: '1px solid #ff4444' }}>
                {error}
                <br /><small>Hint: Did you run <code>update-gaf</code> in the backend?</small>
            </div>
        </div>
    );

    // Helper for human-friendly explanation
    const getBacktestExplanation = (acc) => {
        if (!acc) return "No data available.";
        if (acc > 55) return "✅ **Promising Edge**: The model shows consistent predictive power above random chance.";
        if (acc >= 50) return "⚠️ **Slight Edge**: The model performs slightly better than limit (50%), but requires confirmation from other signals.";
        return "❌ **No Advantage**: The model currently does not outperform random chance.";
    };

    return (
        <div style={{ padding: '20px', color: '#c9d1d9', fontFamily: 'Inter, sans-serif' }}>
            <h1 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '20px' }}>GAF Neural Net Analysis</h1>

            {/* Single Column Vertical Layout */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

                {/* 1. TOP ROW: Prediction | GAF | Grad-CAM */}
                {data ? (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>

                        {/* A. Prediction Card */}
                        <div style={{ background: '#161b22', padding: '20px', borderRadius: '8px', border: '1px solid #30363d', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                            <h3 style={{ margin: '0 0 10px 0', color: '#8b949e', fontSize: '14px' }}>Latest Prediction (Daily)</h3>
                            <div style={{ fontSize: '42px', fontWeight: 'bold', color: data.prediction === 'UP' ? '#26a641' : '#ff4444', marginBottom: '5px' }}>
                                {data.prediction}
                            </div>
                            <div style={{ color: '#c9d1d9', fontSize: '16px' }}>Confidence: {(data.probability * 100).toFixed(1)}%</div>
                            <div style={{ fontSize: '12px', color: '#484f58', marginTop: '10px' }}>Raw Score: {data.raw_score.toFixed(4)}</div>
                        </div>

                        {/* B. GAF Image (Input) */}
                        <div style={{ background: '#161b22', padding: '20px', borderRadius: '8px', border: '1px solid #30363d', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                            <h3 style={{ margin: '0 0 15px 0', color: '#58a6ff', fontSize: '14px', alignSelf: 'flex-start' }}>Input Pattern (GAF)</h3>
                            {data.image_base64 ? (
                                <img
                                    src={data.image_base64}
                                    alt="GAF Input"
                                    style={{ width: '100%', height: '180px', borderRadius: '6px', border: '1px solid #30363d', objectFit: 'contain', backgroundColor: '#000' }}
                                />
                            ) : <div style={{ color: '#484f58', fontSize: '14px' }}>No Image</div>}
                        </div>

                        {/* C. Grad-CAM Image (Attention) */}
                        <div style={{ background: '#161b22', padding: '20px', borderRadius: '8px', border: '1px solid #30363d', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                            <h3 style={{ margin: '0 0 15px 0', color: '#e3be29', fontSize: '14px', alignSelf: 'flex-start' }}>AI Focus (Grad-CAM)</h3>
                            {data.gradcam_image_base64 ? (
                                <img
                                    src={data.gradcam_image_base64}
                                    alt="Grad-CAM Heatmap"
                                    style={{ width: '100%', height: '180px', borderRadius: '6px', border: '1px solid #30363d', objectFit: 'contain', backgroundColor: '#000' }}
                                />
                            ) : <div style={{ color: '#484f58', fontSize: '14px' }}>No Heatmap</div>}
                        </div>
                    </div>
                ) : (
                    <div>Loading real-time analysis...</div>
                )}

                {/* 2. MIDDLE ROW: Attention Chart */}
                <div style={{ background: '#161b22', borderRadius: '8px', border: '1px solid #30363d', padding: '20px' }}>
                    <h3 style={{ margin: '0 0 20px 0', color: '#8b949e', fontSize: '14px' }}>Attention Analysis Chart</h3>
                    <AttentionChart data={data ? data.ohlc_data : []} />
                </div>

                {/* 3. BOTTOM ROW: Backtest Results */}
                <div style={{ background: '#161b22', padding: '20px', borderRadius: '8px', border: '1px solid #30363d' }}>
                    <h3 style={{ margin: '0 0 15px 0', color: '#e6edf3', fontSize: '16px', fontWeight: '600' }}>Backtest Performance (5 Years)</h3>
                    {backtest ? (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', alignItems: 'center' }}>
                            <div>
                                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '5px' }}>Accuracy</div>
                                <div style={{ color: '#e6edf3', fontSize: '24px', fontWeight: 'bold' }}>{backtest.accuracy}%</div>
                            </div>
                            <div>
                                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '5px' }}>Precision</div>
                                <div style={{ color: '#e6edf3', fontSize: '24px' }}>{backtest.precision}</div>
                            </div>
                            <div>
                                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '5px' }}>Recall</div>
                                <div style={{ color: '#e6edf3', fontSize: '24px' }}>{backtest.recall}</div>
                            </div>
                            <div style={{ fontSize: '14px', color: '#c9d1d9', lineHeight: '1.4', background: '#21262d', padding: '15px', borderRadius: '6px' }}>
                                <ReactMarkdown>{getBacktestExplanation(backtest.accuracy)}</ReactMarkdown>
                            </div>
                        </div>
                    ) : (
                        <div style={{ color: '#8b949e', fontSize: '13px' }}>Run "backtest-gaf" CLI to generate data.</div>
                    )}
                </div>

            </div>
        </div>
    );
};

// --- Sub-Component for Chart ---
function AttentionChart({ data }) {
    const chartContainerRef = React.useRef();
    const chartRef = React.useRef();

    useEffect(() => {
        if (!chartContainerRef.current) return;
        if (!data || data.length === 0) return;

        let chart;

        try {
            console.log("Initializing Chart with data:", data);

            // Safety: Ensure container has dimensions
            if (chartContainerRef.current.clientWidth === 0) {
                console.warn("Chart container has 0 width. Skipping render.");
                return;
            }

            chart = createChart(chartContainerRef.current, {
                width: chartContainerRef.current.clientWidth,
                height: 450,
                layout: {
                    background: { type: 'solid', color: '#0d1117' },
                    textColor: '#c9d1d9',
                },
                grid: {
                    vertLines: { color: '#30363d' },
                    horzLines: { color: '#30363d' },
                },
                timeScale: {
                    borderColor: '#30363d',
                },
                rightPriceScale: {
                    borderColor: '#30363d',
                    // Main Pane: Top 70%
                    scaleMargins: {
                        top: 0.1,
                        bottom: 0.3,
                    },
                },
            });
            chartRef.current = chart;

            // 1. Candlestick Series (Main Pane)
            const candleSeries = chart.addSeries(CandlestickSeries, {
                upColor: '#d7e3f3',
                downColor: '#0b1220',
                borderUpColor: '#d7e3f3',
                borderDownColor: '#9e9e9e',
                wickUpColor: '#d7e3f3',
                wickDownColor: '#9e9e9e',
                // Uses 'right' price scale by default
            });

            // 2. Volume Series (Bottom Pane)
            const volumeSeries = chart.addSeries(HistogramSeries, {
                priceFormat: { type: 'volume' },
                priceScaleId: 'volume_scale', // Custom scale
            });

            // Configure Volume Scale to sit at the bottom
            chart.priceScale('volume_scale').applyOptions({
                scaleMargins: {
                    top: 0.75, // Start at 75% down
                    bottom: 0,
                },
            });

            // Format data
            const candleData = [];
            const volumeData = [];

            data.forEach(item => {
                const isHighAttention = item.attention > 0.6;

                // Candle Data
                const point = {
                    time: item.time,
                    open: item.open,
                    high: item.high,
                    low: item.low,
                    close: item.close,
                };

                if (isHighAttention) {
                    point.color = '#a371f7';       // Purple
                    point.borderColor = '#a371f7';
                    point.wickColor = '#a371f7';
                }
                candleData.push(point);

                // Volume Data
                // Color Logic: Light for UP, Darker for DOWN
                const isUp = item.close >= item.open;
                volumeData.push({
                    time: item.time,
                    value: item.volume || 0,
                    color: isUp ? 'rgba(215, 227, 243, 0.5)' : 'rgba(158, 158, 158, 0.5)',
                });
            });

            console.log("Setting chart data:", candleData);
            candleSeries.setData(candleData);
            volumeSeries.setData(volumeData);

            chart.timeScale().fitContent();

        } catch (err) {
            console.error("CRITICAL CHART ERROR:", err);
            if (chart) chart.remove();
        }

        const handleResize = () => {
            if (chartContainerRef.current && chart) {
                chart.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            if (chart) chart.remove();
        };
    }, [data]);

    return <div ref={chartContainerRef} style={{ width: '100%', height: '450px' }} />;
};

export default GAFAnalysisPage;
