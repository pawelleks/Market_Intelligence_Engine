import React, { useMemo } from 'react';

// Helper to format numbers in the FinTech aesthetic
const formatPercent = (value) => value !== undefined && value !== null && !isNaN(value) ? `${(value * 100).toFixed(2)}%` : 'N/A';
const formatSharpe = (value) => value !== undefined && value !== null && !isNaN(value) ? value.toFixed(2) : 'N/A';
const formatDays = (value) => value !== undefined && value !== null ? value.toLocaleString() : 'N/A';

const calculateStats = (returns) => {
    if (!returns || returns.length === 0) return { ann_return: 0, ann_vol: 0, sharpe: 0, days_in_regime: 0 };

    const n = returns.length;
    const mean = returns.reduce((a, b) => a + b, 0) / n;
    const variance = returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / (n - 1 || 1);
    const std = Math.sqrt(variance);

    const ann_return = mean * 252;
    const ann_vol = std * Math.sqrt(252);
    const sharpe = ann_vol > 1e-9 ? ann_return / ann_vol : 0;

    return { ann_return, ann_vol, sharpe, days_in_regime: n };
};

const HMMStatsTable = ({ statsData, hmmData, priceData, bullThreshold, bearThreshold }) => {

    // Dynamic Calculation of Stats based on Thresholds
    const dynamicStats = useMemo(() => {
        if (!hmmData || !priceData || hmmData.length === 0 || priceData.length === 0) {
            return statsData || [];
        }

        // Create a map of date -> return for O(1) lookup
        const returnsMap = new Map();
        priceData.forEach(p => {
            // Ensure we use the correct return column
            const ret = p.ret_1d !== undefined ? p.ret_1d :
                p.log_ret_1d !== undefined ? p.log_ret_1d : 0;
            // Normalize date string just in case (assuming ISO YYYY-MM-DD)
            const dateStr = p.date.split('T')[0];
            returnsMap.set(dateStr, ret);
        });

        const bullReturns = [];
        const bearReturns = [];
        const neutralReturns = [];

        hmmData.forEach(d => {
            const dateStr = d.date.split('T')[0];
            const ret = returnsMap.get(dateStr);

            if (ret !== undefined) {
                // Check Bull
                if (d.hmm_prob_bull >= (bullThreshold / 100)) {
                    bullReturns.push(ret);
                }
                // Check Bear
                if (d.hmm_prob_bear >= (bearThreshold / 100)) {
                    bearReturns.push(ret);
                }
                // Check Neutral (if exists) - default to > 0.5 or plurality if needed, 
                // but for now let's use > 0.5 as a "Strong Neutral" proxy if the column exists
                if (d.hmm_prob_neutral !== undefined && d.hmm_prob_neutral >= 0.5) {
                    neutralReturns.push(ret);
                }
            }
        });

        const newStats = [];

        // Bull Stats
        const bullStat = calculateStats(bullReturns);
        newStats.push({ state: 'Bull', ...bullStat });

        // Bear Stats
        const bearStat = calculateStats(bearReturns);
        newStats.push({ state: 'Bear', ...bearStat });

        // Neutral Stats (only if we have neutral data)
        if (hmmData[0].hmm_prob_neutral !== undefined) {
            const neutralStat = calculateStats(neutralReturns);
            newStats.push({ state: 'Neutral', ...neutralStat });
        }

        return newStats;

    }, [hmmData, priceData, bullThreshold, bearThreshold, statsData]);


    const displayData = dynamicStats.length > 0 ? dynamicStats : statsData;

    if (!displayData || displayData.length === 0) {
        return <p style={{ color: '#9e9e9e' }}>No performance statistics available.</p>;
    }

    // Define table styling for a high-contrast, data-dense look
    const tableStyle = {
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: '13px',
        backgroundColor: '#0e1525',
    };
    const headerStyle = {
        padding: '10px 8px',
        textAlign: 'left',
        borderBottom: '1px solid #203049',
        color: '#9ec4ff',
        fontSize: '11px',
        textTransform: 'uppercase',
    };
    const cellStyle = {
        padding: '8px',
        borderBottom: '1px solid #203049',
        color: '#d7e3f3',
    };

    // Sort states for presentation: Bull > Neutral > Bear
    const sortOrder = { 'Bull': 3, 'Neutral': 2, 'Bear': 1 };
    const sortedStats = [...displayData].sort((a, b) => sortOrder[b.state] - sortOrder[a.state]);

    return (
        <div style={{ overflowX: 'auto', border: '1px solid #203049', borderRadius: '8px' }}>
            <table style={tableStyle}>
                <thead>
                    <tr>
                        <th style={{ ...headerStyle, width: '100px' }}>Regime</th>
                        <th style={headerStyle}>Days</th>
                        <th style={headerStyle}>Annualized Return</th>
                        <th style={headerStyle}>Annualized Volatility</th>
                        <th style={headerStyle}>Sharpe Ratio</th>
                    </tr>
                </thead>
                <tbody>
                    {sortedStats.map((stat) => (
                        <tr key={stat.state}>
                            <td style={{ ...cellStyle, fontWeight: 'bold', color: stat.state === 'Bull' ? '#4caf50' : stat.state === 'Bear' ? '#f44336' : '#9e9e9e' }}>
                                {stat.state}
                            </td>
                            <td style={cellStyle}>{formatDays(stat.days_in_regime)}</td>
                            <td style={cellStyle}>{formatPercent(stat.ann_return)}</td>
                            <td style={cellStyle}>{formatPercent(stat.ann_vol)}</td>
                            <td style={cellStyle}>{formatSharpe(stat.sharpe)}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default HMMStatsTable;
