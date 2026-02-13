import React from 'react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
} from 'recharts';
import { ChartExplainer } from './ChartExplainer';

interface DistributionRow {
    expiration: string;
    dte: number;
    distribution: {
        pdf: number[];
        strikes: number[];
    };
}

interface ProbabilityLayeredChartProps {
    data: DistributionRow[];
    currentPrice: number;
    ticker: string;
    hardAnchor: number;
}

export const ProbabilityLayeredChart: React.FC<ProbabilityLayeredChartProps> = ({
    data = [],
    currentPrice,
    ticker,
    hardAnchor
}) => {
    // 1. SAFETY GUARD: Crash proof check
    if (!data || !Array.isArray(data) || data.length === 0) {
        return (
            <div className="w-full h-[650px] bg-slate-900 rounded-lg p-4 border border-slate-800 flex items-center justify-center">
                <p className="text-slate-400 font-mono">Waiting for Term Structure Data...</p>
            </div>
        );
    }

    // 2. CONVERT MULTI-EXP DATA TO RECHARTS FORMAT
    const chartData = React.useMemo(() => {
        // Collect all unique strikes
        const allStrikesSet = new Set<number>();
        data.forEach(row => {
            if (row.distribution?.strikes) {
                row.distribution.strikes.forEach(s => allStrikesSet.add(s));
            }
        });

        const sortedStrikes = Array.from(allStrikesSet).sort((a, b) => a - b);

        // Map strikes to probabilities across different DTEs
        return sortedStrikes.map(strike => {
            const point: any = { price: strike };
            data.forEach(row => {
                const idx = row.distribution.strikes.indexOf(strike);
                if (idx !== -1) {
                    point[`dte_${row.dte}`] = row.distribution.pdf[idx];
                }
            });
            return point;
        });
    }, [data]);

    // 3. SMART ZOOM: Derive center from data if hardAnchor is missing
    const dataCenter = React.useMemo(() => {
        if (hardAnchor && hardAnchor > 0) return hardAnchor;
        // Fallback: median of all strikes in the data
        const allStrikes: number[] = [];
        data.forEach(row => {
            if (row.distribution?.strikes) allStrikes.push(...row.distribution.strikes);
        });
        if (allStrikes.length === 0) return 0;
        allStrikes.sort((a, b) => a - b);
        return allStrikes[Math.floor(allStrikes.length / 2)];
    }, [hardAnchor, data]);

    const zoomFactor = ticker === 'SPX' ? 0.08 : 0.20;
    const minX = dataCenter * (1 - zoomFactor);
    const maxX = dataCenter * (1 + zoomFactor);
    const xDomain = [minX, maxX];

    const colors = ['#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316', '#eab308'];

    return (
        <div className="w-full bg-slate-900 rounded-lg border border-slate-800 flex flex-col p-4 shadow-xl">
            <div className="mb-4">
                <h3 className="text-slate-100 text-lg font-bold">{ticker} Term Structure Evolution</h3>
            </div>

            <div className="w-full h-[600px]">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} vertical={false} />
                        <XAxis
                            dataKey="price"
                            type="number"
                            domain={xDomain}
                            stroke="#94a3b8"
                            tick={{ fill: '#94a3b8', fontSize: 10 }}
                            allowDataOverflow={true}
                            tickFormatter={(v: number) => `$${Math.round(v).toLocaleString()}`}
                        />
                        <YAxis stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 10 }} orientation="right" width={60} />
                        <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155' }} />
                        <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px' }} />

                        {data.map((row, idx) => (
                            <Line
                                key={row.expiration}
                                type="monotone"
                                dataKey={`dte_${row.dte}`}
                                stroke={colors[idx % colors.length]}
                                strokeWidth={2}
                                dot={false}
                                name={`${row.expiration} (${row.dte}d)`}
                                connectNulls
                            />
                        ))}
                    </LineChart>
                </ResponsiveContainer>
            </div>
            <ChartExplainer>
                <p className="pt-2"><strong className="text-slate-300">What this shows:</strong> Multiple probability bell curves overlaid, one for each option expiration date. Each line represents the market's implied probability distribution for where price could land at that expiration.</p>
                <p><strong className="text-slate-300">Reading the curves:</strong> The peak of each curve is the most likely price at that expiration. Taller, narrower peaks mean higher confidence. Shorter, wider curves mean more uncertainty.</p>
                <p><strong className="text-slate-300">Term structure evolution:</strong> Compare how the distribution changes across expirations. Near-term curves (fewer DTE) are typically taller and narrower. Longer-dated curves flatten out as uncertainty grows over time.</p>
                <p><strong className="text-slate-300">Skew:</strong> If a curve leans to the left (lower prices have more probability mass), the market is pricing in downside risk. A rightward lean suggests upside speculation.</p>
            </ChartExplainer>
        </div>
    );
};
