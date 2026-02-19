import React, { useEffect, useState, useRef, useMemo } from 'react';

// --- Components (Inline replacements for missing UI lib) ---

const Card = ({ children, className }) => (
    <div className={`rounded-lg border shadow-sm ${className}`}>
        {children}
    </div>
);

const Badge = ({ children, className, variant }) => (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ${className}`}>
        {children}
    </span>
);

const StatsCard = ({ title, value, subtext, color = "text-white" }) => (
    <Card className="p-4 bg-slate-900 border-slate-800">
        <div className="text-xs text-slate-400 font-medium uppercase tracking-wider mb-1">{title}</div>
        <div className={`text-2xl font-bold ${color}`}>{value}</div>
        {subtext && <div className="text-xs text-slate-500 mt-1">{subtext}</div>}
    </Card>
);

const SentimentGauge = ({ bullishPct }) => {
    // Determine dominant sentiment
    const isBullish = bullishPct >= 50;
    const value = isBullish ? bullishPct : (100 - bullishPct);
    const label = isBullish ? "Bullish" : "Bearish";
    const color = isBullish ? "text-green-400" : "text-red-400";
    const barColor = isBullish ? "bg-green-500" : "bg-red-500";

    return (
        <Card className="p-4 bg-slate-900 border-slate-800 flex flex-col justify-center">
            <div className="flex justify-between items-center mb-2">
                <span className="text-xs text-slate-400 font-medium uppercase">Flow Sentiment</span>
                <span className={`text-sm font-bold ${color}`}>
                    {value.toFixed(0)}% {label}
                </span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div
                    className={`${barColor} h-full transition-all duration-500`}
                    style={{ width: `${value}%` }}
                />
            </div>
            <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                <span>0%</span>
                <span>100%</span>
            </div>
        </Card>
    );
};

// --- Main Page ---

const AVAILABLE_TICKERS = ["SPY", "SPX", "QQQ", "IWM"];

export default function OptionFlowPage() {
    // State
    const [selectedTickers, setSelectedTickers] = useState(["SPY", "QQQ"]);
    const [minPremium, setMinPremium] = useState(100000);
    const [trades, setTrades] = useState([]);
    const [stats, setStats] = useState({});
    const [isConnected, setIsConnected] = useState(false);

    const wsRef = useRef(null);

    // Stats Aggregation (Computed from current selection stats)
    const aggregateStats = useMemo(() => {
        let callPrem = 0;
        let putPrem = 0;
        let netFlow = 0;

        selectedTickers.forEach(t => {
            const s = stats[t];
            if (s) {
                callPrem += s.call_prem;
                putPrem += s.put_prem;
                netFlow += s.net_flow;
            }
        });

        const totalPrem = callPrem + putPrem;
        const bullishPct = totalPrem > 0 ? (callPrem / totalPrem) * 100 : 50;

        const callPct = totalPrem > 0 ? (callPrem / totalPrem) * 100 : 0;
        const putPct = totalPrem > 0 ? (putPrem / totalPrem) * 100 : 0;

        return { callPrem, putPrem, netFlow, bullishPct, callPct, putPct };
    }, [selectedTickers, stats]);

    // WebSocket Connection
    useEffect(() => {
        console.log("DEBUG: OptionFlowPage Mount Effect");
        // Determine API URL (handle dev proxy automatically or explicit env)
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        // Assume standardized port or proxy
        const port = window.location.port ? `:${window.location.port}` : '';
        const wsUrl = `${protocol}//${host}${port}/api/ws/option-flow`;

        console.log("DEBUG: Connecting to WS:", wsUrl);

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log("Connected to Option Flow WS");
            setIsConnected(true);
            // Send Init Payload
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    action: "filter",
                    tickers: selectedTickers,
                    min_premium: minPremium
                }));
            }
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                // console.log("DEBUG: WS Message", msg.type);

                if (msg.type === "STATS_UPDATE") {
                    setStats(prev => ({ ...prev, ...msg.data }));
                } else if (msg.type === "SNAPSHOT_TRADES") {
                    setTrades(msg.trades.slice(-500)); // Limit initial size
                } else if (msg.type === "TRADE") {
                    // Filter out Stock/Index price updates (keep only Options)
                    if (msg.asset_type !== "OPTION") {
                        return;
                    }

                    // Detect Sentiment if missing (Basic Logic)
                    if (!msg.sentiment || msg.sentiment === "NEUTRAL") {
                        // Simple fallback: Calls=Bullish, Puts=Bearish (Visual Aid Only)
                        msg.sentiment = msg.right === 'C' ? 'BULLISH' : 'BEARISH';
                    }

                    setTrades(prev => {
                        const updated = [msg, ...prev];
                        if (updated.length > 500) updated.pop();
                        return updated;
                    });
                }
            } catch (e) {
                console.error("WS Parse Error", e);
            }
        };

        ws.onclose = () => {
            console.log("Option Flow WS Disconnected");
            setIsConnected(false);
        };

        return () => {
            ws.close();
        };
    }, []); // Only run once on mount

    // Filter Update Logic
    const sendFilterUpdate = (tickers, premium) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                action: "filter",
                tickers: tickers,
                min_premium: premium
            }));
        }
    };

    // Handlers
    const toggleTicker = (ticker) => {
        const newSelection = selectedTickers.includes(ticker)
            ? selectedTickers.filter(t => t !== ticker)
            : [...selectedTickers, ticker];

        setSelectedTickers(newSelection);
        sendFilterUpdate(newSelection, minPremium);
    };

    const handlePremiumChange = (e) => {
        const newVal = parseInt(e.target.value);
        setMinPremium(newVal);
    };

    const handlePremiumCommit = () => {
        sendFilterUpdate(selectedTickers, minPremium);
    }

    // Helper Formatters
    const fmtMoney = (val) => {
        val = Number(val) || 0;
        if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
        if (val >= 1000) return `$${(val / 1000).toFixed(1)}K`;
        return `$${val.toFixed(0)}`;
    };

    const fmtTime = (ts) => {
        return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    };

    return (
        <div className="min-h-screen bg-slate-950 text-slate-200 p-6 font-sans">
            {/* HEADER & FILTERS */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                    <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-400">
                        Real-Time Option Flow
                    </h1>
                    <div className="flex items-center gap-2 text-xs text-slate-500 mt-1">
                        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
                        {isConnected ? 'Connected to Theta Stream' : 'Disconnected'}
                    </div>
                </div>

                <div className="flex flex-wrap items-center gap-4 bg-slate-900/50 p-2 rounded-lg border border-slate-800">

                    {/* Ticker Selector */}
                    <div className="flex gap-1">
                        {AVAILABLE_TICKERS.map(t => (
                            <button
                                key={t}
                                onClick={() => toggleTicker(t)}
                                className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all ${selectedTickers.includes(t)
                                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
                                    : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                    }`}
                            >
                                {t}
                            </button>
                        ))}
                    </div>

                    <div className="h-6 w-px bg-slate-700 mx-2" />

                    {/* Premium Filter */}
                    <div className="flex items-center gap-3 min-w-[200px]">
                        <span className="text-xs text-slate-400 font-medium whitespace-nowrap">
                            Min Prem: <span className="text-white">{fmtMoney(minPremium)}</span>
                        </span>
                        <input
                            type="range"
                            min="0"
                            max="1000000"
                            step="10000"
                            value={minPremium}
                            onChange={handlePremiumChange}
                            onMouseUp={handlePremiumCommit}
                            onTouchEnd={handlePremiumCommit}
                            className="w-32 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                    </div>

                </div>
            </div>

            {/* STATS PANEL */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">

                <SentimentGauge bullishPct={aggregateStats.bullishPct} />

                <StatsCard
                    title="Net Flow"
                    value={fmtMoney(aggregateStats.netFlow)}
                    color={aggregateStats.netFlow >= 0 ? 'text-green-400' : 'text-red-400'}
                    subtext="Total Premium Delta"
                />

                <StatsCard
                    title="Call Premium"
                    value={fmtMoney(aggregateStats.callPrem)}
                    color="text-green-400"
                    subtext={`${aggregateStats.callPct.toFixed(0)}% of Total`}
                />

                <StatsCard
                    title="Put Premium"
                    value={fmtMoney(aggregateStats.putPrem)}
                    color="text-red-400"
                    subtext={`${aggregateStats.putPct.toFixed(0)}% of Total`}
                />

            </div>

            {/* TRADE TABLE */}
            <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-xl">
                <div className="p-3 border-b border-slate-800 bg-slate-900/50 flex justify-between items-center">
                    <h2 className="text-sm font-bold text-slate-300 flex items-center gap-2">
                        Live Trades
                    </h2>
                    <span className="text-xs text-slate-500">{trades.length} events capturing...</span>
                </div>


                <div className="overflow-x-auto max-h-[600px] overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                    <table className="w-full caption-bottom text-sm border-collapse">
                        <thead className="bg-slate-950 sticky top-0 z-10 shadow-sm">
                            <tr className="border-b border-slate-800 text-xs uppercase tracking-wider text-slate-500">
                                <th className="h-10 px-3 text-left font-medium w-[80px]">Time</th>
                                <th className="h-10 px-3 text-left font-medium w-[60px]">Ticker</th>
                                <th className="h-10 px-3 text-left font-medium">Exp</th>
                                <th className="h-10 px-3 text-left font-medium">Strike</th>
                                <th className="h-10 px-3 text-left font-medium">Spot</th>
                                <th className="h-10 px-3 text-left font-medium">Type</th>
                                <th className="h-10 px-3 text-left font-medium">Tags</th>
                                <th className="h-10 px-3 text-right font-medium">Size</th>
                                <th className="h-10 px-3 text-right font-medium">Price</th>
                                <th className="h-10 px-3 text-right font-medium">Value</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/50">
                            {trades.length === 0 ? (
                                <tr>
                                    <td colSpan={10} className="p-8 text-center text-slate-500 italic">
                                        Waiting for institutional flow (Min {fmtMoney(minPremium)})...
                                    </td>
                                </tr>
                            ) : (
                                trades.map((trade, i) => {
                                    // 1. Tags & Golden Logic
                                    const tags = trade.tags || [];
                                    const isSweep = tags.includes('SWEEP');
                                    const isBlock = tags.includes('BLOCK');
                                    const isSplit = tags.includes('SPLIT');

                                    const val = Number(trade.value) || 0;
                                    const isGolden = val > 1_000_000 && isSweep;

                                    // 2. Aggression / Side Coloring
                                    // Side: ASK (Aggressive Buy), BID (Aggressive Sell), MID (Neutral)
                                    const side = trade.side || 'MID';
                                    const isCall = trade.right === 'C';

                                    let rowTextClass = 'text-slate-300'; // Default

                                    if (side === 'ASK') {
                                        // Strong Aggression
                                        rowTextClass = isCall ? 'text-green-400 font-bold' : 'text-red-400 font-bold';
                                    } else if (side === 'BID') {
                                        // Passive / Selling into Bid
                                        rowTextClass = isCall ? 'text-green-800/70' : 'text-red-800/70';
                                    } else {
                                        // Mid / Neutral
                                        rowTextClass = isCall ? 'text-green-200/60' : 'text-red-200/60';
                                    }

                                    // Row Background (Golden or Standard)
                                    const rowBg = isGolden
                                        ? 'bg-amber-500/10 hover:bg-amber-500/20 shadow-[inset_2px_0_0_0_#fbbf24]'
                                        : 'hover:bg-slate-800/30';

                                    // Safety
                                    const safeSpot = Number(trade.spot) || 0;
                                    const safePrice = Number(trade.price) || 0;
                                    const safeTime = trade.time ? fmtTime(trade.time) : '--:--';
                                    const count = trade.count || 1;

                                    return (
                                        <tr key={`${trade.time}-${i}`} className={`transition-colors text-xs ${rowBg}`}>
                                            <td className="p-3 font-mono text-slate-500">{safeTime}</td>
                                            <td className={`p-3 font-bold ${rowTextClass}`}>{trade.root}</td>
                                            <td className="p-3 text-slate-400">{trade.exp}</td>
                                            <td className="p-3 font-mono text-slate-300">{trade.strike}</td>
                                            <td className="p-3 font-mono text-slate-500">{safeSpot.toFixed(2)}</td>
                                            <td className="p-3">
                                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${isCall
                                                    ? 'bg-green-950/30 border-green-900 text-green-500'
                                                    : 'bg-red-950/30 border-red-900 text-red-500'}`}>
                                                    {isCall ? 'CALL' : 'PUT'}
                                                </span>
                                            </td>
                                            <td className="p-3 flex gap-1 flex-wrap max-w-[120px]">
                                                {isSweep && <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-900/50 text-purple-300 border border-purple-800">SWEEP</span>}
                                                {isBlock && <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-blue-900/50 text-blue-300 border border-blue-800">BLOCK</span>}
                                                {isSplit && <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-700 text-slate-300 border border-slate-600">SPLIT</span>}
                                            </td>
                                            <td
                                                className="p-3 text-right font-mono text-slate-300 cursor-help"
                                                title={`Aggregated from ${count} prints`}
                                            >
                                                {trade.size}
                                                {count > 1 && <span className="text-[9px] text-slate-600 ml-0.5 align-top">x{count}</span>}
                                            </td>
                                            <td className="p-3 text-right font-mono text-slate-400">${safePrice.toFixed(2)}</td>
                                            <td className={`p-3 text-right font-bold font-mono ${isGolden ? 'text-amber-300' : 'text-slate-200'}`}>
                                                {fmtMoney(val)}
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
