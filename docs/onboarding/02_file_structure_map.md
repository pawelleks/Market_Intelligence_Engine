# Developer Onboarding Kit – File Structure Map

## Repository Tree (annotated)
```
Market_Intelligence_Engine/
├── app/                        # Streamlit multipage UI package
│   ├── Home.py                # Primary Streamlit entrypoint wiring sidebar + page links
│   ├── bootstrap.py           # Shared Streamlit bootstrap helpers (logging, theme)
│   ├── pages/                 # Individual Streamlit pages (Markov V2, HMM labs, etc.)
│   ├── ui/                    # Reusable UI widgets + theming tokens
│   └── utils/                 # Page-level helpers (ticker policies, cache shims)
├── cli/
│   └── mie.py                 # Thin executable shim delegating to library CLI commands
├── config/                    # YAML knobs for analytics + UI (features.yml, ui.yml, etc.)
├── data/                      # Expected location for generated Parquet/JSON artifacts
├── docs/                      # Canonical architecture + onboarding documentation
│   ├── onboarding/            # Newly added Developer Onboarding Kit
│   ├── CORE/                  # Architecture bible + analytics references
│   └── DEVELOPMENT/           # Dev guide, contribution rules
├── scripts/                   # Bash helpers for cron/nightly pipelines
├── src/
│   ├── mie_lib/               # Installable python package with business logic
│   │   ├── analytics/         # Markov, HMM, seasonality computation engines
│   │   ├── options/           # Expected move calculators + providers
│   │   ├── ui/                # Shared UI utilities (markov snapshots, formatters)
│   │   ├── utils/             # Paths, logging, trading calendar, etc.
│   │   └── cli/               # Argument parsers + task wiring for pipelines
│   ├── analytics/             # Legacy/experimental analytics modules (non package)
│   ├── data_ingest/, data_clean/, features/ # Historical scaffolding for ETL steps
│   └── signals/               # Placeholder for alpha signal research code
├── tests/                     # Pytest suites for CLI + analytics regressions
├── logs/                      # Runtime + cron logs (gitignored in prod)
├── Makefile                   # Convenience targets (lint, tests, pipelines)
├── requirements.txt           # Runtime + UI dependency pins
├── pyproject.toml             # Packaging metadata (name/version, setuptools)
└── README.md                  # Setup instructions + page launch commands
```

## Entry Points & Config Anchors
- **Application Entry:** `app/Home.py` (use `streamlit run app/Home.py`). Individual pages in `app/pages/` assume this root so keep relative paths intact.
- **CLI Entry:** `cli/mie.py` delegates to `mie_lib.cli.mie`. Run via `python -m cli.mie <command>` or `./cli/mie.py`.
- **Configuration Hub:** YAML under `config/` – e.g., `config/expected_moves.yml` for option horizons, `config/ui.yml` for theme tokens, `config/features.yml` for ETL inputs.
- **Data Contracts:** Generated artifacts land beneath `data/analytics/**` (Markov/HMM), `data/options/**` (expected moves), and `data/features/**` (ingested prices). Streamlit pages read directly from those locations, so keep directory names stable.
