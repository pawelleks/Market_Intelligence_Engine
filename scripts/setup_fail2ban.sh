#!/bin/bash
set -e

echo "Updating package lists..."
apt-get update

echo "Installing prerequisites (rsyslog, postfix)..."
# Pre-seed postfix configuration to avoid interactive prompt
debconf-set-selections <<< "postfix postfix/main_mailer_type string 'Internet Site'"
debconf-set-selections <<< "postfix postfix/mailname string $(hostname)"
apt-get install -y rsyslog postfix

echo "Installing Fail2Ban..."
apt-get install -y fail2ban

echo "Configuring Fail2Ban (jail.local)..."
cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
# Ban settings
bantime  = 1h
findtime = 10m
maxretry = 5

# Email settings
destemail = root@localhost
sender = fail2ban@$(hostname)
mta = sendmail
# action_mwl: ban & send an email with whois report and relevant log lines
action = %(action_mwl)s

[sshd]
enabled = true
port    = 2244
# backend = systemd is preferred on modern Debian if using journald, 
# but we installed rsyslog to ensure auth.log exists for traditional tools too.
# fail2ban in Debian 12+ works well with systemd backend.
backend = systemd
EOF

echo "Enabling and starting Fail2Ban..."
systemctl enable fail2ban
systemctl restart fail2ban

echo "Fail2Ban setup complete. Status:"
fail2ban-client status sshd
