import React, { useEffect, useState } from 'react';
import { Calendar, ChevronDown, ChevronUp, Star, Circle } from 'lucide-react';
import { formatDate, formatTime, formatCountdown } from '../utils/dateFormatters';
import '../styles/UpcomingReleases.css';

const UpcomingReleases = ({ indicatorId }) => {
    const [releases, setReleases] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isCollapsed, setIsCollapsed] = useState(true);

    useEffect(() => {
        const fetchReleases = async () => {
            if (!indicatorId) return;
            try {
                setLoading(true);
                const response = await fetch(`/api/v1/jpm-dashboard/indicators/${indicatorId}/upcoming-releases`);
                if (!response.ok) throw new Error('Failed to fetch');
                const data = await response.json();

                // Sort by Date then Time
                const sorted = (data.releases || []).sort((a, b) => {
                    if (a.date !== b.date) return a.date.localeCompare(b.date);
                    return a.time.localeCompare(b.time);
                });
                setReleases(sorted);
            } catch (err) {
                console.error(err);
                setReleases([]);
            } finally {
                setLoading(false);
            }
        };
        fetchReleases();
    }, [indicatorId]);

    if (loading || releases.length === 0) return null;

    const toggle = () => setIsCollapsed(!isCollapsed);
    const nextRelease = releases[0]; // Nearest upcoming

    return (
        <div className="upcoming-releases-container">
            <div className="upcoming-header" onClick={toggle}>
                <div className="upcoming-title">
                    <Calendar size={16} />
                    <span>Upcoming Data Releases</span>
                    <span className="upcoming-count">({releases.length})</span>
                </div>

                <div className="upcoming-controls">
                    <div className="upcoming-legend">
                        <span className="legend-item"><Star size={12} className="icon-primary" /> Key Release</span>
                        <span className="legend-item"><Circle size={10} className="icon-related" /> Related Series</span>
                    </div>
                    {isCollapsed ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
                </div>
            </div>

            {!isCollapsed ? (
                <div className="release-list">
                    {releases.map((release) => (
                        <ReleaseItem key={`${release.id}-${release.date}`} release={release} />
                    ))}
                </div>
            ) : (
                <div className="release-preview" onClick={toggle}>
                    <span className="preview-label">Next:</span>
                    <ReleaseItem release={nextRelease} previewMode={true} />
                </div>
            )}
        </div>
    );
};

const ReleaseItem = ({ release, previewMode = false }) => {
    const todayStr = new Date().toISOString().split('T')[0];
    const isToday = release.date === todayStr;

    return (
        <div className={`release-item ${release.is_primary ? 'primary' : 'related'} ${isToday ? 'today' : ''} ${previewMode ? 'preview' : ''}`}>
            <div className="release-left">
                <div className="release-date-box">
                    <span className="release-date-day">{formatDate(release.date)}</span>
                    <span className="release-date-time">{formatTime(release.time)}</span>
                </div>
                <div className="release-details">
                    <div className="release-name-row">
                        {release.is_primary ? <Star size={14} className="icon-primary" /> : <Circle size={10} className="icon-related" />}
                        <span className="release-name">{release.name}</span>
                    </div>
                </div>
            </div>

            <div className="release-right">
                <div className={`release-countdown ${isToday ? 'today-badge' : ''}`}>
                    {isToday ? 'TODAY' : formatCountdown(release.hours_until)}
                </div>
            </div>
        </div>
    );
};

export default UpcomingReleases;
