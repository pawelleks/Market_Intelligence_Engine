# Developer Onboarding Kit – Core Classes & State

## Markov Analytics (tri/binary regimes)
- **Module:** `src/mie_lib/analytics/markov/markov_engine.py`
- **Key dataclass:** `MarkovConfig(order=1, state_mode='tri', threshold_bps=10, min_samples_per_state=30)` encapsulates tuning knobs for state generation, transition counts, and prediction thresholds.
- **Lifecycle:**
  1. `load_features_for_markov(ticker)` pulls `data/features/{ticker}.parquet`, enforces sorted `date`, derives `ret_1d`, and returns a clean DataFrame or `None` (UI callers treat this as "no data yet").
  2. `_states_from_returns()` classifies each return via `states_model.classify_tri_state/binary`. `_context_series()` builds sliding-window contexts (e.g., `UND`).
  3. `_compute_counts_and_probs()` emits Laplace-smoothed transition matrices with counts (`counts_order{n}.parquet`) and probs (`matrix_order{n}.parquet`).
  4. `_predictions_for_dates()` maps contexts to next-day probability rows with confidence flags; output persists to `predictions.parquet` alongside metadata JSON.
- **State artifacts:** All outputs live under `data/analytics/markov/{ticker}/` and form the contract consumed by Streamlit (`app/pages/01_Markov_Chain_V2.py`, `03_Markov_MultiStep.py`). Tests in `tests/test_markov_*` assert schema stability.
- **Operational notes:** Always call `build_markov_for_ticker()` via CLI (`python -m cli.mie markov build --ticker=AAPL`) so directories are created and metadata stays in sync.

## Expected Moves (options pipelines)
- **Modules:** `src/mie_lib/options/expected_move.py`, `src/mie_lib/options/em_core.py`, `src/mie_lib/options/horizon_resolver.py`.
- **Config dataclasses:**
  - `ExpectedMoveHorizon` (key/label/target_days/use_expiration) defines business horizons like "Next Session" or "Month End".
  - `ExpectedMovesConfig.load()` hydrates from `config/expected_moves.yml`, providing provider name, API limits, and horizon list.
- **Provider abstraction:** `OptionChainProvider` (in `em_core`) defines hooks (`fetch_available_expiries`, `fetch_chain_snapshot`, `fetch_spot_close`, `fetch_vix1d_close`). `PolygonOptionChainProvider` implements those hooks with local parquet fallbacks + Polygon HTTP calls.
- **Pipeline:**
  1. `resolve_horizons()` (in `horizon_resolver`) maps requested labels to concrete expiries + target-day counts per `as_of` date.
  2. `compute_expected_moves_for_horizons()` ingests a provider + resolved horizons, computes straddle-based EM metrics, and emits normalized rows.
  3. `adapt_em_core_to_dashboard_schema()` pads optional columns so the UI can `pd.concat` without schema drift; final frames write to `data/analytics/options/{ticker}/expected_moves.parquet` and the dashboard manifest `data/meta/options_manifest.json`.
- **State artifacts:**
  - Raw pulls under `data/raw/options/{ticker}/{date}_chain.parquet` (ingest).
  - Dashboard-ready tables under `data/analytics/options/`.
  - Weekly reference CSV from `_weeklies` helpers for cross-ticker comparisons.
- **Testing:** `tests/test_expected_moves_snapshots.py` and `tests/test_features_price_fallback.py` rely on deterministic manifests; keep column names stable when refactoring.

## UI Snapshot Utilities
- **Module:** `src/mie_lib/ui/markov_snapshots.py`.
- **Purpose:** Serve precomputed analytics (`data/analytics_snapshots/markov/**`) to Streamlit pages without duplicating IO logic.
- **Key cached helpers:**
  - `load_snapshot_states(ticker, mode, threshold_bps)` scans multiple filename conventions, ensuring backward compatibility as file names evolve.
  - `load_snapshot_matrix(...)` resolves per-window transition matrices and normalizes casing.
  - `compute_snapshot_staleness(last_data_date)` standardizes "days since refresh" metadata for banners.
- **State conventions:** Directory layout is `data/analytics_snapshots/markov/{TICKER}/matrices/{mode}/thr{bps}/order{n}/{window}.parquet` with companion `matrix_metadata.json`. Streamlit color coding comes from `STATE_COLUMN_LABELS` and `_STATE_COLORS`.

## Putting It Together
1. Offline jobs (CLI or `scripts/`) populate `data/features/**`, `data/analytics/**`, and snapshot folders by calling the Markov + Expected Move pipelines.
2. Streamlit pages query those artifacts via the helper modules above. They never run heavy computation; they simply read parquet/JSON and format results.
3. Tests enforce that (a) configs deserialize, (b) CLI wiring calls the right builders, and (c) UI helpers gracefully degrade when files are missing.

Keep these contracts stable—any schema or path change must first update `docs/CORE/DATA_REFERENCE.md`, then adjust callers and tests in lockstep.
