# Market Intelligence Engine - Data Update & Maintenance Guide

This document provides a reference for maintaining the data pipeline of the Market Intelligence Engine (MIE). It covers daily automation, individual module updates, and troubleshooting.

## 1. Quick Start: Daily Update

The recommended way to update all data for the current day is using the Orchestrator script.

### Running via Docker (Recommended)
From your host machine (project root):

```bash
docker-compose exec api bash cli/orchestrator.sh
```

### What `orchestrator.sh` does:
1.  **Ingests** latest price history (`update-raw`) and options snapshots (`fetch-options-snapshot`).
2.  **Builds** technical features (`build-features`).
3.  **Generates** analytics:
    *   Expected Moves (`build-expected-moves`)
    *   Markov Chain Snapshots (`build-markov-snapshots`)
    *   HMM Regimes (`build-hmm-snapshots`)
    *   Gamma Exposure (`build-gex-daily`)

---

## 2. Individual Module Commands

If you need to update specifics or rebuild a single module, use the `mie` CLI directly.

### A. Ingestion Layer

**Update Price History (Incremental)**
Fetches only missing days for all tickers in `config/ticker_list.yml`.
```bash
docker-compose exec api python cli/mie.py update-raw
```

**Fetch Options Snapshot (Daily GEX)**
Fetches the full options chain for today. Must be run before market close or shortly after.
```bash
docker-compose exec api python cli/mie.py fetch-options-snapshot
```

### B. Feature Layer

**Build Features (Incremental)**
Updates technicals for new data points only. Faster.
```bash
docker-compose exec api python cli/mie.py build-features --mode update
```

**Rebuild Features (Full)**
Wipes and recalculates all features from scratch. Use this if you change feature definitions or adding new tickers.
```bash
docker-compose exec api python cli/mie.py build-features --mode full
```

### C. Analytics Layer

**Expected Moves**
Updates the `latest.json` used by the dashboard.
```bash
# Replace YYYY-MM-DD with today's date
docker-compose exec api python cli/mie.py build-expected-moves --ticker @config --start YYYY-MM-DD
```

**Gamma Exposure (GEX)**
Generates GEX profiles from the daily snapshot CSV.
```bash
docker-compose exec api python cli/mie.py build-gex-daily --date YYYY-MM-DD
```

**Markov & HMM**
Generates the static files for the "Market State" and "HMM Backtest" pages.
```bash
docker-compose exec api python cli/mie.py build-markov-snapshots
docker-compose exec api python cli/mie.py build-hmm-snapshots
```

---

## 3. Common Tasks & Troubleshooting

### Adding a New Ticker
1.  Add the symbol to `config/ticker_list.yml`. **Ensure it uses Yahoo Finance format (e.g., `^SPX` not `.SPX`).**
2.  Run the full update cycle (or orchestrator) to populate its history and features.
    ```bash
    docker-compose exec api bash cli/orchestrator.sh
    ```

### Fixing "No Data" on Frontend
1.  **Check Logs**: `data/logs/pipeline_YYYY-MM-DD.log`
2.  **Verify Raw Data**: Ensure `data/raw/{ticker}.parquet` exists.
3.  **Verify Feature Data**: Ensure `data/features/{ticker}.parquet` exists and has recent dates.
4.  **Re-run Analytics**: If features exist but frontend is empty, re-run the specific analytics builder (e.g., `build-gex-daily`).

### Data Delays
If data is slightly delayed, the `fetch-options-snapshot` might run too early.
*   **Retry**: Simply run the command again. It overwrites the daily snapshot.

### Monitoring Progress
To watch the pipeline progress in real-time, you can tail the log file from your host machine:

```bash
# Replace date with today's date
tail -f data/logs/pipeline_$(date +%Y-%m-%d).log
```

Or check the specific container logs if running individual commands:
```bash
docker-compose logs -f api
```

### 404 Errors in Logs
*   Usually means the ticker symbol in `config/ticker_list.yml` is incorrect for Yahoo Finance.
*   **Fix**: Search for the correct symbol (e.g., `^DJI`) and update configuration.
