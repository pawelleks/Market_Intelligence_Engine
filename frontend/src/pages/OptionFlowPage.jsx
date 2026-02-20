import React, { useEffect, useState, useRef, useMemo } from 'react';

// Global blink animation style injected once
const BLINK_STYLE = `
@keyframes rowBlink {
  0%   { background-color: rgba(20, 184, 166, 0.35); }
  60%  { background-color: rgba(20, 184, 166, 0.15); }
  100% { background-color: transparent; }
}
.row-blink { animation: rowBlink 1.2s ease-out forwards; }
`;
if (typeof document !== 'undefined' && !document.getElementById('of-blink-style')) {
    const s = document.createElement('style');
    s.id = 'of-blink-style';
    s.textContent = BLINK_STYLE;
    document.head.appendChild(s);
}

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

const CircularProgress = ({ value, size = 64, strokeWidth = 5, colorClass = "text-blue-500", label }) => {
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (Math.min(value, 100) / 100) * circumference;
    const displayLabel = label !== undefined ? label : `${Math.round(value)}%`;

    return (
        <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
            <svg className="transform -rotate-90 w-full h-full">
                <circle
                    cx="50%"
                    cy="50%"
                    r={radius}
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    fill="transparent"
                    className="text-slate-800"
                />
                <circle
                    cx="50%"
                    cy="50%"
                    r={radius}
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    fill="transparent"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    strokeLinecap="round"
                    className={`${colorClass} transition-all duration-1000 ease-out`}
                />
            </svg>
            <span className="absolute text-[11px] font-bold text-slate-300">
                {displayLabel}
            </span>
        </div>
    );
};

const StatsCard = ({ title, value, secondaryValue, color = "text-white", percentage, isRatio, chartValue }) => (
    <Card className="p-4 bg-black/40 border-slate-800 flex flex-col justify-between h-full hover:bg-black/60 transition-colors">
        <div className="flex justify-between items-start mb-4">
            <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">{title}</div>
            {secondaryValue && <div className={`text-sm font-bold ${color}`}>{secondaryValue}</div>}
        </div>

        <div className="flex justify-between items-end">
            <div className="text-2xl font-bold text-white">{value}</div>
            {percentage !== undefined && (
                <div className="ml-2">
                    <CircularProgress
                        value={chartValue !== undefined ? chartValue : percentage}
                        colorClass={color}
                        label={isRatio}
                    />
                </div>
            )}
        </div>
    </Card>
);

const SentimentGauge = ({ bullishPct }) => {
    // Thresholds: ≥60% calls → Bullish, 40–60% → Neutral, ≤40% → Bearish
    const isBullish = bullishPct >= 60;
    const isBearish = bullishPct <= 40;
    const label = isBullish ? "Bullish" : (isBearish ? "Bearish" : "Neutral");
    const color = isBullish ? "text-green-400" : (isBearish ? "text-red-400" : "text-slate-400");
    const barColor = isBullish ? "bg-green-500" : (isBearish ? "bg-red-500" : "bg-slate-500");
    // Bar width: distance from 50% midpoint, scaled to fill bar meaningfully
    const barWidth = Math.abs(bullishPct - 50) * 2; // 0–100

    return (
        <Card className="p-4 bg-black/40 border-slate-800 flex flex-col justify-center h-full hover:bg-black/60 transition-colors">
            <div className="flex justify-between items-center mb-4">
                <span className="text-xs text-slate-400 font-medium uppercase tracking-wider">Sentiment</span>
                <span className={`text-sm font-bold ${color}`}>
                    {bullishPct.toFixed(0)}% {label}
                </span>
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mb-2">
                <div
                    className={`${barColor} h-full transition-all duration-1000 ease-out`}
                    style={{ width: `${barWidth}%` }}
                />
            </div>
            <div className="flex justify-between text-[9px] text-slate-500 uppercase tracking-tighter">
                <span>Bearish</span>
                <span>Bullish</span>
            </div>
        </Card>
    );
};

// --- Main Page ---

const AVAILABLE_TICKERS = ["SPY", "SPX", "QQQ", "IWM"];

export default function OptionFlowPage() {
    // State
    const [selectedTicker, setSelectedTicker] = useState("SPY");
    const [minPremium, setMinPremium] = useState(100000);
    const [trades, setTrades] = useState([]);
    const [stats, setStats] = useState({});
    const [isConnected, setIsConnected] = useState(false);
    const [isLoadingHistory, setIsLoadingHistory] = useState(true);

    // History mode
    const [mode, setMode] = useState('LIVE');           // 'LIVE' | 'HISTORY'
    const [wsKey, setWsKey] = useState(0);              // increment to force WS reconnect
    const [availableDates, setAvailableDates] = useState([]);
    const [selectedDate, setSelectedDate] = useState(null);
    const [historyStats, setHistoryStats] = useState(null);

    const wsRef = useRef(null);
    // Ephemeral set of row keys currently in the blink animation window
    const [blinkKeys, setBlinkKeys] = useState(new Set());
    const blinkTimersRef = useRef([]);
    // How To Read modal
    const [showHelp, setShowHelp] = useState(false);

    // Stats for the single selected ticker
    const aggregateStats = useMemo(() => {
        const s = stats[selectedTicker];
        const callPrem = s?.call_prem || 0;
        const putPrem = s?.put_prem || 0;
        const callVol = s?.call_vol || 0;
        const putVol = s?.put_vol || 0;
        const netFlow = s?.net_flow || 0;

        const totalPrem = callPrem + putPrem;
        const bullishPct = totalPrem > 0 ? (callPrem / totalPrem) * 100 : 50;
        const callPct = totalPrem > 0 ? (callPrem / totalPrem) * 100 : 0;
        const putPct = totalPrem > 0 ? (putPrem / totalPrem) * 100 : 0;
        const pcr = callVol > 0 ? (putVol / callVol) : 0;

        return { callPrem, putPrem, callVol, putVol, netFlow, bullishPct, callPct, putPct, pcr };
    }, [selectedTicker, stats]);

    // Transparently switch stats source based on mode
    const displayStats = (mode === 'HISTORY' && historyStats) ? historyStats : aggregateStats;

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
                    tickers: [selectedTicker],
                    min_premium: minPremium
                }));
            }
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);

                if (msg.type === "STATS_UPDATE") {
                    setStats(prev => ({ ...prev, ...msg.data }));
                } else if (msg.type === "history") {
                    // Bulk load history from SQLite — reverse so newest is at top
                    const raw = msg.trades.slice(-1000);
                    raw.reverse();
                    setTrades(raw);
                    setIsLoadingHistory(false);
                } else if (msg.type === "SNAPSHOT_TRADES") {
                    // Legacy/Fallback snapshot — reverse so newest is at top
                    const raw = msg.trades.slice(-500);
                    raw.reverse();
                    setTrades(raw);
                    setIsLoadingHistory(false);
                } else if (msg.type === "trade" || msg.type === "TRADE") {
                    // Real-time Trade — prepend with blink flag
                    if (msg.asset_type !== "OPTION") {
                        return;
                    }

                    // Detect Sentiment if missing (Basic Logic)
                    if (!msg.sentiment || msg.sentiment === "NEUTRAL") {
                        msg.sentiment = msg.right === 'C' ? 'BULLISH' : 'BEARISH';
                    }

                    const tradeKey = `${msg.timestamp ?? Date.now()}-${Math.random()}`;

                    setTrades(prev => {
                        const updated = [{ ...msg, _rowKey: tradeKey }, ...prev];
                        if (updated.length > 500) updated.pop();
                        return updated;
                    });

                    // Schedule blink: add key now, remove after animation completes
                    setBlinkKeys(prev => new Set([...prev, tradeKey]));
                    const timer = setTimeout(() => {
                        setBlinkKeys(prev => { const next = new Set(prev); next.delete(tradeKey); return next; });
                    }, 1300);
                    blinkTimersRef.current.push(timer);
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
            // Clear any pending blink timers on cleanup
            blinkTimersRef.current.forEach(clearTimeout);
            blinkTimersRef.current = [];
        };
    }, [wsKey]); // wsKey increments on LIVE mode re-entry to force reconnect

    // Filter Update Logic
    const sendFilterUpdate = (ticker, premium) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                action: "filter",
                tickers: [ticker],
                min_premium: premium
            }));
        }
    };

    // Single-select: clicking an already-active ticker is a no-op
    const selectTicker = (ticker) => {
        if (ticker === selectedTicker) return;
        setSelectedTicker(ticker);
        sendFilterUpdate(ticker, minPremium);
    };

    const handlePremiumChange = (e) => {
        const newVal = parseInt(e.target.value);
        setMinPremium(newVal);
    };

    const handlePremiumCommit = () => {
        sendFilterUpdate(selectedTicker, minPremium);
    }

    // -- Mode switching --
    const switchToHistory = () => {
        wsRef.current?.close();
        setIsConnected(false);
        setMode('HISTORY');
        setTrades([]);
        setHistoryStats(null);
    };

    const switchToLive = () => {
        setMode('LIVE');
        setHistoryStats(null);
        setSelectedDate(null);
        setTrades([]);
        setWsKey(k => k + 1);  // triggers fresh WS connection via useEffect([wsKey])
    };

    // -- History: fetch available dates when entering HISTORY mode --
    useEffect(() => {
        if (mode !== 'HISTORY') return;
        fetch('/api/option-flow/dates')
            .then(r => r.json())
            .then(data => {
                const dates = data.dates || [];
                setAvailableDates(dates);
                if (dates.length > 0) setSelectedDate(d => d || dates[0]);
            })
            .catch(console.error);
    }, [mode]);

    // -- History: fetch trades + stats whenever date / ticker / premium change --
    useEffect(() => {
        if (mode !== 'HISTORY' || !selectedDate) return;
        setIsLoadingHistory(true);
        fetch(`/api/option-flow/history?date=${selectedDate}&ticker=${selectedTicker}&min_premium=${minPremium}`)
            .then(r => r.json())
            .then(data => {
                setTrades((data.trades || []).slice().reverse());
                const s = data.stats || {};
                const cp = s.call_prem || 0;
                const pp = s.put_prem || 0;
                const total = cp + pp;
                setHistoryStats({
                    bullishPct: total > 0 ? (cp / total) * 100 : 50,
                    callPrem: cp,
                    putPrem: pp,
                    netFlow: s.net_flow || 0,
                    callVol: s.call_vol || 0,
                    putVol: s.put_vol || 0,
                    callPct: total > 0 ? (cp / total) * 100 : 0,
                    putPct: total > 0 ? (pp / total) * 100 : 0,
                    pcr: (s.call_vol || 0) > 0 ? (s.put_vol || 0) / s.call_vol : 0,
                });
                setIsLoadingHistory(false);
            })
            .catch(() => setIsLoadingHistory(false));
    }, [mode, selectedDate, selectedTicker, minPremium]);

    // Helper Formatters
    const fmtMoney = (val) => {
        val = Number(val) || 0;
        const absVal = Math.abs(val);
        const prefix = val < 0 ? '-$' : '$';
        if (absVal >= 1000000) return `${prefix}${(absVal / 1000000).toFixed(1)}M`;
        if (absVal >= 1000) return `${prefix}${(absVal / 1000).toFixed(1)}K`;
        return `${prefix}${absVal.toFixed(0)}`;
    };

    const fmtNumber = (val) => {
        return new Intl.NumberFormat().format(val || 0);
    };

    const fmtTime = (ts) => {
        if (!ts) return '--:--';
        let ms;
        // Case 1: ISO String or Date String
        if (typeof ts === 'string') {
            const d = new Date(ts);
            if (isNaN(d.getTime())) return '--:--';
            ms = d.getTime();
        } else {
            // Case 2: Number (Auto-detect: values > 1e11 are milliseconds)
            ms = ts > 1_000_000_000_000 ? ts : ts * 1000;
        }
        // No explicit timeZone → browser local time
        return new Date(ms).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    };

    // Helper: format session date for display (e.g. "Feb 19, 2026")
    const fmtDate = (d) => {
        if (!d) return '';
        const [y, m, day] = d.split('-');
        return new Date(Number(y), Number(m) - 1, Number(day))
            .toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };

    return (
        <div className="h-screen flex flex-col bg-slate-950 text-slate-200 p-6 font-sans overflow-hidden">

            {/* HOW TO READ MODAL */}
            {showHelp && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={() => setShowHelp(false)}>
                    <div className="relative bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-6 max-w-xl w-full mx-4" onClick={e => e.stopPropagation()}>
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-lg font-bold text-slate-100">How To Read Option Flow</h2>
                            <button onClick={() => setShowHelp(false)} className="text-slate-400 hover:text-white transition-colors text-xl leading-none">&times;</button>
                        </div>

                        <p className="text-xs text-slate-400 mb-4">Each row is a significant options transaction detected in the market. Here's what each column means:</p>

                        <table className="w-full text-xs border-collapse mb-5">
                            <thead>
                                <tr className="border-b border-slate-700 text-slate-400 uppercase tracking-wider">
                                    <th className="pb-2 text-left font-medium w-1/4">Field</th>
                                    <th className="pb-2 text-left font-medium">Meaning</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800">
                                {[
                                    ['Tags: BLOCK', 'Single contract printed 200+ times in one 10s window — large institutional order.'],
                                    ['Tags: SWEEP', '30+ contracts traded at $150k+ premium — aggressive cross-exchange activity.'],
                                    ['Side: BOUGHT', 'Option price rose vs prev poll — buyer was the aggressor (paid the ask).'],
                                    ['Side: SOLD', 'Option price fell vs prev poll — seller was the aggressor (hit the bid).'],
                                    ['Side: MID', 'Price was flat — trade likely negotiated at mid, no clear direction.'],
                                    ['Sentiment', 'BULLISH = Call option bought. BEARISH = Put option bought.'],
                                    ['Premium', 'Total dollar value of the trade: Price × Contracts × 100.'],
                                    ['Contracts', 'Number of option contracts traded. 1 contract = 100 shares.'],
                                    ['Time', 'Your local time when the trade was detected.'],
                                ].map(([field, desc]) => (
                                    <tr key={field}>
                                        <td className="py-2 pr-4 font-semibold text-slate-300 whitespace-nowrap">{field}</td>
                                        <td className="py-2 text-slate-400">{desc}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        <p className="text-xs font-semibold text-slate-300 mt-5 mb-2">Expiry Coverage</p>
                        <table className="w-full text-xs border-collapse mb-5">
                            <thead>
                                <tr className="border-b border-slate-700 text-slate-400 uppercase tracking-wider">
                                    <th className="pb-2 text-left font-medium w-1/4">Ticker</th>
                                    <th className="pb-2 text-left font-medium">Expiry Type</th>
                                    <th className="pb-2 text-left font-medium">Coverage (10 expirations)</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800">
                                {[
                                    ['SPXW', 'Daily (every trading day)', '~2 trading weeks'],
                                    ['SPY', 'Mon / Wed / Fri weeklies', '~3–4 weeks'],
                                    ['QQQ / IWM', 'Weekly + Monthly', '~2–3 months'],
                                ].map(([ticker, type, coverage]) => (
                                    <tr key={ticker}>
                                        <td className="py-2 pr-4 font-semibold text-slate-300">{ticker}</td>
                                        <td className="py-2 text-slate-400">{type}</td>
                                        <td className="py-2 text-slate-400">{coverage}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>

                        <p className="text-[10px] text-slate-500 italic">Note: Tags and Side are heuristic estimates derived from volume and price changes between poll intervals. Real-time TCP stream data will provide exact OPRA condition codes.</p>
                    </div>
                </div>
            )}

            {/* HEADER & FILTERS */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4">
                <div>
                    <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-400">
                        {mode === 'HISTORY' ? 'Historical Option Flow' : 'Real-Time Option Flow'}
                    </h1>
                    <div className="flex items-center gap-2 text-xs text-slate-500 mt-1">
                        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-slate-600'}`} />
                        {mode === 'LIVE'
                            ? (isConnected ? 'Connected to Theta Stream' : 'Disconnected')
                            : 'Read-only — historical data'}
                    </div>
                </div>

                <div className="flex flex-wrap items-center gap-4">

                    {/* LIVE / HISTORY mode toggle */}
                    <div className="flex gap-1 bg-slate-900/50 p-1 rounded-lg border border-slate-800">
                        <button
                            onClick={switchToLive}
                            className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all ${mode === 'LIVE'
                                ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
                                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                }`}
                        >
                            LIVE
                        </button>
                        <button
                            onClick={switchToHistory}
                            className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all ${mode === 'HISTORY'
                                ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
                                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                }`}
                        >
                            HISTORY
                        </button>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 bg-slate-900/50 p-2 rounded-lg border border-slate-800">

                        {/* Ticker Selector */}
                        <div className="flex gap-1">
                            {AVAILABLE_TICKERS.map(t => (
                                <button
                                    key={t}
                                    onClick={() => selectTicker(t)}
                                    className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all ${selectedTicker === t
                                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
                                        : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                        }`}
                                >
                                    {t}
                                </button>
                            ))}
                        </div>

                        <div className="h-6 w-px bg-slate-700 mx-2" />

                        {/* History date dropdown (HISTORY mode only) */}
                        {mode === 'HISTORY' && (
                            <select
                                value={selectedDate || ''}
                                onChange={e => setSelectedDate(e.target.value)}
                                className="bg-slate-800 text-slate-200 text-xs font-medium rounded-md px-3 py-1.5 border border-slate-700 cursor-pointer focus:outline-none focus:ring-1 focus:ring-blue-500"
                            >
                                {availableDates.length === 0 && (
                                    <option value="">Loading dates...</option>
                                )}
                                {availableDates.map(d => (
                                    <option key={d} value={d}>{fmtDate(d)}</option>
                                ))}
                            </select>
                        )}

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
            </div>

            {/* HISTORY MODE BANNER */}
            {mode === 'HISTORY' && selectedDate && (
                <div className="flex items-center gap-2 mb-4 px-4 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-medium">
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Viewing: {fmtDate(selectedDate)} — Read Only
                </div>
            )}

            {/* STATS PANEL */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">

                <SentimentGauge bullishPct={displayStats.bullishPct} />

                <StatsCard
                    title="Put to call"
                    value={displayStats.pcr.toFixed(3)}
                    color="text-blue-400"
                    percentage={displayStats.pcr * 100}
                    chartValue={displayStats.pcr * 100}
                    isRatio={displayStats.pcr.toFixed(2)}
                />

                <StatsCard
                    title="Call flow"
                    secondaryValue={fmtMoney(displayStats.callPrem)}
                    color="text-green-500"
                    percentage={displayStats.callPct}
                />

                <StatsCard
                    title="Put flow"
                    secondaryValue={fmtMoney(displayStats.putPrem)}
                    color="text-red-500"
                    percentage={displayStats.putPct}
                />

                <StatsCard
                    title="Net flow"
                    value={fmtMoney(displayStats.netFlow)}
                    color={displayStats.netFlow >= 0 ? "text-green-400" : "text-red-400"}
                />

            </div>

            {/* TRADE TABLE */}
            <div className="flex flex-col flex-1 min-h-0 w-full bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-xl">
                <div className="p-3 border-b border-slate-800 bg-slate-900/50 flex justify-between items-center shrink-0">
                    <h2 className="text-sm font-bold text-slate-300 flex items-center gap-2">
                        {mode === 'HISTORY' ? `Trades — ${fmtDate(selectedDate)}` : 'Live Trades'}
                    </h2>
                    <div className="flex items-center gap-3">
                        <span className="text-xs text-slate-500">
                            {isLoadingHistory
                                ? (mode === 'HISTORY' ? 'Loading historical trades...' : 'Syncing intraday database...')
                                : `${trades.length} ${mode === 'HISTORY' ? 'trades' : 'events capturing...'}`
                            }
                        </span>
                        <button
                            onClick={() => setShowHelp(true)}
                            className="text-[11px] text-slate-400 hover:text-blue-400 underline underline-offset-2 transition-colors whitespace-nowrap"
                        >How to read?</button>
                    </div>
                </div>


                <div className="flex-1 min-h-0 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                    <table className="w-full caption-bottom text-sm border-collapse">
                        <thead className="bg-slate-950 sticky top-0 z-10 shadow-sm">
                            <tr className="border-b border-slate-800 text-xs uppercase tracking-wider text-slate-500">
                                <th className="h-10 px-3 text-left font-medium">Ticker</th>
                                <th className="h-10 px-3 text-left font-medium">Exp</th>
                                <th className="h-10 px-3 text-left font-medium">Strike</th>
                                <th className="h-10 px-3 text-left font-medium">Type</th>
                                <th className="h-10 px-3 text-left font-medium">Tags</th>
                                <th className="h-10 px-3 text-left font-medium">Side</th>
                                <th className="h-10 px-3 text-left font-medium">Sentiment</th>
                                <th className="h-10 px-3 text-right font-medium">Price</th>
                                <th className="h-10 px-3 text-right font-medium">Premium</th>
                                <th className="h-10 px-3 text-right font-medium">Contracts</th>
                                <th className="h-10 px-3 text-right font-medium w-[80px]">Time</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/50">
                            {trades.length === 0 ? (
                                <tr>
                                    <td colSpan={11} className="p-8 text-center text-slate-500 italic font-mono text-xs">
                                        {isLoadingHistory ? (
                                            <span className="flex items-center justify-center gap-2">
                                                <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                                                Replaying today's institutional activity...
                                            </span>
                                        ) : (
                                            `No flow detected meeting $${fmtNumber(minPremium)} threshold.`
                                        )}
                                    </td>
                                </tr>
                            ) : (
                                trades.filter(trade => trade.root === selectedTicker).map((trade, i) => {
                                    const val = Number(trade.value) || 0;
                                    const side = trade.side || 'MID';
                                    const isCall = trade.right === 'C';
                                    const isGolden = val > 1_000_000 && trade.tags?.includes('SWEEP');

                                    // Side: map raw values to trader-friendly labels
                                    const sideLabel = { ASK: 'BOUGHT', BID: 'SOLD', MID: 'MID' }[side] || 'MID';
                                    const sideColor = { ASK: 'text-green-400', BID: 'text-red-400', MID: 'text-slate-400' }[side] || 'text-slate-400';

                                    const rowBg = isGolden
                                        ? 'bg-amber-500/10 hover:bg-amber-500/20'
                                        : 'hover:bg-white/[0.02]';

                                    const safePrice = Number(trade.price) || 0;
                                    // Prefer trade.timestamp (Unix ms, set by TradeProcessor) — fall back to trade.time
                                    const rawTs = trade.timestamp ?? trade.time;
                                    const safeTime = rawTs ? fmtTime(rawTs) : '--:--';

                                    // Tags badge — show first tag only
                                    const firstTag = trade.tags?.[0];
                                    const tagStyles = {
                                        SWEEP: 'bg-orange-500/20 text-orange-300 border border-orange-500/30',
                                        BLOCK: 'bg-purple-500/20 text-purple-300 border border-purple-500/30',
                                        SPLIT: 'bg-blue-500/20 text-blue-300 border border-blue-500/30',
                                    };
                                    const tagClass = firstTag
                                        ? (tagStyles[firstTag] || 'bg-slate-700/40 text-slate-400 border border-slate-600/30')
                                        : '';

                                    // Sentiment badge
                                    const sentiment = trade.sentiment || (trade.right === 'C' ? 'BULLISH' : 'BEARISH');

                                    return (
                                        <tr
                                            key={`${trade.time}-${i}`}
                                            className={`transition-colors text-xs border-b border-slate-800/30 ${rowBg} ${blinkKeys.has(trade._rowKey) ? 'row-blink' : ''}`}
                                        >
                                            <td className="p-3 font-bold text-white">{trade.root}</td>
                                            <td className="p-3 text-slate-400">{trade.exp}</td>
                                            <td className="p-3 font-mono text-slate-300">{trade.strike}</td>
                                            <td className="p-3">
                                                <span className={`font-bold ${isCall ? 'text-green-500' : 'text-red-500'}`}>
                                                    {isCall ? 'CALL' : 'PUT'}
                                                </span>
                                            </td>
                                            <td className="p-3">
                                                {firstTag && (
                                                    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wider ${tagClass}`}>
                                                        {firstTag}
                                                    </span>
                                                )}
                                            </td>
                                            <td className={`p-3 font-bold ${sideColor}`}>{sideLabel}</td>
                                            <td className="p-3">
                                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${sentiment === 'BULLISH'
                                                    ? 'bg-green-500/15 text-green-400'
                                                    : sentiment === 'BEARISH'
                                                        ? 'bg-red-500/15 text-red-400'
                                                        : 'text-slate-500'
                                                    }`}>
                                                    {sentiment || '—'}
                                                </span>
                                            </td>
                                            <td className="p-3 text-right font-mono text-slate-300">{safePrice.toFixed(2)}</td>
                                            <td className={`p-3 text-right font-bold ${isCall ? 'text-green-400' : 'text-red-400'}`}>
                                                {fmtMoney(val)}
                                            </td>
                                            <td className="p-3 text-right font-mono text-slate-600 text-[10px]">
                                                {trade.size ? fmtNumber(trade.size) : '—'}
                                            </td>
                                            <td className="p-3 text-right font-mono text-slate-500">{safeTime}</td>
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
