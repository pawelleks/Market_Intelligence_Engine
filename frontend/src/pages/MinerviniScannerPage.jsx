import React, { useState, useEffect } from 'react';

const MinerviniScannerPage = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showPerfectOnly, setShowPerfectOnly] = useState(false);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await fetch('/api/v1/scanner/minervini/latest');
                if (!res.ok) {
                    if (res.status === 404) throw new Error("No scan data found. Please run backend build.");
                    throw new Error("Failed to fetch scanner data");
                }
                const json = await res.json();
                setData(json);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return <div style={{ color: '#fff', padding: '20px' }}>Loading Scanner Data...</div>;
    if (error) return <div style={{ color: '#ff4444', padding: '20px' }}>Error: {error}</div>;

    // Filter logic
    const displayedData = showPerfectOnly
        ? data.data.filter(r => r.total_score === r.required_score)
        : data.data;

    // Sort by Total Score Descending
    displayedData.sort((a, b) => b.total_score - a.total_score);

    // Helper for Status Cell
    const StatusCell = ({ val, goodLabel = "TRUE", badLabel = "FALSE" }) => {
        const isGood = !!val;
        return (
            <td style={{
                textAlign: 'center',
                color: isGood ? '#4caf50' : '#444',
                fontWeight: isGood ? 'bold' : 'normal',
                backgroundColor: isGood ? 'rgba(76, 175, 80, 0.1)' : 'transparent'
            }}>
                {isGood ? '✔' : '✖'}
            </td>
        );
    };

    return (
        <div style={{ padding: '20px', backgroundColor: '#121212', minHeight: '100vh', color: '#e0e0e0', fontFamily: 'Inter, sans-serif' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div>
                    <h1 style={{ margin: 0, color: '#fff', fontSize: '24px' }}>Minervini Trend Template</h1>
                    <div style={{ fontSize: '14px', color: '#888', marginTop: '5px' }}>
                        Snapshot Date: {data.date} • Checked {data.count} Tickers
                    </div>
                </div>

                <div style={{ display: 'flex', backgroundColor: '#333', borderRadius: '6px', overflow: 'hidden' }}>
                    <button
                        onClick={() => setShowPerfectOnly(false)}
                        style={{
                            padding: '10px 20px',
                            backgroundColor: !showPerfectOnly ? '#58a6ff' : 'transparent',
                            color: !showPerfectOnly ? '#fff' : '#aaa',
                            border: 'none',
                            cursor: 'pointer',
                            fontWeight: 'bold',
                            transition: 'all 0.2s'
                        }}
                    >
                        Show All
                    </button>
                    <button
                        onClick={() => setShowPerfectOnly(true)}
                        style={{
                            padding: '10px 20px',
                            backgroundColor: showPerfectOnly ? '#4caf50' : 'transparent',
                            color: showPerfectOnly ? '#fff' : '#aaa',
                            border: 'none',
                            cursor: 'pointer',
                            fontWeight: 'bold',
                            transition: 'all 0.2s'
                        }}
                    >
                        7/7 Perfect
                    </button>
                </div>
            </div>

            <div style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid #333' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                    <thead style={{ backgroundColor: '#1e1e1e', color: '#aaa', textTransform: 'uppercase', fontSize: '12px' }}>
                        <tr>
                            <th style={{ padding: '12px', textAlign: 'left' }}>Ticker</th>
                            <th style={{ padding: '12px', textAlign: 'right' }}>Price</th>
                            <th style={{ padding: '12px', textAlign: 'center' }}>Score</th>
                            {/* Criteria Columns */}
                            <th style={{ padding: '12px', textAlign: 'center' }}>Price &gt; SMAs</th>
                            <th style={{ padding: '12px', textAlign: 'center' }}>150 &gt; 200</th>
                            <th style={{ padding: '12px', textAlign: 'center' }}>200 Trending</th>
                            <th style={{ padding: '12px', textAlign: 'center' }}>50 &gt; 150</th>
                            <th style={{ padding: '12px', textAlign: 'center' }}>Price &gt; 50</th>
                            <th style={{ padding: '12px', textAlign: 'center' }}>Low Clearance</th>
                            <th style={{ padding: '12px', textAlign: 'center' }}>High Proximity</th>
                        </tr>
                    </thead>
                    <tbody>
                        {displayedData.map(r => {
                            // Fix Logic: Perfect is 7/7. Pass is >= 6.
                            const totalChecks = 7;
                            const isPerfect = r.total_score === 7;
                            const isPass = r.status === "PASS"; // or r.total_score >= r.required_score

                            // Color Logic
                            // 7/7 -> Green
                            // 6/7 -> Yellow (Passing but not perfect) or maybe Light Green? 
                            // User complaint: "7/6 in yellow" -> 7 should be Green.
                            // User complaint: "6/6 in green" -> implies 6 was Green.
                            // Let's make 7 Green, 6 Yellow-Green, <6 Red.
                            // Actually, standard is usually: Pass = Green. Perfect = Gold/Bright Green.
                            // I will use Green for 7/7 and '#ffeb3b' (Yellow) for 6/7 to clearly distinguish, 
                            // OR keep 6 as Green but make 7 MORE Green? 
                            // User said: "7 out of 6 in yellow... 7/7 should give green". 
                            // It seems they want 7 to be the best color.

                            let valColor = '#ff4444'; // Fail
                            if (r.total_score === 7) valColor = '#4caf50'; // Perfect Green
                            else if (r.total_score >= 6) valColor = '#ffeb3b'; // Pass (6/7) Yellow/Gold

                            return (
                                <tr key={r.ticker} style={{
                                    borderBottom: '1px solid #222',
                                    backgroundColor: isPerfect ? 'rgba(76, 175, 80, 0.05)' : 'transparent',
                                    height: '40px'
                                }}>
                                    <td style={{ padding: '12px', fontWeight: 'bold', color: '#fff' }}>{r.ticker}</td>
                                    <td style={{ padding: '12px', textAlign: 'right', fontFamily: 'monospace' }}>${r.current_price?.toFixed(2)}</td>
                                    <td style={{
                                        padding: '12px',
                                        textAlign: 'center',
                                        fontWeight: 'bold',
                                        color: valColor
                                    }}>
                                        {r.total_score}/{totalChecks}
                                    </td>

                                    <StatusCell val={r.price_gt_smas} />
                                    <StatusCell val={r.sma150_gt_sma200} />
                                    <StatusCell val={r.sma200_trending} />
                                    <StatusCell val={r.sma50_gt_sma150} />
                                    <StatusCell val={r.price_gt_sma50} />
                                    <StatusCell val={r.price_gt_52w_low_25} />
                                    <StatusCell val={r.price_near_52w_high_25} />
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
                {displayedData.length === 0 && (
                    <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
                        No tickers match the current filter.
                    </div>
                )}
            </div>
        </div>
    );
};

export default MinerviniScannerPage;
