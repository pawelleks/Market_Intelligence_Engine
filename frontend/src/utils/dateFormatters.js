
export const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr + 'T12:00:00'); // Approx to avoid timezone shifts
    return date.toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric'
    });
};

export const formatTime = (timeStr) => {
    if (!timeStr) return '';
    // Format HH:MM to 12h AM/PM
    const [h, m] = timeStr.split(':');
    const hour = parseInt(h, 10);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const hour12 = hour % 12 || 12;
    return `${hour12}:${m} ${ampm} ET`;
};

export const formatCountdown = (hours) => {
    if (hours < 0) return 'Released';
    if (hours < 1) return '< 1 hr';
    if (hours < 24) return `${Math.round(hours)} hrs`;
    const days = Math.floor(hours / 24);
    return `${days} days`;
};
