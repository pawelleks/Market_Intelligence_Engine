/**
 * Centralized Design System for the Market Intelligence Engine.
 * All chart and table colors are defined here to ensure visual consistency.
 */

// --- Base Dark Theme ---
export const COLORS = {
  // Backgrounds
  bg: {
    primary: '#0b1220',
    card: '#0e1525',
    chart: '#0F172A',
    overlay: 'rgba(15, 23, 42, 0.8)',
  },

  // Text
  text: {
    primary: '#d7e3f3',
    secondary: '#94A3B8',
    muted: '#9e9e9e',
    accent: '#9ec4ff',
    white: '#ffffff',
  },

  // Borders & Grid
  border: {
    default: '#203049',
    grid: '#334155',
    subtle: '#1E293B',
  },

  // Semantic: Status
  status: {
    success: '#4caf50',
    warning: '#ff9800',
    error: '#f44336',
    info: '#38bdf8',
  },

  // Live Data
  live: '#38bdf8', // Cyan-400 — used for live price lines, WebSocket indicators

  // Ticker Label
  ticker: '#4caf50',
};


// --- Expected Moves Color System ---
// These are the canonical colors for 0DTE / Weekly / Monthly across ALL components.
export const EM_COLORS = {
  dte0: {
    high: '#F97316', // Orange-500
    low: '#22C55E',  // Green-500
    label: 'text-amber-400',
  },
  weekly: {
    high: '#EF4444', // Red-500
    low: '#22C55E',  // Green-500
    label: 'text-red-400',
  },
  monthly: {
    high: '#A855F7', // Purple-500
    low: '#3B82F6',  // Blue-500
    label: 'text-purple-400',
  },
};


// --- Candlestick Colors ---
export const CANDLE_COLORS = {
  up: {
    body: 'rgba(34, 197, 94, 0.1)',
    wick: '#ffffff',
    border: '#ffffff',
  },
  down: {
    body: '#64748b',
    wick: '#64748b',
    border: '#64748b',
  },
};


// --- Market Condition Badges ---
export const CONDITION_COLORS = {
  veryCalmColor: '#4caf50',
  normalColor: '#8bc34a',
  volatileColor: '#ffeb3b',
  highVolColor: '#ff9800',
  extremeVolColor: '#f44336',
};
