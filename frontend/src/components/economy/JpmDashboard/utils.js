export const formatValue = (value, unit) => {
    if (value === null || value === undefined) return 'N/A';

    // Handle percentages
    if (unit === '%') {
        return `${value.toFixed(2)}%`;
    }

    // Handle explicit units
    if (unit === '$ Trillions' || unit === '$T') {
        return `$${value.toFixed(2)}T`;
    } else if (unit === '$ Billions' || unit === '$B' || unit === 'Billions $') {
        // Values in billions - check if should display as Trillions
        if (value >= 1000) {
            return `$${(value / 1000).toFixed(1)}T`;
        }
        return `$${value.toFixed(1)}B`;
    } else if (unit === 'Thousands' || unit === 'K') {
        // If raw value is already big (like 200,000), convert to K or M
        if (value >= 1000000) return `${(value / 1000000).toFixed(2)}B`; // e.g. 1000000 thousands = 1B
        if (value >= 1000) return `${(value / 1000).toFixed(2)}M`; // e.g. 7146 thousands = 7.15M
        return `${value.toFixed(0)}K`; // e.g. 210 thousands = 210K
    } else if (unit === 'Millions' || unit === 'M' || unit === 'Millions $') {
        // Trade balance type data - check if should be billions
        if (Math.abs(value) >= 1000) {
            return `$${(value / 1000).toFixed(2)}B`;
        }
        return `${value.toFixed(0)}M`;
    }

    // Auto-detect large numbers without explicit units
    // GDP/Consumer Spending range (> 20,000 suggests billions)
    if (value > 20000 && value < 30000) {
        return `$${(value / 1000).toFixed(1)}T`;
    }

    // Federal deficit range (millions, show as trillions)
    if (Math.abs(value) > 1000000) {
        return `$${(value / 1000000).toFixed(2)}T`;
    }

    // Consumer credit / large positive numbers (trillions)
    if (value > 5000000) {
        return `$${(value / 1000000).toFixed(2)}T`;
    }

    // Existing home sales range (4000-5000 should be millions)
    if (value >= 4000 && value <= 5000) {
        return `${(value / 1000).toFixed(2)}M`;
    }

    // Default: use locale formatting with 2 decimals
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
};

export const getHealthColor = (score) => {
    if (score >= 80) return 'text-green-500 border-green-500';
    if (score >= 60) return 'text-yellow-500 border-yellow-500';
    if (score >= 40) return 'text-orange-500 border-orange-500';
    return 'text-red-500 border-red-500';
};

export const getHealthDots = (score) => {
    const filled = Math.round(score / 10);
    return '●'.repeat(filled) + '○'.repeat(10 - filled);
};

export const getTrendIcon = (direction) => {
    const icons = {
        'up': '↗',
        'improving': '↗',
        'down': '↘',
        'deteriorating': '↘',
        'flat': '→',
        'stable': '→'
    };
    return icons[direction] || '→';
};

export const getStatusIcon = (status) => {
    const icons = {
        'healthy': '✅',
        'warning': '⚠️',
        'concerning': '⚠️',
        'critical': '🚨'
    };
    return icons[status] || '📊';
};

export const calculateStartDate = (range) => {

    // Helper to clone and set year
    const getYearOffset = (offset) => {
        const d = new Date();
        d.setFullYear(d.getFullYear() - offset);
        return d;
    };

    const ranges = {
        '1Y': getYearOffset(1),
        '5Y': getYearOffset(5),
        '10Y': getYearOffset(10),
        '20Y': getYearOffset(20),
        'MAX': new Date('1942-01-01')
    };
    return (ranges[range] || ranges['5Y']).toISOString().split('T')[0];
};

export const getSparklineColor = (score) => {
    if (score >= 80) return '#10b981'; // green
    if (score >= 60) return '#fbbf24'; // yellow
    if (score >= 40) return '#f59e0b'; // orange
    return '#ef4444'; // red
};
