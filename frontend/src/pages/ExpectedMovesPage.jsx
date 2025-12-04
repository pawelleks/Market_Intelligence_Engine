import React, { useEffect, useState } from 'react';
import EMCard from '../components/EMCard';
import EMTradingViewChart from '../components/EMTradingViewChart';

const ExpectedMovesPage = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedTicker, setSelectedTicker] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await fetch('/api/v1/expected_moves/latest');
                if (!response.ok) {
                    throw new Error('Failed to fetch expected moves data');
                }
                const jsonData = await response.json();
                setData(jsonData);
                // Default select first ticker
                if (jsonData.tickers && Object.keys(jsonData.tickers).length > 0) {
                    setSelectedTicker(Object.keys(jsonData.tickers)[0]);
                }
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    // Layout Styles (Matching HMMRegimePage)
    const containerStyle = {
        display: 'flex',
        gap: '20px',
        padding: '20px',
        width: '100%',
        backgroundColor: '#0b1220', // Main background
        minHeight: '100vh',
        color: '#d7e3f3'
    };

    const leftPanelStyle = {
        width: '270px',
        flexShrink: 0,
        textAlign: 'left'
    };

    const rightPanelStyle = {
        flexGrow: 1,
        padding: '0 10px',
        textAlign: 'left',
        minWidth: 0
    };

    const boxStyle = {
        padding: '15px',
        border: '1px solid #203049',
        borderRadius: '8px',
        backgroundColor: '#0e1525',
        textAlign: 'left',
        marginBottom: '20px'
    };

    if (loading) return <div style={{ padding: '20px', color: '#d7e3f3' }}>Loading Expected Moves...</div>;
    if (error) return <div style={{ padding: '20px', color: '#f44336' }}>Error: {error}</div>;
    if (!data) return <div style={{ padding: '20px', color: '#d7e3f3' }}>No data available.</div>;

    const { as_of, vix1d, confidence_score, tickers } = data;

    // Market Condition Logic
    const getMarketCondition = (vix) => {
        if (!vix) return { label: 'Unknown', color: '#9e9e9e' };
        if (vix <= 8) return { label: 'Very Calm', color: '#4caf50' }; // Green
        if (vix <= 12) return { label: 'Normal', color: '#8bc34a' }; // Light Green
        if (vix <= 18) return { label: 'Volatile', color: '#ffeb3b' }; // Yellow
        if (vix <= 25) return { label: 'High Volatility', color: '#ff9800' }; // Orange
        return { label: 'Extreme Volatility', color: '#f44336' }; // Red
    };

    const marketCondition = getMarketCondition(vix1d);

    // Confidence Color Logic
    let confColor = '#f44336'; // Red
    if (confidence_score >= 60) confColor = '#4caf50'; // Green
    else if (confidence_score >= 30) confColor = '#ff9800'; // Orange

    return (
        <div style={containerStyle}>
            {/* Left Panel: Status & Config */}
            <div style={leftPanelStyle}>
                <div style={boxStyle}>
                    <h3 style={{ color: '#4caf50', marginTop: '0', fontSize: '1.1rem' }}>Market Status</h3>

                    <div style={{ marginBottom: '15px' }}>
                        <span style={{ fontSize: '1.2rem', color: '#ffffff', fontWeight: 'bold' }}>VIX1D</span>
                        <div style={{ fontSize: '3.5rem', fontWeight: 'bold', color: '#ffeb3b', lineHeight: '1.1', margin: '5px 0' }}>
                            {vix1d ? vix1d.toFixed(2) : 'N/A'}
                        </div>
                        {/* Market Condition Badge */}
                        <div style={{
                            marginTop: '8px',
                            display: 'inline-block',
                            padding: '6px 12px',
                            borderRadius: '6px',
                            backgroundColor: `${marketCondition.color}20`, // 20% opacity background
                            border: `1px solid ${marketCondition.color}`,
                            color: marketCondition.color,
                            fontSize: '1rem',
                            fontWeight: 'bold'
                        }}>
                            {marketCondition.label}
                        </div>
                    </div>

                    <div style={{ marginBottom: '15px' }}>
                        <span style={{ fontSize: '13px', color: '#9e9e9e' }}>Confidence Score</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{ fontSize: '1.2rem', fontWeight: 'bold', color: confColor }}>
                                {confidence_score}%
                            </span>
                            <div style={{ flexGrow: 1, height: '6px', backgroundColor: '#203049', borderRadius: '3px' }}>
                                <div style={{ width: `${confidence_score}%`, height: '100%', backgroundColor: confColor, borderRadius: '3px' }}></div>
                            </div>
                        </div>
                    </div>

                    <p style={{ fontSize: '12px', color: '#9e9e9e', marginTop: '10px', borderTop: '1px solid #203049', paddingTop: '10px' }}>
                        Calculated: {new Date(as_of).toLocaleDateString()}
                    </p>
                </div>

                <div style={boxStyle}>
                    <h3 style={{ color: '#9ec4ff', marginTop: '0', fontSize: '1rem' }}>About</h3>
                    <p style={{ fontSize: '12px', color: '#d7e3f3', lineHeight: '1.4' }}>
                        Expected Moves are calculated using ATM Straddle prices for the next trading session (ODTE) and the weekly expiration.
                    </p>
                </div>
            </div>

            {/* Right Panel: Data Table */}
            <div style={rightPanelStyle}>
                <h2 style={{ fontSize: '1.5rem', marginBottom: '0', color: '#d7e3f3' }}>Expected Moves Analysis</h2>
                <p style={{ color: '#9e9e9e', fontSize: '0.85rem', borderBottom: '1px solid #203049', paddingBottom: '10px', marginBottom: '20px' }}>
                    Implied volatility derived ranges for key market indices.
                </p>

                {/* Cards Section */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {tickers && Object.entries(tickers).map(([ticker, tData]) => (
                        <EMCard
                            key={ticker}
                            ticker={ticker}
                            data={tData}
                            isSelected={selectedTicker === ticker}
                            onClick={() => setSelectedTicker(ticker)}
                        />
                    ))}
                </div>

                {/* Debug Info Section */}
                {selectedTicker && tickers[selectedTicker] && (
                    <div style={{
                        marginBottom: '20px',
                        padding: '10px',
                        backgroundColor: '#0e1525',
                        border: '1px solid #203049',
                        borderRadius: '8px',
                        fontSize: '0.85rem',
                        color: '#9e9e9e',
                        fontFamily: 'monospace'
                    }}>
                        <div style={{ fontWeight: 'bold', color: '#d7e3f3', marginBottom: '5px' }}>Debug Details (yfinance)</div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
                            {['ODTE', 'WEEKLY', 'MONTHLY'].map(type => {
                                const exp = tickers[selectedTicker]?.expirations?.[type];
                                const debug = exp?.debug;
                                if (!debug) return null;
                                return (
                                    <div key={type}>
                                        <div style={{ color: '#4caf50', fontWeight: 'bold' }}>{type} ({exp.expiry_date})</div>
                                        <div>ATM Strike: {debug.atm_strike}</div>
                                        <div>Call: {debug.call_ticker || 'N/A'} (${debug.call_price?.toFixed(2)})</div>
                                        <div>Put:  {debug.put_ticker || 'N/A'} (${debug.put_price?.toFixed(2)})</div>
                                        <div>Sum:  ${(debug.call_price + debug.put_price).toFixed(2)}</div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Chart Section */}
                {selectedTicker && (
                    <EMTradingViewChart
                        ticker={selectedTicker}
                        odteData={tickers[selectedTicker]?.expirations?.ODTE}
                        weeklyData={tickers[selectedTicker]?.expirations?.WEEKLY}
                        monthlyData={tickers[selectedTicker]?.expirations?.MONTHLY}
                    />
                )}
            </div>
        </div>
    );
};

export default ExpectedMovesPage;
