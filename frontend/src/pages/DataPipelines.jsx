import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import EconomicPipeline from '../components/EconomicPipeline';

// --- STRICT Log Viewer Component (User Requested) ---
const LogViewer = ({ logs }) => {

    // Auto-scroll logic (mimicking tail -f)
    useEffect(() => {
        const scrollToBottom = () => {
            const container = document.getElementById('log-container');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        };
        scrollToBottom();
    }, [logs]);

    // VULN-02FIX: Safe rendering instead of dangerouslySetInnerHTML
    const renderLogLine = (line, idx) => {
        if (!line) return <div key={idx} className="h-4" />;

        // Tokenize by keywords and timestamp
        const parts = line.split(/(ERROR|FAIL|WARNING|INFO|\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/g);

        return (
            <div key={idx} className="whitespace-pre-wrap">
                {parts.map((part, pIdx) => {
                    if (part === "ERROR" || part === "FAIL") return <span key={pIdx} className="log-error">{part}</span>;
                    if (part === "WARNING") return <span key={pIdx} className="log-warn">{part}</span>;
                    if (part === "INFO") return <span key={pIdx} className="log-info">{part}</span>;
                    if (/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/.test(part)) return <span key={pIdx} className="log-timestamp">{part}</span>;
                    return part;
                })}
            </div>
        );
    };

    return (
        <div
            id="log-container"
            className="terminal-window"
        >
            {logs ? logs.split('\n').map(renderLogLine) : "Waiting for logs..."}
        </div>
    );
};

const SystemProgressBar = () => {
    const [status, setStatus] = useState(null);

    useEffect(() => {
        const fetchStatus = async () => {
            try {
                const res = await axios.get('/api/v1/system/status');
                if (res.data && res.data.status === 'running') {
                    setStatus(res.data);
                } else {
                    setStatus(null);
                }
            } catch (err) {
                // Ignore errors (endpoint might not exist yet or job dead)
            }
        };

        fetchStatus();
        const interval = setInterval(fetchStatus, 3000);
        return () => clearInterval(interval);
    }, []);

    if (!status) return null;

    return (
        <div className="w-full max-w-4xl mx-auto mb-6 bg-[#1f2833] border border-gray-600 rounded-lg p-4 shadow-xl animate-pulse-border">
            <div className="flex justify-between items-end mb-2">
                <div>
                    <h3 className="text-[#66fcf1] font-bold text-lg uppercase tracking-wide">
                        {status.job_id || "System Job"}
                    </h3>
                    <p className="text-gray-400 text-xs">
                        {status.step_name} (Step {status.current_step}/{status.total_steps})
                    </p>
                </div>
                <span className="text-[#66fcf1] font-mono font-bold text-xl">
                    {status.progress_percent}%
                </span>
            </div>

            {/* Progress Bar Track */}
            <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
                <div
                    className="bg-gradient-to-r from-[#45a29e] to-[#66fcf1] h-full rounded-full transition-all duration-500 ease-out shadow-[0_0_10px_#66fcf1]"
                    style={{ width: `${status.progress_percent}%` }}
                ></div>
            </div>

            <div className="mt-2 text-right">
                <span className="text-gray-500 text-[10px] font-mono">
                    Last Updated: {new Date(status.last_updated).toLocaleTimeString()}
                </span>
            </div>
        </div>
    );
};

const DataPipelines = () => {
    const [activeTab, setActiveTab] = useState('market'); // 'market' or 'economic'
    const [status, setStatus] = useState({ running: false, logs: '', available_jobs: [] });
    const [loadingJob, setLoadingJob] = useState(null);
    const [selectedJob, setSelectedJob] = useState("");
    const [error, setError] = useState(null);

    // Poll status every 2 seconds
    useEffect(() => {
        const fetchStatus = async () => {
            try {
                const res = await axios.get('/api/v1/system/jobs/status?lines=1000');
                if (res.data) {
                    setStatus(prev => ({ ...res.data, logs: res.data.logs || '' }));
                }
            } catch (err) {
                console.error("Failed to fetch status", err);
            }
        };

        fetchStatus();
        const interval = setInterval(fetchStatus, 2000);
        return () => clearInterval(interval);
    }, []);

    const triggerJob = async (jobName) => {
        if (!jobName) return;
        setLoadingJob(jobName);
        setError(null);
        try {
            await axios.post(`/api/v1/system/jobs/${jobName}`);
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to start job");
        } finally {
            setLoadingJob(null);
        }
    };

    const getJobLabel = (job) => {
        const map = {
            "daily-pipeline": "🚀 Run Full Daily Pipeline",
            "update-raw": "Ingest: Update Raw Prices",
            "fetch-options": "Ingest: Fetch Options",
            "build-features": "Features: Update",
            "rebuild-features": "Features: Rebuild All",
            "build-gex": "Analytics: Build GEX (Gamma Exposure)",
            "build-skew-daily": "Analytics: Option Skew & PCR",
            "update-expected-moves": "Analytics: Exp. Moves",
            "build-hmm": "Analytics: Build HMM",
            "build-minervini": "Analytics: Minervini",
            "build-gaf-daily": "Analytics: GAF Prediction (AI)",
            "build-tsmom-daily": "Analytics: TSMOM (Momentum)",
            "rebuild-reliability": "🎯 Update Reliability (Exp. Moves + Snapshots)",
            "build-volatility-struct": "Analytics: Volatility Term Structure",
            "update-everything": "⚡ Update Everything (Smart Incremental)"
        };
        return map[job] || job;
    };

    const StatusBadge = ({ status }) => {
        const s = (status || "pending").toUpperCase();
        let color = '#999';
        if (s === 'COMPLETED') color = '#4caf50';
        else if (s === 'RUNNING') color = '#2196f3';
        else if (s === 'FAILED') color = '#f44336';
        else if (s === 'PARTIAL') color = '#ff9800';
        else if (s === 'SKIPPED') color = '#777';
        return <span style={{ color, fontWeight: 'bold', fontSize: '12px' }}>{s}</span>;
    };

    const MarketPipeline = ({ status, jobs, triggerJob, selectedJob, setSelectedJob, loadingJob }) => {
        // Parse logs to find latest stage statuses if not directly provided in status object
        // Actually the backend `JobTracker` updates `status` object which SystemProgressBar uses.
        // We probably need a better way to get per-stage status for Market Pipeline similar to Economic.
        // `get_audit_logger().get_job_status()` returns the full JSON.
        // The `/api/v1/system/status` endpoint returns `JobTracker` status which is simple progress.
        // We might need to fetch the actual audit log for detailed stages?
        // For now, let's assume we can add a new endpoint or just parse the simple status if it has stages.
        // Wait, `SystemProgressBar` uses `/api/v1/system/status`.
        // `EconomicPipeline` uses `/api/v1/admin/data/economic/status`.
        // We need an endpoint for Market Pipeline details.
        // But for now, let's just keep the controls and add a visual list of stages that marks them as pending/done based on job progress.

        // Let's rely on the user manually checking logs for now, OR better:
        // visualize the defined stages and if the progress > X, we assume Y is done? No that's brittle.
        // Let's use the layout requested but keep it simple.

        const PHASES = [
            {
                id: "ingestion",
                label: "Phase 1: Ingestion",
                steps: [
                    { name: "Update Raw Data", job: "update-raw" },
                    { name: "Download Daily Options (Flat File)", job: "fetch-options" },
                    { name: "Extract Options Tickers", job: "fetch-options" }
                ]
            },
            {
                id: "features",
                label: "Phase 2: Features",
                steps: [
                    { name: "Update Features", job: "build-features" }
                ]
            },
            {
                id: "analytics",
                label: "Phase 3: Analytics",
                steps: [
                    { name: "SOA/EMA Stack", job: "update-everything" },
                    { name: "Seasonality", job: "update-seasonality" },
                    { name: "Markov Grid", job: "build-markov-grid" },
                    { name: "HMM Grid", job: "build-hmm-grid" },
                    { name: "Expected Moves", job: "update-expected-moves" },
                    { name: "GEX", job: "build-gex" },
                    { name: "GEX Archive", job: "build-gex" }, // Part of GEX flow now
                    { name: "TSMOM", job: "build-tsmom-daily" },
                    { name: "GAF", job: "build-gaf-daily" }
                ]
            },
            {
                id: "reporting",
                label: "Phase 4: Reporting",
                steps: [
                    { name: "AI Context Generation", job: "update-everything" },
                    { name: "Publish Analytics Data", job: "update-everything" }
                ]
            }
        ];

        return (
            <div className="flex flex-col h-full">
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-6">
                    {PHASES.map(phase => (
                        <div key={phase.id} className="bg-[#0e1525] rounded-lg border border-gray-800 overflow-hidden">
                            <div className="bg-[#1a2639] px-4 py-2 font-bold text-gray-200 text-sm uppercase tracking-wide border-b border-gray-800">
                                {phase.label}
                            </div>
                            <div className="p-2">
                                {phase.steps.map((step, idx) => (
                                    <div key={idx} className="flex justify-between items-center py-2 px-2 border-b border-gray-800/50 last:border-0 hover:bg-white/5 transition-colors">
                                        <div className="flex items-center gap-2">
                                            <div className={`w-1.5 h-1.5 rounded-full ${step.name.includes("Archive") ? "bg-purple-500" : "bg-blue-500"}`}></div>
                                            <span className="text-gray-400 text-xs font-medium">{step.name}</span>
                                        </div>
                                        {/* Placeholder status since we don't have granular stream yet */}
                                        <span className="text-[10px] text-gray-600 font-mono">PENDING</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Controls & Logs (Existing functionality wrapped) */}
                <div className="flex-1 flex flex-col min-h-0 bg-[#0e1525] rounded-lg border border-gray-800 p-4">
                    <div className="shrink-0 flex flex-col items-center gap-4 mx-auto w-full max-w-lg mb-4">
                        <h3 className="text-gray-400 text-sm uppercase font-bold tracking-widest">Pipeline Controls</h3>
                        <div className="flex w-full gap-4">
                            <select
                                className="flex-1 bg-[#1f2833] text-gray-200 border border-gray-600 rounded px-4 py-2 focus:outline-none focus:border-[#66fcf1]"
                                value={selectedJob}
                                onChange={(e) => setSelectedJob(e.target.value)}
                                disabled={status.running || loadingJob}
                            >
                                <option value="" disabled>Select Action...</option>
                                {jobs.map(job => (
                                    <option key={job} value={job}>{getJobLabel(job)}</option>
                                ))}
                            </select>

                            <button
                                onClick={() => triggerJob(selectedJob)}
                                disabled={status.running || loadingJob || !selectedJob}
                                className={`
                                        px-6 py-2 rounded font-bold uppercase tracking-wider transition-all
                                        ${status.running || !selectedJob
                                        ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                                        : 'bg-[#66fcf1] text-[#0b0c10] hover:bg-[#45a29e] hover:shadow-[0_0_10px_rgba(102,252,241,0.5)]'
                                    }
                                    `}
                            >
                                {status.running ? "Running..." : "Run Script"}
                            </button>

                            <button
                                onClick={() => {
                                    if (window.confirm("Run Pipeline Health Check?")) triggerJob("test-pipeline");
                                }}
                                disabled={status.running}
                                className="px-4 py-2 rounded border border-gray-600 text-gray-400 font-bold uppercase tracking-wider hover:bg-gray-800 hover:text-white transition-all ml-2"
                            >
                                🩺 Test Health
                            </button>
                        </div>

                        <div className={`px-4 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${status.running ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-gray-700/50 text-gray-400 border border-gray-600/30'}`}>
                            {status.running ? "Global Status: Running" : "Global Status: Idle"}
                        </div>
                    </div>

                    {/* Log Viewer Container */}
                    <div className="flex justify-center w-full flex-1 min-h-0 relative">
                        <div className="absolute inset-0">
                            <LogViewer logs={status.logs} running={status.running} />
                        </div>
                    </div>
                </div>
            </div>
        );
    };



    // Filter relevant jobs
    const jobs = (status.available_jobs || []).filter(j => !['test-job'].includes(j));

    return (
        <div className="h-screen w-full flex flex-col bg-[#0b0c10] text-gray-200 font-sans overflow-hidden">
            {/* Top Bar with Tabs */}
            <div className="bg-[#1f2833] border-b border-[#1f2833] px-8 py-4 shadow-lg z-10 shrink-0">
                <div className="flex justify-between items-center mb-4">
                    <h1 className="text-2xl font-bold text-[#66fcf1] tracking-wide">
                        Data Pipelines
                    </h1>
                    {error && <span className="text-red-400 text-sm font-semibold">{error}</span>}
                </div>
                {/* Tabs */}
                <div className="flex gap-2">
                    <button
                        onClick={() => setActiveTab('market')}
                        className={`px-4 py-2 rounded-t font-medium transition-all ${activeTab === 'market'
                            ? 'bg-[#0b0c10] text-[#66fcf1] border-b-2 border-[#66fcf1]'
                            : 'bg-transparent text-gray-400 hover:text-gray-200'
                            }`}
                    >
                        Market Data Pipeline
                    </button>
                    <button
                        onClick={() => setActiveTab('economic')}
                        className={`px-4 py-2 rounded-t font-medium transition-all ${activeTab === 'economic'
                            ? 'bg-[#0b0c10] text-[#66fcf1] border-b-2 border-[#66fcf1]'
                            : 'bg-transparent text-gray-400 hover:text-gray-200'
                            }`}
                    >
                        Economic Pipeline
                    </button>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-h-0 bg-[#0b0c10] overflow-hidden">
                {activeTab === 'market' ? (
                    <div className="flex-1 flex flex-col min-h-0 p-6 gap-6 relative">
                        {/* --- PROGRESS BAR --- */}
                        <SystemProgressBar />

                        <MarketPipeline
                            status={status}
                            jobs={jobs}
                            triggerJob={triggerJob}
                            selectedJob={selectedJob}
                            setSelectedJob={setSelectedJob}
                            loadingJob={loadingJob}
                        />
                    </div>
                ) : (
                    <EconomicPipeline />
                )}
            </div>
        </div>
    );
};

export default DataPipelines;
