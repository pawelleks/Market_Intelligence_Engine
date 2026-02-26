#!/usr/bin/env bash
# =============================================================================
# theta_remote.sh — Run theta-dependent commands on production
# =============================================================================
#
# ThetaData IP Lock: The terminal locks HTTP access to the first connecting IP
# per session. Production mie-api owns the connection via Docker network.
# Local dev CANNOT tunnel directly to theta (different source IP → HTTP 476).
#
# Instead, this script executes commands on production via SSH + docker exec.
#
# Usage:
#   ./scripts/theta_remote.sh build-gex-theta --tickers SPY
#   ./scripts/theta_remote.sh fetch-eod-chains
#   ./scripts/theta_remote.sh update-expected-moves-v2
#   ./scripts/theta_remote.sh <any-mie-cli-command> [args...]
#
# Prerequisites:
#   - SSH access: ssh deploy@digitalocean
#   - Production Docker stack running
# =============================================================================

set -euo pipefail

REMOTE_HOST="deploy@digitalocean"
CONTAINER="mie-api"

if [ $# -eq 0 ]; then
    echo "Usage: $0 <mie-cli-command> [args...]"
    echo ""
    echo "Examples:"
    echo "  $0 build-gex-theta --tickers SPY"
    echo "  $0 fetch-eod-chains"
    echo "  $0 update-expected-moves-v2"
    echo ""
    echo "This runs the command on production via SSH + docker exec."
    echo "Required because ThetaData IP lock prevents local tunnel access."
    exit 1
fi

echo "→ Running on production: python -m mie_lib.cli.mie $*"
echo ""

ssh "$REMOTE_HOST" "docker exec $CONTAINER python -m mie_lib.cli.mie $*"
