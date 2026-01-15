import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
    ResponsiveContainer, ReferenceLine, ComposedChart, Brush, Area
} from 'recharts';
import { ChevronDown, ChevronUp, Info, Activity, Users, Wallet, CreditCard, AlertTriangle } from 'lucide-react';
import RecessionOverlay from './common/RecessionOverlay';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';
const formatNumber = (val, decimals = 3) => {
    if (val === null || val === undefined || isNaN(val)) return '0.000';
    return Number(val).toFixed(decimals);
};

const getLagStatus = (lagValue) => {
    if (lagValue > 1.0) {
        return {
            status: 'TROUBLE',
            color: '#ef4444',
            bgColor: 'rgb(153, 27, 27)',
            text: 'PEAK CONFIRMED',
            icon: '🔴',
            description: 'Lagging indicators confirm cycle peak. Recession likely started or imminent.'
        };
    } else if (lagValue > 0.5) {
        return {
            status: 'WARNING',
            color: '#f59e0b',
            bgColor: 'rgb(120, 53, 15)',
            text: 'LATE CYCLE',
            icon: '🟡',
            description: 'Peak formation. Lagging indicators reaching cycle highs.'
        };
    } else if (lagValue > 0.0) {
        return {
            status: 'NEUTRAL',
            color: '#10b981',
            bgColor: 'rgb(6, 78, 59)',
            text: 'MID CYCLE',
            icon: '🟢',
            description: 'Lagging indicators slightly elevated but not at peak levels.'
        };
    } else {
        return {
            status: 'CLEAR',
            color: '#22c55e',
            bgColor: 'rgb(5, 46, 22)',
            text: 'EARLY-MID CYCLE',
            icon: '🟢',
            description: 'Lagging indicators below average, typical of expansion/recovery phase.'
        };
    }
};

const AccordionItem = ({ title, icon: Icon, children, explanation }) => {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div style={{ marginBottom: '16px', border: '1px solid #1f2937', borderRadius: '8px', overflow: 'hidden' }}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                style={{
                    width: '100%',
                    padding: '16px 20px',
                    backgroundColor: 'rgba(31, 41, 55, 0.4)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    border: 'none',
                    color: '#f87171',
                    cursor: 'pointer'
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Icon size={20} style={{ color: '#f87171' }} />
                    <span style={{ fontWeight: 'bold', fontSize: '16px' }}>{title}</span>
                </div>
                {isOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </button>

            {isOpen && (
                <div style={{ padding: '24px', backgroundColor: 'rgba(17, 24, 39, 0.2)' }}>
                    <p style={{ color: '#9ca3af', fontSize: '14px', lineHeight: '1.6', marginBottom: '20px' }}>
                        {explanation}
                    </p>
                    <div style={{ height: '250px' }}>
                        {children}
                    </div>
                </div>
            )}
        </div>
    );
};

const LagDashboard = () => {
    const [data, setData] = useState([]);
    const [latest, setLatest] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [startIndex, setStartIndex] = useState(0);
    const [endIndex, setEndIndex] = useState(0);
    const [recessionData, setRecessionData] = useState([]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const res = await axios.get(`${API_BASE_URL}/macro/lag-index`);
                const fullData = res.data.data.map(row => ({
                    ...row,
                    peak_overheat: row.lag_composite > 1 ? row.lag_composite : null
                }));
                setData(fullData);
                setLatest(res.data.latest);

                setStartIndex(0);
                setEndIndex(fullData.length);

                // Use recession data from LAG API response if available
                if (res.data.recessions) {
                    setRecessionData(res.data.recessions);
                }
            } catch (err) {
                console.error("Error fetching LAG data:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const lastUpdateRef = React.useRef(0);
    const setRange = (years) => {
        if (!data.length) return;
        if (years === 'Max') {
            setStartIndex(0);
            setEndIndex(data.length);
        } else {
            const months = years * 12;
            const start = Math.max(0, data.length - months);
            setStartIndex(start);
            setEndIndex(data.length);
        }
    };

    const visibleData = data.slice(startIndex, Math.min(endIndex + 1, data.length));
    const chartData = visibleData.length > 0 ? visibleData : data;

    // Mini Chart Component
    const MiniChart = ({ data, dataKey, name, color, isPct = true, recessionData }) => (
        <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 20, left: 20, bottom: 25 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} opacity={0.3} />
                <XAxis
                    dataKey="date"
                    hide={false}
                    stroke="#9CA3AF"
                    style={{ fontSize: '9px' }}
                    tick={{ fill: '#9CA3AF' }}
                    tickFormatter={(val) => val ? val.split('-')[0] : ''}
                    interval="preserveStartEnd"
                />
                <YAxis
                    stroke="#9CA3AF"
                    style={{ fontSize: '10px' }}
                    tickFormatter={(val) => isPct ? `${formatNumber(val * 100, 1)}%` : formatNumber(val, 1)}
                    domain={['auto', 'auto']}
                />
                <Tooltip
                    contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', fontSize: '11px' }}
                    labelStyle={{ color: '#9ca3af' }}
                    formatter={(val) => [isPct ? `${formatNumber(val * 100, 2)}%` : formatNumber(val, 2), name]}
                />
                <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="3 3" />

                {/* Recession Overlay */}
                <RecessionOverlay data={data} recessionData={recessionData} />

                <Line type="monotone" dataKey={dataKey} name={name} stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
        </ResponsiveContainer>
    );

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#0e1525', color: '#d7e3f3', padding: '24px' }}>
            {/* Header */}
            <header style={{ marginBottom: '32px', borderBottom: '1px solid #1f2937', paddingBottom: '16px' }}>
                <h1 style={{
                    fontSize: '28px',
                    fontWeight: 'bold',
                    background: 'linear-gradient(to right, #f87171, #ef4444)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    margin: 0
                }}>
                    Lagging Indicators Index (Confirmation)
                </h1>
                <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '8px' }}>
                    Economic Inertia Model — Sticky Confirmation & The Fed Trap (v2)
                </p>
            </header>

            {/* Beta Banner Removed */}

            {/* Status Badge */}
            {latest && (() => {
                const lagStatus = getLagStatus(latest.lag_composite);
                return (
                    <div style={{
                        backgroundColor: lagStatus.bgColor,
                        border: `2px solid ${lagStatus.color}`,
                        borderRadius: '12px',
                        padding: '24px',
                        marginBottom: '24px'
                    }}>
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
                            <span style={{ fontSize: '48px' }}>{lagStatus.icon}</span>
                            <div style={{ flex: 1 }}>
                                <h3 style={{
                                    color: lagStatus.color,
                                    fontSize: '24px',
                                    fontWeight: 'bold',
                                    marginBottom: '8px'
                                }}>
                                    Cycle Status: {lagStatus.text}
                                </h3>
                                <div style={{ color: '#e2e8f0', marginBottom: '16px' }}>
                                    <div style={{ fontSize: '18px', marginBottom: '4px' }}>
                                        <strong>Lagging Composite:</strong> {formatNumber(latest.lag_composite, 3)}
                                    </div>
                                    <div style={{ fontSize: '18px' }}>
                                        <strong>Signal Line (12M):</strong> {formatNumber(latest.signal_line, 3)}
                                    </div>
                                </div>
                                <p style={{ color: '#cbd5e1', fontSize: '16px', lineHeight: '1.6' }}>
                                    {lagStatus.description}
                                </p>
                            </div>
                        </div>
                    </div>
                );
            })()}

            {/* Cycle Maturity Conclusion */}
            {latest && (
                <div style={{
                    backgroundColor: 'rgb(15, 23, 42)',
                    border: '1px solid rgb(51, 65, 85)',
                    borderRadius: '12px',
                    padding: '24px',
                    marginBottom: '24px'
                }}>
                    <h3 style={{
                        color: '#60a5fa',
                        fontSize: '20px',
                        fontWeight: 'bold',
                        marginBottom: '16px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                    }}>
                        <Info size={24} />
                        Cycle Maturity Conclusion
                    </h3>

                    <div style={{ color: '#e2e8f0', marginBottom: '16px' }}>
                        <strong>Current Reading:</strong> {formatNumber(latest.lag_composite, 3)}
                        {latest.lag_composite < 0 ? ' (below zero)' : ' (above zero)'}
                    </div>

                    <div style={{ color: '#cbd5e1', lineHeight: '1.7' }}>
                        <p style={{ marginBottom: '12px' }}>
                            <strong>What This Means:</strong>
                        </p>
                        <p style={{ marginBottom: '12px' }}>
                            {latest.lag_composite < 0
                                ? "The LAG Index confirms the economy is in early-to-mid expansion phase. When lagging indicators (inflation, unemployment, labor costs) are below average, it signals:"
                                : latest.lag_composite > 0.5
                                    ? "The LAG Index shows late-cycle conditions. Lagging indicators are elevated, signaling cycle maturity:"
                                    : "The LAG Index shows mid-cycle conditions. Lagging indicators are moderately elevated:"}
                        </p>

                        {latest.lag_composite < 0 ? (
                            <>
                                <p style={{ color: '#10b981', marginBottom: '4px' }}>✅ The economy has NOT reached peak maturity</p>
                                <p style={{ color: '#10b981', marginBottom: '4px' }}>✅ Cycle has room to run before late-cycle pressures build</p>
                                <p style={{ color: '#10b981', marginBottom: '16px' }}>✅ No imminent recession confirmation</p>
                            </>
                        ) : latest.lag_composite > 0.5 ? (
                            <>
                                <p style={{ color: '#f59e0b', marginBottom: '4px' }}>⚠️ Peak formation - late cycle dynamics</p>
                                <p style={{ color: '#f59e0b', marginBottom: '4px' }}>⚠️ Lagging indicators at cycle highs</p>
                                <p style={{ color: '#f59e0b', marginBottom: '16px' }}>⚠️ Recession risk elevated</p>
                            </>
                        ) : (
                            <>
                                <p style={{ color: '#60a5fa', marginBottom: '4px' }}>🔵 Mid-cycle conditions</p>
                                <p style={{ color: '#60a5fa', marginBottom: '16px' }}>🔵 Monitor for further elevation</p>
                            </>
                        )}

                        <p style={{ fontSize: '14px', color: '#94a3b8' }}>
                            <strong>Watch For:</strong> LAG composite rising above 0.5 signals late-cycle conditions developing.
                        </p>

                        <p style={{ fontSize: '14px', color: '#94a3b8', marginTop: '12px' }}>
                            <strong>Historical Context:</strong> LAG typically peaks 6-12 months AFTER recessions begin, confirming the downturn.
                            {latest.lag_composite < 0
                                ? " The current negative reading indicates we are far from that confirmation phase."
                                : " Current elevation warrants close monitoring."}
                        </p>
                    </div>
                </div>
            )}

            {/* Explanation Section */}
            <AccordionItem
                title="What is the Lagging Indicator?"
                icon={Info}
                explanation="The Lagging Economic Index (LAG) tracks structural economic inertia. It represents the 'sticky' parts of the economy that peak long after the business cycle has already turned."
            >
                <div style={{ color: '#d1d5db', fontSize: '14px', lineHeight: '1.6' }}>
                    <p style={{ marginBottom: '12px' }}><strong>Components:</strong> This model monitors Services Inflation (sticky wages), Unemployment (labor market tightness), Unit Labor Costs, and C&I Loans (late-cycle credit expansion).</p>
                    <p style={{ marginBottom: '12px' }}><strong>Importance:</strong> It identifies the 'Fed Trap'. Because lagging data remains strong while the economy is already weakening, it often tricks policymakers into keeping rates too high for too long.</p>
                    <p><strong>How to Read:</strong> Rising LAG values confirm a mature, overheating cycle. A peak in the LAG index, coinciding with a crash in the LEI, typically signals the final 'confirmation' of the business cycle top.</p>
                </div>
            </AccordionItem>

            {/* Master Chart */}
            <div style={{
                backgroundColor: 'rgba(31, 41, 55, 0.3)',
                borderRadius: '8px',
                padding: '24px',
                border: '1px solid #1f2937',
                marginBottom: '32px'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                    <div>
                        <h2 style={{ fontSize: '18px', fontWeight: 'bold' }}>Lagging Inertia Signal (Confirmation)</h2>
                        <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                            {['10', '20', 'Max'].map(range => (
                                <button
                                    key={range}
                                    onClick={() => setRange(range === 'Max' ? 'Max' : parseInt(range))}
                                    style={{
                                        padding: '4px 12px',
                                        backgroundColor: '#1f2937',
                                        border: '1px solid #374151',
                                        borderRadius: '4px',
                                        color: '#9ca3af',
                                        fontSize: '11px',
                                        cursor: 'pointer'
                                    }}
                                >
                                    {range === 'Max' ? 'Full History' : `${range}Y`}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                <div style={{ height: '500px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart
                            data={data}
                            margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                            syncId="lag_dashboard"
                        >
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} opacity={0.5} />
                            <XAxis
                                dataKey="date"
                                stroke="#9CA3AF"
                                style={{ fontSize: '11px' }}
                            />
                            <YAxis domain={['auto', 'auto']} stroke="#9CA3AF" style={{ fontSize: '11px' }} />
                            <Tooltip
                                contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151' }}
                                itemStyle={{ fontSize: '12px' }}
                            />
                            <Legend verticalAlign="top" height={36} />

                            <Area
                                name="US Recession"
                                dataKey={() => null}
                                stroke="none"
                                fill="#374151"
                                fillOpacity={0.4}
                                legendType="rect"
                            />

                            <ReferenceLine y={0} stroke="#9ca3af" strokeWidth={1} strokeDasharray="3 3" />

                            {/* Recession Overlay */}
                            <RecessionOverlay data={data} recessionData={recessionData} />

                            <Area
                                type="monotone"
                                dataKey="peak_overheat"
                                fill="#ef4444"
                                fillOpacity={0.2}
                                stroke="none"
                                name="Cycle Peak Overheat"
                                isAnimationActive={false}
                            />

                            <Line
                                type="monotone"
                                dataKey="lag_composite"
                                name="LAG Composite"
                                stroke="#f87171"
                                strokeWidth={3}
                                dot={false}
                                isAnimationActive={false}
                            />
                            <Line
                                type="monotone"
                                dataKey="signal_line"
                                name="Signal Line (12M SMA)"
                                stroke="#fbbf24"
                                strokeWidth={1.5}
                                dot={false}
                                isAnimationActive={false}
                            />
                            <Brush
                                dataKey="date"
                                height={30}
                                stroke="#374151"
                                fill="#0e1525"
                                onChange={(e) => {
                                    if (e.startIndex !== undefined && e.endIndex !== undefined) {
                                        const now = Date.now();
                                        if (now - lastUpdateRef.current > 30) {
                                            setStartIndex(e.startIndex);
                                            setEndIndex(e.endIndex);
                                            lastUpdateRef.current = now;
                                        }
                                    }
                                }}
                            />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Fed Trap Divergence Chart */}
            <div style={{
                backgroundColor: 'rgba(31, 41, 55, 0.3)',
                borderRadius: '8px',
                padding: '24px',
                border: '1px solid #1f2937',
                marginBottom: '32px'
            }}>
                <div style={{ marginBottom: '20px' }}>
                    <h2 style={{ fontSize: '18px', fontWeight: 'bold' }}>🐊 The "Alligator Jaw" Divergence (LEI vs LAG)</h2>
                    <p style={{ color: '#9ca3af', fontSize: '13px', marginTop: '4px' }}>
                        Visualizing the GAP between leading signals and lagging confirmation.
                    </p>
                </div>

                {/* Jaw Status Explanation */}
                {latest && data.length > 0 && (() => {
                    const latestDataPoint = data[data.length - 1];
                    const leiValue = latestDataPoint.lei || 0;
                    const lagValue = latest.lag_composite || 0;
                    const spread = Math.abs(leiValue - lagValue);

                    let jawStatus, jawColor, jawDescription, jawIcon;
                    if (spread < 0.5) {
                        jawStatus = "JAW CLOSED";
                        jawColor = "#10b981";
                        jawDescription = "Economy stable, synchronized. No divergence risk.";
                        jawIcon = "🟢";
                    } else if (spread < 1.5) {
                        jawStatus = "JAW OPENING";
                        jawColor = "#f59e0b";
                        jawDescription = "Early warning - divergence building. Monitor closely.";
                        jawIcon = "🟡";
                    } else {
                        jawStatus = "JAW WIDE OPEN";
                        jawColor = "#ef4444";
                        jawDescription = "High recession risk - dangerous divergence pattern!";
                        jawIcon = "🔴";
                    }

                    return (
                        <div style={{ marginBottom: '20px', padding: '16px', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
                            <div style={{ marginBottom: '16px' }}>
                                <h4 style={{ color: '#60a5fa', marginBottom: '12px', fontSize: '16px' }}>What to Look For:</h4>
                                <ul style={{ color: '#cbd5e1', lineHeight: '1.8', paddingLeft: '20px', fontSize: '14px' }}>
                                    <li><span style={{ color: '#10b981' }}>🟢 Jaw CLOSED</span> (LEI and LAG near each other): Economy stable, synchronized</li>
                                    <li><span style={{ color: '#f59e0b' }}>🟡 Jaw OPENING</span> (LEI falling faster than LAG): Early warning, divergence building</li>
                                    <li><span style={{ color: '#ef4444' }}>🔴 Jaw WIDE OPEN</span> (LEI deeply negative, LAG still high): High recession risk, "alligator bite" imminent</li>
                                </ul>
                            </div>

                            <div style={{
                                backgroundColor: jawColor + '22',
                                border: `2px solid ${jawColor}`,
                                borderRadius: '8px',
                                padding: '16px',
                                marginBottom: '16px'
                            }}>
                                <h4 style={{ color: jawColor, marginBottom: '12px', fontSize: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    {jawIcon} Current Status: {jawStatus}
                                </h4>
                                <div style={{ color: '#e2e8f0', marginBottom: '8px', fontSize: '14px' }}>
                                    <div>LEI (Leading): {formatNumber(leiValue, 3)}</div>
                                    <div>LAG (Lagging): {formatNumber(lagValue, 3)}</div>
                                    <div>Divergence Spread: {formatNumber(spread, 3)}</div>
                                </div>
                                <p style={{ color: '#cbd5e1', fontSize: '14px' }}>{jawDescription}</p>
                            </div>

                            <div style={{ fontSize: '13px', color: '#94a3b8', fontStyle: 'italic' }}>
                                <strong>What Would Be Concerning:</strong> If LEI drops below -1.0 while LAG rises above 0.5,
                                that's a classic pre-recession "jaw opening" pattern.
                            </div>
                        </div>
                    );
                })()}

                <div style={{ height: '400px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} opacity={0.5} />
                            <XAxis dataKey="date" stroke="#9CA3AF" style={{ fontSize: '11px' }} />
                            <YAxis domain={['auto', 'auto']} stroke="#9CA3AF" style={{ fontSize: '11px' }} />
                            <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151' }} />
                            <Legend verticalAlign="top" height={36} />

                            <Area
                                name="US Recession"
                                dataKey={() => null}
                                stroke="none"
                                fill="#374151"
                                fillOpacity={0.4}
                                legendType="rect"
                            />

                            <ReferenceLine y={0} stroke="#9ca3af" strokeWidth={1} strokeDasharray="3 3" />

                            <Area
                                type="monotone"
                                dataKey="risk_spread"
                                name="Risk Spread (Alligator Jaw)"
                                fill="#ef4444"
                                fillOpacity={0.1}
                                stroke="#ef4444"
                                strokeWidth={1}
                                isAnimationActive={false}
                            />

                            <Line
                                type="monotone"
                                dataKey="lei"
                                name="LEI (Leading)"
                                stroke="#10b981"
                                strokeWidth={2}
                                dot={false}
                                isAnimationActive={false}
                            />
                            <Line
                                type="monotone"
                                dataKey="lag_composite"
                                name="LAG (Lagging)"
                                stroke="#f87171"
                                strokeWidth={2}
                                dot={false}
                                isAnimationActive={false}
                            />

                            <Brush
                                dataKey="date"
                                height={30}
                                stroke="#374151"
                                fill="#0e1525"
                                onChange={(e) => {
                                    if (e.startIndex !== undefined && e.endIndex !== undefined) {
                                        const now = Date.now();
                                        if (now - lastUpdateRef.current > 30) {
                                            setStartIndex(e.startIndex);
                                            setEndIndex(e.endIndex);
                                            lastUpdateRef.current = now;
                                        }
                                    }
                                }}
                            />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Component Breakdown */}
            <div style={{ marginBottom: '32px' }}>
                <h2 style={{ fontSize: '20px', fontWeight: 'bold', marginBottom: '20px' }}>
                    Component Breakdown (12M YoY Transformations)
                </h2>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    {/* CPI Services */}
                    <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.4)', borderRadius: '8px', border: '1px solid #1f2937', padding: '16px 20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <h3 style={{ fontSize: '14px', fontWeight: 'bold', margin: 0 }}>Sticky Inflation: CPI Services (Ex-Shelter)</h3>
                            <span style={{ fontSize: '12px', color: '#6b7280' }}>Weight: 30%</span>
                        </div>
                        <div style={{ height: '120px' }}>
                            <MiniChart data={visibleData} dataKey="cpi_serv" name="CPI Services YoY" color="#f87171" recessionData={recessionData} />
                        </div>
                        <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '15px', lineHeight: '1.4' }}>
                            Wage-driven services inflation. The hardest component for the Fed to break.
                        </p>
                    </div>

                    {/* Unemployment */}
                    <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.4)', borderRadius: '8px', border: '1px solid #1f2937', padding: '16px 20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <h3 style={{ fontSize: '14px', fontWeight: 'bold', margin: 0 }}>Labor Tightness: Inverted Unemployment</h3>
                            <span style={{ fontSize: '12px', color: '#6b7280' }}>Weight: 30%</span>
                        </div>
                        <div style={{ height: '120px' }}>
                            <MiniChart data={visibleData} dataKey="unrate" name="Inverted UNRATE" color="#fbbf24" isPct={false} recessionData={recessionData} />
                        </div>
                        <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '15px', lineHeight: '1.4' }}>
                            Inverted: A rising line means falling unemployment. Cycles peak when labor is scarcest.
                        </p>
                    </div>

                    {/* Labor Cost */}
                    <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.4)', borderRadius: '8px', border: '1px solid #1f2937', padding: '16px 20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <h3 style={{ fontSize: '14px', fontWeight: 'bold', margin: 0 }}>Margin Pressure: Unit Labor Costs</h3>
                            <span style={{ fontSize: '12px', color: '#6b7280' }}>Weight: 20%</span>
                        </div>
                        <div style={{ height: '120px' }}>
                            <MiniChart data={visibleData} dataKey="ulc" name="Unit Labor Costs YoY" color="#60a5fa" recessionData={recessionData} />
                        </div>
                        <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '15px', lineHeight: '1.4' }}>
                            Cost of labor per unit of output. Rising costs squeeze profits at cycle ends.
                        </p>
                    </div>

                    {/* C&I Loans */}
                    <div style={{ backgroundColor: 'rgba(31, 41, 55, 0.4)', borderRadius: '8px', border: '1px solid #1f2937', padding: '16px 20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <h3 style={{ fontSize: '14px', fontWeight: 'bold', margin: 0 }}>Late-Cycle Credit: C&I Loans</h3>
                            <span style={{ fontSize: '12px', color: '#6b7280' }}>Weight: 20%</span>
                        </div>
                        <div style={{ height: '120px' }}>
                            <MiniChart data={visibleData} dataKey="loans" name="C&I Loans YoY" color="#10b981" recessionData={recessionData} />
                        </div>
                        <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '15px', lineHeight: '1.4' }}>
                            Commercial borrowing often peaks as businesses cover cash flow gaps in a slowing economy.
                        </p>
                    </div>
                </div>
            </div>

            {/* Analysis Footer */}
            <div style={{
                padding: '24px',
                borderRadius: '8px',
                backgroundColor: 'rgba(31, 41, 55, 0.4)',
                border: '1px solid #1f2937'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                    <Info size={24} style={{ color: '#60a5fa' }} />
                    <h3 style={{ fontSize: '18px', fontWeight: 'bold', margin: 0 }}>The Role of the Lagging Index</h3>
                </div>
                <p style={{ color: '#9ca3af', lineHeight: '1.6', margin: 0 }}>
                    The Lagging Index is the "villain" that keeps interest rates high. Because it is composed of sticky
                    service inflation and labor metrics, it often shows strength even as the LEI (Leading) is crashing.
                    A confirmed cycle top occurs when the LAG peaks just as the COI (Coincident) starts to drop.
                    <br />
                    <span style={{ fontSize: '12px', opacity: 0.7, marginTop: '8px', display: 'block' }}>
                        * Shaded grey areas represent official US Recession periods defined by NBER.
                    </span>
                </p>
            </div>
        </div>
    );
};

export default LagDashboard;
