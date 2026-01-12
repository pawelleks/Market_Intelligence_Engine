# Economic Models Signal Audit

**Audit Date**: 2026-01-10
**Repository**: Market Intelligence Engine (Economic Analysis)

## Executive Summary
The system currently implements **9 distinct economic models** ranging from business cycle timing (LEI/COI, LAG) to structural risk analysis (Minsky, ABCT) and quantitative signal detection (Hamilton, HP Filter).

Several models are highly sophisticated (Minsky, ABCT), incorporating specific heterodox economic theories. The core "Business Cycle" logic successfully integrates Leading (LEI), Coincident (COI), and Lagging (LAG) indicators into a unified state machine.

**Key Findings:**
- **Data Completeness**: Most models rely on FRED data with good historical depth (1970s+), but some specific series (e.g., Chicago Fed NFCI, specific credit metrics) may limit backtesting before 1990.
- **Signal Clarity**: Signals are generally well-defined (binary Recession flags vs. continuous Z-Scores), but a unified "Risk Level" across all models is currently missing.
- **Validation**: Minsky and ABCT models include specific "trap" or "validation" logic (e.g., checking 2008 behavior), which is a strong practice.

---

## Model Inventory & Readiness

| Model | Primary Inputs | Logic Type | Signal Output | Readiness | Priority Gap |
|-------|----------------|------------|---------------|-----------|--------------|
| **Enhanced LEI/COI** | Housing, Hours, FinCond, IndPro, NFP | Z-Score Aggregation | LEI < -1.0 (Recession) | 🟢 Ready | None |
| **Business Cycle** | LEI, COI, Core CPI, Unrate | State Machine | 4-Phases (Recovery...Recession) | 🟢 Ready | None |
| **Minsky Model** | Corp Debt, Profits, Yields | Ratio Analysis | Instability Gap, Regime (Ponzi/Hedge) | 🟢 Ready | Need daily data consistency |
| **ABCT Model** | Cap Goods PPI, CPI, Savings, Credit | Structural Ratios | Boom Score, Wicksellian Spread | 🟢 Ready | None |
| **Hamilton Switch** | Real GDP | Markov Switching | Recession Probability (%) | 🟡 Partial | Quarterly only (lagged) |
| **HP Filter** | Real GDP, Credit | Trend Decomposition | Output Gap, Credit Gap | 🟢 Ready | Filtering end-point bias risk |
| **Liquidity Impulse** | Fed/ECB/BoJ Assets | Rate of Change | Impulse % (Expanding/Contracting) | 🟢 Ready | FX volatility noise |
| **Recession Momentum** | NFP (PAYEMS) | Trend/SMA | Stall Speed (< 97k jobs) | 🟢 Ready | Binary only, lacks nuance |
| **LAG Index** | CPI Svc, Unrate, ULC, Loans | Inertia/Z-Score | Cycle Peak Confirmation | 🟢 Ready | None |

---

## Detailed Model Analysis

### 1. Enhanced LEI/COI
*   **File**: `scripts/update_economy_data_enhanced.py`
*   **Description**: 3-Factor Leading and 2-Factor Coincident index.
*   **Inputs**:
    *   `HOUST` (Starts), `AWHMAN` (Hours), `NFCI` (Financial Cond) -> **LEI**
    *   `INDPRO` (Production), `PAYEMS` (NFP) -> **COI**
*   **Signal System**:
    *   **Recession Signal**: LEI < -1.0
    *   **Warning**: LEI < -1.0 (used in Frontend)
*   **History**: 1970+ (dependent on NFCI start date).
*   **Assessment**: The core navigational tool. High readiness.

### 2. Business Cycle (LAG + Phases)
*   **File**: `scripts/calculate_business_cycle.py`
*   **Description**: Completes the cycle picture by adding a Lagging Indicator.
*   **Inputs**: `CPILFESL` (Core CPI), `UNRATE`, `SP500`.
*   **Signal System**:
    *   **Phases**: Recovery, Expansion, Slowdown, Recession.
    *   **Logic**: Relative ordering of LEI vs COI vs LAG.
*   **Assessment**: Excellent for timing "Cycle Turns" rather than just "Recession Risk".

### 3. Minsky Financial Instability
*   **File**: `scripts/calculate_minsky_model.py`
*   **Description**: Detects financial fragility vs stability (Hedge/Speculative/Ponzi regimes).
*   **Inputs**:
    *   `BCNSDODNS` (Corp Debt), `CPATAX` (Profits), `BAA10Y` (spread), `LABSHPUSA156NRUG` (Labor Share).
*   **Signal System**:
    *   **Instability Gap**: Debt Growth - Profit Growth (Positive = Bad).
    *   **Regime**: Hedge (Gap < 0), Speculative (Gap > 0), Ponzi (Gap > 0 & Risk Complacency > 0.5).
*   **Assessment**: Unique structural risk model. Essential for "Credit Event" prediction.

### 4. Austrian Business Cycle (ABCT)
*   **File**: `scripts/calculate_abct_model.py`
*   **Description**: Analyzes distortions in capital structure and interest rates.
*   **Inputs**: `WPSFD41312` (Cap Goods PPI), `CPIAUCSL`, `TOTLL` (Loans), `PSAVERT` (Savings), `FEDFUNDS`.
*   **Signal System**:
    *   **Malinvestment Ratio**: Price of Capital Goods / Consumer Goods.
    *   **Wicksellian Spread**: Natural Rate Proxy - Fed Funds (Positive = Rates "Too Low").
    *   **Boom Score**: Composite Z-Score of distortions.
*   **Assessment**: Detects "Artificial Booms" before they bust. Complements Minsky.

### 5. Hamilton Markov Switching
*   **File**: `scripts/hamilton_model_generator.py`
*   **Description**: Probabilistic detection of recession regimes using Real GDP.
*   **Inputs**: `GDPC1` (Real GDP via HP Filter model).
*   **Signal System**:
    *   **Recession Prob**: 0-100% probability of being in low/negative growth regime.
*   **Assessment**: Good confirmation, but GDP is quarterly and lagged. "Rear-view mirror" signal.

### 6. HP Filter (Output & Credit Gaps)
*   **File**: `scripts/hp_model_generator.py`
*   **Description**: Decomposes GDP and Credit into Trend vs Cycle.
*   **Inputs**: `GDPC1`, `TOTDTEUSQ163N` (Nominal Credit), `GDPDEF`.
*   **Signal System**:
    *   **Output Gap**: Excess demand vs potential.
    *   **Credit Gap**: Excess credit vs trend (Lead indicator for banking crises).
*   **Assessment**: Standard IMF/Central Bank style analysis. 

### 7. Global Liquidity Impulse
*   **File**: `scripts/liquidity_impulse_generator.py`
*   **Description**: Tracks global central bank balance sheet expansion/contraction.
*   **Inputs**: Fed (`WALCL`), ECB (`ECBASSETS`), BoJ (`JPNASSETS`), FX Rates.
*   **Signal System**:
    *   **Impulse**: 3-Month Rate of Change.
    *   **State**: Expanding (>0) vs Contracting (<0).
*   **Assessment**: Critical for asset price correlation (Beta).

### 8. Recession Momentum (Stall Speed)
*   **File**: `scripts/recession_momentum_generator.py`
*   **Description**: Simple Stall Speed model for Employment.
*   **Inputs**: `PAYEMS` (NFP).
*   **Signal System**:
    *   **Signal**: 12-Month SMA of Job Gains < 97k.
*   **Assessment**: Simple, robust binary rule.

### 9. LAG Index (Inertia)
*   **File**: `scripts/calculate_lag_index.py`
*   **Description**: Verifies cycle maturity.
*   **Inputs**: CPI Services, Unemployment (Inverted), Unit Labor Costs, Loans.
*   **Signal System**:
    *   **Concept**: Peaks *after* the recession starts. Confirms "The Fed is trapped" (Inflation/Cost sticky while growth falls).
*   **Assessment**: Validation tool for the "Slowdown" phase.

---

## Recommendations
1.  **Unified Risk Gauge**: Create a master `Economic Risk` score (0-100) aggregating Minsky (Fragility), ABCT (Distortion), and LEI (Timing).
2.  **Daily Interpolation**: Most advanced models (Hamilton, HP, Minsky) are Quarterly. For market prediction, careful daily interpolation (ffill vs linear) is needed to avoid look-ahead bias in backtests.
3.  **Visualization**: The frontend currently focuses on LEI/COI. It should be expanded to show the "Cycle Phase" and the "Minsky/ABCT Risk" dashboards.
