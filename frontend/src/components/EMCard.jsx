import React, { useState, useEffect, useRef } from 'react';
import DynamicExpectedMoveChart from './DynamicExpectedMoveChart';

const EMCard = ({ ticker, data, asOf, liveData, lastUpdated, onClick, isSelected }) => {
    if (!data) return null;

    const odte = data.expirations?.ODTE;
    const weekly = data.expirations?.WEEKLY;
    const monthly = data.expirations?.MONTHLY;
    const spot = data.spot_price;

    const fmt = (val) => val ? val.toFixed(2) : '-';

    // --- Blinking Logic ---
    const [blinkClass, setBlinkClass] = useState('');
    const prevLivePriceRef = useRef(liveData?.spot_price);

    useEffect(() => {
        if (!liveData) return;
        const currentPrice = liveData.spot_price;
        const prevPrice = prevLivePriceRef.current;

        if (prevPrice !== undefined && currentPrice !== prevPrice) {
            if (currentPrice > prevPrice) {
                setBlinkClass('blink-green');
            } else if (currentPrice < prevPrice) {
                setBlinkClass('blink-red');
            }
            // Reset after animation
            const timer = setTimeout(() => setBlinkClass(''), 1000);
            return () => clearTimeout(timer);
        }
        prevLivePriceRef.current = currentPrice;
    }, [liveData]);

    // --- Visualization Logic ---
    // We want to show the ranges relative to the spot price.
    // We need a scale. Let's find the min/max of all ranges to set the SVG viewBox.
    const allValues = [
        odte?.lower_range, odte?.upper_range,
        weekly?.lower_range, weekly?.upper_range,
        monthly?.lower_range, monthly?.upper_range,
        liveData?.expirations?.ODTE?.lower_range, liveData?.expirations?.ODTE?.upper_range
    ].filter(v => v !== undefined && v !== null);

    const minVal = Math.min(...allValues, spot || Infinity) * 0.995;
    const maxVal = Math.max(...allValues, spot || -Infinity) * 1.005;
    const rangeSpan = maxVal - minVal;

    const scale = (val) => {
        if (!rangeSpan || rangeSpan === 0 || isNaN(rangeSpan) || !isFinite(rangeSpan)) return 50;
        return ((val - minVal) / rangeSpan) * 100;
    };

    const cardStyle = {
        border: isSelected ? '1px solid #2196f3' : '1px solid #203049',
        backgroundColor: isSelected ? '#131b2e' : '#0e1525',
        borderRadius: '8px',
        padding: '20px',
        marginBottom: '15px',
        cursor: 'pointer',
        transition: 'all 0.2s'
    };

    return (
        <div onClick={onClick} style={cardStyle}>
            <style>
                {`
                    @keyframes flashGreen {
                        0% { color: #4caf50; }
                        50% { color: #69f0ae; text-shadow: 0 0 5px #4caf50; }
                        100% { color: #4caf50; }
                    }
                    @keyframes flashRed {
                        0% { color: #4caf50; }
                        50% { color: #ff5252; text-shadow: 0 0 5px #ff5252; }
                        100% { color: #4caf50; }
                    }
                    .blink-green { animation: flashGreen 1s ease-out; }
                    .blink-red { animation: flashRed 1s ease-out; }
                `}
            </style>

            {/* 1. Ticker Title (Top, White) */}
            <div style={{ marginBottom: '5px' }}>
                <span style={{ fontSize: '1.8rem', fontWeight: 'bold', color: '#fff' }}>{ticker}</span>
            </div>

            {/* 2. Content Grid (3 Columns) */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr 1fr', gap: '20px', alignItems: 'center' }}>

                {/* LEFT: EOD Data */}
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                    {/* Close Price Block (Centered in Column) */}
                    <div style={{ textAlign: 'center', marginBottom: '20px', paddingBottom: '10px', borderBottom: '1px solid #203049' }}>
                        <div style={{ fontSize: '0.7rem', color: '#666', marginBottom: '2px' }}>
                            Close price: {asOf || 'N/A'}
                        </div>
                        <span style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#fff' }}>${fmt(spot)}</span>
                    </div>

                    <div style={{ fontSize: '12px', color: '#888', marginBottom: '15px', fontWeight: 'bold' }}>Polygon EOD</div>
                    {[
                        { label: 'ODTE', d: odte },
                        { label: 'WEEKLY', d: weekly },
                        { label: 'MONTHLY', d: monthly }
                    ].map((item, idx) => (
                        <div key={idx} style={{ marginBottom: '12px' }}>
                            <div style={{ fontSize: '10px', color: '#666', textTransform: 'uppercase' }}>{item.label} ({item.d?.expiry_date})</div>
                            <div style={{ fontSize: '1.1rem', color: '#d7e3f3' }}>
                                {fmt(item.d?.lower_range)} - {fmt(item.d?.upper_range)}
                            </div>
                            <div style={{ fontSize: '0.9rem', color: '#ffeb3b', fontWeight: 'bold' }}>
                                (±{fmt(item.d?.em_dollars)})
                            </div>
                        </div>
                    ))}
                </div>

                {/* CENTER: Visualization (Dynamic Chart) */}
                <div style={{ height: '300px', flexGrow: 1, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '6px' }}>
                    <DynamicExpectedMoveChart
                        ticker={ticker}
                        prevClose={spot} // spot from EOD is previous close
                        // FALLBACK LOGIC: If 0DTE is missing/empty, use Weekly for the chart
                        emHigh={odte?.upper_range || weekly?.upper_range}
                        emLow={odte?.lower_range || weekly?.lower_range}
                        label={odte?.upper_range ? "0DTE" : (weekly?.upper_range ? "WEEKLY" : "N/A")}
                        currentPrice={liveData?.spot_price || spot}
                        lastUpdated={lastUpdated}
                    />
                </div>

                {/* RIGHT: Live Data */}
                <div style={{ border: '1px solid #4caf50', borderRadius: '6px', padding: '15px', backgroundColor: 'rgba(76, 175, 80, 0.05)', display: 'flex', flexDirection: 'column' }}>

                    {/* Live Price Block (Centered in Column) */}
                    <div style={{ textAlign: 'center', marginBottom: '20px', paddingBottom: '10px', borderBottom: '1px solid rgba(76, 175, 80, 0.3)' }}>
                        {liveData ? (
                            <>
                                <div style={{ fontSize: '0.7rem', color: '#666', marginBottom: '2px' }}>
                                    Updated: {lastUpdated}
                                </div>
                                <div className={blinkClass} style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#4caf50', transition: 'color 0.3s' }}>
                                    ${fmt(liveData.spot_price)}
                                </div>
                            </>
                        ) : (
                            <div style={{ fontSize: '0.8rem', color: '#666', fontStyle: 'italic', padding: '10px' }}>Waiting for Live Data...</div>
                        )}
                    </div>

                    <div style={{ fontSize: '12px', color: '#4caf50', marginBottom: '15px', fontWeight: 'bold' }}>Live / Delayed (yfinance)</div>
                    {liveData ? (
                        [
                            { label: 'ODTE', d: liveData.expirations?.ODTE },
                            { label: 'WEEKLY', d: liveData.expirations?.WEEKLY },
                            { label: 'MONTHLY', d: liveData.expirations?.MONTHLY }
                        ].map((item, idx) => (
                            <div key={idx} style={{ marginBottom: '12px' }}>
                                <div style={{ fontSize: '10px', color: '#666', textTransform: 'uppercase' }}>
                                    {item.label} {item.d?.expiry_date ? `(${item.d.expiry_date})` : ''}
                                </div>
                                {item.d ? (
                                    <>
                                        <div style={{ fontSize: '1.1rem', color: '#fff' }}>
                                            {fmt(item.d.lower_range)} - {fmt(item.d.upper_range)}
                                        </div>
                                        <div style={{ fontSize: '0.9rem', color: '#4caf50', fontWeight: 'bold' }}>
                                            (±{fmt(item.d.em_dollars)})
                                        </div>
                                    </>
                                ) : (
                                    <div style={{ color: '#666', fontStyle: 'italic' }}>Loading...</div>
                                )}
                            </div>
                        ))
                    ) : (
                        <div style={{ color: '#888', fontStyle: 'italic', fontSize: '12px' }}>
                            Loading Live Data...
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default EMCard;
