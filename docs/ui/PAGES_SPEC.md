# PAGES SPEC — Market Intelligence Engine

## Shared Controls
- **Ticker selector**: default SPY; allow QQQ, DIA, IWM (extend later).
- **History window**: 1Y, 3Y, 5Y, Max (UI filters only; data is precomputed).
- **Data freshness**: shows last feature/HMM/Markov compute timestamps.

---

## 1) Market Regime Dashboard (Home)
**Purpose**: At-a-glance market state with explainers.

**Header row KPIs (left-to-right)**
- HMM: Bear prob / Bull prob (for selected n_states)
- Markov: P(Green next day) from latest valid context (order=1–4 mini row)
- Downtrend Score (composite), if available; else placeholder

**Cards**
1. **SPY Price with HMM Regimes**
   - Source: `data/analytics/hmm/{TICKER}/hmm_states.parquet`, `hmm_probs.parquet`
   - Chart: Price overlaid with regime colors; hover shows probs
   - Summary (auto): “Over the last X days, regime = Bear/Bull; avg bull prob = …”
   - Actions: Expand, Download CSV/PNG
2. **Markov Order Sweep — Latest Context**
   - Source: `data/analytics/markov/{TICKER}/order_sweep.csv`
   - Chart: grouped bars (orders on X) for next-day probs
   - Table: same numbers in compact % format
   - Summary: “Given context <…>, P(Up) ≈ … across orders …”
3. **One-step Next-State Table**
   - Source: `data/analytics/markov/{TICKER}/matrix_order{K}.parquet` (K from UI radio)
   - Table: transition probs with row sum = 1
   - Heatmap: small, compact
   - Summary: “Most likely transition: …; least likely: …”

---

## 2) Regime Research Lab
**Purpose**: Deep dive into Markov and HMM.

**Cards**
1. **HMM Model Explorer**
   - Inputs selector: n_states (2/3), train window Y
   - Source (precomputed variants as available)
   - Charts: regime probs over time; transition matrix table
   - Summary: state mappings; avg returns by state
2. **Markov Chain Explorer**
   - Inputs selector: order K, threshold bps, mode (binary/tri)
   - Source: `states.parquet`, `matrix_orderK.parquet`, `predictions.parquet`
   - Charts: transition heatmap; predictions timeline (prob up/down/neutral)
   - Summary: recent context + its next-day forecast

---

## 3) Alpha Signals Lab
**Purpose**: Downtrend confirmation & breadth.

**Cards**
1. **Downtrend Confirmation Score**
   - Source: `data/signals/{TICKER}/downtrend_score.parquet`
   - Chart: Score timeline; shaded alert zones
   - Summary: “Score > X persisted Y days → elevated risk”
2. **Seasonality Snapshot** (later)
   - Source: `data/analytics/seasonality/{TICKER}/…`
   - Chart: monthly avg returns heatmap
   - Summary: compact takeaway

---

## 4) Data Control Panel
**Purpose**: Ops visibility (read-only).

**Cards**
- Dataset registry table: first_date, last_date, rows, last_run_ts
- Buttons (disabled if no automation): rebuild features, update raw, recompute models (placeholders)
- Logs: last N lines (optional)