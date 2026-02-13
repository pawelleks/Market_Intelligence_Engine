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

            <div className="mt-4 p-3 bg-blue-900/20 border border-blue-700/30 rounded text-xs text-blue-200">
                <strong>Note:</strong> These metrics use arbitrage-enforced relationships (put-call parity) and
                direct market pricing (ATM straddles), making them robust to data quality issues.
            </div>
        </div>
    );
};
