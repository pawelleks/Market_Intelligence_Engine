#!/bin/bash
set -e

# 1. Get Client IP from SSH environment variable
if [ -z "$SSH_CLIENT" ]; then
    echo "Error: SSH_CLIENT environment variable not set. Are you connected via SSH?"
    exit 1
fi

CLIENT_IP=$(echo $SSH_CLIENT | awk '{print $1}')
echo "Detected Client IP: $CLIENT_IP"

# 2. Check if already ignored (runtime)
if fail2ban-client get sshd ignoreip | grep -q "$CLIENT_IP"; then
    echo "IP $CLIENT_IP is already whitelisted (runtime)."
else
    echo "Adding $CLIENT_IP to runtime whitelist..."
    fail2ban-client set sshd addignoreip "$CLIENT_IP"
fi

# 3. Persist in jail.local
JAIL_CONF="/etc/fail2ban/jail.local"
if [ -f "$JAIL_CONF" ]; then
    if grep -q "ignoreip.*$CLIENT_IP" "$JAIL_CONF"; then
         echo "IP $CLIENT_IP already present in $JAIL_CONF"
    else
         echo "Persisting to $JAIL_CONF..."
         # Append IP to the ignoreip line. Note: This assumes 'ignoreip = ...' exists.
         # If it doesn't, we need to add it.
         if grep -q "^ignoreip =" "$JAIL_CONF"; then
             sed -i "/^ignoreip =/ s/$/ $CLIENT_IP/" "$JAIL_CONF"
         else
             # Insert under [DEFAULT] if distinct ignoreip line missing (simpler fallback: just warn)
             echo "WARNING: Could not automatically append to 'ignoreip' in $JAIL_CONF. Please add manually:"
             echo "ignoreip = 127.0.0.1/8 $CLIENT_IP"
         fi
         # Restart to apply config changes
         systemctl restart fail2ban
    fi
else
    echo "Warning: $JAIL_CONF not found. Whitelist is runtime-only."
fi

echo "✅ Success: $CLIENT_IP whitelisted."
