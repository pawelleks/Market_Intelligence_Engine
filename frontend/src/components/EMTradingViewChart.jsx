import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CrosshairMode, CandlestickSeries, HistogramSeries } from 'lightweight-charts';

// Error Boundary Component
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error("Chart Error:", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: '20px', color: '#f44336', backgroundColor: '#0e1525', border: '1px solid #203049', borderRadius: '8px' }}>
                    <h3>Chart Error</h3>
                    <p>{this.state.error && this.state.error.toString()}</p>
                </div>
            );
        }
        return this.props.children;
    }
}

const EMTradingViewChart = (props) => {
    return (
        <ErrorBoundary>
            <EMTradingViewChartImpl {...props} />
        </ErrorBoundary>
    );
};

const EMTradingViewChartImpl = ({ ticker, odteData, weeklyData, monthlyData }) => {
    const chartContainerRef = useRef();
    const chartRef = useRef(null);
    const candlestickSeriesRef = useRef(null);
    const volumeSeriesRef = useRef(null);

    const [interval, setInterval] = useState('1d');
    const [chartData, setChartData] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Fetch Data
    useEffect(() => {
        if (!ticker) return;

        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const response = await fetch(`/api/v1/market/candles/${ticker}?interval=${interval}&range=2y`);
                if (!response.ok) throw new Error('Failed to fetch candle data');
                const json = await response.json();
                setChartData(json);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [ticker, interval]);

    const [chartReady, setChartReady] = useState(false);

    // Initialize Chart & Series
    useEffect(() => {
        if (!chartContainerRef.current) return;

        // CLEANUP: Explicitly clear container to prevent duplicates
        chartContainerRef.current.innerHTML = '';

        // Create Chart
        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#0e1525' },
                textColor: '#d7e3f3',
            },
            grid: {
                vertLines: { color: '#203049' },
                horzLines: { color: '#203049' },
            },
            width: chartContainerRef.current.clientWidth,
            height: 500,
            crosshair: {
                mode: CrosshairMode.Normal,
            },
            timeScale: {
                borderColor: '#203049',
                timeVisible: true,
            },
            rightPriceScale: {
                borderColor: '#203049',
            },
        });

        chartRef.current = chart;

        // Create Series ONCE (v5 API)
        const candlestickSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#d7e3f3',
            downColor: '#0b1220',
            borderUpColor: '#d7e3f3',
            borderDownColor: '#9e9e9e',
            wickUpColor: '#d7e3f3',
            wickDownColor: '#9e9e9e',
        });
        candlestickSeriesRef.current = candlestickSeries;

        const volumeSeries = chart.addSeries(HistogramSeries, {
            priceFormat: { type: 'volume' },
            priceScaleId: '', // Overlay
            scaleMargins: { top: 0.8, bottom: 0 },
        });
        volumeSeriesRef.current = volumeSeries;

        setChartReady(true);

        // Resize Handler
        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        window.addEventListener('resize', handleResize);

        // Cleanup
        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
            chartRef.current = null;
            candlestickSeriesRef.current = null;
            volumeSeriesRef.current = null;
            setChartReady(false);
        };
    }, []);

    // ... (existing Update Data effect)

    // Update Data
    useEffect(() => {
        const chart = chartRef.current;
        const candlestickSeries = candlestickSeriesRef.current;
        const volumeSeries = volumeSeriesRef.current;

        if (!chart || !candlestickSeries || !volumeSeries || !chartData || chartData.length === 0) return;

        // Process Data
        const candleData = [];
        const volumeData = [];

        // Sort data by date to ensure strictly increasing time
        const sortedData = [...chartData].sort((a, b) => new Date(a.Date) - new Date(b.Date));

        sortedData.forEach(d => {
            let time;
            // Validate Date
            if (!d.Date) return;

            if (interval === '1d') {
                // Robustly extract YYYY-MM-DD from "YYYY-MM-DD..." or "YYYY-MM-DDT..."
                time = d.Date.substring(0, 10);
            } else {
                const dateObj = new Date(d.Date);
                if (isNaN(dateObj.getTime())) return; // Skip invalid dates
                time = dateObj.getTime() / 1000;
            }

            // Avoid duplicates
            if (candleData.length > 0 && candleData[candleData.length - 1].time === time) return;

            // Validate Prices
            if (d.Open == null || d.High == null || d.Low == null || d.Close == null) return;

            candleData.push({
                time: time,
                open: d.Open,
                high: d.High,
                low: d.Low,
                close: d.Close,
            });

            volumeData.push({
                time: time,
                value: d.Volume || 0,
                color: d.Close >= d.Open ? 'rgba(215, 227, 243, 0.5)' : 'rgba(158, 158, 158, 0.5)',
            });
        });

        if (candleData.length === 0) return;

        candlestickSeries.setData(candleData);
        volumeSeries.setData(volumeData);

    }, [chartData, interval, chartReady]); // Update when data changes OR chart becomes ready

    // Separate Effect for Price Lines
    useEffect(() => {
        const candlestickSeries = candlestickSeriesRef.current;
        if (!candlestickSeries || (!odteData && !weeklyData && !monthlyData)) return;

        const lines = [];

        if (odteData) {
            lines.push(candlestickSeries.createPriceLine({
                price: odteData.upper_range,
                color: '#f44336',
                lineWidth: 1,
                lineStyle: 2,
                axisLabelVisible: true,
                title: 'D High',
            }));
            lines.push(candlestickSeries.createPriceLine({
                price: odteData.lower_range,
                color: '#4caf50',
                lineWidth: 1,
                lineStyle: 2,
                axisLabelVisible: true,
                title: 'D Low',
            }));
        }

        if (weeklyData) {
            lines.push(candlestickSeries.createPriceLine({
                price: weeklyData.upper_range,
                color: '#f44336',
                lineWidth: 1, // Changed to 1px as requested
                lineStyle: 0,
                axisLabelVisible: true,
                title: 'W High',
            }));
            lines.push(candlestickSeries.createPriceLine({
                price: weeklyData.lower_range,
                color: '#4caf50',
                lineWidth: 1, // Changed to 1px as requested
                lineStyle: 0,
                axisLabelVisible: true,
                title: 'W Low',
            }));
        }

        if (monthlyData) {
            lines.push(candlestickSeries.createPriceLine({
                price: monthlyData.upper_range,
                color: '#f44336',
                lineWidth: 2, // 2px as requested
                lineStyle: 0,
                axisLabelVisible: true,
                title: 'M High',
            }));
            lines.push(candlestickSeries.createPriceLine({
                price: monthlyData.lower_range,
                color: '#4caf50',
                lineWidth: 2, // 2px as requested
                lineStyle: 0,
                axisLabelVisible: true,
                title: 'M Low',
            }));
        }

        return () => {
            if (candlestickSeries) {
                lines.forEach(line => {
                    try {
                        candlestickSeries.removePriceLine(line)
                    } catch (e) {
                        // ignore cleanup errors if series is gone
                    }
                });
            }
        };
    }, [odteData, weeklyData, monthlyData, chartReady]);

    // Separate Effect for Zoom
    useEffect(() => {
        const chart = chartRef.current;
        if (!chart || !chartData || chartData.length === 0) return;

        const totalBars = chartData.length;
        if (totalBars > 0) {
            const lastDate = new Date(chartData[chartData.length - 1].Date);
            const threeMonthsAgo = new Date(lastDate);
            threeMonthsAgo.setMonth(threeMonthsAgo.getMonth() - 3);

            let startIndex = chartData.findIndex(d => new Date(d.Date) >= threeMonthsAgo);
            if (startIndex === -1) startIndex = 0;

            chart.timeScale().setVisibleLogicalRange({
                from: startIndex,
                to: totalBars + 10, // Add right margin for better visibility
            });
        }
    }, [chartData]);

    const todayStr = new Date().toISOString().split('T')[0];

    return (
        <div style={{ marginTop: '30px', border: '1px solid #203049', borderRadius: '8px', padding: '15px', backgroundColor: '#0e1525' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                <h3 style={{ margin: 0, color: '#9ec4ff', fontSize: '1.2rem' }}>
                    {ticker} chart - expected moves - {todayStr}
                </h3>
                <div style={{ display: 'flex', gap: '10px' }}>
                    {['1h', '4h', '1d'].map(int => (
                        <button
                            key={int}
                            onClick={() => setInterval(int)}
                            style={{
                                padding: '5px 10px',
                                backgroundColor: interval === int ? '#2196f3' : '#203049',
                                color: '#fff',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '12px'
                            }}
                        >
                            {int.toUpperCase()}
                        </button>
                    ))}
                </div>
            </div>

            {loading && <p style={{ color: '#9e9e9e' }}>Loading chart data...</p>}
            {error && <p style={{ color: '#f44336' }}>Error: {error}</p>}

            <div ref={chartContainerRef} style={{ width: '100%', height: '500px' }} />
        </div>
    );
};

export default EMTradingViewChart;
