import React from 'react';

const MinskySignals = ({ data }) => {
    if (!data || data.length === 0) return null;

    const current = data[data.length - 1];

    // Logic 1: Profit Momentum
    let profitStatus = "";
    let profitColor = "";
    let profitAdvice = "";

    if (current.minsky_instability_gap < 0) {
        profitStatus = "Healthy (Hedge)";
        profitColor = "#22c55e"; // Green
        profitAdvice = "Watch for Green bars shrinking (Profit Peak).";
    } else {
        profitStatus = "Unhealthy (Ponzi)";
        profitColor = "#ef4444"; // Red
        profitAdvice = "Watch for Red bars widening (Crisis Acceleration).";
    }

    // Logic 2: Risk Sentiment
    let riskStatus = "";
    let riskColor = "";
    let riskAdvice = "";

    if (current.risk_complacency_index > 0.5) { // User said 0.5 in instructions
        riskStatus = "Euphoric (High Risk Appetite)";
        riskColor = "#a855f7"; // Purple
        riskAdvice = "Watch for a sudden drop in the Purple Area (Panic).";
    } else {
        riskStatus = "Fearful (Risk Off)";
        riskColor = "#9ca3af"; // Gray
        riskAdvice = "Watch for the Purple Area rising (Confidence Returning).";
    }

    // Logic 3: Debt Stress
    let debtStatus = "";
    let debtColor = "";
    let debtAdvice = "";

    if (current.debt_service_proxy < current.leverage_ratio) {
        debtStatus = "Manageable";
        debtColor = "#60a5fa"; // Blue
        debtAdvice = "Watch if the Orange Line crosses above the Blue Line.";
    } else {
        debtStatus = "Critical Stress";
        debtColor = "#f97316"; // Orange
        debtAdvice = "Watch for the Orange Line falling below the Blue Line (Deleveraging).";
    }

    // Styles
    const gridStyle = {
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '24px',
        marginBottom: '32px'
    };

    const cardStyle = {
        backgroundColor: 'rgba(30, 41, 59, 1)', // bg-slate-800
        padding: '20px',
        borderRadius: '8px',
        border: '1px solid #334155' // slate-700
    };

    const titleStyle = {
        color: '#94a3b8', // slate-400
        fontSize: '12px',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        marginBottom: '8px',
        fontWeight: 'bold'
    };

    const statusStyle = (color) => ({
        color: color,
        fontSize: '18px',
        fontWeight: 'bold',
        marginBottom: '12px'
    });

    const adviceLabelStyle = {
        color: '#cbd5e1', // slate-300
        fontSize: '14px',
        fontStyle: 'italic'
    };

    return (
        <div style={gridStyle}>
            {/* Card A: Profit (Chart 1) */}
            <div style={cardStyle}>
                <div style={titleStyle}>A. Profit Validation</div>
                <div style={statusStyle(profitColor)}>{profitStatus}</div>
                <div style={adviceLabelStyle}>
                    <span style={{ fontWeight: 'bold', color: '#fff', display: 'block', marginBottom: '4px', fontStyle: 'normal' }}>What to Watch:</span>
                    {profitAdvice}
                </div>
            </div>

            {/* Card B: Debt (Chart 2) */}
            <div style={cardStyle}>
                <div style={titleStyle}>B. Debt Burden</div>
                <div style={statusStyle(debtColor)}>{debtStatus}</div>
                <div style={adviceLabelStyle}>
                    <span style={{ fontWeight: 'bold', color: '#fff', display: 'block', marginBottom: '4px', fontStyle: 'normal' }}>What to Watch:</span>
                    {debtAdvice}
                </div>
            </div>

            {/* Card C: Risk (Chart 3) */}
            <div style={cardStyle}>
                <div style={titleStyle}>C. Risk Sentiment</div>
                <div style={statusStyle(riskColor)}>{riskStatus}</div>
                <div style={adviceLabelStyle}>
                    <span style={{ fontWeight: 'bold', color: '#fff', display: 'block', marginBottom: '4px', fontStyle: 'normal' }}>What to Watch:</span>
                    {riskAdvice}
                </div>
            </div>
        </div>
    );
};

export default MinskySignals;
