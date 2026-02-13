import React, { useState, useEffect } from 'react';
import { Activity } from 'lucide-react';

const SYMBOLS = ['SPX', 'SPY', 'QQQ', 'IWM'];

interface SkewData {
    symbol: string;
    expiry: string;
    dte: number;
    put_skew: number;
    call_skew: number;
    interpretation: string;
}

const SkewPage = () => {
    const [selectedSymbol, setSelectedSymbol] = useState('SPX');
    const [skewData, setSkewData] = useState < SkewData[] > ([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const loadSkewData = async () => {
            setLoading(true);
            try {
                // TODO: Implement actual skew data endpoint
                // For now, show placeholder
                await new Promise(resolve => setTimeout(resolve, 500));
                setSkewData([]);
            } catch (e) {
                console.error('Failed to load skew data:', e);
            } finally {
                setLoading(false);
            }
        };

        loadSkewData();
    }, [selectedSymbol]);

    return (
        <div className="p-6 space-y-6 bg-slate-950 min-h-screen">
            {/* Header */}
            <header className="border-b border-slate-800 pb-4">
                <h1 className="text-3xl font-bold text-white mb-2">Option Skew & PCR Analysis</h1>
                <p className="text-slate-400">
                    Volatility skew and put-call ratio analysis across expirations
                </p>
            </header>

            {/* Symbol Selector */}
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
                <div className="flex items-center gap-3">
                    <label className="text-sm font-medium text-gray-300">Symbol:</label>
                    <div className="flex gap-2">
                        {SYMBOLS.map(sym => (
                            <button
                                key={sym}
                                onClick={() => setSelectedSymbol(sym)}
                                className={`px-4 py-2 rounded font-semibold transition-colors ${selectedSymbol === sym
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                    }`}
                            >
                                {sym}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Coming Soon Notice */}
            <div className="bg-amber-900/30 border border-amber-600/40 rounded-lg p-6 text-center">
                <Activity className="w-12 h-12 text-amber-400 mx-auto mb-3" />
                <h3 className="text-xl font-semibold text-amber-200 mb-2">
                    Skew Analysis - Under Construction
                </h3>
                <p className="text-amber-100/80">
                    This page will display volatility skew curves, put-call ratios, and risk reversal metrics.
                    Check back soon!
                </p>
            </div>

            {/* Placeholder for Future Content */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
                    <h3 className="text-lg font-semibold text-white mb-4">Volatility Smile</h3>
                    <div className="h-64 flex items-center justify-center text-gray-500">
                        Chart coming soon
                    </div>
                </div>

                <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
                    <h3 className="text-lg font-semibold text-white mb-4">Put-Call Ratio</h3>
                    <div className="h-64 flex items-center justify-center text-gray-500">
                        Chart coming soon
                    </div>
                </div>
            </div>
        </div>
    );
};
