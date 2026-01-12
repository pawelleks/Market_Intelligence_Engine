import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Activity, TrendingUp, AlertTriangle, CheckCircle, XCircle, HelpCircle } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const PredictionAnalysisDashboard = () => {
    const [dashboardData, setDashboardData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeSection, setActiveSection] = useState('summary');

    useEffect(() => {
        const loadData = async () => {
            try {
                // Load dashboard JSON
                // Use relative path if no env var, to allow proxying by Caddy
                const baseUrl = import.meta.env.VITE_API_URL || '';
                const response = await fetch(`${baseUrl}/api/v1/analysis/prediction/dashboard`);

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();
                setDashboardData(data);
                setLoading(false);
            } catch (err) {
                console.error('Error loading dashboard data:', err);
                setError(err.message);
                setLoading(false);
            }
        };

        loadData();
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
                <div className="text-center">
                    <div className="inline-block animate-spin rounded-full h-16 w-16 border-b-2 border-blue-500 mb-4"></div>
                    <div className="text-slate-300 text-lg">Loading Prediction Analysis...</div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
                <div className="bg-red-900/20 border border-red-500/50 rounded-lg p-8 max-w-md">
                    <AlertTriangle className="w-12 h-12 text-red-400 mb-4" />
                    <h3 className="text-xl font-bold text-red-400 mb-2">Error Loading Data</h3>
                    <p className="text-slate-300">{error}</p>
                    <p className="text-sm text-slate-400 mt-4">
                        Make sure the prediction analysis data files have been generated.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white p-6">
            {/* Header */}
            <div className="max-w-7xl mx-auto mb-8">
                <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-t-lg p-8 shadow-2xl">
                    <h1 className="text-4xl font-bold mb-3">Prediction Analysis Framework</h1>
                    <p className="text-lg text-blue-100 mb-4">
                        Comprehensive evaluation of 9 economic models' recession prediction performance
                    </p>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center mt-6">
                        <div className="bg-white/10 rounded-lg p-3">
                            <div className="text-3xl font-bold text-yellow-300">{dashboardData?.summary?.total_models}</div>
                            <div className="text-sm text-blue-100">Models Analyzed</div>
                        </div>
                        <div className="bg-white/10 rounded-lg p-3">
                            <div className="text-3xl font-bold text-yellow-300">{dashboardData?.summary?.total_signals}</div>
                            <div className="text-sm text-blue-100">TROUBLE Signals</div>
                        </div>
                        <div className="bg-white/10 rounded-lg p-3">
                            <div className="text-3xl font-bold text-yellow-300">87%</div>
                            <div className="text-sm text-blue-100">Blow-off Tops</div>
                        </div>
                        <div className="bg-white/10 rounded-lg p-3">
                            <div className="text-3xl font-bold text-green-300">{dashboardData?.summary?.best_model}</div>
                            <div className="text-sm text-blue-100">Top Performer</div>
                        </div>
                    </div>
                </div>

                {/* Navigation Tabs */}
                <div className="bg-slate-800/50 rounded-b-lg px-6 py-3 flex gap-4 overflow-x-auto border-t border-slate-700">
                    {[
                        { id: 'summary', label: 'Summary', icon: Activity },
                        { id: 'scorecard', label: 'Model Scorecard', icon: TrendingUp },
                        { id: 'findings', label: 'Key Findings', icon: AlertTriangle },
                        { id: 'strategy', label: 'Strategy', icon: CheckCircle },
                        { id: 'reports', label: 'Reports', icon: HelpCircle }
                    ].map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveSection(tab.id)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${activeSection === tab.id
                                ? 'bg-blue-600 text-white'
                                : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
                                }`}
                        >
                            <tab.icon className="w-5 h-5" />
                            {tab.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Content Sections */}
            <div className="max-w-7xl mx-auto">
                {activeSection === 'summary' && <SummarySection data={dashboardData} />}
                {activeSection === 'scorecard' && <ScorecardSection data={dashboardData} />}
                {activeSection === 'findings' && <FindingsSection data={dashboardData} />}
                {activeSection === 'strategy' && <StrategySection />}
                {activeSection === 'reports' && <ReportsSection />}
            </div>
        </div>
    );
};

// Summary Section Component
const SummarySection = ({ data }) => (
    <div className="space-y-6">
        {/* Blow-off Top Discovery */}
        <div className="bg-gradient-to-br from-amber-900/30 to-red-900/30 border border-amber-500/50 rounded-lg p-6">
            <div className="flex items-start gap-4">
                <AlertTriangle className="w-12 h-12 text-amber-400 flex-shrink-0" />
                <div>
                    <h3 className="text-2xl font-bold text-amber-300 mb-2">⚠️ Critical Discovery: Blow-off Top Phenomenon</h3>
                    <p className="text-lg text-slate-200 mb-3">
                        <strong>87% of recession signals</strong> were followed by <strong>market rallies of 5-20%</strong> before eventual decline.
                    </p>
                    <div className="bg-amber-950/50 rounded-lg p-4 border border-amber-700/30">
                        <p className="text-amber-100 font-semibold mb-2">Implication:</p>
                        <p className="text-slate-300">
                            Recession signals ≠ immediate sell signals. Markets often rally <em>after</em> warning signs trigger,
                            creating a "blow-off top" before the eventual downturn. Don't short immediately when signals fire!
                        </p>
                    </div>
                </div>
            </div>
        </div>

        {/* Quick Stats Grid */}
        <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
                <h4 className="text-lg font-semibold text-blue-300 mb-3">Hit Rates</h4>
                <div className="space-y-2">
                    <div className="flex justify-between items-center">
                        <span className="text-slate-300">Average</span>
                        <span className="text-xl font-bold text-green-400">{data?.summary?.avg_hit_rate?.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-slate-300">Best (LAG)</span>
                        <span className="text-xl font-bold text-green-400">66.7%</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-slate-300">Lowest (ABCT)</span>
                        <span className="text-xl font-bold text-red-400">0%</span>
                    </div>
                </div>
            </div>

            <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
                <h4 className="text-lg font-semibold text-blue-300 mb-3">False Positives</h4>
                <div className="space-y-2">
                    <div className="flex justify-between items-center">
                        <span className="text-slate-300">Average</span>
                        <span className="text-xl font-bold text-amber-400">{data?.summary?.avg_fp_rate?.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-slate-300">Best (Hamilton)</span>
                        <span className="text-xl font-bold text-green-400">50%</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-slate-300">Insight</span>
                        <span className="text-sm text-slate-400">Fed interventions work!</span>
                    </div>
                </div>
            </div>

            <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
                <h4 className="text-lg font-semibold text-blue-300 mb-3">Model Correlation</h4>
                <div className="space-y-2">
                    <div className="flex justify-between items-center">
                        <span className="text-slate-300">Avg Agreement</span>
                        <span className="text-xl font-bold text-blue-400">77-92%</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-slate-300">Most Independent</span>
                        <span className="text-sm text-green-400">Recession Momentum</span>
                    </div>
                    <div className="flex justify-between items-center">
                        <span className="text-slate-300">Takeaway</span>
                        <span className="text-sm text-slate-400">Limited diversification</span>
                    </div>
                </div>
            </div>
        </div>

        {/* Data Coverage */}
        <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
            <h3 className="text-xl font-bold text-slate-200 mb-4">Data Coverage</h3>
            <div className="grid md:grid-cols-2 gap-4 text-sm">
                <div>
                    <p className="text-slate-400 mb-1">Date Range</p>
                    <p className="text-slate-200 font-semibold">1959-2026 (67 years)</p>
                </div>
                <div>
                    <p className="text-slate-400 mb-1">Recessions Analyzed</p>
                    <p className="text-slate-200 font-semibold">7-8 per model (varies by coverage)</p>
                </div>
                <div>
                    <p className="text-slate-400 mb-1">S&P 500 Observations</p>
                    <p className="text-slate-200 font-semibold">24,613 daily (1927-2025)</p>
                </div>
                <div>
                    <p className="text-slate-400 mb-1">Total Model Observations</p>
                    <p className="text-slate-200 font-semibold">3,661 across 9 models</p>
                </div>
            </div>
        </div>
    </div>
);

// Scorecard Section Component  
const ScorecardSection = ({ data }) => {
    const getScoreColor = (score) => {
        if (score >= 35) return 'bg-green-900/30 border-green-500/50';
        if (score >= 25) return 'bg-yellow-900/30 border-yellow-500/50';
        return 'bg-red-900/30 border-red-500/50';
    };

    const getMetricColor = (value, metric) => {
        if (metric === 'hit_rate') {
            if (value >= 60) return 'text-green-400';
            if (value >= 40) return 'text-yellow-400';
            return 'text-red-400';
        }
        if (metric === 'fp_rate') {
            if (value <= 55) return 'text-green-400';
            if (value <= 75) return 'text-yellow-400';
            return 'text-red-400';
        }
        if (metric === 'lead_time') {
            if (value >= 8 && value <= 15) return 'text-green-400';
            if (value < 20) return 'text-yellow-400';
            return 'text-red-400';
        }
        if (metric === 'return') {
            if (value < 0) return 'text-green-400';
            return 'text-amber-400';
        }
        return 'text-slate-300';
    };

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-200 mb-4">Model Performance Scorecard</h2>

            {/* Mobile-friendly cards */}
            <div className="space-y-4">
                {data?.scorecard?.map((model, idx) => (
                    <div
                        key={model.model}
                        className={`rounded-lg p-6 border ${getScoreColor(model.overall_score || 0)}`}
                    >
                        <div className="flex items-start justify-between mb-4">
                            <div>
                                <div className="flex items-center gap-3">
                                    <span className="text-3xl font-bold text-blue-400">#{idx + 1}</span>
                                    <h3 className="text-xl font-bold text-slate-100">{model.model.toUpperCase().replace('_', ' ')}</h3>
                                </div>
                                <p className="text-sm text-slate-400 mt-1">
                                    {model.years_coverage?.toFixed(0)} years coverage · {model.total_signals} signals
                                </p>
                            </div>
                            <div className="text-right">
                                <div className="text-3xl font-bold text-yellow-300">{model.overall_score?.toFixed(1)}</div>
                                <div className="text-sm text-slate-400">Score</div>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div>
                                <p className="text-xs text-slate-400 mb-1">Hit Rate</p>
                                <p className={`text-lg font-bold ${getMetricColor(model.hit_rate, 'hit_rate')}`}>
                                    {model.hit_rate?.toFixed(1)}%
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-400 mb-1">False Positives</p>
                                <p className={`text-lg font-bold ${getMetricColor(model.false_positive_rate, 'fp_rate')}`}>
                                    {model.false_positive_rate?.toFixed(1)}%
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-400 mb-1">Avg Lead Time</p>
                                <p className={`text-lg font-bold ${getMetricColor(model.avg_lead_time, 'lead_time')}`}>
                                    {model.avg_lead_time?.toFixed(1)} mo
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-400 mb-1">Avg 12m Return</p>
                                <p className={`text-lg font-bold ${getMetricColor(model.avg_12m_return, 'return')}`}>
                                    {model.avg_12m_return?.toFixed(1)}%
                                </p>
                            </div>
                        </div>

                        {/* Assessment badge */}
                        {idx === 0 && (
                            <div className="mt-4 inline-block bg-green-600 text-white px-3 py-1 rounded-full text-sm font-semibold">
                                ⭐ Top Performer
                            </div>
                        )}
                        {model.hit_rate >= 60 && (
                            <div className="mt-4 inline-block bg-green-700 text-white px-3 py-1 rounded-full text-sm mr-2">
                                ✅ High Hit Rate
                            </div>
                        )}
                        {model.false_positive_rate <= 55 && (
                            <div className="mt-4 inline-block bg-blue-700 text-white px-3 py-1 rounded-full text-sm">
                                🎯 Low False Positives
                            </div>
                        )}
                        {model.hit_rate === 0 && (
                            <div className="mt-2 inline-block bg-slate-600 text-slate-200 px-3 py-1 rounded-full text-sm" title="This model detects different economic phenomena (e.g., credit peaks) that may not align with NBER recession dates">
                                ⚠️ Detects Non-Recession Cycles
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
};

// Key Findings Section
const FindingsSection = () => (
    <div className="space-y-6">
        <h2 className="text-2xl font-bold text-slate-200 mb-4">Key Findings & Insights</h2>

        {/* Finding cards */}
        <div className="space-y-4">
            <div className="bg-gradient-to-r from-green-900/30 to-green-800/30 border border-green-500/50 rounded-lg p-6">
                <h3 className="text-xl font-bold text-green-300 mb-3">1. Best Models by Different Metrics</h3>
                <div className="space-y-4 text-slate-200">
                    <div className="bg-slate-800/50 rounded-lg p-4">
                        <p className="font-semibold text-yellow-300 mb-2">📊 Highest Overall Score: HP Filter (31.7)</p>
                        <ul className="space-y-1 text-sm">
                            <li>✅ Best composite score across all metrics</li>
                            <li>⚠️ 87.5% false positive rate limits actionability</li>
                            <li>💡 Use for early cycle awareness and strategic planning</li>
                        </ul>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-4">
                        <p className="font-semibold text-blue-300 mb-2">🎯 Best for Trading: Hamilton (Score 29.7, Rank #3)</p>
                        <ul className="space-y-1 text-sm">
                            <li>✅ <strong>50% false positive rate</strong> - only model below 60%</li>
                            <li>✅ <strong>Negative avg 12m returns</strong> - actually predicts market declines</li>
                            <li>✅ 9.75 month lead time - actionable for tactical positioning</li>
                            <li>💡 Use as primary signal for portfolio hedging decisions</li>
                        </ul>
                    </div>
                    <p className="text-sm text-slate-400 italic">
                        Recommendation: Use HP Filter for early awareness, Hamilton for action triggers.
                    </p>
                </div>
            </div>

            <div className="bg-gradient-to-r from-blue-900/30 to-blue-800/30 border border-blue-500/50 rounded-lg p-6">
                <h3 className="text-xl font-bold text-blue-300 mb-3">2. LEI/COI and LAG Have Best Hit Rates</h3>
                <ul className="space-y-2 text-slate-200">
                    <li>✅ <strong>LEI/COI: 66.7% hit rate</strong> - caught 2 of 3 recessions in analysis period</li>
                    <li>✅ <strong>LAG: 62.5% hit rate</strong> - strong lagging confirmation signal</li>
                    <li>✅ <strong>Business Cycle: 66.7% hit rate</strong> - good phase identification</li>
                    <li>💡 <strong>Use for confirmation</strong> - pair with Hamilton for dual-signal approach</li>
                </ul>
            </div>

            <div className="bg-gradient-to-r from-amber-900/30 to-orange-900/30 border border-amber-500/50 rounded-lg p-6">
                <h3 className="text-xl font-bold text-amber-300 mb-3">3. High Model Correlation (77-92%)</h3>
                <ul className="space-y-2 text-slate-200">
                    <li>📊 <strong>All models agree 77-92% of the time</strong> - limited independence</li>
                    <li>✅ <strong>Good news</strong>: Validates that models detect real economic stress</li>
                    <li>⚠️ <strong>Bad news</strong>: Limited diversification benefit from combining models</li>
                    <li>💡 <strong>Implication</strong>: All models track same underlying macro conditions (GDP, employment, credit)</li>
                </ul>
            </div>

            <div className="bg-gradient-to-r from-red-900/30 to-pink-900/30 border border-red-500/50 rounded-lg p-6">
                <h3 className="text-xl font-bold text-red-300 mb-3">4. High False Positive Rates Everywhere</h3>
                <ul className="space-y-2 text-slate-200">
                    <li>📈 <strong>All models: 50-100% FP rates</strong> - many signals don't lead to recessions</li>
                    <li>🎯 <strong>Why?</strong> Models detect *potential* recession risk, not certainty</li>
                    <li>✅ <strong>Silver lining</strong>: Reflects Fed's success at preventing recessions</li>
                    <li>💡 <strong>Takeaway</strong>: Policy interventions (rate cuts, QE) often prevent predicted downturns</li>
                </ul>
            </div>

            <div className="bg-gradient-to-r from-purple-900/30 to-indigo-900/30 border border-purple-500/50 rounded-lg p-6">
                <h3 className="text-xl font-bold text-purple-300 mb-3">5. Lead Time Clusters</h3>
                <div className="space-y-3 text-slate-200">
                    <div>
                        <p className="font-semibold text-purple-200">Very Early ({'>'}20mo): HP Filter (26.5mo)</p>
                        <p className="text-sm text-slate-400">→ Too early for trading, good for policy planning</p>
                    </div>
                    <div>
                        <p className="font-semibold text-blue-200">Early (15-20mo): LAG (16.5mo), LEI/COI (18.5mo)</p>
                        <p className="text-sm text-slate-400">→ Strategic positioning, portfolio hedging</p>
                    </div>
                    <div>
                        <p className="font-semibold text-green-200">Medium (10-15mo): Recession Momentum (13mo)</p>
                        <p className="text-sm text-slate-400">→ Tactical warning, monitor closely</p>
                    </div>
                    <div>
                        <p className="font-semibold text-yellow-200">Late (5-10mo): Hamilton (5mo), Minsky (7mo)</p>
                        <p className="text-sm text-slate-400">→ Confirmation signals, time for action</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
);

// Strategy Section
const StrategySection = () => (
    <div className="space-y-6">
        <h2 className="text-2xl font-bold text-slate-200 mb-4">Recommended Strategies</h2>

        {/* Tiered Strategy (Recommended) */}
        <div className="bg-gradient-to-br from-green-900/30 to-emerald-900/30 border-2 border-green-500/70 rounded-lg p-6 shadow-xl">
            <div className="flex items-start gap-3 mb-4">
                <CheckCircle className="w-8 h-8 text-green-400 flex-shrink-0 mt-1" />
                <div>
                    <h3 className="text-2xl font-bold text-green-300">⭐ Tiered Strategy (RECOMMENDED)</h3>
                    <p className="text-slate-300 mt-1">Combine early warning with late confirmation for best results</p>
                </div>
            </div>

            <div className="space-y-4 mt-6">
                {/* Tier 1 */}
                <div className="bg-yellow-950/30 border border-yellow-600/50 rounded-lg p-4">
                    <h4 className="text-lg font-bold text-yellow-300 mb-2">Tier 1: Early Warning (16-18 months)</h4>
                    <p className="text-slate-200 mb-3">
                        <strong>Models:</strong> LAG Index + LEI/COI
                    </p>
                    <p className="text-slate-300 text-sm mb-2">
                        <strong>Action:</strong> Reduce risk exposure, increase cash position, add defensive sectors
                    </p>
                    <p className="text-slate-400 text-sm">
                        Accept higher false positive rate for advance notice. Don't overreact - use for strategic positioning.
                    </p>
                </div>

                {/* Monitoring Phase */}
                <div className="flex items-center justify-center">
                    <div className="text-center py-4">
                        <div className="text-slate-400 mb-2">↓</div>
                        <div className="bg-amber-900/30 border border-amber-600/50 rounded-lg px-6 py-3">
                            <p className="text-amber-300 font-semibold">MONITORING PHASE</p>
                            <p className="text-sm text-slate-300 mt-1">Expect 5-20% rally (blow-off top)</p>
                            <p className="text-sm text-slate-400">Watch for late confirmation signals</p>
                        </div>
                        <div className="text-slate-400 mt-2">↓</div>
                    </div>
                </div>

                {/* Tier 2 */}
                <div className="bg-red-950/30 border border-red-600/50 rounded-lg p-4">
                    <h4 className="text-lg font-bold text-red-300 mb-2">Tier 2: Late Confirmation (5-7 months)</h4>
                    <p className="text-slate-200 mb-3">
                        <strong>Models:</strong> Hamilton + Minsky
                    </p>
                    <p className="text-slate-300 text-sm mb-2">
                        <strong>Action:</strong> Take decisive action - exit equities, buy hedges, sell rallies
                    </p>
                    <p className="text-slate-400 text-sm">
                        Lower false positive rate = higher conviction. Time to act, not just monitor.
                    </p>
                </div>

                {/* Outcome */}
                <div className="flex items-center justify-center">
                    <div className="text-center py-4">
                        <div className="text-slate-400 mb-2">↓</div>
                        <div className="bg-slate-800 border border-slate-600 rounded-lg px-6 py-3">
                            <p className="text-slate-200 font-semibold">RECESSION PHASE</p>
                            <p className="text-sm text-slate-400 mt-1">Portfolio protected, positioned for recovery</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        {/* Alternative Strategies */}
        <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
                <h4 className="text-lg font-bold text-blue-300 mb-3">Single Model Strategy (Simplicity)</h4>
                <p className="text-slate-200 mb-3"><strong>Use:</strong> Hamilton alone</p>
                <p className="text-slate-300 text-sm mb-3">
                    <strong>Pros:</strong> Best overall score, lowest FP rate, actually predicts declines
                </p>
                <p className="text-slate-400 text-sm">
                    <strong>Cons:</strong> Only 50% hit rate - misses half of recessions
                </p>
            </div>

            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
                <h4 className="text-lg font-bold text-blue-300 mb-3">Dual Confirmation (Independence)</h4>
                <p className="text-slate-200 mb-3"><strong>Use:</strong> Recession Momentum + Minsky</p>
                <p className="text-slate-300 text-sm mb-3">
                    <strong>Pros:</strong> Most independent pair (73% agreement), reduces false positives
                </p>
                <p className="text-slate-400 text-sm">
                    <strong>Trigger:</strong> Both models signal TROUBLE simultaneously
                </p>
            </div>
        </div>

        {/* Trading Tactics */}
        <div className="bg-purple-900/30 border border-purple-500/50 rounded-lg p-6">
            <h4 className="text-xl font-bold text-purple-300 mb-4">Trading Tactics for Blow-off Tops</h4>
            <div className="grid md:grid-cols-2 gap-6">
                <div>
                    <p className="font-semibold text-purple-200 mb-2">❌ Don't Do This:</p>
                    <ul className="space-y-1 text-sm text-slate-300">
                        <li>• Short immediately when signal triggers</li>
                        <li>• Go all-in on puts at first warning</li>
                        <li>• Sell entire portfolio at once</li>
                        <li>• Panic on early signals</li>
                    </ul>
                </div>
                <div>
                    <p className="font-semibold text-green-200 mb-2">✅ Do This Instead:</p>
                    <ul className="space-y-1 text-sm text-slate-300">
                        <li>• Sell rallies into strength (5-20% gains)</li>
                        <li>• Use 6-12 month options for timing</li>
                        <li>• Reduce exposure gradually</li>
                        <li>• Use volatility strategies (sell calls, buy puts)</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
);

// Reports Section
const ReportsSection = () => {
    const models = [
        { name: 'Hamilton', rank: 1, score: 43.8 },
        { name: 'Recession Momentum', rank: 2, score: 31.7 },
        { name: 'LAG', rank: 3, score: 25.9 },
        { name: 'Minsky', rank: 4, score: 25.1 },
        { name: 'LEI/COI', rank: 5, score: 22.5 },
        { name: 'Business Cycle', rank: 6, score: 20.1 },
        { name: 'HP Filter', rank: 7, score: 18.7 },
        { name: 'ABCT', rank: 8, score: 15.2 },
        { name: 'Fed Trap', rank: 9, score: 0 }
    ];

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold text-slate-200 mb-4">Individual Model Reports</h2>
            <p className="text-slate-300 mb-6">
                Detailed analysis reports for each model including recession-by-recession breakdown,
                market performance analysis, and customized recommendations.
            </p>

            <div className="grid md:grid-cols-3 gap-4">
                {models.map(model => (
                    <div
                        key={model.name}
                        className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 hover:border-blue-500/50 transition-all cursor-pointer"
                    >
                        <div className="flex items-start justify-between mb-3">
                            <div>
                                <div className="text-sm text-slate-400">Rank #{model.rank}</div>
                                <h4 className="text-lg font-bold text-slate-200">{model.name}</h4>
                            </div>
                            <div className="text-right">
                                <div className="text-xl font-bold text-yellow-400">{model.score}</div>
                                <div className="text-xs text-slate-400">Score</div>
                            </div>
                        </div>
                        <Link
                            to={`/report-viewer?path=/public_docs/analysis/model_reports/${model.name.toLowerCase().replace(' ', '_')}_PREDICTION_REPORT.md`}
                            className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-semibold transition-colors"
                        >
                            View Full Report
                        </Link>
                    </div>
                ))}
            </div>

            <div className="bg-blue-900/30 border border-blue-500/50 rounded-lg p-6 mt-8">
                <h4 className="text-lg font-bold text-blue-300 mb-3">📊 Report Contents</h4>
                <div className="grid md:grid-cols-2 gap-4 text-sm text-slate-300">
                    <ul className="space-y-1">
                        <li>• Executive summary with key metrics</li>
                        <li>• Recession-by-recession prediction analysis</li>
                        <li>• False positive assessment</li>
                        <li>• Market performance after signals</li>
                    </ul>
                    <ul className="space-y-1">
                        <li>• Blow-off top analysis</li>
                        <li>• Customized recommendations</li>
                        <li>• Use case guidance</li>
                        <li>• Model limitations</li>
                    </ul>
                </div>
            </div>
        </div>
    );
};

export default PredictionAnalysisDashboard;
