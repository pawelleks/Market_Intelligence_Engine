import React, { useState, useEffect, useRef } from 'react';

interface VolumeRegimeTableProps {
    ticker: string;
    refreshInterval?: number;
    onStateChange?: (changes: { timeframe: string; oldState: string; newState: string }[]) => void;
}

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"];

const STATE_COLORS: Record<string, string> = {
    "Accumulation": "#4caf50",
    "Distribution": "#f44336",
    "Capitulation": "#ff6d00",
    "Consolidation": "#3b82f6",
    "Neutral": "#94a3b8",
    "Insufficient Data": "#64748b",
    "Unavailable": "#64748b"
};

export const VolumeRegimeTable: React.FC<VolumeRegimeTableProps> = React.memo(({
    ticker,
    refreshInterval = 30000,
    onStateChange
}) => {
    const [data, setData] = useState<Record<string, any>>({});
    const [loading, setLoading] = useState<boolean>(true);
    const [lastUpdate, setLastUpdate] = useState<string>('');
    const prevDataRef = useRef<Record<string, any>>({});

    // Track which cells have recently updated to flash them
    const [flashingKeys, setFlashingKeys] = useState<Set<string>>(new Set());

    useEffect(() => {
        let isMounted = true;
        let timer: ReturnType<typeof setInterval>;

        const fetchData = async () => {
            try {
                const res = await fetch(`/api/volume-regime/snapshot/${ticker}`);
                if (!res.ok) throw new Error('Network response was not ok');

                const json = await res.json();

                if (isMounted && json.snapshot) {
                    // Check for changes to trigger flash animation
                    const newFlashing = new Set<string>();
                    const stateChanges: { timeframe: string; oldState: string; newState: string }[] = [];

                    if (Object.keys(prevDataRef.current).length > 0) {
                        for (const tf of TIMEFRAMES) {
                            const oldState = prevDataRef.current[tf]?.state;
                            const newState = json.snapshot[tf]?.state;

                            // Flash if the regime state changed (and we're not just loading for the first time)
                            if (oldState !== undefined && oldState !== newState) {
                                newFlashing.add(tf);
                                stateChanges.push({ timeframe: tf, oldState: oldState || "None", newState: newState });
                            }
                        }
                    }

                    if (stateChanges.length > 0 && onStateChange) {
                        onStateChange(stateChanges);
                    }

                    if (newFlashing.size > 0) {
                        setFlashingKeys(newFlashing);
                        // clear flash after 500ms
                        setTimeout(() => {
                            if (isMounted) setFlashingKeys(new Set());
                        }, 500);
                    }

                    prevDataRef.current = json.snapshot;
                    setData(json.snapshot);
                    setLastUpdate(new Date().toLocaleTimeString());
                    setLoading(false);
                }
            } catch (err) {
                console.error("Failed to fetch volume regime snapshot:", err);
                if (isMounted) setLoading(false);
            }
        };

        setLoading(true);
        fetchData();

        timer = setInterval(fetchData, refreshInterval);

        return () => {
            isMounted = false;
            clearInterval(timer);
        };
    }, [ticker, refreshInterval]);

    // Calculate Confluence
    let confluenceStr = null;
    if (!loading && Object.keys(data).length > 0) {
        const stateCounts: Record<string, number> = {};
        let validStates = 0;

        Object.values(data).forEach(item => {
            const state = item?.state;
            if (state && state !== "Insufficient Data" && state !== "Unavailable") {
                stateCounts[state] = (stateCounts[state] || 0) + 1;
                validStates++;
            }
        });

        // Find highest frequency state
        let maxState = null;
        let maxCount = 0;
        for (const [state, count] of Object.entries(stateCounts)) {
            if (count > maxCount) {
                maxCount = count;
                maxState = state;
            }
        }

        if (maxState && maxCount >= 3) {
            confluenceStr = `⚡ ${maxCount}x ${maxState} Confluence`;
        }
    }

    return (
        <div className="bg-[#0e1525] border border-[#1e3a5f] rounded-lg p-4 flex flex-col w-full relative">

            {/* Table / Grid */}
            <div className="grid grid-cols-2 md:grid-cols-6 gap-2 w-full">
                {TIMEFRAMES.map((tf) => {
                    const isFlashing = flashingKeys.has(tf);
                    const cellData = data[tf] || {};
                    const state = cellData.state || "Loading...";
                    const color = STATE_COLORS[state] || "#94a3b8";
                    const isSkeleton = loading && Object.keys(data).length === 0;
                    const showMetrics = !isSkeleton && state !== "Insufficient Data" && state !== "Unavailable" && state !== "Loading...";

                    return (
                        <div
                            key={tf}
                            className={`flex flex-col items-center justify-center p-3 rounded bg-slate-900 border border-slate-700/50 relative overflow-hidden transition-colors duration-500`}
                            style={isFlashing ? { backgroundColor: 'rgba(56, 189, 248, 0.2)' } : {}}
                        >
                            {/* Timeframe Label */}
                            <div className="text-xs text-slate-400 font-medium tracking-wide mb-1 uppercase">
                                {tf}
                            </div>

                            {/* Regime State */}
                            {isSkeleton ? (
                                <div className="h-6 w-24 bg-slate-800 animate-pulse rounded my-1"></div>
                            ) : (
                                <div
                                    className="text-base font-bold mb-2 tracking-tight transition-colors duration-300"
                                    style={{ color }}
                                >
                                    {state}
                                </div>
                            )}

                            {/* Metrics */}
                            {isSkeleton ? (
                                <>
                                    <div className="h-3 w-16 bg-slate-800 animate-pulse rounded mb-1"></div>
                                    <div className="h-3 w-20 bg-slate-800 animate-pulse rounded"></div>
                                </>
                            ) : showMetrics ? (
                                <div className="text-[11px] text-slate-500 font-sans flex flex-col items-center gap-0.5 mt-1">
                                    {(cellData.ud_vol_ratio !== undefined) && (
                                        <div>Ratio: <span className="text-slate-300">{cellData.ud_vol_ratio.toFixed(2)}</span></div>
                                    )}
                                    {(cellData.volume_vs_avg !== undefined) && (
                                        <div>Vol: <span className="text-slate-300">{cellData.volume_vs_avg.toFixed(1)}x avg</span></div>
                                    )}
                                </div>
                            ) : null}
                        </div>
                    );
                })}
            </div>

            {/* Footer Row: Confluence and Timestamp */}
            <div className="mt-3 flex justify-between items-center text-xs">
                <div>
                    {confluenceStr ? (
                        <span className="text-amber-500 font-bold bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                            {confluenceStr}
                        </span>
                    ) : (
                        <span></span>
                    )}
                </div>
                {lastUpdate && !loading && (
                    <div className="text-slate-500 font-sans">
                        Updated: {lastUpdate}
                    </div>
                )}
            </div>

        </div>
    );
});
