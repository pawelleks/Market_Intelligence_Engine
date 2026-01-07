import React, { useState, useEffect } from 'react';
import { usePageTitle } from '../hooks/usePageTitle';
import { useAuth } from '../context/AuthContext';
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon, Star, Filter } from 'lucide-react';

const DataReleasesCalendar = () => {
    usePageTitle('Data Releases Calendar');
    const { token } = useAuth();

    const [filter, setFilter] = useState('today'); // 'today', 'week', 'month'
    const [monthOffset, setMonthOffset] = useState(0);
    const [onlyTracked, setOnlyTracked] = useState(false);
    const [calendarData, setCalendarData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Fetch calendar data
    useEffect(() => {
        if (!token) return;

        setLoading(true);
        setError(null);

        fetch(`/api/v1/economy/macro/calendar?filter=${filter}&month_offset=${monthOffset}&only_tracked=${onlyTracked}`, {
            headers: { "Authorization": `Bearer ${token}` }
        })
            .then(res => {
                if (!res.ok) throw new Error("Failed to load calendar data");
                return res.json();
            })
            .then(json => {
                if (json.status === 'ok') {
                    setCalendarData(json.data);
                } else {
                    setError(json.message || 'Failed to load calendar');
                }
            })
            .catch(err => setError(err.message))
            .finally(() => setLoading(false));
    }, [filter, monthOffset, onlyTracked, token]);

    const colors = {
        bg: '#0e1525',
        border: '#203049',
        text: '#d7e3f3',
        textMuted: '#9e9e9e',
        activeBg: 'rgba(59, 130, 246, 0.1)',
        activeBorder: '#3b82f6',
        cardBg: '#1b2a40',
        hover: '#1e293b',
        star: '#ffc107',
        tagBg: 'rgba(76, 175, 80, 0.15)',
        tagText: '#4caf50'
    };

    const handleFilterChange = (newFilter) => {
        setFilter(newFilter);
        setMonthOffset(0); // Reset month offset when changing filter
    };

    const handleMonthChange = (offset) => {
        setMonthOffset(prevOffset => prevOffset + offset);
    };

    // Format date for display
    const formatDate = (dateStr) => {
        const date = new Date(dateStr + 'T00:00:00');
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const dateOnly = new Date(date);
        dateOnly.setHours(0, 0, 0, 0);

        const isToday = dateOnly.getTime() === today.getTime();
        const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
        const monthDay = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

        return {
            dayName,
            monthDay,
            isToday,
            fullDate: date.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
        };
    };

    return (
        <div style={{ padding: '20px', minHeight: '100vh', width: '100%', color: colors.text }}>
            {/* Header */}
            <div style={{ marginBottom: '20px', borderBottom: `1px solid ${colors.border}`, paddingBottom: '15px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <CalendarIcon size={28} color="#4caf50" />
                        <h1 style={{ margin: 0, fontSize: '28px' }}>Economic Data Releases Calendar</h1>
                    </div>

                    {/* Tracked Toggle */}
                    <button
                        onClick={() => setOnlyTracked(!onlyTracked)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            padding: '8px 14px',
                            backgroundColor: onlyTracked ? colors.tagBg : colors.hover,
                            border: `1px solid ${onlyTracked ? colors.tagText : colors.border}`,
                            borderRadius: '20px',
                            cursor: 'pointer',
                            color: onlyTracked ? colors.tagText : colors.textMuted,
                            fontSize: '13px',
                            fontWeight: 'bold',
                            transition: 'all 0.2s'
                        }}
                    >
                        <Star size={14} fill={onlyTracked ? colors.tagText : 'none'} />
                        {onlyTracked ? 'Tracked Releases Only' : 'Show All Releases'}
                    </button>
                </div>
                <p style={{ color: colors.textMuted, fontSize: '14px', margin: 0 }}>
                    Scheduled economic data releases from FRED • Times shown in ET
                </p>
            </div>

            {/* Controls */}
            <div style={{ marginBottom: '30px' }}>
                {/* Filter Buttons */}
                <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap' }}>
                    {['today', 'week', 'month'].map(f => (
                        <button
                            key={f}
                            onClick={() => handleFilterChange(f)}
                            style={{
                                padding: '8px 16px',
                                backgroundColor: filter === f ? colors.activeBg : colors.bg,
                                color: filter === f ? colors.activeBorder : colors.text,
                                border: `1px solid ${filter === f ? colors.activeBorder : colors.border}`,
                                borderRadius: '6px',
                                cursor: 'pointer',
                                fontSize: '14px',
                                fontWeight: filter === f ? 'bold' : 'normal',
                                textTransform: 'capitalize',
                                transition: 'all 0.2s'
                            }}
                            onMouseEnter={(e) => {
                                if (filter !== f) {
                                    e.currentTarget.style.backgroundColor = colors.hover;
                                }
                            }}
                            onMouseLeave={(e) => {
                                if (filter !== f) {
                                    e.currentTarget.style.backgroundColor = colors.bg;
                                }
                            }}
                        >
                            {f === 'week' ? 'This Week' : f === 'today' ? 'Today' : 'All'}
                        </button>
                    ))}
                </div>

                {/* Month Navigation (only show for month filter) */}
                {filter === 'month' && (
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '15px',
                        padding: '12px',
                        backgroundColor: colors.bg,
                        border: `1px solid ${colors.border}`,
                        borderRadius: '8px'
                    }}>
                        <button
                            onClick={() => handleMonthChange(-1)}
                            style={{
                                background: 'transparent',
                                border: 'none',
                                color: colors.text,
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                padding: '4px'
                            }}
                            title="Previous Month"
                        >
                            <ChevronLeft size={20} />
                        </button>

                        <div style={{ flex: 1, textAlign: 'center', fontSize: '16px', fontWeight: 'bold' }}>
                            {calendarData?.period?.label || 'Loading...'}
                        </div>

                        <button
                            onClick={() => handleMonthChange(1)}
                            style={{
                                background: 'transparent',
                                border: 'none',
                                color: colors.text,
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                padding: '4px'
                            }}
                            title="Next Month"
                        >
                            <ChevronRight size={20} />
                        </button>
                    </div>
                )}

                {/* Period Label (for today/week filters) */}
                {filter !== 'month' && calendarData && (
                    <div style={{
                        padding: '12px',
                        backgroundColor: colors.bg,
                        border: `1px solid ${colors.border}`,
                        borderRadius: '8px',
                        textAlign: 'center',
                        fontSize: '16px',
                        fontWeight: 'bold'
                    }}>
                        {calendarData.period.label}
                    </div>
                )}
            </div>

            {/* Loading/Error States */}
            {loading && (
                <div style={{ textAlign: 'center', padding: '40px', color: colors.textMuted }}>
                    Loading calendar data...
                </div>
            )}

            {error && (
                <div style={{
                    padding: '20px',
                    backgroundColor: 'rgba(244, 67, 54, 0.1)',
                    border: '1px solid #f44336',
                    borderRadius: '8px',
                    color: '#f44336'
                }}>
                    Error: {error}
                </div>
            )}

            {/* Calendar Data */}
            {!loading && !error && calendarData && (
                <>
                    {/* Total Count */}
                    <div style={{
                        marginBottom: '15px',
                        fontSize: '13px',
                        color: colors.textMuted,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                    }}>
                        {onlyTracked && <Star size={12} fill={colors.star} color={colors.star} />}
                        {calendarData.total_releases} {onlyTracked ? 'tracked' : ''} release{calendarData.total_releases !== 1 ? 's' : ''} scheduled
                    </div>

                    {/* Releases List */}
                    {calendarData.releases.length === 0 ? (
                        <div style={{
                            padding: '40px',
                            textAlign: 'center',
                            backgroundColor: colors.bg,
                            border: `1px solid ${colors.border}`,
                            borderRadius: '8px',
                            color: colors.textMuted
                        }}>
                            No {onlyTracked ? 'tracked' : ''} releases scheduled for this period
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                            {calendarData.releases.map(day => {
                                const { dayName, monthDay, isToday, fullDate } = formatDate(day.date);

                                return (
                                    <div
                                        key={day.date}
                                        style={{
                                            backgroundColor: colors.bg,
                                            border: `1px solid ${isToday ? '#4caf50' : colors.border}`,
                                            borderRadius: '8px',
                                            overflow: 'hidden'
                                        }}
                                    >
                                        {/* Date Header */}
                                        <div style={{
                                            padding: '12px 16px',
                                            backgroundColor: isToday ? 'rgba(76, 175, 80, 0.1)' : colors.cardBg,
                                            borderBottom: `1px solid ${colors.border}`,
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '12px'
                                        }}>
                                            <div style={{
                                                fontSize: '12px',
                                                color: isToday ? '#4caf50' : colors.textMuted,
                                                fontWeight: 'bold',
                                                textTransform: 'uppercase',
                                                minWidth: '40px'
                                            }}>
                                                {dayName}
                                            </div>
                                            <div style={{
                                                fontSize: '16px',
                                                fontWeight: 'bold',
                                                color: isToday ? '#4caf50' : colors.text
                                            }}>
                                                {monthDay}
                                            </div>
                                            {isToday && (
                                                <div style={{
                                                    fontSize: '11px',
                                                    padding: '2px 8px',
                                                    backgroundColor: '#4caf50',
                                                    color: '#000',
                                                    borderRadius: '4px',
                                                    fontWeight: 'bold'
                                                }}>
                                                    TODAY
                                                </div>
                                            )}
                                            <div style={{
                                                marginLeft: 'auto',
                                                fontSize: '12px',
                                                color: colors.textMuted
                                            }}>
                                                {day.releases.length} release{day.releases.length !== 1 ? 's' : ''}
                                            </div>
                                        </div>

                                        {/* Releases for this day */}
                                        <div style={{ padding: '8px' }}>
                                            {day.releases.map((release, idx) => (
                                                <div
                                                    key={`${release.release_id}-${idx}`}
                                                    style={{
                                                        padding: '12px',
                                                        borderBottom: idx < day.releases.length - 1 ? `1px solid ${colors.border}` : 'none',
                                                        display: 'flex',
                                                        alignItems: 'flex-start',
                                                        gap: '15px',
                                                        transition: 'background-color 0.2s',
                                                        borderRadius: '4px'
                                                    }}
                                                    onMouseEnter={(e) => {
                                                        e.currentTarget.style.backgroundColor = colors.hover;
                                                    }}
                                                    onMouseLeave={(e) => {
                                                        e.currentTarget.style.backgroundColor = 'transparent';
                                                    }}
                                                >
                                                    <div style={{
                                                        fontSize: '13px',
                                                        fontFamily: 'monospace',
                                                        color: '#4caf50',
                                                        fontWeight: 'bold',
                                                        minWidth: '50px',
                                                        marginTop: '2px'
                                                    }}>
                                                        {release.time}
                                                    </div>

                                                    <div style={{ flex: 1 }}>
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: release.is_tracked ? '6px' : '0' }}>
                                                            {release.is_tracked && (
                                                                <Star size={14} fill={colors.star} color={colors.star} />
                                                            )}
                                                            <div style={{
                                                                fontSize: '14px',
                                                                color: colors.text,
                                                                fontWeight: release.is_tracked ? 'bold' : 'normal'
                                                            }}>
                                                                {release.release_name}
                                                            </div>
                                                        </div>

                                                        {release.is_tracked && release.series_ids && (
                                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                                                {release.series_ids.map(sid => (
                                                                    <span key={sid} style={{
                                                                        fontSize: '10px',
                                                                        padding: '2px 6px',
                                                                        backgroundColor: colors.tagBg,
                                                                        color: colors.tagText,
                                                                        borderRadius: '10px',
                                                                        fontWeight: 'bold'
                                                                    }}>
                                                                        {sid}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default DataReleasesCalendar;
