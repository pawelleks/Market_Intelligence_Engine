#!/usr/bin/env bash
# Validation Runner: collects environment, syntax, import, tests, CLI, and Streamlit import checks
# into a single timestamped log file under logs/.

set -u

# Go to repo root
cd "$(git rev-parse --show-toplevel)" || exit 1

mkdir -p logs
TS="$(date +%Y-%m-%d_%H-%M-%S)"
LOGFILE="logs/full_validation_${TS}.log"

# Helper to append a header
append_hdr() {
  printf '\n=== %s ===\n' "$1" >> "$LOGFILE"
}

echo "=== FULL VALIDATION START ===" >> "$LOGFILE"

# STEP 2 — ENVIRONMENT & PACKAGE INFO
append_hdr "STEP 2: ENVIRONMENT & PACKAGE INFO"
{
  python --version
  which python
  pip list
} >> "$LOGFILE" 2>&1

# env_check.py
cat > env_check.py <<'PYCODE'
import sys, pkgutil
print("EXEC:", sys.executable)
try:
    import mie_lib
    print("MIE_LIB:", mie_lib.__file__)
    try:
        subs = [m.name for m in pkgutil.walk_packages(mie_lib.__path__)]
    except Exception as e:
        subs = ["PKGUTIL_ERROR:" + repr(e)]
    print("SUBMODULES:", subs)
except Exception as e:
    print("IMPORT_ERROR:", repr(e))
PYCODE
python env_check.py >> "$LOGFILE" 2>&1 || true
rm -f env_check.py

# STEP 3 — SYNTAX CHECK
append_hdr "STEP 3: SYNTAX CHECK"
python -m py_compile $(git ls-files "*.py") >> "$LOGFILE" 2>&1 || echo "PY_COMPILE_FAILED" >> "$LOGFILE"

# STEP 4 — PUBLIC API IMPORT CHECK
append_hdr "STEP 4: PUBLIC API IMPORT CHECK"
cat > import_check.py <<'PYCODE'
errors = []

def check(label, code):
    print("---", label, "---")
    try:
        exec(code, {})
        print("OK")
    except Exception as e:
        print("FAIL:", repr(e))
        errors.append((label, repr(e)))

pairs = [
    ("mie_lib", "import mie_lib"),
    ("markov engine", "from mie_lib.analytics.markov import markov_engine"),
    ("aggregation shim", "from mie_lib.analytics.markov import aggregation"),
    ("paths", "from mie_lib.utils import paths"),
]
for label, code in pairs:
    check(label, code)
print("SUMMARY:", errors)
PYCODE
python import_check.py >> "$LOGFILE" 2>&1 || true
rm -f import_check.py

# STEP 5 — PYTEST
append_hdr "STEP 5: PYTEST"
pytest -q >> "$LOGFILE" 2>&1 || true

# STEP 6 — CLI COMMANDS
append_hdr "STEP 6: CLI COMMANDS"
if [ -f "cli/mie.py" ]; then
  python cli/mie.py --help >> "$LOGFILE" 2>&1 || true
  python cli/mie.py build-features --mode update --lookback 5 --csv >> "$LOGFILE" 2>&1 || true
  python cli/mie.py update-seasonality >> "$LOGFILE" 2>&1 || echo "SEASONALITY_FAILED" >> "$LOGFILE"
  # update-everything detection
  python - <<'PY'
import importlib, inspect
try:
    m = importlib.import_module('cli.mie')
    s = inspect.getsource(m)
    print('HAS_UPDATE_EVERYTHING' if ('update-everything' in s or 'update_everything' in s) else 'NO_UPDATE_EVERYTHING')
except Exception:
    print('NO_UPDATE_EVERYTHING')
PY
  if grep -q HAS_UPDATE_EVERYTHING "$LOGFILE"; then
    python cli/mie.py update-everything >> "$LOGFILE" 2>&1 || true
  fi
else
  echo "cli/mie.py not found; CLI checks skipped" >> "$LOGFILE"
fi

# STEP 7 — STREAMLIT IMPORT CHECK
append_hdr "STEP 7: STREAMLIT IMPORT CHECK"
cat > streamlit_imports.py <<'PYCODE'
import importlib
pages = [
    "app.Home",
    "app.pages.01_Markov_Chain",
    "app.pages.01_Markov_Chain_V2",
    "app.pages.02_Seasonality_Analysis",
    "app.pages.04_Hidden_Markov_Model",
    "app.pages.05_Price_and_Returns_Viewer",
]
for p in pages:
    try:
        importlib.import_module(p)
        print("[OK]", p)
    except Exception as e:
        print("[FAIL]", p, repr(e))
PYCODE
python streamlit_imports.py >> "$LOGFILE" 2>&1 || true
rm -f streamlit_imports.py

# FINAL OUTPUT: print to stdout (not only into the log)
echo "LOG_FILE: $LOGFILE"

