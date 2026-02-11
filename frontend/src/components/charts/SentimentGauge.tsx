import React from 'react';
import { ChartExplainer } from './ChartExplainer';

interface SentimentData {
    implied_drift: number;
    realized_drift: number;
    drift_gap: number;
    implied_vol: number;
    realized_vol: number;
    vol_spread: number;
    signal: 'hedging' | 'neutral' | 'speculative';
    lookback_days: number;
}

interface SentimentGaugeProps {
    sentiment: SentimentData | null;
    ticker: string;
}

const SIGNAL_CONFIG = {
    hedging: {
        label: 'Hedging / Fearful',
        color: '#ef4444',
        bgColor: 'rgba(239, 68, 68, 0.1)',
        borderColor: 'rgba(239, 68, 68, 0.3)',
    },
    neutral: {
        label: 'Neutral',
        color: '#eab308',
        bgColor: 'rgba(234, 179, 8, 0.1)',
        borderColor: 'rgba(234, 179, 8, 0.3)',
    },
    speculative: {
        label: 'Speculative / Bullish',
        color: '#22c55e',
        bgColor: 'rgba(34, 197, 94, 0.1)',
        borderColor: 'rgba(34, 197, 94, 0.3)',
    },
};

const MetricPair = ({
    label,
    implied,
    realized,
    diff,
    format = 'pct',
}: {
    label: string;
    implied: number;
    realized: number;
    diff: number;
    format?: 'pct';
}) => {
    const diffColor = diff > 0.005 ? '#22c55e' : diff < -0.005 ? '#ef4444' : '#eab308';
    const fmtVal = (v: number) => `${(v * 100).toFixed(1)}%`;
    const fmtDiff = (v: number) => `${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}%`;

    return (
        <div className="flex-1 min-w-[200px]">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-2 font-semibold">
                {label}
            </div>
            <div className="flex items-end gap-3">
                <div>
                    <div className="text-[10px] text-slate-500">Implied</div>
                    <div className="text-sm font-mono text-slate-200">{fmtVal(implied)}</div>
                </div>
                <div className="text-slate-600 text-xs pb-0.5">vs</div>
                <div>
                    <div className="text-[10px] text-slate-500">Realized</div>
                    <div className="text-sm font-mono text-slate-200">{fmtVal(realized)}</div>
                </div>
                <div
                    className="text-sm font-mono font-bold pb-0.5"
                    style={{ color: diffColor }}
                >
                    {fmtDiff(diff)}
                </div>
            </div>
        </div>
    );
};

const GaugeBar = ({ value, signal }: { value: number; signal: string }) => {
    // Map drift_gap to 0-100 position. Range: -15% to +15% annualized
    const clampedPct = Math.max(-0.15, Math.min(0.15, value));
    const position = ((clampedPct + 0.15) / 0.30) * 100;

    return (
        <div className="relative w-full h-3 rounded-full overflow-hidden bg-slate-800 border border-slate-700/50">
            {/* Gradient bar: red -> yellow -> green */}
            <div
                className="absolute inset-0 rounded-full"
                style={{
                    background: 'linear-gradient(to right, #ef4444, #f59e0b 35%, #eab308 50%, #84cc16 65%, #22c55e)',
                    opacity: 0.6,
                }}
            />
            {/* Center line */}
            <div
                className="absolute top-0 bottom-0 w-px bg-slate-400/50"
                style={{ left: '50%' }}
            />
            {/* Pointer */}
            <div
                className="absolute top-[-3px] w-[18px] h-[18px] rounded-full border-2 border-white shadow-lg shadow-black/50"
                style={{
                    left: `${position}%`,
                    transform: 'translateX(-50%)',
                    backgroundColor:
                        signal === 'hedging'
                            ? '#ef4444'
                            : signal === 'speculative'
                            ? '#22c55e'
                            : '#eab308',
                }}
            />
        </div>
    );
};

export const SentimentGauge: React.FC<SentimentGaugeProps> = ({ sentiment, ticker }) => {
    if (!sentiment) return null;

    const config = SIGNAL_CONFIG[sentiment.signal] || SIGNAL_CONFIG.neutral;

    return (
        <div
            className="w-full rounded-lg p-4 shadow-xl"
            style={{
                backgroundColor: config.bgColor,
                border: `1px solid ${config.borderColor}`,
            }}
        >
            {/* Header Row */}
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <div className="flex items-center gap-3">
                    <h3 className="text-slate-100 text-base font-bold">
                        {ticker} Market Sentiment
                    </h3>
                    <span
                        className="text-xs font-bold px-2.5 py-1 rounded-full uppercase tracking-wider"
                        style={{
                            color: config.color,
                            backgroundColor: config.bgColor,
                            border: `1px solid ${config.borderColor}`,
                        }}
                    >
                        {config.label}
                    </span>
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                    {sentiment.lookback_days}-day lookback
                </div>
            </div>

            {/* Gauge Bar */}
            <div className="mb-1">
                <GaugeBar value={sentiment.drift_gap} signal={sentiment.signal} />
            </div>
            <div className="flex justify-between text-[9px] text-slate-600 mb-4 px-1">
                <span>Put Hedging</span>
                <span>Neutral</span>
                <span>Call Speculation</span>
            </div>

            {/* Metrics Row */}
            <div className="flex flex-wrap gap-6">
                <MetricPair
                    label="Drift (Annualized)"
                    implied={sentiment.implied_drift}
                    realized={sentiment.realized_drift}
                    diff={sentiment.drift_gap}
                />
                <MetricPair
                    label="Volatility (Annualized)"
                    implied={sentiment.implied_vol}
                    realized={sentiment.realized_vol}
                    diff={sentiment.vol_spread}
                />
                {/* Interpretation */}
                <div className="flex-1 min-w-[200px]">
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-2 font-semibold">
                        Interpretation
                    </div>
                    <div className="text-xs text-slate-400 leading-relaxed">
                        {sentiment.drift_gap < -0.03 ? (
                            <>Options are pricing <span className="text-red-400 font-medium">lower returns</span> than the realized trend. Put skew is steep &mdash; market participants are hedging.</>
                        ) : sentiment.drift_gap > 0.03 ? (
                            <>Options are pricing <span className="text-green-400 font-medium">higher returns</span> than the realized trend. Call skew is steep &mdash; market is speculative.</>
                        ) : (
                            <>Implied and realized drift are <span className="text-yellow-400 font-medium">in balance</span>. No strong directional bias in the options market.</>
                        )}
                        {sentiment.vol_spread > 0.02 && (
                            <> Elevated <span className="text-amber-400 font-medium">fear premium</span> in volatility.</>
                        )}
                        {sentiment.vol_spread < -0.02 && (
                            <> Options are <span className="text-cyan-400 font-medium">cheap</span> vs realized &mdash; complacency risk.</>
                        )}
                    </div>
                </div>
            </div>
            <ChartExplainer>
                <p className="pt-2"><strong className="text-slate-300">What this shows:</strong> A comparison between what options markets <em>imply</em> about future returns and volatility vs. what has actually been <em>realized</em> over the recent lookback period.</p>
                <p><strong className="text-slate-300">Drift (Annualized):</strong> Implied drift is the market's forward-looking expected return derived from option skew. Realized drift is the actual annualized return over the lookback window. A large negative gap means options are pricing worse outcomes than recent reality &mdash; hedging demand is high.</p>
                <p><strong className="text-slate-300">Volatility (Annualized):</strong> Implied vol is the ATM option-implied volatility. Realized vol is the historical standard deviation of returns. When implied &gt; realized (positive spread), options are "expensive" &mdash; the market is paying a fear premium.</p>
                <p><strong className="text-slate-300">The gauge bar:</strong> Positioned based on the drift gap. Left (red) = hedging/fearful market, center (yellow) = neutral, right (green) = speculative/bullish. The pointer shows where sentiment currently sits.</p>
                <p><strong className="text-slate-300">Signals:</strong> <span className="text-red-400">Hedging</span> = put skew is steep, market fears downside. <span className="text-yellow-400">Neutral</span> = balanced. <span className="text-green-400">Speculative</span> = call skew is steep, market expects upside.</p>
            </ChartExplainer>
        </div>
    );
};
