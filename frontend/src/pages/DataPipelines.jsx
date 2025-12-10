import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const DataPipelines = () => {
    const [status, setStatus] = useState({ running: false, logs: '', available_jobs: [] });
    const [loadingJob, setLoadingJob] = useState(null);
    const [error, setError] = useState(null);
    const logEndRef = useRef(null);

    // Poll status every 2 seconds
    useEffect(() => {
        const fetchStatus = async () => {
            try {
                // Assuming Vite proxy works now or direct URL
                const res = await axios.get('/api/v1/system/jobs/status?lines=100');
                setStatus(res.data);
            } catch (err) {
                console.error("Failed to fetch status", err);
            }
        };

        fetchStatus();
        const interval = setInterval(fetchStatus, 2000);
        return () => clearInterval(interval);
    }, []);

    // Auto-scroll logs
    useEffect(() => {
        if (logEndRef.current) {
            logEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [status.logs]);

    const triggerJob = async (jobName) => {
        setLoadingJob(jobName);
        setError(null);
        try {
            await axios.post(`/api/v1/system/jobs/${jobName}`);
            // Status poll will pick up the running state
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to start job");
        } finally {
            setLoadingJob(null);
        }
    };

    const getJobLabel = (job) => {
        const map = {
            "daily-pipeline": "Full Daily Pipeline (Orchestrator)",
            "update-raw": "Ingest: Update Raw Prices",
            "fetch-options": "Ingest: Fetch Options Snapshot",
            "build-features": "Features: Update (Incremental)",
            "rebuild-features": "Features: Rebuild All (Full)",
            "build-gex": "Analytics: Build GEX",
            "update-expected-moves": "Analytics: expected Moves"
        };
        return map[job] || job;
    };

    return (
        <div className="p-6 bg-gray-900 min-h-screen text-gray-100 font-sans">
            <header className="mb-8">
                <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
                    Data Pipelines & System Status
                </h1>
                <p className="text-gray-400 mt-2">Manage backend data ingestion and analytics jobs.</p>
            </header>

            {error && (
                <div className="bg-red-900/50 border border-red-500 text-red-200 p-4 rounded mb-6">
                    {error}
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Control Panel */}
                <div className="lg:col-span-1 bg-gray-800 rounded-xl p-6 shadow-lg border border-gray-700">
                    <h2 className="text-xl font-semibold mb-4 text-blue-300">Available Jobs</h2>

                    <div className="space-y-3">
                        {status.available_jobs.map(job => (
                            <div key={job} className="flex flex-col">
                                <button
                                    onClick={() => triggerJob(job)}
                                    disabled={status.running || loadingJob === job}
                                    className={`
                            px-4 py-3 rounded-lg text-left font-medium transition-all
                            ${status.running
                                            ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                                            : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/20'}
                        `}
                                >
                                    {loadingJob === job ? "Starting..." : getJobLabel(job)}
                                </button>
                            </div>
                        ))}
                    </div>

                    <div className="mt-6 pt-6 border-t border-gray-700">
                        <div className="flex items-center justify-between">
                            <span className="text-gray-400">System State:</span>
                            <span className={`px-3 py-1 rounded-full text-sm font-bold ${status.running ? 'bg-green-900 text-green-300 animate-pulse' : 'bg-gray-700 text-gray-300'}`}>
                                {status.running ? "RUNNING" : "IDLE"}
                            </span>
                        </div>
                    </div>
                </div>

                {/* Console Output */}
                <div className="lg:col-span-2 bg-gray-950 rounded-xl p-0 shadow-lg border border-gray-800 flex flex-col h-96">
                    <div className="bg-gray-900 px-4 py-2 rounded-t-xl border-b border-gray-800 flex justify-between items-center">
                        <span className="text-sm font-mono text-gray-400">Console Output ({status.logs.length > 0 ? "Live" : "No Logs"})</span>
                        <span className="text-xs text-gray-600">Auto-refreshing...</span>
                    </div>
                    <div className="flex-1 overflow-auto p-4 font-mono text-xs text-green-400 leading-relaxed whitespace-pre font-medium">
                        {status.logs || "Waiting for logs..."}
                        <div ref={logEndRef} />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default DataPipelines;
