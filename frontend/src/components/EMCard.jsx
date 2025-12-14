import React, { useState, useEffect, useRef } from 'react';

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
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr 1fr', gap: '20px', alignItems: 'start' }}>

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

                {/* CENTER: Visualization (Centered Deviation Bar) */}
                <div style={{ height: '300px', position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {/* 
                       Logic:
                       - Vertical Bar representing the range.
                       - Center Tick = Previous Close.
                       - Triangle Pointer = Current Price.
                       - Fill Color Logic:
                         - Green: Price > Center (within range)
                         - Orange: Price < Center (within range)
                         - Red: Price outside range
                     */}
                    {(() => {
                        // Use ODTE EOD range as the base reference
                        const rangeLow = odte?.lower_range;
                        const rangeHigh = odte?.upper_range;
                        const centerPrice = spot; // Previous Close
                        const currentPrice = liveData?.spot_price || spot; // Use live if available, else older spot

                        if (!rangeLow || !rangeHigh || !centerPrice) return <div style={{ color: '#666' }}>No Range Data</div>;

                        // Create Scale
                        // We map Price -> Y coordinate (0 at top, 100 at bottom)
                        // Let's add padding (overflow) to the view
                        const span = rangeHigh - rangeLow;
                        const padding = span * 0.2; // 20% padding above/below
                        const viewMax = rangeHigh + padding;
                        const viewMin = rangeLow - padding;
                        const viewSpan = viewMax - viewMin;

                        const scaleY = (p) => {
                            // Inverted Y (Higher price = Lower Y value)
                            return 100 - ((p - viewMin) / viewSpan) * 100;
                        };

                        const yHigh = scaleY(rangeHigh);
                        const yLow = scaleY(rangeLow);
                        const yCenter = scaleY(centerPrice);
                        const yCurrent = scaleY(currentPrice);

                        // Determine Fill Color
                        let fillColor = '#4caf50'; // Default Green (Up)
                        let isWarning = false;

                        if (currentPrice < centerPrice) {
                            fillColor = '#ff9800'; // Orange (Down)
                        }

                        if (currentPrice > rangeHigh || currentPrice < rangeLow) {
                            fillColor = '#f44336'; // Red (Breakout)
                            isWarning = true;
                        }

                        // Determine Fill Height & Position
                        // Rect starts at Math.min(yCenter, yCurrent) and height is abs(yCenter - yCurrent)
                        const fillY = Math.min(yCenter, yCurrent);
                        const fillHeight = Math.abs(yCenter - yCurrent);

                        return (
                            <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ overflow: 'visible' }}>

                                {/* 1. Main Range Bar (Vertical Line) */}
                                <line
                                    x1="50" y1={yHigh}
                                    x2="50" y2={yLow}
                                    stroke="#334455"
                                    strokeWidth="6"
                                    strokeLinecap="round"
                                />

                                {/* 2. Active Fill (Dynamic) */}
                                <rect
                                    x="47"
                                    y={fillY}
                                    width="6"
                                    height={fillHeight}
                                    fill={fillColor}
                                    opacity="0.8"
                                />

                                {/* 3. Center Reference (Previous Close) - Horizontal Tick */}
                                <line
                                    x1="40" y1={yCenter}
                                    x2="60" y2={yCenter}
                                    stroke="#fff"
                                    strokeWidth="1"
                                    strokeDasharray="2 1"
                                    opacity="0.6"
                                />
                                <text x="35" y={yCenter + 1} fill="#888" fontSize="4" textAnchor="end" alignmentBaseline="middle">Prev Close</text>

                                {/* 4. Range Boundaries (Dots) */}
                                {/* Upper (Red Dot) */}
                                <circle cx="50" cy={yHigh} r="2" fill="#f44336" />

                                {/* Lower (Green Dot) */}
                                <circle cx="50" cy={yLow} r="2" fill="#4caf50" />

                                {/* 5. Current Price Pointer (Triangle) */}
                                {/* Shifted to the right of the bar */}
                                <g transform={`translate(0, ${yCurrent})`}>
                                    {/* Triangle pointing LEFT towards the bar */}
                                    <polygon points="60,0 65,-3 65,3" fill="#fff" />
                                    <text x="68" y="1.5" fill="#fff" fontSize="5" fontWeight="bold" alignmentBaseline="middle">
                                        {fmt(currentPrice)}
                                    </text>
                                </g>

                            </svg>
                        );
                    })()}
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
