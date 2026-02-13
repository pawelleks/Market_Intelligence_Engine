import React, { useMemo, useState, useEffect } from 'react';
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from 'recharts';
import { ChartExplainer } from './ChartExplainer';

interface DistributionRow {
    expiration: string;
    dte: number;
    distribution: {
        pdf: number[];
        strikes: number[];
        normalized_pdf?: number[];
    };
}

interface ProbabilityBellCurveProps {
    data: DistributionRow[];
    currentPrice: number;
    ticker: string;
    hardAnchor: number;
}

export const ProbabilityBellCurve: React.FC<ProbabilityBellCurveProps> = ({
    data = [],
    currentPrice,
    ticker,
    hardAnchor
}) => {
    // Internal state for selected expiration
    const [selectedExp, setSelectedExp] = useState<string>('');

    // Initialize selectedExp when data changes
    useEffect(() => {
        if (data.length > 0 && !selectedExp) {
            const defaultIndex = Math.min(data.length - 1, 4);
            setSelectedExp(data[defaultIndex].expiration);
        }
    }, [data, selectedExp]);

    // 1. SAFETY GUARD: Crash proof check
    if (!data || !Array.isArray(data) || data.length === 0) {
        return (
            <div className="w-full h-[650px] bg-slate-900 rounded-lg p-4 border border-slate-800 flex items-center justify-center">
                <p className="text-slate-400 font-mono">Waiting for PDF Data...</p>
            </div>
        );
    }

    const row = data.find(d => d.expiration === selectedExp) || data[0];
    const { strikes = [], pdf = [] } = row.distribution || {};

    if (strikes.length === 0) {
        return (
            <div className="w-full h-[650px] bg-slate-900 rounded-lg p-4 border border-slate-800 flex items-center justify-center">
                <p className="text-slate-400 font-mono">No distribution for {selectedExp}</p>
            </div>
        );
    }

    // 2. DATA PREPARATION: Recharts format
    const { chartData, anchor, minX, maxX } = useMemo(() => {
        const peak = Math.max(...pdf);
        const norm = row.distribution.normalized_pdf || pdf.map(p => peak > 0 ? (p / peak) : 0);

        const mapped = strikes.map((s, i) => ({
            strike: s,
            prob: norm[i]
        }));

        const currentAnchor = hardAnchor || 5000;
        return {
            chartData: mapped,
            anchor: currentAnchor,
            minX: currentAnchor * 0.8,
            maxX: currentAnchor * 1.2
        };
    }, [pdf, strikes, row.distribution, hardAnchor]);

    return (
        <div className="w-full bg-slate-900 rounded-lg border border-slate-800 flex flex-col p-4 shadow-xl">
            <div className="mb-2 flex justify-between items-center">
                <div className="flex flex-col">
                    <h3 className="text-slate-100 text-lg font-bold">{ticker} Probability Density</h3>
                    <p className="text-[10px] text-slate-500 italic uppercase tracking-wider">Relative Probability Density</p>
                </div>

                {/* Expiration Selector - Moved here from page header */}
                <div className="flex items-center gap-3">
                    <div className="text-[10px] text-slate-400 font-mono">
                        Spot: ${anchor.toLocaleString()}
                    </div>
                    <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 flex items-center gap-2">
                        <label className="text-xs font-medium text-slate-400">Expiration:</label>
                        <select
                            value={selectedExp}
                            onChange={(e) => setSelectedExp(e.target.value)}
                            className="bg-slate-950 border border-slate-600 rounded px-2 py-1 text-slate-200 focus:ring-1 focus:ring-cyan-500 outline-none text-xs cursor-pointer"
                        >
                            {data.map((d) => (
                                <option key={d.expiration} value={d.expiration}>
                                    {d.expiration} ({d.dte}d)
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>

            <div className="w-full h-[600px]">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                        <defs>
                            <linearGradient id="cyanBlue" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.2} />
                                <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.2} vertical={false} />
                        <XAxis
                            dataKey="strike"
                            type="number"
                            domain={[minX, maxX]}
                            stroke="#475569"
                            tick={{ fill: '#94a3b8', fontSize: 11 }}
                            tickFormatter={(val) => `$${val.toLocaleString()}`}
                        />
                        <YAxis hide={true} domain={[0, 1.1]} />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '4px' }}
                            itemStyle={{ fontSize: '12px', color: '#06b6d4' }}
                            formatter={(value: number) => [`${(value * 100).toFixed(1)}%`, 'Density']}
                            labelFormatter={(label) => `Strike: $${label.toLocaleString()}`}
                        />
                        <Area
                            type="monotone"
                            dataKey="prob"
                            stroke="#06b6d4"
                            strokeWidth={3}
                            fill="url(#cyanBlue)"
                            connectNulls
                            isAnimationActive={true}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
            <ChartExplainer>
                <p className="pt-2"><strong className="text-slate-300">What this shows:</strong> The probability density function (PDF) for a single expiration date, extracted from options prices using the Breeden-Litzenberger method. The area under the curve represents 100% of possible outcomes.</p>
                <p><strong className="text-slate-300">Reading the shape:</strong> The peak is the single most likely closing price at expiration. The width at the base shows the range of outcomes the market considers plausible.</p>
                <p><strong className="text-slate-300">Tails:</strong> The left tail represents crash scenarios; the right tail represents rally scenarios. Heavier tails mean the market is pricing in more extreme moves. Options traders call this "fat tails" or excess kurtosis.</p>
                <p><strong className="text-slate-300">Skewness:</strong> A symmetric bell curve means balanced risk. If the left side is fatter (negative skew), downside protection is expensive &mdash; the market fears a drop. If the right side is fatter, calls are expensive &mdash; speculation is elevated.</p>
                <p><strong className="text-slate-300">Use the Exp selector</strong> above the chart to switch between different expiration dates and see how the distribution changes over time.</p>
            </ChartExplainer>
        </div>
    );
};
