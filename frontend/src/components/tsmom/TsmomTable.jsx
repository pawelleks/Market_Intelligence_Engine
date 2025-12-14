import React, { useState, useMemo } from 'react';

const TsmomTable = ({ data, onTickerSelect }) => {
    const [sortConfig, setSortConfig] = useState({ key: 'ret_12m', direction: 'descending' });

    const requestSort = (key) => {
        let direction = 'ascending';
        if (sortConfig.key === key && sortConfig.direction === 'ascending') {
            direction = 'descending';
        }
        setSortConfig({ key, direction });
    };

    const sortedData = useMemo(() => {
        if (!data) return [];
        let sortableItems = [...data];
        if (sortConfig.key) {
            sortableItems.sort((a, b) => {
                let aVal = a[sortConfig.key];
                let bVal = b[sortConfig.key];

                // Handle strings (case-insensitive)
                if (typeof aVal === 'string') aVal = aVal.toLowerCase();
                if (typeof bVal === 'string') bVal = bVal.toLowerCase();

                if (aVal < bVal) {
                    return sortConfig.direction === 'ascending' ? -1 : 1;
                }
                if (aVal > bVal) {
                    return sortConfig.direction === 'ascending' ? 1 : -1;
                }
                return 0;
            });
        }
        return sortableItems;
    }, [data, sortConfig]);

    const getSortIndicator = (key) => {
        if (sortConfig.key !== key) return <span style={{ color: '#444' }}> ⇅</span>;
        return sortConfig.direction === 'ascending' ? ' ▲' : ' ▼';
    };

    const getHeaderColor = (key) => {
        return sortConfig.key === key ? '#d7e3f3' : '#68778d';
    };

    if (!data || data.length === 0) return <div>No data available.</div>;

    const headerStyle = { padding: '12px', cursor: 'pointer', userSelect: 'none' };

    return (
        <div style={{ backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049', overflow: 'hidden' }}>
            <div style={{ padding: '15px', borderBottom: '1px solid #203049', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0, color: '#d7e3f3', fontSize: '1rem' }}>Market Snapshot</h3>
                <span style={{ color: '#68778d', fontSize: '0.9rem', fontWeight: 'bold' }}>Available Tickers: {sortedData.length}</span>
            </div>

            <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', color: '#d7e3f3', fontSize: '0.9rem' }}>
                    <thead>
                        <tr style={{ borderBottom: '1px solid #203049', backgroundColor: '#1b263b' }}>
                            <th style={{ padding: '12px', textAlign: 'center', color: '#68778d', width: '50px' }}>#</th>
                            <th
                                style={{ padding: '12px', textAlign: 'left', cursor: 'pointer', color: getHeaderColor('ticker') }}
                                onClick={() => requestSort('ticker')}
                            >
                                Ticker {getSortIndicator('ticker')}
                            </th>
                            <th style={{ padding: '12px', textAlign: 'right', color: '#68778d' }}>Close</th>
                            <th
                                style={{ padding: '12px', textAlign: 'right', cursor: 'pointer', color: getHeaderColor('ret_12m') }}
                                onClick={() => requestSort('ret_12m')}
                            >
                                12M Return {getSortIndicator('ret_12m')}
                            </th>
                            <th style={{ padding: '12px', textAlign: 'center', color: '#68778d' }}>Trend</th>
                            <th style={{ padding: '12px', textAlign: 'center', color: '#68778d' }}>Signal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sortedData.map((row, index) => {
                            const isBullish = row.tsmom_dir === 1;
                            const isBearish = row.tsmom_dir === -1;
                            const trendColor = isBullish ? '#4caf50' : (isBearish ? '#f44336' : '#9e9e9e');
                            const trendText = isBullish ? 'UP' : (isBearish ? 'DOWN' : 'NEUTRAL');

                            return (
                                <tr
                                    key={row.ticker}
                                    style={{ borderBottom: '1px solid #203049', cursor: 'pointer', transition: 'background 0.2s' }}
                                    onClick={() => onTickerSelect(row.ticker)}
                                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#1c2533'}
                                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                                >
                                    <td style={{ padding: '12px', textAlign: 'center', color: '#506070' }}>{index + 1}</td>
                                    <td style={{ padding: '12px', fontWeight: 'bold' }}>{row.ticker}</td>
                                    <td style={{ padding: '12px', textAlign: 'right' }}>{row.close.toFixed(2)}</td>
                                    <td style={{ padding: '12px', textAlign: 'right', color: row.ret_12m !== null && row.ret_12m >= 0 ? '#4caf50' : '#f44336' }}>
                                        {row.ret_12m !== null ? `${(row.ret_12m * 100).toFixed(2)}%` : <span style={{ color: '#666' }}>N/A</span>}
                                    </td>
                                    <td style={{ padding: '12px', textAlign: 'center' }}>
                                        <span style={{
                                            backgroundColor: row.ret_12m !== null ? `${trendColor}33` : '#333',
                                            color: row.ret_12m !== null ? trendColor : '#888',
                                            padding: '4px 8px',
                                            borderRadius: '4px',
                                            fontWeight: 'bold',
                                            fontSize: '0.8rem'
                                        }}>
                                            {row.ret_12m !== null ? trendText : row.signal_today || 'NO DATA'}
                                        </span>
                                    </td>
                                    <td style={{ padding: '12px', textAlign: 'center' }}>
                                        {row.signal_changed ? (
                                            <span style={{
                                                border: `1px solid ${trendColor}`,
                                                color: trendColor,
                                                padding: '2px 6px',
                                                borderRadius: '4px',
                                                fontSize: '0.8rem'
                                            }}>
                                                {row.signal_today}
                                            </span>
                                        ) : (
                                            <span style={{ color: '#506070', fontSize: '0.8rem' }}>-</span>
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default TsmomTable;
