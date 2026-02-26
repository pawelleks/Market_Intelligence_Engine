import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import FredPipeline from '../../components/FredPipeline';
import EconomicPipeline from '../../components/EconomicPipeline';
import { usePageTitle } from '../../hooks/usePageTitle';

// Pipeline phases are now fetched from /api/v1/system/pipeline/stages (driven by stages.yml)

const StatusBadge = ({ status }) => {
    const s = (status || "UNKNOWN").toUpperCase();
    let color = '#999';
    if (s === 'COMPLETED' || s === 'SUCCESS') color = '#4caf50';
    else if (s === 'FAILED' || s === 'ERROR') color = '#f44336';
    else if (s === 'RUNNING') color = '#2196f3';
    else if (s === 'SKIPPED') color = '#ff9800';
    return <span style={{ color, fontWeight: 'bold' }}>{s}</span>;
};

// --- Reusable Paginated Table ---
const PaginatedTable = ({ data, columns, pageSize = 50 }) => {
    const [page, setPage] = useState(1);

    // Reset page if data changes significantly
    useEffect(() => { setPage(1); }, [data?.length]);

    if (!data || data.length === 0) return <div style={{ padding: '20px', color: '#888' }}>No data available.</div>;

    const totalPages = Math.ceil(data.length / pageSize);
    const displayedData = data.slice((page - 1) * pageSize, page * pageSize);

    return (
        <div>
            <div style={{ padding: '10px 0', fontSize: '14px', color: '#94a3b8', display: 'flex', justifyContent: 'space-between' }}>
                <span>Showing {((page - 1) * pageSize) + 1}-{Math.min(page * pageSize, data.length)} of {data.length} records</span>
                <span style={{ fontWeight: 'bold', color: '#fff' }}>Total: {data.length}</span>
            </div>
            <div style={{ overflowX: 'auto', border: '1px solid #1e293b', borderRadius: '8px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                    <thead>
                        <tr style={{ textAlign: 'left', color: '#94a3b8', borderBottom: '1px solid #444', backgroundColor: '#1e293b' }}>
                            {columns.map(c => <th key={c.key} style={{ padding: '12px' }}>{c.label}</th>)}
                        </tr>
                    </thead>
                    <tbody>
                        {displayedData.map((row, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid #1e293b' }}>
                                {columns.map(c => <td key={c.key} style={{ padding: '10px', color: '#cbd5e1' }}>{c.render ? c.render(row) : row[c.key]}</td>)}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {/* Pagination Controls */}
            {totalPages > 1 && (
                <div style={{ padding: '15px 0', display: 'flex', gap: '10px', justifyContent: 'center' }}>
                    <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} style={{ padding: '5px 10px', cursor: page === 1 ? 'not-allowed' : 'pointer' }}>Prev</button>
                    <span style={{ color: '#fff' }}>Page {page} of {totalPages}</span>
                    <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} style={{ padding: '5px 10px', cursor: page === totalPages ? 'not-allowed' : 'pointer' }}>Next</button>
                </div>
            )}
        </div>
    );
};

const API_BASE = "/api/v1/admin/data";

import { useSearchParams } from 'react-router-dom';

const DataManagementPage = () => {
    usePageTitle('Data Management');
    const { token } = useAuth();
    const [searchParams, setSearchParams] = useSearchParams();

    // Default: pipeline
    const activeTab = searchParams.get('tab') || 'pipeline';
    const setActiveTab = (tab) => setSearchParams({ tab });

    // Sub-tabs state
    const [pipelineSubTab, setPipelineSubTab] = useState('audit');
    const [viewerSubTab, setViewerSubTab] = useState('ohlc');
    const [contentSubTab, setContentSubTab] = useState('latest');

    // Data State
    const [pipelinePhases, setPipelinePhases] = useState([]);
    const [auditData, setAuditData] = useState(null);
    const [historyData, setHistoryData] = useState([]);
    const [ohlcData, setOhlcData] = useState([]);
    const [featuresData, setFeaturesData] = useState([]);
    const [optionsData, setOptionsData] = useState([]);
    const [emData, setEmData] = useState([]);
    const [gexData, setGexData] = useState([]);
    const [aiContextData, setAiContextData] = useState(null);
    const [reportsData, setReportsData] = useState([]);
    const [loading, setLoading] = useState(false);

    // Initial Fetch
    useEffect(() => {
        if (token) fetchAllData();
    }, [token]);

    // Polling for Audit
    useEffect(() => {
        if (!token) return;
        let interval;
        if (auditData?.status === 'RUNNING' || activeTab === 'pipeline') {
            interval = setInterval(() => {
                fetchAudit();
            }, 5000);
        }
        return () => clearInterval(interval);
    }, [activeTab, auditData?.status, token]);


    const fetchPipelineStages = async () => {
        try {
            const res = await fetch(`/api/v1/system/pipeline/stages`, { headers });
            if (res.ok) {
                const json = await res.json();
                setPipelinePhases(json.phases || []);
            }
        } catch (e) { console.error('Failed to fetch pipeline stages:', e); }
    };

    const fetchAllData = () => {
        setLoading(true);
        Promise.all([
            fetchPipelineStages(),
            fetchAudit(),
            fetchHistory(),
            fetchViewerData('ohlc', setOhlcData),
            fetchViewerData('features', setFeaturesData),
            fetchViewerData('options', setOptionsData),
            fetchViewerData('em', setEmData),
            fetchViewerData('gex', setGexData),
            fetchAiContext(),
            fetchReports()
        ]).finally(() => setLoading(false));
    };

    // --- Fetch Helpers ---
    const headers = { "Authorization": `Bearer ${token}` };

    const fetchAudit = async () => {
        try {
            const res = await fetch(`/api/v1/system/audit/latest`, { headers });
            if (res.ok) setAuditData(await res.json());
        } catch (e) { console.error(e); }
    };
    const fetchHistory = async () => {
        try {
            const res = await fetch(`${API_BASE}/pipeline/history?limit=10`, { headers });
            if (res.ok) {
                const json = await res.json();
                if (json.status === 'ok') setHistoryData(json.data);
            }
        } catch (e) { console.error(e); }
    };
    const fetchViewerData = async (endpoint, setter) => {
        try {
            const res = await fetch(`${API_BASE}/${endpoint}`, { headers });
            if (res.ok) {
                const json = await res.json();
                if (json.status === 'ok') setter(json.data);
            }
        } catch (e) { console.error(e); }
    };
    const fetchAiContext = async () => {
        try {
            const res = await fetch(`${API_BASE}/ai-context`, { headers });
            if (res.ok) {
                const json = await res.json();
                if (json.status === 'ok') setAiContextData(json.data);
            }
        } catch (e) { console.error(e); }
    };
    const fetchReports = async () => {
        try {
            const res = await fetch(`${API_BASE}/reports`, { headers });
            if (res.ok) {
                const json = await res.json();
                if (json.status === 'ok') setReportsData(json.data);
            }
        } catch (e) { console.error(e); }
    };

    const triggerPipeline = async (force = false) => {
        if (!force && !window.confirm("Start a new Daily Pipeline job? This runs in the background.")) return;
        try {
            const url = `${API_BASE}/pipeline/start` + (force ? '?force=true' : '');
            const res = await fetch(url, { method: 'POST', headers });
            const json = await res.json();

            if (res.status === 409) {
                // Already running
                if (window.confirm("Pipeline is already RUNNING. Do you want to FORCE START a new one? (This will override the current status)")) {
                    triggerPipeline(true);
                }
                return;
            }

            if (res.ok) {
                alert(json.message);
                setTimeout(fetchAudit, 1000);
            } else {
                alert("Error: " + (json.message || "Failed"));
            }
        } catch (e) { alert("Failed to trigger pipeline"); }
    };

    // --- Render Helpers ---
    const renderAudit = () => {
        if (!auditData) return <div>Waiting for audit log...</div>;
        const stages = auditData.stages || {};
        const isRunning = auditData.status === 'RUNNING';

        const formatDetails = (details) => {
            if (!details) return null;
            let d = details;
            if (typeof d === 'string' && d.trim().startsWith('{')) {
                try { d = JSON.parse(d); } catch (e) { }
            }
            if (typeof d === 'string') return <span style={{ color: '#666', fontSize: '0.8rem' }}>{d}</span>;

            const elems = [];
            if (d.duration_seconds) {
                elems.push(<span key="dur" style={{ color: '#94a3b8', marginRight: '8px' }}>({Number(d.duration_seconds).toFixed(1)}s)</span>);
            }
            if (d.processed !== undefined || d.total !== undefined) {
                const p = d.processed !== undefined ? d.processed : '?';
                const t = d.total !== undefined ? d.total : '?';
                elems.push(<span key="prog" style={{ color: '#94a3b8', marginRight: '8px' }}>{p}/{t}</span>);
            }
            if (d.error) {
                elems.push(<span key="err" style={{ color: '#ef4444' }}>{d.error}</span>);
            }

            return <span style={{ fontSize: '0.8rem' }}>{elems}</span>;
        };

        // Count completed/total for progress display
        const totalStages = pipelinePhases.reduce((sum, p) => sum + p.stages.length, 0);
        const getStageInfo = (s) => stages[s.id] || stages[s.name];
        const completedStages = pipelinePhases.reduce((sum, p) =>
            sum + p.stages.filter(s => {
                const st = (getStageInfo(s)?.status || '').toUpperCase();
                return st === 'COMPLETED' || st === 'SUCCESS' || st === 'WARNING';
            }).length, 0);

        return (
            <div>
                <div style={{ backgroundColor: '#162032', padding: '20px', borderRadius: '8px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between' }}>
                    <div>
                        <h2>Pipeline Job: {auditData.job_name}</h2>
                        <div style={{ color: '#888' }}>
                            Started: {auditData.start_time ? new Date(auditData.start_time).toLocaleString() : '-'}
                            {isRunning && <span style={{ marginLeft: '15px', color: '#94a3b8' }}>Progress: {completedStages}/{totalStages}</span>}
                        </div>
                    </div>
                    <div>
                        <StatusBadge status={auditData.status} />
                        <button
                            onClick={() => triggerPipeline(false)}
                            style={{
                                marginLeft: '20px',
                                padding: '8px 16px',
                                background: isRunning ? '#ff9800' : '#2196f3',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontWeight: 'bold'
                            }}
                        >
                            {isRunning ? 'Force Restart' : 'Run Pipeline'}
                        </button>
                    </div>
                </div>
                {pipelinePhases.map(phase => {
                    // Count completed in this phase
                    const phaseComplete = phase.stages.filter(s => {
                        const st = ((stages[s.id] || stages[s.name])?.status || '').toUpperCase();
                        return st === 'COMPLETED' || st === 'SUCCESS' || st === 'WARNING';
                    }).length;

                    return (
                        <div key={phase.label} style={{ marginBottom: '15px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #222' }}>
                            <div style={{ padding: '10px 15px', backgroundColor: '#1a2639', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between' }}>
                                <span>{phase.label}</span>
                                <span style={{ color: '#94a3b8', fontWeight: 'normal', fontSize: '0.85rem' }}>{phaseComplete}/{phase.stages.length}</span>
                            </div>
                            <div>
                                {phase.stages.map(stage => {
                                    // Try exact ID match first (new format), fallback to name match (legacy)
                                    let info = stages[stage.id];
                                    if (!info) info = stages[stage.name];
                                    const status = info ? info.status : 'PENDING';
                                    return (
                                        <div key={stage.id} style={{ padding: '10px 15px', borderBottom: '1px solid #222', display: 'flex', justifyContent: 'space-between' }}>
                                            <span>{stage.name}</span>
                                            <div style={{ display: 'flex', gap: '10px' }}>
                                                {info && info.details && formatDetails(info.details)}
                                                <StatusBadge status={status} />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    );
                })}
            </div>
        );
    };

    const renderHistory = () => (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
                <tr style={{ textAlign: 'left', color: '#888', borderBottom: '1px solid #444' }}>
                    <th style={{ padding: '10px' }}>Date</th><th style={{ padding: '10px' }}>Job</th><th style={{ padding: '10px' }}>Status</th>
                </tr>
            </thead>
            <tbody>
                {historyData.map((run, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                        <td style={{ padding: '10px' }}>{run.start_time ? new Date(run.start_time).toLocaleString() : '-'}</td>
                        <td style={{ padding: '10px' }}>{run.job_name}</td>
                        <td style={{ padding: '10px' }}><StatusBadge status={run.status} /></td>
                    </tr>
                ))}
            </tbody>
        </table>
    );

    const renderViewerTable = (data, columns) => (
        <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                <thead>
                    <tr style={{ textAlign: 'left', color: '#888', borderBottom: '1px solid #444' }}>
                        {columns.map(c => <th key={c.key} style={{ padding: '10px' }}>{c.label}</th>)}
                    </tr>
                </thead>
                <tbody>
                    {data.map((row, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                            {columns.map(c => <td key={c.key} style={{ padding: '10px' }}>{c.render ? c.render(row) : row[c.key]}</td>)}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );

    const handleDownloadReport = async (filename) => {
        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch(`${API_BASE}/reports/${filename}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                if (response.status === 401) alert("Unauthorized. Please login again.");
                else if (response.status === 404) alert("Report file not found.");
                else alert("Download failed. Status: " + response.status);
                return;
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            console.error("Download error:", error);
            alert("Failed to download report: " + error.message);
        }
    };

    const renderAiContext = () => (
        <div>
            <h3>Latest AI Context</h3>
            {aiContextData ? (
                <pre style={{ background: '#111', padding: '15px', overflow: 'auto', maxHeight: '600px' }}>{JSON.stringify(aiContextData, null, 2)}</pre>
            ) : (
                <div style={{ padding: '20px', textAlign: 'center', color: '#888' }}>Null</div>
            )}
        </div>
    );

    const renderReports = () => (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
                <tr style={{ textAlign: 'left', color: '#888', borderBottom: '1px solid #444' }}>
                    <th style={{ padding: '10px' }}>Filename</th><th style={{ padding: '10px' }}>Date</th><th style={{ padding: '10px' }}>Size</th><th style={{ padding: '10px' }}>Action</th>
                </tr>
            </thead>
            <tbody>
                {reportsData.map((row, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                        <td style={{ padding: '10px' }}>{row.filename}</td>
                        <td style={{ padding: '10px' }}>{new Date(row.modified).toLocaleString()}</td>
                        <td style={{ padding: '10px' }}>{(row.size_bytes / 1024).toFixed(1)} KB</td>
                        <td style={{ padding: '10px' }}>
                            <button onClick={() => handleDownloadReport(row.filename)} style={{ color: '#3b82f6', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline' }}>Download</button>
                        </td>
                    </tr>
                ))}
            </tbody>
        </table>
    );

    // --- Main Render ---
    return (
        <div style={{ padding: '20px', maxWidth: '1600px', margin: '0 auto', color: '#e2e8f0' }}>
            <h1>Data Management</h1>

            {/* Top Tabs */}
            <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', borderBottom: '1px solid #334155', paddingBottom: '10px' }}>
                {['pipeline', 'economic', 'fred', 'viewer', 'content'].map(tab => (
                    <button key={tab}
                        onClick={() => setActiveTab(tab)}
                        style={{
                            padding: '10px 20px',
                            background: activeTab === tab ? '#3b82f6' : 'transparent',
                            color: activeTab === tab ? '#fff' : '#94a3b8',
                            border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold',
                            textTransform: 'capitalize'
                        }}>
                        {tab === 'economic' ? 'Economic Pipeline' : tab === 'fred' ? 'FRED Data' : tab === 'viewer' ? 'Data Availability' : tab === 'content' ? 'Computed Content' : 'Market Pipeline'}
                    </button>
                ))}
            </div>

            {/* Content Area */}
            <div style={{ minHeight: '600px', backgroundColor: '#0f172a', padding: '20px', borderRadius: '8px' }}>

                {/* 1. PIPELINE */}
                {activeTab === 'pipeline' && (
                    <div>
                        <div style={{ marginBottom: '20px', display: 'flex', gap: '10px' }}>
                            <button onClick={() => setPipelineSubTab('audit')} style={{ color: pipelineSubTab === 'audit' ? '#fff' : '#888', background: 'none', border: 'none', borderBottom: pipelineSubTab === 'audit' ? '2px solid #fff' : 'none', cursor: 'pointer', padding: '5px' }}>Pipeline Audit</button>
                            <button onClick={() => setPipelineSubTab('history')} style={{ color: pipelineSubTab === 'history' ? '#fff' : '#888', background: 'none', border: 'none', borderBottom: pipelineSubTab === 'history' ? '2px solid #fff' : 'none', cursor: 'pointer', padding: '5px' }}>Pipeline History</button>
                        </div>
                        {pipelineSubTab === 'audit' && renderAudit()}
                        {pipelineSubTab === 'history' && renderHistory()}
                    </div>
                )}

                {/* 2. ECONOMIC PIPELINE */}
                {activeTab === 'economic' && <EconomicPipeline />}

                {/* 3. FRED */}
                {activeTab === 'fred' && <FredPipeline />}

                {/* 4. VIEWER */}
                {activeTab === 'viewer' && (
                    <div>
                        <div style={{ marginBottom: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                            {['ohlc', 'features', 'options', 'em', 'gex'].map(st => (
                                <button key={st} onClick={() => setViewerSubTab(st)}
                                    style={{ color: viewerSubTab === st ? '#fff' : '#888', background: 'none', border: 'none', borderBottom: viewerSubTab === st ? '2px solid #fff' : 'none', cursor: 'pointer', padding: '5px', textTransform: 'uppercase' }}>
                                    {st}
                                </button>
                            ))}
                        </div>
                        {viewerSubTab === 'ohlc' && (
                            <PaginatedTable
                                data={ohlcData.filter(r => r.rows > 0)}
                                columns={[
                                    { key: 'ticker', label: 'Ticker' },
                                    { key: 'rows', label: 'Rows' },
                                    { key: 'last_update', label: 'Updated', render: r => r.last_update?.slice(0, 19) }
                                ]}
                            />
                        )}
                        {viewerSubTab === 'features' && renderViewerTable(featuresData, [
                            { key: 'ticker', label: 'Ticker' }, { key: 'size_bytes', label: 'Size', render: r => (r.size_bytes / 1024).toFixed(1) + ' KB' }, { key: 'last_updated', label: 'Updated', render: r => r.last_updated?.slice(0, 19) }
                        ])}
                        {viewerSubTab === 'options' && renderViewerTable(optionsData, [
                            { key: 'filename', label: 'File' }, { key: 'size_mb', label: 'Size MB' }, { key: 'last_modified', label: 'Modified', render: r => r.last_modified?.slice(0, 19) }
                        ])}
                        {viewerSubTab === 'em' && renderViewerTable(emData, [
                            { key: 'ticker', label: 'Ticker' }, { key: 'has_em', label: 'Status', render: r => r.has_em ? 'OK' : 'Missing' }
                        ])}
                        {viewerSubTab === 'gex' && renderViewerTable(gexData, [
                            { key: 'ticker', label: 'Ticker' }, { key: 'spot_price', label: 'Spot' }, { key: 'has_profile', label: 'Profile' }
                        ])}
                    </div>
                )}

                {/* 5. CONTENT */}
                {activeTab === 'content' && (
                    <div>
                        <div style={{ marginBottom: '20px', display: 'flex', gap: '10px' }}>
                            <button onClick={() => setContentSubTab('latest')} style={{ color: contentSubTab === 'latest' ? '#fff' : '#888', background: 'none', border: 'none', borderBottom: contentSubTab === 'latest' ? '2px solid #fff' : 'none', cursor: 'pointer', padding: '5px' }}>Latest AI Context</button>
                            <button onClick={() => setContentSubTab('archive')} style={{ color: contentSubTab === 'archive' ? '#fff' : '#888', background: 'none', border: 'none', borderBottom: contentSubTab === 'archive' ? '2px solid #fff' : 'none', cursor: 'pointer', padding: '5px' }}>Report History</button>
                        </div>
                        {contentSubTab === 'latest' && renderAiContext()}
                        {contentSubTab === 'archive' && renderReports()}
                    </div>
                )}

            </div>
        </div>
    );
};

export default DataManagementPage;
