import React, { useState, useMemo } from 'react';

// Heatmap Color Scale (Red -> Neutral -> Green)
const getReturnColor = (val) => {
    if (val === null || val === undefined) return 'inherit';
    if (val > 0.10) return '#4caf50'; // Strong Green
    if (val > 0.05) return '#81c784'; // Light Green
    if (val > 0) return '#a5d6a7';    // Very Light Green
    if (val === 0) return '#b0bec5';  // Neutral
    if (val > -0.05) return '#ef9a9a'; // Very Light Red
    if (val > -0.10) return '#e57373'; // Light Red
    return '#f44336'; // Strong Red
};

// Progress Bar Component
const RangeProgressBar = ({ pct }) => {
    if (pct === null || pct === undefined) return <span style={{ color: '#666' }}>-</span>;
    // pct is 0.0 to 1.0
    const percentage = Math.min(Math.max(pct * 100, 0), 100);

    // Color bar based on position? Or just neutral? Let's use Blue.
    return (
        <div style={{ width: '100%', height: '8px', backgroundColor: '#37474f', borderRadius: '4px', position: 'relative', overflow: 'hidden' }}>
            <div style={{
                width: `${percentage}%`,
                height: '100%',
                backgroundColor: '#2196f3',
                transition: 'width 0.3s ease'
            }} />
        </div>
    );
};

const PerformanceTable = ({ data }) => {
    // data: Array of objects { ticker, group, price, ret_1d, ..., high_52w, low_52w, pct_52w }

    // 1. Group Data
    const groupedData = useMemo(() => {
        const groups = {};
        data.forEach(row => {
            const grp = row.group || 'Other';
            if (!groups[grp]) groups[grp] = [];
            groups[grp].push(row);
        });
        return groups;
    }, [data]);

    // Group Order: We want to preserve the order from the API (which follows config),
    // so we just take the keys as they were inserted.
    const sortedGroups = Object.keys(groupedData);

    return (
        <div style={{ overflowX: 'auto', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', color: '#d7e3f3', fontSize: '0.9rem' }}>
                <thead>
                    <tr style={{ backgroundColor: '#1b263b', borderBottom: '2px solid #2d3b55' }}>
                        <th style={{ padding: '12px', textAlign: 'left' }}>Ticker</th>
                        <th style={{ padding: '12px', textAlign: 'right' }}>Price</th>
                        <th style={{ padding: '12px', textAlign: 'right' }}>1 Day</th>
                        <th style={{ padding: '12px', textAlign: 'right' }}>1 Week</th>
                        <th style={{ padding: '12px', textAlign: 'right' }}>1 Month</th>
                        <th style={{ padding: '12px', textAlign: 'right' }}>3 Months</th>
                        <th style={{ padding: '12px', textAlign: 'right' }}>6 Months</th>
                        <th style={{ padding: '12px', textAlign: 'right' }}>1 Year</th>
                        <th style={{ padding: '12px', textAlign: 'center', width: '150px' }}>52W Range</th>
                        <th style={{ padding: '12px', textAlign: 'right' }}>52W High</th>
                        <th style={{ padding: '12px', textAlign: 'right' }}>52W Low</th>
                    </tr>
                </thead>
                <tbody>
                    {sortedGroups.map(groupName => (
                        <React.Fragment key={groupName}>
                            {/* Group Header */}
                            <tr style={{ backgroundColor: '#10192c' }}>
                                <td colSpan={11} style={{ padding: '10px 15px', fontWeight: 'bold', color: '#90caf9', fontSize: '1rem', borderBottom: '1px solid #2d3b55' }}>
                                    {groupName} <span style={{ fontSize: '0.8rem', color: '#546e7a', fontWeight: 'normal' }}>({groupedData[groupName].length})</span>
                                </td>
                            </tr>

                            {/* Rows */}
                            {groupedData[groupName].map(row => (
                                <tr key={row.ticker} style={{ borderBottom: '1px solid #203049', transition: 'background 0.2s' }}>
                                    <td style={{ padding: '10px', textAlign: 'left', fontWeight: 'bold' }}>{row.ticker}</td>
                                    <td style={{ padding: '10px', textAlign: 'right' }}>{row.price?.toFixed(2)}</td>

                                    {/* Returns */}
                                    {['ret_1d', 'ret_1w', 'ret_1m', 'ret_3m', 'ret_6m', 'ret_1y'].map(key => (
                                        <td key={key} style={{ padding: '10px', textAlign: 'right', color: getReturnColor(row[key]) }}>
                                            {row[key] !== null ? `${(row[key] * 100).toFixed(2)}%` : '-'}
                                        </td>
                                    ))}

                                    {/* 52W Range Bar */}
                                    <td style={{ padding: '10px', verticalAlign: 'middle' }}>
                                        <RangeProgressBar pct={row.pct_52w} />
                                    </td>

                                    <td style={{ padding: '10px', textAlign: 'right', fontSize: '0.9rem', color: '#d7e3f3' }}>
                                        {row.high_52w?.toFixed(2)}
                                    </td>
                                    <td style={{ padding: '10px', textAlign: 'right', fontSize: '0.9rem', color: '#d7e3f3' }}>
                                        {row.low_52w?.toFixed(2)}
                                    </td>
                                </tr>
                            ))}
                        </React.Fragment>
                    ))}
                    {sortedGroups.length === 0 && (
                        <tr><td colSpan={11} style={{ padding: '20px', textAlign: 'center' }}>No Data Available</td></tr>
                    )}
                </tbody>
            </table>
        </div>
    );
};

export default PerformanceTable;
