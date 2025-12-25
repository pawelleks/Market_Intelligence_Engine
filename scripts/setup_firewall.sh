#!/bin/bash
set -e

echo "Installing UFW..."
apt-get update
apt-get install -y ufw

echo "Setting default policies..."
ufw default deny incoming
ufw default allow outgoing

echo "Configuring rules..."

# SSH - Limit to prevent brute force (port 2244)
# 'limit' allows 6 connections within 30 seconds, then denies
echo "Allowing SSH (rate limited) on port 2244..."
ufw limit 2244/tcp

# Web Application
echo "Allowing HTTP/HTTPS..."
ufw allow 80/tcp
ufw allow 443/tcp

# API
echo "Allowing API port 8000..."
ufw allow 8000/tcp

echo "Enabling logging..."
ufw logging medium

echo "Enabling UFW..."
# --force avoids the interactive "Command may disrupt existing ssh connections" prompt
ufw --force enable

echo "Firewall setup complete. Current Status:"
ufw status verbose
