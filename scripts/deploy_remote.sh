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
# --- Configuration ---
REMOTE_USER="${REMOTE_USER:-}"
REMOTE_HOST="${REMOTE_HOST:-}"
IDENTITY_FILE="${IDENTITY_FILE:-}"
REMOTE_DIR="${REMOTE_DIR:-~/market_intelligence_engine}"
SSH_PORT="${SSH_PORT:-22}"

# --- Load Local .env ---
if [ -f ".env" ]; then
    echo "Loading local .env file..."
    set -a
    source .env
    set +a
fi


# --- Validation ---
if [[ -z "$REMOTE_USER" || -z "$REMOTE_HOST" ]]; then
    echo "Error: REMOTE_USER and REMOTE_HOST environment variables must be set."
    echo "Usage: REMOTE_USER=user REMOTE_HOST=host [SSH_PORT=22] ./scripts/deploy_remote.sh"
    exit 1
fi

# Check GOOGLE_CLIENT_ID
if [[ -z "$GOOGLE_CLIENT_ID" ]]; then
    echo "WARNING: GOOGLE_CLIENT_ID is not set. Google Sign-In will not work in the deployed app."
fi

# Check Identity File if provided
if [[ -n "$IDENTITY_FILE" ]]; then
    if [[ ! -f "$IDENTITY_FILE" ]]; then
        echo "Error: Identity file '$IDENTITY_FILE' not found."
        exit 1
    fi
    SSH_OPTS="-o StrictHostKeyChecking=no -i $IDENTITY_FILE -p $SSH_PORT"
else
    SSH_OPTS="-o StrictHostKeyChecking=no -p $SSH_PORT"
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
# --- Step 2.5: Prepare Environment Updates (Local Execution) ---
echo "[2.5/3] Verifying and packing environment variables..."
ENV_UPDATES=""
REQUIRED_KEYS=("POLYGON_API_KEY" "MASSIVE_API_KEY" "GOOGLE_CLIENT_ID" "JWT_SECRET_KEY" "OPENAI_API_KEY" "LLM_MODEL_NAME" "FRED_API_KEY")

for KEY in "${REQUIRED_KEYS[@]}"; do
    VAL="${!KEY}"
    
    if [ -z "$VAL" ]; then
        echo "ERROR: $KEY is missing in the LOCAL environment or .env file."
        echo "Please ensure all required keys are set before deploying."
        exit 1
    fi
    
    # Safe quote the value for remote shell execution
    SAFE_VAL=$(printf %q "$VAL")
    
    # Append the update command to the script we will send
    ENV_UPDATES+="
    if grep -q \"^$KEY=\" .env; then sed -i \"/^$KEY=/d\" .env; fi
    echo \"$KEY=$SAFE_VAL\" >> .env
    echo \"Synced $KEY...\"
    "
done

# --- Step 2.7: Database Integrity Guard ---
echo "[2.7/3] Verifying remote database integrity..."
ssh $SSH_OPTS "${REMOTE_USER}@${REMOTE_HOST}" << EOF
    # Check current user count if python3 and sqlite3 available
    DB_FILE="${REMOTE_DIR}/data/users.db"
    if [ -f "\$DB_FILE" ]; then
        COUNT=\$(docker exec mie-api python3 -c "import sqlite3; c=sqlite3.connect('data/users.db'); print(c.execute('SELECT COUNT(*) FROM users').fetchone()[0]); c.close()" 2>/dev/null || echo "unknown")
        echo "Current User Count: \$COUNT"
        if [[ "\$COUNT" != "unknown" && "\$COUNT" -lt 10 ]]; then
            echo "WARNING: User count is suspiciously low (\$COUNT). Please verify data/users.db is correctly mounted."
        fi
    fi
EOF

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

    # --- Apply Injected Environment Updates ---
    $ENV_UPDATES
    # ------------------------------------------

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
