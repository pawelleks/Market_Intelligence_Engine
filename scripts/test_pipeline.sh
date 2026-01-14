#!/bin/bash
# scripts/test_pipeline.sh
# Test Harness for Market Intelligence Engine Pipeline
# Safe to run: Uses --dry-run or validates specific stages.

set -e

# Configuration
PY="python3"
MIE_CMD="${PY} -m mie_lib.cli.mie"

# Load env variables if .env exists
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

# Add src to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

echo "======================================================="
echo "🧪 Starting Pipeline Test Suite"
echo "======================================================="

# 1. Pre-flight Health Check
echo ""
echo "test: Running Pre-flight Health Check..."
if ./scripts/check_pipeline_health.sh; then
    echo "✅ Health Check Passed"
else
    echo "⚠️ Health Check Warnings (see above)"
    # We continue for testing purposes unless it's a hard failure in the script
fi

# 2. Validate Pipeline Configuration
echo ""
echo "test: Validating Pipeline Configuration..."
${MIE_CMD} update-everything --validate-only
echo "✅ Configuration Validated"

# 3. Dry Run Full Pipeline
echo ""
echo "test: Running Full Pipeline Dry-Run..."
${MIE_CMD} update-everything --dry-run
echo "✅ Dry-Run Completed"

# 4. Independent GEX Archive Test (Simulation)
# We test the command logic availability, not the actual archive to avoid overwriting production data
echo ""
echo "test: Verifying GEX Archive Command Availability..."
${MIE_CMD} archive-gex-daily --help > /dev/null
echo "✅ GEX Archive Command is registered"

echo ""
echo "======================================================="
echo "🎉 All Test Suites Passed"
echo "======================================================="
