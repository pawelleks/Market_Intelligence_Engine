import React from 'react';
import Sparkline from './Sparkline';
import { formatValueWithUnit } from '../utils/formatters';
import '../styles/RelatedMetrics.css';

const RelatedMetricCard = ({ metric, config }) => {
    const {
        series_id,
        display_name: apiDisplayName,
        current_value,
        unit: apiUnit,
        yoy_change_pct,
        period_change_pct,
        period_label,
        trend_6m,
        historical_data
    } = metric;

    // Prefer config values over API values for display_name and unit
    const display_name = config?.display_name || apiDisplayName;
    const unit = config?.unit || apiUnit;

    // Determine trend config
    const trendConfig = {
        up: { icon: '↗', color: '#10b981', label: 'Trending Up' },
        flat: { icon: '→', color: '#f59e0b', label: 'Flat' },
        down: { icon: '↘', color: '#ef4444', label: 'Trending Down' }
    };

    const trend = trendConfig[trend_6m] || trendConfig.flat;

    // Format formatted value
    const formattedValue = formatValueWithUnit(current_value, unit);

    // Helper to format percentage change with sign
    const formatChange = (val) => {
        if (val === null || val === undefined) return 'N/A';
        const num = parseFloat(val);
        const sign = num > 0 ? '+' : '';
        return `${sign}${num.toFixed(1)}%`;
    };

    const tooltipText = config?.tooltip || `Series: ${series_id}`;

    return (
        <div className="related-metric-card group relative p-4 bg-gray-900/50 border border-gray-700 rounded-lg hover:border-gray-500 transition-all hover:-translate-y-0.5 hover:shadow-lg h-[180px] flex flex-col">

            {/* Header Row: Title + Trend Arrow */}
            <div className="flex justify-between items-start mb-2">
                <h4
                    className="metric-title text-xs text-gray-400 uppercase font-semibold truncate cursor-help border-b border-dotted border-gray-600 hover:text-gray-200 hover:border-gray-400 transition-colors max-w-[70%]"
                    title={tooltipText}
                >
                    {display_name}
                </h4>
                <div
                    className="trend-indicator flex items-center gap-1 bg-gray-800/50 px-1.5 py-0.5 rounded"
                    title={`6-Month Trend: ${trend.label}`}
                >
                    <span className="text-[10px] text-gray-500 uppercase font-bold tracking-wider mr-1">6M</span>
                    <span className="text-lg leading-none" style={{ color: trend.color }}>{trend.icon}</span>
                </div>
            </div>

            {/* Value */}
            <div className="metric-value mb-3">
                <div className="text-2xl font-bold text-cyan-400 tracking-tight">
                    {formattedValue}
                </div>
            </div>

            {/* Changes Row */}
            <div className="metric-changes flex items-center gap-3 text-xs text-gray-400 mb-auto">
                <div className="flex items-center gap-1">
                    <span className="text-gray-500">YoY:</span>
                    <span className={yoy_change_pct > 0 ? 'text-green-400' : yoy_change_pct < 0 ? 'text-red-400' : 'text-gray-400'}>
                        {formatChange(yoy_change_pct)}
                    </span>
                </div>
                <div className="w-[1px] h-3 bg-gray-700"></div>
                <div className="flex items-center gap-1">
                    <span className="text-gray-500">{period_label || 'Period'}:</span>
                    <span className={period_change_pct > 0 ? 'text-green-400' : period_change_pct < 0 ? 'text-red-400' : 'text-gray-400'}>
                        {formatChange(period_change_pct)}
                    </span>
                </div>
            </div>

            {/* Mini Chart */}
            <div className="metric-chart h-12 w-full mt-3 opacity-60 group-hover:opacity-100 transition-opacity">
                <Sparkline
                    data={historical_data}
                    color={trend.color}
                />
            </div>
        </div>
    );
};

export default RelatedMetricCard;
