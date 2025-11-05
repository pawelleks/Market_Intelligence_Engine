# Project CLI & Bash Command Cheatsheet
_Last updated: 2025-11-05 11:17._

A concise, copy‑pasteable reference for common commands you (and AI agents) run in this repo: testing, pipelines, analytics, Streamlit, logging, and handy Bash patterns.

---

## Table of Contents
- [Environment & Setup](#environment--setup)
- [Project Pipeline (MIE CLI)](#project-pipeline-mie-cli)
- [Analytics & Markov Matrices](#analytics--markov-matrices)
- [Testing with Pytest](#testing-with-pytest)
- [Logging Output (stdout + stderr)](#logging-output-stdout--stderr)
- [Streamlit Apps](#streamlit-apps)
- [Convenience Scripts](#convenience-scripts)
- [Handy Bash Patterns](#handy-bash-patterns)
- [Troubleshooting Patterns](#troubleshooting-patterns)

---

## Environment & Setup

```bash
# Create and activate virtualenv
python -m venv .venv && source .venv/bin/activate

# Upgrade pip and install deps
pip install -U pip
pip install -e .            # editable install for this repo (if setup.py/pyproject exists)
pip install -r requirements.txt

# Freeze dependency versions
pip freeze > requirements.txt
```

> Tip: Add a `.env` (for local config) and load it in your app/Streamlit as needed.

---

## Project Pipeline (MIE CLI)

Typical full pipeline run (quiet pytest first, then features & analytics).

```bash
# Full run (overwrite log)
{
pytest -q
ls data/features
python cli/mie.py build-features --mode full
python cli/mie.py update-features --lookback 90
python cli/mie.py ensure-markov-available --ticker SPY --window 2Y
python cli/mie.py update-all-analytics
ls data/analytics/markov/SPY/matrices/*/*/2Y*
} > logs/pipeline_$(date +'%Y%m%d_%H%M').log 2>&1
```

Common sub-commands & flags (examples):

```bash
# Build / update features
python cli/mie.py build-features --mode full
python cli/mie.py update-features --lookback 90

# Ensure Markov data available for a ticker / window
python cli/mie.py ensure-markov-available --ticker SPY --window 2Y

# Recompute/refresh analytics
python cli/mie.py update-all-analytics
```

Parameters you might use frequently:

- `--mode`: e.g. `full`, `incremental`
- `--lookback`: integer days, e.g. `90`
- `--ticker`: e.g. `SPY`, `QQQ`, etc.
- `--window`: e.g. `6M`, `1Y`, `2Y`, `5Y`

> Suggestion: Run with `-h/--help` on each subcommand to discover more options, e.g. `python cli/mie.py build-features -h`.

---

## Analytics & Markov Matrices

List generated matrices for SPY / 2Y window:

```bash
ls data/analytics/markov/SPY/matrices/*/*/2Y*
```

Count how many matrices exist:

```bash
ls data/analytics/markov/SPY/matrices/*/*/2Y* | wc -l
```

Search for a specific date/timestamp in matrix filenames:

```bash
ls data/analytics/markov/SPY/matrices/*/*/2Y* | grep 2024-12
```

---

## Testing with Pytest

Quick runs:

```bash
pytest -q                         # quiet mode
pytest -q --maxfail=1 --tb=short  # stop on first failure
pytest --lf -q                    # last failures only
pytest tests/test_module.py::TestClass::test_case -q -vv  # single test
```

Useful flags:

- `--maxfail=1` – fail fast
- `--lf / --ff` – last failed / failed first
- `--tb=short` – compact tracebacks
- `-rE` – show error summary
- `-vv` – extra verbosity for debugging

Log test output to file:

```bash
pytest -q --maxfail=10 --tb=short -rE 2>&1 | tee logs/pytest_$(date +'%Y%m%d_%H%M').log
```

Optional `pytest.ini` for good defaults:

```ini
[pytest]
addopts = -q --disable-warnings --maxfail=1 --tb=short
testpaths = tests
```

---

## Logging Output (stdout + stderr)

Overwrite vs append:

```bash
your_command > out.txt 2>&1      # overwrite
your_command >> out.txt 2>&1     # append
```

Group multiple commands and log together:

```bash
{
cmd1
cmd2
cmd3
} > out.txt 2>&1
```

See output live **and** save to file:

```bash
your_command 2>&1 | tee out.txt
your_command 2>&1 | tee -a out.txt   # append
```

---

## Streamlit Apps

Run a Streamlit app:

```bash
streamlit run app.py
```

Pass CLI args through to your Python app (after `--`):

```bash
streamlit run app.py -- --ticker SPY --window 2Y --mode full
```

Auto-reload is on by default when files change. If you need a specific server port:

```bash
streamlit run app.py --server.port 8502
```

Open in a specific browser (example macOS):

```bash
BROWSER=open streamlit run app.py
```

---

## Convenience Scripts

### `scripts/run_pipeline.sh`

```bash
#!/bin/bash
set -euo pipefail

pytest -q --maxfail=1 --tb=short 2>&1 | tee "logs/tests_$(date +'%Y%m%d_%H%M').log"

ls data/features || true
python cli/mie.py build-features --mode full
python cli/mie.py update-features --lookback 90
python cli/mie.py ensure-markov-available --ticker SPY --window 2Y
python cli/mie.py update-all-analytics

ls data/analytics/markov/SPY/matrices/*/*/2Y* | tee -a "logs/tests_$(date +'%Y%m%d_%H%M').log"
```

Make it executable and run:

```bash
chmod +x scripts/run_pipeline.sh
./scripts/run_pipeline.sh > logs/pipeline_$(date +'%Y%m%d_%H%M').log 2>&1
```

### `scripts/validate.sh`

```bash
#!/bin/bash
set -euo pipefail

ruff check .                 # or: flake8
black --check .
mypy . || true               # keep non-blocking for now
pytest -q --maxfail=1 --tb=short
```

---

## Handy Bash Patterns

**Run in background & keep alive (even if terminal closes):**
```bash
nohup ./scripts/run_pipeline.sh > logs/nohup_$(date +'%Y%m%d_%H%M').log 2>&1 &
```

**Watch a command repeat every 2s:**
```bash
watch -n2 'ls -lh data/analytics/markov/SPY/matrices/*/*/2Y* | tail -n 10'
```

**Search codebase for a symbol quickly:**
```bash
grep -RIn "ensure-markov-available" -n
```

**Find large files (top 20):**
```bash
du -ah . | sort -hr | head -n 20
```

**Export a timestamp var for reuse during a session:**
```bash
TS=$(date +'%Y%m%d_%H%M'); echo $TS
```

---

## Troubleshooting Patterns

**Check Python path/imports:**
```bash
python - << 'PY'
import sys, pprint; pprint.pprint(sys.path)
PY
```

**Confirm package entry points (editable install works):**
```bash
python -c "import pkgutil; import your_pkg; print('OK', bool(pkgutil.find_loader('your_pkg')))"
```

**Pin a problematic dependency version:**
```bash
pip install package==X.Y.Z
pip freeze | grep package
```

**Clear Streamlit cache (if stale data causes odd UI):**
```bash
streamlit cache clear   # or: streamlit --version (ensures CLI works)
```

---

### Notes
- Prefer saving logs to `logs/` and scripts to `scripts/`.
- Use `-h/--help` on each CLI subcommand to list all options.
- For long runs, prefer `nohup` or `tmux` to avoid accidental interruption.
