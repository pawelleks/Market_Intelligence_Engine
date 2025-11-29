# Developer Onboarding Kit – System Architecture

## Executive Summary
- **Inputs:** hourly/daily market features under `data/features/*.parquet`, option-chain snapshots, config YAML under `config/`, and runtime parameters provided via CLI flags or Streamlit widgets.
- **Processing:** offline pipelines in `mie_lib.analytics` + `mie_lib.options` build analytical artifacts (Markov matrices, HMM states, expected-move bands) via CLI entry `cli/mie.py`; Streamlit pages in `app/` hydrate those files, enrich them with UI-only helpers, and produce interactive narratives.
- **Outputs:** parquet/JSON artifacts persisted under `data/analytics/**`, manifests in `data/options/**`, log files in `logs/`, and Streamlit visualizations (heatmaps, probability tables, staleness banners) that traders consume via `app/Home.py`.

## Tech Stack
| Layer | Details |
| --- | --- |
| Language / Runtime | **Python 3.13.0** (verified via `.venv/bin/python -c 'import sys; print(sys.version)'`). |
| Data tooling | `pandas>=1.5`, `numpy>=1.23`, `pyarrow>=9.0`, `yfinance>=0.2.18` for IO + computation. |
| Analytics | `hmmlearn>=0.3.2`, `scikit-learn>=1.2`, `scipy>=1.9` for regime detection & volatility math. |
| UI | `streamlit>=1.35`, `plotly>=5.17`, `matplotlib>=3.7` for interactive dashboards.
| Testing / Ops | `pytest>=7.0`, shell orchestration via `scripts/*.sh`, CLI glue in `cli/mie.py`. |

## High-Level Data Flow
```mermaid
graph TD
    A[Market + Options Sources\nPolygon, CSV drops, yfinance] --> B[Ingestion & Feature Builders\n mie_lib.data_ingest / features]
    B --> C[data/features/*.parquet]
    C --> D[Analytics Engines\nMarkov / HMM / Expected Moves]
    D --> E[data/analytics/** snapshots\nJSON + Parquet]
    D --> F[data/options/** manifests]
    E --> G[Streamlit UI (app/Home.py + pages)]
    F --> G
    G --> H[End Users / Traders]
    E --> I[CLI Consumers / Downstream scripts]
```

## Design Patterns in Play
| Pattern | Location | Rationale |
| --- | --- | --- |
| **Strategy** | `mie_lib.options.em_core.OptionChainProvider` (base) with concrete `PolygonOptionChainProvider` / `MockOptionChainProvider`. | Swap data sources (live Polygon, mocks) without touching calculators. |
| **Builder / Pipeline** | `mie_lib.options.expected_move.ExpectedMovesCalculator` orchestrates horizon resolution, manifest writing, and historical merges. | Encapsulates multi-step artifact generation with deterministic outputs. |
| **Factory Method** | `ExpectedMovesConfig.load()` and `_default_expected_moves_provider()` instantiate configs/providers from YAML at runtime. | Centralizes config parsing + dependency wiring. |
| **Value Objects (Dataclasses)** | `MarkovConfig`, `HMMConfig`, `HorizonResolution`. | Immutable state passed across pure functions instead of globals. |
| **Adapter** | `_build_multi_horizon_table()` in `app/pages/01_Markov_Chain_V2.py`. | Translates library `multi_step()` output into UI-friendly tables/plots without leaking UI concerns back into analytics. |

These patterns aim to keep analytics reusable (CLI, notebooks, UI) while isolating IO and vendor-specific code paths.
