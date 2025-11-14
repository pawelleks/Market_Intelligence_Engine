````markdown
# UI Reference (LEGACY)

> ⚠️ **DEPRECATED**: This document has been superseded by the UI_SYSTEM folder.
> 
> **Please refer to**:
> - [`UI_SYSTEM_INDEX.md`](UI_SYSTEM_INDEX.md) — Entry point for all UI documentation
> - [`UI_README_v2.md`](UI_README_v2.md) — Current UI system overview
> - [`PAGE_SPEC_MARKOV_v2.md`](PAGE_SPEC_MARKOV_v2.md) — Page specifications
> 
> This file is preserved for historical reference (2025-11-14).
>
> ---

# UI Reference

This document describes the Streamlit UI layer as it exists today. It consolidates prior UI documents under docs/UI_SYSTEM and legacy/ui.

## Pages

Main pages live under `app/pages/`:
- `01_Markov_Chain.py` — Markov chains (states, matrices, multi-horizon view)
- `01_Markov_Chain_V2.py` — Experimental/alternative Markov page using matrix grid helpers
- `02_Seasonality_Analysis.py` — Seasonality base visualization and calendar summaries
- `04_Hidden_Markov_Model.py` — HMM regimes and transition matrix view
- `05_Price_and_Returns_Viewer.py` — Simple price/returns inspection

Launch the multi-page app from repository root:

```bash
streamlit run app/Home.py
```

Pages import library code from `mie_lib.*` only. Avoid `sys.path` shims.

## Layout Conventions

- Offline-first: pages never perform heavy computation; they read Parquet/JSON written by offline pipelines.
- Theme: dark by default; use named colors/tokens via `app.ui.theme.get_tokens()`.
- No inline hex color codes in code; use named colors or theme tokens.
- Show clear diagnostics when files are missing and include CLI hints to rebuild artifacts.

## Data Locations (read-only in UI)

- Features: `data/features/{TICKER}.parquet`
- Markov matrices: `data/analytics/markov/{TICKER}/matrices/{state_mode}/thr{bps}/order{K}/{WINDOW}.parquet`
- HMM outputs: `data/analytics/hmm/{TICKER}/...`
- Seasonality base: `data/seasonality/base/{TICKER}.parquet`

Use `mie_lib.utils.paths` for canonical roots and path helpers.

## Page-Specific Notes

- Markov pages: prefer using `mie_lib.analytics.markov` public API (e.g., `states_for`, matrix grid loader helpers) and aggregation shims from `mie_lib.analytics.markov.aggregation`.
- Seasonality page: reads seasonality base for a ticker and renders average paths and calendar table.
- HMM page: reads standardized HMM artifacts; shows regimes and transition matrix.

## Legacy UI Docs

The following are preserved for context under `docs/legacy/` or `docs/UI_SYSTEM/` and may be partially outdated:
- `docs/UI_SYSTEM/UI_README_v2.md`
- `docs/UI_SYSTEM/PAGE_SPEC_MARKOV_v2.md`
- `docs/UI_SYSTEM/CHART_SPECS_v2.md`
- `docs/UI_SYSTEM/DESIGN_BRIEF_v2.md`
- `docs/legacy/ui/*`

If these conflict with code or this document, code and this file take precedence.


````