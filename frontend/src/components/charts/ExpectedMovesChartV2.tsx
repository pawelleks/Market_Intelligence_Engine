import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CrosshairMode, LineStyle, LineSeries, CandlestickSeries } from 'lightweight-charts';
import { COLORS, EM_COLORS, CANDLE_COLORS } from '../../constants/theme';
import { getMarketStatus, fetchMarketStatus, type MarketStatus } from '../../utils/marketHours';

type CalcMode = 'sigma' | 'breakeven';

interface ExpectedMovesChartV2Props {
    ticker: string;
    calcMode?: CalcMode;
}

interface RangeLevel {
    high: number;
    low: number;
    plus_minus: number;
    breakeven_move?: number;
    sigma_move?: number;
    upper_breakeven?: number;
    lower_breakeven?: number;
    upper_sigma?: number;
    lower_sigma?: number;
    data_quality?: string;
}

interface ExpectedMovesData {
    ticker: string;
    current_price: number; // This is the Static EOD Reference
    data_date: string;
    "0dte_range": RangeLevel | null;
    "weekly_range": RangeLevel | null;
    "monthly_range": RangeLevel | null;
}

// Static EM data shape from /api/v1/expected_moves/static/latest
interface StaticEmTenor {
    breakeven_move: number;
    sigma_move: number;
    upper_breakeven: number;
    lower_breakeven: number;
    upper_sigma: number;
    lower_sigma: number;
    date: string;
    target_date: string;
    dte: number;
    data_quality: string;
}

interface StaticEmTicker {
    close: number;
    "0dte": StaticEmTenor | null;
    weekly: StaticEmTenor | null;
    monthly: StaticEmTenor | null;
}

export const ExpectedMovesChartV2: React.FC<ExpectedMovesChartV2Props> = ({ ticker, calcMode = 'sigma' }) => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const [connectionStatus, setConnectionStatus] = useState<string>('Disconnected');
    const [chartType, setChartType] = useState<'Area' | 'Candles'>('Candles');
    const [resolution, setResolution] = useState<string>('1d');
    const [emData, setEmData] = useState<ExpectedMovesData | null>(null);
    const [lastPrice, setLastPrice] = useState<number | null>(null);
    const [marketStatus, setMarketStatus] = useState<MarketStatus>(getMarketStatus());
    const [dataError, setDataError] = useState<string | null>(null);
    const [emLoading, setEmLoading] = useState<boolean>(true);
    const [chartLoading, setChartLoading] = useState<boolean>(true);

    // Static EM: pre-computed from previous close (instant load)
    const [staticEm, setStaticEm] = useState<StaticEmTicker | null>(null);
    const [staticEmLoading, setStaticEmLoading] = useState<boolean>(true);

    // Refs for Chart primitives
    const chartRef = useRef<any>(null);
    const seriesRef = useRef<any>(null);
    const livePriceLineRef = useRef<any>(null);

    // Ref mirror for staticEm (avoids chart recreation when static EM loads)
    const staticEmRef = useRef<StaticEmTicker | null>(null);

    // Refs for dynamic EM price lines (updated on each live price tick)
    const emPriceLineRefs = useRef<any[]>([]);
    // Store EM move amounts for dynamic recalculation: {key, move, highColor, lowColor, style, label}
    const emMovesRef = useRef<{ key: string, move: number, highColor: string, lowColor: string, style: any, label: string }[]>([]);
    // Ref mirror for lastPrice (avoids stale closures in effects)
    const lastPriceRef = useRef<number | null>(null);

    // Clear stale data immediately when ticker changes
    useEffect(() => {
        setEmData(null);
        setLastPrice(null);
        lastPriceRef.current = null;
        setDataError(null);
        setEmLoading(true);
        setChartLoading(true);
        setStaticEm(null);
        setStaticEmLoading(true);
        staticEmRef.current = null;
    }, [ticker]);

    // Fetch static EM (instant, cached JSON) — separate from chart lifecycle
    useEffect(() => {
        let cancelled = false;
        setStaticEmLoading(true);
        fetch('/api/v1/expected_moves/static/latest')
            .then(r => { if (!r.ok) throw new Error('not found'); return r.json(); })
            .then(data => {
                if (cancelled) return; // Ticker changed — discard stale result
                const em = data?.[ticker] ?? null;
                setStaticEm(em);
                staticEmRef.current = em;
                setStaticEmLoading(false);
            })
            .catch(() => { if (!cancelled) setStaticEmLoading(false); });
        return () => { cancelled = true; };
    }, [ticker]);

    // Fetch authoritative market status from backend on mount, then poll every 30s
    useEffect(() => {
        // Initial fetch from backend (populates cache for synchronous calls)
        fetchMarketStatus().then(setMarketStatus);
        const id = setInterval(() => {
            fetchMarketStatus().then(setMarketStatus);
        }, 30_000);
        return () => clearInterval(id);
    }, []);

    // 1. Initialize Chart
    useEffect(() => {
        if (!chartContainerRef.current) return;
        setChartLoading(true);

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: COLORS.bg.chart },
                textColor: COLORS.text.secondary,
                fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
                fontSize: 11,
            },
            grid: {
                vertLines: { color: COLORS.border.grid, style: LineStyle.SparseDotted },
                horzLines: { color: COLORS.border.grid, style: LineStyle.SparseDotted },
            },
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: { labelBackgroundColor: COLORS.border.subtle },
                horzLine: { labelBackgroundColor: COLORS.border.subtle },
            },
            timeScale: {
                timeVisible: true,
                secondsVisible: ['1m', '5m', '15m'].includes(resolution),
                borderColor: COLORS.border.grid,
                rightOffset: resolution !== '1d' ? 5 : 2,
            },
            rightPriceScale: {
                borderColor: COLORS.border.grid,
                visible: true,
                autoScale: true,
                scaleMargins: {
                    top: 0.1,
                    bottom: 0.1,
                },
            },
        });

        // Add Series based on Type
        let mainSeries: any;
        if (chartType === 'Candles') {
            mainSeries = chart.addSeries(CandlestickSeries, {
                upColor: CANDLE_COLORS.up.body,
                wickUpColor: CANDLE_COLORS.up.wick,
                borderUpColor: CANDLE_COLORS.up.border,
                borderVisible: true,

                downColor: CANDLE_COLORS.down.body,
                wickDownColor: CANDLE_COLORS.down.wick,
                borderDownColor: CANDLE_COLORS.down.border,
            });
        } else {
            mainSeries = chart.addSeries(LineSeries, {
                color: COLORS.live,
                lineWidth: 2,
            });
        }
        seriesRef.current = mainSeries;
        chartRef.current = chart;

        // Stale request guard — prevents old fetch results from overwriting new ticker data
        let cancelled = false;

        // Fetch History & Levels
        const initData = async () => {
            // 1. History — use Parquet for 1d, ThetaData stream for intraday
            setDataError(null); // Clear previous errors on resolution switch
            let formatted: any[] = [];
            try {
                if (resolution === '1d') {
                    // Daily: try ThetaData REST first (fresh data), fall back to Parquet
                    let dailyLoaded = false;
                    try {
                        const resThetaDaily = await fetch(`/api/v1/stream/history/${ticker}?resolution=1d`);
                        if (resThetaDaily.ok) {
                            const hist = await resThetaDaily.json();
                            const validHist = (Array.isArray(hist) ? hist : []).filter((d: any) => d.close > 0);
                            if (validHist.length > 50) {
                                // ThetaData REST returns {time: "YYYY-MM-DD", ...} for daily
                                formatted = validHist.map((d: any) => {
                                    const dateStr = d.time || d.date;
                                    if (chartType === 'Candles') {
                                        return { time: dateStr, open: d.open, high: d.high, low: d.low, close: d.close };
                                    } else {
                                        return { time: dateStr, value: d.close };
                                    }
                                });
                                dailyLoaded = true;
                            }
                        }
                    } catch { /* ThetaData REST failed — fall back to Parquet */ }

                    if (!dailyLoaded) {
                        // Fallback: use pre-ingested Parquet data
                        const resHist = await fetch(`/api/history/${ticker}`);
                        if (resHist.ok) {
                            const payload = await resHist.json();
                            const hist = payload.data || [];
                            const validHist = hist.filter((d: any) => d.close > 0);

                            formatted = validHist.map((d: any) => {
                                if (chartType === 'Candles') {
                                    return { time: d.date, open: d.open, high: d.high, low: d.low, close: d.close };
                                } else {
                                    return { time: d.date, value: d.close };
                                }
                            });
                        }
                    }
                } else {
                    // Intraday: use ThetaData OHLC history (source=ohlc bypasses flow history)
                    for (let attempt = 0; attempt < 2; attempt++) {
                        try {
                            const resHist = await fetch(`/api/v1/stream/history/${ticker}?resolution=${resolution}&source=ohlc`);
                            if (resHist.ok) {
                                const hist = await resHist.json();
                                const validHist = (Array.isArray(hist) ? hist : []).filter((d: any) => d.close > 0);

                                if (validHist.length > 0) {
                                    formatted = validHist.map((d: any) => {
                                        if (chartType === 'Candles') {
                                            return { time: d.time, open: d.open, high: d.high, low: d.low, close: d.close };
                                        } else {
                                            return { time: d.time, value: d.close };
                                        }
                                    });
                                    break; // Success — exit retry loop
                                }
                            }
                        } catch { /* retry */ }
                        if (attempt === 0) await new Promise(r => setTimeout(r, 2000)); // wait 2s before retry
                    }
                }

                // Sort (string dates sort lexicographically which is correct for YYYY-MM-DD)
                formatted.sort((a: any, b: any) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));

                if (cancelled) return; // Ticker changed — discard stale result
                if (formatted.length > 0) {
                    mainSeries.setData(formatted);
                    const last = formatted[formatted.length - 1];
                    const price = chartType === 'Candles' ? last.close : last.value;
                    setLastPrice(price);
                    lastPriceRef.current = price;

                    // Default zoom: show last 6 months for 1D, last N bars for intraday
                    if (resolution === '1d' && formatted.length > 126) {
                        const from = formatted[formatted.length - 126].time;
                        const to = formatted[formatted.length - 1].time;
                        chart.timeScale().setVisibleRange({ from, to });
                    } else if (resolution !== '1d' && formatted.length > 0) {
                        // Intraday: zoom to last N bars so new WS bars are visible
                        const barCounts: Record<string, number> = {
                            '1m': 120, '5m': 80, '15m': 60, '30m': 48, '1h': 40, '4h': 30
                        };
                        const n = barCounts[resolution] || 120;
                        const startIdx = Math.max(0, formatted.length - n);
                        chart.timeScale().setVisibleRange({
                            from: formatted[startIdx].time,
                            to: formatted[formatted.length - 1].time,
                        });
                    } else {
                        chart.timeScale().fitContent();
                    }

                    // Add live price line init
                    if (livePriceLineRef.current) {
                        mainSeries.removePriceLine(livePriceLineRef.current);
                        livePriceLineRef.current = null;
                    }
                    if (price > 0) {
                        livePriceLineRef.current = mainSeries.createPriceLine({
                            price: price,
                            color: COLORS.live,
                            lineWidth: 1,
                            lineStyle: LineStyle.Solid,
                            axisLabelVisible: true,
                            title: 'LIVE',
                        });
                    }
                    setChartLoading(false);
                } else if (resolution !== '1d') {
                    setDataError(`No intraday data for ${resolution}. ThetaData may be initializing — try again in a few seconds.`);
                    setChartLoading(false);
                } else {
                    setChartLoading(false);
                }
            } catch (e) {
                console.warn("History fetch failed:", (e as Error).message);
                setDataError("History data unavailable — retrying may help");
                setChartLoading(false);
            }

            // 2. Expected Moves Levels — try static first (instant), then live as fallback/enhancement
            const createEmLines = (moveData: { key: string, move: number, highColor: string, lowColor: string, style: any, label: string }[], centerPrice: number) => {
                // Remove old lines
                for (const line of emPriceLineRefs.current) {
                    try { mainSeries.removePriceLine(line); } catch { }
                }
                emPriceLineRefs.current = [];

                for (const em of moveData) {
                    const hi = centerPrice + em.move;
                    const lo = centerPrice - em.move;

                    const hiLine = mainSeries.createPriceLine({
                        price: hi,
                        color: em.highColor,
                        lineWidth: 2,
                        lineStyle: em.style,
                        axisLabelVisible: true,
                        title: `${em.label} High`
                    });
                    const loLine = mainSeries.createPriceLine({
                        price: lo,
                        color: em.lowColor,
                        lineWidth: 2,
                        lineStyle: em.style,
                        axisLabelVisible: true,
                        title: `${em.label} Low`
                    });
                    emPriceLineRefs.current.push(hiLine, loLine);
                }
                emMovesRef.current = moveData;
                chart.priceScale('right').applyOptions({ autoScale: true });
            };

            const emConfigs = [
                { tenor: "0dte", eodKey: "0dte_range", highColor: EM_COLORS.dte0.high, lowColor: EM_COLORS.dte0.low, style: LineStyle.Dotted, label: "0DTE" },
                { tenor: "weekly", eodKey: "weekly_range", highColor: EM_COLORS.weekly.high, lowColor: EM_COLORS.weekly.low, style: LineStyle.Dashed, label: "Weekly" },
                ...(resolution === '1d' ? [
                    { tenor: "monthly", eodKey: "monthly_range", highColor: EM_COLORS.monthly.high, lowColor: EM_COLORS.monthly.low, style: LineStyle.Solid, label: "Monthly" }
                ] : []),
            ];

            // 2a. Try static EM first (instant from cached JSON, via ref)
            const currentStaticEm = staticEmRef.current;
            let staticMoves: typeof emMovesRef.current = [];
            if (currentStaticEm) {
                for (const cfg of emConfigs) {
                    const tenorData = (currentStaticEm as any)[cfg.tenor];
                    if (!tenorData) continue;
                    const move = calcMode === 'breakeven' ? tenorData.breakeven_move : tenorData.sigma_move;
                    if (move && move > 0) {
                        staticMoves.push({ key: cfg.eodKey, move, highColor: cfg.highColor, lowColor: cfg.lowColor, style: cfg.style, label: cfg.label });
                    }
                }
            }

            if (staticMoves.length > 0) {
                const lastChartPrice = formatted.length > 0
                    ? (chartType === 'Candles' ? formatted[formatted.length - 1].close : formatted[formatted.length - 1].value)
                    : (currentStaticEm?.close ?? 0);
                if (lastChartPrice > 0 && !cancelled) {
                    createEmLines(staticMoves, lastChartPrice);
                    setEmLoading(false);
                }
            }

            // 2b. Also fetch live EM (slower, but provides fresh live-computed data)
            const fetchEmWithRetry = async (): Promise<any> => {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout
                try {
                    const r = await fetch(`/api/v1/expected_moves/theta/latest/${ticker}`, {
                        signal: controller.signal
                    });
                    if (r.ok) {
                        const d = await r.json();
                        if (d && !d.error && (d["0dte_range"] || d["weekly_range"] || d["monthly_range"])) return d;
                    }
                } catch {
                    // Timeout or network error — static EM is the fallback
                } finally {
                    clearTimeout(timeoutId);
                }
                return null;
            };
            try {
                const data = await fetchEmWithRetry();
                if (cancelled) return; // Ticker changed — discard stale result
                setEmLoading(false);
                if (data) {
                    setEmData(data);

                    // Build live move data
                    const liveMoves: typeof emMovesRef.current = [];
                    for (const cfg of emConfigs) {
                        const range = data[cfg.eodKey];
                        if (range) {
                            const move = calcMode === 'breakeven'
                                ? (range.breakeven_move ?? range.plus_minus)
                                : (range.sigma_move ?? range.plus_minus);
                            if (move && move > 0) {
                                liveMoves.push({ key: cfg.eodKey, move, highColor: cfg.highColor, lowColor: cfg.lowColor, style: cfg.style, label: cfg.label });
                            }
                        }
                    }

                    // Update chart lines with live EM data (replaces static lines if they existed)
                    if (liveMoves.length > 0) {
                        const centerPrice = formatted.length > 0
                            ? (chartType === 'Candles' ? formatted[formatted.length - 1].close : formatted[formatted.length - 1].value)
                            : data.current_price;
                        createEmLines(liveMoves, centerPrice);
                    }
                }
            } catch (e) {
                if (!cancelled) setEmLoading(false);
                console.warn("EM fetch failed (expected when market closed):", (e as Error).message);
            }
        };

        initData();

        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                    height: chartContainerRef.current.clientHeight,
                });
            }
        };
        window.addEventListener('resize', handleResize);

        return () => {
            cancelled = true;
            livePriceLineRef.current = null;
            emPriceLineRefs.current = [];
            emMovesRef.current = [];
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, [ticker, chartType, resolution, calcMode]);

    // Create static EM lines when data arrives after chart is already initialized
    useEffect(() => {
        if (!staticEm || !seriesRef.current || !chartRef.current) return;

        const emConfigs = [
            { tenor: "0dte", eodKey: "0dte_range", highColor: EM_COLORS.dte0.high, lowColor: EM_COLORS.dte0.low, style: LineStyle.Dotted, label: "0DTE" },
            { tenor: "weekly", eodKey: "weekly_range", highColor: EM_COLORS.weekly.high, lowColor: EM_COLORS.weekly.low, style: LineStyle.Dashed, label: "Weekly" },
            ...(resolution === '1d' ? [
                { tenor: "monthly", eodKey: "monthly_range", highColor: EM_COLORS.monthly.high, lowColor: EM_COLORS.monthly.low, style: LineStyle.Solid, label: "Monthly" }
            ] : []),
        ];

        const moves: typeof emMovesRef.current = [];
        for (const cfg of emConfigs) {
            const tenorData = (staticEm as any)[cfg.tenor];
            if (!tenorData) continue;
            const move = calcMode === 'breakeven' ? tenorData.breakeven_move : tenorData.sigma_move;
            if (move && move > 0) {
                moves.push({ key: cfg.eodKey, move, highColor: cfg.highColor, lowColor: cfg.lowColor, style: cfg.style, label: cfg.label });
            }
        }

        if (moves.length === 0) return;
        const centerPrice = lastPriceRef.current ?? staticEm.close;
        if (!centerPrice || centerPrice <= 0) return;

        // Remove any existing EM lines and create new ones
        for (const line of emPriceLineRefs.current) {
            try { seriesRef.current.removePriceLine(line); } catch { }
        }
        emPriceLineRefs.current = [];

        for (const em of moves) {
            const hiLine = seriesRef.current.createPriceLine({ price: centerPrice + em.move, color: em.highColor, lineWidth: 2, lineStyle: em.style, axisLabelVisible: true, title: `${em.label} High` });
            const loLine = seriesRef.current.createPriceLine({ price: centerPrice - em.move, color: em.lowColor, lineWidth: 2, lineStyle: em.style, axisLabelVisible: true, title: `${em.label} Low` });
            emPriceLineRefs.current.push(hiLine, loLine);
        }
        emMovesRef.current = moves;
        chartRef.current.priceScale('right').applyOptions({ autoScale: true });
        setEmLoading(false);
    }, [staticEm, calcMode, resolution]);

    // WebSocket Updates (only connect during market sessions)
    useEffect(() => {
        // Skip WebSocket when market is fully closed (weekend/holiday/overnight)
        if (marketStatus.sessionType === 'closed') {
            setConnectionStatus('Market Closed');
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/ws/theta?ticker=${ticker}`;
        let ws: WebSocket | null = null;
        let reconnectTimeout: ReturnType<typeof setTimeout>;

        // Ref to track the current accumulating bar to prevent "resetting" high/low wicks
        // We initialize it with null.
        const currentBarRef = { current: null as { time: number | string, open: number, high: number, low: number, close: number } | null };

        const connect = () => {
            setConnectionStatus('Connecting...');
            ws = new WebSocket(wsUrl);

            ws.onopen = () => { setConnectionStatus('Live'); };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.error) return;

                    // 0. FILTER: Only accept STOCK/INDEX trades (ignore Option flow for the price chart)
                    if (data.asset_type && data.asset_type !== 'STOCK') return;

                    const time = data.time as number;
                    // FIX: Convert timestamp to unix seconds.
                    let chartTime = time;
                    if (!chartTime && data.timestamp) {
                        chartTime = Math.floor(new Date(data.timestamp).getTime() / 1000);
                    }
                    if (!chartTime) return;

                    const price = Number(data.price);
                    // 1. FILTER: Ignore Zero, Negative or NaN Prices
                    if (isNaN(price) || price <= 0) return;

                    if (seriesRef.current) {
                        // 2. FILTER: Sanity Check (5% Outlier Protection)
                        // Use ref (not state) to avoid stale closure on ticker switch
                        const refPrice = lastPriceRef.current;
                        if (refPrice && refPrice > 0) {
                            const pctChange = Math.abs((price - refPrice) / refPrice);
                            if (pctChange > 0.05) {
                                return;
                            }
                        }

                        setLastPrice(price);
                        lastPriceRef.current = price;

                        // Update Live Price Line
                        if (livePriceLineRef.current) {
                            seriesRef.current.removePriceLine(livePriceLineRef.current);
                            livePriceLineRef.current = null;
                        }

                        livePriceLineRef.current = seriesRef.current.createPriceLine({
                            price: price,
                            color: COLORS.live,
                            lineWidth: 1,
                            lineStyle: LineStyle.Solid,
                            axisLabelVisible: true,
                            title: 'LIVE',
                        });

                        // Dynamic EM: recenter expected move bands on live price
                        if (emMovesRef.current.length > 0) {
                            // Remove old EM lines
                            for (const line of emPriceLineRefs.current) {
                                try { seriesRef.current.removePriceLine(line); } catch { }
                            }
                            emPriceLineRefs.current = [];

                            // Recreate at new center
                            for (const em of emMovesRef.current) {
                                const hiLine = seriesRef.current.createPriceLine({
                                    price: price + em.move,
                                    color: em.highColor,
                                    lineWidth: 2,
                                    lineStyle: em.style,
                                    axisLabelVisible: true,
                                    title: `${em.label} High`,
                                });
                                const loLine = seriesRef.current.createPriceLine({
                                    price: price - em.move,
                                    color: em.lowColor,
                                    lineWidth: 2,
                                    lineStyle: em.style,
                                    axisLabelVisible: true,
                                    title: `${em.label} Low`,
                                });
                                emPriceLineRefs.current.push(hiLine, loLine);
                            }
                        }

                        // 3. LOGIC: OHLC Accumulation for Candles
                        if (chartType === 'Candles') {
                            let bar = currentBarRef.current;

                            // For 1D resolution, use "YYYY-MM-DD" string time to match Parquet data
                            if (resolution === '1d') {
                                const d = new Date(chartTime * 1000);
                                const dayStr = d.toISOString().slice(0, 10); // "YYYY-MM-DD"

                                if (bar && bar.time === dayStr) {
                                    bar.high = Math.max(bar.high, price);
                                    bar.low = Math.min(bar.low, price);
                                    bar.close = price;
                                } else {
                                    bar = {
                                        time: dayStr as any,
                                        open: price,
                                        high: price,
                                        low: price,
                                        close: price
                                    };
                                }
                            } else {
                                // Intraday: snap to resolution bucket (unix seconds)
                                const resMap: Record<string, number> = {
                                    '1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '4h': 14400
                                };
                                const bucketSize = resMap[resolution] || 60;
                                const snappedTime = Math.floor(chartTime / bucketSize) * bucketSize;

                                if (bar && bar.time === snappedTime) {
                                    bar.high = Math.max(bar.high, price);
                                    bar.low = Math.min(bar.low, price);
                                    bar.close = price;
                                } else {
                                    bar = {
                                        time: snappedTime as any,
                                        open: price,
                                        high: price,
                                        low: price,
                                        close: price
                                    };
                                }
                            }

                            currentBarRef.current = bar;
                            seriesRef.current.update(bar);

                        } else {
                            seriesRef.current.update({ time: chartTime, value: price });
                        }
                    }
                } catch (e) { }
            };
            ws.onclose = () => { setConnectionStatus('Disconnected'); reconnectTimeout = setTimeout(connect, 3000); };
        };

        connect();
        return () => {
            livePriceLineRef.current = null;
            if (ws) ws.close();
            clearTimeout(reconnectTimeout);
        };
    }, [ticker, chartType, resolution, marketStatus.sessionType]);

    // Build dual-row table data
    const tenors = [
        { label: "0DTE", eodKey: "0dte_range" as const, staticKey: "0dte" as const, color: "text-amber-400" },
        { label: "Weekly", eodKey: "weekly_range" as const, staticKey: "weekly" as const, color: "text-red-400" },
        { label: "Monthly", eodKey: "monthly_range" as const, staticKey: "monthly" as const, color: "text-purple-400" }
    ];

    return (
        <div className="flex flex-col h-full bg-slate-900 rounded-xl border border-slate-700 shadow-xl overflow-hidden">
            {/* Toolbar */}
            <div className="flex flex-col border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-10">
                {/* Top Row: Title, Resolution, Status */}
                <div className="flex items-center justify-between p-3 border-b border-slate-800/50">
                    <div className="flex items-center gap-4">
                        <h2 className="text-slate-100 font-bold flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full ${connectionStatus === 'Live' ? 'bg-cyan-500 animate-pulse' :
                                connectionStatus === 'Market Closed' ? 'bg-amber-500' :
                                    'bg-red-500'
                                }`}></span>
                            Theta Expected Moves V2
                        </h2>

                        {/* Calc Mode Badge */}
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${calcMode === 'breakeven'
                            ? 'bg-amber-900/50 text-amber-400 border border-amber-700/50'
                            : 'bg-cyan-900/50 text-cyan-400 border border-cyan-700/50'
                            }`}>
                            {calcMode === 'breakeven' ? 'Breakeven (~50%)' : '1-Sigma (~68%)'}
                        </span>

                        {/* Market Status Badge */}
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${marketStatus.isOpen
                            ? 'bg-emerald-900/50 text-emerald-400 border border-emerald-700/50'
                            : marketStatus.sessionType === 'pre_market' || marketStatus.sessionType === 'after_hours'
                                ? 'bg-amber-900/30 text-amber-400 border border-amber-700/50'
                                : 'bg-slate-800 text-slate-500 border border-slate-700/50'
                            }`}>
                            {marketStatus.status}
                        </span>

                        <div className="flex bg-slate-800/50 rounded p-1 border border-slate-700/50">
                            {['Candles', 'Area'].map((type) => (
                                <button
                                    key={type}
                                    onClick={() => setChartType(type as any)}
                                    className={`px-3 py-1 text-xs font-semibold rounded transition-all ${chartType === type ? 'bg-cyan-600 text-white shadow-lg' : 'text-slate-400 hover:text-slate-200'}`}
                                >
                                    {type}
                                </button>
                            ))}
                        </div>

                        <div className="flex bg-slate-800/50 rounded p-1 border border-slate-700/50 ml-2 overflow-x-auto max-w-[400px]">
                            {['1m', '5m', '15m', '30m', '1h', '4h', '1d'].map((res) => (
                                <button
                                    key={res}
                                    onClick={() => setResolution(res)}
                                    className={`px-3 py-1 text-xs font-semibold rounded transition-all ${resolution === res ? 'bg-slate-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}
                                >
                                    {res}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="flex items-center gap-6 text-xs text-slate-400 font-mono">
                        {staticEmLoading && !staticEm ? (
                            <div className="flex items-center gap-2 px-3 py-1 bg-slate-800/80 rounded-full border border-slate-700 shadow-inner">
                                <span className="text-[9px] text-slate-500 uppercase font-black tracking-tighter">EOD Anchor:</span>
                                <span className="text-slate-400 animate-pulse">Loading...</span>
                            </div>
                        ) : staticEm && staticEm.close > 0 && (
                            <div className="flex items-center gap-2 px-3 py-1 bg-slate-800/80 rounded-full border border-slate-700 shadow-inner">
                                <span className="text-[9px] text-slate-500 uppercase font-black tracking-tighter">EOD Anchor (Locked):</span>
                                <span className="text-slate-200 font-bold">${staticEm.close.toFixed(2)}</span>
                            </div>
                        )}
                        {lastPrice !== null && lastPrice !== undefined && !isNaN(lastPrice) && (
                            <div className="flex items-center gap-2 px-3 py-1 bg-cyan-950/30 rounded-full border border-cyan-500/30 shadow-inner animate-in fade-in duration-500">
                                <span className="text-[9px] text-cyan-500 uppercase font-black tracking-tighter">Intraday Market (Live):</span>
                                <span className="text-white font-black">${lastPrice.toFixed(2)}</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Stats Table UI — Dual Row: Static (EOD) + Dynamic (Live) */}
                <div className="bg-slate-950/40 p-3 overflow-x-auto">
                    <table className="w-full text-left border-collapse min-w-[700px]">
                        <thead>
                            <tr className="border-b border-slate-800 text-[10px] uppercase font-black text-slate-500">
                                <th className="pb-2 pl-2">Tenor</th>
                                <th className="pb-2">Type</th>
                                <th className="pb-2">Center</th>
                                <th className="pb-2">Expected Move</th>
                                <th className="pb-2">Expected Low</th>
                                <th className="pb-2">Expected High</th>
                                <th className="pb-2 pr-2">Expiry</th>
                            </tr>
                        </thead>
                        <tbody className="text-xs">
                            {(staticEmLoading && emLoading && !staticEm && !emData) ? (
                                /* Loading shimmer rows */
                                [0, 1, 2].map((i) => (
                                    <tr key={`loading-${i}`} className="border-b border-slate-800/30">
                                        <td colSpan={7} className="p-2">
                                            <div className="h-4 bg-slate-800 rounded animate-pulse" style={{ width: `${70 + i * 10}%` }} />
                                        </td>
                                    </tr>
                                ))
                            ) : tenors.flatMap((row, idx) => {
                                const rows: React.ReactNode[] = [];

                                // --- Static Row (EOD Anchor) ---
                                const sTenor = staticEm ? (staticEm as any)[row.staticKey] : null;
                                const sMove = sTenor
                                    ? (calcMode === 'breakeven' ? sTenor.breakeven_move : sTenor.sigma_move)
                                    : null;
                                const sCenter = staticEm?.close ?? 0;
                                const sHi = sMove && sCenter > 0
                                    ? (calcMode === 'breakeven' ? sTenor.upper_breakeven : sTenor.upper_sigma)
                                    : null;
                                const sLo = sMove && sCenter > 0
                                    ? (calcMode === 'breakeven' ? sTenor.lower_breakeven : sTenor.lower_sigma)
                                    : null;
                                const sExpiry = sTenor?.target_date || sTenor?.date;
                                const sQuality = sTenor?.data_quality;

                                rows.push(
                                    <tr key={`static-${idx}`} className="border-b border-slate-800/20 hover:bg-slate-900/40 transition-colors">
                                        <td className={`p-2 font-bold ${row.color}`} rowSpan={1}>
                                            {row.label}
                                            {sQuality === 'estimated' && (
                                                <span className="ml-1 text-[8px] text-amber-500 font-normal" title="One leg was estimated (bad tick)">*</span>
                                            )}
                                        </td>
                                        <td className="text-[10px] text-slate-500 font-bold uppercase">
                                            <span className="px-1.5 py-0.5 rounded bg-slate-800/60 border border-slate-700/40">EOD</span>
                                        </td>
                                        <td className="font-mono text-slate-400">
                                            {sCenter > 0 ? `$${sCenter.toFixed(2)}` : '---'}
                                        </td>
                                        <td className="font-mono font-bold text-slate-300">
                                            {sMove ? `\u00B1${sMove.toFixed(2)}` : staticEmLoading ? '...' : '---'}
                                        </td>
                                        <td className="font-mono text-red-400/70">
                                            {sLo ? `$${sLo.toFixed(2)}` : staticEmLoading ? '...' : '---'}
                                        </td>
                                        <td className="font-mono text-emerald-400/70">
                                            {sHi ? `$${sHi.toFixed(2)}` : staticEmLoading ? '...' : '---'}
                                        </td>
                                        <td className="text-slate-500 italic text-[10px]">
                                            {sExpiry || '---'}
                                        </td>
                                    </tr>
                                );

                                // --- Dynamic Row (Live Intraday) — only during regular session ---
                                // Outside regular hours, option chains aren't trading so EM values
                                // would be stale (previous close) recentered on live price — inaccurate.
                                if (marketStatus.sessionType === 'regular') {
                                    const sTenorForLive = staticEm ? (staticEm as any)[row.staticKey] : null;
                                    const dMove = sTenorForLive
                                        ? (calcMode === 'breakeven' ? sTenorForLive.breakeven_move : sTenorForLive.sigma_move)
                                        : null;
                                    const dCenter = lastPrice && lastPrice > 0 ? lastPrice : 0;
                                    const dHi = dMove && dCenter > 0 ? dCenter + dMove : null;
                                    const dLo = dMove && dCenter > 0 ? dCenter - dMove : null;
                                    const dExpiry = sTenorForLive?.target_date || sTenorForLive?.date;
                                    const dQuality = sTenorForLive?.data_quality;

                                    rows.push(
                                        <tr key={`dynamic-${idx}`} className="border-b border-slate-800/30 hover:bg-slate-900/40 transition-colors">
                                            <td className="p-2"></td>
                                            <td className="text-[10px] font-bold uppercase">
                                                <span className="px-1.5 py-0.5 rounded bg-cyan-900/30 text-cyan-400 border border-cyan-700/30">LIVE</span>
                                            </td>
                                            <td className="font-mono text-cyan-300 font-bold">
                                                {dCenter > 0 ? `$${dCenter.toFixed(2)}` : '---'}
                                            </td>
                                            <td className="font-mono font-bold text-slate-200">
                                                {dMove ? `\u00B1${dMove.toFixed(2)}` : staticEmLoading ? (
                                                    <span className="text-slate-500 animate-pulse">Loading...</span>
                                                ) : '---'}
                                                {dQuality === 'estimated' && (
                                                    <span className="ml-1 text-[8px] text-amber-500" title="One leg was estimated">*</span>
                                                )}
                                            </td>
                                            <td className="font-mono text-red-400 font-bold">
                                                {dLo ? `$${dLo.toFixed(2)}` : staticEmLoading ? '...' : '---'}
                                            </td>
                                            <td className="font-mono text-emerald-400 font-bold">
                                                {dHi ? `$${dHi.toFixed(2)}` : staticEmLoading ? '...' : '---'}
                                            </td>
                                            <td className="text-slate-500 italic text-[10px]">
                                                {dExpiry || '---'}
                                            </td>
                                        </tr>
                                    );
                                }

                                return rows;
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Chart Canvas */}
            <div className="flex-grow relative bg-slate-900">
                <div ref={chartContainerRef} className="absolute inset-0" />
                {chartLoading && (
                    <div className="absolute inset-0 flex items-center justify-center z-10 bg-slate-900/60 backdrop-blur-[1px]">
                        <div className="flex flex-col items-center gap-3">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500"></div>
                            <span className="text-xs text-slate-400">Loading chart data...</span>
                        </div>
                    </div>
                )}
                {dataError && (
                    <div className="absolute top-3 left-1/2 -translate-x-1/2 bg-amber-900/80 text-amber-200 text-xs px-4 py-1.5 rounded-full border border-amber-700/50 backdrop-blur-sm z-10">
                        {dataError}
                    </div>
                )}
            </div>
        </div>
    );
};
