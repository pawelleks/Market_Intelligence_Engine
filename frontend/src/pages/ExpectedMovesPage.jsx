import React, { useEffect, useState } from 'react';
import EMCard from '../components/EMCard';
import EMTradingViewChart from '../components/EMTradingViewChart';

// Error Boundary Component
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error("Page Error:", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: '20px', color: '#f44336', backgroundColor: '#0e1525', minHeight: '100vh' }}>
                    <h2>Something went wrong.</h2>
                    <pre style={{ whiteSpace: 'pre-wrap' }}>{this.state.error && this.state.error.toString()}</pre>
                </div>
            );
        }
        return this.props.children;
    }
}

import { usePageTitle } from '../hooks/usePageTitle';

const ExpectedMovesPage = () => {
    usePageTitle('Analysis: Expected Moves');
    return (
        <ErrorBoundary>
            <ExpectedMovesPageContent />
        </ErrorBoundary>
    );
};

const ExpectedMovesPageContent = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedTicker, setSelectedTicker] = useState(null);

    const [liveData, setLiveData] = useState(null);
    const [liveLoading, setLiveLoading] = useState(true);
    const [lastLiveUpdate, setLastLiveUpdate] = useState(null);

    const fetchData = async () => {
        try {
            const response = await fetch('/api/v1/expected_moves/latest');
            if (!response.ok) {
                throw new Error('Failed to fetch expected moves data');
            }
            const jsonData = await response.json();
            setData(jsonData);
            // Default select first ticker (Sorted)
            if (jsonData.tickers && Object.keys(jsonData.tickers).length > 0) {
                const sortedKeys = Object.keys(jsonData.tickers).sort();
                setSelectedTicker(sortedKeys[0]);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const fetchLiveData = async () => {
        try {
            const response = await fetch('/api/v1/expected_moves/massive/latest');
            if (response.ok) {
                const json = await response.json();
                setLiveData(json);
                setLastLiveUpdate(new Date().toLocaleTimeString());
            }
        } catch (err) {
            console.error("Failed to fetch live data", err);
        } finally {
            setLiveLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        fetchLiveData();
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

    // Auto-Refresh Logic
    useEffect(() => {
        const intervalId = setInterval(() => {
            fetchLiveData();
        }, 30000); // 30 seconds

        return () => clearInterval(intervalId);
    }, []);

    if (loading) return <div style={{ padding: '20px', color: '#d7e3f3' }}>Loading Expected Moves...</div>;
    if (error) return <div style={{ padding: '20px', color: '#f44336' }}>Error: {error}</div>;
    if (!data) return <div style={{ padding: '20px', color: '#d7e3f3' }}>No data available.</div>;

    const { as_of, vix1d, confidence_score, tickers } = data;

    // Get Sorted Tickers for stable display order
    const sortedTickers = tickers ? Object.keys(tickers).sort() : [];

    // Ensure selectedTicker is valid
    if (sortedTickers.length > 0 && (!selectedTicker || !tickers[selectedTicker])) {
        // We do this in render, but better to do in effect. For now this is safe as it won't cause infinite loop if we check condition
        // Actually, let's just use derived state or default.
    }

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

    // Helper to get previous trading day
    const getPreviousTradingDay = (dateStr) => {
        if (!dateStr) return null;
        const date = new Date(dateStr);
        date.setDate(date.getDate() - 1);
        // If Sunday, go back to Friday
        if (date.getDay() === 0) date.setDate(date.getDate() - 2);
        // If Saturday, go back to Friday
        if (date.getDay() === 6) date.setDate(date.getDate() - 1);
        return date.toISOString().split('T')[0];
    };

    const closePriceDate = getPreviousTradingDay(as_of);

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
                        Expected Moves are calculated using ATM Straddle prices for the 0DTE (Current/Next Session), Weekly, and Monthly expirations.
                    </p>
                </div>
            </div>

            {/* Right Panel: Data Table */}
            <div style={rightPanelStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid #203049', paddingBottom: '10px' }}>
                    <div>
                        <h2 style={{ fontSize: '1.5rem', marginBottom: '0', color: '#d7e3f3' }}>Expected Moves Analysis</h2>
                        <p style={{ color: '#9e9e9e', fontSize: '0.85rem', margin: '5px 0 0' }}>
                            Implied volatility derived ranges for key market indices.
                        </p>
                    </div>

                    {/* Ticker Selector */}
                    {sortedTickers.length > 0 && (
                        <select
                            value={selectedTicker || sortedTickers[0]}
                            onChange={(e) => setSelectedTicker(e.target.value)}
                            style={{
                                backgroundColor: '#1e293b',
                                color: '#fff',
                                border: '1px solid #334155',
                                padding: '8px 12px',
                                borderRadius: '4px',
                                fontSize: '14px',
                                outline: 'none',
                                cursor: 'pointer'
                            }}
                        >
                            {sortedTickers.map(t => (
                                <option key={t} value={t}>{t}</option>
                            ))}
                        </select>
                    )}
                </div>

                {/* Cards Section - Show ONLY Selected Ticker */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {selectedTicker && tickers[selectedTicker] && (
                        <EMCard
                            key={selectedTicker}
                            ticker={selectedTicker}
                            data={tickers[selectedTicker]}
                            asOf={closePriceDate}
                            liveData={liveData?.tickers?.[selectedTicker]}
                            lastUpdated={lastLiveUpdate}
                            isSelected={true}
                            onClick={() => { }} // No-op since it's the only one
                        />
                    )}
                </div>

                {/* Debug Info Section */}
                {selectedTicker && tickers[selectedTicker] && (
                    <div style={{
                        marginTop: '20px',
                        marginBottom: '20px',
                        padding: '10px',
                        backgroundColor: '#0e1525',
                        border: '1px solid #203049',
                        borderRadius: '8px',
                        fontSize: '0.85rem',
                        color: '#9e9e9e',
                        fontFamily: 'monospace'
                    }}>
                        <div style={{ fontWeight: 'bold', color: '#d7e3f3', marginBottom: '5px' }}>Debug Details (Polygon EOD) - {selectedTicker}</div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
                            {['ODTE', 'WEEKLY', 'MONTHLY'].map(type => {
                                const exp = tickers[selectedTicker]?.expirations?.[type];
                                const debug = exp?.debug;
                                if (!debug) return null;
                                return (
                                    <div key={type}>
                                        <div style={{ color: '#4caf50', fontWeight: 'bold' }}>{type} ({exp.expiry_date})</div>
                                        {debug.atm_strike !== undefined && <div>ATM Strike: {debug.atm_strike}</div>}
                                        {debug.call_price !== undefined && <div>Call: {debug.call_ticker || 'N/A'} (${debug.call_price?.toFixed(2)})</div>}
                                        {debug.put_price !== undefined && <div>Put:  {debug.put_ticker || 'N/A'} (${debug.put_price?.toFixed(2)})</div>}
                                        {debug.call_price !== undefined && debug.put_price !== undefined &&
                                            <div>Sum:  ${(debug.call_price + debug.put_price).toFixed(2)}</div>
                                        }
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
                        liveData={liveData?.tickers?.[selectedTicker]}
                    />
                )}
            </div>
        </div>
    );
};

export default ExpectedMovesPage;
