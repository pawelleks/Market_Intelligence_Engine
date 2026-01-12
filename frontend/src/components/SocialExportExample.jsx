import React, { useRef } from 'react';
import { Share2, Download } from 'lucide-react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

import useSocialExport from '../hooks/useSocialExport';
import HiddenRenderViewport from './common/SocialExport/HiddenRenderViewport';
import SocialCardTemplate from './common/SocialExport/SocialCardTemplate';

// Dummy Data
const data = [
    { name: 'Mon', value: 400 },
    { name: 'Tue', value: 300 },
    { name: 'Wed', value: 600 },
    { name: 'Thu', value: 800 },
    { name: 'Fri', value: 500 },
];

/**
 * Example Component demonstrating the Social Export System.
 */
const SocialExportExample = () => {
    const exportRef = useRef();
    const { exportImage, isExporting } = useSocialExport(exportRef, 'market-snapshot.png');

    return (
        <div className="p-8 bg-slate-950 min-h-screen text-white">
            <div className="max-w-4xl mx-auto space-y-8">
                <header className="flex justify-between items-center">
                    <div>
                        <h2 className="text-3xl font-bold">Market Performance</h2>
                        <p className="text-slate-400">Live Interactive Dashboard</p>
                    </div>

                    {/* TRIGGER BUTTON */}
                    <button
                        onClick={exportImage}
                        disabled={isExporting}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-lg font-bold transition-all disabled:opacity-50"
                    >
                        {isExporting ? (
                            "Generating..."
                        ) : (
                            <>
                                <Share2 size={18} />
                                Export to X (Twitter)
                            </>
                        )}
                    </button>
                </header>

                {/* 1. LIVE INTERACTIVE UI */}
                <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800 h-[400px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis dataKey="name" stroke="#94a3b8" />
                            <YAxis stroke="#94a3b8" />
                            <Tooltip
                                contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px' }}
                                itemStyle={{ color: '#60a5fa' }}
                            />
                            <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={3} dot={{ r: 6 }} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>

                <div className="p-4 bg-blue-900/20 border border-blue-500/20 rounded-lg text-blue-300 text-sm">
                    <strong>Tip:</strong> The live chart above is interactive. Clicking "Export" will capture a
                    specially optimized version of this data rendered in a hidden viewport.
                </div>

                {/* 2. HIDDEN VIEWPORT FOR EXPORT (THE ENGINE) */}
                <HiddenRenderViewport innerRef={exportRef}>
                    <SocialCardTemplate
                        title="Weekly Volatility Analysis"
                        subtitle="Jan 2 - Jan 9, 2026 • Global Equity Markets"
                    >
                        {/* 
                            OPTIMIZED CHART FOR STATIC IMAGE:
                            - No ResponsiveContainer (we use explicit width/height)
                            - Larger fonts for Axes
                            - Thicker lines
                            - NO Tooltips (they don't render well in static snapshots)
                            - Higher contrast colors
                        */}
                        <LineChart width={1100} height={400} data={data}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                            <XAxis
                                dataKey="name"
                                stroke="#cbd5e1"
                                tick={{ fontSize: 20, fontWeight: '600' }}
                                dy={15}
                            />
                            <YAxis
                                stroke="#cbd5e1"
                                tick={{ fontSize: 20, fontWeight: '600' }}
                                dx={-10}
                            />
                            {/* NOTE: Tooltip removed for static capture consistency */}
                            <Line
                                type="monotone"
                                dataKey="value"
                                stroke="#60a5fa"
                                strokeWidth={8} // Massive stroke for visibility on mobile feeds
                                dot={{ r: 12, fill: '#60a5fa', strokeWidth: 4, stroke: '#0f172a' }}
                            />
                        </LineChart>
                    </SocialCardTemplate>
                </HiddenRenderViewport>
            </div>
        </div>
    );
};

export default SocialExportExample;
