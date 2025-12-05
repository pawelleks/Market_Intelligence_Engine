import React, { useState, useEffect } from 'react';

const COMMON_TICKERS = [
    "SPY", "QQQ", "IWM", "DIA",
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
    "XLE", "XLF", "XLK", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",
    "SMH", "IGV", "XBI", "KRE"
].sort();

const MinerviniPage = ({ settings, setSettings }) => {
    const [templateData, setTemplateData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Use settings.ticker if available, otherwise default
    const ticker = settings?.ticker || "SPY";

    const handleTickerChange = (e) => {
        const newTicker = e.target.value;
        if (setSettings) {
            setSettings(prev => ({ ...prev, ticker: newTicker }));
        }
    };

    useEffect(() => {
        const fetchTemplate = async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await fetch(`/api/v1/template/minervini/${ticker}`);
                if (!res.ok) throw new Error("Failed to fetch template data");
                const json = await res.json();
                setTemplateData(json.results);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        if (ticker) fetchTemplate();
    }, [ticker]);

    const data = templateData?.data_status || {};
    const passCount = templateData?.total_passed;
    const isPass = templateData?.status === "PASS";
    const totalChecks = templateData?.required_passes || 7;

    // --- Subcomponents ---

    const CheckIcon = ({ passed }) => (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{
            color: passed ? '#4caf50' : '#444',
            marginRight: '12px',
            minWidth: '20px'
        }}>
            {passed ? (
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            ) : (
                <circle cx="12" cy="12" r="10"></circle>
            )}
            {passed && <polyline points="22 4 12 14.01 9 11.01" />}
        </svg>
    );

    const StatCard = ({ label, value }) => (
        <div style={{ backgroundColor: '#161b22', padding: '15px', borderRadius: '6px', flex: 1, border: '1px solid #30363d' }}>
            <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '5px' }}>{label}</div>
            <div style={{ color: '#c9d1d9', fontSize: '18px', fontWeight: '600' }}>{value}</div>
        </div>
    );

    const CheckItem = ({ index, label, passed }) => (
        <div style={{ display: 'flex', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid #21262d', color: '#c9d1d9' }}>
            <div style={{ marginRight: '10px' }}>
                {passed ? (
                    <span style={{ color: '#4caf50' }}>&#10004;</span>
                ) : (
                    <span style={{ color: '#fa7970' }}>?</span>
                )}
            </div>
            <div style={{ flex: 1 }}>
                <span style={{ color: '#8b949e', marginRight: '8px' }}>{index}.</span>
                {label}
            </div>
        </div>
    );

    return (
        <div style={{ display: 'flex', gap: '20px', padding: '20px', maxWidth: '1200px', margin: '0 auto', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif' }}>

            {/* Sidebar / Filters */}
            <div style={{ width: '280px', flexShrink: 0 }}>
                <div style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', overflow: 'hidden' }}>
                    <div style={{ padding: '12px 16px', borderBottom: '1px solid #30363d', fontWeight: 'bold', color: '#c9d1d9', backgroundColor: '#161b22' }}>
                        Trend Template Filters
                    </div>
                    <div style={{ padding: '16px' }}>
                        <label style={{ display: 'block', color: '#8b949e', fontSize: '12px', marginBottom: '8px' }}>Select Ticker</label>
                        <select
                            value={ticker}
                            onChange={handleTickerChange}
                            style={{
                                width: '100%',
                                padding: '8px',
                                backgroundColor: '#0d1117',
                                border: '1px solid #30363d',
                                color: '#c9d1d9',
                                borderRadius: '6px',
                                outline: 'none'
                            }}
                        >
                            {COMMON_TICKERS.map(t => (
                                <option key={t} value={t}>{t}</option>
                            ))}
                        </select>
                        <div style={{ marginTop: '10px', fontSize: '11px', color: '#8b949e' }}>
                            Or type manually (not implemented in simple select).
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div style={{ flex: 1 }}>
                {error && <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#3d1619', color: '#fa7970', borderRadius: '6px', border: '1px solid #ff4444' }}>{error}</div>}

                <div style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', overflow: 'hidden' }}>
                    {/* Header */}
                    <div style={{ padding: '20px', borderBottom: '1px solid #30363d', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h2 style={{ margin: 0, fontSize: '24px', color: '#c9d1d9' }}>
                            Minervini Trend Template: <span style={{ color: '#58a6ff' }}>{ticker}</span>
                        </h2>
                        {templateData && (
                            <div style={{
                                padding: '6px 16px',
                                borderRadius: '20px',
                                backgroundColor: isPass ? (passCount === 7 ? 'rgba(76, 175, 80, 0.25)' : 'rgba(255, 235, 59, 0.15)') : 'rgba(218, 54, 51, 0.15)',
                                color: isPass ? (passCount === 7 ? '#4caf50' : '#fdd835') : '#f85149',
                                border: isPass ? (passCount === 7 ? '1px solid rgba(76, 175, 80, 0.4)' : '1px solid rgba(255, 235, 59, 0.4)') : '1px solid rgba(218, 54, 51, 0.4)',
                                fontWeight: 'bold'
                            }}>
                                {templateData.status} ({passCount}/7)
                            </div>
                        )}
                    </div>

                    {loading ? (
                        <div style={{ padding: '40px', textAlign: 'center', color: '#8b949e' }}>Loading analysis...</div>
                    ) : templateData ? (
                        <div style={{ padding: '20px' }}>
                            {/* Stats */}
                            <div style={{ display: 'flex', gap: '20px', marginBottom: '30px' }}>
                                <StatCard label="Check Date" value={templateData.check_date} />
                                <StatCard label="Current Price" value={`$${templateData.current_price?.toFixed(2)}`} />
                            </div>

                            {/* Checklist */}
                            <h3 style={{ fontSize: '16px', color: '#58a6ff', marginBottom: '15px' }}>Technical Checklist</h3>
                            <div>
                                <CheckItem index="1" label="Current Price > 150-day SMA AND Price > 200-day SMA" passed={data.P_GT_MA} />
                                <CheckItem index="2" label="150-day SMA > 200-day SMA" passed={data.MA_150_GT_200} />
                                <CheckItem index="3" label="200-day SMA is trending up" passed={data.MA_200_RISING} />
                                <CheckItem index="4" label="50-day SMA > 150-day SMA AND 50-day SMA > 200-day SMA" passed={data.MA_50_GT_LONG} />
                                <CheckItem index="5" label="Current Price > 50-day SMA" passed={data.P_GT_MA_50} />
                                <CheckItem index="6" label="Current Price is within 25% of 52-week High" passed={data.CLOSE_TO_HIGH} />
                                <CheckItem index="7" label="Current Price is at least 30% above 52-week Low" passed={data.FAR_FROM_LOW} />
                            </div>

                            <div style={{ marginTop: '30px', padding: '15px', backgroundColor: '#161b22', borderRadius: '6px', fontSize: '13px', color: '#8b949e' }}>
                                <strong>Note:</strong> This template requires at least {templateData.required_passes} out of 7 technical criteria to pass. It is adapted for ETF trend following but applies to individual stocks as well.
                            </div>
                        </div>
                    ) : null}
                </div>
            </div>
        </div>
    );
};

export default MinerviniPage;
