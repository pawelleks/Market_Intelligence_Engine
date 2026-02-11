/**
 * NYSE Market Hours Utility.
 * Uses backend /api/v1/market/status (powered by pandas_market_calendars)
 * with a local fallback for instant time-of-day checks.
 */

export interface MarketStatus {
    isOpen: boolean;
    status: string;
    sessionType: "pre_market" | "regular" | "after_hours" | "closed";
    isTradingDay?: boolean;
}

// ---- Cached Backend Response ----
let _cachedStatus: MarketStatus | null = null;
let _cacheTimestamp = 0;
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Fetches market status from the backend (pandas_market_calendars).
 * Results are cached for 5 minutes. Falls back to local logic on failure.
 */
export async function fetchMarketStatus(): Promise<MarketStatus> {
    const now = Date.now();
    if (_cachedStatus && now - _cacheTimestamp < CACHE_TTL_MS) {
        return _cachedStatus;
    }

    try {
        const res = await fetch("/api/v1/market/status");
        if (res.ok) {
            const data = await res.json();
            const status: MarketStatus = {
                isOpen: data.is_open,
                status: data.status,
                sessionType: data.session_type,
                isTradingDay: data.is_trading_day,
            };
            _cachedStatus = status;
            _cacheTimestamp = now;
            return status;
        }
    } catch {
        // Network error — fall through to local
    }

    // Fallback to local logic
    return getMarketStatusLocal();
}

/**
 * Synchronous local market status (weekends + time-of-day only, no holiday awareness).
 * Use as fallback when backend is unreachable.
 */
export function getMarketStatusLocal(): MarketStatus {
    const now = new Date();
    const etString = now.toLocaleString("en-US", { timeZone: "America/New_York" });
    const et = new Date(etString);

    const day = et.getDay(); // 0=Sun, 6=Sat
    const hours = et.getHours();
    const minutes = et.getMinutes();
    const timeInMinutes = hours * 60 + minutes;

    // Weekend
    if (day === 0 || day === 6) {
        return { isOpen: false, status: "Weekend \u2014 Market Closed", sessionType: "closed" };
    }

    // Time boundaries (in minutes from midnight ET)
    const PRE_MARKET_OPEN = 4 * 60;         // 4:00 AM
    const REGULAR_OPEN = 9 * 60 + 30;       // 9:30 AM
    const REGULAR_CLOSE = 16 * 60;          // 4:00 PM
    const AFTER_HOURS_CLOSE = 20 * 60;      // 8:00 PM

    if (timeInMinutes < PRE_MARKET_OPEN) {
        return { isOpen: false, status: "Overnight \u2014 Market Closed", sessionType: "closed" };
    }
    if (timeInMinutes < REGULAR_OPEN) {
        return { isOpen: false, status: "Pre-Market (4:00\u20139:30 AM ET)", sessionType: "pre_market" };
    }
    if (timeInMinutes < REGULAR_CLOSE) {
        return { isOpen: true, status: "Market Open (9:30 AM\u20134:00 PM ET)", sessionType: "regular" };
    }
    if (timeInMinutes < AFTER_HOURS_CLOSE) {
        return { isOpen: false, status: "After Hours (4:00\u20138:00 PM ET)", sessionType: "after_hours" };
    }

    return { isOpen: false, status: "Overnight \u2014 Market Closed", sessionType: "closed" };
}

/**
 * Returns the current NYSE market status.
 * Uses cached backend data if available, otherwise falls back to local logic.
 * This is the synchronous entry point used by components.
 */
export function getMarketStatus(): MarketStatus {
    // Return cached backend result if fresh
    if (_cachedStatus && Date.now() - _cacheTimestamp < CACHE_TTL_MS) {
        return _cachedStatus;
    }
    // Otherwise return local estimate (backend fetch happens async)
    return getMarketStatusLocal();
}

/**
 * Returns true if current time is within regular NYSE trading hours.
 */
export function isRegularSession(): boolean {
    return getMarketStatus().sessionType === "regular";
}
