#!/bin/bash
set -e

CONFIG_FILE="/etc/ssh/sshd_config"
BACKUP_FILE="/etc/ssh/sshd_config.bak.$(date +%F_%T)"

echo "Backing up sshd_config to $BACKUP_FILE..."
cp $CONFIG_FILE $BACKUP_FILE

# Function to update or add a configuration option
update_config() {
    local key="$1"
    local value="$2"
    if grep -q "^[#]*\s*${key}\s" "$CONFIG_FILE"; then
        sed -i "s/^[#]*\s*${key}\s.*/${key} ${value}/" "$CONFIG_FILE"
    else
        echo "${key} ${value}" >> "$CONFIG_FILE"
    fi
}

echo "Applying hardening configuration..."

# 1. Change Port
# Note: changing port needs to be done carefully. Default might be commented out.
update_config "Port" "2244"

# 2. PermitRootLogin no
update_config "PermitRootLogin" "no"

# 3. PasswordAuthentication no
update_config "PasswordAuthentication" "no"

# 4. PubkeyAuthentication yes
update_config "PubkeyAuthentication" "yes"

# 5. Protocol 2
# Some modern SSHD versions might deprecate this, but user requested it.
update_config "Protocol" "2"

# 6. LoginGraceTime 30
update_config "LoginGraceTime" "30"

# 7. MaxAuthTries 3
update_config "MaxAuthTries" "3"

# Ensure ChallengeResponseAuthentication is no (often defaults to yes in some older distros, safer to disable if using keys only)
update_config "ChallengeResponseAuthentication" "no"

# 8. Session Timeout (10 minutes)
# ClientAliveInterval 300 (5 minutes) * ClientAliveCountMax 2 = 10 minutes
update_config "ClientAliveInterval" "300"
update_config "ClientAliveCountMax" "2"

# UsePAM yes is usually needed for session setup, but PasswordAuth is controlled separately. keeping default or what is there.

echo "Configuration applied. Testing config syntax..."
if sshd -t; then
    echo "Syntax check passed. Reloading SSHD..."
    systemctl reload ssh
    echo "SSHD reloaded successfully."
else
    echo "Syntax check FAILED! Reverting changes..."
    cp $BACKUP_FILE $CONFIG_FILE
    echo "Changes reverted. Please check the error manually."
    exit 1
fi
