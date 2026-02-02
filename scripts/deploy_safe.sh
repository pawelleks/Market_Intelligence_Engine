#!/bin/bash
set -e

# ==============================================================================
# Market Intelligence Engine - SAFE Remote Deployment Script
# ==============================================================================
# Features:
# - Full Data Backup (Analytics + DB)
# - Code Backup (Rollback capability)
# - Safe Sync (Excludes data overwrite)
# ==============================================================================

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
    echo "Usage: REMOTE_USER=user REMOTE_HOST=host [SSH_PORT=22] ./scripts/deploy_safe.sh"
    exit 1
fi

# Check Identity File
if [[ -n "$IDENTITY_FILE" ]]; then
    SSH_OPTS="-o StrictHostKeyChecking=no -i $IDENTITY_FILE -p $SSH_PORT"
else
    SSH_OPTS="-o StrictHostKeyChecking=no -p $SSH_PORT"
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "========================================================"
echo "SAFE DEPLOY to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}"
echo "========================================================"

# --- Pre-flight Check ---
echo "[0/4] Checking connectivity..."
ssh $SSH_OPTS -o ConnectTimeout=5 "${REMOTE_USER}@${REMOTE_HOST}" "echo Connection successful" || exit 1

# --- Step 1: Remote Backups (CRITICAL) ---
echo "[1/4] Creating Safety Backups on Remote Host..."
ssh $SSH_OPTS "${REMOTE_USER}@${REMOTE_HOST}" << EOF
    mkdir -p ${REMOTE_DIR}/_backups/${TIMESTAMP}
    
    # 1. Backup DATA (Analytics + DB)
    if [ -d "${REMOTE_DIR}/data" ]; then
        echo "Backing up 'data' directory..."
        # Use cp -al for hardlink copy (fast, minimal space) if possible, else cp -r
        # We use tar to be safe and isolated
        tar -czf ${REMOTE_DIR}/_backups/${TIMESTAMP}/data_backup.tar.gz -C ${REMOTE_DIR} data
        echo "Data backup saved to: _backups/${TIMESTAMP}/data_backup.tar.gz"
    else
        echo "No existing data directory found to backup."
    fi

    # 2. Backup CODE (For Rollback)
    echo "Backing up existing code..."
    # Exclude data, backups, logs, node_modules to keep it light
    tar -czf ${REMOTE_DIR}/_backups/${TIMESTAMP}/code_backup.tar.gz -C ${REMOTE_DIR} \
        --exclude='data' --exclude='_backups' --exclude='logs' --exclude='node_modules' .
    echo "Code backup saved to: _backups/${TIMESTAMP}/code_backup.tar.gz"
EOF

# --- Step 2: Sync Files (Rsync) ---
echo "[2/4] Syncing new code..."
# Excludes data to protect remote state
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
    --exclude '/data' \
    --exclude '/_backups' \
    ./ "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

# --- Step 3: Env Update ---
echo "[3/4] Updating Envs & Secrets..."
ENV_UPDATES=""
REQUIRED_KEYS=("POLYGON_API_KEY" "MASSIVE_API_KEY" "GOOGLE_CLIENT_ID" "JWT_SECRET_KEY" "OPENAI_API_KEY" "LLM_MODEL_NAME" "FRED_API_KEY" "SENDGRID_API_KEY" "SENDGRID_FROM_EMAIL" "SENDGRID_FROM_NAME")
for KEY in "${REQUIRED_KEYS[@]}"; do
    VAL="${!KEY}"
    if [ -z "$VAL" ]; then
         echo "WARNING: $KEY missing locally. Skipping update (Remote might have it)."
    else
         SAFE_VAL=$(printf %q "$VAL")
         ENV_UPDATES+="
         if grep -q \"^$KEY=\" .env; then sed -i \"/^$KEY=/d\" .env; fi
         echo \"$KEY=$SAFE_VAL\" >> .env
         "
    fi
done

# --- Step 4: Rebuild & Restart ---
echo "[4/4] Rebuilding & Restarting..."
ssh $SSH_OPTS "${REMOTE_USER}@${REMOTE_HOST}" << EOF
    set -e
    cd ${REMOTE_DIR}
    touch .env
    $ENV_UPDATES
    
    # Docker Rebuild
    if command -v docker-compose &> /dev/null; then
        docker-compose down || true
        docker rm -f mie-api mie-web mie-cron || true
        # Ensure Theta Terminal container is handled (if new)
        docker-compose up -d --build --remove-orphans
    else
        docker compose down || true
        docker rm -f mie-api mie-web mie-cron || true
        docker compose up -d --build --remove-orphans
    fi
    
    docker image prune -f
EOF

echo "========================================================"
echo "Deployment Complete!"
echo "Backup ID: ${TIMESTAMP}"
echo "--------------------------------------------------------"
echo "ROLLBACK INSTRUCTIONS:"
echo "If this deployment fails, run the following on remote:"
echo "  cd ${REMOTE_DIR}"
echo "  # Restore Code"
echo "  tar -xzf _backups/${TIMESTAMP}/code_backup.tar.gz"
echo "  # Restore Data (If corrupted)"
echo "  # rm -rf data && tar -xzf _backups/${TIMESTAMP}/data_backup.tar.gz"
echo "  # Restart"
echo "  docker-compose up -d"
echo "========================================================"
