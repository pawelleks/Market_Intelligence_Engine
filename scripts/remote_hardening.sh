#!/bin/bash
set -e

# 1. Update all packages
echo "Updating package lists and upgrading packages..."
apt-get update
apt-get upgrade -y

# 2. Configure automatic security updates
echo "Installing and configuring unattended-upgrades..."
apt-get install -y unattended-upgrades apt-listchanges

# Create configuration for unattended-upgrades
cat > /etc/apt/apt.conf.d/50unattended-upgrades <<EOF
Unattended-Upgrade::Allowed-Origins {
    "\${distro_id}:\${distro_codename}-security";
    "\${distro_id}:\${distro_codename}-updates";
    "\${distro_id}:\${distro_codename}";
};
Unattended-Upgrade::Package-Blacklist {
};
Unattended-Upgrade::DevRelease "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

# Enable auto-upgrades
cat > /etc/apt/apt.conf.d/20auto-upgrades <<EOF
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

echo "Unattended upgrades configured."

# 3. Set up non-root user 'deploy'
if id "deploy" &>/dev/null; then
    echo "User 'deploy' already exists. Skipping creation."
else
    echo "Creating user 'deploy'..."
    useradd -m -s /bin/bash deploy
    # Start with a disabled password or random? Usually better to just rely on SSH key, 
    # but sudo might require a password.
    # For now we will rely on sudo group.
fi

# Add to sudo group
usermod -aG sudo deploy
echo "User 'deploy' added to sudo group."

# 4. Add SSH public key
echo "Setting up SSH key for 'deploy'..."
mkdir -p /home/deploy/.ssh
chmod 700 /home/deploy/.ssh

# Your public key
PUB_KEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMUtfZ/HwJd+UEc8k54k0boN3cJUyzORUB0UQUmAohh7"

if ! grep -q "$PUB_KEY" /home/deploy/.ssh/authorized_keys 2>/dev/null; then
    echo "$PUB_KEY" >> /home/deploy/.ssh/authorized_keys
    echo "Key added."
else
    echo "Key already authorized."
fi

chmod 600 /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh

echo "Security hardening steps complete!"
