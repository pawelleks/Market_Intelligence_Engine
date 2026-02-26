import React, { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, ColorType, CrosshairMode, LineStyle, LineSeries, CandlestickSeries, HistogramSeries } from 'lightweight-charts';
import { CANDLE_COLORS } from '../constants/theme';

const STATE_COLORS: Record<string, string> = {
    "Accumulation": "#4caf50",
    "Distribution": "#f44336",
    "Capitulation": "#ff6d00",
    "Consolidation": "#3b82f6",
    "Neutral": "#94a3b8",
    "Insufficient Data": "#64748b",
    "Unavailable": "#64748b"
};

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"];

interface VolumeRegimeChartProps {
    initialTicker?: string;
    initialTimeframe?: string;
    onTickerChange?: (ticker: string) => void;
    onTimeframeChange?: (tf: string) => void;
}

export const VolumeRegimeChart: React.FC<VolumeRegimeChartProps> = ({
    initialTicker = "SPY",
    initialTimeframe = "5m",
    onTickerChange,
    onTimeframeChange
}) => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const [ticker, setTicker] = useState<string>(initialTicker);
    const [timeframe, setTimeframe] = useState<string>(initialTimeframe);
    const [inputValue, setInputValue] = useState<string>(initialTicker);
    const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
    const [loading, setLoading] = useState<boolean>(true);
    const [fetchError, setFetchError] = useState<string | null>(null);
    const [isStale, setIsStale] = useState<boolean>(false);

    // Regimes & Metrics logic
    const [currentRegime, setCurrentRegime] = useState<string>('Loading...');
    const [currentRatio, setCurrentRatio] = useState<string>('--');

    // Chart refs
    const chartRef = useRef<any>(null);
    const candleSeriesRef = useRef<any>(null);
    const smaSeriesRef = useRef<any>(null);
    const volumeSeriesRef = useRef<any>(null);

    const handleFormSubmit = (e?: React.FormEvent) => {
        if (e) e.preventDefault();
        const t = inputValue.trim().toUpperCase();
        if (t && t !== ticker) {
            setTicker(t);
            if (onTickerChange) onTickerChange(t);
        } else if (!t) {
            setInputValue(ticker); // Revert to current ticker if empty
        }
    };

    const handleTfClick = (tf: string) => {
        setTimeframe(tf);
        if (onTimeframeChange) onTimeframeChange(tf);
    };

    const fetchChartData = useCallback(async () => {
        if (!chartRef.current || !candleSeriesRef.current) return;
        setLoading(true);
        setFetchError(null);
        try {
            const res = await fetch(`/api/volume-regime/historical/${ticker}?timeframe=${timeframe}`);
            if (res.ok) {
                const json = await res.json();
                const data = json.data || [];

                if (data.length > 0) {
                    const candleData: any[] = [];
                    const smaData: any[] = [];
                    const volData: any[] = [];

                    data.forEach((d: any) => {
                        // Use time directly if available (unix timestamp) or string ISO
                        let cTime = d.time;
                        // Time string in LW chart for intraday needs to be unix integer, for daily needs to be YYYY-MM-DD string
                        if (timeframe === '1d') {
                            if (d.timestamp) {
                                cTime = d.timestamp.split('T')[0];
                            } else if (d.date) { // fallback
                                cTime = d.date.split('T')[0];
                            }
                        } else {
                            if (!cTime && d.timestamp) {
                                cTime = Math.floor(new Date(d.timestamp).getTime() / 1000);
                            }
                        }

                        candleData.push({
                            time: cTime,
                            open: d.open,
                            high: d.high,
                            low: d.low,
                            close: d.close
                        });

                        if (d.sma20 > 0 && d.sma20 !== null && !isNaN(d.sma20)) {
                            smaData.push({
                                time: cTime,
                                value: d.sma20
                            });
                        }

                        const color = (d.close >= d.open) ? CANDLE_COLORS.up.body : "rgba(100, 116, 139, 0.6)";
                        volData.push({
                            time: cTime,
                            value: d.volume,
                            color: color
                        });
                    });

                    candleSeriesRef.current.setData(candleData);
                    smaSeriesRef.current.setData(smaData);
                    volumeSeriesRef.current.setData(volData);

                    // Update Regimes state badge
                    const last = data[data.length - 1];
                    setCurrentRegime(last.state || "Unknown");
                    if (last.ud_vol_ratio !== undefined) {
                        setCurrentRatio(parseFloat(last.ud_vol_ratio).toFixed(2));
                    }
                    setIsStale(false);

                    chartRef.current.timeScale().fitContent();
                } else {
                    // Empty data
                    candleSeriesRef.current.setData([]);
                    smaSeriesRef.current.setData([]);
                    volumeSeriesRef.current.setData([]);
                    setCurrentRegime("Insufficient Data");
                    setCurrentRatio("--");
                    setIsStale(false);
                }
            } else {
                setFetchError("Failed to fetch volume regime history.");
                setIsStale(true);
            }
        } catch (err) {
            console.error(err);
            setFetchError("Network error occurred.");
            setIsStale(true);
        } finally {
            setLoading(false);
        }
    }, [ticker, timeframe]);

    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#0b1220' },
                textColor: '#94a3b8',
                fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Arial, sans-serif",
            },
            grid: {
                vertLines: { color: '#1e3a5f', style: LineStyle.SparseDotted },
                horzLines: { color: '#1e3a5f', style: LineStyle.SparseDotted },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
            },
            timeScale: {
                timeVisible: timeframe !== '1d',
                borderColor: '#1e3a5f',
                rightOffset: 5,
            },
            rightPriceScale: {
                borderColor: '#1e3a5f',
                autoScale: true,
                scaleMargins: {
                    top: 0.1,
                    bottom: 0.25, // provide vertical space for bottom volume overlap
                },
            },
        });

        const candleSeries = chart.addSeries(CandlestickSeries, {
            upColor: CANDLE_COLORS.up.body,
            wickUpColor: CANDLE_COLORS.up.wick,
            borderUpColor: CANDLE_COLORS.up.border,
            borderVisible: true,
            downColor: CANDLE_COLORS.down.body,
            wickDownColor: CANDLE_COLORS.down.wick,
            borderDownColor: CANDLE_COLORS.down.border,
        });

        const smaSeries = chart.addSeries(LineSeries, {
            color: '#f59e0b',
            lineWidth: 2,
            crosshairMarkerVisible: false,
        });

        const volumeSeries = chart.addSeries(HistogramSeries, {
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: '', // set as overlay by removing price scale id
        });

        // Scale overlay bounds for volume
        volumeSeries.priceScale().applyOptions({
            scaleMargins: {
                top: 0.8, // highest point of volume will be at 80% from top
                bottom: 0,
            },
        });

        chartRef.current = chart;
        candleSeriesRef.current = candleSeries;
        smaSeriesRef.current = smaSeries;
        volumeSeriesRef.current = volumeSeries;

        const resizeObserver = new ResizeObserver(entries => {
            if (entries.length === 0 || !entries[0].contentRect) return;
            const { width, height } = entries[0].contentRect;
            if (width > 0 && height > 0) chart.applyOptions({ width, height });
        });
        resizeObserver.observe(chartContainerRef.current);

        return () => {
            resizeObserver.disconnect();
            chart.remove();
            chartRef.current = null;
        };
    }, []); // Init chart only once

    // Fetch data when ticker or timeframe changes
    useEffect(() => {
        fetchChartData();
    }, [ticker, timeframe, fetchChartData]);

    // Auto-refresh interval (5 min — matches 5m candle cadence, avoids Theta overload)
    useEffect(() => {
        if (!autoRefresh) return;
        const iv = setInterval(() => {
            fetchChartData();
        }, 300000);
        return () => clearInterval(iv);
    }, [autoRefresh, fetchChartData]);

    const badgeColor = STATE_COLORS[currentRegime] || "#94a3b8";

    return (
        <div className="flex flex-col bg-[#0b1220] border border-[#1e3a5f] rounded-lg shadow-lg overflow-hidden w-full">
            {/* Toolbar */}
            <div className="flex flex-col md:flex-row justify-between items-center p-3 border-b border-[#1e3a5f] gap-3">
                <form onSubmit={handleFormSubmit} className="flex items-center gap-2">
                    <input
                        type="text"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onBlur={handleFormSubmit}
                        className="bg-[#1b2a40] border border-[#1e3a5f] text-[#d7e3f3] text-sm rounded px-3 py-1.5 w-24 outline-none focus:border-[#3b82f6] transition-colors uppercase font-bold text-center"
                        placeholder="TICKER"
                    />
                </form>

                <div className="flex bg-[#1b2a40] rounded p-1 border border-[#1e3a5f] gap-1">
                    {TIMEFRAMES.map((tf) => (
                        <button
                            key={tf}
                            onClick={() => handleTfClick(tf)}
                            className={`px-3 py-1 text-xs font-semibold rounded transition-colors ${timeframe === tf
                                ? 'bg-[#3b82f6] text-white shadow-sm'
                                : 'text-[#94a3b8] hover:text-[#d7e3f3] hover:bg-slate-700/50'
                                }`}
                        >
                            {tf}
                        </button>
                    ))}
                </div>

                <div className="flex items-center gap-2 text-xs text-[#94a3b8]">
                    <span className="font-medium tracking-wide border-r border-[#1e3a5f] pr-2 mr-1">SMA20: <span className="text-[#f59e0b]">■</span></span>
                    <span>Auto-Refresh</span>
                    <button
                        onClick={() => setAutoRefresh(!autoRefresh)}
                        className={`w-8 h-4 rounded-full transition-colors relative ${autoRefresh ? 'bg-[#3b82f6]' : 'bg-[#1e3a5f]'}`}
                    >
                        <span className={`absolute top-0.5 bottom-0.5 left-0.5 w-3 h-3 bg-white rounded-full transition-transform ${autoRefresh ? 'translate-x-4' : 'translate-x-0'}`}></span>
                    </button>
                </div>
            </div>

            {/* Chart Container */}
            <div className="relative w-full h-[500px]">
                {/* Badge Overlay */}
                <div className="absolute top-4 right-4 z-10 bg-[#0e1525]/90 backdrop-blur-sm border border-[#1e3a5f] p-3 rounded-md shadow-md min-w-[140px] flex flex-col items-end">
                    <div className="text-[10px] text-[#94a3b8] uppercase tracking-wider mb-1 flex items-center gap-1.5">
                        {isStale && <span className="bg-amber-500/20 text-amber-500 font-bold px-1.5 py-0.5 rounded border border-amber-500/30">STALE</span>}
                        Volume Regime
                    </div>
                    <div className="text-xl font-bold tracking-tight" style={{ color: badgeColor }}>
                        {loading && currentRegime === 'Loading...' ? 'Updating...' : currentRegime}
                    </div>
                    {(currentRatio !== '--') && (
                        <div className="text-xs text-[#d7e3f3] mt-1 font-mono">
                            <span className="text-[#94a3b8]">U/D Ratio:</span> {currentRatio}
                        </div>
                    )}
                </div>

                {/* Loading Spinner */}
                {loading && (
                    <div className="absolute inset-0 z-20 bg-[#0b1220]/50 backdrop-blur-[2px] flex items-center justify-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3b82f6]"></div>
                    </div>
                )}

                {/* Error Banner */}
                {fetchError && !loading && (
                    <div className="absolute top-4 left-4 right-[180px] z-20 bg-red-900/80 backdrop-blur-sm border border-red-500 p-3 rounded-md shadow-lg flex items-center text-sm text-red-100">
                        <span className="mr-2">⚠️</span>
                        {fetchError}
                    </div>
                )}

                {/* Chart DOM node */}
                <div ref={chartContainerRef} className="w-full h-full" />
            </div>
        </div>
    );
};

export default VolumeRegimeChart;
