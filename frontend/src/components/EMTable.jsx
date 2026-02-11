import React from 'react';
import { COLORS, EM_COLORS } from '../constants/theme';

const EMTable = ({ tickers }) => {
    if (!tickers || Object.keys(tickers).length === 0) {
        return <p style={{ color: COLORS.text.muted }}>No expected moves data available.</p>;
    }

    const tableStyle = {
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: '13px',
        backgroundColor: COLORS.bg.card,
    };
    const headerStyle = {
        padding: '10px 8px',
        textAlign: 'left',
        borderBottom: `1px solid ${COLORS.border.default}`,
        color: COLORS.text.accent,
        fontSize: '11px',
        textTransform: 'uppercase',
    };
    const cellStyle = {
        padding: '8px',
        borderBottom: `1px solid ${COLORS.border.default}`,
        color: COLORS.text.primary,
        fontFamily: 'monospace',
    };

    const fmt = (val) => val ? val.toFixed(2) : '-';

    return (
        <div style={{ overflowX: 'auto', border: `1px solid ${COLORS.border.default}`, borderRadius: '8px' }}>
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
                        if (data.error) return null;

                        const odte = data.expirations?.ODTE;
                        const weekly = data.expirations?.WEEKLY;

                        return (
                            <tr key={ticker}>
                                <td style={{ ...cellStyle, fontWeight: 'bold', color: COLORS.ticker }}>{ticker}</td>
                                <td style={cellStyle}>{fmt(data.spot_price)}</td>

                                {/* ODTE */}
                                <td style={{ ...cellStyle, color: COLORS.text.muted }}>{odte ? odte.expiry_date : '-'}</td>
                                <td style={cellStyle}>
                                    {odte ? (
                                        <span style={{ color: EM_COLORS.dte0.high }}>
                                            {fmt(odte.lower_range)} - {fmt(odte.upper_range)}
                                            <span style={{ color: COLORS.border.grid, marginLeft: '5px' }}>(±{fmt(odte.em_dollars)})</span>
                                        </span>
                                    ) : '-'}
                                </td>

                                {/* Weekly */}
                                <td style={{ ...cellStyle, color: COLORS.text.muted }}>{weekly ? weekly.expiry_date : '-'}</td>
                                <td style={cellStyle}>
                                    {weekly ? (
                                        <span style={{ color: COLORS.text.primary }}>
                                            {fmt(weekly.lower_range)} - {fmt(weekly.upper_range)}
                                            <span style={{ color: COLORS.border.grid, marginLeft: '5px' }}>(±{fmt(weekly.em_dollars)})</span>
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
