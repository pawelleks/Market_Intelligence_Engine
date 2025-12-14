# Analytics Reference

This document summarizes the analytics modules and their artifacts. It does not define math; code is the source of truth.

## Markov Chains

- Package: `mie_lib.analytics.markov`
- Public API: `MarkovConfig`, `build_markov_for_ticker`, `load_markov_matrix_grid`, `get_markov_features_alignment`, `load_features_for_markov`
- Helpers/shims: `mie_lib.analytics.markov.aggregation` exposes `aggregate_to_state_matrix`, `select_context_row`, `compute_multi_horizon_probs` for API/tests compatibility.

### Outputs (per ticker)
- `states.parquet` — daily classified states and context (columns include `mc_state_today`, `mc_state_window`)
- `counts_order{K}.parquet` — raw transition counts per context
- `matrix_order{K}.parquet` — Laplace-smoothed transition probabilities per context
- `predictions.parquet` — mapped context → next-state probability rows per date
- `metadata.json` — parameters used (order, threshold, state_mode, etc.)

### Grid Matrices (UI)
Parquet files for specific `(state_mode, threshold_bps, order, window)`:
`data/analytics/markov/{TICKER}/matrices/{state_mode}/thr{bps}/order{K}/{WINDOW}.parquet`

## Hidden Markov Model (HMM)

- Package: `mie_lib.analytics.hmm`
- Public API: `HMMConfig`, `build_hmm_for_ticker`, `build_hmm_standardized_for_ticker`

### Outputs
- `hmm_probs.parquet`, `hmm_states.parquet`, `hmm_metrics.parquet`, `hmm_metadata.json`
- Standard path: `data/analytics/hmm/{TICKER}/win{N}y/states{S}/`

## Seasonality

- Package: `mie_lib.analytics.seasonality`
- Public API: re-exported functions from `base_builder.py` and `preprocess.py` via `loader.py`

### Outputs
- Seasonality base: `data/seasonality/base/{TICKER}.parquet`
- Columns: `ticker, date, year, doy_trading, open, high, low, close, r, lr, month, day`

## Usage Notes

- The API/Frontend must not recompute analytics; endpoints serve these precomputed artifacts.
- Path helpers in `mie_lib.utils.paths` should be used by library code when constructing paths.

## Markov Chain Analysis Endpoints
### GET /api/v1/markov/matrix/{ticker}/{state_mode}
**Description:** Retrieves the Markov transition matrix (counts and probabilities).
**Path Parameters:**
- `ticker`: Asset ticker (e.g., SPY).
- `state_mode`: 'binary' (2 states) or 'tri' (3 states).
**Query Parameters:**
- `order`: Markov order (k). Default is 1.
- `threshold_bps`: Return threshold in basis points.
