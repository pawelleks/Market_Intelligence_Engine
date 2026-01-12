import React, { useState, useEffect, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';

const MacroLab = () => {
    const [activeTab, setActiveTab] = useState('LEI');
    const [weights, setWeights] = useState({});
    const [experimentalData, setExperimentalData] = useState([]);
    const [referenceData, setReferenceData] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // --- Configuration ---
    const CONFIG = {
        LEI: {
            title: "Leading Economic Index",
            components: [
                { key: 'z_spread_10y2y', name: '10Y-2Y Spread', default: 0.30, color: '#60a5fa' },
                { key: 'z_spread_10y3m', name: '10Y-3M Spread', default: 0.20, color: '#818cf8' },
                { key: 'z_permit', name: 'Housing Permits', default: 0.20, color: '#22c55e' },
                { key: 'z_orders', name: 'New Orders', default: 0.15, color: '#fbbf24' },
                { key: 'z_hours', name: 'Weekly Hours', default: 0.05, color: '#fca5a5' },
                { key: 'z_claims', name: 'Jobless Claims', default: 0.05, color: '#ef4444' },
                { key: 'z_sentiment', name: 'Consumer Sent.', default: 0.05, color: '#f472b6' },
            ],
            referenceEndpoint: '/api/macro/lei-index'
        },
        COI: {
            title: "Coincident Index",
            components: [
                { key: 'z_indpro', name: 'Ind. Production', default: 0.35, color: '#a78bfa' },
                { key: 'z_payrolls', name: 'NFP Payrolls', default: 0.35, color: '#34d399' },
                { key: 'z_income', name: 'Real Income', default: 0.15, color: '#60a5fa' },
                { key: 'z_sales', name: 'Retail Sales', default: 0.075, color: '#fbbf24' },
                { key: 'z_gdp', name: 'Real GDP', default: 0.075, color: '#f472b6' },
            ],
            referenceEndpoint: '/api/macro/coi-index' // Assuming exists? Fallback if not
        },
        LAG: {
            title: "Lagging Index",
            components: [
                { key: 'z_cpi_services', name: 'CPI Services', default: 0.30, color: '#ef4444' },
                { key: 'z_unrate', name: 'Unemployment', default: 0.20, color: '#60a5fa' },
                { key: 'z_labor_cost', name: 'Labor Costs', default: 0.20, color: '#fbbf24' },
                { key: 'z_yield_10y', name: '10Y Yield', default: 0.20, color: '#818cf8' },
                { key: 'z_credit', name: 'Comm. Credit', default: 0.10, color: '#34d399' },
            ],
            referenceEndpoint: '/api/macro/lag-index' // Assuming exists?
        }
    };

    // --- Initialization ---
    useEffect(() => {
        // Reset Weights on Tab Switch
        const defaults = {};
        CONFIG[activeTab].components.forEach(c => {
            defaults[c.key] = c.default * 100; // Store as 0-100 for slider
        });
        setWeights(defaults);

        // Load Reference Data
        const fetchRef = async () => {
            // For now only LEI reference is guaranteed to match the exact keys expected? 
            // Actually index endpoints usually return {data: [{date, value...}]}
            // Let's protect against missing endpoints
            try {
                const res = await fetch(CONFIG[activeTab].referenceEndpoint);
                if (res.ok) {
                    const json = await res.json();
                    setReferenceData(json.data || []);
                } else {
                    setReferenceData([]);
                }
            } catch (e) {
                setReferenceData([]);
            }
        };
        fetchRef();
        setExperimentalData([]); // Clear old experiment
    }, [activeTab]);

    // --- Handlers ---
    const handleWeightChange = (key, val) => {
        setWeights(prev => ({ ...prev, [key]: parseFloat(val) }));
    };

    const runSimulation = async () => {
        setLoading(true);
        setError(null);
        try {
            // Convert 0-100 to 0-1.0
            const apiWeights = {};
            Object.keys(weights).forEach(k => apiWeights[k] = weights[k] / 100.0);

            const res = await fetch('/api/macro/lab/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    index_type: activeTab,
                    weights: apiWeights
                })
            });

            if (!res.ok) throw new Error("Simulation Failed");

            const json = await res.json();
            setExperimentalData(json.data || []);

        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // --- Derived ---
    const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);
    const weightColor = Math.abs(totalWeight - 100) < 0.1 ? '#22c55e' : '#ef4444';

    // Merge Data for Chart
    const chartData = useMemo(() => {
        // Map Experimental Date -> Value
        const expMap = new Map();
        experimentalData.forEach(d => expMap.set(d.date, d.value));

        // Map Reference Date -> Value (Need to know the key: 'lei_composite' etc)
        // Usually Reference API returns specific keys.
        // LEI: lei_composite. COI: coi_composite?
        const getRefVal = (row) => {
            if (activeTab === 'LEI') return row.lei_composite;
            if (activeTab === 'COI') return row.coi_composite;
            if (activeTab === 'LAG') return row.lag_composite;
            return null;
        };

        // Combine Keys
        const allDates = new Set([...expMap.keys(), ...referenceData.map(d => d.date)]);
        const combined = Array.from(allDates).sort().map(date => {
            const refRow = referenceData.find(d => d.date === date);
            return {
                date,
                Experimental: expMap.get(date) || null,
                Reference: refRow ? getRefVal(refRow) : null
            };
        });

        // Filter out ancient history if we want
        return combined.filter(d => d.date >= '1970-01-01');

    }, [experimentalData, referenceData, activeTab]);

    return (
        <div style={{ padding: '20px', backgroundColor: '#0b1220', minHeight: '100vh', color: '#e5e7eb', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid #1f2937', paddingBottom: '15px' }}>
                <h1 style={{ fontSize: '24px', fontWeight: 'bold', margin: 0 }}>Macro Lab Sandbox</h1>
                <div style={{ display: 'flex', gap: '10px' }}>
                    {['LEI', 'COI', 'LAG'].map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            style={{
                                padding: '8px 16px',
                                borderRadius: '6px',
                                backgroundColor: activeTab === tab ? '#3b82f6' : '#1f2937',
                                color: activeTab === tab ? 'white' : '#9ca3af',
                                border: 'none',
                                cursor: 'pointer',
                                fontWeight: 'bold'
                            }}
                        >
                            {tab} Experiment
                        </button>
                    ))}
                </div>
            </div>

            <div style={{ display: 'flex', gap: '20px', flexGrow: 1 }}>

                {/* --- Sidebar Controls --- */}
                <div style={{ width: '320px', backgroundColor: '#111827', borderRadius: '8px', padding: '20px', border: '1px solid #1f2937', display: 'flex', flexDirection: 'column' }}>
                    <h2 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '15px', color: '#9ca3af' }}>{CONFIG[activeTab].title} Weights</h2>

                    <div style={{ flexGrow: 1, overflowY: 'auto', paddingRight: '5px' }}>
                        {CONFIG[activeTab].components.map(comp => (
                            <div key={comp.key} style={{ marginBottom: '20px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                                    <span style={{ fontSize: '14px', color: comp.color }}>{comp.name}</span>
                                    <span style={{ fontSize: '14px', fontWeight: 'bold' }}>{weights[comp.key] || 0}%</span>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max="100"
                                    step="1"
                                    value={weights[comp.key] || 0}
                                    onChange={(e) => handleWeightChange(comp.key, e.target.value)}
                                    style={{ width: '100%', accentColor: comp.color }}
                                />
                            </div>
                        ))}
                    </div>

                    <div style={{ marginTop: '20px', borderTop: '1px solid #374151', paddingTop: '15px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px', fontWeight: 'bold' }}>
                            <span>Total Allocation:</span>
                            <span style={{ color: weightColor }}>{totalWeight.toFixed(1)}%</span>
                        </div>
                        <button
                            onClick={runSimulation}
                            disabled={loading}
                            style={{
                                width: '100%',
                                padding: '12px',
                                backgroundColor: loading ? '#4b5563' : '#2563eb',
                                color: 'white',
                                border: 'none',
                                borderRadius: '6px',
                                cursor: loading ? 'not-allowed' : 'pointer',
                                fontWeight: 'bold',
                                fontSize: '16px'
                            }}
                        >
                            {loading ? 'Simulating...' : 'Run Simulation'}
                        </button>
                        {error && <p style={{ color: '#ef4444', fontSize: '12px', marginTop: '10px' }}>{error}</p>}
                    </div>
                </div>

                {/* --- Main Chart --- */}
                <div style={{ flexGrow: 1, backgroundColor: '#111827', borderRadius: '8px', padding: '20px', border: '1px solid #1f2937', minHeight: '500px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                            <XAxis
                                dataKey="date"
                                stroke="#9ca3af"
                                tick={{ fontSize: 12 }}
                                tickFormatter={(str) => str.slice(0, 4)}
                                minTickGap={50}
                            />
                            <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} domain={['auto', 'auto']} />
                            <Tooltip
                                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
                                labelStyle={{ color: '#e5e7eb' }}
                            />
                            <Legend wrapperStyle={{ paddingTop: '10px' }} />
                            <ReferenceLine y={0} stroke="#6b7280" />

                            {/* Reference Model */}
                            <Line
                                type="monotone"
                                dataKey="Reference"
                                stroke="#6b7280"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                dot={false}
                                name="Production Model (Ref)"
                            />

                            {/* Experimental Model */}
                            <Line
                                type="monotone"
                                dataKey="Experimental"
                                stroke="#3b82f6"
                                strokeWidth={3}
                                dot={false}
                                name="Experimental Model"
                                animationDuration={500}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>

            </div>
        </div>
    );
};

export default MacroLab;
