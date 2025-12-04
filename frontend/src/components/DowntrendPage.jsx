import React, { useState, useEffect } from 'react';
import DowntrendSignalHistory from './DowntrendSignalHistory';

const API_BASE = "/api/v1";

const DowntrendPage = () => {
    const [ticker, setTicker] = useState('SPY');
    const [timeRange, setTimeRange] = useState('1y');
    const [rowsPerPage, setRowsPerPage] = useState(50);
    const [historyData, setHistoryData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Fetch Data
    useEffect(() => {
        async function fetchData() {
            setLoading(true);
            setError(null);
            try {
                const response = await fetch(`${API_BASE}/dcs/history/${ticker}`);
                const json = await response.json();

                if (!response.ok) {
                    throw new Error(json.detail || 'Failed to fetch history');
                }
                setHistoryData(json.data);
            } catch (err) {
                console.error("DCS History Fetch Error:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        }
        fetchData();
    }, [ticker]);

    return (
        <div style={{ display: 'flex', gap: '20px', padding: '20px', height: 'calc(100vh - 60px)', overflow: 'hidden' }}>

            {/* Left Sidebar: Controls */}
            <div style={{
                width: '250px',
                flexShrink: 0,
                backgroundColor: '#0e1525',
                padding: '20px',
                borderRadius: '8px',
                border: '1px solid #203049',
                display: 'flex',
                flexDirection: 'column',
                gap: '20px'
            }}>
                <h3 style={{ color: '#9ec4ff', margin: '0 0 10px 0' }}>Signal History — Controls</h3>

                {/* Ticker Selector */}
                <div>
                    <label style={{ display: 'block', color: '#d7e3f3', marginBottom: '5px', fontSize: '13px' }}>Ticker</label>
                    <input
                        type="text"
                        value={ticker}
                        onChange={(e) => setTicker(e.target.value.toUpperCase())}
                        style={{ width: '100%', padding: '8px', backgroundColor: '#151d30', border: '1px solid #203049', color: '#d7e3f3', borderRadius: '4px' }}
                    />
                </div>

                {/* Time Range Selector */}
                <div>
                    <label style={{ display: 'block', color: '#d7e3f3', marginBottom: '5px', fontSize: '13px' }}>Time Range</label>
                    <select
                        value={timeRange}
                        onChange={(e) => setTimeRange(e.target.value)}
                        style={{ width: '100%', padding: '8px', backgroundColor: '#151d30', border: '1px solid #203049', color: '#d7e3f3', borderRadius: '4px' }}
                    >
                        <option value="1m">1 Month</option>
                        <option value="3m">3 Months</option>
                        <option value="6m">6 Months</option>
                        <option value="1y">1 Year</option>
                        <option value="5y">5 Years</option>
                        <option value="10y">10 Years</option>
                    </select>
                </div>

                {/* Rows Per Page Selector */}
                <div>
                    <label style={{ display: 'block', color: '#d7e3f3', marginBottom: '5px', fontSize: '13px' }}>Rows per page</label>
                    <select
                        value={rowsPerPage}
                        onChange={(e) => setRowsPerPage(parseInt(e.target.value))}
                        style={{ width: '100%', padding: '8px', backgroundColor: '#151d30', border: '1px solid #203049', color: '#d7e3f3', borderRadius: '4px' }}
                    >
                        <option value={50}>50</option>
                        <option value={100}>100</option>
                        <option value={200}>200</option>
                    </select>
                </div>

                {/* Download Button (Placeholder logic) */}
                <button
                    onClick={() => alert("CSV Download not implemented yet.")}
                    style={{ marginTop: 'auto', padding: '10px', backgroundColor: '#203049', border: '1px solid #4caf50', color: '#4caf50', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
                >
                    Download CSV
                </button>
            </div>

            {/* Main Content: Table */}
            <div style={{ flexGrow: 1, overflowY: 'auto', paddingRight: '10px' }}>
                <h2 style={{ fontSize: '1.8rem', marginTop: 0 }}>Signal History — {ticker} Signals & Contributions</h2>

                {loading && <p style={{ color: '#9e9e9e' }}>Loading history data...</p>}
                {error && <p style={{ color: '#f44336' }}>Error: {error}</p>}

                {!loading && !error && (
                    <DowntrendSignalHistory
                        data={historyData}
                        timeRange={timeRange}
                        rowsPerPage={rowsPerPage}
                    />
                )}
            </div>
        </div>
    );
};

export default DowntrendPage;
