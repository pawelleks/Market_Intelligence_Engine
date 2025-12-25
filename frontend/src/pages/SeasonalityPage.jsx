import React, { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';

const API_BASE = "/api/v1";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_TICKS = [1, 21, 42, 63, 84, 105, 126, 147, 168, 189, 210, 231];
const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const SeasonalityPage = ({ settings, onSettingsChange }) => {
    // Local State for Seasonality-specific settings
    const [localLookbacks, setLocalLookbacks] = useState([10, 20]); // Historical curves
    const [localHeatmapLookback, setLocalHeatmapLookback] = useState(20); // Calendar grid
    const [drillDate, setDrillDate] = useState({ month: new Date().getMonth() + 1, day: new Date().getDate() });

    // Ticker List State
    const [availableTickers, setAvailableTickers] = useState([]);
    const [loadingTickers, setLoadingTickers] = useState(true);

    // Data State
    const [curvesData, setCurvesData] = useState(null);
    const [heatmapData, setHeatmapData] = useState(null);
    const [drillData, setDrillData] = useState(null);
    const [loading, setLoading] = useState(true);

    // Derived URLs (CRITICAL)
    const TICKERS_URL = `${API_BASE}/tickers/Seasonality_Analysis`;

    // --- Fetch Tickers Effect ---
    useEffect(() => {
        async function fetchTickers() {
            setLoadingTickers(true);
            try {
                const response = await fetch(TICKERS_URL);
                const json = await response.json();
                if (response.ok) {
                    setAvailableTickers(json.tickers);
                    // If current ticker is not in the allowed list, default to the first one
                    if (json.tickers.length > 0 && !json.tickers.includes(settings.ticker)) {
                        onSettingsChange({ ...settings, ticker: json.tickers[0] });
                    }
                }
            } catch (error) {
                console.error("Failed to fetch seasonality tickers:", error);
                setAvailableTickers(['SPY', 'QQQ']); // Fallback
            } finally {
                setLoadingTickers(false);
            }
        }
        fetchTickers();
    }, []);

    // --- Data Fetching Effect ---
    useEffect(() => {
        if (!settings.ticker) return;

        const controller = new AbortController();
        const signal = controller.signal;

        const fetchAllData = async () => {
            setLoading(true);
            try {
                // Define URLs inside to guarantee freshness and correct state usage
                const LOOKBACK_STRING = localLookbacks.join(',');
                const CURVES_URL = `${API_BASE}/seasonality/curves/${settings.ticker}?lookbacks=${LOOKBACK_STRING}`;
                const HEATMAP_URL = `${API_BASE}/seasonality/heatmap/${settings.ticker}?lookback=${localHeatmapLookback}`;
                const DRILLDOWN_URL = `${API_BASE}/seasonality/drilldown/${settings.ticker}/${drillDate.month}/${drillDate.day}?lookback=${localHeatmapLookback}`;

                console.log(`Fetching Seasonality Data for ${settings.ticker}...`);

                const [curvesRes, heatmapRes, drillRes] = await Promise.all([
                    fetch(CURVES_URL, { signal, cache: 'no-store' }).then(r => r.json()),
                    fetch(HEATMAP_URL, { signal, cache: 'no-store' }).then(r => r.json()),
                    fetch(DRILLDOWN_URL, { signal, cache: 'no-store' }).then(r => r.json())
                ]);

                if (!signal.aborted) {
                    setCurvesData(curvesRes.data || curvesRes);
                    setHeatmapData(heatmapRes.data || heatmapRes);
                    setDrillData(drillRes.data || drillRes);
                }
            } catch (err) {
                if (err.name !== 'AbortError') {
                    console.error("Seasonality Fetch Failed:", err);
                }
            } finally {
                if (!signal.aborted) setLoading(false);
            }
        };

        fetchAllData();

        return () => controller.abort();
    }, [settings.ticker, localLookbacks, localHeatmapLookback, drillDate]); // Dependencies

    // --- Helpers ---
    const getHeatmapCellColor = (val) => {
        if (val === null || val === undefined) return '#1e2837'; // Empty
        // Color scale: Red (-1%) <-> Black (0%) <-> Green (+1%)
        if (val > 0) {
            const intensity = Math.min(1, val / 1.0); // Cap at 1%
            return `rgba(76, 175, 80, ${0.3 + intensity * 0.7})`;
        } else {
            const intensity = Math.min(1, Math.abs(val) / 1.0);
            return `rgba(244, 67, 54, ${0.3 + intensity * 0.7})`;
        }
    };

    return (
        <div style={{ display: 'flex', gap: '20px', padding: '20px', width: '100%' }}>
            {/* LEFT PANEL: CONFIG */}
            <div style={{ width: '250px', flexShrink: 0 }}>
                <div style={{ padding: '15px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049' }}>
                    <h4 style={{ margin: '0 0 15px 0', color: '#9ec4ff' }}>Config</h4>

                    {/* Ticker Selector (Dynamic) */}
                    <div style={{ marginBottom: '15px' }}>
                        <label style={{ display: 'block', color: '#9e9e9e', fontSize: '12px' }}>Ticker</label>
                        {loadingTickers ? (
                            <span style={{ fontSize: '12px', color: '#6c757d' }}>Loading...</span>
                        ) : (
                            <select
                                value={settings.ticker}
                                onChange={(e) => onSettingsChange({ ...settings, ticker: e.target.value })}
                                style={{ width: '100%', padding: '8px', background: '#0b1220', color: '#d7e3f3', border: '1px solid #203049', borderRadius: '4px' }}
                            >
                                {availableTickers.map(t => (
                                    <option key={t} value={t}>{t}</option>
                                ))}
                            </select>
                        )}
                    </div>

                    <div style={{ marginBottom: '15px' }}>
                        <label style={{ display: 'block', color: '#9e9e9e', fontSize: '12px' }}>Heatmap Lookback (Years)</label>
                        <select
                            value={localHeatmapLookback}
                            onChange={(e) => setLocalHeatmapLookback(parseInt(e.target.value))}
                            style={{ width: '100%', padding: '8px', background: '#0b1220', color: '#d7e3f3', border: '1px solid #203049', borderRadius: '4px' }}
                        >
                            <option value="5">5 Years</option>
                            <option value="10">10 Years</option>
                            <option value="20">20 Years</option>
                            <option value="50">50 Years</option>
                        </select>
                    </div>
                </div>

                {/* Last Data Date Display */}
                {curvesData && curvesData.current_path && curvesData.current_path.data.length > 0 && (
                    <div style={{ marginTop: '20px', padding: '10px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049' }}>
                        <label style={{ display: 'block', color: '#9e9e9e', fontSize: '12px' }}>Analysis based on data up to:</label>
                        <div style={{ color: '#4caf50', fontWeight: 'bold', fontSize: '14px', marginTop: '4px' }}>
                            {curvesData.current_path.data[curvesData.current_path.data.length - 1].date || "Unknown"}
                        </div>
                    </div>
                )}
            </div>

            {/* RIGHT PANEL: VISUALIZATION */}
            <div style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: '20px' }}>

                {/* 1. CURVES CHART */}
                <div style={{ padding: '20px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049' }}>
                    <h3 style={{ marginTop: 0 }}>Seasonality vs Actual: {settings.ticker}</h3>
                    {loading && <p style={{ color: '#9ec4ff' }}>Loading data...</p>}

                    {curvesData && curvesData.curves ? (
                        <Plot
                            data={[
                                // Historical Curves (Ghosts)
                                ...curvesData.curves.map(c => ({
                                    x: c.data.map(d => d.tdoy),
                                    y: c.data.reduce((acc, curr) => {
                                        const last = acc.length > 0 ? acc[acc.length - 1] : 0;
                                        acc.push(last + curr.r);
                                        return acc;
                                    }, []),
                                    type: 'scatter',
                                    mode: 'lines',
                                    name: c.label,
                                    line: { dash: 'dot', width: 2 },
                                    opacity: 0.6
                                })),
                                // Current Year (Bold)
                                {
                                    x: curvesData.current_path.data.map(d => d.tdoy),
                                    y: curvesData.current_path.data.reduce((acc, curr) => {
                                        const last = acc.length > 0 ? acc[acc.length - 1] : 0;
                                        acc.push(last + curr.r);
                                        return acc;
                                    }, []),
                                    type: 'scatter',
                                    mode: 'lines',
                                    name: curvesData.current_path.label,
                                    line: { color: '#ffffff', width: 3 }
                                }
                            ]}
                            layout={{
                                autosize: true,
                                height: 400,
                                plot_bgcolor: '#0e1525',
                                paper_bgcolor: '#0e1525',
                                font: { color: '#d7e3f3' },
                                xaxis: {
                                    title: 'Month',
                                    gridcolor: '#203049',
                                    tickmode: 'array',
                                    tickvals: MONTH_TICKS,
                                    ticktext: MONTH_LABELS
                                },
                                yaxis: {
                                    title: 'Cumulative Return (%)',
                                    gridcolor: '#203049',
                                    tickformat: '.1%',
                                },
                                margin: { t: 10, r: 10, l: 40, b: 40 },
                                legend: { orientation: 'h', y: 1.1 }
                            }}
                            style={{ width: '100%' }}
                            config={{ responsive: true, displayModeBar: false }}
                        />
                    ) : (!loading && <p>No curve data available.</p>)}
                </div>

                {/* 2. CALENDAR HEATMAP */}
                <div style={{ padding: '20px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049' }}>
                    <h3 style={{ marginTop: 0 }}>Seasonality Calendar ({localHeatmapLookback}-Year Avg)</h3>
                    {heatmapData ? (
                        <div style={{ display: 'grid', gridTemplateColumns: '50px repeat(31, 1fr)', gap: '2px', fontSize: '10px' }}>
                            {/* Header Row: Days */}
                            <div></div> {/* Corner */}
                            {Array.from({ length: 31 }, (_, i) => (
                                <div key={i} style={{ textAlign: 'center', color: '#9e9e9e' }}>{i + 1}</div>
                            ))}

                            {/* Rows: Months */}
                            {MONTHS.map((mName, mIdx) => (
                                <React.Fragment key={mIdx}>
                                    <div style={{ alignSelf: 'center', color: '#9e9e9e' }}>{mName}</div>
                                    {Array.from({ length: 31 }, (_, dIdx) => {
                                        const cell = heatmapData?.heatmap?.find(h => h.month === mIdx + 1 && h.day === dIdx + 1);
                                        const val = cell ? cell.value : null;
                                        return (
                                            <div
                                                key={dIdx}
                                                onClick={() => val !== null && setDrillDate({ month: mIdx + 1, day: dIdx + 1 })}
                                                title={val !== null ? `${mName} ${dIdx + 1}: ${val}%` : 'N/A'}
                                                style={{
                                                    height: '25px',
                                                    backgroundColor: getHeatmapCellColor(val),
                                                    borderRadius: '2px',
                                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                    cursor: val !== null ? 'pointer' : 'default',
                                                    border: (drillDate.month === mIdx + 1 && drillDate.day === dIdx + 1) ? '1px solid white' : 'none'
                                                }}
                                            >
                                                {val !== null ? val.toFixed(2) : ''}
                                            </div>
                                        );
                                    })}
                                </React.Fragment>
                            ))}
                        </div>
                    ) : (!loading && <p>No heatmap data available.</p>)}
                </div>

                {/* 3. DRILL DOWN */}
                {drillData && (
                    <div style={{ padding: '20px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #203049' }}>
                        <h3 style={{ marginTop: 0 }}>Drill Down: {MONTHS[drillData.month - 1]} {drillData.day} (Last {localHeatmapLookback} Years)</h3>

                        {/* Drill-down Bar Chart (NEW) */}
                        <h4 style={{ color: '#9ec4ff', marginTop: '15px', marginBottom: '10px' }}>Historical Daily Returns</h4>
                        <div style={{ display: 'flex', justifyContent: 'center' }}>
                            <div style={{ width: '70%', margin: '0 auto 20px auto', padding: '15px', border: '1px solid #203049', borderRadius: '8px', backgroundColor: '#0e1525' }}>
                                <Plot
                                    data={[{
                                        x: drillData.records.map(r => r.year),
                                        y: drillData.records.map(r => r.r_pct / 100),
                                        type: 'bar',
                                        marker: {
                                            color: drillData.records.map(r => r.r_pct > 0 ? '#4caf50' : '#f44336')
                                        },
                                        hovertemplate: 'Year: %{x}<br>Return: %{y:.2%}<extra></extra>',
                                    }]}
                                    layout={{
                                        autosize: true,
                                        height: 350,
                                        plot_bgcolor: '#0e1525',
                                        paper_bgcolor: '#0e1525',
                                        font: { color: '#d7e3f3' },
                                        xaxis: { title: 'Year', gridcolor: '#203049' },
                                        yaxis: { title: 'Return %', tickformat: '.1%', gridcolor: '#203049', zerolinecolor: '#d7e3f3' },
                                        margin: { t: 5, b: 40, l: 40, r: 10 }
                                    }}
                                    config={{ responsive: true, displayModeBar: false }}
                                />
                            </div>
                        </div>

                        <div style={{ display: 'flex', gap: '20px', marginBottom: '20px', padding: '10px', backgroundColor: '#1e2837', borderRadius: '8px' }}>
                            <div style={{ color: '#9e9e9e' }}>Win Rate: <span style={{ color: drillData.stats.win_rate > 50 ? '#4caf50' : '#f44336', fontWeight: 'bold' }}>{drillData.stats.win_rate.toFixed(1)}%</span></div>
                            <div style={{ color: '#9e9e9e' }}>Avg Return: <span style={{ color: drillData.stats.mean > 0 ? '#4caf50' : '#f44336', fontWeight: 'bold' }}>{drillData.stats.mean.toFixed(2)}%</span></div>
                            <div style={{ color: '#9e9e9e' }}>Total Samples: <span style={{ fontWeight: 'bold' }}>{drillData.stats.count}</span></div>
                        </div>

                        <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                                <thead>
                                    <tr style={{ textAlign: 'left', borderBottom: '1px solid #203049', color: '#9e9e9e' }}>
                                        <th style={{ padding: '8px' }}>Year</th>
                                        <th style={{ padding: '8px' }}>Date</th>
                                        <th style={{ padding: '8px' }}>Close</th>
                                        <th style={{ padding: '8px' }}>Return %</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {drillData.records.map(rec => (
                                        <tr key={rec.year} style={{ borderBottom: '1px solid #1e2837' }}>
                                            <td style={{ padding: '8px' }}>{rec.year}</td>
                                            <td style={{ padding: '8px', color: '#9e9e9e' }}>{rec.date}</td>
                                            <td style={{ padding: '8px' }}>{rec.close ? rec.close.toFixed(2) : 'N/A'}</td>
                                            <td style={{ padding: '8px', color: rec.r_pct > 0 ? '#4caf50' : '#f44336' }}>
                                                {rec.r_pct !== null && rec.r_pct !== undefined ? (rec.r_pct > 0 ? '+' : '') + rec.r_pct.toFixed(2) + '%' : 'N/A'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

            </div>
        </div>
    );
};

export default SeasonalityPage;
