#!/usr/bin/env bash
# Convenience wrapper to rebuild all offline analytics
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${HERE}/.."
cd "$ROOT"

python scripts/rebuild_all_analytics.py

