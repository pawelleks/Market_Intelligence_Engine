
import React, { useState, useEffect } from 'react';

const AbctSignalHistory = ({ data }) => {
    // Data is passed from parent to avoid double fetching
    const [history, setHistory] = useState([]);

    // Regime Logic
    const getRegime = (score) => {
        if (score >= 2.0) return "Crack-up Boom";
        if (score > 0.0) return "Distorted";
        return "Sustainable";
    };

    const getRegimeColor = (regime) => {
        switch (regime) {
            case 'Crack-up Boom': return '#ef4444'; // Red
            case 'Distorted': return '#f97316'; // Orange
            case 'Sustainable': return '#22c55e'; // Green
            default: return '#9ca3af';
        }
    };

    useEffect(() => {
        if (!data || data.length === 0) return;

        const events = [];
        let currentRegime = null;
        let lastFlipDate = null;

        // Data is usually sorted by date in parent, but let's be safe or assume chronological
        // My main dashboard sorts it. Let's assume input is chronological or check.
        // If data comes from rechart formatted data, it might include date strings.

        // Ensure chronological order
        const sorted = [...data].sort((a, b) => new Date(a.date) - new Date(b.date));

        for (let i = 0; i < sorted.length; i++) {
            const row = sorted[i];
            const regime = getRegime(row.boom_score); // using boom_score alias

            if (i === 0) {
                currentRegime = regime;
                lastFlipDate = new Date(row.date);
                continue;
            }

            if (regime !== currentRegime) {
                const flipDate = new Date(row.date);

                // Duration
                const diffTime = Math.abs(flipDate - lastFlipDate);
                const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                let durationStr = `${diffDays} days`;

                if (diffDays > 365) {
                    durationStr = `${(diffDays / 365).toFixed(1)} years`;
                } else if (diffDays > 30) {
                    durationStr = `${(diffDays / 30).toFixed(1)} months`;
                }

                events.push({
                    date: row.date,
                    from: currentRegime,
                    to: regime,
                    duration: durationStr
                });

                currentRegime = regime;
                lastFlipDate = flipDate;
            }
        }

        setHistory(events.reverse());
    }, [data]);

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
        link.setAttribute("download", "abct_cycle_history.csv");
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    if (!data || data.length === 0) return null;

    return (
        <section style={{ marginTop: '48px', marginBottom: '48px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                    <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#fff', margin: 0 }}>Cycle History (Regime Shifts)</h2>
                    <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '4px' }}>
                        Chronological record of shifts between Organic Growth, Distortion, and Crack-up Booms.
                    </p>
                </div>
                <button
                    onClick={downloadCSV}
                    style={{
                        backgroundColor: '#1f2937', color: '#d1d5db', border: '1px solid #374151',
                        padding: '8px 16px', borderRadius: '4px', cursor: 'pointer', fontSize: '14px',
                        display: 'flex', alignItems: 'center', gap: '8px'
                    }}
                >
                    <span>Download CSV</span>
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
                            <tr key={idx} style={{ borderBottom: '1px solid rgba(55, 65, 81, 0.3)' }}>
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

            </div>
        </section>
    );
};

export default AbctSignalHistory;
