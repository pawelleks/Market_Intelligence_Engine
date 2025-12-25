#!/bin/bash
set -e

echo "Starting System Hardening Process..."

# 1. Install Dependencies
echo "Installing libpam-pwquality..."
apt-get update
apt-get install -y libpam-pwquality

# 2. Configure Password Policies (/etc/security/pwquality.conf)
echo "Configuring Password Quality..."
CONFIG_FILE="/etc/security/pwquality.conf"
if [ ! -f "$CONFIG_FILE" ]; then
    touch "$CONFIG_FILE"
fi

# Function to update or add config
update_config() {
    local file="$1"
    local key="$2"
    local value="$3"
    if grep -q "^#*\s*${key}\s*=" "$file"; then
        sed -i "s/^#*\s*${key}\s*=.*/${key} = ${value}/" "$file"
    else
        echo "${key} = ${value}" >> "$file"
    fi
}

update_config "$CONFIG_FILE" "minlen" "12"
update_config "$CONFIG_FILE" "dcredit" "-1" # Require at least 1 digit
update_config "$CONFIG_FILE" "ucredit" "-1" # Require at least 1 uppercase
update_config "$CONFIG_FILE" "ocredit" "-1" # Require at least 1 other char
update_config "$CONFIG_FILE" "lcredit" "-1" # Require at least 1 lowercase

echo "Password quality configured."

# 3. Configure Password Aging & Umask (/etc/login.defs)
echo "Configuring Password Aging and Umask in /etc/login.defs..."
LOGIN_DEFS="/etc/login.defs"

# Update function for space-separated files
update_space_config() {
    local file="$1"
    local key="$2"
    local value="$3"
    if grep -q "^#*\s*${key}\s" "$file"; then
        sed -i "s/^#*\s*${key}\s.*/${key} ${value}/" "$file"
    else
        echo "${key} ${value}" >> "$file"
    fi
}

update_space_config "$LOGIN_DEFS" "PASS_MAX_DAYS" "90"
update_space_config "$LOGIN_DEFS" "PASS_MIN_DAYS" "1"
update_space_config "$LOGIN_DEFS" "PASS_WARN_AGE" "7"
update_space_config "$LOGIN_DEFS" "UMASK" "0027"

echo "Password aging and umask configured."

# 4. Lock down Cron
echo "Restricting Cron..."
echo "root" > /etc/cron.allow
echo "deploy" >> /etc/cron.allow
# Ensure cron.deny is empty or removed so only allow list applies (default behavior varies, usually allow takes precedence)
if [ -f /etc/cron.deny ]; then
    rm /etc/cron.deny
fi
echo "Cron restricted to root and deploy."

# 5. Disable unused user accounts
echo "Locking unused system accounts..."
# List of standard unused accounts to lock
UNUSED_USERS=("games" "gnats" "irc" "list" "news" "uucp" "proxy" "sync" "backup")

for user in "${UNUSED_USERS[@]}"; do
    if id "$user" &>/dev/null; then
        echo "Locking user $user..."
        usermod -L "$user" 2>/dev/null || echo "Could not lock $user (might be in use or protected?)"
        # Also set shell to /usr/sbin/nologin
        usermod -s /usr/sbin/nologin "$user"
    fi
done
echo "Unused accounts locked."

# 6. Restrict 'su' command
echo "Restricting 'su' to sudo group..."
# On Debian, it's often pam_wheel.so. Check if wheel exists, else use sudo group.
# By default, Debian uses 'sudo' group. pam_wheel checks for 'wheel' group by default unless 'group=' is specified.

PAM_SU="/etc/pam.d/su"
if [ -f "$PAM_SU" ]; then
    # We want: auth required pam_wheel.so use_uid group=sudo
    # Uncomment or add
    if grep -q "pam_wheel.so" "$PAM_SU"; then
        # Uncomment if commented
        sed -i 's/^#\s*\(auth.*pam_wheel.so\)/\1/' "$PAM_SU"
        
        # Ensure group=sudo is present if we are relying on sudo group
        # If the line doesn't have group=..., append it? 
        # Easier to just append a known good line if not present active
        if ! grep -q "^auth.*pam_wheel.so.*group=" "$PAM_SU"; then
             # Simple append might duplicate. Let's try to enable the standard line.
             # Standard line in Debian: # auth       required   pam_wheel.so
             # We want to change it to: auth       required   pam_wheel.so group=sudo
             sed -i 's/^auth.*pam_wheel.so$/auth       required   pam_wheel.so group=sudo/' "$PAM_SU"
        fi
    else
        echo "auth       required   pam_wheel.so group=sudo" >> "$PAM_SU"
    fi
fi
echo "su restricted."

echo "System Hardening Complete."
