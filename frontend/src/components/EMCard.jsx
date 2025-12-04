import React from 'react';

const EMCard = ({ ticker, data, onClick, isSelected }) => {
    if (!data) return null;

    const odte = data.expirations?.ODTE;
    const weekly = data.expirations?.WEEKLY;
    const spot = data.spot_price;

    const fmt = (val) => val ? val.toFixed(2) : '-';

    return (
        <div
            onClick={onClick}
            style={{
                border: isSelected ? '1px solid #2196f3' : '1px solid #203049',
                backgroundColor: isSelected ? '#131b2e' : '#0e1525',
                borderRadius: '8px',
                padding: '15px',
                marginBottom: '15px',
                cursor: 'pointer',
                transition: 'all 0.2s'
            }}
        >
            {/* Header: Ticker & Spot */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                    <span style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#4caf50' }}>{ticker}</span>
                    <span style={{ fontSize: '1rem', color: '#d7e3f3' }}>${fmt(spot)}</span>
                </div>
                {/* Placeholder for Live Price if needed later */}
            </div>

            {/* Row 1: ODTE */}
            <div style={{ marginBottom: '10px' }}>
                <div style={{ fontSize: '11px', color: '#9e9e9e', textTransform: 'uppercase' }}>ODTE ({odte?.expiry_date})</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                    <span style={{ color: '#9ec4ff', fontSize: '1.1rem' }}>
                        {fmt(odte?.lower_range)} - {fmt(odte?.upper_range)}
                    </span>
                    {/* Straddle Value: Yellow and Bigger */}
                    <span style={{ color: '#ffeb3b', fontSize: '1.1rem', fontWeight: 'bold' }}>
                        (±{fmt(odte?.em_dollars)})
                    </span>
                </div>
            </div>

            {/* Row 2: Weekly */}
            <div style={{ marginBottom: '10px' }}>
                <div style={{ fontSize: '11px', color: '#9e9e9e', textTransform: 'uppercase' }}>Weekly ({weekly?.expiry_date})</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                    <span style={{ color: '#9ec4ff', fontSize: '1.1rem' }}>
                        {fmt(weekly?.lower_range)} - {fmt(weekly?.upper_range)}
                    </span>
                    <span style={{ color: '#ffeb3b', fontSize: '1.1rem', fontWeight: 'bold' }}>
                        (±{fmt(weekly?.em_dollars)})
                    </span>
                </div>
            </div>

            {/* Row 3: Monthly */}
            <div>
                <div style={{ fontSize: '11px', color: '#9e9e9e', textTransform: 'uppercase' }}>Monthly ({data.expirations?.MONTHLY?.expiry_date})</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
                    <span style={{ color: '#9ec4ff', fontSize: '1.1rem' }}>
                        {fmt(data.expirations?.MONTHLY?.lower_range)} - {fmt(data.expirations?.MONTHLY?.upper_range)}
                    </span>
                    <span style={{ color: '#ffeb3b', fontSize: '1.1rem', fontWeight: 'bold' }}>
                        (±{fmt(data.expirations?.MONTHLY?.em_dollars)})
                    </span>
                </div>
            </div>
        </div>
    );
};

export default EMCard;
