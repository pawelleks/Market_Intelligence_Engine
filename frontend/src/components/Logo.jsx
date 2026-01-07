import React from 'react';

const Logo = ({ className = "", style = {}, fontSize = "1.5rem" }) => {
    // Colors mapped from Tailwind:
    // text-white -> #ffffff
    // text-slate-200 -> #e2e8f0
    // text-yellow-400 -> #facc15

    return (
        <div
            className={className}
            style={{
                fontFamily: '"Outfit", system-ui, sans-serif',  // Using modern font stack
                fontWeight: 800,
                letterSpacing: '-0.05em',
                lineHeight: 1,
                fontSize: fontSize, // Allow manual override or prop usage
                display: 'flex',
                alignItems: 'center',
                userSelect: 'none',
                ...style
            }}
        >
            <span style={{ color: '#ffffff' }}>blind</span>
            <span style={{ color: '#e2e8f0' }}>monkey</span>
            <span style={{ color: '#facc15' }}>.io</span>
        </div>
    );
};

export default Logo;
