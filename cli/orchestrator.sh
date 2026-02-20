#!/bin/bash
# orchestrator.sh
# Automates the Daily Market Intelligence Engine Workflow
#
# Usage:
#   Run inside the API container:
#     ./orchestrator.sh [RUN_TYPE] [EXTRA_ARGS...]
#   Or from host via docker-compose:
#     docker-compose exec api bash orchestrator.sh
#
# Examples:
#   ./orchestrator.sh MANUAL --dry-run
#   ./orchestrator.sh CRON

set -e  # Exit immediately if a command exits with a non-zero status.

# Python Detection (Robust)
if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
elif [ -x "/app/.venv/bin/python" ]; then
    PY="/app/.venv/bin/python"
elif command -v python3 &> /dev/null; then
    PY="python3"
else
    PY="python"
fi

echo "🚀 Starting Daily MIE Pipeline Wrapper..."
echo "---------------------------------------------------"
echo "Delegating execution to run_pipeline.py"
echo "---------------------------------------------------"

# Default run-type to MANUAL if not specified
# Logic: If $1 matches MANUAL|CRON|RETRY, use it as run-type.
# Else, if $1 starts with --, assume args only and default to MANUAL.

RUN_TYPE="MANUAL"
EXTRA_ARGS=()

if [[ "$1" =~ ^(MANUAL|CRON|RETRY)$ ]]; then
    RUN_TYPE="$1"
    shift # Remove first arg
fi

# Collect remaining arguments
EXTRA_ARGS=("$@")

echo "Run Type: ${RUN_TYPE}"
echo "Extra Args: ${EXTRA_ARGS[*]}"

# Pass arguments to run_pipeline.py
${PY} run_pipeline.py --run-type "${RUN_TYPE}" "${EXTRA_ARGS[@]}"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Wrapper finished successfully."
else
    echo "❌ Wrapper finished with errors (Exit Code: $EXIT_CODE)."
fi

exit $EXIT_CODE
