# Testing Guide

This guide covers testing practices, test execution, and debugging for the Market Intelligence Engine.

**Related Documentation**:
- [`DEV_GUIDE.md`](DEV_GUIDE.md) — Development setup and workflows
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — Contributing guidelines and code standards
- [`../CORE/ARCHITECT_BIBLE.md`](../CORE/ARCHITECT_BIBLE.md) — System architecture

---

## Test Organization

Tests are located in the `tests/` directory:

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_features.py         # Feature engineering tests
├── test_markov*.py          # Markov chain tests
├── test_hmm*.py             # Hidden Markov Model tests
├── test_ingest*.py          # Data ingestion tests
└── test_*.py                # Other module-specific tests
```

## Running Tests

### Run All Tests

```bash
pytest -q
```

### Run Specific Test File

```bash
pytest tests/test_hmm.py
```

### Run with Project Environment

```bash
PYTHONPATH=/path/to/repo/src .venv/bin/python -m pytest tests/
```

### Useful Options

- `--maxfail=1` — Stop after first failure
- `--tb=short` — Show shorter tracebacks
- `-v` — Verbose output
- `-x` — Stop on first error
- `--lf` — Rerun last failed tests
- `-k "pattern"` — Run tests matching pattern

### Examples

```bash
# Fast fail mode
pytest --maxfail=1 --tb=short

# Run only HMM tests
pytest tests/test_hmm.py -v

# Run tests with specific name pattern
pytest -k "markov" -v
```

## Test Structure

Tests interact with `mie_lib` public API and use canonical paths from `mie_lib.utils.paths`.

### Typical Test Pattern

```python
from mie_lib.analytics.markov import build_markov_for_ticker, MarkovConfig
from mie_lib.utils.paths import features_parquet_path

def test_markov_build():
    ticker = "SPY"
    cfg = MarkovConfig(order=1, threshold_bps=10, state_mode="tri")
    
    # Build artifacts
    result = build_markov_for_ticker(ticker, cfg)
    
    # Verify outputs
    assert result["states"] is not None
    assert features_parquet_path(ticker).exists()
```

## Debugging Tests

### Print Debug Info

```python
import sys
print(f"Python: {sys.executable}")
print(f"PYTHONPATH: {sys.path}")
```

### Interactive Debugging

```bash
pytest tests/test_hmm.py --pdb
```

Drops into debugger on failure.

### Logging

Tests emit logs to `data/logs/` when configured. Check these for detailed execution traces.

## Continuous Integration

When running in CI:
- All tests must pass
- No warnings allowed
- Coverage thresholds enforced (if configured)

## Common Issues

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'mie_lib'`

**Solution**:
```bash
# Ensure editable install
pip install -e .

# Or set PYTHONPATH
export PYTHONPATH=/path/to/repo/src
```

### Missing Dependencies

**Problem**: `ModuleNotFoundError: No module named 'hmmlearn'`

**Solution**:
```bash
pip install -r requirements.txt
# Or install specific package
pip install hmmlearn
```

### Path Issues

**Problem**: Tests can't find data files

**Solution**: Use path helpers from `mie_lib.utils.paths`:
```python
from mie_lib.utils.paths import DATA_DIR, features_parquet_path
```

## Adding New Tests

1. Create test file in `tests/` following naming convention `test_*.py`
2. Import from `mie_lib.*` (not `src.*`)
3. Use fixtures from `conftest.py` where appropriate
4. Test public API, not internal implementation
5. Keep tests isolated (no shared state)
6. Clean up temporary files if created

## Test Coverage

Run coverage report:
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## Performance Testing

For performance-critical code, use:
```python
import time

def test_markov_performance():
    start = time.time()
    # ... test code ...
    duration = time.time() - start
    assert duration < 2.0, f"Too slow: {duration}s"
```

---

**See also**: [`DEV_GUIDE.md`](DEV_GUIDE.md) for general development setup
