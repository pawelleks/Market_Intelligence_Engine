import React, { useMemo } from 'react';
import { ReferenceArea, ReferenceLine } from 'recharts';

/**
 * RecessionOverlay Component
 * Renders shaded regions and dashed boundary lines for recession periods.
 * 
 * Supports TWO formats:
 * 1. New format: Array of {start, end} date ranges (preferred)
 * 2. Legacy format: Array of {date, value} where value=1 is recession
 * 
 * @param {Array} data - The main chart data array (used for date alignment)
 * @param {Array} recessionData - Recession periods in either format
 * @param {string} color - Shading color (default: #374151)
 * @param {number} opacity - Shading opacity (default: 0.3)
 */
const RecessionOverlay = ({ data, recessionData, color = '#374151', opacity = 0.3 }) => {
    const spans = useMemo(() => {
        if (!data || data.length === 0 || !recessionData || recessionData.length === 0) return [];

        // Detect format: new format has 'start' and 'end' keys
        const isNewFormat = recessionData[0] && ('start' in recessionData[0] || 'end' in recessionData[0]);

        if (isNewFormat) {
            // New format: {start, end} date ranges.
            // Critical fix: Map these dates to the actual data points available in the chart.
            // Charts often use Categorical axes where exact string matches are required.
            // Also handles mismatch between Start-of-Month (USREC) and End-of-Month (LEI/COI) dates.

            const areas = [];

            recessionData.forEach(r => {
                const rStart = r.start;
                const rEnd = r.end;

                // 1. Find start index: first data point where date >= r.start
                const si = data.findIndex(d => d.date >= rStart);

                // If all data points are before the recession start, skip
                if (si === -1) return;

                // 2. Find end index: first data point where date >= r.end
                // (Using >= to ensure we capture the full month if r.end is start-of-month)
                let ei = -1;
                for (let i = si; i < data.length; i++) {
                    if (data[i].date >= rEnd) {
                        ei = i;
                        break;
                    }
                }

                // If no point is >= r.end, it means recession extends past dataset end. Snap to last point.
                if (ei === -1) ei = data.length - 1;

                // 3. Validation: Ensure the found data segment is actually relevant.
                // If the data point found for start is chronologically AFTER the recession end,
                // it implies the whole recession happened before this data point.
                if (data[si].date > rEnd) return;

                areas.push({
                    x1: data[si].date,
                    x2: data[ei].date
                });
            });

            return areas;
        } else {
            // Legacy format: {date, value} where value=1 is recession
            const recessionDates = new Set(recessionData.filter(d => d.value === 1).map(d => d.date));

            const areas = [];
            let start = null;

            data.forEach((entry, i) => {
                const isRecession = recessionDates.has(entry.date);

                if (isRecession && start === null) {
                    start = entry.date;
                } else if (!isRecession && start !== null) {
                    areas.push({ x1: start, x2: data[i - 1].date });
                    start = null;
                }
            });

            // Close last if open
            if (start !== null) {
                areas.push({ x1: start, x2: data[data.length - 1].date });
            }

            return areas;
        }
    }, [data, recessionData]);

    if (spans.length === 0) return null;

    return (
        <>
            {spans.map((span, idx) => (
                <React.Fragment key={`span-${idx}`}>
                    {/* Background Shading */}
                    <ReferenceArea
                        x1={span.x1}
                        x2={span.x2}
                        fill={color}
                        fillOpacity={opacity}
                        stroke="none"
                        isFront={false}
                    />
                    {/* Boundary Lines */}
                    <ReferenceLine
                        x={span.x1}
                        stroke={color}
                        strokeWidth={1}
                        strokeDasharray="3 3"
                        isFront={true}
                    />
                    <ReferenceLine
                        x={span.x2}
                        stroke={color}
                        strokeWidth={1}
                        strokeDasharray="3 3"
                        isFront={true}
                    />
                </React.Fragment>
            ))}
        </>
    );
};

export default RecessionOverlay;

