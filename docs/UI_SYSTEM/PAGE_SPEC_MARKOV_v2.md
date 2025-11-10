---
title: Page Spec – Markov Chains Analysis
version: 2.0.0
last_updated: 2025-11-07
status: active
owner: product+architecture
---

# Markov Chains Analysis – Page Spec (v2)

This spec defines the **Markov Chain (discretized returns)** page:
- UX structure
- Required inputs
- Expected offline artifacts
- Section-by-section behavior
- Text and summary patterns

It extends:
- `ARCHITECT_BIBLE.md`
- `UI_README_v2.md`
- `CHART_SPECS_v2.md`

---

## 1. Purpose

Provide an **intuitive yet rigorous view** of discrete return regimes modeled as Markov chains, for:
- Next-day transitions.
- Multi-step horizons.
- Different thresholds, state modes, orders, and windows.

All analytics must be sourced from offline-precomputed Parquet files.

---

## 2. Inputs & Controls

**Global filters (top-of-page):**

1. `Ticker`:
   - Allowed universe (e.g. SPY, QQQ, DIA, IWM).
   - Backed by existing artifacts; show a friendly message if unsupported.

2. `Time range`:
   - Options: `1Y, 2Y, 5Y, 10Y, 20Y, MAX`.
   - Maps to canonical keys used in file paths (e.g. `1Y` → `1Y`, `Max` → `MAX`).

3. `State mode`:
   - `binary` (U/D)
   - `tri` (U/N/D)

4. `Threshold (bps)`:
   - Supported grid: `0,5,10,15,20,25,30,40,50,75,100,125,150`
   - UI must snap to available artifacts; when missing, show CLI hint.

5. `Order (K)`:
   - `1,2,3,4`
   - Higher orders allowed only if artifact exists; otherwise show inline explanation.

6. `Source`:
   - Display-only, currently: `offline`.
   - Used to remind that values are derived from prebuilt matrices.

---

## 3. Offline Artifacts (Contract)

All reads from `data/analytics/markov/{TICKER}`.

Required patterns:

- States:
  - `states_thr{thr}_{mode}.parquet`
- Matrices (grid-based K-order, windowed):
  - `matrices/{mode}/thr{thr}/order{K}/{WINDOW}.parquet`
- Meta:
  - `meta_states.json` (optional helper)
  - Optional matrix meta JSON.

If an artifact for a selected configuration is missing:
- Message: `Markov matrix unavailable for this configuration.`
- Include CLI hint:
  - `python cli/mie.py ensure-markov-available --ticker {T} --order {K} --state-mode {mode} --threshold-bps {thr} --window {WINDOW}`

No silent substitution across:
- Different thresholds
- Different windows
- Different orders
- Different modes

---

## 4. Page Layout & Sections

### 4.1 Header

- **Title**: `Markov Chains Analysis`
- **Meta line**:
  - `Release: vX.Y.Z • Last updated: YYYY-MM-DD HH:MM • Data coverage: [TICKERS] w/ windowed Markov matrices`
- Implementation:
  - `Last updated` = from artifacts or build metadata (not epoch junk).

---

### 4.2 Section: One-Step Next-State Summary

**Goal**: Human-readable statement of K=1 transition behavior for the current configuration.

1. **Title**: `One-Step Next-State Summary`
2. **Settings line**: standard pattern.
3. **Data source**:
   - Uses **K=1 matrix** for selected:
     - ticker, window, mode, threshold.
4. **Displayed content**:
   - A small result table OR direct extraction from K=1 matrix (optional minimal table).
   - Primary summary sentence:
     - Example:
       - `Given previous state was Green, next day is most likely Red (53.0%). Continuation (stay Green) = 47.0%.`
   - Color-coded state terms:
     - Green / Neutral / Red styled per DESIGN_BRIEF_v2.
5. **Rules**:
   - If K>1 selected, this summary is still based on **K=1** matrix (explicitly labeled as such), or clearly disabled with explanation.
   - If data missing → short hint, no crash.

---

### 4.3 Section: K=1 Transition Matrix

1. **Title**: `K=1 Transition Matrix`
2. **Settings line**: explicit K=1 even if global Order >1 (or clarify if tied to current order).
3. **Data**:
   - Load `matrices/{mode}/thr{thr}/order1/{WINDOW}.parquet`.
   - Show matrix with:
     - `context`
     - `mc_prob_*` columns
     - `counts`
   - Validate probabilities ~ sum to 1.
4. **Summary text**:
   - Example pattern:
     - `Strongest transition: Green → Red (53.0%). Weakest: Green → Green (47.0%). Overall tilt: mildly bearish.`
5. **If artifact missing**:
   - CLI hint as above.

---

### 4.4 Section: Multi-Horizon Forecasts (P^h Exact)

1. **Title**: `Multi-Horizon Forecasts (P^h)`
2. **Settings line**.
3. **Data & Logic**:
   - Use **K=1 matrix** as base transition matrix `P`.
   - Use matrix powers to compute:
     - `p(h) = p0 @ P^h` for horizons h ∈ {1,2,3,4,5}.
   - `p0`:
     - Derived from current state context selection OR last observed state, depending on UI.
     - Must be explicit and deterministic.
4. **Display**:
   - Table:
     - Rows: horizons
     - Cols: Green / Neutral / Red probabilities
   - Optional chart:
     - Per CHART_SPECS_v2 (e.g. stacked or grouped probabilities).
5. **Summary example**:
   - `Summary: probabilities show a persistent bearish bias (Red dominates in 4/5 horizons).`
6. **Constraints**:
   - No approximations, use exact `P^h`.
   - If K>1 in UI:
     - Either:
       - Clearly documented fallback to K=1 for horizon view, or
       - Use an approved higher-order logic per future spec.

---

### 4.5 Section: Higher-Order Contexts (K>1)

If implemented:

- Title: `Higher-Order Contexts (K>2)`
- Show:
  - Which contexts exist.
  - How sparsity affects interpretability.
- Must:
  - Not break or confuse non-quants.
  - Be optionally collapsible/advanced.

---

## 5. Error & Debug UI

- Debug JSON or raw dicts **must not** appear by default.
- Debug expanders allowed:
  - Collapsed by default.
  - Only for:
    - File paths
    - sha1
    - window/threshold diagnostics.

---

## 6. Tests & Acceptance

Changes to this page must:
- Keep all existing tests green:
  - `python -m pytest -q`
- Add/update:
  - UI-level helpers tests for:
    - horizon computations (P^h)
    - correct artifact path selection
    - no cross-threshold/window fallback.

No change violating this spec is allowed without an explicit spec patch.