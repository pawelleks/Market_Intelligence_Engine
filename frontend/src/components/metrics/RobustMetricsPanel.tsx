import React from 'react';
import { TrendingUp, Activity, Gauge } from 'lucide-react';

interface RobustMetricsPanelProps {
    forwardPrice?: number;
    spotPrice?: number;
    expectedMove?: number;
    skew?: number;
    dte?: number; // Days to expiration for these metrics
    loading?: boolean;
}

export const RobustMetricsPanel: React.FC<RobustMetricsPanelProps> = ({
    forwardPrice,
    spotPrice,
    expectedMove,
    skew,
    dte = 30, // Default to 30 DTE
    loading = false
}) => {
    if (loading) {
        return (
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Market-Implied Metrics</h3>
                <div className="text-gray-400">Loading...</div>
            </div>
        );
    }

    const forwardDrift = forwardPrice && spotPrice ? ((forwardPrice - spotPrice) / spotPrice) * 100 : 0;
    const expectedMovePct = expectedMove && spotPrice ? (expectedMove / spotPrice) * 100 : 0;

    const getSkewLabel = (skewValue: number) => {
        if (skewValue > 5) return { label: 'BEARISH', color: 'text-red-400' };
        if (skewValue < -5) return { label: 'BULLISH', color: 'text-green-400' };
        return { label: 'NEUTRAL', color: 'text-gray-400' };
    };

    const skewInfo = skew !== undefined ? getSkewLabel(skew) : null;

    const [isExplained, setIsExplained] = React.useState(false);

    return (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Market-Implied Metrics</h3>
            <p className="text-xs text-gray-400 mb-4">
                Battle-tested practitioner metrics using put-call parity and ATM straddles
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Forward Price */}
                <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
                    <div className="flex items-center gap-2 mb-2">
                        <TrendingUp className="w-4 h-4 text-blue-400" />
                        <span className="text-sm text-gray-400">Forward Price ({dte} DTE)</span>
                    </div>
                    {forwardPrice !== undefined ? (
                        <>
                            <div className="text-2xl font-bold text-white">
                                ${forwardPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </div>
                            <div className={`text-sm mt-1 ${forwardDrift >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {forwardDrift >= 0 ? '+' : ''}{forwardDrift.toFixed(2)}% drift to {dte}d
                            </div>
                        </>
                    ) : (
                        <div className="text-gray-500">N/A</div>
                    )}
                </div>

                {/* Expected Move */}
                <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
                    <div className="flex items-center gap-2 mb-2">
                        <Activity className="w-4 h-4 text-purple-400" />
                        <span className="text-sm text-gray-400">Expected Move ({dte} DTE)</span>
                    </div>
                    {expectedMove !== undefined ? (
                        <>
                            <div className="text-2xl font-bold text-white">
                                ±${expectedMove.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                            </div>
                            <div className="text-sm text-gray-400 mt-1">
                                ±{expectedMovePct.toFixed(1)}% (1σ to {dte}d exp)
                            </div>
                        </>
                    ) : (
                        <div className="text-gray-500">N/A</div>
                    )}
                </div>

                {/* IV Skew */}
                <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
                    <div className="flex items-center gap-2 mb-2">
                        <Gauge className="w-4 h-4 text-yellow-400" />
                        <span className="text-sm text-gray-400">IV Skew ({dte} DTE)</span>
                    </div>
                    {skew !== undefined && skewInfo ? (
                        <>
                            <div className="text-2xl font-bold text-white">
                                {skew >= 0 ? '+' : ''}{skew.toFixed(1)}%
                            </div>
                            <div className={`text-sm mt-1 font-semibold ${skewInfo.color}`}>
                                {skewInfo.label}
                            </div>
                        </>
                    ) : (
                        <div className="text-gray-500">N/A</div>
                    )}
                </div>
            </div>

            <div className="mt-4">
                <button
                    onClick={() => setIsExplained(!isExplained)}
                    className="flex items-center gap-2 text-xs text-blue-400 hover:text-blue-300 transition-colors"
                >
                    {isExplained ? 'Hide Explanation' : 'How to read this?'}
                </button>

                {isExplained && (
                    <div className="mt-4 p-4 bg-slate-900/50 border border-slate-700/50 rounded-lg text-sm text-slate-300 space-y-4 animate-in fade-in slide-in-from-top-2">
                        <p className="text-slate-400 italic">
                            The "Market-Implied Metrics" on the Implied Probability page are designed to give you a quick read on what the options market is pricing in, independent of technical analysis or news.
                        </p>

                        <div>
                            <h4 className="font-semibold text-blue-400 mb-1">1. Forward Price</h4>
                            <p className="mb-1"><strong>What it means:</strong> This is the market's consensus for where the price will be at expiration (e.g., 30 days from now). Ideally, this should match the current Spot Price, but it differs due to interest rates (cost of carry) and dividends.</p>
                            <p className="mb-1"><strong>Bullish/Bearish Signal:</strong> If the Forward Price is significantly higher than Spot (after accounting for interest rates), it implies "Call Skew" or upside demand. If it's lower, it implies heavy Put buying.</p>
                            <p className="mb-1"><strong>How it is calculated:</strong> We use Put-Call Parity. The formula derives the price that guarantees no arbitrage between the stock and the options:</p>
                            <code className="block bg-slate-950 p-2 rounded text-xs text-blue-200 my-1 font-mono">
                                F = K + e^(rT) × (Call - Put)
                            </code>
                            <p className="text-xs text-slate-400">
                                We look at the ATM (At-The-Money) Strike (K), iterate the difference between Call and Put prices, and adjust for risk-free rate (r) and time to expiration (T).
                            </p>
                        </div>

                        <div>
                            <h4 className="font-semibold text-purple-400 mb-1">2. Expected Move</h4>
                            <p className="mb-1"><strong>What it means:</strong> This represents the magnitude of the move (up or down) that the market expects with ~68% confidence (1 Standard Deviation) by the expiration date. It defines the "normal" trading range.</p>
                            <p className="mb-1"><strong>How it is calculated:</strong> We rely on the ATM Straddle price (cost of buying both a Call and a Put at the expected price).</p>
                            <code className="block bg-slate-950 p-2 rounded text-xs text-purple-200 my-1 font-mono">
                                Practitioner Rule: Expected Move ≈ 0.85 × (ATM Call + ATM Put)<br />
                                Theoretical: Spot × Implied Volatility × √Time
                            </code>
                            <p className="text-xs text-slate-400">
                                If the Straddle costs $100, the market expects the stock to move roughly ±$85 by expiration.
                            </p>
                        </div>

                        <div>
                            <h4 className="font-semibold text-yellow-400 mb-1">3. IV Skew</h4>
                            <p className="mb-1"><strong>What it means:</strong> This measures the "Fear vs. Greed" balance. It compares the cost of downside protection (Puts) versus upside speculation (Calls).</p>
                            <ul className="list-disc pl-5 mb-1 space-y-1">
                                <li><span className="text-red-400">Positive Skew (Bearish):</span> OTM Puts are much more expensive than OTM Calls. Investors are terrified of a crash.</li>
                                <li><span className="text-green-400">Negative Skew (Bullish):</span> OTM Calls are more expensive. Investors are chasing upside (FOMO).</li>
                            </ul>
                            <p className="mb-1"><strong>How it is calculated:</strong> We compare the Implied Volatility (IV) of options at equal distances from the spot price (e.g., 25 Delta Puts vs. 25 Delta Calls).</p>
                            <code className="block bg-slate-950 p-2 rounded text-xs text-yellow-200 my-1 font-mono">
                                Skew = IV(25Δ Put) - IV(25Δ Call)
                            </code>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
