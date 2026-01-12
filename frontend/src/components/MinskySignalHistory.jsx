
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const MinskySignalHistory = () => {
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const res = await axios.get(`${API_BASE_URL}/minsky-market-data`);
                const { dates, indicators } = res.data;

                if (!dates || !indicators) throw new Error("Invalid data format");

                // Transform to Row-based
                const rows = dates.map((date, i) => ({
                    date,
                    minsky_regime: indicators.minsky_regime[i]
                }));

                // Logic 1: The "Flip" Detector
                const events = [];
                let currentRegime = null;
                let lastFlipDate = null;

                // Loop chronologically (oldest to newest)
                for (let i = 0; i < rows.length; i++) {
                    const row = rows[i];
                    const regime = row.minsky_regime;

                    if (i === 0) {
                        currentRegime = regime;
                        lastFlipDate = new Date(row.date);
                        continue;
                    }

                    if (regime !== currentRegime) {
                        // Flip detected
                        const flipDate = new Date(row.date);

                        // Calculate Duration of PREVIOUS regime
                        const diffTime = Math.abs(flipDate - lastFlipDate);
                        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                        let durationStr = `${diffDays} days`;

                        if (diffDays > 365) {
                            const years = (diffDays / 365).toFixed(1);
                            durationStr = `${years} years`;
                        } else if (diffDays > 30) {
                            const months = (diffDays / 30).toFixed(1);
                            durationStr = `${months} months`;
                        }

                        events.push({
                            date: row.date,
                            from: currentRegime,
                            to: regime,
                            duration: durationStr
                        });

                        // Update state
                        currentRegime = regime;
                        lastFlipDate = flipDate;
                    }
                }

                // Reverse for display (Newest First)
                setHistory(events.reverse());

            } catch (err) {
                console.error("Signal History Fetch Error:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    const downloadCSV = () => {
        if (history.length === 0) return;

        const headers = ["Date", "From", "To", "Duration"];
        const rows = history.map(h => [h.date, h.from, h.to, h.duration]);

        const csvContent = [
            headers.join(","),
            ...rows.map(e => e.join(","))
        ].join("\n");

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        const url = URL.createObjectURL(blob);
        link.setAttribute("href", url);
        link.setAttribute("download", "minsky_signal_history.csv");
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const getRegimeColor = (regime) => {
        switch (regime) {
            case 'Ponzi': return '#ef4444'; // Red
            case 'Speculative': return '#f97316'; // Orange
            case 'Hedge': return '#22c55e'; // Green
            default: return '#9ca3af'; // Gray
        }
    };

    if (loading) return <div style={{ padding: '20px', textAlign: 'center', color: '#6b7280' }}>Loading History...</div>;
    if (error) return null;
    if (history.length === 0) return null;

    return (
        <section style={{ marginTop: '48px', marginBottom: '48px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                    <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#fff', margin: 0 }}>Signal History</h2>
                    <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px' }}>
                        Chronological record of Minsky Regime changes.
                    </p>
                </div>
                <button
                    onClick={downloadCSV}
                    style={{
                        backgroundColor: '#1f2937', color: '#d1d5db', border: '1px solid #374151',
                        padding: '8px 16px', borderRadius: '4px', cursor: 'pointer', fontSize: '14px',
                        transition: 'background 0.2s',
                        display: 'flex', alignItems: 'center', gap: '8px'
                    }}
                    onMouseOver={(e) => e.target.style.backgroundColor = '#374151'}
                    onMouseOut={(e) => e.target.style.backgroundColor = '#1f2937'}
                >
                    <span>Download CSV</span>
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                </button>
            </div>

            <div style={{ overflowX: 'auto', backgroundColor: 'rgba(31, 41, 55, 0.5)', borderRadius: '8px', border: '1px solid rgba(55, 65, 81, 0.5)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
                    <thead>
                        <tr style={{ borderBottom: '1px solid #374151', backgroundColor: 'rgba(17, 24, 39, 0.5)' }}>
                            <th style={{ padding: '12px 16px', color: '#9ca3af', fontWeight: '500' }}>Date</th>
                            <th style={{ padding: '12px 16px', color: '#9ca3af', fontWeight: '500' }}>Signal Change</th>
                            <th style={{ padding: '12px 16px', color: '#9ca3af', fontWeight: '500' }}>Previous Duration</th>
                        </tr>
                    </thead>
                    <tbody>
                        {history.map((item, idx) => (
                            <tr key={idx} style={{ borderBottom: '1px solid rgba(55, 65, 81, 0.3)', transition: 'background 0.1s' }}>
                                <td style={{ padding: '12px 16px', color: '#e5e7eb', fontFamily: 'monospace' }}>
                                    {item.date.substring(0, 10)}
                                </td>
                                <td style={{ padding: '12px 16px' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        <span style={{
                                            display: 'inline-block',
                                            padding: '2px 8px', borderRadius: '12px',
                                            backgroundColor: `${getRegimeColor(item.from)}20`,
                                            color: getRegimeColor(item.from),
                                            fontSize: '12px', fontWeight: '500'
                                        }}>
                                            {item.from}
                                        </span>
                                        <span style={{ color: '#6b7280' }}>→</span>
                                        <span style={{
                                            display: 'inline-block',
                                            padding: '2px 8px', borderRadius: '12px',
                                            backgroundColor: `${getRegimeColor(item.to)}20`,
                                            color: getRegimeColor(item.to),
                                            fontSize: '12px', fontWeight: '500'
                                        }}>
                                            {item.to}
                                        </span>
                                    </div>
                                </td>
                                <td style={{ padding: '12px 16px', color: '#9ca3af' }}>
                                    {item.duration}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {history.length > 10 && (
                    <div style={{ padding: '12px', textAlign: 'center', color: '#6b7280', fontSize: '12px', borderTop: '1px solid #374151' }}>
                        Showing all {history.length} regime changes since 1993
                    </div>
                )}
            </div>
        </section>
    );
};

export default MinskySignalHistory;
