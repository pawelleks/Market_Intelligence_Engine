import React from 'react';
import TsmomChart from './TsmomChart';

const TsmomSignalOverlay = ({ ticker, row, chartData, onClose }) => {
    if (!ticker || !row) return null;

    // --- 1. Interpretation Logic ---
    const retPct = row.ret_12m !== null ? (row.ret_12m * 100).toFixed(2) + '%' : 'N/A';
    const isBullish = row.tsmom_dir === 1;
    const isBearish = row.tsmom_dir === -1;
    const signalText = isBullish ? 'LONG' : (isBearish ? 'SHORT' : 'NEUTRAL');
    const signalColor = isBullish ? '#4caf50' : (isBearish ? '#f44336' : '#9e9e9e');

    // Construct the "Human Friendly" explanation
    let explanation = "";
    if (row.signal_changed) {
        // ALERT Context
        explanation = `An alert was generated for ${ticker} because the strategy signal changed to ${signalText}. `;
        if (isBullish) {
            explanation += `The 12-Month Momentum is positive (${retPct}), indicating an UP trend. `;
        } else if (isBearish) {
            explanation += `The 12-Month Momentum is negative (${retPct}), indicating a DOWN trend. `;
        }
        explanation += `This crossover confirms a new trend direction based on the TSMOM rules.`;
    } else {
        // STATUS Context
        explanation = `The strategy maintains a ${signalText} position. `;
        explanation += `The 12-Month return remains ${row.ret_12m >= 0 ? "positive" : "negative"} at ${retPct}. `;
        explanation += `No new alert was generated this month.`;
    }

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1000,
            padding: '20px' // Mobile padding
        }} onClick={onClose}>
            <div style={{
                backgroundColor: '#0e1525',
                border: '1px solid #203049',
                borderRadius: '8px',
                width: '100%',
                maxWidth: '900px',
                maxHeight: '90vh',
                overflowY: 'auto',
                boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
                display: 'flex',
                flexDirection: 'column'
            }} onClick={e => e.stopPropagation()}>

                {/* Header */}
                <div style={{
                    padding: '20px',
                    borderBottom: '1px solid #203049',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    backgroundColor: '#1b263b'
                }}>
                    <div>
                        <h2 style={{ margin: 0, color: '#d7e3f3' }}>
                            {ticker} Analysis
                            <span style={{
                                marginLeft: '15px',
                                fontSize: '0.8em',
                                backgroundColor: signalColor,
                                color: 'white',
                                padding: '2px 8px',
                                borderRadius: '4px'
                            }}>
                                {signalText}
                            </span>
                        </h2>
                    </div>
                    <button onClick={onClose} style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#68778d',
                        fontSize: '1.5rem',
                        cursor: 'pointer'
                    }}>×</button>
                </div>

                {/* Content */}
                <div style={{ padding: '20px' }}>

                    {/* Explanation Box */}
                    <div style={{
                        backgroundColor: '#1c2533',
                        padding: '20px',
                        borderRadius: '8px',
                        marginBottom: '20px',
                        borderLeft: `4px solid ${signalColor}`
                    }}>
                        <h4 style={{ margin: '0 0 10px 0', color: '#d7e3f3' }}>Why was this alert generated?</h4>
                        <p style={{ margin: 0, color: '#b0bec5', lineHeight: '1.5' }}>
                            {explanation}
                        </p>
                    </div>

                    {/* Stats Grid */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                        gap: '15px',
                        marginBottom: '20px'
                    }}>
                        <StatItem label="Closing Price" value={row.close.toFixed(2)} />
                        <StatItem label="12M Return" value={retPct} color={row.ret_12m >= 0 ? '#4caf50' : '#f44336'} />
                        <StatItem label="Signal Date" value={row.last_signal_date || "N/A"} />
                        <StatItem label="Next Review" value={row.next_rebalance_date || "Month End"} />
                    </div>

                    {/* Chart */}
                    <div style={{ minHeight: '400px' }}>
                        <TsmomChart ticker={ticker} chartData={chartData} />
                    </div>

                </div>
            </div>
        </div>
    );
};

const StatItem = ({ label, value, color }) => (
    <div style={{ backgroundColor: '#1b263b', padding: '15px', borderRadius: '4px' }}>
        <div style={{ color: '#68778d', fontSize: '0.8rem', marginBottom: '5px' }}>{label}</div>
        <div style={{ color: color || '#d7e3f3', fontSize: '1.2rem', fontWeight: 'bold' }}>{value}</div>
    </div>
);

export default TsmomSignalOverlay;
