import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import Plot from 'react-plotly.js';
import {
    getHealthColor,
    getHealthDots,
    getTrendIcon,
    getSparklineColor
} from './utils';
import { formatValueWithUnit } from '../../../utils/formatters';

const Overview = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const navigate = useNavigate();

    useEffect(() => {
        fetchOverviewData();
    }, []);

    const fetchOverviewData = async () => {
        try {
            // Use /api/v1 prefix based on your App.jsx config
            const response = await axios.get('/api/v1/jpm-dashboard/overview');
            setData(response.data);
            setLoading(false);
        } catch (error) {
            console.error('Failed to fetch dashboard data:', error);
            setError('Unable to load dashboard data. Please check connection and try again.');
            setLoading(false);
        }
    };

    const calculateOverallHealth = () => {
        if (!data?.indicators) return 0;
        const scores = data.indicators.map(ind => ind.health_score || 0);
        return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
    };

    const getOverallStatus = (score) => {
        if (score >= 80) return "Strong economic expansion";
        if (score >= 60) return "Moderate growth, mixed signals";
        if (score >= 40) return "Slowing economy, caution advised";
        return "Contraction / Recession risk elevated";
    };

    const getOverallTrendIcon = () => {
        if (!data?.indicators) return '→';

        // Use backend data if available
        if (data.overall_health_30d !== undefined && data.overall_health_30d !== null) {
            const current = data.overall_health;
            const previous = data.overall_health_30d;
            const diff = current - previous;

            let icon = '→';
            let color = 'text-amber-400';
            let text = 'stable';

            if (diff > 0) {
                icon = '↗';
                color = 'text-emerald-400';
                text = 'Improving';
            } else if (diff < 0) {
                icon = '↘';
                color = 'text-red-400';
                text = 'Deteriorating';
            }

            return (
                <div className={`flex flex-col items-end ${color}`}>
                    <div className="text-3xl font-light">{icon}</div>
                    <div className="text-lg font-medium mt-1">
                        {text}: {previous} → {current}
                    </div>
                    <div className="text-xs opacity-75">over last 30 days</div>
                </div>
            );
        }

        // Fallback
        const improving = data.indicators.filter(i => i.trend_direction === 'up' || i.trend_direction === 'improving').length;
        if (improving > 5) return '↗ Improving trend over last 30 days';
        if (improving < 3) return '↘ Deteriorating trend over last 30 days';
        return '→ Stable trend over last 30 days';
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-page text-white">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-cyan-500 mx-auto mb-4"></div>
                    <div className="text-gray-400">Loading economic data...</div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-page text-white">
                <div className="text-center max-w-md p-6">
                    <div className="text-red-500 text-5xl mb-4">⚠️</div>
                    <h2 className="text-2xl font-bold text-white mb-2">Unable to Load Data</h2>
                    <p className="text-gray-400 mb-6">{error}</p>
                    <button
                        onClick={() => { setLoading(true); fetchOverviewData(); }}
                        className="px-6 py-3 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg"
                    >
                        Try Again
                    </button>
                </div>
            </div>
        );
    }

    const overallScore = calculateOverallHealth();

    return (
        <div className="p-6 bg-page min-h-screen text-white">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white mb-2">JPM Economic Dashboard</h1>
                <p className="text-gray-400">
                    Track 10 key economic indicators recommended by JPMorgan for business owners.
                </p>
            </div>

            {/* BETA WARNING BANNER */}
            <div className="mb-6 p-4 bg-yellow-900/20 border border-yellow-500/50 rounded-lg flex items-start gap-3">
                <div className="text-yellow-500 text-xl">⚠️</div>
                <div>
                    <h3 className="font-bold text-yellow-500 text-sm uppercase tracking-wider mb-1">
                        BETA: Work in Progress
                    </h3>
                    <p className="text-sm text-gray-300">
                        This model is currently under construction. Data feeds and scores are being actively calibrated and may change without notice.
                    </p>
                </div>
            </div>

            {/* Overall Health Banner */}
            <div className="mb-8 p-6 border-2 border-cyan-500 rounded-lg bg-gray-900/50">
                <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                    <div>
                        <div className="text-sm text-gray-400 uppercase tracking-widest">Overall Economic Health</div>
                        <div className="flex items-baseline gap-3 mt-1">
                            <div className="text-4xl font-bold text-cyan-400">
                                {overallScore}/100
                            </div>
                            <div className="text-lg text-white font-medium">
                                {getOverallStatus(overallScore)}
                            </div>
                        </div>
                    </div>
                    <div className="text-left md:text-right">
                        {typeof getOverallTrendIcon() === 'string' ? (
                            <div className="text-xl text-gray-300 font-light">{getOverallTrendIcon()}</div>
                        ) : (
                            getOverallTrendIcon()
                        )}
                        <div className="text-xs text-gray-500 mt-2">
                            Last updated: {data.last_updated ? new Date(data.last_updated).toLocaleString() : 'N/A'}
                        </div>
                    </div>
                </div>
            </div>

            {/* Indicator Grid */}
            {/* Top 4 Indicators (Key Drivers) */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                {data.indicators.slice(0, 4).map(indicator => (
                    <IndicatorCard key={indicator.id} indicator={indicator} navigate={navigate} />
                ))}
            </div>

            {/* Remaining 6 Indicators */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
                {data.indicators.slice(4).map(indicator => (
                    <IndicatorCard key={indicator.id} indicator={indicator} navigate={navigate} />
                ))}
            </div>

            {/* About Section */}
            <div className="mt-12 p-6 bg-gray-900/30 rounded-lg border border-gray-700">
                <h3 className="text-xl font-bold text-white mb-4">About This Dashboard</h3>
                <div className="text-gray-400 space-y-3">
                    <p>
                        This dashboard tracks the 10 key economic indicators recommended by JPMorgan
                        for business owners to monitor. Each indicator provides insights into different
                        aspects of economic health and helps inform strategic business decisions.
                    </p>
                    <p>
                        The <span className="text-cyan-400 font-semibold">health score</span> (0-100) reflects how each
                        indicator compares to historical norms and recession thresholds. Higher scores
                        indicate healthier economic conditions.
                    </p>
                    <p>
                        Click any indicator card to view detailed historical data, components, and
                        AI-generated insights.
                    </p>
                </div>
            </div>
        </div>
    );
};

// Sub-component for individual cards
const IndicatorCard = ({ indicator, navigate }) => {
    const healthColor = getHealthColor(indicator.health_score);

    // Determine trend color and icon
    let trendIcon = getTrendIcon(indicator.trend_direction);
    let trendColor = 'text-amber-500'; // Default flat

    // Rough heuristic for direction colors (assuming 'up' is generally green unless inverted logic needed later)
    if (trendIcon.includes('↗') || indicator.trend_direction === 'up' || indicator.trend_direction === 'improving') {
        trendColor = 'text-emerald-500';
    } else if (trendIcon.includes('↘') || indicator.trend_direction === 'down' || indicator.trend_direction === 'deteriorating') {
        trendColor = 'text-red-500';
    }

    return (
        <div
            onClick={() => navigate(`/economy/jpm-dashboard/${indicator.id}`)}
            className={`p-4 border-2 ${healthColor} rounded-lg bg-gray-900/50 cursor-pointer hover:bg-gray-800/70 transition-all transform hover:-translate-y-1`}
        >
            {/* Title - Made more prominent */}
            <div className="text-base font-bold text-white mb-3 uppercase tracking-wide">
                {indicator.name}
            </div>

            {/* Health Score & Trend Arrow (Header) */}
            <div className="flex items-start justify-between mb-3">
                {/* Score */}
                <div>
                    <div className="text-2xl font-bold text-white">
                        {indicator.health_score}/100
                    </div>
                    <div className={`text-xs ${healthColor} tracking-tighter`}>
                        {getHealthDots(indicator.health_score)}
                    </div>
                </div>

                {/* Trend Arrow (Relocated) */}
                <div
                    className={`flex flex-col items-center ${trendColor}`}
                    title={`6-month trend: ${indicator.trend_direction}`}
                >
                    <span className="text-3xl leading-none">{trendIcon}</span>
                    <span className="text-[10px] uppercase font-bold tracking-wider opacity-80">(6M)</span>
                </div>
            </div>

            {/* Current Value + Growth Rates */}
            <div className="mb-3">
                <div className="text-xl font-semibold text-cyan-400">
                    {formatValueWithUnit(indicator.current_value, indicator.unit)}
                </div>

                {/* Growth rates display */}
                {(indicator.yoy_change !== null || indicator.last_period_change !== null) && (
                    <div className="text-xs text-gray-400 mt-1">
                        {indicator.yoy_change !== null && (
                            <span>YoY: {indicator.yoy_change > 0 ? '+' : ''}{indicator.yoy_change.toFixed(1)}%</span>
                        )}
                        {indicator.yoy_change !== null && indicator.last_period_change !== null && (
                            <span className="mx-1">|</span>
                        )}
                        {indicator.last_period_change !== null && (
                            <span>
                                {indicator.last_period_label}: {indicator.last_period_change > 0 ? '+' : ''}{indicator.last_period_change.toFixed(1)}%
                            </span>
                        )}
                    </div>
                )}
            </div>

            {/* REMOVED: Old Trend Label */}

            {/* Sparkline Chart (Expanded Height) */}
            <div className="h-24 mb-3">
                {indicator.sparkline && indicator.sparkline.length > 0 ? (
                    <Plot
                        data={[{
                            x: indicator.sparkline.map(d => d.date),
                            y: indicator.sparkline.map(d => d.value),
                            type: 'scatter',
                            mode: 'lines',
                            line: { color: getSparklineColor(indicator.health_score), width: 2 },
                            hoverinfo: 'skip'
                        }]}
                        layout={{
                            margin: { l: 0, r: 0, t: 0, b: 0 },
                            paper_bgcolor: 'rgba(0,0,0,0)',
                            plot_bgcolor: 'rgba(0,0,0,0)',
                            xaxis: { visible: false, fixedrange: true },
                            yaxis: { visible: false, fixedrange: true },
                            showlegend: false,
                            hovermode: false
                        }}
                        config={{ displayModeBar: false, staticPlot: true }}
                        style={{ width: '100%', height: '100%' }}
                    />
                ) : (
                    <div className="h-full flex items-center justify-center text-xs text-gray-600">No chart data</div>
                )}
            </div>

            {/* One-line insight */}
            <div className="text-xs text-gray-400 border-t border-gray-700 pt-3 min-h-[50px]">
                {indicator.one_line_insight || "No insight available."}
            </div>

            {/* Click prompt */}
            <div className="text-xs text-cyan-400 mt-2 text-right font-semibold">
                View Details →
            </div>
        </div>
    );
};

export default Overview;
