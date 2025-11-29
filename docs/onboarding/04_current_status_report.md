# Developer Onboarding Kit – Current Status Report

## Snapshot (as of latest commit)
- **Runtime:** Python 3.13.0 venv, package installed via `pip install -e .` plus `requirements.txt` for UI extras (Streamlit, Plotly, hmmlearn, scikit-learn, etc.).
- **Primary workflows:** Offline analytics (`mie_lib.analytics`, `mie_lib.options`) generate Parquet/JSON under `data/`; Streamlit (`app/Home.py`) renders those artifacts without recompute.
- **Automation hooks:** `cli/mie.py` exposes Markov, HMM, and expected-move jobs; `scripts/*.sh` wrap common cron/nightly sequences (e.g., `scripts/rebuild_all_analytics.sh`).

## Recent Highlights
- ✅ **Markov refresh:** `load_features_for_markov()` now tolerates missing columns and derives `ret_1d`, eliminating crashes on partially-populated feature sets. Multi-horizon matrices share Laplace smoothing logic across CLI + UI.
- ✅ **Expected move pipeline:** `resolve_horizons()` + dashboard adapter keep option horizon names synced between config and UI, matching the new WEEKLY reference row.
- ✅ **UI resilience:** `mie_lib.ui.markov_snapshots` gained cached lookups + staleness helpers, so Streamlit pages degrade gracefully when analytics snapshots lag.

## Known Watch-outs
- ⚠️ **Data folder contract:** Streamlit pages hardcode relative paths (e.g., `data/analytics/markov/{ticker}/predictions.parquet`). Changing paths requires simultaneous updates to UI helpers + `docs/CORE/DATA_REFERENCE.md`.
- ⚠️ **Feature parquet freshness:** Markov builders assume `data/features/{ticker}.parquet` exists. Missing/empty files bubble up as FileNotFound errors—triage by running ingest scripts (`scripts/run_pipeline.sh --features`).
- ⚠️ **Polygon quotas:** `PolygonOptionChainProvider` tracks `max_api_calls_per_day`. When running expected-move jobs manually, confirm `config/expected_moves.yml` reflects the day’s call budget to avoid null dashboards.
- ⚠️ **UI launch context:** Always run `streamlit run app/Home.py` from repo root. Non-root execution causes relative imports (`from app.ui ...`) to fail.

## Immediate Next Steps
1. **Rebuild analytics** after onboarding: `python -m cli.mie markov build --ticker=AAPL` (repeat per coverage list) and `python -m cli.mie expected-moves --tickers AAPL,MSFT` to repopulate `data/`.
2. **Run regression suite:** `pytest -q` ensures CLI + analytics changes keep passing snapshot tests.
3. **Document updates:** Keep this onboarding kit plus `docs/CORE/*` in sync whenever data contracts or configs change.

Keep an eye on `logs/` and `data/audit/` during nightly pipelines; failures are recorded there before surfacing in the UI.
