import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = '/api/v1/admin/data/economic';

const StatusBadge = ({ status }) => {
    const s = (status || "pending").toUpperCase();
    let color = '#999';
    if (s === 'COMPLETED') color = '#4caf50';
    else if (s === 'RUNNING') color = '#2196f3';
    else if (s === 'FAILED') color = '#f44336';
    else if (s === 'PARTIAL') color = '#ff9800';
    return <span style={{ color, fontWeight: 'bold' }}>{s}</span>;
};

const EconomicPipeline = () => {
    const [status, setStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [triggering, setTriggering] = useState(false);

    useEffect(() => {
        fetchStatus();
        const interval = setInterval(fetchStatus, 5000);
        return () => clearInterval(interval);
    }, []);

    const fetchStatus = async () => {
        try {
            const res = await axios.get(`${API_BASE}/status`);
            if (res.data && res.data.data) {
                setStatus(res.data.data);
            }
        } catch (err) {
            console.error("Failed to fetch economic pipeline status:", err);
        } finally {
            setLoading(false);
        }
    };

    const triggerPipeline = async () => {
        if (!window.confirm("Start Economic Data Pipeline? This will fetch FRED data and recalculate all models.")) return;
        setTriggering(true);
        try {
            await axios.post(`${API_BASE}/start`);
            alert("Pipeline started successfully!");
            setTimeout(fetchStatus, 2000);
        } catch (err) {
            alert("Failed to start pipeline: " + (err.response?.data?.detail || err.message));
        } finally {
            setTriggering(false);
        }
    };

    const getStepStatus = (stepName) => {
        const step = status?.steps?.find(s => s.name === stepName);
        if (!step) return { status: 'pending' };
        return step;
    };

    const formatMeta = (step) => {
        const parts = [];
        if (step.series_updated) parts.push(`${step.series_updated}/${step.series_count} series`);
        if (step.file_size_kb) {
            const size = step.file_size_kb < 1024
                ? `${step.file_size_kb.toFixed(0)} KB`
                : `${(step.file_size_kb / 1024).toFixed(2)} MB`;
            parts.push(size);
        }
        if (step.errors && step.errors.length > 0) parts.push(`${step.errors.length} errors`);
        return parts.length > 0 ? `(${parts.join(', ')})` : '';
    };

    if (loading) {
        return <div style={{ padding: '20px', color: '#888' }}>Loading...</div>;
    }

    // Define phases matching backend steps
    const PHASES = [
        {
            id: "ingestion",
            label: "Phase 1: Data Ingestion",
            steps: ["Fetch FRED Data"]
        },
        {
            id: "indicators",
            label: "Phase 2: Economic Indicators",
            steps: [
                "Calculate Enhanced LEI/COI",
                "Calculate Business Cycle",
                "Calculate LAG Index"
            ]
        },
        {
            id: "models",
            label: "Phase 3: Economic Models",
            steps: [
                "Calculate Minsky Model",
                "Calculate ABCT Model",
                "Calculate HP Filter",
                "Calculate Hamilton Model",
                "Calculate Liquidity Impulse",
                "Calculate Recession Momentum",
                "Generate Prediction Analysis"
            ]
        }
    ];

    const isRunning = status?.status === 'running';
    const pipelineStatus = status?.status === 'running' ? 'RUNNING' :
        status?.status === 'failed' ? 'FAILED' : 'COMPLETED';

    return (
        <div>
            {/* Header */}
            <div style={{ backgroundColor: '#162032', padding: '20px', borderRadius: '8px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <h2 style={{ color: '#fff', margin: '0 0 8px 0', fontSize: '24px' }}>
                        Economic Pipeline: {status?.last_run ? new Date(status.last_run).toLocaleDateString() : 'Never Run'}
                    </h2>
                    <div style={{ color: '#888', fontSize: '14px' }}>
                        Started: {status?.last_run ? new Date(status.last_run).toLocaleString() : '-'}
                    </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                    <StatusBadge status={pipelineStatus} />
                    <button
                        onClick={triggerPipeline}
                        disabled={isRunning || triggering}
                        style={{
                            padding: '8px 16px',
                            background: isRunning || triggering ? '#555' : '#2196f3',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: isRunning || triggering ? 'not-allowed' : 'pointer',
                            fontWeight: 'bold'
                        }}
                    >
                        {isRunning ? 'Running...' : triggering ? 'Starting...' : 'Run Pipeline'}
                    </button>
                </div>
            </div>

            {/* Phases */}
            {PHASES.map(phase => (
                <div key={phase.id} style={{ marginBottom: '15px', backgroundColor: '#0e1525', borderRadius: '8px', border: '1px solid #222', overflow: 'hidden' }}>
                    <div style={{ padding: '10px 15px', backgroundColor: '#1a2639', fontWeight: 'bold', color: '#fff' }}>
                        {phase.label}
                    </div>
                    <div>
                        {phase.steps.map(stepName => {
                            const stepData = getStepStatus(stepName);
                            const meta = formatMeta(stepData);
                            return (
                                <div key={stepName} style={{
                                    padding: '10px 15px',
                                    borderBottom: '1px solid #222',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center'
                                }}>
                                    <span style={{ color: '#cbd5e1' }}>{stepName}</span>
                                    <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                                        {meta && <span style={{ color: '#666', fontSize: '0.8rem' }}>{meta}</span>}
                                        <StatusBadge status={stepData.status} />
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            ))}
        </div>
    );
};

export default EconomicPipeline;
