import React, { useState, useEffect } from 'react';

const SignalBox = ({ history }) => {
    // history: List of all signal events { event_date, ticker, signal, tsmom_dir, ... }

    if (!history || history.length === 0) {
        return (
            <div style={{ padding: '20px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049', marginBottom: '20px', textAlign: 'center' }}>
                <h3 style={{ margin: 0, color: '#68778d', fontSize: '1rem' }}>No Signal History Available</h3>
            </div>
        );
    }

    // 1. Group by Date
    const grouped = history.reduce((acc, row) => {
        const dateStr = row.event_date; // "YYYY-MM-DD"
        if (!acc[dateStr]) acc[dateStr] = [];
        acc[dateStr].push(row);
        return acc;
    }, {});

    // 2. Sort Dates Descending
    const sortedDates = Object.keys(grouped).sort((a, b) => new Date(b) - new Date(a));

    // 3. Take Top 4
    const recentDates = sortedDates.slice(0, 4);

    return (
        <div style={{ padding: '20px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049', marginBottom: '20px' }}>
            <h3 style={{ margin: '0 0 20px 0', color: '#d7e3f3', fontSize: '1.2rem', borderBottom: '1px solid #203049', paddingBottom: '10px' }}>
                Recent Signal History (Last 4 Months)
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px' }}>
                {recentDates.map((date) => {
                    const signals = grouped[date];
                    // Parse date for nice display (e.g., "November 2025")
                    const dateObj = new Date(date);
                    const monthName = dateObj.toLocaleString('default', { month: 'long', year: 'numeric' });

                    return (
                        <div key={date} style={{ backgroundColor: '#1b263b', borderRadius: '8px', padding: '15px', border: '1px solid #304050' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                                <span style={{ fontWeight: 'bold', color: '#fff', fontSize: '1rem' }}>{monthName}</span>
                                <span style={{ fontSize: '0.8rem', color: '#68778d' }}>{date}</span>
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {signals.map((sig, idx) => {
                                    const isLong = sig.tsmom_dir === 1;
                                    const color = isLong ? '#4caf50' : '#f44336';
                                    return (
                                        <div key={`${sig.ticker}-${idx}`} style={{
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'center',
                                            backgroundColor: `${color}11`,
                                            padding: '6px 10px',
                                            borderRadius: '4px',
                                            borderLeft: `3px solid ${color}`
                                        }}>
                                            <span style={{ fontWeight: 'bold', color: '#d7e3f3' }}>{sig.ticker}</span>
                                            <span style={{ fontSize: '0.75rem', color: color, fontWeight: 'bold' }}>
                                                {isLong ? 'BUY' : 'SELL'}
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default SignalBox;
