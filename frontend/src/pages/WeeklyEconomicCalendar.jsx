import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { format, parseISO } from 'date-fns';
import { Globe, Clock, AlertCircle, Info, Hash, ChevronDown, ChevronUp } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// Flag Mapping for Bonus Requirement
const getFlagEmoji = (countryCode) => {
    const codeMap = {
        'USD': 'us',
        'EUR': 'eu',
        'GBP': 'gb',
        'JPY': 'jp',
        'CAD': 'ca',
        'AUD': 'au',
        'CHF': 'ch',
        'CNY': 'cn',
        'NZD': 'nz'
    };
    const isoCode = codeMap[countryCode] || countryCode.substring(0, 2).toLowerCase();
    return `https://flagcdn.com/w40/${isoCode}.png`;
};

const ImpactBadge = ({ impact }) => {
    const styles = {
        High: { bg: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', border: '#ef4444' },
        Medium: { bg: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b', border: '#f59e0b' },
        Low: { bg: 'rgba(251, 191, 36, 0.15)', color: '#fbbf24', border: '#fbbf24' },
        Holiday: { bg: 'rgba(156, 163, 175, 0.2)', color: '#9ca3af', border: '#9ca3af' }
    };

    const style = styles[impact] || styles.Low;

    return (
        <span style={{
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '11px',
            fontWeight: 'bold',
            backgroundColor: style.bg,
            color: style.color,
            border: `1px solid ${style.border}`,
            textTransform: 'uppercase',
            display: 'inline-block',
            textAlign: 'center',
            minWidth: '60px'
        }}>
            {impact}
        </span>
    );
};

const WeeklyEconomicCalendar = () => {
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const response = await axios.get(`${API_BASE_URL}/macro/calendar`);
                if (response.data.status === 'ok' || response.data.status === 'warning') {
                    setEvents(response.data.data);
                } else {
                    throw new Error(response.data.message || 'Failed to fetch calendar');
                }
            } catch (err) {
                console.error("Error fetching calendar:", err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return <div className="p-8 text-center text-gray-400">Loading Global Economic Calendar...</div>;
    if (error) return <div className="p-8 text-center text-red-500">Error: {error}</div>;

    // Group events by local day
    const groupedEvents = events.reduce((acc, event) => {
        const localDate = new Date(event.date);
        const dayLabel = format(localDate, 'EEEE, MMMM do');
        if (!acc[dayLabel]) acc[dayLabel] = [];
        acc[dayLabel].push({
            ...event,
            localTime: format(localDate, 'HH:mm')
        });
        return acc;
    }, {});

    return (
        <div style={{ padding: '24px', backgroundColor: '#0e1525', minHeight: '100vh', color: '#d7e3f3' }}>
            <header style={{ marginBottom: '24px', borderBottom: '1px solid #1f2937', paddingBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Globe size={28} style={{ color: '#3b82f6' }} />
                    <h1 style={{ fontSize: '28px', fontWeight: 'bold', margin: 0 }}>Weekly Economic Calendar</h1>
                </div>
                <p style={{ color: '#9ca3af', fontSize: '14px', marginTop: '8px' }}>
                    Real-time economic events with automated timezone conversion to your local browser time.
                </p>
            </header>

            {/* Experimental Warning Banner */}
            <div style={{
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                borderRadius: '8px',
                padding: '16px',
                marginBottom: '32px',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px'
            }}>
                <AlertCircle size={20} style={{ color: '#f59e0b', flexShrink: 0, marginTop: '2px' }} />
                <div>
                    <h4 style={{ margin: 0, color: '#f59e0b', fontSize: '14px', fontWeight: 'bold' }}>Experimental Feature</h4>
                    <p style={{ margin: '4px 0 0 0', color: '#d1d5db', fontSize: '13px', lineHeight: '1.5' }}>
                        This module is currently in **Beta**. It functions as a scheduled events calendar only.
                        Please note that **published actual values** are not yet integrated into this feed.
                    </p>
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
                {Object.keys(groupedEvents).map(day => (
                    <section key={day}>
                        <h2 style={{
                            fontSize: '18px',
                            fontWeight: 'bold',
                            marginBottom: '16px',
                            color: '#3b82f6',
                            borderLeft: '4px solid #3b82f6',
                            paddingLeft: '12px'
                        }}>
                            {day}
                        </h2>

                        <div style={{ overflowX: 'auto', backgroundColor: 'rgba(31, 41, 55, 0.4)', borderRadius: '8px', border: '1px solid #1f2937' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '700px' }}>
                                <thead>
                                    <tr style={{ borderBottom: '1px solid #1f2937', backgroundColor: 'rgba(31, 41, 55, 0.6)' }}>
                                        <th style={{ padding: '12px 16px', fontSize: '12px', color: '#9ca3af', textTransform: 'uppercase' }}>Time</th>
                                        <th style={{ padding: '12px 16px', fontSize: '12px', color: '#9ca3af', textTransform: 'uppercase' }}>Cur</th>
                                        <th style={{ padding: '12px 16px', fontSize: '12px', color: '#9ca3af', textTransform: 'uppercase' }}>Impact</th>
                                        <th style={{ padding: '12px 16px', fontSize: '12px', color: '#9ca3af', textTransform: 'uppercase' }}>Event</th>
                                        <th style={{ padding: '12px 16px', fontSize: '12px', color: '#9ca3af', textTransform: 'uppercase', textAlign: 'center' }}>Forecast</th>
                                        <th style={{ padding: '12px 16px', fontSize: '12px', color: '#9ca3af', textTransform: 'uppercase', textAlign: 'center' }}>Previous</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {groupedEvents[day].map((event, idx) => (
                                        <tr key={idx} style={{ borderBottom: '1px solid #1f2937', transition: 'background-color 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.05)'} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
                                            <td style={{ padding: '14px 16px', fontSize: '14px', whiteSpace: 'nowrap' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                                    <Clock size={14} style={{ opacity: 0.5 }} />
                                                    {event.localTime}
                                                </div>
                                            </td>
                                            <td style={{ padding: '14px 16px', fontSize: '14px' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                    <img
                                                        src={getFlagEmoji(event.country)}
                                                        alt={event.country}
                                                        style={{ width: '20px', height: '14px', objectFit: 'cover', borderRadius: '2px', boxShadow: '0 0 2px rgba(255,255,255,0.2)' }}
                                                        onError={(e) => e.target.style.display = 'none'}
                                                    />
                                                    <span style={{ fontWeight: 500 }}>{event.country}</span>
                                                </div>
                                            </td>
                                            <td style={{ padding: '14px 16px' }}>
                                                <ImpactBadge impact={event.impact} />
                                            </td>
                                            <td style={{ padding: '14px 16px', fontSize: '14px', fontWeight: 500 }}>
                                                {event.title}
                                            </td>
                                            <td style={{ padding: '14px 16px', fontSize: '14px', textAlign: 'center', color: '#d1d5db' }}>
                                                {event.forecast || '--'}
                                            </td>
                                            <td style={{ padding: '14px 16px', fontSize: '14px', textAlign: 'center', color: '#9ca3af' }}>
                                                {event.previous || '--'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>
                ))}
            </div>

            <footer style={{ marginTop: '48px', color: '#6b7280', fontSize: '11px', textAlign: 'center', borderTop: '1px solid #1f2937', paddingTop: '16px' }}>
                Data provided by Financial Juice / Fair Economy. Cached locally to avoid rate limits. Refresh every 60 minutes.
            </footer>
        </div>
    );
};

export default WeeklyEconomicCalendar;
