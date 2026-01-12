import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

const FredPipeline = () => {
    const { token } = useAuth();
    const [statusData, setStatusData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [updating, setUpdating] = useState(false);
    const [message, setMessage] = useState(null);

    const fetchStatus = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/v1/admin/data/fred', {
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            });
            if (res.ok) {
                const json = await res.json();
                setStatusData(json.data || []);
            }
        } catch (error) {
            console.error("Error fetching FRED status:", error);
        } finally {
            setLoading(false);
        }
    };

    const runPipeline = async () => {
        setUpdating(true);
        setMessage(null);
        try {
            const res = await fetch('/api/v1/admin/data/fred/start', {
                method: 'POST',
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            });
            if (res.ok) {
                setMessage("Pipeline started successfully. Refresh status in a few moments.");
            } else {
                const json = await res.json();
                // Show more detailed error if available
                setMessage(`Failed to start pipeline: ${json.detail || json.message || res.status}`);
            }
        } catch (error) {
            console.error("Error starting pipeline:", error);
            setMessage("Error starting pipeline.");
        } finally {
            setUpdating(false);
            // Poll for status update after a few seconds
            setTimeout(fetchStatus, 5000);
        }
    };

    useEffect(() => {
        if (token) fetchStatus();
    }, [token]);

    return (
        <div style={{ padding: '20px', color: '#e0e0e0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3 style={{ margin: 0 }}>FRED Economic Data Pipeline</h3>
                <button
                    onClick={runPipeline}
                    disabled={updating}
                    style={{
                        padding: '10px 20px',
                        backgroundColor: updating ? '#64748b' : '#3b82f6',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: updating ? 'not-allowed' : 'pointer',
                        fontWeight: 'bold'
                    }}
                >
                    {updating ? "Updating..." : "Update FRED Data Only"}
                </button>
            </div>

            {message && (
                <div style={{ marginBottom: '20px', padding: '10px', backgroundColor: '#1e293b', border: '1px solid #3b82f6', borderRadius: '4px' }}>
                    {message}
                </div>
            )}

            <div style={{ backgroundColor: '#0f172a', borderRadius: '8px', overflow: 'hidden', border: '1px solid #1e293b' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                    <thead style={{ backgroundColor: '#1e293b', color: '#94a3b8', textAlign: 'left' }}>
                        <tr>
                            <th style={{ padding: '12px' }}>Series ID</th>
                            <th style={{ padding: '12px' }}>Description</th>
                            <th style={{ padding: '12px' }}>Status</th>
                            <th style={{ padding: '12px' }}>Data Range</th>
                            <th style={{ padding: '12px' }}>Last Updated</th>
                            <th style={{ padding: '12px' }}>Size</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            <tr><td colSpan="5" style={{ padding: '20px', textAlign: 'center', color: '#64748b' }}>Loading status...</td></tr>
                        ) : statusData.length === 0 ? (
                            <tr><td colSpan="5" style={{ padding: '20px', textAlign: 'center', color: '#64748b' }}>No data found.</td></tr>
                        ) : (
                            statusData.map((row) => (
                                <tr key={row.series_id} style={{ borderBottom: '1px solid #1e293b' }}>
                                    <td style={{ padding: '12px', fontWeight: 'bold' }}>{row.series_id}</td>
                                    <td style={{ padding: '12px', color: '#94a3b8' }}>{row.description}</td>
                                    <td style={{ padding: '12px' }}>
                                        <span style={{
                                            padding: '2px 8px',
                                            borderRadius: '12px',
                                            fontSize: '12px',
                                            backgroundColor: row.status === 'ok' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                            color: row.status === 'ok' ? '#34d399' : '#f87171'
                                        }}>
                                            {row.status.toUpperCase()}
                                        </span>
                                    </td>
                                    <td style={{ padding: '12px', color: '#e2e8f0', fontFamily: 'monospace' }}>{row.date_range || '-'}</td>
                                    <td style={{ padding: '12px', color: '#94a3b8' }}>{row.last_updated ? new Date(row.last_updated).toLocaleString() : '-'}</td>
                                    <td style={{ padding: '12px', color: '#94a3b8' }}>{row.size_bytes ? `${(row.size_bytes / 1024).toFixed(1)} KB` : '-'}</td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default FredPipeline;
