# Time Series Momentum (TSMOM) Dashboard Backend

## Overview
The TSMOM module calculates trend-following momentum signals for all tracked tickers based on trailing 12-month returns. It generates daily snapshots of the current state and maintains a history of "Signal Events" (trend reversals).

## Methodology

### Lookback Window
- **252 Trading Days**: The calculation looks back exactly 252 trading days (approx. 1 calendar year) using the available OHLC data series.

### Metric Calculation
For each ticker $T$ and trading day $d$:
$$ \text{ret}_{12m}(d) = \frac{\text{close}(d)}{\text{close}(d - 252)} - 1 $$

### Signal Generation
The momentum direction (`tsmom_dir`) is determined by the sign of the 12-month return:
- **+1 (Bullish)**: if $\text{ret}_{12m} > 0$
- **-1 (Bearish)**: if $\text{ret}_{12m} < 0$
- **0 (Neutral)**: if return is exactly 0 or insufficient data.

### Signal Events
A "Signal Event" (BUY or SELL) is triggered when the `tsmom_dir` changes from the previous trading day:
- **BUY**: Direction flips from -1 (or 0) to +1.
- **SELL**: Direction flips from +1 (or 0) to -1.

## Data Artifacts

### 1. Current Snapshot
Contains the latest momentum status for every ticker. This file is **overwritten** on each daily update.

- **Path:** `data/tsmom/tsmom_current.parquet`
- **Schema:**
    | Column | Type | Description |
    |---|---|---|
    | `asof_date` | date | Date of the calculation (latest available close). |
    | `ticker` | string | Ticker symbol. |
    | `close` | float | Adjusted close price used for calculation. |
    | `ret_12m` | float | The calculated 12-month return value. |
    | `tsmom_dir` | int | Current momentum direction (+1, -1, 0). |
    | `signal_today` | string | "BUY", "SELL", or empty string if no change. |
    | `rows_used` | int | Total historical rows used for calculation context. |
    | `signal_changed` | bool | Boolean flag for convenience (True if signal_today is set). |
    | `lookback_days` | int | The lookback window used (default 252). |
    | `data_start` | date | Start date of available history. |
    | `data_end` | date | End date of available history. |

### 2. Signal History
An append-only log of all momentum reversals (flips).

- **Path:** `data/tsmom/tsmom_signals.parquet`
- **Schema:**
    | Column | Type | Description |
    |---|---|---|
    | `event_date` | date | The date the flip occurred. |
    | `ticker` | string | Ticker symbol. |
    | `signal` | string | "BUY" or "SELL". |
    | `close` | float | Price at the time of the signal. |
    | `ret_12m` | float | The return value that triggered the signal. |
    | `run_id` | string | Unique execution ID for traceability. |
    | `created_at` | timestamp | System timestamp of generation. |
    | `tsmom_dir` | int | The new direction (+1 or -1). |
    | `lookback_days` | int | Lookback parameter used. |

- **Deduplication:** A unique key constraint is enforced on `(ticker, event_date, signal, lookback_days)`. Re-running the pipeline for the same day will update (overwrite) the existing entry rather than duplicating it.

## Usage

### CLI Command
To run the daily update manually:
```bash
python src/mie_lib/cli/mie.py build-tsmom-daily --tickers SPY,QQQ
```

### Integration
The `run_tsmom_daily_update` function in `mie_lib.analytics.tsmom.engine` acts as the primary entry point for pipeline orchestration.
