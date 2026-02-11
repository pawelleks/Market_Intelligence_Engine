import React, { Fragment } from 'react';

interface ProbabilityEducationModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export const ProbabilityEducationModal: React.FC<ProbabilityEducationModalProps> = ({ isOpen, onClose }) => {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="relative w-full max-w-2xl bg-[#0e1525] border border-slate-700 rounded-xl shadow-2xl max-h-[90vh] overflow-y-auto animate-in zoom-in-95 duration-200">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-slate-700/50 sticky top-0 bg-[#0e1525] z-10">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-500/10 rounded-lg">
                            <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <h2 className="text-xl font-bold text-white">How to Read These Charts</h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 space-y-8 text-slate-300">

                    {/* Section 1: Bell Curves */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 mb-2">
                            <div className="w-1 h-6 bg-purple-500 rounded-full"></div>
                            <h3 className="text-lg font-bold text-white">Chart 1: The Probability Bell Curves (Layered Hills)</h3>
                        </div>
                        <div className="pl-3 border-l-2 border-slate-800 space-y-3">
                            <div>
                                <h4 className="font-semibold text-slate-200 mb-1">What is this?</h4>
                                <p className="text-sm leading-relaxed">This chart shows where the market expects the SPX price to be on specific future dates (e.g., 7 days vs. 45 days).</p>
                            </div>

                            <div>
                                <h4 className="font-semibold text-slate-200 mb-2">How to Read It:</h4>
                                <ul className="space-y-2 text-sm">
                                    <li className="flex items-start gap-2">
                                        <span className="text-purple-400 mt-1">•</span>
                                        <span><strong className="text-slate-200">The Peak:</strong> The highest point of the curve is the Most Likely Price (Market Consensus).</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <span className="text-purple-400 mt-1">•</span>
                                        <div>
                                            <strong className="text-slate-200">The Width:</strong>
                                            <div className="mt-1 ml-1 space-y-1 text-slate-400">
                                                <div className="flex items-center gap-2"><span className="text-green-400 text-xs">Tall & Skinny</span> = Low Volatility (Market is confident).</div>
                                                <div className="flex items-center gap-2"><span className="text-red-400 text-xs">Short & Wide</span> = High Volatility (Market is fearful).</div>
                                            </div>
                                        </div>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <span className="text-purple-400 mt-1">•</span>
                                        <span><strong className="text-slate-200">The Layers:</strong> Notice how the curves get flatter and wider as you look further out in time. This is natural—uncertainty increases with time.</span>
                                    </li>
                                </ul>
                            </div>

                            <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                                <h4 className="font-semibold text-amber-400 text-xs uppercase tracking-wide mb-1">Trader Insight</h4>
                                <p className="text-sm">If the curve is "leaning" to the left (skewed), traders are paying more for downside protection (Puts), signaling fear of a drop.</p>
                            </div>
                        </div>
                    </div>

                    <div className="h-px bg-slate-800"></div>

                    {/* Section 2: The Cone (Forward Projection) */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 mb-2">
                            <div className="w-1 h-6 bg-red-500 rounded-full"></div>
                            <h3 className="text-lg font-bold text-white">Chart 2: Market Forward Projection (The Cone)</h3>
                        </div>
                        <div className="pl-3 border-l-2 border-slate-800 space-y-3">
                            <div>
                                <h4 className="font-semibold text-slate-200 mb-1">What is this?</h4>
                                <p className="text-sm leading-relaxed">This chart projects the future possible range of the S&P 500 based on current options prices. Think of it as the "Hurricane Cone" for the stock market.</p>
                            </div>

                            <div>
                                <h4 className="font-semibold text-slate-200 mb-2">How to Read the Zones:</h4>
                                <div className="grid grid-cols-1 gap-3">
                                    <div className="flex items-center gap-3 bg-red-900/10 p-2 rounded border border-red-900/20">
                                        <div className="w-4 h-4 rounded bg-red-500/20 border border-red-500 shrink-0"></div>
                                        <div className="text-sm"><strong className="text-red-300">Red Zone (95% Confidence):</strong> The market is 95% sure price will stay inside this outer band. Candles rarely leave this area.</div>
                                    </div>
                                    <div className="flex items-center gap-3 bg-yellow-900/10 p-2 rounded border border-yellow-900/20">
                                        <div className="w-4 h-4 rounded bg-yellow-500/20 border border-yellow-500 shrink-0"></div>
                                        <div className="text-sm"><strong className="text-yellow-300">Gold Zone (50% Confidence):</strong> The "Likely Range". Price spends about half its time here.</div>
                                    </div>
                                    <div className="flex items-center gap-3 bg-slate-800/50 p-2 rounded border border-slate-700">
                                        <div className="w-8 h-0 border-t-2 border-dotted border-white shrink-0"></div>
                                        <div className="text-sm"><strong className="text-white">White Dotted Line:</strong> The Median (Fair Value). This is the market's consensus for the future price path.</div>
                                    </div>
                                </div>
                            </div>

                            <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                                <h4 className="font-semibold text-amber-400 text-xs uppercase tracking-wide mb-1">Trader Insight</h4>
                                <p className="text-sm">When price touches the <strong className="text-red-400">Red Band</strong>, it is statistically extended (overbought or oversold). Mean reversion to the center is common from these extremes.</p>
                            </div>
                        </div>
                    </div>

                </div>

                {/* Footer */}
                <div className="p-6 border-t border-slate-700 bg-[#0e1525] sticky bottom-0">
                    <button
                        onClick={onClose}
                        className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg transition-colors"
                    >
                        Got it
                    </button>
                </div>
            </div>
        </div>
    );
};
