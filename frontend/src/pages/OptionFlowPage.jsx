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

const SentimentGauge = ({ bullishPct }) => (
    <Card className="p-4 bg-slate-900 border-slate-800 flex flex-col justify-center">
        <div className="flex justify-between items-center mb-2">
            <span className="text-xs text-slate-400 font-medium uppercase">Flow Sentiment</span>
            <span className={`text-sm font-bold ${bullishPct >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                {bullishPct.toFixed(0)}% Bullish
            </span>
        </div>
        <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
            <div
                className="bg-green-500 h-full transition-all duration-500"
                style={{ width: `${bullishPct}%` }}
            />
        </div>
        <div className="flex justify-between text-[10px] text-slate-500 mt-1">
            <span>Bearish</span>
            <span>Bullish</span>
        </div>
    </Card>
);

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

        return { callPrem, putPrem, netFlow, bullishPct };
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
                />

                <StatsCard
                    title="Put Premium"
                    value={fmtMoney(aggregateStats.putPrem)}
                    color="text-red-400"
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
                    <table className="w-full caption-bottom text-sm">
                        <thead className="[&_tr]:border-b border-slate-800 bg-slate-950 sticky top-0 z-10">
                            <tr className="border-b transition-colors hover:bg-transparent data-[state=selected]:bg-muted border-slate-800">
                                <th className="h-10 px-2 text-left align-middle font-medium text-slate-400 w-[80px]">Time</th>
                                <th className="h-10 px-2 text-left align-middle font-medium text-slate-400 w-[60px]">Ticker</th>
                                <th className="h-10 px-2 text-left align-middle font-medium text-slate-400">Expiration</th>
                                <th className="h-10 px-2 text-left align-middle font-medium text-slate-400">Strike</th>
                                <th className="h-10 px-2 text-left align-middle font-medium text-slate-400">Spot</th>
                                <th className="h-10 px-2 text-left align-middle font-medium text-slate-400">C/P</th>
                                <th className="h-10 px-2 text-right align-middle font-medium text-slate-400">Size</th>
                                <th className="h-10 px-2 text-right align-middle font-medium text-slate-400">Price</th>
                                <th className="h-10 px-2 text-right align-middle font-medium text-slate-400">Value</th>
                                <th className="h-10 px-2 text-left align-middle font-medium text-slate-400 w-[40px]"></th>
                            </tr>
                        </thead>
                        <tbody className="[&_tr:last-child]:border-0">
                            {trades.length === 0 ? (
                                <tr>
                                    <td colSpan={10} className="p-4 text-center py-10 text-slate-500">
                                        Waiting for trades matching filter (Min {fmtMoney(minPremium)})...
                                    </td>
                                </tr>
                            ) : (
                                trades.map((trade, i) => {
                                    const isBullish = trade.sentiment === 'BULLISH';
                                    const rowColor = isBullish
                                        ? 'bg-green-950/10 hover:bg-green-900/20 text-green-100'
                                        : 'bg-red-950/10 hover:bg-red-900/20 text-red-100';

                                    // Safety Helpers
                                    const safeSpot = Number(trade.spot) || 0;
                                    const safePrice = Number(trade.price) || 0;
                                    const safeValue = Number(trade.value) || 0;
                                    const safeTime = trade.time ? fmtTime(trade.time) : '--:--';

                                    return (
                                        <tr key={`${trade.time}-${i}`} className={`border-b border-slate-800/50 ${rowColor} transition-colors`}>
                                            <td className="p-2 align-middle font-mono text-xs text-slate-400">
                                                {safeTime}
                                            </td>
                                            <td className="p-2 align-middle font-bold">{trade.root}</td>
                                            <td className="p-2 align-middle text-xs">{trade.exp}</td>
                                            <td className="p-2 align-middle font-mono">{trade.strike}</td>
                                            <td className="p-2 align-middle text-slate-400 text-xs">{safeSpot.toFixed(2)}</td>
                                            <td className="p-2 align-middle">
                                                <Badge variant="outline" className={`text-[10px] h-5 border-0 font-bold ${trade.right === 'C' ? 'bg-green-900/40 text-green-400' : 'bg-red-900/40 text-red-400'
                                                    }`}>
                                                    {trade.right === 'C' ? 'CALL' : 'PUT'}
                                                </Badge>
                                            </td>
                                            <td className="p-2 align-middle text-right font-mono">{trade.size}</td>
                                            <td className="p-2 align-middle text-right font-mono text-slate-300">${safePrice.toFixed(2)}</td>
                                            <td className="p-2 align-middle text-right font-bold text-white">
                                                {fmtMoney(safeValue)}
                                            </td>
                                            <td className="p-2 align-middle">
                                                {trade.sweep && (
                                                    <span className="text-yellow-400 text-xs font-bold">SWEEP</span>
                                                )}
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
