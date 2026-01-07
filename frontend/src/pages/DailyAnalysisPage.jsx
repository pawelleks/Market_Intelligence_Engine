import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';

const DailyAnalysisPage = () => {
    const [report, setReport] = useState(null);
    const [context, setContext] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showContext, setShowContext] = useState(true);

    useEffect(() => {
        fetch('/api/v1/ai-report')
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    setReport(data.data);
                    setContext(data.context);
                } else {
                    setError(data.message || data.error || 'Failed to load report');
                }
                setLoading(false);
            })
            .catch(err => {
                setError(err.message);
                setLoading(false);
            });
    }, []);

    if (loading) return <div style={{ padding: '40px', textAlign: 'center', color: '#889' }}>Loading Daily Intelligence...</div>;

    if (error) return (
        <div style={{ padding: '40px', textAlign: 'center', color: '#ff6b6b' }}>
            <h3>Unable to Load Analysis</h3>
            <p>{error}</p>
        </div>
    );

    if (!report) return <div style={{ padding: '40px', textAlign: 'center' }}>No report available. (Run generate-ai-report CLI)</div>;

    const { scorecard, content, date, ticker } = report;
    const { signal, conviction, regime } = scorecard || {};

    // Helper for colors
    const getSignalColor = (s) => {
        const sl = (s || "").toLowerCase();
        if (sl.includes("long") || sl.includes("bull")) return "#4caf50";
        if (sl.includes("short") || sl.includes("bear")) return "#f44336";
        return "#9e9e9e"; // Neutral
    };

    return (
        <div style={{ padding: '20px', color: '#d7e3f3', maxWidth: '1200px', margin: '0 auto', fontFamily: 'Inter, sans-serif' }}>
            {/* Header Area */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #2d3748', paddingBottom: '20px', marginBottom: '30px' }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: '28px', fontWeight: 600, letterSpacing: '-0.5px' }}>Daily Market Intelligence</h1>
                    <div style={{ color: '#94a3b8', fontSize: '14px', marginTop: '5px' }}>Date: <span style={{ color: '#fff' }}>{date}</span> • Asset: <span style={{ color: '#fff' }}>{ticker}</span></div>
                </div>

                {/* Scorecard Badges */}
                <div style={{ display: 'flex', gap: '20px' }}>
                    <StatusCard label="Signal" value={signal} color={getSignalColor(signal)} />
                    <ConvictionCard value={conviction} />
                    <StatusCard label="Regime" value={regime} color="#fbbf24" subColor="#92400e" />
                </div>
            </div>

            {/* Collapsible Market State Vector (Context) */}
            {context && (
                <div style={{ marginBottom: '30px' }}>
                    <button
                        onClick={() => setShowContext(!showContext)}
                        style={{
                            background: '#1e293b',
                            color: '#94a3b8',
                            border: '1px solid #334155',
                            padding: '10px 20px',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            fontSize: '14px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                            transition: 'all 0.2s',
                            width: '100%',
                            justifyContent: 'space-between'
                        }}
                    >
                        <span style={{ fontWeight: 600, color: '#e2e8f0' }}>🔍 Market State Vector (AI Input Data)</span>
                        <span>{showContext ? '▲ Hide' : '▼ Show Details'}</span>
                    </button>

                    {showContext && (
                        <div style={{
                            marginTop: '10px',
                            background: '#0f172a',
                            borderRadius: '12px',
                            border: '1px solid #1e293b',
                            padding: '24px',
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                            gap: '20px'
                        }}>
                            {/* Technicals */}
                            <ContextGroup title="Price & Trend">
                                <DataRow label="Close" value={`$${context.price?.close}`} />
                                <DataRow label="EMA Stack" value={context.trend?.ema_stack?.verdict} />
                                <DataRow label="ADX" value={`${context.trend?.adx?.val} (${context.trend?.adx?.trend_strength})`} />
                                <DataRow label="Ichimoku" value={context.trend?.ichimoku?.status} />
                                <DataRow label="vs 52W High" value={context.price?.dist_52w_high_label} color={context.price?.dist_52w_high_pct?.startsWith('-') ? '#f44336' : '#4caf50'} />
                                <DataRow label="52W Range" value={`$${context.price?.['52w_low']} - $${context.price?.['52w_high']}`} />
                            </ContextGroup>

                            {/* Regime & Vol */}
                            <ContextGroup title="Regime & Volatility">
                                <DataRow label="HMM State" value={context.regime?.hmm?.desc} color="#fbbf24" />
                                <DataRow label="Vol Regime" value={context.regime?.vol?.regime} />
                                <DataRow label="ATR (14)" value={context.regime?.vol?.atr_14} />
                                <DataRow label="ATR Rank" value={context.regime?.vol?.rank_6m} />
                                <DataRow label="DCS Status" value={context.trend?.dcs?.status} color={context.trend?.dcs?.score > 50 ? '#f44336' : '#4caf50'} />
                            </ContextGroup>

                            {/* Options & Sentiment */}
                            <ContextGroup title="Options & Sentiment">
                                <DataRow label="Net GEX" value={context.options?.gex?.net_regime} />
                                <DataRow label="Call Wall" value={context.options?.gex?.call_wall_dist} />
                                <DataRow label="Put Wall" value={context.options?.gex?.put_wall_dist} />
                                <DataRow label="PCR (Vol)" value={context.options?.sentiment?.pcr_vol} />
                                <DataRow label="0DTE Expected" value={context.options?.exp_moves?.['0dte_range']} />
                            </ContextGroup>

                            {/* Seasonality */}
                            <ContextGroup title="Seasonality">
                                <DataRow label="Next Day" value={context.seasonality?.next_day} />
                                <DataRow label="Next Week" value={context.seasonality?.next_week} />
                                <DataRow label="TSMOM Signal" value={context.trend?.tsmom?.signal} />
                                <DataRow label="TSMOM 12M" value={context.trend?.tsmom?.['12m_return']} />
                            </ContextGroup>

                            {/* Performance */}
                            <ContextGroup title="Market Performance">
                                <DataRow label="1 Day" value={context.performance?.['1d']} color={context.performance?.['1d']?.startsWith('+') ? '#4caf50' : '#f44336'} />
                                <DataRow label="1 Week" value={context.performance?.['1w']} color={context.performance?.['1w']?.startsWith('+') ? '#4caf50' : '#f44336'} />
                                <DataRow label="1 Month" value={context.performance?.['1m']} color={context.performance?.['1m']?.startsWith('+') ? '#4caf50' : '#f44336'} />
                                <DataRow label="3 Months" value={context.performance?.['3m']} color={context.performance?.['3m']?.startsWith('+') ? '#4caf50' : '#f44336'} />
                                <DataRow label="6 Months" value={context.performance?.['6m']} color={context.performance?.['6m']?.startsWith('+') ? '#4caf50' : '#f44336'} />
                                <DataRow label="1 Year" value={context.performance?.['1y']} color={context.performance?.['1y']?.startsWith('+') ? '#4caf50' : '#f44336'} />
                            </ContextGroup>
                        </div>
                    )}
                </div>
            )}

            {/* Main Content Area */}
            <div className="report-markdown" style={{ background: '#0f172a', padding: '40px', borderRadius: '16px', border: '1px solid #1e293b', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}>
                <ReactMarkdown>{content}</ReactMarkdown>
            </div>

            <style>{`
                .report-markdown { color: #cbd5e1; font-size: 16px; line-height: 1.7; }
                .report-markdown h1 { color: #f8fafc; border-bottom: 2px solid #334155; padding-bottom: 0.3em; margin-top: 1.5em; margin-bottom: 1em; font-size: 2em; }
                .report-markdown h2 { color: #e2e8f0; margin-top: 1.5em; margin-bottom: 0.8em; font-size: 1.5em; }
                .report-markdown h3 { color: #94a3b8; margin-top: 1.5em; margin-bottom: 0.5em; font-size: 1.25em; text-transform: uppercase; letter-spacing: 0.05em; }
                .report-markdown p { margin-bottom: 1.2em; }
                .report-markdown ul { margin-bottom: 1.5em; padding-left: 1.5em; }
                .report-markdown li { margin-bottom: 0.5em; }
                .report-markdown strong { color: #fff; font-weight: 600; }
                .report-markdown blockquote { border-left: 4px solid #3b82f6; padding-left: 1em; margin-left: 0; color: #94a3b8; font-style: italic; }
            `}</style>
        </div>
    );
};

const ContextGroup = ({ title, children }) => (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
        <h4 style={{ margin: '0 0 12px 0', fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{title}</h4>
        <div style={{ background: '#0a0f1d', padding: '12px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            {children}
        </div>
    </div>
);

const DataRow = ({ label, value, color }) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #1e293b', fontSize: '13px' }}>
        <span style={{ color: '#94a3b8' }}>{label}</span>
        <span style={{ color: color || '#f8fafc', fontWeight: 500 }}>{value}</span>
    </div>
);

const StatusCard = ({ label, value, color }) => (
    <div style={{ background: '#1e293b', padding: '12px 24px', borderRadius: '12px', textAlign: 'center', minWidth: '120px', border: '1px solid #334155' }}>
        <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>{label}</div>
        <div style={{ color: color, fontWeight: '700', fontSize: '18px' }}>{value}</div>
    </div>
);

const ConvictionCard = ({ value }) => (
    <div style={{ background: '#1e293b', padding: '12px 24px', borderRadius: '12px', textAlign: 'center', minWidth: '140px', border: '1px solid #334155' }}>
        <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>Conviction</div>
        <div style={{ color: '#fff', fontWeight: '700', fontSize: '18px', marginBottom: '4px' }}>{value}%</div>
        <div style={{ width: '100%', height: '4px', background: '#334155', borderRadius: '2px', overflow: 'hidden' }}>
            <div style={{ width: `${value}%`, height: '100%', background: '#3b82f6', borderRadius: '2px', transition: 'width 1s ease-out' }}></div>
        </div>
    </div>
);

export default DailyAnalysisPage;
