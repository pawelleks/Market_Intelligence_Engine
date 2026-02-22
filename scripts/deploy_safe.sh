#!/bin/bash
set -e

# ==============================================================================
# Market Intelligence Engine - SAFE Remote Deployment Script
# ==============================================================================
# Usage:
#   ./scripts/deploy_safe.sh [staging|production]
#
# Defaults to "production" if no argument given.
# ==============================================================================

# --- Environment Selection ---
DEPLOY_ENV="${1:-production}"

case "$DEPLOY_ENV" in
    staging)
        ENV_CADDYFILE="Caddyfile.staging"
        ENV_DISABLE_AUTH="true"
        ;;
    production|prod)
        DEPLOY_ENV="production"
        ENV_CADDYFILE="Caddyfile.prod"
        ENV_DISABLE_AUTH="false"
        ;;
    *)
        echo "Error: Unknown environment '$DEPLOY_ENV'. Use 'staging' or 'production'."
        exit 1
        ;;
esac

# --- Configuration ---
REMOTE_USER="${REMOTE_USER:-}"
REMOTE_HOST="${REMOTE_HOST:-}"
IDENTITY_FILE="${IDENTITY_FILE:-}"
REMOTE_DIR="${REMOTE_DIR:-}"
SSH_PORT="${SSH_PORT:-22}"

# --- Load Local .env (preserve connection vars if already set) ---
_SAVED_REMOTE_USER="${REMOTE_USER:-}"
_SAVED_REMOTE_HOST="${REMOTE_HOST:-}"
_SAVED_IDENTITY_FILE="${IDENTITY_FILE:-}"
_SAVED_REMOTE_DIR="${REMOTE_DIR:-}"
_SAVED_SSH_PORT="${SSH_PORT:-}"

if [ -f ".env" ]; then
    echo "Loading local .env file..."
    set -a
    source .env
    set +a
fi

# Restore connection vars that were set before .env was loaded
[ -n "$_SAVED_REMOTE_USER" ] && REMOTE_USER="$_SAVED_REMOTE_USER"
[ -n "$_SAVED_REMOTE_HOST" ] && REMOTE_HOST="$_SAVED_REMOTE_HOST"
[ -n "$_SAVED_IDENTITY_FILE" ] && IDENTITY_FILE="$_SAVED_IDENTITY_FILE"
[ -n "$_SAVED_REMOTE_DIR" ] && REMOTE_DIR="$_SAVED_REMOTE_DIR"
[ -n "$_SAVED_SSH_PORT" ] && SSH_PORT="$_SAVED_SSH_PORT"

# --- Validation ---
if [[ -z "$REMOTE_USER" || -z "$REMOTE_HOST" ]]; then
    echo "Error: REMOTE_USER and REMOTE_HOST environment variables must be set."
    echo "Usage: ./scripts/deploy_safe.sh [staging|production]"
    exit 1
fi

# Check Identity File
if [[ -n "$IDENTITY_FILE" ]]; then
    SSH_OPTS="-o StrictHostKeyChecking=no -i $IDENTITY_FILE -p $SSH_PORT"
else
    SSH_OPTS="-o StrictHostKeyChecking=no -p $SSH_PORT"
fi

# Resolve REMOTE_DIR: default to remote $HOME/market_intelligence_engine
if [[ -z "$REMOTE_DIR" ]]; then
    REMOTE_HOME=$(ssh $SSH_OPTS -o ConnectTimeout=5 "${REMOTE_USER}@${REMOTE_HOST}" 'echo $HOME')
    REMOTE_DIR="${REMOTE_HOME}/market_intelligence_engine"
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "========================================================"
echo "SAFE DEPLOY [${DEPLOY_ENV}] to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}"
echo "  Caddyfile: ${ENV_CADDYFILE}  |  Auth disabled: ${ENV_DISABLE_AUTH}"
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
    --exclude '/public/data' \
    ./ "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

# --- Step 3: Env Update ---
echo "[3/4] Updating Envs & Secrets..."
ENV_UPDATES=""
REQUIRED_KEYS=("POLYGON_API_KEY" "MASSIVE_API_KEY" "GOOGLE_CLIENT_ID" "JWT_SECRET_KEY" "OPENAI_API_KEY" "LLM_MODEL_NAME" "FRED_API_KEY" "SENDGRID_API_KEY" "SENDGRID_FROM_EMAIL" "SENDGRID_FROM_NAME" "THETADATA_USERNAME" "THETADATA_PASSWORD")

# Environment-specific overrides (Caddy config + auth)
ENV_OVERRIDES=(
    "CADDYFILE=${ENV_CADDYFILE}"
    "VITE_DISABLE_AUTH=${ENV_DISABLE_AUTH}"
)
for OVERRIDE in "${ENV_OVERRIDES[@]}"; do
    KEY="${OVERRIDE%%=*}"
    VAL="${OVERRIDE#*=}"
    ENV_UPDATES+="
    if grep -q \"^$KEY=\" .env; then sed -i \"/^$KEY=/d\" .env; fi
    echo \"$KEY=$VAL\" >> .env
    "
done
for KEY in "${REQUIRED_KEYS[@]}"; do
    VAL="${!KEY}"
    if [ -z "$VAL" ]; then
         echo "WARNING: $KEY missing locally. Skipping update (Remote might have it)."
    else
         SAFE_VAL="${VAL//\$/\\$}"
         ENV_UPDATES+="
         if grep -q \"^$KEY=\" .env; then sed -i \"/^$KEY=/d\" .env; fi
         echo \"$KEY='$SAFE_VAL'\" >> .env
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
