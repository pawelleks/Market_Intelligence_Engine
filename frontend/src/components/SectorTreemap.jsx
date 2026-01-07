import React, { useState, useEffect } from 'react';
import { ResponsiveContainer, Treemap, Tooltip } from 'recharts';

// Approximate S&P 500 Sector Weights (Static for visual approximation)
const SECTOR_WEIGHTS = {
    'XLK': 31.0,  // Technology
    'XLF': 13.0,  // Financials
    'XLV': 12.0,  // Healthcare
    'XLY': 10.0,  // Consumer Cyclical
    'XLC': 9.0,   // Communication Services
    'XLI': 8.5,   // Industrials
    'XLP': 6.0,   // Consumer Defensive
    'XLE': 4.0,   // Energy
    'XLB': 2.5,   // Basic Materials
    'XLRE': 2.5,  // Real Estate
    'XLU': 2.5    // Utilities
};

const TIME_PERIODS = [
    { id: 'ret_1d', label: '1 Day' },
    { id: 'ret_1w', label: '1 Week' },
    { id: 'ret_1m', label: '1 Month' },
    { id: 'ret_3m', label: '3 Months' },
    { id: 'ret_6m', label: '6 Months' },
    { id: 'ret_ytd', label: 'YTD' },
    { id: 'ret_1y', label: '1 Year' },
];

const COLORS = {
    'Technology': '#10b981', // Emerald
    'Financials': '#3b82f6', // Blue
    'Healthcare': '#ef4444', // Red (example)
    // Actually we want dynamic coloring based on return, not sector identity.
};

// Custom Content for Treemap Node
// Custom Content for Treemap Node
const CustomizedContent = (props) => {
    // Recharts passes properties including x, y, width, height, name.
    // 'payload' typically matches the data object.
    const { x, y, width, height, index, name } = props;

    // Safety check for size
    if (!width || !height || width < 5 || height < 5) return null;

    const item = props.payload || {};
    // Fallback fill if not found
    const fill = item.fill || props.fill || '#334155';
    const returnVal = item.returnVal;

    // Don't render the Root node (Market) with a color if it doesn't have one
    if (name === 'Market') return null; // Or render a border? Recharts handles root depth automatically usually.

    return (
        <g>
            <rect
                x={x}
                y={y}
                width={width}
                height={height}
                fill={fill}
                stroke="#0f172a"
                strokeWidth={2}
            />
            <foreignObject x={x} y={y} width={width} height={height} style={{ pointerEvents: 'none' }}>
                <div style={{
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    padding: '2px',
                    overflow: 'hidden',
                    color: '#fff',
                    fontWeight: 'bold',
                    textShadow: '0px 1px 3px rgba(0,0,0,0.8)',
                    textAlign: 'center'
                }}>
                    <span style={{ fontSize: '13px' }}>
                        {name}
                        {returnVal !== undefined && returnVal !== null && (
                            <span style={{ fontSize: '12px', marginLeft: '4px', fontWeight: 'normal', opacity: 0.9 }}>
                                {(returnVal * 100).toFixed(2)}%
                            </span>
                        )}
                    </span>
                </div>
            </foreignObject>
        </g>
    );
};

const getReturnColor = (val) => {
    if (val === null || val === undefined) return '#334155';
    // Green -> Red scale
    if (val >= 0.03) return '#1b5e20'; // Strong Green > 3%
    if (val >= 0.01) return '#2e7d32'; // Med Green > 1%
    if (val >= 0) return '#4caf50';    // Light Green > 0%
    if (val <= -0.03) return '#b71c1c'; // Strong Red < -3%
    if (val <= -0.01) return '#c62828'; // Med Red < -1%
    return '#ef5350';                   // Light Red < 0%
};

const SectorTreemap = () => {
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [period, setPeriod] = useState('ret_1d'); // Default 1 Day

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await fetch('/api/v1/performance/snapshot');
                if (res.ok) {
                    const json = await res.json();
                    setData(json);
                }
            } catch (err) {
                console.error("Error fetching performance snapshot:", err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return <div style={{ color: '#888', padding: '20px' }}>Loading...</div>;
    if (!data || data.length === 0) return <div style={{ color: '#888', padding: '20px' }}>No data available.</div>;

    // Filter only Sector ETFs and enrich with Weight
    const sectorData = data
        .filter(row => SECTOR_WEIGHTS[row.ticker])
        .map(row => ({
            ...row,
            weight: SECTOR_WEIGHTS[row.ticker] || 1.0,
            activeReturn: row[period]
        }))
        .sort((a, b) => b.weight - a.weight);

    // Prepare Tree Data structure for Recharts
    // Inject 'fill' directly into data objects so we can easy access it
    const treeData = [
        {
            name: 'Market',
            children: sectorData.map(s => ({
                name: s.ticker, // Use Ticker for box label
                fullName: s.name,
                size: s.weight,
                returnVal: s.activeReturn,
                fill: getReturnColor(s.activeReturn) // Pre-calculate color
            }))
        }
    ];

    // Debug: Ensure we have data
    // console.log("TreeData:", treeData);

    return (
        <div style={{ padding: '20px' }}>
            {/* Experimental Banner */}
            <div style={{ backgroundColor: 'rgba(255, 193, 7, 0.1)', border: '1px solid #ffc107', color: '#ffc107', padding: '10px', borderRadius: '4px', marginBottom: '20px', fontSize: '13px', display: 'flex', alignItems: 'center' }}>
                <span style={{ marginRight: '10px', fontSize: '18px' }}>⚠️</span>
                <span><strong>Experimental:</strong> The system does not currently contain enough data to calculate real-time S&P sector weights. Returns are accurate, but weights shown are static approximations.</span>
            </div>

            {/* Header / Controls */}
            <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ color: '#fff', margin: 0 }}>Sector Heatmap</h3>
                <div style={{ display: 'flex', gap: '5px' }}>
                    {TIME_PERIODS.map(p => (
                        <button
                            key={p.id}
                            onClick={() => setPeriod(p.id)}
                            style={{
                                padding: '6px 12px',
                                backgroundColor: period === p.id ? '#4CAF50' : '#1e293b',
                                color: period === p.id ? '#fff' : '#888',
                                border: '1px solid #334155',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '12px'
                            }}
                        >
                            {p.label}
                        </button>
                    ))}
                </div>
            </div>

            <div style={{ display: 'flex', gap: '20px', flexDirection: 'row' }}>
                {/* Visual Breakdown List (Left) */}
                <div style={{ flex: '1', minWidth: '300px', backgroundColor: '#0f172a', padding: '15px', borderRadius: '8px', border: '1px solid #1e293b' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', color: '#888', fontSize: '12px', marginBottom: '10px', paddingBottom: '5px', borderBottom: '1px solid #334155' }}>
                        <span>Sector</span>
                        <div style={{ display: 'flex', gap: '40px' }}>
                            <span>Weight</span>
                            <span>Return</span>
                        </div>
                    </div>
                    {sectorData.map(item => {
                        const ret = item.activeReturn;
                        const retColor = ret >= 0 ? '#4caf50' : '#ef5350';
                        return (
                            <div key={item.ticker} style={{ display: 'flex', alignItems: 'center', marginBottom: '12px', fontSize: '13px' }}>
                                <div style={{ flex: 1, color: '#e0e0e0', fontWeight: '500' }}>
                                    {item.name} <span style={{ color: '#666', fontSize: '11px', marginLeft: '5px' }}>{item.ticker}</span>
                                </div>
                                <div style={{ width: '80px', marginRight: '20px' }}>
                                    <div style={{ height: '6px', width: '100%', backgroundColor: '#334155', borderRadius: '3px', overflow: 'hidden' }}>
                                        <div style={{ height: '100%', width: `${(item.weight / 31) * 100}%`, backgroundColor: '#64748b' }}></div>
                                    </div>
                                    <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px', textAlign: 'right' }}>{item.weight.toFixed(2)}%</div>
                                </div>
                                <div style={{ width: '50px', textAlign: 'right', color: retColor, fontWeight: 'bold' }}>
                                    {ret ? `${(ret * 100).toFixed(2)}%` : '-'}
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Treemap (Right) */}
                <div style={{ flex: '2', height: '600px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <Treemap
                            data={treeData}
                            dataKey="size"
                            aspectRatio={4 / 3}
                            stroke="#fff"
                            fill="#8884d8"
                            content={<CustomizedContent />}
                        >
                            <Tooltip
                                content={({ active, payload }) => {
                                    if (active && payload && payload.length) {
                                        const d = payload[0].payload;
                                        return (
                                            <div style={{ backgroundColor: '#1e293b', padding: '10px', border: '1px solid #475569', color: '#fff' }}>
                                                <p style={{ margin: 0, fontWeight: 'bold' }}>{d.name}</p>
                                                <p style={{ margin: 0 }}>Weight: {d.size}%</p>
                                                <p style={{ margin: 0 }}>Return: {(d.returnVal * 100).toFixed(2)}%</p>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                        </Treemap>
                    </ResponsiveContainer>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: '5px', marginTop: '10px' }}>
                        {/* Legend / Scale if needed */}
                        <div style={{ width: '20px', height: '10px', backgroundColor: '#b71c1c' }}></div>
                        <div style={{ width: '20px', height: '10px', backgroundColor: '#c62828' }}></div>
                        <div style={{ width: '20px', height: '10px', backgroundColor: '#ef5350' }}></div>
                        <div style={{ fontSize: '11px', color: '#888', margin: '0 10px' }}>Returns</div>
                        <div style={{ width: '20px', height: '10px', backgroundColor: '#4caf50' }}></div>
                        <div style={{ width: '20px', height: '10px', backgroundColor: '#2e7d32' }}></div>
                        <div style={{ width: '20px', height: '10px', backgroundColor: '#1b5e20' }}></div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default SectorTreemap;
