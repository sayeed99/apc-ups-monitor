#!/bin/bash
set -e

# Setup script for UPS Monitor sudo permissions
# This script configures passwordless sudo access for specific commands
# needed by the UPS Monitor application

echo "Setting up sudo permissions for UPS Monitor..."

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: run this repair tool with sudo."
    echo "Use: sudo ./scripts/setup-sudo-permissions.sh"
    exit 1
fi

SERVICE_USER=apc-ups-monitor
if ! getent passwd "$SERVICE_USER" >/dev/null 2>&1; then
    adduser --system --group --home /var/lib/apc-ups-monitor --no-create-home \
        --gecos "APC UPS Monitor Service" --shell /bin/false "$SERVICE_USER"
fi

mkdir -p /var/lib/apc-ups-monitor/staging /var/log/apc-ups-monitor
chown -R "$SERVICE_USER:$SERVICE_USER" /var/lib/apc-ups-monitor /var/log/apc-ups-monitor
chmod 755 /var/lib/apc-ups-monitor /var/lib/apc-ups-monitor/staging /var/log/apc-ups-monitor

echo "Configuring sudo permissions for service account: $SERVICE_USER"

# Create sudoers file for UPS Monitor
SUDOERS_FILE="/etc/sudoers.d/apc-ups-monitor"

cat > "$SUDOERS_FILE" << EOF
# UPS Monitor sudo permissions
# Allows the UPS Monitor application to manage apcupsd configuration and services

$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/apt-get update
$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/apt-get install -y apcupsd apcupsd-cgi
$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/cp /etc/apcupsd/apcupsd.conf /etc/apcupsd/apcupsd.conf.backup
$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/install -o root -g root -m 0644 /var/lib/apc-ups-monitor/staging/apcupsd.conf /etc/apcupsd/apcupsd.conf
$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/install -o root -g root -m 0644 /var/lib/apc-ups-monitor/staging/apcupsd.default /etc/default/apcupsd
$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/systemctl daemon-reload
$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/systemctl enable apcupsd
$SERVICE_USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart apcupsd
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

echo ""
echo "✓ UPS Monitor sudo permissions configured successfully!"
echo ""
echo "The following operations can now be run by service account '$SERVICE_USER':"
echo "- apcupsd package installation"
echo "- apcupsd configuration file management"
echo "- apcupsd service management"
echo ""
echo "SECURITY NOTE:"
echo "These permissions are restricted to specific paths and commands"
echo "required for UPS Monitor operation only."
echo ""
