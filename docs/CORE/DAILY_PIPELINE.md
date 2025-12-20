# Daily Pipeline Walkthrough

This document explains the **Daily Market Intelligence Engine Pipeline** (`orchestrator.sh`) step-by-step. It details what happens, where data comes from, and where it is stored.

## 🏃 Run the Pipeline
To run the full daily pipeline manually (e.g., if the automatic schedule missed a run):

```bash
docker exec -it mie-cron /app/cli/orchestrator.sh
```

---

## 📋 The Ticker List
The pipeline processes tickers defined in **`config/tickers.yml`**.
*   **How it works**: The script reads the `tickers:` section of this file.
*   **Groups**: Tickers can be grouped (e.g., `index`, `single_stock`), but the daily pipeline generally iterates through **all** defined tickers unless restricted (e.g., by `@scope`).
*   **Symbol Format**:
    *   `^GSPC` → S&P 500 Index (YFinance format)
    *   `SPY` → SPDR S&P 500 ETF
    *   **Note**: For Polygon.io interactions, the system automatically converts `^SYMBOL` to `I:SYMBOL` (e.g., `^GSPC` → `I:GSPC`).

---

## 🔄 Pipeline Steps (In Order)

### Phase 1: Ingestion (Getting Data)

#### 1. `update-raw` (Historical Price Data)
*   **What it does**: Fetches the latest daily Open/High/Low/Close/Volume (OHLCV) **Price** data for all tickers.
*   **Source**: **Yahoo Finance** (Official API via `yfinance`).
*   **Storage**: Time-series Parquet files.
    *   Path: `data/raw/{TICKER}.parquet`
*   **Why**: Essential for all technical analysis, charts, and trend models.

#### 2. `fetch-options-snapshot` (Options Chain)
*   **What it does**: Downloads the *entire* options chain (all strikes, all expirations) for the current day for every ticker.
*   **Source**: **Polygon.io** (Snapshot API).
*   **Storage**: A single massive CSV file per day.
    *   Path: `data/raw/massive/options/options_YYYY-MM-DD.csv`
*   **Why**: Required to calculate Gamma Exposure (GEX) profiles.

---

### Phase 2: Feature Engineering (Processing Data)

#### 3. `build-features` (Calculations & Returns)
*   **What it does**: Calculates **Returns**, technical indicators (RSI, Moving Averages, volatility, etc.), and other derived metrics.
*   **Source**: Reads from `data/raw/{TICKER}.parquet`.
*   **Storage**: Feature Parquet files.
    *   Path: `data/features/{TICKER}.parquet`
*   **Why**: These features feed the Minervini scanner, Markov models, and HMM analysis.

---

### Phase 3: Scanners & Analytics (Intelligence)

#### 4. `build-minervini-daily` (Trend Scanner)
*   **What it does**: Checks every ticker against Minervini Trend Template rules (e.g., "Price > 200 SMA").
*   **Source**: `data/features/{TICKER}.parquet`.
*   **Storage**: JSON result file.
    *   Path: `data/analytics/minervini/latest.json`
*   **Why**: Powers the "Trend Scanner" dashboard.

#### 5. `build-markov-grid` & `markov-snapshots` (Probability)
*   **What it does**: Updates the transition matrices for Market State analysis (e.g., "What is the probability of an Up day after a Down day?").
*   **Source**: `data/features/{TICKER}.parquet`.
*   **Storage**:
    *   Models: `data/analytics/markov/{TICKER}/...`
    *   Snapshots (Frontend): `data/analytics_snapshots/markov/{TICKER}/...`
*   **Why**: Powers the "Market Regimes" view.

#### 6. `build-hmm-daily` & `hmm-snapshots` (Regime Detection)
*   **What it does**: Updates Hidden Markov Models to classify the current market regime (e.g., "Bull Volatile", "Bear Quiet").
*   **Source**: `data/features/{TICKER}.parquet`.
*   **Storage**:
    *   Models: `data/analytics/hmm/{TICKER}/...`
    *   Snapshots (Frontend): `data/analytics_snapshots/hmm/{TICKER}/...`
*   **Why**: Powers the "HMM Backtest" and Regime dashboard.

#### 7. `build-gex-daily` (Gamma Exposure)
*   **What it does**: Processes the massive options CSV to calculate Net Gamma per strike.
*   **Source**: `data/raw/massive/options/options_YYYY-MM-DD.csv`.
*   **Storage**: Daily GEX profiles.
    *   Path: `data/analytics/gex/{TICKER}/profile_{YYYY-MM-DD}.json`
*   **Why**: Powers the "GEX" dashboard to show dealer positioning.

#### 8. `update-seasonality` (Historical Trends)
*   **What it does**: Updates the seasonality database (e.g., "How does AAPL typically perform in December?").
*   **Source**: `data/features/{TICKER}.parquet` (history).
*   **Storage**: Seasonality facts database in `data/analytics/seasonality/facts/...`
*   **Why**: Powers the "Seasonality" dashboard.

#### 9. Trend & Volatility Analytics
*   **What it does**: Computes and persists special analytics for the "Trading" dashboards.
    *   **SMA Stack**: Assessing alignment of short/long term moving averages.
    *   **ADX/DMI**: Trend strength analysis.
    *   **PSAR**: Parabolic SAR momentum.
    *   **Ichimoku**: Cloud trend analysis.
    *   **Volatility Term Structure**: Analysis of VIX/VIX3M ratio and Contango/Backwardation regimes.
*   **Source**: `data/features/{TICKER}.parquet` + VIX Data.
*   **Storage**: 
    *   Trend reports in `data/analytics/{ANALYTIC_NAME}/latest.json` or similar.
    *   Volatility report in `data/analytics/volatility_term_structure.json`.
*   **Why**: Powers the "Trading" section dashboards.

#### 10. `build-gaf-daily` (Computer Vision Prediction)
*   **What it does**: Generates a Gramian Angular Field (image of price action) and uses a CNN model to predict the next day's movement.
*   **Source**: `data/raw/{TICKER}.parquet`.
*   **Storage**: Prediction JSON.
    *   Path: `data/analytics/gaf/latest.json`
*   **Why**: Powers the "GAF Analysis" page.

#### 10. `update-expected-moves` (Volatility Range)
*   **What it does**: Calculates the expected weekly/monthly price range based on Implied Volatility (IV).
*   **Source**: **Hybrid**: Options & Spot via **Polygon.io**, VIX via **Yahoo Finance**.
*   **Storage**: A single JSON summary.
    *   Path: `data/analytics/options/latest.json`
*   **Why**: Powers the "Expected Moves" dashboard.

---

## ⚡ On-Demand Analytics (Not in Pipeline)
Some analytics are calculated **live** when you visit the dashboard, rather than being pre-computed in the daily batch.

#### Downtrend Confirmation Score (DCS)
*   **Status**: On-Demand (Real-time calculation).
*   **Why**: It aggregates multiple signals (Price, Features, VIX, etc.) and is lightweight enough to compute on the fly via the API (`/api/downtrend/...`).
*   **Source**: Uses the latest `data/features/{TICKER}.parquet` generated by Step 3.

---

## ✅ Completion
When the script finishes, it logs:
> `🚀 DAILY UPDATE COMPLETED SUCCESSFULLY 🚀`

All dashboards will now reflect data for the date `${TODAY}`.
