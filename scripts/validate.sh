#!/bin/bash
# Lint/format/type + quick tests
set -euo pipefail

ruff check . || true
black --check . || true
mypy . || true
pytest -q --maxfail=1 --tb=short
