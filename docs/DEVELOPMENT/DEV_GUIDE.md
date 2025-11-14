# Developer Guide

This guide explains how to set up the environment, run tests, and run the UI. It reflects the current repo state.

**Related Documentation**:
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — PR process, code style, commit conventions
- [`TESTING.md`](TESTING.md) — Comprehensive testing guide
- [`../CORE/ARCHITECT_BIBLE.md`](../CORE/ARCHITECT_BIBLE.md) — System architecture and principles
- [`../CORE/CLI_REFERENCE.md`](../CORE/CLI_REFERENCE.md) — Command-line interface documentation

---

## Environment Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
pip install -r requirements.txt
```

Confirm editable install:
```bash
python -c "import mie_lib, sys; print(mie_lib.__file__, '||', sys.executable)"
```

## Running Tests

**Quick start:**

```bash
pytest -q
```

For detailed testing documentation, see [`TESTING.md`](TESTING.md).

## Running Streamlit UI

From repo root:
```bash
streamlit run app/Home.py
```

Open pages via the sidebar. Pages read offline artifacts only; if files are missing, follow the CLI hints displayed in the UI.

## Coding Rules (summary)

- UI must use named colors/tokens; avoid inline hex.
- Streamlit pages import from `mie_lib.*` (not `src.*`) and use `mie_lib.utils.paths`.
- No heavy computation in Streamlit; compute offline and write Parquet/JSON.
- Use path helpers from `mie_lib.utils.paths` in library code.

## Where to Look

- Canonical docs live under `../`:
  - [`TESTING.md`](TESTING.md) — Comprehensive testing guide
  - [`../CORE/ARCHITECT_BIBLE.md`](../CORE/ARCHITECT_BIBLE.md) — System architecture
  - [`../CORE/DATA_REFERENCE.md`](../CORE/DATA_REFERENCE.md) — Data schemas
  - [`../CORE/ANALYTICS_REFERENCE.md`](../CORE/ANALYTICS_REFERENCE.md) — Analytics API
  - [`../CORE/CLI_REFERENCE.md`](../CORE/CLI_REFERENCE.md) — CLI reference
  - `DEV_GUIDE.md` (this file)

Legacy/historical documents are preserved under `../legacy/` and marked for deletion.

