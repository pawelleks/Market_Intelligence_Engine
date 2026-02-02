import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { createChart, ColorType, CrosshairMode, LineStyle, LineSeries } from 'lightweight-charts';

interface RealTimeDataPoint {
    time: number;
    price: number;
    dealer_flow: number;
}

interface RealTimeDealerFlowProps {
    ticker: string;
}

export const RealTimeDealerFlow: React.FC<RealTimeDealerFlowProps> = ({ ticker }) => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const [connectionStatus, setConnectionStatus] = useState<string>('Disconnected');
    const [error, setError] = useState<string | null>(null);
    const [gexProfile, setGexProfile] = useState<any[]>([]);
    const [chartLimits, setChartLimits] = useState<{ min: number, max: number } | null>(null);
    const [gexStatus, setGexStatus] = useState<string>('');
    const [currentPrice, setCurrentPrice] = useState<number | null>(null);

    // Data Refs
    const chartRef = useRef<any>(null);
    const priceSeriesRef = useRef<any>(null);
    const flowSeriesRef = useRef<any>(null);
    const lastPriceUpdate = useRef<number>(0);

    // Dynamic Chart Initialization
    useEffect(() => {
        if (!chartContainerRef.current) return;

        // STRICT SCALING: Zero Margins on Right Price Scale
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
            crosshair: {
                mode: CrosshairMode.Normal,
            },
            timeScale: {
                timeVisible: true,
                secondsVisible: true,
            },
            rightPriceScale: {
                borderColor: '#334155',
                visible: true,
                scaleMargins: {
                    top: 0,
                    bottom: 0,
                },
                autoScale: true, // Overridden by applyOptions if chartLimits set
            },
            leftPriceScale: {
                visible: true,
                borderColor: '#334155',
            },
        });

        // 2. Add Series
        const priceSeries = chart.addSeries(LineSeries, {
            color: '#F8FAFC', // Slate 50
            lineWidth: 2,
            priceScaleId: 'right', // Main scale
            title: `${ticker} Price`,
        });

        const flowSeries = chart.addSeries(LineSeries, {
            color: '#06B6D4', // Cyan 500
            lineWidth: 2,
            lineStyle: LineStyle.Solid,
            priceScaleId: 'left', // Bind to Left Axis
            title: 'Dealer Flow (HIRO)',
        });

        // 3. Fetch Data
        const fetchEverything = async () => {
            try {
                // A. History
                const resHist = await fetch(`/api/v1/stream/history/${ticker}`);
                if (resHist.ok) {
                    const historyData = await resHist.json();
                    if (historyData.length > 0) {
                        const formattedData = historyData.map((d: any) => ({
                            time: d.time as any,
                            value: d.value
                        }));
                        priceSeries.setData(formattedData);
                        const last = formattedData[formattedData.length - 1];
                        if (last) setCurrentPrice(last.value);
                    }
                }

                // B. GEX Data
                setGexStatus('Fetching...');
                const resGex = await fetch(`/api/v1/gex/latest/${ticker}?_t=${Date.now()}`);
                let profile: any[] = [];

                if (resGex.ok) {
                    const gexData = await resGex.json();

                    if (gexData.profile && Array.isArray(gexData.profile) && gexData.profile.length > 0) {
                        profile = gexData.profile;
                        // Sort profile by strike to ensure correct flip detection
                        profile.sort((a: any, b: any) => a.strike - b.strike);
                        setGexProfile(profile);
                        setGexStatus(`Loaded (${profile.length} levels)`);

                        // Render Walls logic
                        let maxCallGex = -Infinity; let callWallStrike = 0;
                        let minPutGex = Infinity; let putWallStrike = 0;
                        let zeroGammaStrike = 0;

                        let flips: number[] = [];
                        let prevNet = 0;

                        // Reference Price for picking best flip (use currentPrice or center of profile)
                        const refPrice = currentPrice || (profile[0].strike + profile[profile.length - 1].strike) / 2;

                        for (const row of profile) {
                            if ((row.total_call_gex || 0) > maxCallGex) { maxCallGex = row.total_call_gex || 0; callWallStrike = row.strike; }
                            if ((row.total_put_gex || 0) < minPutGex) { minPutGex = row.total_put_gex || 0; putWallStrike = row.strike; }

                            const net = row.total_net_gex || 0;
                            // Check for zero crossing (Flip)
                            if (prevNet !== 0) {
                                if ((prevNet < 0 && net >= 0) || (prevNet > 0 && net <= 0)) {
                                    flips.push(row.strike);
                                }
                            }
                            prevNet = net;
                        }

                        // Pick flip closest to reference price
                        if (flips.length > 0) {
                            zeroGammaStrike = flips.reduce((prev, curr) => {
                                return (Math.abs(curr - refPrice) < Math.abs(prev - refPrice) ? curr : prev);
                            });
                        }

                        if (callWallStrike) priceSeries.createPriceLine({ price: callWallStrike, color: '#EF4444', lineWidth: 2, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: 'Call Wall' });
                        if (putWallStrike) priceSeries.createPriceLine({ price: putWallStrike, color: '#22C55E', lineWidth: 2, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: 'Put Wall' });
                        if (zeroGammaStrike) priceSeries.createPriceLine({ price: zeroGammaStrike, color: '#F97316', lineWidth: 2, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: 'Vol Trigger' });

                    } else {
                        setGexProfile([]);
                        setGexStatus('Empty Profile');
                    }
                }

                // C. Expected Moves Or Fallback for Limits
                try {
                    const resEM = await fetch(`/api/v1/expected_moves/latest?_t=${Date.now()}`);
                    let hasLevels = false;
                    let globalMin = Infinity;
                    let globalMax = -Infinity;

                    if (resEM.ok) {
                        const emData = await resEM.json();
                        const tickersMap = emData.tickers || emData;

                        if (tickersMap && tickersMap[ticker] && tickersMap[ticker].expirations) {
                            const exps = tickersMap[ticker].expirations;

                            const addLevels = (expKey: string, label: string, colorHigh: string, colorLow: string, style: LineStyle) => {
                                const exp = exps[expKey];
                                if (exp && exp.upper_range && exp.lower_range) {
                                    hasLevels = true;
                                    globalMax = Math.max(globalMax, exp.upper_range);
                                    globalMin = Math.min(globalMin, exp.lower_range);
                                    priceSeries.createPriceLine({ price: exp.upper_range, color: colorHigh, lineWidth: 1, lineStyle: style, axisLabelVisible: true, title: `${label} High` });
                                    priceSeries.createPriceLine({ price: exp.lower_range, color: colorLow, lineWidth: 1, lineStyle: style, axisLabelVisible: true, title: `${label} Low` });
                                }
                            };

                            addLevels('ODTE', '0DTE', '#EF4444', '#22C55E', LineStyle.Dotted);
                            addLevels('WEEKLY', 'Weekly', '#EF4444', '#22C55E', LineStyle.Dashed);
                        }
                    }

                    // FALLBACK: If expected moves missing, use GEX profile range
                    if (!hasLevels && profile.length > 0) {
                        // Find min and max strike from profile
                        profile.forEach(p => {
                            if (p.strike > globalMax) globalMax = p.strike;
                            if (p.strike < globalMin) globalMin = p.strike;
                        });
                        hasLevels = true; // Use GEX range as truth
                        // Add buffer to GEX range so bars aren't cut off at edge
                        const gexHeight = globalMax - globalMin;
                        globalMax += gexHeight * 0.05;
                        globalMin -= gexHeight * 0.05;
                    }

                    if (hasLevels) {
                        const height = globalMax - globalMin;
                        const buffer = height * 0.15; // 15% buffer
                        const minLimit = globalMin - buffer;
                        const maxLimit = globalMax + buffer;

                        setChartLimits({ min: minLimit, max: maxLimit });

                        // Force Strict Scales
                        priceSeries.applyOptions({
                            autoscaleInfoProvider: () => ({
                                priceRange: {
                                    minValue: minLimit,
                                    maxValue: maxLimit
                                },
                                margins: {
                                    above: 0,
                                    below: 0,
                                }
                            })
                        });
                    }

                } catch (e) { console.error(e); }

                chart.timeScale().fitContent();

            } catch (e) { console.error(e); }
        };
        fetchEverything();

        chartRef.current = chart;
        priceSeriesRef.current = priceSeries;
        flowSeriesRef.current = flowSeries;

        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                    height: chartContainerRef.current.clientHeight
                });
            }
        };
        window.addEventListener('resize', handleResize);
        return () => { window.removeEventListener('resize', handleResize); chart.remove(); };
    }, [ticker]);

    // WebSocket logic (unchanged)
    useEffect(() => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/ws/theta`;
        let ws: WebSocket | null = null;
        let reconnectTimeout: ReturnType<typeof setTimeout>;

        const connect = () => {
            setConnectionStatus('Connecting...');
            ws = new WebSocket(wsUrl);

            ws.onopen = () => { setConnectionStatus('Connected (Streaming)'); setError(null); };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.error) return;
                    const time = data.time as number;
                    const price = data.price;

                    if (priceSeriesRef.current && price) {
                        priceSeriesRef.current.update({ time, value: price });
                    }
                    if (flowSeriesRef.current && data.hiro_flow !== undefined) {
                        flowSeriesRef.current.update({ time, value: data.hiro_flow });
                    }

                    if (price) {
                        const now = Date.now();
                        if (now - lastPriceUpdate.current > 1000) {
                            setCurrentPrice(price);
                            lastPriceUpdate.current = now;
                        }
                    }
                } catch (e) { }
            };

            ws.onclose = () => { setConnectionStatus('Disconnected'); reconnectTimeout = setTimeout(connect, 3000); };
        };

        connect();
        return () => { if (ws) ws.close(); clearTimeout(reconnectTimeout); };
    }, [ticker]);

    // Render Sidebar
    const renderSidebar = () => {
        if (!gexProfile || gexProfile.length === 0) return null;
        if (!chartLimits) return <div className="text-[10px] text-slate-500 p-2">Waiting for Levels...</div>;

        const minS = chartLimits.min;
        const maxS = chartLimits.max;
        const filtered = gexProfile.filter(p => p.strike >= minS && p.strike <= maxS);

        const maxNet = Math.max(...filtered.map(r => Math.abs(r.total_net_gex || 0)));
        const range = maxS - minS;

        return (
            <div className="relative w-full h-full overflow-hidden">
                {filtered.map((row) => {
                    const net = row.total_net_gex || 0;
                    const barWidth = maxNet > 0 ? (Math.abs(net) / maxNet) * 100 : 0;

                    // Top% Calculation
                    const topPct = ((maxS - row.strike) / range) * 100;

                    if (topPct < 0 || topPct > 98) return null; // Prevent bottom cutoff

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
                                    {net < 0 && (
                                        <div style={{ width: `${barWidth}%` }} className="h-full bg-red-500"></div>
                                    )}
                                </div>
                                <div className="flex-1 flex justify-start pl-0.5">
                                    {net > 0 && (
                                        <div style={{ width: `${barWidth}%` }} className="h-full bg-sky-500"></div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )
                })}

                {currentPrice && currentPrice >= minS && currentPrice <= maxS && (
                    <div
                        style={{ top: `${((maxS - currentPrice) / range) * 100}%` }}
                        className="absolute left-0 right-0 h-[1px] bg-white z-20 shadow-[0_0_8px_white]"
                    ></div>
                )}
            </div>
        );
    };

    return (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 shadow-sm flex flex-col h-[850px] relative">
            {/* Header */}
            <div className="flex justify-between items-center mb-4 shrink-0">
                <div>
                    <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse"></span>
                        Real-Time Dealer Flow (HIRO)
                    </h3>
                    <p className="text-xs text-slate-400">Streaming {ticker} via ThetaData</p>
                </div>
                <div className="flex items-center gap-3">
                    <div className={`text-xs px-2 py-1 rounded border ${connectionStatus.includes('Connected')
                        ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                        : 'bg-red-500/10 border-red-500/20 text-red-400'
                        }`}>
                        {connectionStatus}
                    </div>
                </div>
            </div>

            {error && (
                <div className="bg-red-900/50 border border-red-800 text-red-200 p-3 rounded mb-4 text-sm shrink-0">
                    {error}
                </div>
            )}

            {/* Headers Calculation for Alignment */}
            <div className="flex w-full mb-1 border-b border-slate-800 pb-1">
                {/* Sidebar Header Match */}
                <div className="w-[15%] flex justify-between px-2 text-[10px] text-slate-500 font-sans tracking-wide">
                    <span>Strike</span>
                    <span>Net GEX</span>
                </div>
                <div className="w-[85%] text-[10px] text-slate-500 pl-4 font-sans tracking-wide">
                    Price Action
                </div>
            </div>

            {/* Main Content Area: Sidebar + Chart */}
            <div className="flex flex-1 w-full min-h-0 relative">
                {/* GEX Sidebar (15%) */}
                <div className="w-[15%] bg-[#0F172A] border-r border-slate-800 relative select-none">
                    {renderSidebar()}
                </div>

                {/* Chart (85%) */}
                <div className="w-[85%] relative bg-[#0F172A]">
                    <div ref={chartContainerRef} className="w-full h-full" />
                </div>
            </div>

            {/* Legend */}
            <div className="mt-1 pb-1 px-2 border-t border-slate-800 pt-2 flex flex-wrap gap-4 text-[10px] text-slate-400 justify-center font-sans">
                <div className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 bg-white"></span>
                    <span>Price</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 bg-cyan-500"></span>
                    <span>Flow</span>
                </div>
                {/* Walls */}
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
                {/* Walls */}
                <div className="flex items-center gap-1.5 ml-2 border-l border-slate-700 pl-2">
                    <span className="w-3 h-0.5 bg-red-500"></span>
                    <span>Call Wall (Res)</span>
                </div>
                <div className="flex items-center gap-1.5">
                    <span className="w-3 h-0.5 bg-green-500"></span>
                    <span>Put Wall (Supp)</span>
                </div>
                {/* Expected Moves */}
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
