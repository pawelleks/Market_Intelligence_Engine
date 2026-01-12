import React, { useState } from 'react';

const MinskyExplainer = () => {
    const [isOpen, setIsOpen] = useState(false);

    const toggle = () => setIsOpen(!isOpen);

    const containerStyle = {
        marginBottom: '24px',
        backgroundColor: 'rgba(31, 41, 55, 0.5)', // Gray-800/50
        borderRadius: '8px',
        border: '1px solid rgba(55, 65, 81, 0.5)', // Gray-700/50
        overflow: 'hidden',
        color: '#d1d5db' // Gray-300
    };

    const headerStyle = {
        padding: '16px',
        cursor: 'pointer',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontWeight: '600',
        color: '#93c5fd', // Blue-300
        backgroundColor: 'rgba(17, 24, 39, 0.5)' // Gray-900/50
    };

    const contentStyle = {
        padding: '24px',
        borderTop: '1px solid rgba(55, 65, 81, 0.5)'
    };

    const sectionTitleStyle = {
        fontSize: '16px',
        fontWeight: 'bold',
        color: '#f3f4f6', // Gray-100
        marginTop: '16px',
        marginBottom: '8px'
    };

    const textStyle = {
        fontSize: '14px',
        lineHeight: '1.6',
        color: '#9ca3af', // Gray-400
        margin: 0
    };

    return (
        <div style={containerStyle}>
            <div onClick={toggle} style={headerStyle}>
                <span>ℹ️ How to read this model (Minsky for Beginners)</span>
                <span>{isOpen ? '▲' : '▼'}</span>
            </div>

            {isOpen && (
                <div style={contentStyle}>
                    <div style={{ marginBottom: '20px' }}>
                        <h3 style={{ ...sectionTitleStyle, marginTop: 0, fontSize: '18px', color: '#fff' }}>The Big Idea</h3>
                        <p style={textStyle}>
                            Think of the economy like a driver. When the road is smooth (Stability), the driver speeds up (Debt).
                            Eventually, they go so fast that a small bump causes a crash. Minsky proved that "Stability breeds Instability".
                        </p>
                    </div>

                    <div>
                        <h4 style={sectionTitleStyle}>1. The Crisis Signal (Top Chart)</h4>
                        <p style={textStyle}>
                            Tracks the race between Profits and Debt.
                            <span style={{ color: '#22c55e', fontWeight: 'bold' }}> Green Bars</span> mean Profits are winning (Safe).
                            <span style={{ color: '#ef4444', fontWeight: 'bold' }}> Red Bars</span> mean Debt is winning (Danger/Ponzi Finance).
                        </p>
                    </div>

                    <div>
                        <h4 style={sectionTitleStyle}>2. The Fuel (Middle Chart)</h4>
                        <p style={textStyle}>
                            Shows Leverage (Blue) vs. Interest Costs (Orange). High leverage is fine until interest costs spike.
                            Divergence here signals a crash.
                        </p>
                    </div>

                    <div>
                        <h4 style={sectionTitleStyle}>3. The Trigger (Bottom Chart)</h4>
                        <p style={textStyle}>
                            High peaks mean investors are euphoric and ignoring risk. Sudden drops usually mark the onset of a panic.
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
};

export default MinskyExplainer;
