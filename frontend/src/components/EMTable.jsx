import React from 'react';

const EMTable = ({ tickers }) => {
    if (!tickers || Object.keys(tickers).length === 0) {
        return <p style={{ color: '#9e9e9e' }}>No expected moves data available.</p>;
    }

    // Define table styling to match HMMStatsTable
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
        fontFamily: 'monospace', // Monospace for numbers
    };

    const fmt = (val) => val ? val.toFixed(2) : '-';

    return (
        <div style={{ overflowX: 'auto', border: '1px solid #203049', borderRadius: '8px' }}>
            <table style={tableStyle}>
                <thead>
                    <tr>
                        <th style={{ ...headerStyle, width: '80px' }}>Ticker</th>
                        <th style={headerStyle}>Spot Price</th>
                        <th style={headerStyle}>ODTE Exp</th>
                        <th style={headerStyle}>ODTE Range</th>
                        <th style={headerStyle}>Weekly Exp</th>
                        <th style={headerStyle}>Weekly Range</th>
                    </tr>
                </thead>
                <tbody>
                    {Object.entries(tickers).map(([ticker, data]) => {
                        if (data.error) return null; // Skip errors for now or handle differently

                        const odte = data.expirations?.ODTE;
                        const weekly = data.expirations?.WEEKLY;

                        return (
                            <tr key={ticker}>
                                <td style={{ ...cellStyle, fontWeight: 'bold', color: '#4caf50' }}>{ticker}</td>
                                <td style={cellStyle}>{fmt(data.spot_price)}</td>

                                {/* ODTE */}
                                <td style={{ ...cellStyle, color: '#9e9e9e' }}>{odte ? odte.expiry_date : '-'}</td>
                                <td style={cellStyle}>
                                    {odte ? (
                                        <span style={{ color: '#9ec4ff' }}>
                                            {fmt(odte.lower_range)} - {fmt(odte.upper_range)}
                                            <span style={{ color: '#555', marginLeft: '5px' }}>(±{fmt(odte.em_dollars)})</span>
                                        </span>
                                    ) : '-'}
                                </td>

                                {/* Weekly */}
                                <td style={{ ...cellStyle, color: '#9e9e9e' }}>{weekly ? weekly.expiry_date : '-'}</td>
                                <td style={cellStyle}>
                                    {weekly ? (
                                        <span style={{ color: '#d7e3f3' }}>
                                            {fmt(weekly.lower_range)} - {fmt(weekly.upper_range)}
                                            <span style={{ color: '#555', marginLeft: '5px' }}>(±{fmt(weekly.em_dollars)})</span>
                                        </span>
                                    ) : '-'}
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
};

export default EMTable;
