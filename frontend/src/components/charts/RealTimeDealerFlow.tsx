import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { createChart, ColorType, CrosshairMode, LineStyle, LineSeries } from 'lightweight-charts';
import { useWebSocket } from '../../hooks/useWebSocket';

interface RealTimeDealerFlowProps {
    ticker: string;
}

export const RealTimeDealerFlow: React.FC<RealTimeDealerFlowProps> = ({ ticker }) => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const [connectionStatus, setConnectionStatus] = useState<string>('Disconnected');
    const [gexProfile, setGexProfile] = useState<any[]>([]);
    const [chartLimits, setChartLimits] = useState<{ min: number; max: number } | null>(null);
    const [gexStatus, setGexStatus] = useState<string>('');
    const [currentPrice, setCurrentPrice] = useState<number | null>(null);
    const [horizon, setHorizon] = useState<'total' | 'eow' | 'next5'>('total');
    const [dataSource, setDataSource] = useState<'theta'>('theta');

    // Refs for chart + series (survive re-renders, persist across horizon changes)
    const chartRef = useRef<any>(null);
    const priceSeriesRef = useRef<any>(null);
    const flowSeriesRef = useRef<any>(null);
    const lastPriceUpdate = useRef<number>(0);
    const lastMessageTime = useRef<number>(Date.now());
    const priceLineRefs = useRef<any[]>([]);
    const gexProfileRef = useRef<any[]>([]);
    const emDataRef = useRef<any>(null);

    // Keep gexProfile ref in sync for horizon recalc
    useEffect(() => { gexProfileRef.current = gexProfile; }, [gexProfile]);

    // Helper: recalculate walls and EM price lines for a given horizon
    const applyPriceLines = useCallback((
        priceSeries: any,
        profile: any[],
        emTickers: any,
        hz: string,
        refPrice: number
    ) => {
        // Remove old price lines
        for (const line of priceLineRefs.current) {
            try { priceSeries.removePriceLine(line); } catch { }
        }
        priceLineRefs.current = [];

        if (!profile.length) return { min: Infinity, max: -Infinity };

        const prefix = hz === 'total' ? 'total' : hz === 'next5' ? 'next5' : 'eow';
        const cKey = `${prefix}_call_gex`;
        const pKey = `${prefix}_put_gex`;
        const netKey = `${prefix}_net_gex`;

        let maxCallGex = -Infinity, callWallStrike = 0;
        let minPutGex = Infinity, putWallStrike = 0;
        const flips: number[] = [];
        let prevNet = 0;

        for (const row of profile) {
            const c = row[cKey] ?? row.total_call_gex ?? 0;
            const p = row[pKey] ?? row.total_put_gex ?? 0;
            if (c > maxCallGex) { maxCallGex = c; callWallStrike = row.strike; }
            if (p < minPutGex) { minPutGex = p; putWallStrike = row.strike; }

            const net = row[netKey] ?? row.total_net_gex ?? 0;
            if (prevNet !== 0 && ((prevNet < 0 && net >= 0) || (prevNet > 0 && net <= 0))) {
                flips.push(row.strike);
            }
            prevNet = net;
        }

        const zeroGamma = flips.length > 0
            ? flips.reduce((a, b) => Math.abs(b - refPrice) < Math.abs(a - refPrice) ? b : a)
            : 0;

        if (callWallStrike) priceLineRefs.current.push(priceSeries.createPriceLine({ price: callWallStrike, color: '#EF4444', lineWidth: 2, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: 'Call Wall' }));
        if (putWallStrike) priceLineRefs.current.push(priceSeries.createPriceLine({ price: putWallStrike, color: '#22C55E', lineWidth: 2, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: 'Put Wall' }));
        if (zeroGamma) priceLineRefs.current.push(priceSeries.createPriceLine({ price: zeroGamma, color: '#F97316', lineWidth: 2, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: 'Vol Trigger' }));

        // Track global min/max for Y-axis scaling
        let globalMin = Infinity, globalMax = -Infinity;
        if (callWallStrike) { globalMax = Math.max(globalMax, callWallStrike); globalMin = Math.min(globalMin, callWallStrike); }
        if (putWallStrike) { globalMax = Math.max(globalMax, putWallStrike); globalMin = Math.min(globalMin, putWallStrike); }

        // Expected Moves
        const exps = emTickers?.[ticker]?.expirations;
        if (exps) {
            const addEM = (expKey: string, label: string, style: LineStyle) => {
                const exp = exps[expKey];
                if (exp?.upper_range && exp?.lower_range) {
                    globalMax = Math.max(globalMax, exp.upper_range);
                    globalMin = Math.min(globalMin, exp.lower_range);
                    priceLineRefs.current.push(priceSeries.createPriceLine({ price: exp.upper_range, color: '#EF4444', lineWidth: 1, lineStyle: style, axisLabelVisible: true, title: `${label} High` }));
                    priceLineRefs.current.push(priceSeries.createPriceLine({ price: exp.lower_range, color: '#22C55E', lineWidth: 1, lineStyle: style, axisLabelVisible: true, title: `${label} Low` }));
                }
            };
            addEM('ODTE', '0DTE', LineStyle.Dotted);
            addEM('WEEKLY', 'Weekly', LineStyle.Dashed);
        }

        // Fallback to GEX profile range
        if (globalMin === Infinity && profile.length > 0) {
            profile.forEach((p: any) => { globalMax = Math.max(globalMax, p.strike); globalMin = Math.min(globalMin, p.strike); });
            const h = globalMax - globalMin;
            globalMax += h * 0.05;
            globalMin -= h * 0.05;
        }

        return { min: globalMin, max: globalMax };
    }, [ticker]);

    // ===== CHART CREATION: depends ONLY on ticker =====
    useEffect(() => {
        if (!chartContainerRef.current) return;
        chartContainerRef.current.innerHTML = '';
        priceLineRefs.current = [];

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#0F172A' },
                textColor: '#94A3B8',
                fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
                fontSize: 11,
            },
            grid: {
                vertLines: { color: '#1E293B' },
                horzLines: { color: '#1E293B' },
            },
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
            crosshair: { mode: CrosshairMode.Normal },
            timeScale: {
                timeVisible: true,
                secondsVisible: true,
                rightOffset: 20,
            },
            rightPriceScale: {
                borderColor: '#334155',
                visible: true,
                scaleMargins: { top: 0, bottom: 0 },
                autoScale: true,
            },
            leftPriceScale: {
                visible: true,
                borderColor: '#334155',
            },
        });

        const priceSeries = chart.addSeries(LineSeries, {
            color: '#F8FAFC',
            lineWidth: 2,
            priceScaleId: 'right',
            title: `${ticker} Price`,
        });

        const flowSeries = chart.addSeries(LineSeries, {
            color: '#06B6D4',
            lineWidth: 2,
            lineStyle: LineStyle.Solid,
            priceScaleId: 'left',
            title: 'Dealer Flow (HIRO)',
        });

        chartRef.current = chart;
        priceSeriesRef.current = priceSeries;
        flowSeriesRef.current = flowSeries;

        // Fetch history, GEX, and EM data
        const fetchEverything = async () => {
            let loadedProfile: any[] = [];
            let emTickers: any = null;
            let refPrice = 0;

            try {
                // A. History
                const resHist = await fetch(`/api/v1/stream/history/${ticker}`);
                if (resHist.ok) {
                    const historyData = await resHist.json();
                    if (historyData.length > 0) {
                        const priceData = historyData
                            .filter((d: any) => d.value && d.value > 0)
                            .map((d: any) => ({ time: d.time as any, value: d.value }));
                        const flowData = historyData
                            .filter((d: any) => d.value && d.value > 0)
                            .map((d: any) => ({ time: d.time as any, value: d.flow ?? 0 }));
                        priceSeries.setData(priceData);
                        flowSeries.setData(flowData);
                        const last = priceData[priceData.length - 1];
                        if (last) {
                            setCurrentPrice(last.value);
                            refPrice = last.value;
                        }
                    }
                }

                // B. GEX
                setGexStatus('Fetching...');
                const resGex = await fetch(`/api/v1/gex/latest/${ticker}?_t=${Date.now()}`);
                if (resGex.ok) {
                    const gexData = await resGex.json();
                    if (gexData.profile?.length > 0) {
                        loadedProfile = [...gexData.profile].sort((a: any, b: any) => a.strike - b.strike);
                        setGexProfile(loadedProfile);
                        setGexStatus(`Loaded (${loadedProfile.length} levels)`);
                    } else {
                        setGexProfile([]);
                        setGexStatus('Empty Profile');
                    }
                }

                // C. Expected Moves
                const resEM = await fetch(`/api/v1/expected_moves/latest?_t=${Date.now()}`);
                if (resEM.ok) {
                    const emData = await resEM.json();
                    emTickers = emData.tickers || emData;
                    emDataRef.current = emTickers;
                }

                // D. Apply price lines + Y-axis scaling
                if (!refPrice && loadedProfile.length > 0) {
                    refPrice = (loadedProfile[0].strike + loadedProfile[loadedProfile.length - 1].strike) / 2;
                }
                const range = applyPriceLines(priceSeries, loadedProfile, emTickers, horizon, refPrice);

                if (range.min < Infinity) {
                    const height = range.max - range.min;
                    const buffer = height * 0.15;
                    const minLimit = range.min - buffer;
                    const maxLimit = range.max + buffer;
                    setChartLimits({ min: minLimit, max: maxLimit });

                    priceSeries.applyOptions({
                        autoscaleInfoProvider: () => ({
                            priceRange: { minValue: minLimit, maxValue: maxLimit },
                            margins: { above: 0, below: 0 },
                        }),
                    });
                }

                chart.timeScale().fitContent();
            } catch (e) { console.error('Data fetch error:', e); }
        };
        fetchEverything();

        // Resize
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
            priceSeriesRef.current = null;
            flowSeriesRef.current = null;
        };
    }, [ticker]); // Chart lifecycle: ONLY ticker

    // ===== HORIZON CHANGE: just recalculate price lines, don't recreate chart =====
    useEffect(() => {
        const priceSeries = priceSeriesRef.current;
        const profile = gexProfileRef.current;
        const emTickers = emDataRef.current;
        if (!priceSeries || !profile.length) return;

        const refPrice = currentPrice || (profile[0].strike + profile[profile.length - 1].strike) / 2;
        const range = applyPriceLines(priceSeries, profile, emTickers, horizon, refPrice);

        if (range.min < Infinity) {
            const height = range.max - range.min;
            const buffer = height * 0.15;
            const minLimit = range.min - buffer;
            const maxLimit = range.max + buffer;
            setChartLimits({ min: minLimit, max: maxLimit });

            priceSeries.applyOptions({
                autoscaleInfoProvider: () => ({
                    priceRange: { minValue: minLimit, maxValue: maxLimit },
                    margins: { above: 0, below: 0 },
                }),
            });
        }
    }, [horizon, applyPriceLines, currentPrice]);



    // ===== WEBSOCKET: depends ONLY on ticker =====
    // Uses unified /ws/quotes endpoint
    // ===== WEBSOCKET: depends ONLY on ticker =====
    // Uses unified /ws/quotes endpoint
    const handleWebSocketMessage = useCallback((data: any) => {
        if (data.error) return;
        if (data.root && data.root !== ticker) return;

        if (data.source) setDataSource(data.source);

        const time = data.time || data.timestamp_ms || Math.floor(Date.now() / 1000);
        const price = data.price;
        const flow = data.hiro_flow;

        if (!price || price === 0) return;

        lastMessageTime.current = Date.now();

        if (priceSeriesRef.current) {
            priceSeriesRef.current.update({ time, value: price });
        }
        if (flowSeriesRef.current && flow !== undefined) {
            flowSeriesRef.current.update({ time, value: flow });
        }

        const now = Date.now();
        if (now - lastPriceUpdate.current > 1000) {
            setCurrentPrice(price);
            lastPriceUpdate.current = now;
        }
    }, [ticker]);

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/quotes`;

    const { status: wsStatus } = useWebSocket({
        url: wsUrl,
        onMessage: handleWebSocketMessage,
        shouldConnect: true,
        reconnectInterval: 3000
    });

    useEffect(() => {
        setConnectionStatus(wsStatus);
    }, [wsStatus]);

    // GEX Sidebar data
    const sidebarData = useMemo(() => {
        if (!gexProfile.length || !chartLimits) return { bars: [], maxAbsNet: 0, minS: 0, maxS: 0, netKey: 'total_net_gex' };
        const { min: minS, max: maxS } = chartLimits;
        const prefix = horizon === 'total' ? 'total' : horizon === 'next5' ? 'next5' : 'eow';
        const netKey = `${prefix}_net_gex`;
        const filtered = gexProfile.filter((p: any) => p.strike >= minS && p.strike <= maxS);
        const maxAbsNet = Math.max(...filtered.map((r: any) => Math.abs(r[netKey] ?? r.total_net_gex ?? 0)), 1);
        return { bars: filtered, maxAbsNet, minS, maxS, netKey };
    }, [gexProfile, chartLimits, horizon]);

    return (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 shadow-sm flex flex-col h-[850px] relative">
            {/* Header */}
            <div className="flex justify-between items-center mb-4 shrink-0">
                <div>
                    <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse"></span>
                        Real-Time Dealer Flow (HIRO)
                    </h3>
                    <div className="flex items-center gap-2">
                        <p className="text-xs text-slate-400">Streaming {ticker} via</p>
                        <span className="text-xs bg-blue-600/20 text-blue-400 px-2 py-0.5 rounded border border-blue-600/30">
                            ThetaData
                        </span>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <span className={`text-xs px-2 py-1 rounded border ${connectionStatus === 'Connected'
                        ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                        : connectionStatus.includes('Stalled')
                            ? 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400'
                            : 'bg-red-500/10 border-red-500/20 text-red-400'
                        }`}>
                        {connectionStatus}
                    </span>
                    {/* Horizon Toggles */}
                    <div className="flex bg-slate-800 rounded p-1 border border-slate-700">
                        {(['eow', 'total', 'next5'] as const).map(h => (
                            <button
                                key={h}
                                onClick={() => setHorizon(h)}
                                className={`px-2 py-0.5 text-[10px] rounded uppercase font-medium transition-colors ${horizon === h
                                    ? 'bg-slate-600 text-white'
                                    : 'text-slate-400 hover:text-slate-200'
                                    }`}
                            >
                                {h === 'next5' ? 'Short' : h}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Column Headers */}
            <div className="flex w-full mb-1 border-b border-slate-800 pb-1 shrink-0">
                <div className="w-[15%] flex justify-between px-2 text-[10px] text-slate-500 font-sans tracking-wide">
                    <span>Strike</span>
                    <span>Net GEX</span>
                </div>
                <div className="w-[85%] text-[10px] text-slate-500 pl-4 font-sans tracking-wide">
                    Price Action
                </div>
            </div>

            {/* Main Content: GEX Sidebar + Chart */}
            <div className="flex flex-1 w-full min-h-0 relative">
                {/* GEX Sidebar (15%) */}
                <div className="w-[15%] bg-[#0F172A] border-r border-slate-800 relative select-none overflow-hidden">
                    {sidebarData.bars.length > 0 ? (
                        <div className="relative w-full h-full">
                            {sidebarData.bars.map((row: any) => {
                                const net = row[sidebarData.netKey] ?? row.total_net_gex ?? 0;
                                const barWidth = sidebarData.maxAbsNet > 0 ? (Math.abs(net) / sidebarData.maxAbsNet) * 100 : 0;
                                const range = sidebarData.maxS - sidebarData.minS;
                                const topPct = ((sidebarData.maxS - row.strike) / range) * 100;
                                if (topPct < 0 || topPct > 98) return null;

                                return (
                                    <div
                                        key={row.strike}
                                        style={{ top: `${topPct}%`, height: '1.5%' }}
                                        className="absolute left-0 right-0 flex items-center group hover:bg-slate-800/30 transition-colors"
                                    >
                                        <div className="w-[45%] flex justify-between items-center pr-1 text-[10px] font-sans leading-none">
                                            <span className={net > 0 ? "text-sky-400" : "text-red-400"}>{row.strike}</span>
                                            <span className="text-slate-500 scale-75 origin-right">{(net / 1e6).toFixed(1)}</span>
                                        </div>
                                        <div className="flex-1 h-[2px] flex bg-slate-900/50">
                                            <div className="flex-1 flex justify-end pr-0.5 border-r border-slate-700/30">
                                                {net < 0 && (<div style={{ width: `${barWidth}%` }} className="h-full bg-red-500"></div>)}
                                            </div>
                                            <div className="flex-1 flex justify-start pl-0.5">
                                                {net > 0 && (<div style={{ width: `${barWidth}%` }} className="h-full bg-sky-500"></div>)}
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                            {currentPrice && currentPrice >= sidebarData.minS && currentPrice <= sidebarData.maxS && (
                                <div
                                    style={{ top: `${((sidebarData.maxS - currentPrice) / (sidebarData.maxS - sidebarData.minS)) * 100}%` }}
                                    className="absolute left-0 right-0 h-[1px] bg-white z-20 shadow-[0_0_8px_white]"
                                ></div>
                            )}
                        </div>
                    ) : (
                        <div className="text-[10px] text-slate-500 p-2">
                            {gexStatus === 'Fetching...' ? 'Loading GEX...' : 'No GEX Data'}
                        </div>
                    )}
                </div>

                {/* Chart (85%) */}
                <div className="w-[85%] relative bg-[#0F172A]">
                    <div ref={chartContainerRef} className="w-full h-full" />
                </div>
            </div>

            {/* Legend */}
            <div className="mt-1 pb-1 px-2 border-t border-slate-800 pt-2 flex flex-wrap gap-4 text-[10px] text-slate-400 justify-center font-sans shrink-0">
                <div className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 bg-white"></span>
                    <span>Price</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 bg-cyan-500"></span>
                    <span>Flow</span>
                </div>
                <div className="flex items-center gap-1.5 ml-2 border-l border-slate-700 pl-2">
                    <span className="w-3 h-0.5 bg-red-500"></span>
                    <span>Call Wall (Res)</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 bg-green-500"></span>
                    <span>Put Wall (Supp)</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 border-b-2 border-[#F97316] border-dashed"></span>
                    <span>Vol Trigger</span>
                </div>
                <div className="flex items-center gap-1.5 ml-2 border-l border-slate-700 pl-2">
                    <span className="w-3 h-0.5 border-b-2 border-red-500 border-dotted"></span>
                    <span>0DTE High</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 border-b-2 border-green-500 border-dotted"></span>
                    <span>0DTE Low</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 border-b-2 border-red-500 border-dashed"></span>
                    <span>Weekly High</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 border-b-2 border-green-500 border-dashed"></span>
                    <span>Weekly Low</span>
                </div>
            </div>
        </div>
    );
};
