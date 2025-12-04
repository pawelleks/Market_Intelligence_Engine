import React, { useState, useMemo } from 'react';

// Shortened labels for vertical headers
const SIGNAL_LABELS = {
    'price_lt_ema50': 'Price < EMA50',
    'ema20_lt_ema50': 'EMA20 < EMA50',
    'mom21_lt_0': 'Mom(21) < 0',
    'atr_gt_sma63': 'ATR > SMA63',
    'rv20_gt_rv63': 'RV20 > RV63',
    'vix_term_pos': 'VIX Term > 0',
    'rsp_spy_63_neg': 'RSP/SPY < 0',
    'hyg_lqd_21_neg': 'HYG/LQD < 0',
    'hmm_bear_prob': 'HMM Bear %'
};

const getScoreStyle = (score) => {
    let backgroundColor = '#2e7d32'; // Safe (Green)
    let color = '#ffffff';

    if (score >= 80) {
        backgroundColor = '#c62828'; // Crisis (Red)
    } else if (score >= 60) {
        backgroundColor = '#f57c00'; // Alert (Orange)
    } else if (score >= 40) {
        backgroundColor = '#c0ca33'; // Warning (Lime/Khaki)
        color = '#000000'; // Dark text for light background
    }

    return {
        backgroundColor,
        color,
        fontWeight: 'bold',
        textAlign: 'center',
        padding: '8px',
        borderRadius: '4px'
    };
};

const DowntrendSignalHistory = ({ data, timeRange, rowsPerPage }) => {
    const [currentPage, setCurrentPage] = useState(1);

    // Filter data based on timeRange
    const filteredData = useMemo(() => {
        if (!data) return [];

        const now = new Date();
        let cutoffDate = new Date();

        switch (timeRange) {
            case '1m': cutoffDate.setMonth(now.getMonth() - 1); break;
            case '3m': cutoffDate.setMonth(now.getMonth() - 3); break;
            case '6m': cutoffDate.setMonth(now.getMonth() - 6); break;
            case '1y': cutoffDate.setFullYear(now.getFullYear() - 1); break;
            case '5y': cutoffDate.setFullYear(now.getFullYear() - 5); break;
            case '10y': cutoffDate.setFullYear(now.getFullYear() - 10); break;
            default: cutoffDate.setFullYear(now.getFullYear() - 1); // Default 1y
        }

        return data.filter(row => new Date(row.date) >= cutoffDate).sort((a, b) => new Date(b.date) - new Date(a.date));
    }, [data, timeRange]);

    // Pagination logic
    const totalPages = Math.ceil(filteredData.length / rowsPerPage);
    const paginatedData = filteredData.slice((currentPage - 1) * rowsPerPage, currentPage * rowsPerPage);

    const handlePageChange = (newPage) => {
        if (newPage >= 1 && newPage <= totalPages) {
            setCurrentPage(newPage);
        }
    };

    if (!data || data.length === 0) {
        return <div style={{ color: '#9e9e9e', padding: '20px' }}>No signal history available.</div>;
    }

    const signalKeys = Object.keys(SIGNAL_LABELS).filter(k => k in data[0]);

    return (
        <div style={{ marginTop: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <h3 style={{ color: '#d7e3f3', margin: 0 }}>Signal History — {filteredData.length} Rows</h3>

                {/* Pagination Controls */}
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <button
                        onClick={() => handlePageChange(currentPage - 1)}
                        disabled={currentPage === 1}
                        style={{ padding: '5px 10px', backgroundColor: '#203049', border: 'none', color: '#d7e3f3', borderRadius: '4px', cursor: 'pointer', opacity: currentPage === 1 ? 0.5 : 1 }}
                    >
                        Prev
                    </button>
                    <span style={{ color: '#9e9e9e', fontSize: '14px' }}>Page {currentPage} of {totalPages}</span>
                    <button
                        onClick={() => handlePageChange(currentPage + 1)}
                        disabled={currentPage === totalPages}
                        style={{ padding: '5px 10px', backgroundColor: '#203049', border: 'none', color: '#d7e3f3', borderRadius: '4px', cursor: 'pointer', opacity: currentPage === totalPages ? 0.5 : 1 }}
                    >
                        Next
                    </button>
                </div>
            </div>

            <div style={{ overflowX: 'auto', border: '1px solid #203049', borderRadius: '8px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', whiteSpace: 'nowrap' }}>
                    <thead>
                        <tr style={{ backgroundColor: '#151d30', color: '#9ec4ff' }}>
                            <th style={{ padding: '8px', textAlign: 'left', borderBottom: '1px solid #203049', position: 'sticky', left: 0, backgroundColor: '#151d30', zIndex: 1 }}>Date</th>
                            <th style={{ padding: '8px', textAlign: 'center', borderBottom: '1px solid #203049' }}>Score</th>
                            {signalKeys.map(key => (
                                <th key={key} style={{ padding: '8px', textAlign: 'center', borderBottom: '1px solid #203049', verticalAlign: 'bottom' }}>
                                    <div style={{
                                        writingMode: 'vertical-rl',
                                        transform: 'rotate(180deg)',
                                        height: '100px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'flex-start' // Start from bottom due to rotation
                                    }}>
                                        {SIGNAL_LABELS[key]}
                                    </div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {paginatedData.map((row, idx) => (
                            <tr key={idx} style={{ borderBottom: '1px solid #203049', backgroundColor: idx % 2 === 0 ? '#0b1220' : '#0e1525' }}>
                                <td style={{ padding: '8px', color: '#d7e3f3', position: 'sticky', left: 0, backgroundColor: idx % 2 === 0 ? '#0b1220' : '#0e1525' }}>{row.date}</td>
                                <td style={{ padding: '4px' }}>
                                    <div style={getScoreStyle(row.score)}>
                                        {row.score.toFixed(2)}
                                    </div>
                                </td>
                                {signalKeys.map(key => {
                                    const val = row[key];

                                    // HMM Bear Prob is a float.
                                    if (key === 'hmm_bear_prob') {
                                        // Color gradient for HMM? Or just text.
                                        // Let's use simple text for now, maybe bold if high.
                                        const prob = val * 100;
                                        return (
                                            <td key={key} style={{ padding: '8px', textAlign: 'center', color: prob > 50 ? '#f44336' : '#d7e3f3' }}>
                                                {prob.toFixed(0)}%
                                            </td>
                                        );
                                    }

                                    // Boolean Signals (0 or 1)
                                    // 1 = Bad (Bearish) -> Red
                                    // 0 = Good (Bullish) -> Green
                                    const isBearish = val >= 0.5;
                                    const cellColor = isBearish ? '#ef5350' : '#66bb6a'; // Red vs Green

                                    return (
                                        <td key={key} style={{ padding: '4px', textAlign: 'center' }}>
                                            <div style={{
                                                width: '100%',
                                                height: '20px',
                                                backgroundColor: cellColor,
                                                borderRadius: '2px',
                                                opacity: 0.8
                                            }}></div>
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default DowntrendSignalHistory;
