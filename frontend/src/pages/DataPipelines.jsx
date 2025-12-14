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

const DataPipelines = () => {
    const [status, setStatus] = useState({ running: false, logs: '', available_jobs: [] });
    const [loadingJob, setLoadingJob] = useState(null);
    const [selectedJob, setSelectedJob] = useState(""); // Track selected dropdown option
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
            "rebuild-reliability": "🎯 Update Reliability (Exp. Moves + Snapshots)"
        };
        return map[job] || job;
    };

    // Filter relevant jobs to show in toolbar
    const jobs = (status.available_jobs || []).filter(j => !['test-job'].includes(j));

    return (
        <div className="h-screen w-full flex flex-col bg-[#0b0c10] text-gray-200 font-sans overflow-hidden">
            {/* Top Bar - Fixed Height */}
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

            {/* Main Content Area - Flex Grow */}
            <div className="flex-1 flex flex-col min-h-0 p-6 gap-6 relative">

                {/* 1. Job Controls Toolbar - Fixed Height */}
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

                {/* 2. Log Viewer Container - Centered */}
                <div className="flex justify-center w-full">
                    <LogViewer logs={status.logs} running={status.running} />
                </div>

            </div>
        </div>
    );
};

export default DataPipelines;
