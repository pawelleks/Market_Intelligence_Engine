import React, { useState, useCallback } from 'react';
import { VolumeRegimeChart } from '../components/VolumeRegimeChart';
import { VolumeRegimeTable } from '../components/VolumeRegimeTable';
import { Activity } from 'lucide-react';

export const VolumeRegimeAlphaPage = () => {
    const [ticker, setTicker] = useState('SPY');
    const [signals, setSignals] = useState < { timestamp: string; timeframe: string; oldState: string; newState: string }[] > ([]);

    const handleTickerChange = useCallback((newTicker: string) => {
        setTicker(newTicker);
        setSignals([]); // optionally clear signals on ticker change
    }, []);

    // We pass this callback to VolumeRegimeTable so it can report state changes
    const handleStateChange = useCallback((changes: { timeframe: string; oldState: string; newState: string }[]) => {
        if (changes.length === 0) return;

        const timestamp = new Date().toLocaleTimeString();
        const newSignals = changes.map(change => ({
            timestamp,
            timeframe: change.timeframe,
            oldState: change.oldState,
            newState: change.newState
        }));

        setSignals(prev => {
            const updated = [...newSignals, ...prev];
            return updated.slice(0, 20); // Keep max 20 entries
        });
    }, []);

    return (
        <div className="p-6 space-y-6 bg-[#0b1220] min-h-screen flex flex-col w-full">
            {/* Header */}
            <header className="mb-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-[#f8fafc] mb-1 flex items-center gap-3">
                        <Activity className="w-8 h-8 text-[#3b82f6]" />
                        Volume Regime Alpha
                    </h1>
                    <p className="text-[#94a3b8]">Institutional Volume Flow · Multi-Timeframe Regime Detection</p>
                </div>
            </header>

            {/* Main Content Area */}
            <div className="flex flex-col xl:flex-row gap-6 w-full">

                {/* Left Column (Chart + Table) */}
                <div className="flex-1 flex flex-col space-y-6 min-w-0">
                    <div className="w-full">
                        <VolumeRegimeChart
                            initialTicker={ticker}
                            onTickerChange={handleTickerChange}
                        />
                    </div>
                    <div className="w-full">
                        <VolumeRegimeTable
                            ticker={ticker}
                            onStateChange={handleStateChange}
                        />
                    </div>
                </div>

                {/* Right Column (Signal Log) */}
                <div className="xl:w-80 flex flex-col bg-[#0e1525] border border-[#1e3a5f] rounded-lg shadow-lg overflow-hidden shrink-0">
                    <div className="p-4 border-b border-[#1e3a5f] bg-[#1b2a40]/30 shrink-0">
                        <h3 className="text-[#f8fafc] font-bold text-sm uppercase tracking-wide flex items-center justify-between">
                            Signal Log
                            <span className="text-xs font-normal text-[#94a3b8] normal-case bg-[#1b2a40] px-2 py-0.5 rounded-full border border-[#1e3a5f]">
                                {ticker}
                            </span>
                        </h3>
                    </div>

                    <div className="flex-1 overflow-y-auto p-2" style={{ maxHeight: '700px' }}>
                        {signals.length === 0 ? (
                            <div className="p-4 text-center text-[#94a3b8] text-sm italic mt-10">
                                Waiting for regime shifts...
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {signals.map((sig, idx) => (
                                    <div key={idx} className="flex flex-col p-3 rounded-lg border border-[#1e3a5f] bg-[#0b1220] transition-all hover:bg-[#1b2a40]/50 text-sm">
                                        <div className="flex justify-between items-center mb-2">
                                            <span className="text-[#94a3b8] text-xs font-mono">{sig.timestamp}</span>
                                            <span className="bg-[#3b82f6]/20 text-[#3b82f6] text-[10px] font-bold uppercase px-2 py-0.5 rounded border border-[#3b82f6]/30">
                                                {sig.timeframe}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-2 text-xs font-medium">
                                            <span className="text-slate-500 truncate">{sig.oldState || "None"}</span>
                                            <span className="text-[#94a3b8] shrink-0">→</span>
                                            <span className="text-[#f8fafc] truncate">{sig.newState}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

            </div>
        </div>
    );
};

export default VolumeRegimeAlphaPage;
