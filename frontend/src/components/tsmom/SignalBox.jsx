import React, { useState, useEffect } from 'react';

const SignalBox = ({ data, date }) => {
    // data: List of tickers with signal change on 'date'

    if (!data || data.length === 0) {
        return (
            <div style={{ padding: '15px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049', marginBottom: '20px' }}>
                <h3 style={{ margin: '0 0 10px 0', color: '#9ec4ff', fontSize: '1rem' }}>No Recent Signals</h3>
                <p style={{ color: '#68778d', fontSize: '0.9rem' }}>No trend changes detected in the latest review.</p>
            </div>
        );
    }

    return (
        <div style={{ padding: '15px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049', marginBottom: '20px' }}>
            <h3 style={{ margin: '0 0 15px 0', color: '#9ec4ff', fontSize: '1rem', display: 'flex', justifyContent: 'space-between' }}>
                <span>Latest Rebalance Signals ({data.length})</span>
                <span style={{ fontSize: '0.9rem', color: '#68778d' }}>Review Date: {date}</span>
            </h3>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '15px' }}>
                {data.map((row) => {
                    const isLong = row.tsmom_dir === 1;
                    const color = isLong ? '#4caf50' : '#f44336';
                    const perf = row.perf_since_signal || 0;
                    const perfColor = perf >= 0 ? '#4caf50' : '#f44336';

                    return (
                        <div key={row.ticker} style={{
                            padding: '12px',
                            backgroundColor: '#1b263b',
                            borderRadius: '6px',
                            borderLeft: `4px solid ${color}`,
                            minWidth: '200px',
                            flex: '1 0 auto',
                            maxWidth: '250px'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                                <div style={{ fontWeight: 'bold', color: '#d7e3f3', fontSize: '1.1rem' }}>{row.ticker}</div>
                                <div style={{
                                    color: color,
                                    fontWeight: 'bold',
                                    textTransform: 'uppercase',
                                    fontSize: '0.9rem',
                                    backgroundColor: `${color}22`,
                                    padding: '2px 6px',
                                    borderRadius: '4px'
                                }}>
                                    {isLong ? 'NEW LONG' : 'NEW SHORT'}
                                </div>
                            </div>

                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                                <div style={{ color: '#68778d', fontSize: '0.8rem' }}>Since Rebalance:</div>
                                <div style={{ fontWeight: 'bold', color: perfColor }}>
                                    {(perf * 100).toFixed(2)}%
                                </div>
                            </div>

                            <div style={{ fontSize: '0.75rem', color: '#68778d', marginTop: '4px' }}>
                                Entry: {row.last_signal_price ? row.last_signal_price.toFixed(2) : '-'}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default SignalBox;
