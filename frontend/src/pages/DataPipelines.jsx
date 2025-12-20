import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

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

    // Syntax Highlighting Logic
    const formatLogOutput = (rawText) => {
        if (!rawText) return "";
        let formatted = rawText
            .replace(/ERROR/g, '<span class="log-error">ERROR</span>')
            .replace(/FAIL/g, '<span class="log-error">FAIL</span>')
            .replace(/WARNING/g, '<span class="log-warn">WARNING</span>')
            .replace(/INFO/g, '<span class="log-info">INFO</span>');

        // Highlight Timestamps (YYYY-MM-DD HH:MM:SS)
        formatted = formatted.replace(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/g, '<span class="log-timestamp">$1</span>');
        return formatted;
    };

    return (
        <div
            id="log-container"
            className="terminal-window"
            dangerouslySetInnerHTML={{ __html: formatLogOutput(logs || "Waiting for logs...") }}
        >
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
    const [status, setStatus] = useState({ running: false, logs: '', available_jobs: [] });
    // ... (rest of existing state)
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

    // Filter relevant jobs
    const jobs = (status.available_jobs || []).filter(j => !['test-job'].includes(j));

    return (
        <div className="h-screen w-full flex flex-col bg-[#0b0c10] text-gray-200 font-sans overflow-hidden">
            {/* Top Bar */}
            <div className="bg-[#1f2833] border-b border-[#1f2833] px-8 py-4 flex justify-between items-center shadow-lg z-10 shrink-0">
                <div className="flex items-center gap-4">
                    <h1 className="text-2xl font-bold text-[#66fcf1] tracking-wide">
                        System Pipelines
                    </h1>
                    <div className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${status.running ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-gray-700/50 text-gray-400 border border-gray-600/30'}`}>
                        {status.running ? "Running" : "Idle"}
                    </div>
                </div>
                {error && <span className="text-red-400 text-sm font-semibold">{error}</span>}
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-h-0 p-6 gap-6 relative">

                {/* --- PROGRESS BAR --- */}
                <SystemProgressBar />

                {/* Job Controls Toolbar */}
                <div className="shrink-0 flex flex-col items-center gap-4 mx-auto w-full max-w-lg">

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
                    </div>

                    <div className={`px-4 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${status.running ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-gray-700/50 text-gray-400 border border-gray-600/30'}`}>
                        {status.running ? "Status: Running" : "Status: Idle"}
                    </div>
                </div>

                {/* Log Viewer Container */}
                <div className="flex justify-center w-full flex-1 min-h-0">
                    <LogViewer logs={status.logs} running={status.running} />
                </div>

            </div>
        </div>
    );
};

export default DataPipelines;
