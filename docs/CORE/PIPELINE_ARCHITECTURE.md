# Market Intelligence Engine - CLI Dependency Graph & Workflow

This document outlines the data flow, dependencies, and execution order for the Market Intelligence Engine (MIE) CLI tools. It provides a roadmap for rebuilding the system from "zero data" to a fully populated analytics state.

## 1. System Overview

The pipeline consists of three distinct layers:
1.  **Ingestion Layer**: Fetches raw data from external providers (Yahoo Finance, etc.).
2.  **Feature Layer**: Transforms raw price data into vectorized features (returns, volatility, moving averages).
3.  **Analytics Layer**: Consumes features or raw data to generate higher-order insights (Markov, HMM, Expected Moves, GEX).

## 2. CLI Command Reference

| Command | Layer | Input Dependencies | Output Artifacts | description |
| :--- | :--- | :--- | :--- | :--- |
| `update-raw` | Ingestion | `config/ticker_list.yml`<br>External API (Yahoo) | `data/raw/{ticker}.parquet` | Fetches historical price data (OHLCV). |
| `fetch-options-snapshot` | Ingestion | `config/ticker_list.yml`<br>External API (Yahoo) | `data/raw/massive/options/options_{DATE}.csv` | Fetches daily options chain snapshot for GEX. |
| `build-features` | Feature | `data/raw/{ticker}.parquet`<br>`config/features.yml` (optional) | `data/features/{ticker}.parquet` | Computes technical indicators and returns. |
| `build-markov-snapshots` | Analytics | `data/features/{ticker}.parquet` | `data/analytics_snapshots/markov/...` | Generates Markov Chain states, transition matrices, and predictions. |
| `build-hmm-snapshots` | Analytics | `data/features/{ticker}.parquet` | `data/analytics_snapshots/hmm/...` | Generates HMM regimes (Bull/Bear/Neutral), probabilities, and metrics. |
| `build-expected-moves` | Analytics | External API (Yahoo)<br>`config/expected_moves.yml` | `data/analytics/options/{ticker}_expected_moves.parquet`<br>`data/analytics/options/latest.json` | Calculates Daily, Weekly, and Monthly expected moves based on ATM straddles. |
| `build-gex-daily` | Analytics | `data/raw/massive/options/options_{DATE}.csv` | `data/analytics/gex/{ticker}_gex_profile.json` (via storage) | Calculates Gamma Exposure (GEX) profiles from options snapshots. |

## 3. Dependency Graph

```mermaid
graph TD
    %% Config Inputs
    Config[config/ticker_list.yml]
    ConfigEM[config/expected_moves.yml]
    ConfigFeat[config/features.yml]

    %% External APIs
    API_Price[Yahoo Finance API (Price)]
    API_Options[Yahoo Finance API (Options)]

    %% Ingestion Layer
    UpdateRaw(update-raw)
    FetchOptions(fetch-options-snapshot)

    %% Raw Data
    RawParquet[data/raw/{ticker}.parquet]
    RawOptionsCSV[data/raw/massive/options/options_{DATE}.csv]

    %% Feature Layer
    BuildFeatures(build-features)
    FeaturesParquet[data/features/{ticker}.parquet]

    %% Analytics Layer - Markov
    BuildMarkov(build-markov-snapshots)
    markov_snap[data/analytics_snapshots/markov]

    %% Analytics Layer - HMM
    BuildHMM(build-hmm-snapshots)
    hmm_snap[data/analytics_snapshots/hmm]

    %% Analytics Layer - Expected Moves
    BuildEM(build-expected-moves)
    em_hist[data/analytics/options/{ticker}_expected_moves.parquet]
    em_latest[data/analytics/options/latest.json]

    %% Analytics Layer - GEX
    BuildGEX(build-gex-daily)
    gex_json[data/analytics/gex/{ticker}_gex_profile.json]

    %% Graph Connections
    Config --> UpdateRaw
    API_Price --> UpdateRaw
    UpdateRaw --> RawParquet

    Config --> FetchOptions
    API_Options --> FetchOptions
    FetchOptions --> RawOptionsCSV

    RawParquet --> BuildFeatures
    ConfigFeat --> BuildFeatures
    BuildFeatures --> FeaturesParquet

    FeaturesParquet --> BuildMarkov
    BuildMarkov --> markov_snap

    FeaturesParquet --> BuildHMM
    BuildHMM --> hmm_snap

    ConfigEM --> BuildEM
    API_Price --> BuildEM
    API_Options --> BuildEM
    BuildEM --> em_hist
    BuildEM --> em_latest

    RawOptionsCSV --> BuildGEX
    BuildGEX --> gex_json
    API_Price -.-> BuildGEX  
    %% (Dotted line: GEX can verify spot via API if missing in CSV)
```

## 4. Execution Workflow (Zero to Hero)

To rebuild the entire system from scratch, execute commands in this exact order. Ensure you are in the project root.

### Phase 1: Ingestion
1.  **Update Raw Price Data**:
    ```bash
    python cli/mie.py update-raw --all
    ```
    *   **Check**: Ensure `data/raw/*.parquet` files exist.

2.  **Fetch Options Snapshot (Daily)**:
    ```bash
    python cli/mie.py fetch-options-snapshot
    ```
    *   **Check**: Ensure `data/raw/massive/options/options_YYYY-MM-DD.csv` exists.

### Phase 2: Feature Engineering
3.  **Build Features**:
    ```bash
    python cli/mie.py build-features --mode full
    ```
    *   **Check**: Ensure `data/features/*.parquet` files exist and are populated.

### Phase 3: Analytics Generation
4.  **Build Expected Moves**:
    ```bash
    # Replace YYYY-MM-DD with today's date
    python cli/mie.py build-expected-moves --ticker @config --start YYYY-MM-DD
    ```

5.  **Build Markov Analytics**:
    ```bash
    python cli/mie.py build-markov-snapshots
    ```
    *   *Note*: This runs the `build_markov_for_ticker` logic internally for configured windows.

6.  **Build HMM Analytics**:
    ```bash
    python cli/mie.py build-hmm-snapshots
    ```

7.  **Build Daily GEX**:
    ```bash
    # Replace YYYY-MM-DD with today's date
    python cli/mie.py build-gex-daily --date YYYY-MM-DD
    ```

## 5. Notes & Guardrails

*   **Existence Checks**: Most scripts (like `build-features` and analytic builders) check for input file existence and will fail gracefully or skip if inputs are missing.
*   **Overwrite Behavior**:
    *   `build-features --mode full` completely rebuilds the feature file.
    *   `update-raw` is incremental (appends new days).
    *   `build-expected-moves` merges new data into `latest.json` but appends to historical parquet.
*   **Dates**: `build-expected-moves` and `build-gex-daily` are date-sensitive. Ensure you provide the correct `--start` or `--date` arguments corresponding to the raw data available.
