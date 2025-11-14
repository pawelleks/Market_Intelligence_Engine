#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== cron smoke $(date -Is) ==="
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python"
fi

echo "PY=${PY}"
echo "PWD=$(pwd)"
echo "PATH=${PATH}"
${PY} -V
${PY} -m pip --version || true
echo "=== ok ==="

