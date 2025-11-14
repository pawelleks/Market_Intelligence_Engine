# Market Intelligence Engine — Architecture (DEPRECATED)

> ----------------------------------------------  
> **DEPRECATED** — moved to docs/legacy/ on 2025-11-14  
> Not referenced from v2 documentation.  
> Safe to delete after manual review.  
> ----------------------------------------------
>
> ⚠️ **This document has been merged into `ARCHITECT_BIBLE.md`**.
> 
> **Please refer to**:
> - [`../CORE/ARCHITECT_BIBLE.md`](../CORE/ARCHITECT_BIBLE.md) — Authoritative architecture document
> - [`../CORE/ANALYTICS_REFERENCE.md`](../CORE/ANALYTICS_REFERENCE.md) — Analytics API reference
> - [`../CORE/DATA_REFERENCE.md`](../CORE/DATA_REFERENCE.md) — Data schemas and storage patterns
> 
> This file is preserved for historical reference only.
>
> ---

# Market Intelligence Engine — Architecture

This document is the canonical high-level overview of the system. It supersedes prior architecture drafts preserved under docs/legacy/ and ARCHITECT_BIBLE.md files.

Scope here is descriptive only. The codebase (mie_lib, app, scripts) is the source of truth for behavior.

## Overview

The Market Intelligence Engine (MIE) is an offline-first analytics stack:
- Data layers under `data/` (raw → features → analytics → UI consumption).
- Python package `mie_lib` provides reusable library modules (analytics, utilities, page shims).
- Streamlit app under `app/` reads precomputed artifacts and renders pages.
- Batch scripts under `scripts/` create/update artifacts; Streamlit does not do heavy compute.

## Components

- Library: `src/mie_lib`
  - `mie_lib.analytics.markov`: Markov states, counts, matrices, and grid loaders. Public API re-exports `MarkovConfig`, `build_markov_for_ticker`, shims in `aggregation.py`.
  - `mie_lib.analytics.hmm`: HMM config and builders; `loader.py` re-exports stable API.
  - `mie_lib.analytics.seasonality`: Seasonality base builder and preprocess; `loader.py` re-exports stable API.
  - `mie_lib.utils.paths`: Canonical roots and path helpers (DATA_DIR, FEATURES_DIR, MARKOV_DIR, HMM_DIR, SEASONALITY_DIR, and getters).
  - `mie_lib.pages`: import-time shims that forward to Streamlit pages under `app/pages/` and provide small, testable helpers (e.g., `m_chain.py`).

- UI: `app/`
  - `app/Home.py` is the Streamlit entry point.
  - Pages under `app/pages/` include Markov, Seasonality, HMM, and Price viewer. Pages import from `mie_lib.*` only.

- Data: `data/`
  - `data/raw/` — OHLCV sources (Parquet primary, CSV fallback).
  - `data/features/` — feature files per ticker (must include `date`, `ret_1d`).
  - `data/analytics/markov/<TICKER>/` — Markov outputs (see Data Reference).
  - `data/analytics/hmm/<TICKER>/` — HMM outputs.
  - `data/seasonality/base/` — Seasonality base per ticker.

- Scripts: `scripts/`
  - Validation/integrity checks and rebuild/update scripts (no Streamlit here).

## Data Flow (offline → online)

1) Ingest/prepare market data → `data/raw/*`.
2) Build features → `data/features/<TICKER>.parquet`.
3) Analytics (Markov/HMM/Seasonality) write offline artifacts into `data/analytics/*` and `data/seasonality/*`.
4) Streamlit pages read artifacts and render visualizations. No heavy compute in UI.

## Storage Layout (canonical patterns)

- Features: `data/features/{TICKER}.parquet`
- Markov per-ticker flat outputs (builder):
  - `data/analytics/markov/{TICKER}/states.parquet`
  - `data/analytics/markov/{TICKER}/counts_order{K}.parquet`
  - `data/analytics/markov/{TICKER}/matrix_order{K}.parquet`
  - `data/analytics/markov/{TICKER}/predictions.parquet`
  - `data/analytics/markov/{TICKER}/metadata.json`
- Markov grid matrices (UI consumption):
  - `data/analytics/markov/{TICKER}/matrices/{state_mode}/thr{bps}/order{K}/{WINDOW}.parquet`
- HMM standardized:
  - `data/analytics/hmm/{TICKER}/win{N}y/states{S}/hmm_{probs,states,metrics}.parquet`
- Seasonality base:
  - `data/seasonality/base/{TICKER}.parquet`

See DATA_REFERENCE and ANALYTICS_REFERENCE for details.

## Package Structure (current)

- `mie_lib.analytics.*` — analytics engines and loaders.
- `mie_lib.utils.*` — cross-cutting utilities (paths, logging).
- `mie_lib.pages.*` — thin compatibility layer exposing page-related helpers for tests.

## Design Rules

- Offline-first: Streamlit reads Parquet/JSON only; no network calls.
- Deterministic writes: analytics builders write idempotent files with atomic replace where applicable.
- Stable API: shims (re-exports and compatibility modules) keep `mie_lib` imports stable across pages/tests.

## Legacy Notes

Historical architecture drafts are preserved (see docs/legacy). Where they disagree with code, code wins. This document reflects the current repository state and public APIs.

