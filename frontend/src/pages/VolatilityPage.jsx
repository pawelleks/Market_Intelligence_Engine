import React, { useState, useEffect } from 'react';
import VolatilityChart from '../components/VolatilityChart';

const API_BASE = '/api/v1';

const VolatilityPage = () => {
    // State
    const [summary, setSummary] = useState([]);
    const [history, setHistory] = useState([]);
    const [selectedTicker, setSelectedTicker] = useState('SPY');
    const [loadingSummary, setLoadingSummary] = useState(true);
    const [loadingHistory, setLoadingHistory] = useState(false);
    const [error, setError] = useState(null);

    // Initial Load: Summary + Ticker List
    useEffect(() => {
        fetchSummary();
    }, []);

    // On Ticker Change: Fetch History
    useEffect(() => {
        if (selectedTicker) {
            fetchHistory(selectedTicker);
        }
    }, [selectedTicker]);

    const fetchSummary = async () => {
        setLoadingSummary(true);
        try {
            const res = await fetch(`${API_BASE}/volatility/summary`);
            if (!res.ok) throw new Error("Failed to fetch summary");
            const data = await res.json();
            setSummary(Array.isArray(data) ? data : []);

            // Auto-select first if SPY not found
            if (data.length > 0) {
                const hasSPY = data.find(d => d.ticker === 'SPY');
                if (!hasSPY && !selectedTicker) setSelectedTicker(data[0].ticker);
            }
        } catch (e) {
            console.error(e);
            setError(e.message);
        } finally {
            setLoadingSummary(false);
        }
    };

    const fetchHistory = async (ticker) => {
        setLoadingHistory(true);
        try {
            const res = await fetch(`${API_BASE}/volatility/history/${ticker}`);
            if (!res.ok) throw new Error("Failed to fetch history");
            const data = await res.json();
            setHistory(data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoadingHistory(false);
        }
    };

    // Get current ticker metrics
    const currentMetrics = summary.find(s => s.ticker === selectedTicker) || {};

    // Helper for Card Color
    const getRegimeColor = (regime) => {
        if (regime === 'Squeeze') return '#ffab40'; // Orange Warning
        if (regime === 'Expansion') return '#ff5252'; // Red Danger
        if (regime === 'Trend Strength') return '#69f0ae'; // Green Good
        return '#90caf9'; // Blue Neutral
    };

    // Helper for Card Border
    const getCardStyle = (regime) => {
        const color = getRegimeColor(regime);
        return {
            borderTop: `4px solid ${color}`,
            backgroundColor: '#131c2e' // Darker card bg
        };
    };

    return (
        <div style={{ padding: '20px', maxWidth: '1600px', margin: '0 auto', color: '#d7e3f3' }}>

            {/* Header Area */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: '2rem' }}>Volatility & Risk (ATR)</h1>
                    <div style={{ color: '#68778d', marginTop: '5px' }}>
                        Volatility Regime Analysis using 14-period ATR
                    </div>
                </div>

                {/* Ticker Selector */}
                <select
                    value={selectedTicker}
                    onChange={(e) => setSelectedTicker(e.target.value)}
                    style={{
                        padding: '10px 20px',
                        fontSize: '1rem',
                        backgroundColor: '#1b2637',
                        color: '#d7e3f3',
                        border: '1px solid #2d3b55',
                        borderRadius: '4px',
                        outline: 'none',
                        cursor: 'pointer'
                    }}
                >
                    {summary.map(s => (
                        <option key={s.ticker} value={s.ticker}>{s.ticker}</option>
                    ))}
                </select>
            </div>

            {/* Metrics Grid */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
                gap: '20px',
                marginBottom: '30px'
            }}>
                {/* ATR Value */}
                <div className="stat-card" style={{ padding: '20px', backgroundColor: '#131c2e', borderRadius: '8px', border: '1px solid #203049' }}>
                    <div style={{ color: '#68778d', fontSize: '0.9rem', marginBottom: '8px' }}>Current ATR (14)</div>
                    <div style={{ fontSize: '1.8rem', fontWeight: 'bold' }}>
                        {currentMetrics.atr ? `$${currentMetrics.atr.toFixed(2)}` : '-'}
                    </div>
                </div>

                {/* ATR Percent */}
                <div className="stat-card" style={{ padding: '20px', backgroundColor: '#131c2e', borderRadius: '8px', border: '1px solid #203049' }}>
                    <div style={{ color: '#68778d', fontSize: '0.9rem', marginBottom: '8px' }}>Avg Daily Range %</div>
                    <div style={{ fontSize: '1.8rem', fontWeight: 'bold' }}>
                        {currentMetrics.atr_percent ? `${currentMetrics.atr_percent.toFixed(2)}%` : '-'}
                    </div>
                </div>

                {/* ATR Rank */}
                <div className="stat-card" style={{ padding: '20px', backgroundColor: '#131c2e', borderRadius: '8px', border: '1px solid #203049' }}>
                    <div style={{ color: '#68778d', fontSize: '0.9rem', marginBottom: '8px' }}>Volatility Rank (6M)</div>
                    <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: currentMetrics.atr_rank > 80 ? '#ff5252' : (currentMetrics.atr_rank < 20 ? '#ffab40' : '#d7e3f3') }}>
                        {currentMetrics.atr_rank ? `${currentMetrics.atr_rank.toFixed(0)}%` : '-'}
                    </div>
                </div>

                {/* Regime / Conclusion */}
                <div className="stat-card" style={{
                    padding: '20px',
                    borderRadius: '8px',
                    ...getCardStyle(currentMetrics.volatility_regime)
                }}>
                    <div style={{ color: '#68778d', fontSize: '0.9rem', marginBottom: '8px' }}>Market Regime</div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 'bold', marginBottom: '5px' }}>
                        {currentMetrics.volatility_regime || 'Loading...'}
                    </div>
                    <div style={{ fontSize: '0.9rem', opacity: 0.8 }}>
                        {currentMetrics.volatility_desc}
                    </div>
                </div>
            </div>

            {/* Chart Section */}
            <div style={{ backgroundColor: '#131c2e', borderRadius: '8px', padding: '20px', border: '1px solid #203049', minHeight: '600px' }}>
                {loadingHistory ? (
                    <div style={{ padding: '40px', textAlign: 'center', color: '#68778d' }}>Loading Chart Data...</div>
                ) : (
                    <VolatilityChart data={history} ticker={selectedTicker} />
                )}
            </div>

        </div>
    );
};

export default VolatilityPage;
