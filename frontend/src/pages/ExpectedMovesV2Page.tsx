import React, { useState } from 'react';
import { ExpectedMovesChartV2 } from '../components/charts/ExpectedMovesChartV2';

export type CalcMode = 'sigma' | 'breakeven';

export const ExpectedMovesV2Page = () => {
    const [ticker, setTicker] = useState('SPY');
    const [calcMode, setCalcMode] = useState<CalcMode>('sigma');

    return (
        <div className="p-6 space-y-6 bg-slate-950 min-h-screen flex flex-col">
            {/* Construction Banner */}
            <div className="bg-amber-900/40 border border-amber-600/50 rounded-lg px-4 py-2.5 text-center text-sm text-amber-200">
                Under Construction — This page may not work properly as it is still under development. Do not use the data presented to make any trading or investment decisions.
            </div>

            {/* Header */}
            <header className="mb-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-100 mb-1">Expected Moves V2</h1>
                    <p className="text-slate-400">Real-time straddle-based expected moves powered by ThetaData.</p>
                </div>

                <div className="flex flex-wrap items-center gap-4">
                    {/* Calc Mode Toggle */}
                    <div className="flex items-center gap-1 bg-slate-900 border border-slate-700 rounded-lg p-1">
                        <button
                            onClick={() => setCalcMode('sigma')}
                            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
                                calcMode === 'sigma'
                                    ? 'bg-cyan-600 text-white shadow-md'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                            }`}
                        >
                            1-Sigma
                        </button>
                        <button
                            onClick={() => setCalcMode('breakeven')}
                            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
                                calcMode === 'breakeven'
                                    ? 'bg-amber-600 text-white shadow-md'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                            }`}
                        >
                            Breakeven
                        </button>
                    </div>

                    {/* Ticker Selector */}
                    <div className="bg-slate-900 border border-slate-700 rounded-lg p-2 flex items-center gap-3 shadow-sm">
                        <label className="text-sm font-medium text-slate-400">Ticker</label>
                        <select
                            value={ticker}
                            onChange={(e) => setTicker(e.target.value)}
                            className="bg-slate-950 border border-slate-700 rounded px-3 py-1 text-slate-200 focus:ring-2 focus:ring-cyan-500 outline-none text-sm"
                        >
                            <option value="SPY">SPY</option>
                            <option value="SPX">SPX</option>
                            <option value="QQQ">QQQ</option>
                            <option value="IWM">IWM</option>
                        </select>
                    </div>
                </div>
            </header>

            {/* Main Chart Area */}
            <div className="w-full h-[800px]">
                <ExpectedMovesChartV2 ticker={ticker} calcMode={calcMode} />
            </div>

            {/* Footer / Methodology Note */}
            <div className="text-xs text-slate-500 mt-4 border-t border-slate-800 pt-4">
                <p>
                    <strong>Methodology:</strong>{' '}
                    {calcMode === 'sigma'
                        ? '1-Sigma Mode: Expected Move = ATM Straddle × 0.85 (~68% probability, 1 standard deviation).'
                        : 'Breakeven Mode: Expected Move = Raw ATM Straddle (Call + Put). Market Maker breakeven (~50% probability).'
                    }
                    {' '}Calculated using EOD Option Chain snapshots from ThetaData.
                    0DTE refers to the current session or next immediate expiry.
                </p>
            </div>
        </div>
    );
};

export default ExpectedMovesV2Page;
