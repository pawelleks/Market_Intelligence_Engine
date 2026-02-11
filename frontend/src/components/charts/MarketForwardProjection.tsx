import React, { useMemo } from 'react';
import {
    ComposedChart,
    Line,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine
} from 'recharts';
import { format } from 'date-fns';

interface ProjectionPoint {
    date: string;
    p05: number;
    p10: number;
    p20: number;
    p30: number;
    p40: number;
    p50: number;
    p60: number;
    p70: number;
    p80: number;
    p90: number;
    p95: number;
    dte: number;
}

interface ForwardProjectionProps {
    projection: ProjectionPoint[];
    currentPrice?: number;
    ticker: string;
    livePriceOverlay?: number;
}

const CustomTooltip = ({ active, payload, label, hardAnchor }: any) => {
    if (active && payload && payload.length) {
        const currentData = payload[0].payload;

        return (
            <div className="bg-slate-900 border border-slate-700 p-3 rounded shadow-xl text-xs">
                <p className="font-bold text-slate-200 mb-2 border-b border-slate-700 pb-1">
                    {label}
                </p>

                {/* Reference Price Header */}
                <div className="flex justify-between items-center mb-2 text-slate-400">
                    <span>🎯 Reference Spot:</span>
                    <span className="font-mono text-white">
                        ${(hardAnchor || 0).toFixed(2)}
                    </span>
                </div>

                {/* Decile List - Traffic Light Colors */}
                <div className="space-y-1">
                    {/* RED: Extreme High */}
                    <div className="flex justify-between gap-4 text-red-500">
                        <span>🔴 Extreme High (95%):</span>
                        <span className="font-mono">${(currentData.p95 || 0).toFixed(2)}</span>
                    </div>

                    {/* YELLOW: Broad Likely */}
                    <div className="flex justify-between gap-4 text-yellow-500">
                        <span>🟡 Broad High (80%):</span>
                        <span className="font-mono">${(currentData.p80 || 0).toFixed(2)}</span>
                    </div>

                    {/* GREEN: Core Area */}
                    <div className="flex justify-between gap-4 text-green-500">
                        <span>🟢 Core High (60%):</span>
                        <span className="font-mono">${(currentData.p60 || 0).toFixed(2)}</span>
                    </div>

                    {/* Median */}
                    <div className="flex justify-between gap-4 text-white font-bold my-1 border-y border-slate-800 py-1">
                        <span>⚪ Expected (Median):</span>
                        <span className="font-mono">${(currentData.p50 || 0).toFixed(2)}</span>
                    </div>

                    {/* GREEN: Core Area */}
                    <div className="flex justify-between gap-4 text-green-500">
                        <span>🟢 Core Low (40%):</span>
                        <span className="font-mono">${(currentData.p40 || 0).toFixed(2)}</span>
                    </div>

                    {/* YELLOW: Broad Likely */}
                    <div className="flex justify-between gap-4 text-yellow-500">
                        <span>🟡 Broad Low (20%):</span>
                        <span className="font-mono">${(currentData.p20 || 0).toFixed(2)}</span>
                    </div>

                    {/* RED: Extreme Low */}
                    <div className="flex justify-between gap-4 text-red-500">
                        <span>🔴 Extreme Low (5%):</span>
                        <span className="font-mono">${(currentData.p05 || 0).toFixed(2)}</span>
                    </div>
                </div>
            </div>
        );
    }
    return null;
};

export const MarketForwardProjection: React.FC<ForwardProjectionProps> = ({
    projection = [],
    currentPrice,
    ticker,
    livePriceOverlay
}) => {
    if (!projection || !Array.isArray(projection) || projection.length === 0) {
        return (
            <div className="w-full h-[650px] bg-slate-900 rounded-lg p-4 border border-slate-800 flex items-center justify-center">
                <p className="text-slate-400 font-mono">Waiting for {ticker} Projection Data...</p>
            </div>
        );
    }

    const { chartData, refPriceAnchor } = useMemo(() => {
        const anchor = currentPrice || projection[0]?.p50 || 0;

        const mapped = projection.map(d => ({
            dateShort: format(new Date(d.date), 'MMM dd'),
            p05: d.p05,
            p10: d.p10,
            p20: d.p20,
            p30: d.p30,
            p40: d.p40,
            p50: d.p50,
            p60: d.p60,
            p70: d.p70,
            p80: d.p80,
            p90: d.p90,
            p95: d.p95,
            // Pre-computed range arrays for Recharts v3 Area bands
            outerRange: [d.p05, d.p95],
            midRange: [d.p20, d.p80],
            coreRange: [d.p40, d.p60],
        }));

        return { chartData: mapped, refPriceAnchor: anchor };
    }, [projection, currentPrice]);


    return (
        <div className="w-full bg-slate-900 rounded-lg border border-slate-800 flex flex-col p-4 shadow-xl">
            <div className="mb-2 flex justify-between items-center">
                <h3 className="text-slate-100 text-lg font-bold">{ticker} Forward Price Projection</h3>
                <div className="text-[10px] text-slate-500 font-mono">
                    Spot: ${refPriceAnchor?.toLocaleString()}
                </div>
            </div>

            <div className="w-full h-[600px]">
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                        key={ticker + "-fan-heatmap"}
                        data={chartData}
                        margin={{ top: 10, right: 30, left: 10, bottom: 0 }}
                    >
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} vertical={false} />
                        <XAxis
                            dataKey="dateShort"
                            stroke="#94a3b8"
                            tick={{ fill: '#94a3b8', fontSize: 11 }}
                            minTickGap={30}
                        />
                        <YAxis
                            stroke="#94a3b8"
                            tick={{ fill: '#94a3b8', fontSize: 11 }}
                            orientation="right"
                            width={60}
                            domain={['auto', 'auto']}
                            tickFormatter={(val) => val.toLocaleString()}
                        />
                        <Tooltip content={<CustomTooltip hardAnchor={refPriceAnchor} />} />

                        {/* 1. OUTER RED ZONE (Tail Risk) - Band from p05 to p95 */}
                        <Area
                            type="monotone"
                            dataKey="outerRange"
                            stroke="none"
                            fill="#ef4444"
                            fillOpacity={0.15}
                            name="90% Range"
                            legendType="none"
                        />

                        {/* 2. MIDDLE YELLOW ZONE (Likely) - Band from p20 to p80 */}
                        <Area
                            type="monotone"
                            dataKey="midRange"
                            stroke="none"
                            fill="#eab308"
                            fillOpacity={0.25}
                            name="60% Range"
                            legendType="none"
                        />

                        {/* 3. INNER GREEN ZONE (Core) - Band from p40 to p60 */}
                        <Area
                            type="monotone"
                            dataKey="coreRange"
                            stroke="none"
                            fill="#22c55e"
                            fillOpacity={0.4}
                            name="20% Core"
                            legendType="none"
                        />

                        {/* 4. MEDIAN LINE (White) - The Anchor */}
                        <Line
                            type="monotone"
                            dataKey="p50"
                            stroke="#ffffff"
                            strokeWidth={2}
                            dot={false}
                            name="Median"
                            connectNulls
                        />

                        {/* Live Price Reference */}
                        {livePriceOverlay && (
                            <ReferenceLine y={livePriceOverlay} stroke="#22c55e" strokeDasharray="3 3" label={{ value: 'Live', position: 'left', fill: '#22c55e', fontSize: 10 }} />
                        )}
                    </ComposedChart>
                </ResponsiveContainer>
            </div>

            <div className="mt-4 p-3 bg-slate-800/20 rounded border border-slate-700/30">
                <p className="text-xs text-slate-500 leading-relaxed text-center">
                    High-Resolution Probability Heatmap. Red = 95% Tail Risk, Gold = Core Expectation.
                </p>
            </div>
        </div>
    );
};
