import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

const API_BASE = "/api/v1/admin/data";

const PIPELINE_STEPS = [
    { id: "Ingestion", label: "Phase 1: Ingestion", steps: ["Update Raw Data", "Download Daily Options (Flat File)", "Extract Options Tickers"] },
    { id: "Features", label: "Phase 2: Features", steps: ["Update Features"] },
    { id: "Analytics", label: "Phase 3: Analytics", steps: ["Minervini Scanner", "Markov Grid", "Markov Snapshots", "HMM Grid", "Backtest HMM", "GEX", "Expected Moves", "Skew & PCR", "Seasonality", "TSMOM", "GAF", "SMA/EMA Stack", "ADX/DMI", "Ichimoku", "PSAR", "VolatilityTermStructure", "AI Context Generation"] },
    { id: "Snapshots", label: "Phase 4: Data Publishing", steps: ["Publish Analytics Data"] }
];

const StatusBadge = ({ status }) => {
    const s = (status || "UNKNOWN").toUpperCase();
    let color = '#999';
    if (s === 'COMPLETED' || s === 'SUCCESS') color = '#4caf50';
    else if (s === 'FAILED' || s === 'ERROR') color = '#f44336';
    else if (s === 'RUNNING') color = '#2196f3';
    else if (s === 'SKIPPED') color = '#ff9800';

    return <span style={{ color, fontWeight: 'bold' }}>{s}</span>;
};

import { usePageTitle } from '../hooks/usePageTitle';

const AdminDataDashboard = () => {
    usePageTitle('Admin Dashboard');
    const auth = useAuth() || {};
    const { user, token } = auth;
    console.log("AdminDashboard Mount, User:", user?.email);

    const [activeTab, setActiveTab] = useState('audit');
    const [loading, setLoading] = useState(false);
    const [ohlcData, setOhlcData] = useState([]);
    const [featuresData, setFeaturesData] = useState([]);
    const [optionsData, setOptionsData] = useState([]);
    const [emData, setEmData] = useState([]);
    const [gexData, setGexData] = useState([]);
    const [auditData, setAuditData] = useState(null);
    const [historyData, setHistoryData] = useState([]);
    const [aiContextData, setAiContextData] = useState(null);
    const [auditLoading, setAuditLoading] = useState(false);

    useEffect(() => {
        fetchAllData();
    }, []);

    // Polling for live updates
    useEffect(() => {
        let interval;
        if (auditData?.status === 'RUNNING') {
            interval = setInterval(async () => {
                try {
                    const headers = token ? { "Authorization": `Bearer ${token}` } : {};
                    const res = await fetch(`/api/v1/system/audit/latest`, { headers });
                    if (res.ok) {
                        const json = await res.json();
                        setAuditData(json);
                    }
                } catch (e) {
                    console.error("Poll error", e);
                }
            }, 5000);
        }
        return () => clearInterval(interval);
    }, [auditData, token]);

    const fetchAllData = () => {
        setLoading(true);
        const headers = token ? { "Authorization": `Bearer ${token}` } : {};

        // Independent fetches
        const fetchData = async (endpoint, setter) => {
            try {
                const res = await fetch(`${API_BASE}/${endpoint}`, { headers });
                if (res.ok) {
                    const json = await res.json();
                    // Some endpoints return {status: 'ok', data: ...}, others just list/dict
                    // Audit endpoint returns raw object
                    if (endpoint === 'audit') {
                        setter(json);
                    } else if (json.status === 'ok') {
                        setter(json.data);
                    }
                } else {
                    console.error(`Failed to fetch ${endpoint}: ${res.status}`);
                }
            } catch (err) {
                console.error(`Error fetching ${endpoint}`, err);
            }
        };

        const fetchAudit = async () => {
            try {
                const res = await fetch(`/api/v1/system/audit/latest`, { headers });
                if (res.ok) {
                    const json = await res.json();
                    setAuditData(json);
                }
            } catch (e) { console.error("Audit fetch fail", e); }
        };

        const fetchHistory = async () => {
            try {
                const res = await fetch(`${API_BASE}/pipeline/history?limit=10`, { headers });
                if (res.ok) {
                    const json = await res.json();
                    if (json.status === 'ok') setHistoryData(json.data);
                }
            } catch (e) { console.error("History fetch fail", e); }
        };

        // Trigger all
        Promise.all([
            fetchData('ohlc', setOhlcData),
            fetchData('features', setFeaturesData),
            fetchData('options', setOptionsData),
            fetchData('em', setEmData),
            fetchData('gex', setGexData),
            fetchData('ai-context', setAiContextData),
            fetchAudit(),
            fetchHistory()
        ]).finally(() => setLoading(false));

    };

    const triggerPipeline = async () => {
        if (!window.confirm("Start a new Daily Pipeline job? This runs in the background.")) return;

        try {
            const headers = token ? { "Authorization": `Bearer ${token}` } : {};
            const res = await fetch(`${API_BASE}/pipeline/start`, {
                method: 'POST',
                headers
            });
            const json = await res.json();
            if (res.ok) {
                alert(json.message);
                // Wait a sec for the process to spin up then refresh
                setTimeout(fetchAllData, 2000);
            } else {
                alert("Error: " + (json.error || json.message));
            }
        } catch (e) {
            console.error(e);
            alert("Failed to trigger pipeline.");
        }
    };

    const renderAuditTable = () => {
        if (!auditData) return <div style={{ marginTop: 20, color: '#aaa' }}>Waiting for audit log...</div>;

        const stages = auditData.stages || {};

        // Helper to find stage status regardless of exact naming match
        const getStage = (name) => {
            // Direct match
            if (stages[name]) return stages[name];
            // Fuzzy match (e.g. "Build Features" vs "Update Features")
            const keys = Object.keys(stages);
            const found = keys.find(k => k.toLowerCase().includes(name.toLowerCase()) || name.toLowerCase().includes(k.toLowerCase()));
            return found ? stages[found] : null;
        };

        return (
            <div style={{ marginTop: '20px', maxWidth: '800px' }}>
                <div style={{
                    backgroundColor: '#162032',
                    padding: '20px',
                    borderRadius: '8px',
                    border: '1px solid #333',
                    marginBottom: '20px',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                }}>
                    <div>
                        <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#e0e0e0' }}>Pipeline Job: {auditData.job_name}</h2>
                        <div style={{ fontSize: '0.9rem', color: '#888', marginTop: '5px' }}>
                            Started: {auditData.start_time ? new Date(auditData.start_time).toLocaleString() : '-'}
                        </div>
                    </div>
                    <StatusBadge status={auditData.status} />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                    {PIPELINE_STEPS.map(phase => (
                        <div key={phase.id} style={{
                            backgroundColor: '#0e1525',
                            borderRadius: '8px',
                            border: '1px solid #222',
                            overflow: 'hidden'
                        }}>
                            <div style={{
                                padding: '10px 15px',
                                backgroundColor: '#1a2639',
                                borderBottom: '1px solid #333',
                                fontWeight: 'bold',
                                color: '#a0aec0'
                            }}>
                                {phase.label}
                            </div>
                            <div>
                                {phase.steps.map(stepName => {
                                    const stageInfo = getStage(stepName);
                                    const status = stageInfo ? stageInfo.status : 'PENDING';
                                    const isDone = status === 'COMPLETED';
                                    const isRunning = status === 'RUNNING';
                                    const isFailed = status === 'FAILED';

                                    return (
                                        <div key={stepName} style={{
                                            padding: '12px 15px',
                                            borderBottom: '1px solid #222',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'space-between',
                                            backgroundColor: isRunning ? '#131d2e' : 'transparent'
                                        }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                                <div style={{
                                                    width: '20px', height: '20px',
                                                    borderRadius: '50%',
                                                    border: `2px solid ${isDone ? '#4caf50' : (isFailed ? '#f44336' : '#444')}`,
                                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                    color: isDone ? '#4caf50' : (isFailed ? '#f44336' : 'transparent'),
                                                    fontSize: '14px'
                                                }}>
                                                    {isDone && '✓'}
                                                    {isFailed && '!'}
                                                </div>
                                                <span style={{
                                                    color: isDone ? '#e0e0e0' : '#888',
                                                    textDecoration: isDone ? 'none' : 'none'
                                                }}>
                                                    {stepName}
                                                </span>
                                            </div>

                                            <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
                                                {stageInfo && stageInfo.details && (
                                                    <span style={{ fontSize: '0.8rem', color: '#666' }}>
                                                        {Object.entries(stageInfo.details).map(([k, v]) => `${k}: ${v}`).join(', ')}
                                                    </span>
                                                )}
                                                <StatusBadge status={status} />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    ))}
                </div>
            </div >
        );
    };

    const renderOhlcTable = () => (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '10px', fontSize: '0.85rem' }}>
            <thead>
                <tr style={{ borderBottom: '1px solid #444', textAlign: 'left', color: '#888' }}>
                    <th style={{ padding: '6px' }}>Ticker</th>
                    <th style={{ padding: '6px' }}>Rows</th>
                    <th style={{ padding: '6px' }}>Range</th>
                    <th style={{ padding: '6px' }}>Last Update (UTC)</th>
                    <th style={{ padding: '6px' }}>Source</th>
                </tr>
            </thead>
            <tbody>
                {ohlcData.map((row) => (
                    <tr key={row.ticker} style={{ borderBottom: '1px solid #222' }}>
                        <td style={{ padding: '6px', fontWeight: 'bold', color: '#4caf50' }}>{row.ticker}</td>
                        <td style={{ padding: '6px' }}>{row.rows}</td>
                        <td style={{ padding: '6px' }}>{(row.data_range || []).join(' → ')}</td>
                        <td style={{ padding: '6px' }}>{row.last_update ? new Date(row.last_update).toLocaleString() : '-'}</td>
                        <td style={{ padding: '6px' }}>
                            <span style={{
                                padding: '1px 5px',
                                borderRadius: '3px',
                                backgroundColor: row.source === 'polygon' ? '#2e7d32' : (row.source === 'yfinance' ? '#f57c00' : '#444'),
                                fontSize: '0.75rem'
                            }}>
                                {row.source}
                            </span>
                        </td>
                    </tr>
                ))}
            </tbody>
        </table>
    );

    const renderFeaturesTable = () => (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '10px', fontSize: '0.85rem' }}>
            <thead>
                <tr style={{ borderBottom: '1px solid #444', textAlign: 'left', color: '#888' }}>
                    <th style={{ padding: '6px' }}>Ticker</th>
                    <th style={{ padding: '6px' }}>Status</th>
                    <th style={{ padding: '6px' }}>Size</th>
                    <th style={{ padding: '6px' }}>Last Updated</th>
                </tr>
            </thead>
            <tbody>
                {featuresData.map((row) => (
                    <tr key={row.ticker} style={{ borderBottom: '1px solid #222' }}>
                        <td style={{ padding: '6px', fontWeight: 'bold', color: '#009688' }}>{row.ticker}</td>
                        <td style={{ padding: '6px', color: '#4caf50' }}>✅ Built</td>
                        <td style={{ padding: '6px', color: '#aaa' }}>
                            {row.size_bytes ? `${(row.size_bytes / 1024).toFixed(1)} KB` : '-'}
                        </td>
                        <td style={{ padding: '6px', color: '#aaa' }}>
                            {row.last_updated ? new Date(row.last_updated).toLocaleString() : '-'}
                        </td>
                    </tr>
                ))}
            </tbody>
        </table>
    );

    const renderOptionsTable = () => (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '20px', fontSize: '0.85rem' }}>
            <thead>
                <tr style={{ borderBottom: '1px solid #444', textAlign: 'left' }}>
                    <th style={{ padding: '10px' }}>Filename</th>
                    <th style={{ padding: '10px' }}>Size (MB)</th>
                    <th style={{ padding: '10px' }}>Last Modified (UTC)</th>
                </tr>
            </thead>
            <tbody>
                {optionsData.length === 0 ? (
                    <tr>
                        <td colSpan="3" style={{ padding: '20px', color: '#888', textAlign: 'center' }}>
                            No Massive flat files found. Run Download Daily Options step to fetch data.
                        </td>
                    </tr>
                ) : (
                    optionsData.map((row, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid #222' }}>
                            <td style={{ padding: '10px', fontWeight: 'bold', color: '#2196f3' }}>{row.filename}</td>
                            <td style={{ padding: '10px' }}>{row.size_mb} MB</td>
                            <td style={{ padding: '10px' }}>{row.last_modified ? new Date(row.last_modified).toLocaleString() : '-'}</td>
                        </tr>
                    ))
                )}
            </tbody>
        </table>
    );

    const renderEmTable = () => (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '20px', fontSize: '0.85rem' }}>
            <thead>
                <tr style={{ borderBottom: '1px solid #444', textAlign: 'left' }}>
                    <th style={{ padding: '10px' }}>Ticker</th>
                    <th style={{ padding: '10px' }}>Expected Moves Status</th>
                    <th style={{ padding: '10px' }}>Size</th>
                    <th style={{ padding: '10px' }}>Last Validated (UTC)</th>
                </tr>
            </thead>
            <tbody>
                {emData.map((row) => (
                    <tr key={row.ticker} style={{ borderBottom: '1px solid #222' }}>
                        <td style={{ padding: '10px', fontWeight: 'bold', color: '#3f51b5' }}>{row.ticker}</td>
                        <td style={{ padding: '10px', color: row.has_em ? '#4caf50' : '#f44336' }}>
                            {row.has_em ? '✅ Computed' : '❌ Missing'}
                        </td>
                        <td style={{ padding: '10px' }}>{(row.size_bytes / 1024).toFixed(1)} KB</td>
                        <td style={{ padding: '10px' }}>{row.last_modified ? new Date(row.last_modified).toLocaleString() : '-'}</td>
                    </tr>
                ))}
            </tbody>
        </table>
    );

    const renderGexTable = () => (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '20px' }}>
            <thead>
                <tr style={{ borderBottom: '1px solid #444', textAlign: 'left' }}>
                    <th style={{ padding: '10px' }}>Ticker</th>
                    <th style={{ padding: '10px' }}>Timestamp (UTC)</th>
                    <th style={{ padding: '10px' }}>Spot Price</th>
                    <th style={{ padding: '10px' }}>Algo</th>
                    <th style={{ padding: '10px' }}>Profile?</th>
                </tr>
            </thead>
            <tbody>
                {gexData.map((row) => (
                    <tr key={row.ticker} style={{ borderBottom: '1px solid #222' }}>
                        <td style={{ padding: '10px', fontWeight: 'bold', color: '#9c27b0' }}>{row.ticker}</td>
                        <td style={{ padding: '10px' }}>{row.timestamp ? new Date(row.timestamp).toLocaleString() : '-'}</td>
                        <td style={{ padding: '10px' }}>{row.spot_price}</td>
                        <td style={{ padding: '10px' }}>{row.algo}</td>
                        <td style={{ padding: '10px' }}>{row.has_profile ? '✅' : '❌'}</td>
                    </tr>
                ))}
            </tbody>
        </table>
    );

    const renderHistoryTable = () => (
        <div style={{ marginTop: '20px' }}>
            <h3 style={{ color: '#aaa', fontSize: '1rem', borderBottom: '1px solid #333', paddingBottom: '5px' }}>Pipeline History</h3>
            {(!historyData || historyData.length === 0) ? (
                <p>No history found.</p>
            ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                    <thead>
                        <tr style={{ textAlign: 'left', color: '#888', borderBottom: '1px solid #444' }}>
                            <th style={{ padding: '12px' }}>Date</th>
                            <th style={{ padding: '12px' }}>Job Name</th>
                            <th style={{ padding: '12px' }}>Type</th>
                            <th style={{ padding: '12px' }}>Status</th>
                            <th style={{ padding: '12px' }}>Duration</th>
                        </tr>
                    </thead>
                    <tbody>
                        {historyData.map((run, idx) => {
                            const start = run.start_time ? new Date(run.start_time) : null;
                            const end = run.end_time ? new Date(run.end_time) : null;
                            const duration = start && end ? ((end - start) / 1000 / 60).toFixed(1) + 'm' : '-';
                            return (
                                <tr key={idx} style={{ borderBottom: '1px solid #222' }}>
                                    <td style={{ padding: '12px', color: '#ddd' }}>{start ? start.toLocaleString() : '-'}</td>
                                    <td style={{ padding: '12px', color: '#aaa' }}>{run.job_name}</td>
                                    <td style={{ padding: '12px' }}>
                                        <span style={{
                                            padding: '4px 8px', borderRadius: '4px',
                                            backgroundColor: run.run_type === 'CRON' ? '#673ab7' : '#333',
                                            color: 'white', fontSize: '0.75rem', fontWeight: 'bold'
                                        }}>
                                            {run.run_type || 'MANUAL'}
                                        </span>
                                    </td>
                                    <td style={{ padding: '12px' }}><StatusBadge status={run.status} /></td>
                                    <td style={{ padding: '12px', color: '#888' }}>{duration}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            )}
        </div>
    );

    const renderAiContext = () => {
        if (!aiContextData) return <p style={{ color: '#888' }}>No AI context found. Run "generate-ai-context" via CLI or Pipeline.</p>;

        const { meta, price, regime, trend, options, seasonality } = aiContextData;

        // Fallback for old schema if data hasn't refreshed yet
        if (!meta && aiContextData.ticker) {
            return (
                <div style={{ marginTop: '20px' }}>
                    <p style={{ color: '#f57c00' }}>Warning: Old JSON schema detected. Please regenerate context.</p>
                    <details open>
                        <summary>Raw Data</summary>
                        <pre style={{ backgroundColor: '#111', padding: '15px' }}>{JSON.stringify(aiContextData, null, 2)}</pre>
                    </details>
                </div>
            )
        }

        const Card = ({ title, children, color = '#1a2639' }) => (
            <div style={{ backgroundColor: color, padding: '15px', borderRadius: '8px', flex: '1 1 300px', border: '1px solid #333' }}>
                <h4 style={{ margin: '0 0 10px 0', borderBottom: '1px solid #444', paddingBottom: '5px', color: '#ccc' }}>{title}</h4>
                <div style={{ fontSize: '0.9rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>{children}</div>
            </div>
        );

        const Row = ({ label, value, unit = '', color = '#ddd' }) => (
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #333', paddingBottom: '4px' }}>
                <span style={{ color: '#888' }}>{label}:</span>
                <span style={{ fontWeight: 'bold', color }}>
                    {value !== null && value !== undefined ? `${value}${unit}` : <span style={{ color: '#555' }}>N/A</span>}
                </span>
            </div>
        );

        return (
            <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ margin: 0 }}>AI Context: <span style={{ color: '#2196f3' }}>{meta?.ticker}</span></h3>
                    <span style={{ color: '#888' }}>Date: {meta?.date}</span>
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '15px' }}>
                    {/* PRICE & TREND */}
                    <Card title="📈 Price & Trend">
                        <Row label="Close" value={price?.close?.toFixed(2)} />
                        <Row label="Dist SMA200" value={price?.dist_sma200_pct} color={price?.dist_sma200_pct?.startsWith('-') ? '#f44336' : '#4caf50'} />
                        <Row label="Dist 52W High" value={price?.dist_52w_high_pct} />
                        <div style={{ margin: '5px 0', borderTop: '1px dashed #444' }}></div>
                        <Row label="DCS Status" value={trend?.dcs?.status} color={trend?.dcs?.status === 'Safe' ? '#4caf50' : '#f44336'} />
                        <Row label="DCS Score" value={trend?.dcs?.score} />
                        <Row label="EMA Stack" value={trend?.ema_stack?.verdict} />
                        <Row label="ADX Strength" value={`${trend?.adx?.val?.toFixed(1)} (${trend?.adx?.trend_strength})`} />
                        <Row label="Ichimoku" value={trend?.ichimoku?.status} />
                        <Row label="TSMOM" value={trend?.tsmom?.signal} />
                    </Card>

                    {/* REGIME & VOL */}
                    <Card title="🏛️ Regime & Volatility">
                        <Row label="HMM State" value={regime?.hmm?.desc} color={regime?.hmm?.state === '0' ? '#4caf50' : '#f44336'} />
                        <Row label="Markov Verdict" value={regime?.markov?.verdict} />
                        <Row label="Next Bull Prob" value={(regime?.markov?.next_prob_bull * 100)?.toFixed(1)} unit="%" />
                        <div style={{ margin: '5px 0', borderTop: '1px dashed #444' }}></div>
                        <Row label="Vol Regime" value={regime?.vol?.regime} />
                        <Row label="ATR (14)" value={regime?.vol?.atr_14?.toFixed(2)} />
                        <Row label="ATR Rank" value={regime?.vol?.rank_6m} unit="%" />
                    </Card>

                    {/* OPTIONS */}
                    <Card title="🎲 Options & GEX">
                        <Row label="Net GEX" value={options?.gex?.net_regime} />
                        <Row label="Call Wall" value={options?.gex?.call_wall_dist_pct} />
                        <Row label="Put Wall" value={options?.gex?.put_wall_dist_pct} />
                        <div style={{ margin: '5px 0', borderTop: '1px dashed #444' }}></div>
                        <Row label="EM (1W)" value={options?.exp_moves?.['1w_range']?.join(' - ')} />
                        <Row label="0DTE Range" value={`+/- ${options?.exp_moves?.['0dte_range']?.toFixed(2)}`} />
                        <Row label="PCR (Vol)" value={options?.sentiment?.pcr_vol?.toFixed(2)} />
                        <Row label="Skew (24d)" value={options?.sentiment?.skew_24d} />
                    </Card>

                    {/* SEASONALITY */}
                    <Card title="📅 Seasonality">
                        <Row label="Next Session" value={seasonality?.next_day} />
                        <Row label="Next Week" value={seasonality?.next_week} />
                    </Card>
                </div>

                {/* RAW JSON TOGGLE */}
                <details style={{ marginTop: '20px', borderTop: '1px solid #333', paddingTop: '10px' }}>
                    <summary style={{ cursor: 'pointer', color: '#888' }}>View Raw JSON</summary>
                    <pre style={{
                        backgroundColor: '#111',
                        padding: '15px',
                        borderRadius: '8px',
                        color: '#ce9178',
                        fontSize: '0.8rem',
                        overflowX: 'auto',
                        marginTop: '10px'
                    }}>
                        {JSON.stringify(aiContextData, null, 2)}
                    </pre>
                </details>
            </div>
        );
    };

    return (
        <div style={{ padding: '20px', color: '#d7e3f3', minHeight: '100vh', backgroundColor: '#0b1220' }}>
            <h1>Admin Data Dashboard</h1>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <p style={{ color: '#888', margin: '5px 0 20px 0' }}>System Data Status Overview</p>
                {auditData && auditData.start_time && (
                    <div style={{ color: '#4caf50', fontWeight: 'bold', fontSize: '0.9rem' }}>
                        Last Run: {new Date(auditData.start_time).toLocaleString()}
                    </div>
                )}
            </div>

            {/* TABS */}
            {/* TABS */}
            <div style={{ display: 'flex', gap: '5px', borderBottom: '1px solid #444', paddingBottom: '10px', flexWrap: 'wrap' }}>
                <button
                    onClick={() => setActiveTab('audit')}
                    style={{
                        background: activeTab === 'audit' ? '#ff9800' : '#222',
                        color: 'white', border: 'none', padding: '6px 12px', cursor: 'pointer', borderRadius: '4px', fontWeight: 'bold', fontSize: '0.85rem'
                    }}>
                    Pipeline Audit
                </button>
                <button
                    onClick={() => setActiveTab('history')}
                    style={{
                        background: activeTab === 'history' ? '#673ab7' : '#222',
                        color: 'white', border: 'none', padding: '6px 12px', cursor: 'pointer', borderRadius: '4px', fontWeight: 'bold', fontSize: '0.85rem'
                    }}>
                    History
                </button>
                <button
                    onClick={() => setActiveTab('ohlc')}
                    style={{
                        background: activeTab === 'ohlc' ? '#4caf50' : '#222',
                        color: 'white', border: 'none', padding: '6px 12px', cursor: 'pointer', borderRadius: '4px', fontSize: '0.85rem'
                    }}>
                    OHLC Data
                </button>
                <button
                    onClick={() => setActiveTab('features')}
                    style={{
                        background: activeTab === 'features' ? '#009688' : '#222',
                        color: 'white', border: 'none', padding: '6px 12px', cursor: 'pointer', borderRadius: '4px', fontSize: '0.85rem'
                    }}>
                    Features
                </button>
                <button
                    onClick={() => setActiveTab('options')}
                    style={{
                        background: activeTab === 'options' ? '#2196f3' : '#222',
                        color: 'white', border: 'none', padding: '6px 12px', cursor: 'pointer', borderRadius: '4px', fontSize: '0.85rem'
                    }}>
                    Options (Raw)
                </button>
                <button
                    onClick={() => setActiveTab('em')}
                    style={{
                        background: activeTab === 'em' ? '#3f51b5' : '#222',
                        color: 'white', border: 'none', padding: '6px 12px', cursor: 'pointer', borderRadius: '4px', fontSize: '0.85rem'
                    }}>
                    Expected Moves
                </button>
                <button
                    onClick={() => setActiveTab('gex')}
                    style={{
                        background: activeTab === 'gex' ? '#9c27b0' : '#222',
                        color: 'white', border: 'none', padding: '6px 12px', cursor: 'pointer', borderRadius: '4px', fontSize: '0.85rem'
                    }}>
                    GEX
                </button>
                <button
                    onClick={fetchAllData}
                    style={{
                        background: '#444',
                        marginLeft: 'auto',
                        color: 'white', border: 'none', padding: '6px 12px', cursor: 'pointer', borderRadius: '4px', fontSize: '0.85rem'
                    }}>
                    🔄 Refresh
                </button>
                <button
                    onClick={() => setActiveTab('ai-context')}
                    style={{
                        background: activeTab === 'ai-context' ? '#e91e63' : '#222',
                        color: 'white', border: 'none', padding: '6px 12px', cursor: 'pointer', borderRadius: '4px', fontSize: '0.85rem'
                    }}>
                    AI Context
                </button>
                <button
                    onClick={triggerPipeline}
                    style={{
                        background: '#2196f3',
                        color: 'white', border: 'none', padding: '6px 12px', cursor: 'pointer', borderRadius: '4px',
                        marginLeft: '10px', fontWeight: 'bold', fontSize: '0.85rem'
                    }}>
                    ▶ Run Pipeline
                </button>
            </div>

            {loading && <p>Loading data...</p>}

            {!loading && (
                <div>
                    {activeTab === 'audit' && renderAuditTable()}
                    {activeTab === 'history' && renderHistoryTable()}
                    {activeTab === 'ohlc' && renderOhlcTable()}
                    {activeTab === 'features' && renderFeaturesTable()}
                    {activeTab === 'options' && renderOptionsTable()}
                    {activeTab === 'em' && renderEmTable()}
                    {activeTab === 'gex' && renderGexTable()}
                    {activeTab === 'ai-context' && renderAiContext()}
                </div>
            )}
        </div>
    );
};

export default AdminDataDashboard;
