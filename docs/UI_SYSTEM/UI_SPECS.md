# UI System Specifications (v3)

**Status**: Active / In Development
**Stack**: React, Vite, TailwindCSS, Recharts
**Backend**: FastAPI (`mie-api`)

---

## 1. Overview

The Market Intelligence Engine (MIE) UI is a modern single-page application (SPA) designed for high-performance interactive analytics. Unlike the previous Streamlit version (v2), this system decouples the frontend from the data processing layer completely.

### Core Architecture
-   **Frontend**: React 18+ (Vite)
-   **Styling**: TailwindCSS (Utility-first) + Custom Design Tokens
-   **Charts**: Recharts (primary) & Plotly.js (complex heatmaps)
-   **State Management**: React Query (Server State) + Context/Zustand (Client State)
-   **API Client**: Axios with strict typing

---

## 2. Design System

### 2.1 Theme & Colors
The UI operates in a **Dark Mode** by default, optimized for financial data visualization.

-   **Backgrounds**:
    -   `bg-slate-900` (App Background)
    -   `bg-slate-800` (Card/Panel Surface)
-   **Text**:
    -   `text-slate-50` (Primary)
    -   `text-slate-400` (Secondary/Muted)
-   **Semantic Colors**:
    -   **Bullish/Green**: `text-emerald-400`, `bg-emerald-500/20`
    -   **Bearish/Red**: `text-rose-400`, `bg-rose-500/20`
    -   **Neutral/Gray**: `text-slate-400`, `bg-slate-500/20`
    -   **Accent**: `indigo-500` (Primary Actions)

### 2.2 Typography
-   **Font Family**: Inter (sans-serif)
-   **Headings**: Bold, Tracking-tight for modern feel.
-   **Data**: Monospace (JetBrains Mono or similar) for tabular numbers.

---

## 3. Directory Structure (`frontend/src`)

```text
src/
├── components/         # Shared UI definitions
│   ├── common/         # Buttons, Inputs, Cards
│   ├── layout/         # Navbar, Sidebar, PageContainer
│   └── charts/         # Reusable Chart Wrappers
├── pages/              # Route Components (Pages)
│   ├── Dashboard/      # Main Executive Summary
│   ├── Markov/         # Markov Chain Analytics
│   ├── Seasonality/    # Seasonality Analysis
│   └── HMM/           # Hidden Markov Models
├── services/           # API Clients (Axios)
│   └── api.ts          # Central API definition
├── hooks/              # Custom React Hooks (useMarkov, useTicker)
├── types/              # TypeScript Interfaces
└── utils/              # Helper functions (Formatters, Dates)
```

---

## 4. Component Standards

### 4.1 "Smart" vs "Dumb" Components
-   **Page Components** (e.g., `MarkovPage.tsx`):
    -   Handle data fetching (`useQuery`).
    -   Manage page-level state (filters).
    -   Pass data down to dumb components.
-   **UI Components** (e.g., `TransitionMatrix.tsx`):
    -   Purely presentational.
    -   Accept data/props.
    -   No side effects or API calls.

### 4.2 Charts
-   Use `Recharts` for time-series and bar charts.
-   **Responsive**: All charts must be wrapped in `ResponsiveContainer`.
-   **Tooltips**: Custom tooltip components that match the dark theme.
-   **Optimization**: Use `memo` to prevent re-rendering charts on minor state changes.

---

## 5. API Integration Pattern

All backend communication must go through `src/services/api.ts`. Do not use `fetch` directly in components.

**Example Pattern:**

```typescript
// services/api.ts
export const fetchMarkovMatrix = async (ticker: string, order: number) => {
    const { data } = await api.get(\`/analytics/markov/\${ticker}\`, { params: { order } });
    return data;
};

// components/MarkovPage.tsx
const { data, isLoading } = useQuery(['markov', ticker, order], () => fetchMarkovMatrix(ticker, order));
```

---

## 6. Routing

We use `react-router-dom` (v6+).
-   `/` : Home / Dashboard
-   `/markov` : Markov Chain Analysis
-   `/hmm` : Hidden Markov Models
-   `/seasonality` : Seasonality Analysis
-   `/gaf` : GAF/CNN Patterns
-   `/settings` : Data Management

---

## 7. Development Workflow

1.  **Start Backend**: `docker-compose up mie-api` (Port 8000)
2.  **Start Frontend**: `cd frontend && npm run dev` (Port 5173)
3.  **Mocking**: Use `msw` (Mock Service Worker) for testing edge cases if backend is unavailable.

---

## 8. Legacy Migration Guide

If porting a page from Streamlit (v2):
1.  Identify the **Data Source** (Parquet file).
2.  Ensure a corresponding **API Endpoint** exists in `mie-api` (`src/mie_lib/api/routers/`).
3.  Create the **React Page**.
4.  Recreate the **Layout** using Grid/Flexbox.
5.  Replace Streamlit charts (`st.line_chart`) with `Recharts`.
