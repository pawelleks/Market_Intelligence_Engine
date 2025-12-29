import React, { useState, useEffect } from 'react';
import PerformanceTable from '../components/performance/PerformanceTable';

const API_BASE = '/api/v1/performance';

import { usePageTitle } from '../hooks/usePageTitle';

const PerformancePage = () => {
    usePageTitle('Market Performance');
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/snapshot`);
            if (!res.ok) {
                throw new Error(`API Error: ${res.status}`);
            }
            const json = await res.json();
            // Validate that json is an array
            if (Array.isArray(json)) {
                setData(json);
            } else {
                console.error("API did not return an array:", json);
                // Fallback or error
                setData([]);
                // Optional: setError("Invalid data format");
            }
        } catch (e) {
            console.error("Failed to fetch performance data", e);
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    return (
        <div style={{ padding: '20px', width: '100%', maxWidth: '1600px', margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h2 style={{ fontSize: '1.8rem', color: '#d7e3f3', margin: 0 }}>Market Performance</h2>
                <div style={{ fontSize: '0.9rem', color: '#68778d', textAlign: 'right' }}>
                    <div style={{ fontWeight: 'bold', color: '#90caf9' }}>
                        {data.length > 0 && data[0].asof_date ? `Data Date: ${data[0].asof_date}` : ''}
                    </div>
                    Live Snapshot (Calculated on-fly)
                </div>
            </div>

            {loading && <div style={{ color: '#aaa', padding: '20px' }}>Loading snapshot... calculation may take a moment...</div>}

            {error && (
                <div style={{ backgroundColor: '#ff525222', border: '1px solid #ff5252', borderRadius: '4px', padding: '15px', color: '#ff8a80', marginBottom: '20px' }}>
                    Error loading data: {error}
                </div>
            )}

            {!loading && !error && (
                <PerformanceTable data={data} />
            )}
        </div>
    );
};

export default PerformancePage;
