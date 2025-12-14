---
title: Page Spec – Hidden Markov Model (Regimes)
version: 2.0.0
last_updated: 2025-11-14
status: active
owner: product+architecture
---

# Hidden Markov Model (Regimes) – Page Spec (v2)

This spec defines the **Hidden Markov Model (Regimes)** page:
- UX structure and interactive controls
- Model training specifications
- Section-by-section behavior
- Charts, tables, and strategy backtests
- Text and summary patterns

It extends:
- [`../CORE/ARCHITECT_BIBLE.md`](../CORE/ARCHITECT_BIBLE.md)
- [`UI_README_v2.md`](UI_README_v2.md)
- [`CHART_SPECS_v2.md`](CHART_SPECS_v2.md)
- [`DESIGN_BRIEF_v2.md`](DESIGN_BRIEF_v2.md)

**Related Documentation**:
- [`PAGE_SPEC_MARKOV_v2.md`](PAGE_SPEC_MARKOV_v2.md) — Related Markov Chains page spec
- [`../CORE/ANALYTICS_REFERENCE.md`](../CORE/ANALYTICS_REFERENCE.md) — HMM analytics reference
- [`../DEVELOPMENT/TESTING.md`](../DEVELOPMENT/TESTING.md) — Testing requirements

---

## 1. Purpose

Provide an **interactive regime detection and analysis tool** using Hidden Markov Models (HMM) with Gaussian emissions to:
- Identify market regimes (Bull, Bear, Neutral) from price returns and realized volatility
- Visualize regime probabilities over time
- Compute transition matrices and expected regime durations
- Backtest regime-based trading strategies

**Key Distinction from Offline Analytics:**
- This page trains HMM models **on-demand** in the UI using cached computations
- Models are trained with user-selected parameters (n_states, training window, features)
- Results are ephemeral (not persisted to disk)

---

## 2. Inputs & Controls

**Sidebar Configuration Panel:**

### 2.1 Ticker Selection
- **Control**: `st.selectbox("Ticker", ...)`
- **Source**: `config/tickers.yml`
- **Default**: `SPY`
- **Behavior**: Changes trigger full model retraining

### 2.2 Hidden States
- **Control**: `st.selectbox("Hidden states", options=[2, 3])`
- **Default**: `3` (Bull, Neutral, Bear)
- **Options**:
  - `2`: Bull/Bear only
  - `3`: Bull/Neutral/Bear
- **Behavior**: Changes model complexity and state identification

### 2.3 Feature Selection
- **Control**: `st.checkbox("Include RV20 feature", value=True)`
- **Default**: `True` (checked)
- **Features Used**:
  - Always: Daily returns (`ret_1d`)
  - Optional: 20-day realized volatility (`rv_20d`)
- **Rationale**: RV20 improves regime separation by capturing volatility clustering

### 2.4 Training Window
- **Control**: `st.select_slider("Training window (years)", options=[5, 10, 15, 20, 25])`
- **Default**: `15` years
- **Minimum Data**: 400 trading days
- **Behavior**: Determines how far back to train the HMM (uses most recent N years)

### 2.5 Signal Thresholds
- **Bull Signal Threshold**:
  - `st.slider("Bull signal threshold", min=0.50, max=0.95, value=0.60, step=0.01)`
  - Defines minimum probability to classify as Bull regime
- **Bear Signal Threshold**:
  - `st.slider("Bear signal threshold", min=0.50, max=0.95, value=0.60, step=0.01)`
  - Defines minimum probability to classify as Bear regime
- **Usage**: Used for strategy backtests and signal generation

### 2.6 Backtest Evaluation Window
- **Control**: `st.selectbox("Backtest evaluation window", options=["5y", "10y", "15y", "20y"])`
- **Default**: `5y`
- **Behavior**: Limits strategy backtest to most recent N years of data

---

## 3. Data Requirements

### 3.1 Input Data
- **Source**: `data/features/{TICKER}.parquet`
- **Required Columns**:
  - `date`: Trading date (timezone-naive)
  - `close` or `adj_close`: Price for visualization
  - `ret_1d`: Daily returns (feature for HMM)
  - `rv_20d`: 20-day realized volatility (optional feature)

### 3.2 Missing Data Handling
- **If features file missing**:
  - Show error: `"Features parquet for {ticker} not found at {path}. Run the feature pipeline first."`
  - Display CLI hint: `python cli/mie.py rebuild-features --tickers {ticker}`
  - Stop page execution (`st.stop()`)

- **If insufficient training data**:
  - Show warning: `"Not enough training data: {rows} rows (need ≥{MIN_TRAIN_ROWS})"`
  - Stop page execution

---

## 4. Model Training Specification

### 4.1 HMM Configuration
- **Library**: `hmmlearn.hmm.GaussianHMM`
- **Model Type**: Gaussian emissions with diagonal covariance
- **Algorithm**: Viterbi for state decoding
- **Parameters**:
  - `n_components`: User-selected (2 or 3 states)
  - `covariance_type`: `"diag"`
  - `n_iter`: 100 iterations max
  - `random_state`: 42 (deterministic)
  - `tol`: 1e-4 (convergence threshold)

### 4.2 Training Process
1. **Data Preparation**:
   - Load features from Parquet
   - Filter to training window (most recent N years)
   - Extract feature columns: `[ret_1d]` or `[ret_1d, rv_20d]`
   - Ensure ≥400 rows for stable training

2. **Model Fitting**:
   - Fit GaussianHMM to feature matrix
   - Decode states using Viterbi algorithm
   - Map numeric states (0,1,2) to semantic names (Bull/Neutral/Bear)

3. **State Mapping Logic**:
   - Sort states by mean return (ascending)
   - Lowest mean → Bear
   - Highest mean → Bull
   - Middle mean → Neutral (if 3 states)

4. **Post-Processing**:
   - Compute state probabilities for all dates
   - Compute transition matrix
   - Calculate expected durations: `1 / (1 - P(stay))`

### 4.3 Caching
- **Decorator**: `@st.cache_data(show_spinner=False)`
- **Cache Key**: `(ticker, n_states, include_rv20, train_window_years)`
- **Benefits**: Avoid retraining when switching between charts/views

---

## 5. Page Layout & Sections

### 5.1 Header
- **Title**: `"Hidden Markov Model (Regimes)"`
- **Meta Line**:
  - Format: `Release: {version} • Last updated: {timestamp} UTC • Data coverage: {ticker} ({start_date} – {end_date})`
  - Example: `Release: 1.2.3 • Last updated: 2025-11-14 15:30 UTC • Data coverage: SPY (1993-01-29 – 2025-10-31)`

- **Subtitle (Below Charts)**:
  - Shows active configuration
  - Format: `States={n}, Window={years}y, RV20={'On'|'Off'}, Bull≥{threshold:.2f}, Bear≥{threshold:.2f}`
  - Example: `States=3, Window=15y, RV20=On, Bull≥0.60, Bear≥0.60`

---

### 5.2 Section: Price Chart with Regime Overlay

**Title**: `"Price Chart with Regime Shading"`

**Visual Specification**:
- **Chart Type**: Line chart with vertical rectangles (regime shading)
- **X-Axis**: Date
- **Y-Axis**: Price (log scale optional)
- **Components**:
  1. **Regime Shading**: Vertical rectangles colored by current regime
     - Bull: `#00B050` (green)
     - Bear: `#C00000` (red)
     - Neutral: `#999999` (gray)
     - Opacity: 0.15 for background shading
  2. **Price Line**: `#33B5FF` (blue), overlaid on regime shading
  3. **Hover Tooltip**:
     - Date
     - Price
     - Current regime
     - Bull/Neutral/Bear probabilities

**Implementation Notes**:
- Use `go.Figure()` with `add_vrect()` for regime shading
- Each regime change creates a new rectangle
- Price line rendered last (on top of shading)
- Template: `plotly_dark`
- Height: 500px

**Summary Text**:
- Auto-generated summary describing current regime and recent transitions
- Example: `"Currently in Bull regime (prob=0.85). Last regime change: 2025-10-15 (Bear → Bull)."`

---

### 5.3 Section: Probability Timeline

**Title**: `"Regime Probabilities Over Time"`

**Visual Specification**:
- **Chart Type**: Stacked area chart
- **X-Axis**: Date
- **Y-Axis**: Probability (0–1 scale)
- **Series** (stacked):
  1. Bull probability (green `#00B050`)
  2. Neutral probability (gray `#999999`) — if 3-state model
  3. Bear probability (red `#C00000`)
- **Stackgroup**: All series stacked to sum to 1.0
- **Hover Mode**: `x unified` (show all probabilities at once)
- **Template**: `plotly_dark`
- **Height**: 400px

**Summary Text**:
- Describe dominant regime and stability
- Example: `"Bull regime dominates 65% of the period. High stability with avg duration of 45 trading days."`

---

### 5.4 Section: Transition Matrix Heatmap

**Title**: `"Transition Matrix"`

**Visual Specification**:
- **Chart Type**: Heatmap
- **Dimensions**: 
  - Rows: Current state (Bull, Neutral, Bear)
  - Columns: Next state (Bull, Neutral, Bear)
- **Cell Values**: Transition probabilities (0–1)
- **Colorscale**: 
  - `[[0.0, "#E0E0E0"], [0.5, "#F2C94C"], [1.0, "#008F39"]]`
  - Light gray → yellow → green
- **Text Annotations**: Probability percentages in each cell (e.g., "53.2%")
- **Template**: `plotly_dark`
- **Height**: 400px

**Data Table**:
- Display transition matrix as formatted table below heatmap
- Columns: `from_state`, `to_Bull`, `to_Neutral`, `to_Bear`
- Format: Percentages with 1 decimal place

**Expected Duration Table**:
- Show expected regime durations (in trading days)
- Columns: `state`, `expected_duration_days`
- Calculation: `1 / (1 - diagonal_probability)`

**Summary Text**:
- Highlight strongest and weakest transitions
- Example: `"Strongest persistence: Bull → Bull (75.3%). Most volatile: Neutral (avg duration 12 days)."`

---

### 5.5 Section: Regime Statistics

**Title**: `"Regime Statistics"`

**Data Table**:
- **Columns**:
  - `regime`: State name (Bull, Neutral, Bear)
  - `occurrences`: Number of days in this regime
  - `pct_of_days`: Percentage of total days
  - `avg_return`: Average daily return during regime
  - `volatility`: Standard deviation of returns during regime
  - `sharpe`: Sharpe ratio (annualized, assuming 252 trading days)
  - `expected_duration`: Average days per regime episode

**Formatting**:
- Percentages: 1 decimal place
- Returns: 2 decimal places
- Duration: Integer days
- Color-code regime names per STATE_COLORS

**Summary Text**:
- Compare regime characteristics
- Example: `"Bull regime shows 0.08% avg daily return with lower volatility. Bear regime: -0.12% return with 1.5x higher volatility."`

---

### 5.6 Section: Strategy Backtests

**Title**: `"Strategy Backtests (Last {N} Years)"`

**Strategy Variants**:
1. **Long-only**: Always invested (buy-and-hold)
2. **Bull signals**: Long only when `P(Bull) ≥ threshold`
3. **Bear signals**: Short only when `P(Bear) ≥ threshold`
4. **Bull-only**: Long when Bull, cash otherwise
5. **Bear-avoidance**: Long when NOT Bear (above threshold)
6. **Bull+BearShort**: Long when Bull, short when Bear

**Performance Metrics Table**:
- **Columns**:
  - `strategy`: Strategy name
  - `total_return`: Cumulative return (%)
  - `cagr`: Compound annual growth rate (%)
  - `volatility`: Annualized volatility (%)
  - `sharpe`: Sharpe ratio
  - `max_drawdown`: Maximum peak-to-trough decline (%)

**Equity Curves Chart**:
- **Chart Type**: Multi-line chart
- **X-Axis**: Date
- **Y-Axis**: Growth of $1 (log scale optional)
- **Series**: One line per strategy
- **Colors**: Distinct colors per strategy
- **Template**: `plotly_dark`
- **Height**: 460px
- **Legend**: Horizontal, bottom

**Summary Text**:
- Identify best/worst performing strategies
- Example: `"Bull-only strategy achieves 12.5% CAGR vs. 8.2% buy-and-hold. Bear-avoidance reduces max drawdown to -15% (vs. -32%)."`

---

## 6. Error Handling & Edge Cases

### 6.1 Missing Dependencies
- **Error**: `hmmlearn` not installed
- **Message**: `"hmmlearn is not installed. Install it via pip install hmmlearn to use this page."`
- **Action**: Stop page execution

### 6.2 Insufficient Data
- **Error**: Training window requires 400+ rows, but fewer available
- **Message**: `"Not enough training data: {rows} rows (need ≥400)"`
- **Action**: Show warning and stop

### 6.3 Model Training Failures
- **Error**: GaussianHMM fitting fails (numerical issues)
- **Message**: `"HMM training failed: {error_message}"`
- **Action**: Show error and stop

### 6.4 State Mapping Edge Cases
- **2-state model**: Map to Bull/Bear only (no Neutral)
- **Identical mean returns**: Use variance as tiebreaker
- **Non-convergence**: Show warning if `n_iter` reached without convergence

---

## 7. Performance & Optimization

### 7.1 Caching Strategy
- Cache HMM training results with `@st.cache_data`
- Cache key includes all model parameters
- Cache invalidates on parameter change

### 7.2 Data Downsampling
- If feature history >10,000 rows, consider warning about long training times
- Charts automatically downsample to ≤2,500 points (per CHART_SPECS_v2.md)

### 7.3 Spinner Messages
- Show `"Training HMM and loading artifacts..."` during model fit
- Suppress cache spinner (`show_spinner=False` on cache decorator)

---

## 8. Implementation Reference

**File**: `app/pages/04_Hidden_Markov_Model.py`

**Key Functions**:
- `_train_and_score_hmm()`: Train model and return results dataclass
- `_map_state_names()`: Map numeric states to Bull/Neutral/Bear
- `_compute_strategy_returns()`: Calculate backtest metrics
- `_render_price_chart()`: Price with regime shading (vrect)
- `_render_probability_chart()`: Stacked probability areas
- `_render_transition_matrix()`: Heatmap + tables
- `_render_regime_stats()`: Statistics table
- `_render_strategy_backtests()`: Backtest table + equity curves

**Key Constants**:
- `STATE_DISPLAY_ORDER`: `["Bull", "Neutral", "Bear"]`
- `STATE_COLORS`: `{"Bull": "#00B050", "Bear": "#C00000", "Neutral": "#999999"}`
- `PRICE_COLOR`: `"#33B5FF"`
- `MIN_TRAIN_ROWS`: `400`
- `DEFAULT_RANDOM_SEED`: `42`

---

## 9. Testing Requirements

Changes to this page must:
- Keep all existing tests green: `python -m pytest tests/test_hmm.py -v`
- Verify:
  - HMM training with 2 and 3 states
  - State mapping correctness (Bull = highest mean)
  - Transition matrix row sums = 1.0
  - Strategy return calculations
  - Edge cases (insufficient data, missing features)

No change violating this spec is allowed without an explicit spec patch.

---

## 10. Future Enhancements (Out of Scope)

These are **not** currently implemented but may be added:

1. **Persistent HMM Artifacts**:
   - Save trained models to `data/analytics/hmm/` for offline reuse
   - Would align with Markov page's offline-first approach

2. **Multiple Model Comparison**:
   - Side-by-side comparison of 2-state vs 3-state models
   - Statistical model selection (BIC/AIC)

3. **Advanced Features**:
   - Include momentum, moving averages, or technical indicators
   - Feature importance analysis

4. **Regime Forecasting**:
   - N-step ahead regime probability forecasts
   - Similar to Markov horizon analysis

Any implementation of these features requires:
- Update to this spec
- Alignment with `ARCHITECT_BIBLE.md` offline-first principles
- Full test coverage
