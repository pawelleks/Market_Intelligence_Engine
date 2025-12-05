# Reliability Dashboard Component Design (`EMReliabilityPage`)

## Overview
The `EMReliabilityPage` is a new frontend view designed to provide transparency into the performance of the Expected Moves (EM) model. It consumes data from the `/api/v1/expected_moves/reliability` endpoints to display both high-level aggregate statistics and detailed historical records.

## Layout Structure

The page is divided into two main vertical sections:

1.  **Summary Statistics (Top)**
2.  **Historical Records Table (Bottom)**

---

## 1. Summary Statistics Section

**Visual Style:** A responsive grid of cards. Each card represents a specific Ticker + Expiry Type combination (e.g., "SPY ODTE", "QQQ WEEKLY").

**Data Source:** `GET /api/v1/expected_moves/reliability/summary`

**Card Content:**
*   **Header:** Ticker & Expiry Type (e.g., **SPY - ODTE**)
*   **Primary Metric:** Hit Rate %
    *   *Visual:* Large percentage text (e.g., **85%**).
    *   *Color Coding:* Green (>80%), Yellow (60-80%), Red (<60%).
*   **Secondary Metrics:**
    *   **Avg Breach:** Displayed in dollars (e.g., "Avg Miss: $1.50").
    *   **Max Breach:** Displayed in percent (e.g., "Max Miss: 2.1%").
*   **Volume:** Total records analyzed (e.g., "N=150").

**Mockup Layout (Grid):**
```
[ SPY ODTE ] [ SPY WEEKLY ] [ QQQ ODTE ] [ QQQ WEEKLY ] ...
```

---

## 2. Historical Records Table Section

**Visual Style:** A sortable, filterable data table.

**Data Source:** `GET /api/v1/expected_moves/reliability/history`

**Features:**
*   **Filtering:** Dropdowns for Ticker (All/SPY/QQQ...) and Expiry Type (All/ODTE/WEEKLY...).
*   **Sorting:** Default sort by `Calculation Date` (Descending).

**Columns:**

| Column Name | Data Field | Rendering Logic |
| :--- | :--- | :--- |
| **Calc Date** | `timestamp` | Format: `YYYY-MM-DD` |
| **Expiry Date** | `expiry_date` | Format: `YYYY-MM-DD` |
| **Ticker** | `ticker` | Text (e.g., SPY) |
| **Type** | `expiry_type` | Badge (ODTE=Blue, WEEKLY=Purple) |
| **EM Range** | `lower_range` - `upper_range` | Text: `$450.00 - $455.00` |
| **Realized Close** | `realized_ohlc.close` | Text: `$452.50` (or "-" if pending) |
| **Status** | `closed_within_em` | **Badge:**<br>✅ **Success** (Green) if True<br>❌ **Breach** (Red) if False<br>⏳ **Pending** (Gray) if null |
| **Confidence** | `confidence_score_percent` | Progress Bar or Color-coded Text (0-100%) |

---

## Data Binding & State Management

**React Hooks:**
*   `useReliabilitySummary()`: Fetches summary data on mount.
*   `useReliabilityHistory(filters)`: Fetches history data, re-fetching when filters change.

**API Integration:**
```javascript
// Example Fetch Logic
const fetchSummary = async () => {
  const res = await fetch('/api/v1/expected_moves/reliability/summary');
  return res.json();
};

const fetchHistory = async (ticker, type) => {
  const params = new URLSearchParams();
  if (ticker) params.append('ticker', ticker);
  if (type) params.append('expiry_type', type);
  const res = await fetch(`/api/v1/expected_moves/reliability/history?${params}`);
  return res.json();
};
```

## User Interaction Flow
1.  **Page Load:** User lands on `/analysis/reliability`.
2.  **Initial Fetch:** Both Summary and History (unfiltered) load.
3.  **Review:** User sees high-level hit rates in the top cards.
4.  **Drill Down:** User filters the table to "SPY" to see specific recent failures.
5.  **Analysis:** User identifies that breaches often occur on low-confidence days (correlation check).
