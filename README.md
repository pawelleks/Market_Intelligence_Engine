Market Intelligence Engine

- Scaffold only: initial project structure following `docs/CORE/ARCHITECT_BIBLE.md`.

## Environment setup

Use a virtual environment and install the package in editable mode so tests and pages import `mie_lib` correctly.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e .
pip install -r requirements.txt
```

Run tests:

```bash
pytest -q
```

This README is plain text per project guidelines.

## UI quickstart (dark-only scaffold)

Precomputed files are expected under `data/` as produced by the offline pipelines.

Run pages locally:

- `streamlit run app/pages/01_Market_Regime_Dashboard.py`
- `streamlit run app/pages/02_Regime_Research_Lab.py`
- `streamlit run app/pages/03_Alpha_Signals_Lab.py`
- `streamlit run app/pages/04_Data_Control_Panel.py`

## Running Streamlit pages

Run from the repository root so absolute imports (`from app.ui ...`) resolve correctly:

- `streamlit run app/pages/01_Market_Regime_Dashboard.py`
- `streamlit run app/pages/02_Regime_Research_Lab.py`
- `streamlit run app/pages/03_Alpha_Signals_Lab.py`
- `streamlit run app/pages/04_Data_Control_Panel.py`

Notes:
- The `app/` directory is a Python package (with `__init__.py`).
- Pages include a safe file-relative path shim to handle IDE executions where CWD may differ.

## Multipage app (recommended)

Run the multipage UI from the repository root:

- `streamlit run app/Home.py`

Note: launching an individual page directly (e.g., a file under `app/pages/`) will bypass the multipage sidebar.

Notes:
- Theming comes from `config/ui.yml` and is loaded via `app.ui.theme.get_tokens()`.
- Pages render lightweight placeholders and show warnings if files are missing.
- No heavy compute runs in the UI; all data must be precomputed and saved (Parquet primary, CSV as needed).

Important:
- Pages must live under `app/pages/`.
- When using `st.page_link` from `app/Home.py`, use paths relative to the entrypoint folder, e.g., `"pages/01_Market_Regime_Dashboard.py"`.

## Optional dependencies

Some visuals (e.g., heatmaps on V2 Markov page) can use Plotly if installed. To add:

```bash
pip install plotly
```

## Documentation

Canonical documentation lives under `docs/`:
- docs/CORE/ARCHITECT_BIBLE.md — Master architecture document
- docs/CORE/ANALYTICS_REFERENCE.md — Markov, HMM, Seasonality outputs
- docs/CORE/DATA_REFERENCE.md — Data directories and file patterns
- docs/CORE/CLI_REFERENCE.md — Command-line and scripts reference
- docs/DEVELOPMENT/DEV_GUIDE.md — Environment, tests, and running the app
- docs/DEVELOPMENT/CONTRIBUTING.md — Contributing guidelines
- docs/UI_SYSTEM/ — UI specifications (v2)
- docs/CHANGELOG.md — Documentation changes

Legacy drafts/specs are preserved under `docs/legacy/` (marked for deletion after 2026-05-14).
