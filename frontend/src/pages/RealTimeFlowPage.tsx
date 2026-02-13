import React, { useState, useEffect } from 'react';
import { RealTimeDealerFlow } from '../components/charts/RealTimeDealerFlow';

export const RealTimeFlowPage = () => {
    const [ticker, setTicker] = useState('SPY');
    const [gexInfo, setGexInfo] = useState<any>(null);

    useEffect(() => {
        fetch(`/api/v1/gex/latest/${ticker}?_t=${Date.now()}`)
            .then(res => res.ok ? res.json() : null)
            .then(data => { if (data) setGexInfo(data); })
            .catch(() => { });
    }, [ticker]);

    const spotPrice = gexInfo?.spot_price;
    const profileLen = gexInfo?.profile?.length ?? 0;

    return (
        <div className="p-6 space-y-6 bg-slate-950 min-h-screen flex flex-col">
            {/* Construction Banner */}
            <div className="bg-amber-900/40 border border-amber-600/50 rounded-lg px-4 py-2.5 text-center text-sm text-amber-200">
                Under Construction — This page may not work properly as it is still under development. Do not use the data presented to make any trading or investment decisions.
            </div>

            {/* Header: Title Left, Selector Right */}
            <header className="mb-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-100 mb-1">Real-Time Flow Analysis</h1>
                    <p className="text-slate-400">High-frequency dealer hedging impact (HIRO) and price action.</p>
                </div>

                {/* Ticker Selector */}
                <div className="bg-slate-900 border border-slate-700 rounded-lg p-2 flex items-center gap-3 shadow-sm">
                    <label className="text-sm font-medium text-slate-400">Target Ticker</label>
                    <select
                        value={ticker}
                        onChange={(e) => setTicker(e.target.value)}
                        className="bg-slate-950 border border-slate-700 rounded px-3 py-1 text-slate-200 focus:ring-2 focus:ring-cyan-500 outline-none text-sm"
                    >
                        <option value="SPY">SPY (S&P 500 ETF)</option>
                        <option value="SPX">SPX (Index)</option>
                        <option value="QQQ">QQQ (Nasdaq)</option>
                        <option value="IWM">IWM (Russell)</option>
                    </select>
                </div>
            </header>

            {/* Main Chart Area - Full Width */}
            <div className="w-full flex-grow">
                <RealTimeDealerFlow ticker={ticker} />
            </div>

            {/* Metrics - Bottom */}
            <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
                    <h3 className="text-slate-100 font-medium mb-2">System Metrics</h3>
                    <ul className="space-y-2 text-sm">
                        <li className="flex justify-between">
                            <span className="text-slate-500">Update Rate</span>
                            <span className="text-slate-300">2/sec (throttled)</span>
                        </li>
                        <li className="flex justify-between">
                            <span className="text-slate-500">Source</span>
                            <span className="text-emerald-400">Alpaca IEX + ThetaData</span>
                        </li>
                    </ul>
                </div>

                <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
                    <h3 className="text-slate-100 font-medium mb-2">Gamma Exposure</h3>
                    <ul className="space-y-2 text-sm">
                        <li className="flex justify-between">
                            <span className="text-slate-500">Status</span>
                            <span className={profileLen > 0 ? "text-emerald-400" : "text-slate-500"}>
                                {profileLen > 0 ? `Loaded (${profileLen} levels)` : 'Loading...'}
                            </span>
                        </li>
                        <li className="flex justify-between">
                            <span className="text-slate-500">Spot Price</span>
                            <span className="text-slate-300">{spotPrice ? `$${spotPrice.toFixed(2)}` : '—'}</span>
                        </li>
                    </ul>
                </div>

                <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
                    <h3 className="text-slate-100 font-medium mb-2">Data Info</h3>
                    <ul className="space-y-2 text-sm">
                        <li className="flex justify-between">
                            <span className="text-slate-500">GEX Date</span>
                            <span className="text-slate-300">{gexInfo?.date || '—'}</span>
                        </li>
                        <li className="flex justify-between">
                            <span className="text-slate-500">Net GEX</span>
                            <span className={`${(gexInfo?.net_gex ?? 0) >= 0 ? 'text-sky-400' : 'text-red-400'}`}>
                                {gexInfo?.net_gex ? `${(gexInfo.net_gex / 1e9).toFixed(2)}B` : '—'}
                            </span>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    );
};

export default RealTimeFlowPage;
