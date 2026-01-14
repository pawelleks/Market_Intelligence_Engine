import React, { useMemo } from 'react';

const Sparkline = ({ data, color = '#06b6d4', width = '100%', height = '100%' }) => {
    const path = useMemo(() => {
        if (!data || data.length === 0) return '';

        const values = data.map(d => d.value);
        const min = Math.min(...values);
        const max = Math.max(...values);
        const range = max - min || 1;

        // We use a fixed internal coordinate system (e.g. 100x100) and preserveAspectRatio in SVG
        const internalWidth = 100;
        const internalHeight = 50;

        const points = data.map((d, i) => {
            const x = (i / (data.length - 1)) * internalWidth;
            const y = internalHeight - ((d.value - min) / range) * internalHeight;
            return `${x},${y}`;
        });

        return `M ${points.join(' L ')}`;
    }, [data]);

    if (!data || data.length === 0) {
        return <div className="text-xs text-gray-500 flex items-center justify-center h-full">No data</div>;
    }

    return (
        <svg
            className="w-full h-full overflow-visible"
            viewBox="0 0 100 50"
            preserveAspectRatio="none"
        >
            <path
                d={path}
                stroke={color}
                strokeWidth="2"
                fill="none"
                vectorEffect="non-scaling-stroke"
            />
        </svg>
    );
};

export default Sparkline;
