# Daily Pipeline Run Documentation

This document details the **Full Daily Pipeline** run (`cli/orchestrator.sh`), which is scheduled to run overnight (typically via cron in the `mie-cron` container).

## 🚀 Overview
**Entry Point**: `cli/orchestrator.sh`
**Schedule**: Overnight (Daily)
**Goal**: Update all data artifacts (Prices, Options, Analytics, Scanners) for the most recent completed trading day.

## 🔄 Dependency Graph (High Level)
1. **Raw Ingestion** (Prices, Options Snapshot)
    ↓
2. **Feature Engineering** (Technicals)
    ↓
3. **Analytics & Models** (Markov, HMM, Minervini, GEX, Seasonality, etc.)
    ↓
4. **Snapshots** (JSON/Parquet optimized for Frontend)

---

## 📝 Step-by-Step Breakdown

### 1. Ingestion Phase

#### Step 1.1: Fetch Historical Prices (`update-raw`)
*   **Command**: `python -m mie_lib.cli.mie update-raw`
*   **Description**: Incrementally updates OHLCV price data for all configured tickers. Fetches only missing data since the last update.
*   **Source Code**: `mie_lib.data_ingest.yfinance_loader.update_ticker_incremental`
*   **Dependencies**: Internet (Yahoo Finance API)
*   **Output**:
    *   `data/raw/{TICKER}.parquet` (Time series data)

#### Step 1.2: Fetch Options Snapshot (`fetch-options-snapshot`)
*   **Command**: `python -m mie_lib.cli.mie fetch-options-snapshot`
*   **Description**: Downloads the full options chain universe for the current day from Polygon.io.
*   **Source Code**: `mie_lib.cli.mie.handle_fetch_options_snapshot` -> `mie_lib.data_ingest.providers.polygon.fetch_options_snapshot`
*   **Dependencies**: Internet (Polygon.io API), `POLYGON_API_KEY`
*   **Output**:
    *   `data/raw/massive/options/options_YYYY-MM-DD.csv` (Massive CSV ~1-2GB)

---

### 2. Feature Engineering Phase

#### Step 2.1: Build Features (`build-features`)
*   **Command**: `python -m mie_lib.cli.mie build-features --mode update --lookback 90`
*   **Description**: Calculates technical indicators (RSI, ADX, Moving Averages, Volatility) and returns. "Update" mode only re-calculates the last 90 days for efficiency.
*   **Source Code**: `mie_lib.features.build_features.build_features_for_ticker`
*   **Dependencies**: `data/raw/{TICKER}.parquet` (from Step 1.1)
*   **Output**:
    *   `data/features/{TICKER}.parquet` (Enriched time series)

---

### 3. Scanners & Analytics Phase

#### Step 3.1: Minervini Trend Scanner (`build-minervini-daily`)
*   **Command**: `python -m mie_lib.cli.mie build-minervini-daily --tickers @config`
*   **Description**: Scans all tickers against Mark Minervini's Trend Template criteria (Stage 2 uptrend rules).
*   **Source Code**: `mie_lib.analytics.scanner.minervini_build.build_minervini_snapshot`
*   **Dependencies**: `data/features/{TICKER}.parquet`
*   **Output**:
    *   `data/analytics/minervini/latest.json`

#### Step 3.2: Markov Models (`build-markov-grid` & `build-markov-snapshots`)
*   **Command 1**: `python -m mie_lib.cli.mie build-markov-grid ...`
    *   *Updates transition matrices for Binary/Tri-state modes across various windows (1Y, 5Y, MAX).*
*   **Command 2**: `python -m mie_lib.cli.mie build-markov-snapshots`
    *   *Copies relevant analytics to the snapshot directory for the UI.*
*   **Source Code**: `mie_lib.analytics.markov.markov_engine`
*   **Dependencies**: `data/features/{TICKER}.parquet`
*   **Output**:
    *   `data/analytics/markov/...`
    *   `data/analytics_snapshots/markov/...`

#### Step 3.3: HMM Regime Detection (`build-hmm-daily` ...)
*   **Command 1**: `python -m mie_lib.cli.mie build-hmm-daily --tickers @config`
    *   *Builds the primary Hidden Markov Model (typically 2-state).*
*   **Command 2**: `python -m mie_lib.cli.mie build-hmm-grid ...`
    *   *Builds standardized grid models (2 & 3 states, various windows) for comparison.*
*   **Command 3**: `python -m mie_lib.cli.mie build-hmm-snapshots`
    *   *Deploys snapshots for UI.*
*   **Command 4**: `python -m mie_lib.cli.mie backtest-hmm --tickers @config`
    *   *Runs a backtest on the HMM strategy.*
*   **Source Code**: `mie_lib.analytics.hmm.hmm_engine`
*   **Dependencies**: `data/features/{TICKER}.parquet`
*   **Output**:
    *   `data/analytics/hmm/...`

#### Step 3.4: Gamma Exposure (GEX) (`build-gex-daily`)
*   **Command**: `python -m mie_lib.cli.mie build-gex-daily --date {TODAY} --tickers @config`
*   **Description**: Calculates GEX profile (Gamma per Strike) using the massive options snapshot.
*   **Source Code**: `mie_lib.analytics.gex.gex_engine.GEXEngine`
*   **Dependencies**:
    *   `data/raw/massive/options/options_YYYY-MM-DD.csv` (from Step 1.2)
    *   Spot Price (yfinance fallback if needed)
    *   **Enrichment**: YFinance (fetches Open Interest/IV if missing in flat file)
*   **Output**:
    *   `data/analytics/gex/{TICKER}/profile_{DATE}.json`

#### Step 3.5: Expected Moves (`update-expected-moves`)
*   **Command 1**: `python -m mie_lib.cli.mie update-expected-moves --tickers @config --lookback 5 ...`
    *   *Calculates expected price ranges based on IV.*
*   **Command 2**: `python -m mie_lib.cli.mie build-expected-moves-snapshots`
    *   *Deploys to snapshots.*
*   **Source Code**: `mie_lib.analytics.expected_moves.engine`
*   **Dependencies**: 
    *   Polygon API (for Options info) / `latest.json` checks
    *   **Enrichment**: YFinance (fills missing Open Interest/IV for current/future expirations)
*   **Output**:
    *   `data/analytics/options/latest.json`

#### Step 3.6: Seasonality (`update-seasonality`)
*   **Command**: `python -m mie_lib.cli.mie update-seasonality`
*   **Description**: Updates historical seasonality statistics (Monthly/Weekly performance).
*   **Source Code**: `mie_lib.analytics.seasonality.update`
*   **Dependencies**: `data/features/{TICKER}.parquet`
*   **Output**:
    *   `data/analytics/seasonality/facts/...`

#### Step 3.7: New Analytics Stack (SMA, ADX, PSAR, Ichimoku)
*   **Commands**:
    *   `python -m mie_lib.cli.mie update-sma-stack`
    *   `python -m mie_lib.cli.mie update-adx`
    *   `python -m mie_lib.cli.mie update-psar`
    *   `python -m mie_lib.cli.mie update-ichimoku`
*   **Description**: Updates specialized technical indicators for specific dashboard widgets.
*   **Dependencies**: `data/features/{TICKER}.parquet`
*   **Output**:
    *   Various JSON/Parquet artifacts in `data/analytics/...`

#### Step 3.8: GAF Prediction (`build-gaf-daily`)
*   **Command**: `python -m mie_lib.cli.mie build-gaf-daily`
*   **Description**: Generates Gramian Angular Fields and runs CNN inference for tomorrow's prediction.
*   **Source Code**: `mie_lib.analytics.gaf.pipeline.run_inference_latest`
*   **Dependencies**: `data/raw/{TICKER}.parquet`
*   **Output**:
    *   `data/analytics/gaf/latest.json`

---

## 📂 File Locations Summary

| Artifact Type | Location |
| :--- | :--- |
| **Logs** | `data/logs/pipeline_{DATE}.log` |
| **Raw Prices** | `data/raw/{TICKER}.parquet` |
| **Raw Options** | `data/raw/massive/options/options_{DATE}.csv` |
| **Features** | `data/features/{TICKER}.parquet` |
| **Analytics** | `data/analytics/{MODULE}/...` |
| **Snapshots (UI)** | `data/analytics_snapshots/{MODULE}/...` |
