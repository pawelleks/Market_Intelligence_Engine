#!/bin/bash
set -e

# ==============================================================================
# Market Intelligence Engine - Remote Deployment Script
# ==============================================================================
# Usage:
#   REMOTE_USER=ubuntu REMOTE_HOST=1.2.3.4 [IDENTITY_FILE=~/.ssh/key.pem] ./scripts/deploy_remote.sh
#
# Description:
#   Synchronizes the current project directory to a remote server and redeploys
#   the application using Docker Compose.
# ==============================================================================

# --- Configuration ---
REMOTE_USER="${REMOTE_USER:-}"
REMOTE_HOST="${REMOTE_HOST:-}"
IDENTITY_FILE="${IDENTITY_FILE:-}"
REMOTE_DIR="${REMOTE_DIR:-~/market_intelligence_engine}"


# --- Validation ---
if [[ -z "$REMOTE_USER" || -z "$REMOTE_HOST" ]]; then
    echo "Error: REMOTE_USER and REMOTE_HOST environment variables must be set."
    echo "Usage: REMOTE_USER=user REMOTE_HOST=host ./scripts/deploy_remote.sh"
    exit 1
fi

# Check Identity File if provided
if [[ -n "$IDENTITY_FILE" ]]; then
    if [[ ! -f "$IDENTITY_FILE" ]]; then
        echo "Error: Identity file '$IDENTITY_FILE' not found."
        exit 1
    fi
    SSH_OPTS="-o StrictHostKeyChecking=no -i $IDENTITY_FILE"
else
    SSH_OPTS="-o StrictHostKeyChecking=no"
fi

echo "========================================================"
echo "Deploying to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}"
echo "========================================================"

# --- Pre-flight Check ---
echo "[0/3] Checking connectivity..."
if ! ssh $SSH_OPTS -o ConnectTimeout=5 "${REMOTE_USER}@${REMOTE_HOST}" "echo Connection successful"; then
    echo "Error: Unable to connect to ${REMOTE_USER}@${REMOTE_HOST}."
    echo "Please check your IP address, username, and SSH key."
    exit 1
fi


# --- Step 1: Create Remote Directory ---
echo "[1/3] Preparing remote directory..."
ssh $SSH_OPTS "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p ${REMOTE_DIR}"

# --- Step 1.5: Backup Database (Safety Net) ---
echo "[1.5/3] Backing up remote database..."
ssh $SSH_OPTS "${REMOTE_USER}@${REMOTE_HOST}" "if [ -f ${REMOTE_DIR}/data/users.db ]; then cp ${REMOTE_DIR}/data/users.db ${REMOTE_DIR}/data/users.db.bak_\$(date +%s); echo 'Database backed up.'; else echo 'No database to backup yet.'; fi"

# --- Step 2: Sync Files (Rsync) ---
echo "[2/3] Syncing files..."
# Excludes:
# - .git: Repo history not needed for running
# - .venv: Local virtual environment (OS specific)
# - node_modules: Local frontend deps (OS specific)
# - __pycache__: Python bytecode
# - logs: Local logs
# - data: OPTIONAL. We typically want to keep remote data. 
#   For now, we sync 'config', 'cli', 'src', 'scripts', project files.
#   We DO sync 'data/seeds' or defaults if they exist, but generally strict sync
#   might overwrite production data if not careful.
#   SAFER STRATEGY: Exclude 'data' folder from sync, only sync code.
#   IF this is a first deploy and you need data/raw, you might want to remove that exclude manually.

rsync -avz --delete \
    -e "ssh $SSH_OPTS" \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude '.env' \
    --exclude 'node_modules' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.DS_Store' \
    --exclude 'logs' \
    --exclude 'data' \
    ./ "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

# Sync .env separately if it exists (be careful not to overwrite prod env with local dev env automatically without asking)
# echoing "Skipping .env sync to protect production secrets. Manually copy if needed."

# --- Step 3: Remote Build & Restart ---
echo "[3/3] Rebuilding & Restarting Remote Containers..."
ssh $SSH_OPTS "${REMOTE_USER}@${REMOTE_HOST}" << EOF
    set -e
    cd ${REMOTE_DIR}
    
    # Ensure a basic .env exists if none
    if [ ! -f .env ]; then
        echo "Creating default .env..."
        touch .env
    fi

    # Ensure POLYGON_API_KEY exists
    if ! grep -q "POLYGON_API_KEY" .env; then
        echo "Injecting POLYGON_API_KEY..."
        echo "POLYGON_API_KEY=keXDhBdz5zuofjHkeiYMznzUiyDerXgu" >> .env
    fi

    # Ensure GOOGLE_CLIENT_ID exists (for OAuth)
    # We try to grep it from the local environment passed via SSH or just manual injection here?
    # Ideally script captures it from local execution context.
    # But shell variable expansion happens on CLIENT side inside the HERE-DOC unless escaped.
    # Wait, we want the VALUE from the CLIENT environment.
    # So we should pass it.
    
    # Ensure GOOGLE_CLIENT_ID exists (force update)
    if grep -q "GOOGLE_CLIENT_ID" .env; then
        # Remove existing line to prevent duplicates or empty values
        sed -i '/GOOGLE_CLIENT_ID/d' .env
    fi
    echo "Injecting GOOGLE_CLIENT_ID..."
    echo "GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}" >> .env

    # Check for docker-compose or docker compose
    if command -v docker-compose &> /dev/null; then
        echo "Stopping old containers..."
        docker-compose down || true
        echo "Forcing removal of potentially conflicting containers..."
        docker rm -f mie-api mie-web mie-cron || true
        echo "Starting new build..."
        docker-compose up -d --build
    else
        echo "Stopping old containers..."
        docker compose down || true
        echo "Forcing removal of potentially conflicting containers..."
        docker rm -f mie-api mie-web mie-cron || true
        echo "Starting new build..."
        docker compose up -d --build
    fi

    # Prune unused images to save space
    docker image prune -f
EOF

echo "========================================================"
echo "Deployment Complete!"
echo "========================================================"
