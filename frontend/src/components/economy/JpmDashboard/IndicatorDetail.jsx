import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import Plot from 'react-plotly.js';
import {
    getHealthColor,
    getHealthDots,
    getTrendIcon,
    getStatusIcon,
    calculateStartDate,
    getSparklineColor
} from './utils';
import { formatValueWithUnit } from '../../../utils/formatters';
import { tier2Configs } from '../../../data/tier2_configs';
import UpcomingReleases from '../../UpcomingReleases';
import RelatedMetricCard from '../../RelatedMetrics';

const IndicatorDetail = () => {
    const { category } = useParams();
    const navigate = useNavigate();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [timeRange, setTimeRange] = useState('10Y');  // Default to 10Y for better historical context
    const [distributionView, setDistributionView] = useState('gaussian'); // 'histogram', 'density', or 'gaussian'
    const [showContext, setShowContext] = useState(true);

    // Get configuration for this page (if available)
    const config = tier2Configs[category];

    useEffect(() => {
        fetchIndicatorData();
    }, [category, timeRange]);

    const fetchIndicatorData = async () => {
        try {
            const startDate = calculateStartDate(timeRange);
            // NOTE: API currently doesn't filter by start_date query param on the backend for the main JSON structure,
            // but it does return the full historical data series.
            // Ideally we filter it on frontend or update backend. 
            // For now, let's fetch default and let Plotly handle zoom/range or filter manually.
            const response = await axios.get(
                `/api/v1/jpm-dashboard/indicators/${category}`
            );
            setData(response.data);
            setLoading(false);
        } catch (error) {
            console.error('Failed to fetch indicator data:', error);
            setError('Unable to load indicator details.');
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-page text-white">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-cyan-500 mx-auto mb-4"></div>
                    <div className="text-gray-400">Loading analysis for {category}...</div>
                </div>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-page text-white">
                <div className="text-center max-w-md p-6">
                    <div className="text-red-500 text-5xl mb-4">⚠️</div>
                    <h2 className="text-2xl font-bold text-white mb-2">Error Loading Data</h2>
                    <p className="text-gray-400 mb-6">{error}</p>
                    <button
                        onClick={() => navigate('/economy/jpm-dashboard')}
                        className="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg"
                    >
                        Return to Dashboard
                    </button>
                </div>
            </div>
        );
    }

    // --- Helpers for Display ---

    const getStatusBannerStyle = (healthStatus) => {
        // Current API returns 'health_score', but not explicit 'health_status' string always.
        // We derive it or use existing if present.
        // If API doesn't provide status string, infer from score:
        let status = 'warning';
        const score = data.health_score;
        if (score >= 80) status = 'healthy';
        else if (score >= 60) status = 'warning';
        else if (score >= 40) status = 'concerning';
        else status = 'critical';

        const styles = {
            'healthy': 'border-green-500 bg-green-900/20',
            'warning': 'border-yellow-500 bg-yellow-900/20',
            'concerning': 'border-orange-500 bg-orange-900/20',
            'critical': 'border-red-500 bg-red-900/20'
        };
        return styles[status] || styles.warning;
    };

    const getStatusLabel = (score) => {
        if (score >= 80) return 'HEALTHY / EXPANSION';
        if (score >= 60) return 'MODERATE / STABLE';
        if (score >= 40) return 'CONCERNING / SLOWING';
        return 'CRITICAL / RECESSIONARY';
    };

    // Filter data for chart based on timeRange
    const filterDataByDate = (points) => {
        if (!points) return [];

        // First filter out null values (important for quarterly data with monthly padding)
        const validPoints = points.filter(p => p.value !== null && p.value !== undefined);

        // Then filter by date range
        const start = new Date(calculateStartDate(timeRange));
        return validPoints.filter(p => new Date(p.date) >= start);
    };

    const primaryData = filterDataByDate(data.primary_metric?.data);
    const healthColor = getHealthColor(data.health_score);

    // Helper functions for dynamic axis scaling
    const getXAxisRange = () => {
        if (!primaryData || primaryData.length === 0) return undefined;
        const dates = primaryData.map(d => d.date);
        return [dates[0], dates[dates.length - 1]];
    };

    const getYAxisRange = () => {
        if (!primaryData || primaryData.length === 0) return undefined;

        const values = primaryData.map(d => d.value);
        const minValue = Math.min(...values);
        const maxValue = Math.max(...values);

        // Handle flat line case (all values the same)
        if (minValue === maxValue) {
            return [minValue * 0.95, maxValue * 1.05];
        }

        const range = maxValue - minValue;
        // Add 5% padding top and bottom, with minimum 0.1 padding for small ranges
        const padding = Math.max(range * 0.05, 0.1);

        return [minValue - padding, maxValue + padding];
    };

    // Helper to format date as "Dec 2025"
    const formatReportedDate = (dateString) => {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    };

    // Helper for percentile descriptions
    const getPercentileDescription = (percentile) => {
        if (percentile >= 90) return 'Top 10% historically';
        if (percentile >= 75) return 'Top 25% historically';
        if (percentile >= 50) return 'Above average';
        if (percentile >= 25) return 'Below average';
        if (percentile >= 10) return 'Bottom 25% historically';
        return 'Bottom 10% historically';
    };

    // Helper for distribution interpretation
    const getDistributionInterpretation = (percentile, categoryName) => {
        const name = categoryName.replace(/-/g, ' ');

        if (percentile >= 90) {
            return `Current ${name} is in the top 10% of historical performance, indicating exceptionally strong conditions relative to the past several decades.`;
        } else if (percentile >= 75) {
            return `Current ${name} is in the top quartile historically, showing above-average performance compared to historical norms.`;
        } else if (percentile >= 50) {
            return `Current ${name} is above the historical median, indicating moderately favorable conditions.`;
        } else if (percentile >= 25) {
            return `Current ${name} is below the historical median, suggesting weaker conditions relative to the long-term average.`;
        } else if (percentile >= 10) {
            return `Current ${name} is in the bottom quartile historically, indicating below-average performance.`;
        } else {
            return `Current ${name} is in the bottom 10% historically, showing exceptionally weak conditions relative to historical norms.`;
        }
    };

    // Helper to generate Gaussian curve points
    const generateGaussianData = (mean, std, min, max, totalCount, binWidth) => {
        if (!std || std === 0) return { x: [], y: [] };

        const points = 100;
        const xValues = [];
        const yValues = [];
        const range = max - min;
        const start = min - (range * 0.1); // Add little padding
        const end = max + (range * 0.1);
        const step = (end - start) / points;

        for (let i = 0; i <= points; i++) {
            const x = start + (i * step);
            // Gaussian PDF formula
            const exponent = Math.exp(-0.5 * Math.pow((x - mean) / std, 2));
            const probability = (1 / (std * Math.sqrt(2 * Math.PI))) * exponent;

            // Scale to match histogram counts: P(x) * TotalCount * BinWidth
            const y = probability * totalCount * binWidth;

            xValues.push(x);
            yValues.push(y);
        }

        return { x: xValues, y: yValues };
    };



    return (
        <div className="p-6 bg-page min-h-screen text-white">
            {/* Navigation Breadcrumb */}
            <button
                onClick={() => navigate('/economy/jpm-dashboard')}
                className="flex items-center text-gray-400 hover:text-white mb-6 transition-colors"
            >
                <span className="mr-2">←</span> Back to Dashboard
            </button>

            {/* Title Header - Compressed */}
            <div className="mb-4">
                <h1 className="text-2xl font-bold text-white mb-1">{data.name || data.primary_metric?.name || data.category}</h1>
                <div className="text-sm text-gray-400">{data.description || `Tracking key metrics for ${(data.name || data.primary_metric?.name || data.category || '').toLowerCase()}.`}</div>
                <div className="text-xs text-gray-500 mt-0.5">
                    Last updated: {new Date().toLocaleDateString()}
                </div>
            </div>

            {/* Status Banner - Compressed */}
            <div className={`mb-4 p-4 border-2 rounded-lg ${getStatusBannerStyle()}`}>
                <div className="flex items-center">
                    <div className="text-3xl mr-3">
                        {getStatusIcon(data.health_score >= 80 ? 'healthy' : data.health_score >= 40 ? 'warning' : 'critical')}
                    </div>
                    <div className="flex-1">
                        <div className="text-base font-bold text-white uppercase tracking-wide">
                            {getStatusLabel(data.health_score)}
                        </div>
                        {data.insights?.one_line_insight && (
                            <div className="text-sm text-gray-300 mt-0.5">
                                {data.insights.one_line_insight}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Top Metrics Grid - Compressed */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                {/* Current Value Card with Last Reported */}
                <div className="p-3 bg-gray-900/50 border border-gray-700 rounded-lg">
                    <div className="text-xs text-gray-400 uppercase tracking-wider">
                        {category === 'gdp' ? 'Current Growth Rate' : 'Current Value'}
                    </div>
                    <div className="text-2xl font-bold text-cyan-400 mt-1">
                        {formatValueWithUnit(data.primary_metric?.current, data.primary_metric?.unit)}
                        {/* Change Indicator */}
                        <span className="ml-2 text-sm font-medium">
                            {data.primary_metric?.yoy_absolute_change !== null && data.primary_metric?.yoy_absolute_change !== undefined ? (
                                <span className={data.primary_metric.yoy_absolute_change > 0 ? (data.category === 'labor-market' ? 'text-orange-400' : 'text-green-400') : (data.category === 'labor-market' ? 'text-green-400' : 'text-red-400')}>
                                    {data.primary_metric.yoy_absolute_change > 0 ? '+' : ''}{data.primary_metric.yoy_absolute_change.toFixed(1)} pts
                                </span>
                            ) : data.primary_metric?.yoy_change !== null && data.primary_metric?.yoy_change !== undefined ? (
                                <span className={data.primary_metric.yoy_change > 0 ? 'text-green-400' : 'text-red-400'}>
                                    {data.primary_metric.yoy_change > 0 ? '+' : ''}{data.primary_metric.yoy_change.toFixed(1)}%
                                </span>
                            ) : null}
                        </span>
                    </div>
                    <div className="flex items-center justify-between mt-1">
                        <div className="flex items-center text-xs text-gray-400">
                            <span className="text-lg mr-1">{getTrendIcon(data.trend_direction)}</span>
                            <span className="uppercase">{data.trend_direction}</span>
                        </div>
                        <div className="text-xs text-gray-500">
                            As of {formatReportedDate(data.primary_metric?.current_date)}
                        </div>
                    </div>
                </div>

                {/* Health Score Card - Compressed */}
                <div className="p-3 bg-gray-900/50 border border-gray-700 rounded-lg">
                    <div className="text-xs text-gray-400 uppercase tracking-wider">Health Score</div>
                    <div className="text-2xl font-bold text-white mt-1">
                        {data.health_score}/100
                    </div>
                    <div className={`text-xs ${healthColor} mt-1 tracking-widest`}>
                        {getHealthDots(data.health_score)}
                    </div>
                </div>

                {/* Historical Context Card - Compressed */}
                <div className="p-3 bg-gray-900/50 border border-gray-700 rounded-lg">
                    <div className="text-xs text-gray-400 uppercase tracking-wider">vs Historical Cycle</div>
                    <div className="text-2xl font-bold text-white mt-1">
                        {(() => {
                            if (!data.primary_metric?.historical_avg || !data.primary_metric?.current) return 'N/A';
                            const diff = ((data.primary_metric.current - data.primary_metric.historical_avg) / data.primary_metric.historical_avg) * 100;

                            // Simple heuristic for "Better/Worse" depends on indicator type
                            // But "Above/Below Average" is neutral and accurate
                            if (Math.abs(diff) < 5) return 'On Average';
                            return diff > 0 ? `Above Avg` : `Below Avg`;
                        })()}
                    </div>
                    <div className="text-sm text-gray-400 mt-2">
                        {data.primary_metric?.historical_avg
                            ? `${data.primary_metric.current > data.primary_metric.historical_avg ? '+' : ''}${((data.primary_metric.current - data.primary_metric.historical_avg) / Math.abs(data.primary_metric.historical_avg) * 100).toFixed(1)}% vs 10Y Mean`
                            : 'Relative to 10-year mean'
                        }
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                        Compares current {data.primary_metric?.unit === '%' ? 'rate' : 'level'} to its 10-year average
                    </div>
                </div>
            </div>

            {/* Upcoming Releases Section */}
            <UpcomingReleases indicatorId={category} />

            {/* Primary Chart Section */}
            <div className="mb-10 p-6 bg-gray-900/30 border border-gray-800 rounded-xl">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                    <div>
                        <h3 className="text-xl font-bold text-white">
                            {category === 'policy' ? 'Federal Funds Rate History' : `${data.primary_metric?.name} History`}
                        </h3>
                        <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span>{data.primary_metric?.unit}</span>
                            <span className={`px-2 py-0.5 rounded-full border text-[10px] font-medium ${
                                data.primary_metric?.sa
                                    ? 'border-green-600/50 text-green-400 bg-green-900/20'
                                    : 'border-gray-600 text-gray-400 bg-gray-800/50'
                            }`}>
                                {data.primary_metric?.sa ? 'Seasonally Adjusted' : 'Not Seasonally Adjusted'}
                            </span>
                        </div>
                    </div>

                    <div className="flex bg-gray-800/50 rounded-lg p-1">
                        {['1Y', '5Y', '10Y', '20Y', 'MAX'].map(range => (
                            <button
                                key={range}
                                onClick={() => setTimeRange(range)}
                                className={`px-3 py-1 text-sm rounded transition-colors ${timeRange === range
                                    ? 'bg-cyan-600 text-white font-medium shadow-sm'
                                    : 'text-gray-400 hover:text-white hover:bg-gray-700'
                                    }`}
                            >
                                {range}
                            </button>
                        ))}
                    </div>
                </div>

                <Plot
                    data={[
                        // Trace 1: Actual data
                        {
                            x: primaryData.map(d => d.date),
                            y: primaryData.map(d => d.value),
                            type: 'scatter',
                            mode: 'lines',
                            name: 'Actual',
                            line: { color: '#00d4ff', width: 3 },
                            fill: 'tozeroy',
                            fillcolor: 'rgba(0, 212, 255, 0.05)'
                        },
                        // Trace 2: 10Y Moving Average
                        ...(data.primary_metric.moving_average_10y ? [{
                            x: filterDataByDate(data.primary_metric.moving_average_10y).map(d => d.date),
                            y: filterDataByDate(data.primary_metric.moving_average_10y).map(d => d.value),
                            type: 'scatter',
                            mode: 'lines',
                            name: '10Y Average',
                            line: {
                                color: '#fbbf24',
                                width: 2,
                                dash: 'dash'
                            },
                            hovertemplate: '10Y Avg: %{y:.2f}<extra></extra>'
                        }] : [])
                    ]}
                    layout={{
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        font: { color: '#9ca3af', family: 'Inter, sans-serif' },
                        xaxis: {
                            gridcolor: '#1f2937',
                            showgrid: true,
                            linecolor: '#374151',
                            type: 'date',
                            range: getXAxisRange(),
                            autorange: false
                        },
                        yaxis: {
                            gridcolor: '#1f2937',
                            showgrid: true,
                            title: data.primary_metric?.unit,
                            zerolinecolor: '#374151',
                            range: getYAxisRange(),
                            autorange: false
                        },
                        hovermode: 'x unified',
                        hoverlabel: {
                            bgcolor: '#1f2937',
                            bordercolor: '#374151',
                            font: {
                                family: 'Inter, sans-serif',
                                size: 12,
                                color: '#f9fafb'
                            },
                            align: 'left'
                        },
                        showlegend: true,
                        legend: {
                            x: 0.02,
                            y: 0.98,
                            bgcolor: 'rgba(10, 14, 26, 0.8)',
                            bordercolor: '#374151',
                            borderwidth: 1,
                            font: { color: '#9ca3af', size: 11 }
                        },
                        margin: { l: 50, r: 20, t: 10, b: 40 },
                        shapes: (data.recessions || []).map(rec => ({
                            type: 'rect',
                            xref: 'x',
                            yref: 'paper',
                            x0: rec.start,
                            x1: rec.end,
                            y0: 0,
                            y1: 1,
                            fillcolor: 'rgba(255, 255, 255, 0.08)',
                            line: { width: 0 },
                            layer: 'below'
                        }))
                    }}
                    config={{ displayModeBar: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'], responsive: true }}
                    useResizeHandler={true}
                    style={{ width: '100%', height: '380px' }}  // Reduced from 450px
                />
            </div>

            {/* Historical Distribution Section */}
            {data.primary_metric?.distribution && (
                <div className="mb-8">
                    <div className="flex justify-between items-center mb-4">
                        <h2 className="text-xl font-semibold text-white">Historical Distribution</h2>

                        {/* View Toggle */}
                        <div className="flex gap-2">
                            <button
                                onClick={() => setDistributionView('histogram')}
                                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${distributionView === 'histogram'
                                    ? 'bg-cyan-500 text-white'
                                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                                    }`}
                            >
                                Histogram
                            </button>
                            <button
                                onClick={() => setDistributionView('density')}
                                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${distributionView === 'density'
                                    ? 'bg-cyan-500 text-white'
                                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                                    }`}
                            >
                                Density Curve
                            </button>
                            <button
                                onClick={() => setDistributionView('gaussian')}
                                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${distributionView === 'gaussian'
                                    ? 'bg-cyan-500 text-white'
                                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                                    }`}
                            >
                                Gaussian
                            </button>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Left: Distribution Chart (2 columns on desktop) */}
                        <div className="lg:col-span-2 bg-gray-900/30 border border-gray-700 rounded-lg p-4">
                            <Plot
                                data={distributionView === 'histogram' ? [
                                    // Histogram bars
                                    {
                                        x: data.primary_metric.distribution.bins,
                                        y: data.primary_metric.distribution.counts,
                                        type: 'bar',
                                        name: 'Frequency',
                                        marker: {
                                            color: '#374151',
                                            line: { color: '#4b5563', width: 1 }
                                        },
                                        hovertemplate: 'Value: %{x:.1f}<br>Count: %{y}<extra></extra>'
                                    },
                                    // Current value marker
                                    {
                                        x: [data.primary_metric.distribution.current_value, data.primary_metric.distribution.current_value],
                                        y: [0, Math.max(...data.primary_metric.distribution.counts) * 1.1],
                                        type: 'scatter',
                                        mode: 'lines',
                                        name: 'Current',
                                        line: { color: '#00d4ff', width: 3 },
                                        hovertemplate: 'Current: %{x:.2f}<extra></extra>'
                                    }
                                ] : distributionView === 'density' ? [
                                    // Density curve with fill
                                    {
                                        x: data.primary_metric.distribution.bins,
                                        y: data.primary_metric.distribution.counts,
                                        type: 'scatter',
                                        mode: 'lines',
                                        name: 'Density',
                                        line: { color: '#6366f1', width: 3, shape: 'spline', smoothing: 1.3 },
                                        fill: 'tozeroy',
                                        fillcolor: 'rgba(99, 102, 241, 0.2)',
                                        hovertemplate: 'Value: %{x:.1f}<br>Frequency: %{y}<extra></extra>'
                                    },
                                    // Current value marker
                                    {
                                        x: [data.primary_metric.distribution.current_value, data.primary_metric.distribution.current_value],
                                        y: [0, Math.max(...data.primary_metric.distribution.counts) * 1.1],
                                        type: 'scatter',
                                        mode: 'lines',
                                        name: 'Current',
                                        line: { color: '#00d4ff', width: 3 },
                                        hovertemplate: 'Current: %{x:.2f}<extra></extra>'
                                    }
                                ] : [
                                    // Gaussian Bell Curve
                                    {
                                        x: generateGaussianData(
                                            data.primary_metric.distribution.mean_value,
                                            data.primary_metric.distribution.std_value || (data.primary_metric.distribution.max_value - data.primary_metric.distribution.min_value) / 6, // Fallback approx std
                                            data.primary_metric.distribution.min_value,
                                            data.primary_metric.distribution.max_value,
                                            data.primary_metric.distribution.counts.reduce((a, b) => a + b, 0),
                                            data.primary_metric.distribution.bins[1] - data.primary_metric.distribution.bins[0]
                                        ).x,
                                        y: generateGaussianData(
                                            data.primary_metric.distribution.mean_value,
                                            data.primary_metric.distribution.std_value || (data.primary_metric.distribution.max_value - data.primary_metric.distribution.min_value) / 6,
                                            data.primary_metric.distribution.min_value,
                                            data.primary_metric.distribution.max_value,
                                            data.primary_metric.distribution.counts.reduce((a, b) => a + b, 0),
                                            data.primary_metric.distribution.bins[1] - data.primary_metric.distribution.bins[0]
                                        ).y,
                                        type: 'scatter',
                                        mode: 'lines',
                                        name: 'Gaussian',
                                        line: { color: '#10b981', width: 3, shape: 'spline' },
                                        fill: 'tozeroy',
                                        fillcolor: 'rgba(16, 185, 129, 0.2)',
                                        hovertemplate: 'Value: %{x:.1f}<br>Prob (scaled): %{y:.1f}<extra></extra>'
                                    },
                                    // Current value marker
                                    {
                                        x: [data.primary_metric.distribution.current_value, data.primary_metric.distribution.current_value],
                                        y: [0, Math.max(...data.primary_metric.distribution.counts) * 1.1], // Keep scale consistent with bar max
                                        type: 'scatter',
                                        mode: 'lines',
                                        name: 'Current',
                                        line: { color: '#00d4ff', width: 3 },
                                        hovertemplate: 'Current: %{x:.2f}<extra></extra>'
                                    }
                                ]}
                                layout={{
                                    paper_bgcolor: '#0a0e1a',
                                    plot_bgcolor: '#0a0e1a',
                                    font: { color: '#9ca3af', size: 12 },
                                    xaxis: {
                                        title: {
                                            text: `${data.primary_metric.name} (${data.primary_metric.unit})`,
                                            font: { size: 13, color: '#d1d5db' }
                                        },
                                        gridcolor: '#1f2937',
                                        showgrid: true
                                    },
                                    yaxis: {
                                        title: 'Frequency',
                                        gridcolor: '#1f2937',
                                        showgrid: true
                                    },
                                    showlegend: true,
                                    legend: {
                                        x: 0.02,
                                        y: 0.98,
                                        bgcolor: 'rgba(10, 14, 26, 0.8)',
                                        bordercolor: '#374151',
                                        borderwidth: 1
                                    },
                                    margin: { l: 60, r: 20, t: 20, b: 60 },
                                    annotations: [{
                                        x: data.primary_metric.distribution.current_value,
                                        y: Math.max(...data.primary_metric.distribution.counts) * 0.9,
                                        text: `${data.primary_metric.distribution.percentile.toFixed(0)}th Percentile`,
                                        showarrow: true,
                                        arrowhead: 2,
                                        arrowcolor: '#00d4ff',
                                        ax: 40,
                                        ay: -40,
                                        font: { color: '#00d4ff', size: 13, weight: 'bold' },
                                        bgcolor: 'rgba(10, 14, 26, 0.9)',
                                        bordercolor: '#00d4ff',
                                        borderwidth: 1,
                                        borderpad: 4
                                    }]
                                }}
                                config={{ displayModeBar: false, responsive: true }}
                                style={{ width: '100%', height: '300px' }}
                            />
                        </div>

                        {/* Right: Distribution Statistics (1 column on desktop) */}
                        <div className="bg-gray-900/30 border border-gray-700 rounded-lg p-4">
                            <h3 className="text-sm font-semibold text-gray-400 mb-4">Distribution Stats</h3>

                            <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                                <div className="col-span-2">
                                    <div className="text-xs text-gray-500">
                                        {data.primary_metric?.unit === '%' ? 'Current Rate' : 'Current Level'}
                                    </div>
                                    <div className="text-lg font-bold text-cyan-400">
                                        {formatValueWithUnit(data.primary_metric.distribution.current_value, data.primary_metric.unit)}
                                    </div>
                                </div>

                                <div className="col-span-2">
                                    <div className="text-xs text-gray-500">Percentile Rank</div>
                                    <div className="text-base font-bold text-cyan-400">
                                        {data.primary_metric.distribution.percentile.toFixed(1)}th
                                    </div>
                                    <div className="text-xs text-gray-400">
                                        {getPercentileDescription(data.primary_metric.distribution.percentile)}
                                    </div>
                                </div>

                                <div className="col-span-2 border-t border-gray-700 pt-2">
                                    <div className="text-xs text-gray-500">Historical Range</div>
                                    <div className="text-xs text-gray-300">
                                        {formatValueWithUnit(data.primary_metric.distribution.min_value, data.primary_metric.unit)} to {formatValueWithUnit(data.primary_metric.distribution.max_value, data.primary_metric.unit)}
                                    </div>
                                </div>

                                <div>
                                    <div className="text-xs text-gray-500">Mean</div>
                                    <div className="text-sm text-gray-300">
                                        {formatValueWithUnit(data.primary_metric.distribution.mean_value, data.primary_metric.unit)}
                                    </div>
                                </div>

                                <div>
                                    <div className="text-xs text-gray-500">Median</div>
                                    <div className="text-sm text-gray-300">
                                        {formatValueWithUnit(data.primary_metric.distribution.median_value, data.primary_metric.unit)}
                                    </div>
                                </div>

                                <div className="col-span-2 border-t border-gray-700 pt-2">
                                    <div className="text-xs text-gray-500">Above/Below Mean</div>
                                    {(() => {
                                        const diff = data.primary_metric.distribution.current_value - data.primary_metric.distribution.mean_value;
                                        const pct = (diff / Math.abs(data.primary_metric.distribution.mean_value) * 100);
                                        return (
                                            <div className={`text-sm font-semibold ${diff > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                {pct > 0 ? '+' : ''}{pct.toFixed(1)}% vs historical mean
                                            </div>
                                        );
                                    })()}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Interpretation Text */}
                    <div className="mt-4 p-4 bg-gray-900/20 border border-gray-700 rounded-lg">
                        <p className="text-sm text-gray-300">
                            {getDistributionInterpretation(data.primary_metric.distribution.percentile, category)}
                        </p>
                    </div>
                </div>
            )}

            {/* Secondary Metrics & Components Grid - STANDARDIZED */}
            <div className="flex items-center justify-between mb-4 pl-1 border-l-4 border-cyan-500">
                <h3 className="text-xl font-bold text-white">
                    {config?.related_metrics?.length === 0 ? "Related Indicators" : "Related Metrics"}
                </h3>
                <button
                    onClick={() => setShowContext(!showContext)}
                    className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors uppercase tracking-wider font-semibold"
                >
                    {showContext ? 'HIDE CONTEXT [-]' : 'SHOW CONTEXT [+]'}
                </button>
            </div>


            {/* Educational Content Section - Config Driven */}
            {(() => {
                // debug log
                // console.log('IndicatorDetail config lookup:', { category, hasConfig: !!config, edu: config?.educational_content });

                if (showContext && config?.educational_content) {
                    return (
                        <div className="mb-6 p-4 bg-gray-900/40 border border-gray-700/50 rounded-lg text-sm text-gray-300 animate-fadeIn">
                            <div className="mb-3">
                                <strong className="text-cyan-400">{config.educational_content.title || "Understanding these sub-metrics"}:</strong>
                                <span className="ml-1">{config.educational_content.overview}</span>
                            </div>
                            <ul className="list-disc pl-4 space-y-2 text-xs text-gray-400">
                                {config.educational_content.bullets.map((bullet, idx) => (
                                    <li key={idx}>
                                        <strong className="text-gray-300">{bullet.label}:</strong> {bullet.text}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    );
                }
                return null;
            })()}

            {/* Fallback for pages without config (e.g. Stock Market if not configured) */}
            {!config && (
                <div className="mb-12">
                    {/* Existing logic for non-configured pages could go here, or we just show nothing/message */}
                    <div className="text-gray-500 italic">No configuration found for this category.</div>
                </div>
            )}

            {/* Related Metrics Grid */}
            {config && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
                    {(() => {
                        // 1. Gather all available metrics from API
                        const allMetrics = [
                            ...(data.secondary_metrics || []),
                            ...(data.component_metrics || [])
                        ];

                        // 2. Map keyed by series_id for easy lookup
                        const metricMap = new Map(allMetrics.map(m => [m.series_id, m]));

                        // 3. Use Config to drive display order and properties
                        return config.related_metrics.map(confMetric => {
                            const apiMetric = metricMap.get(confMetric.series_id);

                            if (!apiMetric) return null;

                            // 4. Render Enhanced Card
                            return (
                                <RelatedMetricCard
                                    key={confMetric.series_id}
                                    metric={apiMetric}
                                    config={confMetric}
                                />
                            );
                        });
                    })()}
                </div>
            )}

            {/* Show message if housing/trade/business have no metrics (empty array in config) */}
            {
                config && config.related_metrics.length === 0 && (
                    <div className="text-gray-500 italic mb-12">
                        Tracking primary indicator only.
                    </div>
                )
            }


            {/* AI Analysis Section */}
            <div className="mb-12 p-6 bg-gray-900/50 border border-gray-700 rounded-lg shadow-lg">
                <h3 className="text-xl font-bold text-white mb-2 flex items-center">
                    <span className="mr-2">🤖</span> AI-Generated Insights
                </h3>
                {data.insights?.generated_at && (
                    <div className="text-xs text-gray-500 mb-4">
                        Generated based on data as of {formatReportedDate(data.insights.generated_at)}
                    </div>
                )}

                <div className="prose prose-invert max-w-none">
                    <div className="text-gray-300 leading-relaxed mb-6 bg-black/20 p-4 rounded border border-gray-800">
                        {data.insights?.detailed_insight || "Detailed analysis is being computed by the MIE Engine..."}
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                    {/* Key Takeaways */}
                    <div>
                        <h4 className="text-sm font-bold text-gray-400 uppercase mb-3">Key Takeaways</h4>
                        <ul className="space-y-2">
                            {data.insights?.key_takeaways?.map((takeaway, idx) => (
                                <li key={idx} className="flex items-start text-sm">
                                    <span className="text-cyan-400 mr-2 mt-1">•</span>
                                    <span className="text-gray-300">{takeaway}</span>
                                </li>
                            )) || <li className="text-gray-500 italic">Analysis pending...</li>}
                        </ul>
                    </div>

                    {/* Business Impact */}
                    <div>
                        <h4 className="text-sm font-bold text-gray-400 uppercase mb-3">Implications</h4>
                        <div className="text-sm text-gray-300 border-l-2 border-orange-500 pl-3">
                            {data.insights?.business_impact || "Business impact analysis pending..."}
                        </div>
                    </div>
                </div>
            </div>



            <div className="h-24"></div> {/* Bottom Spacer */}
        </div >
    );
};

export default IndicatorDetail;
