import React, { useState, useEffect } from 'react';

// --- MOCK DATA ---
const mockSummary = [
    { ticker: 'SPY', expiry_type: 'ODTE', hit_rate_percent: 85.5, average_high_breach_dollars: 1.25, max_breach_percent: 2.1, total_records: 120 },
    { ticker: 'SPY', expiry_type: 'WEEKLY', hit_rate_percent: 92.0, average_high_breach_dollars: 2.50, max_breach_percent: 1.5, total_records: 45 },
    { ticker: 'QQQ', expiry_type: 'ODTE', hit_rate_percent: 78.0, average_high_breach_dollars: 3.10, max_breach_percent: 3.8, total_records: 115 },
    { ticker: 'QQQ', expiry_type: 'WEEKLY', hit_rate_percent: 88.5, average_high_breach_dollars: 4.20, max_breach_percent: 2.9, total_records: 42 },
];

const mockHistory = [
    {
        ticker: 'SPY', expiry_type: 'ODTE', timestamp: '2025-12-01T16:00:00', expiry_date: '2025-12-02',
        lower_range: 495.50, upper_range: 502.50, realized_ohlc: { close: 498.00 },
        closed_within_em: true, confidence_score_percent: 85
    },
    {
        ticker: 'SPY', expiry_type: 'ODTE', timestamp: '2025-12-02T16:00:00', expiry_date: '2025-12-03',
        lower_range: 498.00, upper_range: 505.00, realized_ohlc: { close: 506.50 },
        closed_within_em: false, confidence_score_percent: 45
    },
    {
        ticker: 'SPY', expiry_type: 'WEEKLY', timestamp: '2025-11-25T16:00:00', expiry_date: '2025-11-29',
        lower_range: 490.00, upper_range: 510.00, realized_ohlc: { close: 505.00 },
        closed_within_em: true, confidence_score_percent: 92
    },
    {
        ticker: 'QQQ', expiry_type: 'WEEKLY', timestamp: '2025-11-28T16:00:00', expiry_date: '2025-12-05',
        lower_range: 420.00, upper_range: 435.00, realized_ohlc: { close: 425.00 },
        closed_within_em: true, confidence_score_percent: 90
    },
    {
        ticker: 'IWM', expiry_type: 'ODTE', timestamp: '2025-12-03T16:00:00', expiry_date: '2025-12-04',
        lower_range: 210.00, upper_range: 215.00, realized_ohlc: { close: 209.50 },
        closed_within_em: false, confidence_score_percent: 30
    },
];

const InfoTooltip = ({ text }) => {
    const [show, setShow] = useState(false);
    return (
        <div style={{ position: 'relative', display: 'inline-block', marginLeft: '6px', cursor: 'help' }}
            onMouseEnter={() => setShow(true)}
            onMouseLeave={() => setShow(false)}>
            <div style={{
                width: '14px', height: '14px', borderRadius: '50%', border: '1px solid #666',
                color: '#666', fontSize: '10px', display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>?</div>
            {show && (
                <div style={{
                    position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)',
                    backgroundColor: '#2a2a2a', color: '#e0e0e0', padding: '10px', borderRadius: '6px',
                    fontSize: '11px', width: '220px', zIndex: 100, boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                    marginBottom: '8px', textAlign: 'center', border: '1px solid #444', lineHeight: '1.4'
                }}>
                    {text}
                    <div style={{
                        position: 'absolute', top: '100%', left: '50%', marginLeft: '-5px',
                        borderWidth: '5px', borderStyle: 'solid', borderColor: '#2a2a2a transparent transparent transparent'
                    }} />
                </div>
            )}
        </div>
    );
};

const EMReliabilityDashboard = () => {
    const [summaryData, setSummaryData] = useState([]);
    const [historyData, setHistoryData] = useState([]);

    // UI State
    const [availableTickers, setAvailableTickers] = useState([]);
    const [selectedTicker, setSelectedTicker] = useState('');
    const [selectedPeriod, setSelectedPeriod] = useState('ALL'); // ALL, ODTE, WEEKLY, MONTHLY
    const [loading, setLoading] = useState(true);

    // 1. Fetch Available Tickers on Mount
    useEffect(() => {
        const fetchTickers = async () => {
            try {
                const res = await fetch('/api/v1/tickers/Expected_Moves_Reliability');
                if (!res.ok) throw new Error('Failed to fetch tickers');
                const json = await res.json();
                const tickers = json.tickers || [];
                setAvailableTickers(tickers);
                if (tickers.length > 0) {
                    setSelectedTicker(tickers[0]);
                }
            } catch (err) {
                console.error("Error fetching tickers:", err);
                // Fallback for demo/dev if API fails
                setAvailableTickers(['SPY', 'QQQ', 'IWM']);
                setSelectedTicker('SPY');
            }
        };
        fetchTickers();
    }, []);

    // 2. Fetch Data when Ticker Changes
    // 2. Fetch Data when Ticker Changes
    useEffect(() => {
        if (!selectedTicker) return;

        const fetchData = async () => {
            setLoading(true);
            try {
                // Fetch Summary
                const summaryRes = await fetch(`/api/v1/expected_moves/reliability/summary`);
                if (summaryRes.ok) {
                    const summaryJson = await summaryRes.json();
                    setSummaryData(summaryJson);
                }

                // Fetch History
                const historyRes = await fetch(`/api/v1/expected_moves/reliability/history?ticker=${selectedTicker}`);
                if (historyRes.ok) {
                    const historyJson = await historyRes.json();
                    setHistoryData(historyJson);
                }
            } catch (err) {
                console.error("Error fetching data:", err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [selectedTicker]);

    // Helper for formatting currency
    const fmt = (val) => val ? `$${val.toFixed(2)}` : '-';
    // Helper for formatting date
    const fmtDate = (isoStr) => isoStr ? isoStr.split('T')[0] : '-';

    // Filter Logic
    // 1. Filter History by Ticker AND Period
    let filteredHistory = historyData.filter(r => {
        const matchTicker = r.ticker === selectedTicker;
        const matchPeriod = selectedPeriod === 'ALL' || r.expiry_type === selectedPeriod;
        return matchTicker && matchPeriod;
    });

    // 2. Sort by Date Descending (Newest First)
    filteredHistory.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    // 3. Pagination
    const [currentPage, setCurrentPage] = useState(1);
    const itemsPerPage = 10;
    const totalPages = Math.ceil(filteredHistory.length / itemsPerPage);

    // Reset page when filters change
    useEffect(() => {
        setCurrentPage(1);
    }, [selectedTicker, selectedPeriod]);

    const paginatedHistory = filteredHistory.slice(
        (currentPage - 1) * itemsPerPage,
        currentPage * itemsPerPage
    );

    // 4. Filter Summary by Ticker AND Period
    // If ALL is selected, show cards for all periods for this ticker.
    // If specific period is selected, show only that card.
    const filteredSummary = summaryData.filter(item => {
        const matchTicker = item.ticker === selectedTicker;
        const matchPeriod = selectedPeriod === 'ALL' || item.expiry_type === selectedPeriod;
        return matchTicker && matchPeriod;
    }).sort((a, b) => {
        const order = { 'ODTE': 1, 'WEEKLY': 2, 'MONTHLY': 3 };
        return (order[a.expiry_type] || 99) - (order[b.expiry_type] || 99);
    });

    return (
        <div style={{ padding: '20px', color: '#e0e0e0', fontFamily: 'Inter, sans-serif' }}>

            {/* --- HEADER & CONTROLS --- */}
            <div style={{ marginBottom: '30px', borderBottom: '1px solid #333', paddingBottom: '15px', display: 'flex', justifyContent: 'space-between', alignItems: 'end' }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: '24px', fontWeight: '600', color: '#fff' }}>
                        Expected Move Reliability
                    </h1>
                    <p style={{ margin: '5px 0 0', color: '#888', fontSize: '14px' }}>
                        Historical performance tracking and breach analysis.
                    </p>
                </div>

                {/* CONTROLS */}
                <div style={{ display: 'flex', gap: '15px' }}>
                    {/* Ticker Select */}
                    <div>
                        <label style={{ display: 'block', fontSize: '12px', color: '#888', marginBottom: '4px' }}>Ticker</label>
                        <select
                            value={selectedTicker}
                            onChange={(e) => setSelectedTicker(e.target.value)}
                            style={{
                                backgroundColor: '#1e1e1e', color: '#fff', border: '1px solid #444',
                                padding: '8px 12px', borderRadius: '4px', outline: 'none', minWidth: '100px', fontSize: '14px'
                            }}
                        >
                            {availableTickers.map(t => (
                                <option key={t} value={t}>{t}</option>
                            ))}
                        </select>
                    </div>

                    {/* Period Select */}
                    <div>
                        <label style={{ display: 'block', fontSize: '12px', color: '#888', marginBottom: '4px' }}>Period</label>
                        <select
                            value={selectedPeriod}
                            onChange={(e) => setSelectedPeriod(e.target.value)}
                            style={{
                                backgroundColor: '#1e1e1e', color: '#fff', border: '1px solid #444',
                                padding: '8px 12px', borderRadius: '4px', outline: 'none', minWidth: '100px', fontSize: '14px'
                            }}
                        >
                            <option value="ALL">All Periods</option>
                            <option value="ODTE">0DTE</option>
                            <option value="WEEKLY">Weekly</option>
                            <option value="MONTHLY">Monthly</option>
                        </select>
                    </div>
                </div>
            </div>

            {/* --- SUMMARY CARDS (GRID) --- */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
                gap: '20px',
                marginBottom: '40px'
            }}>
                {filteredSummary.length === 0 && !loading && (
                    <div style={{ color: '#888', fontStyle: 'italic' }}>No summary data for this selection.</div>
                )}
                {filteredSummary.map((item, idx) => {
                    const isHigh = item.hit_rate_percent >= 80;
                    const isLow = item.hit_rate_percent < 60;
                    const color = isHigh ? '#4caf50' : (isLow ? '#f44336' : '#ffeb3b');

                    return (
                        <div key={idx} style={{
                            backgroundColor: '#1e1e1e', borderRadius: '8px', padding: '20px',
                            border: '1px solid #333', boxShadow: '0 4px 6px rgba(0,0,0,0.3)'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                                <span style={{ fontWeight: 'bold', fontSize: '16px', color: '#fff' }}>
                                    {item.ticker} <span style={{ color: '#888', fontSize: '12px' }}>{item.expiry_type}</span>
                                </span>
                                <span style={{ fontSize: '12px', color: '#666' }}>N={item.total_records}</span>
                            </div>

                            <div style={{ marginBottom: '15px' }}>
                                <div style={{ fontSize: '12px', color: '#aaa', marginBottom: '4px' }}>Hit Rate</div>
                                <div style={{ fontSize: '32px', fontWeight: 'bold', color: color }}>
                                    {item.hit_rate_percent.toFixed(1)}%
                                </div>
                            </div>

                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                                <div>
                                    <div style={{ color: '#666', display: 'flex', alignItems: 'center' }}>
                                        Avg Excess
                                        <InfoTooltip text="Average dollar amount by which the price missed the expected range (when a breach occurred)." />
                                    </div>
                                    <div style={{ color: '#ddd' }}>${item.average_high_breach_dollars.toFixed(2)}</div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <div style={{ color: '#666', display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                                        Max Excess
                                        <InfoTooltip text="Largest % by which price exceeded the range. Formula: (Excess $ / Expected Move $) * 100" />
                                    </div>
                                    <div style={{ color: '#ddd' }}>{item.max_breach_percent.toFixed(1)}%</div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* --- HISTORICAL TABLE --- */}
            <div style={{ backgroundColor: '#1e1e1e', borderRadius: '8px', border: '1px solid #333', overflow: 'hidden' }}>

                {/* Table Header */}
                <div style={{ padding: '15px 20px', borderBottom: '1px solid #333', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ margin: 0, fontSize: '16px', color: '#fff' }}>
                        Historical Records ({selectedTicker} - {selectedPeriod})
                    </h3>
                    {/* Pagination Controls */}
                    {totalPages > 1 && (
                        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', fontSize: '12px' }}>
                            <button
                                disabled={currentPage === 1}
                                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                style={{ padding: '4px 8px', backgroundColor: '#333', border: 'none', borderRadius: '4px', color: '#fff', cursor: currentPage === 1 ? 'not-allowed' : 'pointer', opacity: currentPage === 1 ? 0.5 : 1 }}
                            >
                                Prev
                            </button>
                            <span style={{ color: '#888' }}>Page {currentPage} of {totalPages}</span>
                            <button
                                disabled={currentPage === totalPages}
                                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                style={{ padding: '4px 8px', backgroundColor: '#333', border: 'none', borderRadius: '4px', color: '#fff', cursor: currentPage === totalPages ? 'not-allowed' : 'pointer', opacity: currentPage === totalPages ? 0.5 : 1 }}
                            >
                                Next
                            </button>
                        </div>
                    )}
                </div>

                {/* Table Content */}
                <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                        <thead>
                            <tr style={{ backgroundColor: '#252525', color: '#888', textAlign: 'left' }}>
                                <th style={{ padding: '12px 20px', fontWeight: '500' }}>Type</th>
                                <th style={{ padding: '12px 20px', fontWeight: '500' }}>Calc Date</th>
                                <th style={{ padding: '12px 20px', fontWeight: '500' }}>Expiry Date</th>
                                <th style={{ padding: '12px 20px', fontWeight: '500' }}>Expected Move</th>
                                <th style={{ padding: '12px 20px', fontWeight: '500' }}>Expected Range</th>
                                <th style={{ padding: '12px 20px', fontWeight: '500' }}>Realized Close</th>
                                <th style={{ padding: '12px 20px', fontWeight: '500' }}>Confidence</th>
                                <th style={{ padding: '12px 20px', fontWeight: '500', textAlign: 'center' }}>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {paginatedHistory.length === 0 && (
                                <tr>
                                    <td colSpan="8" style={{ padding: '20px', textAlign: 'center', color: '#888' }}>
                                        No records found.
                                    </td>
                                </tr>
                            )}
                            {paginatedHistory.map((row, idx) => {
                                const isSuccess = row.closed_within_em;
                                const isPending = isSuccess === null || isSuccess === undefined;
                                const emPct = (row.expected_move_dollars / row.underlying_price) * 100;
                                return (
                                    <tr key={idx} style={{ borderBottom: '1px solid #2c2c2c' }}>
                                        <td style={{ padding: '12px 20px' }}>
                                            <span style={{ fontSize: '11px', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#333', color: '#aaa' }}>
                                                {row.expiry_type}
                                            </span>
                                        </td>
                                        <td style={{ padding: '12px 20px', color: '#ccc' }}>{fmtDate(row.timestamp)}</td>
                                        <td style={{ padding: '12px 20px', color: '#ccc' }}>{fmtDate(row.expiry_date)}</td>
                                        <td style={{ padding: '12px 20px', color: '#ccc' }}>
                                            {fmt(row.expected_move_dollars)} <span style={{ color: '#666', fontSize: '12px' }}>({emPct.toFixed(1)}%)</span>
                                        </td>
                                        <td style={{ padding: '12px 20px', color: '#ccc' }}>
                                            {fmt(row.lower_range)} - {fmt(row.upper_range)}
                                        </td>
                                        <td style={{ padding: '12px 20px', color: '#ccc' }}>
                                            {fmt(row.realized_close || row.realized_ohlc?.close)}
                                        </td>
                                        <td style={{ padding: '12px 20px' }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                <div style={{ flex: 1, height: '4px', backgroundColor: '#333', borderRadius: '2px', width: '60px' }}>
                                                    <div style={{
                                                        width: `${row.confidence_score_percent}%`, height: '100%', borderRadius: '2px',
                                                        backgroundColor: row.confidence_score_percent >= 80 ? '#4caf50' : (row.confidence_score_percent >= 40 ? '#ff9800' : '#f44336')
                                                    }} />
                                                </div>
                                                <span style={{ fontSize: '12px', color: '#888', minWidth: '80px' }}>
                                                    {row.confidence_score_percent}%
                                                    <span style={{ fontSize: '10px', marginLeft: '4px', color: row.confidence_score_percent >= 80 ? '#4caf50' : (row.confidence_score_percent >= 40 ? '#ff9800' : '#f44336') }}>
                                                        {row.confidence_score_percent >= 80 ? 'Calm' : (row.confidence_score_percent >= 40 ? 'Mod' : 'Panic')}
                                                    </span>
                                                </span>
                                            </div>
                                        </td>
                                        <td style={{ padding: '12px 20px', textAlign: 'center' }}>
                                            {isPending ? (
                                                <span style={{
                                                    padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: '600',
                                                    backgroundColor: 'rgba(158, 158, 158, 0.15)', color: '#9e9e9e'
                                                }}>
                                                    PENDING
                                                </span>
                                            ) : (
                                                <span style={{
                                                    padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: '600',
                                                    backgroundColor: isSuccess ? 'rgba(76, 175, 80, 0.15)' : 'rgba(244, 67, 54, 0.15)',
                                                    color: isSuccess ? '#66bb6a' : '#ef5350'
                                                }}>
                                                    {isSuccess ? 'WITHIN' : 'BREACH'}
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default EMReliabilityDashboard;
