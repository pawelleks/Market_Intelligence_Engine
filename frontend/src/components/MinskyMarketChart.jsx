import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
    ResponsiveContainer,
    ComposedChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ReferenceArea, Brush
} from 'recharts';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const MinskyMarketChart = () => {
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const res = await axios.get(`${API_BASE_URL}/minsky-market-data`);
                const { dates, indicators } = res.data;

                if (!dates || !indicators) throw new Error("Invalid data format");

                // Transform Columnar to Row-based for Recharts
                const transformed = dates.map((date, i) => {
                    const row = { date };
                    Object.keys(indicators).forEach(key => {
                        row[key] = indicators[key][i];
                    });
                    return row;
                });

                setData(transformed);
            } catch (err) {
                console.error("Market Data Fetch Error:", err);
                // Don't show critical error on dashboard if just this chart fails, but handle state
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    if (loading) return <div style={{ color: '#6b7280', padding: '20px', textAlign: 'center' }}>Loading Market Validation...</div>;
    if (error) return null; // Hide if fails, or show error? Let's hide to be safe or minimal.
    if (data.length === 0) return null;

    // Helper to find Recession Areas (USREC == 1)
    const getReferenceAreas = (dataKey, conditionVal, color) => {
        const areas = [];
        let start = null;

        data.forEach((entry, i) => {
            const val = entry[dataKey];
            if (val === conditionVal && start === null) {
                start = entry.date;
            } else if (val !== conditionVal && start !== null) {
                areas.push({ x1: start, x2: data[i - 1].date, color });
                start = null;
            }
        });
        // Close last if open
        if (start !== null) areas.push({ x1: start, x2: data[data.length - 1].date, color });

        return areas;
    };

    // Helper for Regimes
    // Regime logic is already in 'minsky_regime' column: Ponzi, Speculative, Hedge
    const getRegimeAreas = () => {
        const areas = [];
        let start = null;
        let currentRegime = null;

        data.forEach((entry, i) => {
            const r = entry.minsky_regime;
            // We only care about coloring Ponzi (#ef4444) and Speculative (#f97316)
            // Hedge is transparent

            if (r !== currentRegime) {
                // Close previous if needed
                if (start !== null && (currentRegime === 'Ponzi' || currentRegime === 'Speculative')) {
                    const color = currentRegime === 'Ponzi' ? '#ef4444' : '#f97316';
                    const opacity = currentRegime === 'Ponzi' ? 0.15 : 0.1;
                    areas.push({ x1: start, x2: data[i - 1].date, color, opacity });
                }

                // Start new
                start = entry.date;
                currentRegime = r;
            }
        });

        // Close final
        if (start !== null && (currentRegime === 'Ponzi' || currentRegime === 'Speculative')) {
            const color = currentRegime === 'Ponzi' ? '#ef4444' : '#f97316';
            const opacity = currentRegime === 'Ponzi' ? 0.15 : 0.1;
            areas.push({ x1: start, x2: data[data.length - 1].date, color, opacity });
        }

        return areas;
    };

    const recessionAreas = getReferenceAreas('USREC', 1, '#374151');
    const regimeAreas = getRegimeAreas();

    const formatYear = ((tick) => tick ? tick.substring(0, 4) : '');

    return (
        <section style={{ marginTop: '48px' }}>
            <div style={{ marginBottom: '16px' }}>
                <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#fff', margin: 0 }}>4. Market Correlation (Model Validation)</h2>
                <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px' }}>
                    S&P 500 overlaid with <span style={{ color: '#9ca3af' }}>Recessions (Gray Bars)</span> and Minsky Stress Regimes (<span style={{ color: '#ef4444' }}>Red = Ponzi</span>, <span style={{ color: '#f97316' }}>Orange = Speculative</span>, Transparent = Stable).
                </p>
            </div>

            <div style={{ height: '400px', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', padding: '16px', border: '1px solid rgba(55, 65, 81, 0.5)' }}>
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                        <XAxis
                            dataKey="date"
                            tickFormatter={(tick) => {
                                if (!tick) return '';
                                // Robustly extract year whether tick is timestamp or string
                                const str = String(tick);
                                return str.substring(0, 4);
                            }}
                            stroke="#9CA3AF"
                            fontSize={12}
                            minTickGap={50}
                        />
                        <YAxis domain={['auto', 'auto']} stroke="#9CA3AF" fontSize={12} />

                        {/* Hidden Axis for Heat Strip (0 to 1) */}
                        <YAxis yAxisId="heatstrip" domain={[0, 1]} hide />

                        <Tooltip
                            contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', color: '#f3f4f6' }}
                            labelStyle={{ color: '#9ca3af' }}
                            formatter={(value, name, props) => {
                                if (name === "S&P 500") return [value ? value.toFixed(2) : 'N/A', name];
                                return [value, name];
                            }}
                        />
                        <Legend />

                        {/* Layer 1: Recessions (Full Height - Main Axis) */}
                        {recessionAreas.map((area, idx) => (
                            <ReferenceArea key={`rec-${idx}`} x1={area.x1} x2={area.x2} fill={area.color} fillOpacity={0.5} />
                        ))}

                        {/* Layer 2: Minsky Signals (Full Height Overlay) */}
                        {regimeAreas.map((area, idx) => (
                            <ReferenceArea
                                key={`reg-${idx}`}
                                x1={area.x1}
                                x2={area.x2}
                                fill={area.color}
                                fillOpacity={area.opacity}
                            />
                        ))}

                        {/* Layer 3: Price Line (Main Axis) */}
                        <Line
                            type="monotone"
                            dataKey="SP500"
                            name="S&P 500"
                            stroke="#f3f4f6"
                            dot={false}
                            strokeWidth={2}
                        />

                        {/* Fix A: Zoom with Brush */}
                        <Brush
                            dataKey="date"
                            height={30}
                            stroke="#8884d8"
                            tickFormatter={(tick) => tick ? tick.substring(0, 4) : ''}
                            alwaysShowText={false}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </section>
    );
};

export default MinskyMarketChart;
