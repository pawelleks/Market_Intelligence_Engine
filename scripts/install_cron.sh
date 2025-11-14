#!/usr/bin/env bash
# Install a nightly cron job to run the incremental update at 00:00 local time.
# This writes/updates a crontab entry pointing to this repo and logs to logs/cron_YYYY-MM-DD.log
set -euo pipefail

# cd to repo root
cd "$(dirname "$0")/.."

# Absolute paths
REPO_ROOT="$(pwd)"
WRAPPER="${REPO_ROOT}/scripts/nightly_update.sh"
LOGDIR="${REPO_ROOT}/logs"
mkdir -p "${LOGDIR}"
CRON_MARKER="# MIE_NIGHTLY_UPDATE"

# Build new cron entry: run daily at 00:00 local time
# Wrapper manages lock/logs; we just call it.
NEW_LINE="0 0 * * * cd ${REPO_ROOT} && ${WRAPPER} >> ${LOGDIR}/cron_\$(date +\\%F).log 2>&1 ${CRON_MARKER}"

# Install or update crontab idempotently
TMP="$(mktemp)"
crontab -l 2>/dev/null | grep -v "${CRON_MARKER}" > "${TMP}" || true
echo "${NEW_LINE}" >> "${TMP}"
crontab "${TMP}"
rm -f "${TMP}"

echo "Cron installed. Current crontab:"
crontab -l
