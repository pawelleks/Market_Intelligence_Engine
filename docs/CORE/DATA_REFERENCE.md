# Data Reference

Canonical description of data directories and file patterns used by MIE.

## Root Directories

- `data/raw/` — Input OHLCV per ticker, Parquet primary (CSV backup possible)
- `data/features/` — Engineered features per ticker (must include `date`, `ret_1d`)
- `data/analytics/` — Outputs from analytics engines (Markov, HMM, etc.)
- `data/seasonality/` — Seasonality base/facts
- `data/logs/` — Logs (optional scripts)

## Features

- File: `data/features/{TICKER}.parquet`
- Required columns: `date` (datetime), `ret_1d` (float) at minimum
- Ordering: ascending by `date`, unique per ticker

## Markov Outputs (per ticker)

- Base outputs (produced by Markov builder):
  - `data/analytics/markov/{TICKER}/states.parquet`
  - `data/analytics/markov/{TICKER}/counts_order{K}.parquet`
  - `data/analytics/markov/{TICKER}/matrix_order{K}.parquet`
  - `data/analytics/markov/{TICKER}/predictions.parquet`
  - `data/analytics/markov/{TICKER}/metadata.json`

- Grid matrices (UI consumption):
  - `data/analytics/markov/{TICKER}/matrices/{state_mode}/thr{bps}/order{K}/{WINDOW}.parquet`

## HMM Outputs

- Standardized per ticker and configuration (window years and number of states):
  - Directory: `data/analytics/hmm/{TICKER}/win{N}y/states{S}/`
  - Files: `hmm_probs.parquet`, `hmm_states.parquet`, `hmm_metrics.parquet`, `hmm_metadata.json`

## Seasonality Base

- File: `data/seasonality/base/{TICKER}.parquet`
- Columns: `ticker, date, year, doy_trading, open, high, low, close, r, lr, month, day`

## Path Helpers

Use `mie_lib.utils.paths` for canonical path building:
- `FEATURES_DIR`, `MARKOV_DIR`, `HMM_DIR`, `SEASONALITY_DIR`
- `features_parquet_path(ticker)`
- `markov_out_dir(ticker)`, `markov_*_path(...)`
- `hmm_out_dir(ticker)`, `hmm_std_out_dir(ticker, window_years, n_states)`
- `seasonality_base_path(ticker)`

This document reflects current code and tests; if discrepancies arise, code wins.

