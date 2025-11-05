# CHART SPECS — Market Intelligence Engine

## Conventions
- Dark theme. Axes and labels in #D7E3F3, thin gridlines #203049.
- Default size small; each chart has an Expand action opening a modal at 1200x700.
- Downsample to ≤ 2,500 points per series.
- Tooltip shows exact values + date.
- Percentages shown with 1 decimal place by default.

---

### CHART 1 — SPY Price with HMM Regimes
**Goal**: Show regimes overlay and help users visually spot regime shifts.
**Data**:
- Price: `data/features/{TICKER}.parquet` (adj_close or close)
- Regimes: `data/analytics/hmm/{TICKER}/hmm_states.parquet` + `hmm_probs.parquet`
**Encoding**:
- Line: price
- Background bands or under-curve fill by regime: Bull (green), Bear (red), Neutral (gray)
**Interactions**:
- Tooltip with date, price, probs
- Expand to modal with zoom/pan
**Summary (auto)**:
- Recent regime, average bull/bear prob over last N days

---

### CHART 2 — Markov Order Sweep (Latest Context)
**Goal**: Compare next-day probabilities across orders.
**Data**: `data/analytics/markov/{TICKER}/order_sweep.csv`
**Encoding**:
- X: order (1..4)
- Y: grouped bars for P(Up), P(Neutral), P(Down)
- Labels: compact % on bars
**Interactions**:
- Tooltip: full % and support_count
- Expand: larger grouped bar chart with table
**Summary (auto)**:
- “Given context <…>, P(Up)≈…, coverage …%”

---

### CHART 3 — Markov Transition Heatmap
**Goal**: Show transition probabilities per context (rows sum to 1).
**Data**: `data/analytics/markov/{TICKER}/matrix_order{K}.parquet`
**Encoding**:
- Heatmap (rows: contexts, cols: next states)
**Interactions**:
- Tooltip on cell: prob %, sample count if available
- Expand: larger heatmap with sorting by row entropy or support
**Summary (auto)**:
- “Most likely transition: X→Y at Z%”

---

### CHART 4 — HMM Probabilities Timeline
**Goal**: Show smooth regime probabilities through time.
**Data**: `data/analytics/hmm/{TICKER}/hmm_probs.parquet`
**Encoding**:
- Lines: prob_bull, prob_bear, (prob_neutral if 3-state)
**Interactions**:
- Tooltip with date + probs
- Expand with zoom/pan
**Summary (auto)**:
- “Bull prob averaged …% over last N days”

---

### CHART 5 — Downtrend Confirmation Score
**Goal**: Visual alerting for elevated downside risk.
**Data**: `data/signals/{TICKER}/downtrend_score.parquet`
**Encoding**:
- Line: score (0–100)
- Shaded bands for alert thresholds (e.g., 60, 80)
**Interactions**:
- Tooltip; expand; download
**Summary (auto)**:
- “Score > X for Y days → high caution”