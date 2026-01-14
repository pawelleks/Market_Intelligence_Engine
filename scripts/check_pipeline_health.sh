#!/bin/bash
# scripts/check_pipeline_health.sh
# Verifies environment health before running the heavy pipeline.

set -e

# Configuration
MIN_DISK_GB=5
RAW_DATA_DIR="data/raw/massive/options"
MAX_DATA_AGE_HOURS=48

# Load env variables if .env exists
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

LOG_MSG() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

ERROR_MSG() {
    echo "❌ ERROR: $1" >&2
}

WARN_MSG() {
    echo "⚠️ WARNING: $1" >&2
}

PASS_MSG() {
    echo "✅ PASS: $1"
}

EXIT_CODE=0

# 1. Disk Space Check
DISK_FREE_GB=$(df -bg . | awk 'NR==2 {print $4}' | sed 's/G//')
if [ "$DISK_FREE_GB" -lt "$MIN_DISK_GB" ]; then
    ERROR_MSG "Low Disk Space: ${DISK_FREE_GB}GB free (Min: ${MIN_DISK_GB}GB)"
    EXIT_CODE=2
else
    PASS_MSG "Disk Space (${DISK_FREE_GB}GB > ${MIN_DISK_GB}GB)"
fi

# 2. Environment Variables (Mock check, relying on presence in .env or shell not explicit contents due to security)
# We check if specific variables are set (non-empty)
if [ -z "$MASSIVE_API_KEY" ]; then
    WARN_MSG "MASSIVE_API_KEY is missing or empty"
    # Don't fail hard on this yet as config might handle it differently, but warn
    EXIT_CODE=1
else
    PASS_MSG "MASSIVE_API_KEY is set"
fi

if [ -z "$OPENAI_API_KEY" ]; then
    WARN_MSG "OPENAI_API_KEY is missing"
    EXIT_CODE=1
else
    PASS_MSG "OPENAI_API_KEY is set"
fi

# 3. Network Connectivity
if ping -c 1 -W 2 google.com &> /dev/null; then
    PASS_MSG "Internet Connectivity (google.com)"
else
    ERROR_MSG "No Internet Connectivity"
    EXIT_CODE=2
fi

if curl -s --head --request GET https://api.polygon.io | grep "200\|403\|401" > /dev/null; then 
    PASS_MSG "Polygon API Reachable"
else
    # Could be rate limit or down
    WARN_MSG "Polygon API Verification failed (could be rate limit)"
fi

# 4. Data Freshness
# Check if we have recent options data
if [ -d "$RAW_DATA_DIR" ]; then
    # Find latest file
    LATEST_FILE=$(ls -t "$RAW_DATA_DIR"/*.csv 2>/dev/null | head -n 1)
    if [ -n "$LATEST_FILE" ]; then
        FILE_AGE_SECS=$(($(date +%s) - $(date -r "$LATEST_FILE" +%s)))
        FILE_AGE_HOURS=$((FILE_AGE_SECS / 3600))
        
        if [ "$FILE_AGE_HOURS" -gt "$MAX_DATA_AGE_HOURS" ]; then
            WARN_MSG "Latest Options Data is stale: ${FILE_AGE_HOURS} hours old (Limit: ${MAX_DATA_AGE_HOURS})"
            # Warn only, might be weekend
            EXIT_CODE=1
        else
            PASS_MSG "Data Freshness (${FILE_AGE_HOURS}h < ${MAX_DATA_AGE_HOURS}h)"
        fi
    else
        WARN_MSG "No CSV files found in $RAW_DATA_DIR"
        EXIT_CODE=1
    fi
else
    WARN_MSG "Raw Data Directory not found: $RAW_DATA_DIR"
    EXIT_CODE=1
fi

LOG_MSG "Health Check Completed with Exit Code: $EXIT_CODE"
exit $EXIT_CODE
