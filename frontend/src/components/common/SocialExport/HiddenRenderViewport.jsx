import React from 'react';

/**
 * A hidden viewport container that renders children at a fixed 1200x630 resolution.
 * Used for consistent social media image generation (16:9 aspect ratio).
 * 
 * @param {Object} props - { children, innerRef }
 */
const HiddenRenderViewport = ({ children, innerRef }) => {
    return (
        <div
            style={{
                position: 'fixed',
                left: '-9999px',
                top: '-9999px',
                width: '1200px',
                height: '630px',
                overflow: 'hidden',
                zIndex: -1,
                pointerEvents: 'none'
            }}
            aria-hidden="true"
        >
            <div
                ref={innerRef}
                className="bg-[#0e1525] text-[#d7e3f3] w-full h-full relative"
                style={{
                    width: '1200px',
                    height: '630px',
                }}
            >
                {children}
            </div>
        </div>
    );
};

export default HiddenRenderViewport;
