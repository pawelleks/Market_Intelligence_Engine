# Markov Chain (discretized returns) — UI Viewer

This page is a read-only viewer of offline Markov outputs. It never recomputes analytics in the UI.

Artifacts are loaded from:

- `data/analytics/markov/{TICKER}/states.parquet`
- `data/analytics/markov/{TICKER}/matrix_order{K}.parquet`
- `data/analytics/markov/{TICKER}/metadata.json`
- `data/features/{TICKER}.parquet` (for date range display only)

If an artifact is missing for the selected parameters (ticker, order, state mode, threshold), the page shows a gentle warning and suggests a CLI build command.

## Build missing combinations offline

Run from repo root, for example:

```
python cli/mie.py build-markov --ticker SPY --order 2 --state-mode tri --threshold-bps 10
```

Then refresh the UI.

