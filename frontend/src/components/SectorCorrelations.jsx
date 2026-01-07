import React, { useState, useEffect } from 'react';

const SectorCorrelations = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [mode, setMode] = useState('calendar'); // 'calendar' or 'rolling'

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await fetch('/api/v1/performance/correlation');
                if (res.ok) {
                    const json = await res.json();
                    setData(json);
                }
            } catch (err) {
                console.error("Error fetching correlations:", err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return <div style={{ color: '#888', padding: '20px' }}>Loading correlation data...</div>;
    if (!data) return <div style={{ color: '#888', padding: '20px' }}>No correlation data available.</div>;

    const matrixData = mode === 'calendar' ? data.calendar_year : data.rolling_12m;
    const title = mode === 'calendar'
        ? `Correlation Matrix: Last Calendar Year (${data.year_label})`
        : 'Correlation Matrix: Rolling 12 Months';

    if (!matrixData || !matrixData.tickers || matrixData.tickers.length === 0) {
        return <div style={{ color: '#888', padding: '20px' }}>No data for selected period.</div>;
    }

    const { tickers, matrix } = matrixData;

    // Color Scale: Red (-1) <-> Yellow (0) <-> Green (1)
    const getCellStyle = (value) => {
        // Diagonal
        if (value > 0.999) return { backgroundColor: '#1b5e20', color: '#fff', fontWeight: 'bold' };

        let r, g, b;

        // Value range -1 to 1
        if (value >= 0) {
            // 0 -> 1: Yellow (255,255,0) -> Green (0,200,0)
            // Keeping it slightly darker green for readability against white text? 
            // Or use Black text on bright colors.
            // Let's go:
            // 0: 200, 200, 50 (Dark Yellow)
            // 1: 0, 150, 0 (Dark Green)

            // Actually, for "Green to Red" request, usually standard bright colors are expected.
            // Let's use semi-transparent background to blend with dark theme?
            // No, user wants color scale.

            // Linear Interpolation
            // 0 (Yellow): 255, 235, 59
            // 1 (Green): 76, 175, 80

            const ratio = value;
            r = Math.round(255 * (1 - ratio) + 76 * ratio);
            g = Math.round(235 * (1 - ratio) + 175 * ratio);
            b = Math.round(59 * (1 - ratio) + 80 * ratio);

        } else {
            // -1 -> 0: Red (244, 67, 54) -> Yellow (255, 235, 59)
            // -1 is Red. 0 is Yellow.
            // ratio: 0 (at -1) to 1 (at 0)?
            // Let's Normalize negative val:
            // ratio = 1 - abs(val). 
            // If val = -1, ratio = 0. (Pure Red)
            // If val = 0, ratio = 1. (Pure Yellow)

            const ratio = 1 - Math.abs(value);
            // Red: 244, 67, 54
            // Yellow: 255, 235, 59

            r = Math.round(244 * (1 - ratio) + 255 * ratio);
            g = Math.round(67 * (1 - ratio) + 235 * ratio);
            b = Math.round(54 * (1 - ratio) + 59 * ratio);
        }

        // Text Color: Black for better contrast on bright colors?
        // These colors are quite bright.
        return {
            backgroundColor: `rgb(${r}, ${g}, ${b})`,
            color: '#111',
            fontWeight: Math.abs(value) > 0.5 ? 'bold' : 'normal'
        };
    };

    return (
        <div style={{ padding: '20px' }}>
            {/* Controls */}
            <div style={{ marginBottom: '20px', display: 'flex', gap: '10px' }}>
                <button
                    onClick={() => setMode('calendar')}
                    style={{
                        padding: '8px 16px',
                        backgroundColor: mode === 'calendar' ? '#4CAF50' : '#1e293b',
                        color: mode === 'calendar' ? '#fff' : '#888',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer'
                    }}
                >
                    Last Calendar Year ({data.year_label})
                </button>
                <button
                    onClick={() => setMode('rolling')}
                    style={{
                        padding: '8px 16px',
                        backgroundColor: mode === 'rolling' ? '#4CAF50' : '#1e293b',
                        color: mode === 'rolling' ? '#fff' : '#888',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer'
                    }}
                >
                    Rolling 12 Months
                </button>
            </div>

            <h3 style={{ color: '#e0e0e0', fontSize: '16px', marginBottom: '20px' }}>{title}</h3>

            <div style={{ overflowX: 'auto' }}>
                <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '13px' }}>
                    <thead>
                        <tr>
                            <th style={{ padding: '10px', textAlign: 'left', color: '#888' }}></th>
                            {tickers.map(t => (
                                <th key={t} style={{ padding: '10px', color: '#d7e3f3', borderBottom: '1px solid #333' }}>{t}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {matrix.map((row, i) => (
                            <tr key={tickers[i]}>
                                <td style={{ padding: '10px', color: '#d7e3f3', fontWeight: 'bold', borderRight: '1px solid #333' }}>
                                    {tickers[i]}
                                </td>
                                {row.map((val, j) => {
                                    const style = getCellStyle(val);
                                    return (
                                        <td key={j} style={{
                                            padding: '12px',
                                            textAlign: 'center',
                                            backgroundColor: style.backgroundColor,
                                            color: style.color,
                                            border: '1px solid #0b1220'
                                        }}>
                                            {val.toFixed(2)}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default SectorCorrelations;
