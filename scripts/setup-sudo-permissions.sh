#!/bin/bash
set -e

# Setup script for UPS Monitor sudo permissions
# This script configures passwordless sudo access for specific commands
# needed by the UPS Monitor application

echo "Setting up sudo permissions for UPS Monitor..."

# Get the current user
CURRENT_USER=${SUDO_USER:-$(whoami)}

if [ "$CURRENT_USER" = "root" ]; then
    echo "Error: Don't run this script as root directly."
    echo "Use: sudo ./setup-sudo-permissions.sh"
    exit 1
fi

echo "Configuring sudo permissions for user: $CURRENT_USER"

# Create sudoers file for UPS Monitor
SUDOERS_FILE="/etc/sudoers.d/apc-ups-monitor"

cat > "$SUDOERS_FILE" << EOF
# UPS Monitor sudo permissions
# Allows the UPS Monitor application to manage apcupsd configuration and services

$CURRENT_USER ALL=(root) NOPASSWD: /usr/bin/apt-get update
$CURRENT_USER ALL=(root) NOPASSWD: /usr/bin/apt-get install -y apcupsd apcupsd-cgi
$CURRENT_USER ALL=(root) NOPASSWD: /bin/cp /tmp/*.conf /etc/apcupsd/apcupsd.conf
$CURRENT_USER ALL=(root) NOPASSWD: /bin/cp /etc/apcupsd/apcupsd.conf /etc/apcupsd/apcupsd.conf.backup
$CURRENT_USER ALL=(root) NOPASSWD: /bin/cp /tmp/*.default /etc/default/apcupsd
$CURRENT_USER ALL=(root) NOPASSWD: /bin/chmod 644 /etc/apcupsd/apcupsd.conf
$CURRENT_USER ALL=(root) NOPASSWD: /bin/chmod 644 /etc/default/apcupsd
$CURRENT_USER ALL=(root) NOPASSWD: /bin/chown root\:root /etc/apcupsd/apcupsd.conf
$CURRENT_USER ALL=(root) NOPASSWD: /bin/chown root\:root /etc/default/apcupsd
$CURRENT_USER ALL=(root) NOPASSWD: /bin/systemctl daemon-reload
$CURRENT_USER ALL=(root) NOPASSWD: /bin/systemctl enable apcupsd
$CURRENT_USER ALL=(root) NOPASSWD: /bin/systemctl restart apcupsd
$CURRENT_USER ALL=(root) NOPASSWD: /bin/systemctl start apcupsd
$CURRENT_USER ALL=(root) NOPASSWD: /bin/systemctl stop apcupsd
EOF

# Set proper permissions on sudoers file
chmod 440 "$SUDOERS_FILE"

# Validate sudoers file
if visudo -c -f "$SUDOERS_FILE"; then
    echo "✓ Sudoers file created and validated successfully"
else
    echo "✗ Error: Invalid sudoers file created"
    rm -f "$SUDOERS_FILE"
    exit 1
fi

# Create apc-ups-monitor group if it doesn't exist
if ! getent group apc-ups-monitor >/dev/null 2>&1; then
    groupadd apc-ups-monitor
    echo "✓ Created apc-ups-monitor group"
fi

# Add user to apc-ups-monitor group
usermod -a -G apc-ups-monitor "$CURRENT_USER"
echo "✓ Added $CURRENT_USER to apc-ups-monitor group"

# Create directory for UPS Monitor data with proper permissions
UPS_DATA_DIR="/var/lib/apc-ups-monitor"
if [ ! -d "$UPS_DATA_DIR" ]; then
    mkdir -p "$UPS_DATA_DIR"
    chown "$CURRENT_USER":apc-ups-monitor "$UPS_DATA_DIR"
    chmod 755 "$UPS_DATA_DIR"
    echo "✓ Created data directory: $UPS_DATA_DIR"
fi

# Create log directory
UPS_LOG_DIR="/var/log/apc-ups-monitor"
if [ ! -d "$UPS_LOG_DIR" ]; then
    mkdir -p "$UPS_LOG_DIR"
    chown "$CURRENT_USER":apc-ups-monitor "$UPS_LOG_DIR"
    chmod 755 "$UPS_LOG_DIR"
    echo "✓ Created log directory: $UPS_LOG_DIR"
fi

echo ""
echo "✓ UPS Monitor sudo permissions configured successfully!"
echo ""
echo "The following commands can now be run without password by user '$CURRENT_USER':"
echo "- apcupsd package installation"
echo "- apcupsd configuration file management"
echo "- apcupsd service management"
echo ""
echo "SECURITY NOTE:"
echo "These permissions are restricted to specific paths and commands"
echo "required for UPS Monitor operation only."
echo ""
echo "You may need to log out and back in for group changes to take effect."
echo ""