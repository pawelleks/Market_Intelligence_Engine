
import React, { useEffect, useState } from 'react';
import { BarChart2, TrendingUp, TrendingDown, Minus, Loader2, AlertTriangle, CheckCircle, Info } from 'lucide-react';

const VolumeRegimeReport = () => {
    const [reportData, setReportData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                // 1. Get Ticker List
                const tickersRes = await fetch('/api/v1/tickers');
                const tickersData = await tickersRes.json();
                const tickers = tickersData.tickers || [];

                // 2. Fetch Volume Analysis for each
                // We'll process them in parallel.
                const promises = tickers.map(async (ticker) => {
                    try {
                        const res = await fetch(`/api/v1/analytics/volume/${ticker}`);
                        if (!res.ok) return null;
                        return await res.json();
                    } catch (e) {
                        return null;
                    }
                });

                const results = await Promise.all(promises);
                // Filter out failures
                const validResults = results.filter(r => r !== null && !r.error);
                setReportData(validResults);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    const colors = {
        bg: '#0b1220',
        panelBg: '#0e1525',
        border: '#203049',
        text: '#d7e3f3',
        textMuted: '#9e9e9e',
        success: '#4caf50',
        danger: '#f44336',
        warning: '#ff9800',
        neutral: '#2196f3'
    };

    const getRatioColor = (ratio) => {
        if (ratio > 1.2) return colors.success;
        if (ratio < 0.8) return colors.danger;
        if (ratio < 1.0) return colors.warning;
        return colors.text; // 1.0 - 1.2 Neutral-ish
    };

    return (
        <div style={{ padding: '20px', backgroundColor: colors.bg, minHeight: '100vh', color: colors.text }}>

            {/* Header */}
            <div style={{ marginBottom: '30px', borderBottom: `1px solid ${colors.border}`, paddingBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <BarChart2 size={32} color={colors.neutral} />
                    <h1 style={{ margin: 0, fontSize: '28px', fontWeight: 'bold' }}>Volume Regime Analysis</h1>
                </div>
                <p style={{ marginTop: '10px', color: colors.textMuted, maxWidth: '800px' }}>
                    Market state classification based on 20-day Up/Down Volume Ratio and price action.
                    Identifies institutional accumulation, distribution, and capitulation signals.
                </p>
            </div>

            {/* Content */}
            {loading ? (
                <div style={{ textAlign: 'center', padding: '50px', color: colors.textMuted }}>
                    <Loader2 className="animate-spin" size={32} style={{ display: 'inline-block', marginBottom: '10px' }} />
                    <div>Analyzing all tracked tickers...</div>
                </div>
            ) : error ? (
                <div style={{ padding: '20px', color: colors.danger, border: `1px solid ${colors.danger}`, borderRadius: '8px' }}>
                    Error loading report: {error}
                </div>
            ) : (
                <div style={{ backgroundColor: colors.panelBg, borderRadius: '8px', border: `1px solid ${colors.border}`, overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '800px' }}>
                        <thead>
                            <tr style={{ backgroundColor: '#1a2639', borderBottom: `1px solid ${colors.border}`, textAlign: 'left' }}>
                                <th style={{ padding: '15px', color: colors.textMuted, fontWeight: '500', fontSize: '14px' }}>Ticker</th>
                                <th style={{ padding: '15px', color: colors.textMuted, fontWeight: '500', fontSize: '14px', textAlign: 'right' }}>Price</th>
                                <th style={{ padding: '15px', color: colors.textMuted, fontWeight: '500', fontSize: '14px', textAlign: 'center' }}>Vol Ratio (20d)</th>
                                <th style={{ padding: '15px', color: colors.textMuted, fontWeight: '500', fontSize: '14px' }}>Market State</th>
                                <th style={{ padding: '15px', color: colors.textMuted, fontWeight: '500', fontSize: '14px' }}>Analysis Conclusion</th>
                            </tr>
                        </thead>
                        <tbody>
                            {reportData.map((row, idx) => (
                                <tr key={row.ticker} style={{ borderBottom: idx === reportData.length - 1 ? 'none' : `1px solid ${colors.border}`, transition: 'background-color 0.2s' }}>
                                    {/* Ticker */}
                                    <td style={{ padding: '15px', fontWeight: 'bold', fontFamily: 'monospace', fontSize: '15px' }}>
                                        {row.ticker}
                                    </td>

                                    {/* Price */}
                                    <td style={{ padding: '15px', textAlign: 'right', fontFamily: 'monospace' }}>
                                        ${row.current_price?.toFixed(2) || "-"}
                                        <div style={{ fontSize: '11px', color: row.price_change_20d >= 0 ? colors.success : colors.danger }}>
                                            {row.price_change_20d >= 0 ? "+" : ""}{(row.price_change_20d * 100).toFixed(1)}% (20d)
                                        </div>
                                    </td>

                                    {/* Ratio */}
                                    <td style={{ padding: '15px', textAlign: 'center' }}>
                                        <div style={{
                                            display: 'inline-block',
                                            padding: '4px 8px',
                                            borderRadius: '4px',
                                            backgroundColor: 'rgba(0,0,0,0.2)',
                                            color: getRatioColor(row.current_ratio),
                                            fontWeight: 'bold',
                                            border: `1px solid ${getRatioColor(row.current_ratio)}40`
                                        }}>
                                            {row.current_ratio?.toFixed(2) || "N/A"}
                                        </div>
                                    </td>

                                    {/* State Badge */}
                                    <td style={{ padding: '15px' }}>
                                        <span style={{
                                            display: 'inline-flex',
                                            alignItems: 'center',
                                            gap: '6px',
                                            padding: '4px 10px',
                                            borderRadius: '12px',
                                            fontSize: '12px',
                                            fontWeight: '600',
                                            backgroundColor: row.market_state === 'Accumulation' ? `${colors.success}20` :
                                                row.market_state === 'Distribution' || row.market_state === 'Capitulation' ? `${colors.danger}20` :
                                                    row.market_state === 'Consolidation' ? `${colors.neutral}20` : `${colors.textMuted}20`,
                                            color: row.market_state === 'Accumulation' ? colors.success :
                                                row.market_state === 'Distribution' || row.market_state === 'Capitulation' ? colors.danger :
                                                    row.market_state === 'Consolidation' ? colors.neutral : colors.textMuted
                                        }}>
                                            {row.market_state}
                                        </span>
                                    </td>

                                    {/* Conclusion Text */}
                                    <td style={{ padding: '15px', color: '#e2e8f0', fontSize: '13px', lineHeight: '1.5' }}>
                                        {row.conclusion}
                                    </td>
                                </tr>
                            ))}
                            {reportData.length === 0 && (
                                <tr>
                                    <td colSpan={5} style={{ padding: '30px', textAlign: 'center', color: colors.textMuted }}>
                                        No data available. Ensure tickers are configured and raw data is present.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default VolumeRegimeReport;
