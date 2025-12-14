import React, { useState, useEffect } from 'react';
import SignalBox from '../components/tsmom/SignalBox';
import TsmomTable from '../components/tsmom/TsmomTable';
import TsmomChart from '../components/tsmom/TsmomChart';

const API_BASE = "/api/v1/tsmom";

const TsmomDashboardPage = () => {
    const [snapshotData, setSnapshotData] = useState([]);
    const [selectedTicker, setSelectedTicker] = useState(null);
    const [chartData, setChartData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [loadingChart, setLoadingChart] = useState(false);
    const [runStatus, setRunStatus] = useState("");

    // Filters
    const [trendFilter, setTrendFilter] = useState("ALL");
    const [signalFilter, setSignalFilter] = useState("ALL");

    // Filter Logic
    const filteredData = snapshotData.filter(row => {
        // Trend Filter
        if (trendFilter === "UP" && row.tsmom_dir != 1) return false;
        if (trendFilter === "DOWN" && row.tsmom_dir != -1) return false;

        // Signal Filter
        if (signalFilter === "ON" && !row.signal_changed) return false;
        if (signalFilter === "OFF" && row.signal_changed) return false;

        return true;
    });

    const fetchData = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/current`);
            if (res.ok) {
                const json = await res.json();
                setSnapshotData(json);
            }
        } catch (e) {
            console.error("Failed to load snapshot", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleTickerSelect = async (ticker) => {
        setSelectedTicker(ticker);
        setLoadingChart(true);
        try {
            const res = await fetch(`${API_BASE}/chart/${ticker}`);
            if (res.ok) {
                const json = await res.json();
                setChartData(json);
            }
        } catch (e) {
            console.error("Failed to load chart", e);
            setChartData(null);
        } finally {
            setLoadingChart(false);
        }
    };

    const handleRunUpdate = async () => {
        setRunStatus("Running...");
        try {
            const res = await fetch(`${API_BASE}/run`, { method: "POST" });
            if (res.ok) {
                setRunStatus("Update Triggered! Check back in a moment.");
                // Should probably refresh data after a delay or let user refresh
                setTimeout(fetchData, 3000);
            } else {
                setRunStatus("Failed to trigger update.");
            }
        } catch (e) {
            setRunStatus("Error: " + e.message);
        }
    };

    const latestSignalDate = snapshotData.reduce((max, row) => {
        if (!row.last_signal_date) return max;
        // Compare dates strings (ISO format sorts correctly)
        return row.last_signal_date > max ? row.last_signal_date : max;
    }, "");

    // Filter signals that happened on the latest date
    const latestSignals = snapshotData.filter(r => r.last_signal_date === latestSignalDate);

    return (
        <div style={{ padding: '20px', width: '100%', maxWidth: '1600px', margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h2 style={{ fontSize: '1.8rem', color: '#d7e3f3', margin: 0 }}>TSMOM Analytics</h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {runStatus && <span style={{ color: '#ffb74d', fontSize: '0.9rem' }}>{runStatus}</span>}
                    <button
                        onClick={handleRunUpdate}
                        style={{
                            backgroundColor: '#2962ff',
                            color: 'white',
                            border: 'none',
                            padding: '8px 16px',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontWeight: 'bold'
                        }}
                    >
                        Run Daily Update
                    </button>
                </div>
            </div>

            {loading ? (
                <div style={{ color: '#d7e3f3' }}>Loading Data...</div>
            ) : (
                <>
                    <SignalBox data={latestSignals} date={latestSignalDate} />

                    {/* Filter Controls Row */}
                    <div style={{ display: 'flex', gap: '20px', marginBottom: '10px', alignItems: 'center' }}>
                        {/* Display As-Of Date if available */}
                        {snapshotData.length > 0 && (
                            <div style={{ marginRight: 'auto', color: '#9ec4ff', fontWeight: 'bold' }}>
                                Data Date: {snapshotData[0].asof_date}
                            </div>
                        )}

                        <select
                            value={trendFilter}
                            onChange={(e) => setTrendFilter(e.target.value)}
                            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #203049', backgroundColor: '#0e1525', color: '#d7e3f3' }}
                        >
                            <option value="ALL">Trend: All</option>
                            <option value="UP">Trend: Up</option>
                            <option value="DOWN">Trend: Down</option>
                        </select>

                        <select
                            value={signalFilter}
                            onChange={(e) => setSignalFilter(e.target.value)}
                            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #203049', backgroundColor: '#0e1525', color: '#d7e3f3' }}
                        >
                            <option value="ALL">Signal: All</option>
                            <option value="ON">Signal: On (Changed)</option>
                            <option value="OFF">Signal: Off (Unchanged)</option>
                        </select>
                    </div>

                    <div style={{ display: 'flex', gap: '20px', marginTop: '10px', flexDirection: 'column' }}>
                        {/* Chart Section */}
                        {/* Chart Section */}
                        {selectedTicker && (
                            <div style={{ flex: 1 }}>
                                {loadingChart ? (
                                    <div style={{ color: '#68778d' }}>Loading Chart for {selectedTicker}...</div>
                                ) : (
                                    <>
                                        {/* Ticker Status Card */}
                                        {(() => {
                                            const row = snapshotData.find(r => r.ticker === selectedTicker);
                                            if (!row) return null;

                                            const isDivergent = row.theoretical_signal !== 0 && row.theoretical_signal !== row.tsmom_dir;
                                            const posColor = row.tsmom_dir === 1 ? '#4caf50' : (row.tsmom_dir === -1 ? '#f44336' : '#9e9e9e');
                                            const posText = row.tsmom_dir === 1 ? 'LONG' : (row.tsmom_dir === -1 ? 'SHORT' : 'NEUTRAL');

                                            return (
                                                <div style={{
                                                    backgroundColor: '#1b263b',
                                                    padding: '15px',
                                                    borderRadius: '8px',
                                                    marginBottom: '15px',
                                                    border: '1px solid #203049',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '20px',
                                                    flexWrap: 'wrap'
                                                }}>
                                                    <div>
                                                        <div style={{ color: '#68778d', fontSize: '0.8rem', textTransform: 'uppercase' }}>Current Position</div>
                                                        <div style={{ color: posColor, fontWeight: 'bold', fontSize: '1.2rem' }}>{posText}</div>
                                                    </div>

                                                    <div>
                                                        <div style={{ color: '#68778d', fontSize: '0.8rem', textTransform: 'uppercase' }}>Next Rebalance</div>
                                                        <div style={{ color: '#d7e3f3', fontWeight: 'bold' }}>{row.next_rebalance_date || "Month End"}</div>
                                                    </div>

                                                    {isDivergent && (
                                                        <div style={{
                                                            backgroundColor: '#ff980022',
                                                            border: '1px solid #ff9800',
                                                            padding: '8px 12px',
                                                            borderRadius: '4px',
                                                            color: '#ff9800',
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            gap: '8px'
                                                        }}>
                                                            <span>⚠️ Intra-month divergence - Holding until month-end</span>
                                                        </div>
                                                    )}

                                                    <div style={{ marginLeft: 'auto', color: '#68778d', fontSize: '0.8rem', maxWidth: '300px', textAlign: 'right' }}>
                                                        ℹ️ Signals are evaluated only on the last trading day of the month to reduce noise.
                                                    </div>
                                                </div>
                                            );
                                        })()}

                                        <TsmomChart ticker={selectedTicker} chartData={chartData} />
                                    </>
                                )}
                            </div>
                        )}

                        {/* Table Section */}
                        <div style={{ flex: 1 }}>
                            <TsmomTable data={filteredData} onTickerSelect={handleTickerSelect} />
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export default TsmomDashboardPage;
