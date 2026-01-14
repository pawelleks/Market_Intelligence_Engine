/**
 * Format numeric value with appropriate unit
 * @param {number} value - The numeric value
 * @param {string} unit - Unit abbreviation (%, K, $B, etc.)
 * @returns {string} Formatted string
 */
export const formatValueWithUnit = (value, unit) => {
    if (!value && value !== 0) return 'N/A';

    const formattedNumber = formatNumber(value);

    // Handle different unit types
    switch (unit) {
        case 'K':
        case 'k':
            return `${formattedNumber}K`;

        case '$B':
        case 'B':
            return unit === '$B' ? `$${formattedNumber}B` : `${formattedNumber}B`;

        case '$T':
        case 'T':
            return unit === '$T' ? `$${formattedNumber}T` : `${formattedNumber}T`;

        case '%':
            return `${formattedNumber}%`;

        case 'bps':
            return `${formattedNumber} bps`;

        case 'months':
            return `${formattedNumber} months`;

        case 'index':
        case 'Index':
        case '':
            return formattedNumber;

        default:
            // Handle common verbose units legacy support
            if (unit === 'Thousands') return `${formattedNumber}K`;
            if (unit === 'Billions $') return `$${formattedNumber}B`;
            if (unit === 'Millions') return `${formattedNumber}M`;

            return `${formattedNumber} ${unit}`;
    }
};

/**
 * Format number with commas and appropriate decimal places
 * @param {number} num - Number to format
 * @param {number} decimals - Number of decimal places (default: auto)
 * @returns {string} Formatted number
 */
export const formatNumber = (num, decimals) => {
    if (typeof num !== 'number') return String(num);

    // Determine decimal places
    let decimalPlaces = decimals;
    if (decimalPlaces === undefined) {
        // Auto-determine based on magnitude
        if (Math.abs(num) >= 1000) {
            decimalPlaces = 0; // No decimals for > 1000 usually
        } else if (Math.abs(num) >= 100) {
            decimalPlaces = 1;
        } else if (Math.abs(num) >= 10) {
            decimalPlaces = 2;
        } else {
            decimalPlaces = 2;
        }
    }

    return num.toLocaleString('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: decimalPlaces
    });
};

/**
 * Format change value with sign and unit
 * @param {number} change - Change value
 * @param {string} unit - Unit (%, pts, K, etc.)
 * @returns {string} Formatted change string
 */
export const formatChange = (change, unit = '%') => {
    if (!change && change !== 0) return 'N/A';

    const sign = change > 0 ? '+' : '';
    const formatted = formatNumber(Math.abs(change), 2);

    return `${sign}${change < 0 ? '-' : ''}${formatted}${unit}`;
};
