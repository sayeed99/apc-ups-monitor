#!/bin/bash

# Local installation script for UPS Monitor (development/testing)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(dirname "$SCRIPT_DIR")"

echo "Installing UPS Monitor locally for development/testing..."
echo "Package directory: $PACKAGE_DIR"

cd "$PACKAGE_DIR"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo "Please don't run this script as root. It will use sudo when needed."
    exit 1
fi

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv apcupsd

# Setup sudo permissions for UPS Monitor operations
echo "Setting up sudo permissions for configuration management..."
sudo "$SCRIPT_DIR/setup-sudo-permissions.sh"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create directories
echo "Creating directories..."
sudo mkdir -p /var/lib/apc-ups-monitor
sudo mkdir -p /var/log/apc-ups-monitor
sudo mkdir -p /etc/apc-ups-monitor

# Create apc-ups-monitor user
echo "Creating apc-ups-monitor user..."
if ! getent passwd apc-ups-monitor >/dev/null 2>&1; then
    sudo adduser --system --group --home /var/lib/apc-ups-monitor --no-create-home \
        --gecos "UPS Monitor Service" --shell /bin/false apc-ups-monitor
fi

# Set permissions
echo "Setting permissions..."
sudo chown -R apc-ups-monitor:apc-ups-monitor /var/lib/apc-ups-monitor
sudo chown -R apc-ups-monitor:apc-ups-monitor /var/log/apc-ups-monitor
sudo chmod 755 /var/lib/apc-ups-monitor
sudo chmod 755 /var/log/apc-ups-monitor

# Install systemd service
echo "Installing systemd service..."
sudo cp systemd/apc-ups-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload

# Create configuration
echo "Creating configuration..."
if [ ! -f /etc/apc-ups-monitor/config.conf ]; then
    sudo cp /dev/stdin <<'EOF' > /etc/apc-ups-monitor/config.conf
# UPS Monitor Configuration
[DEFAULT]
host = 0.0.0.0
port = 5000
debug = false
log_level = INFO
db_path = /var/lib/apc-ups-monitor/ups_monitoring.db

[database]
# Database connection pool settings
pool_size = 5
cache_timeout = 30
monitor_interval = 5
batch_size = 100

[monitoring]
# UPS monitoring settings
use_mock_data = false
apcaccess_timeout = 5
websocket_emit_interval = 2
EOF
    sudo chown apc-ups-monitor:apc-ups-monitor /etc/apc-ups-monitor/config.conf
    sudo chmod 644 /etc/apc-ups-monitor/config.conf
fi

# Install the package in development mode
echo "Installing package in development mode..."
pip install -e .

# Create a wrapper script
echo "Creating wrapper script..."
sudo tee /usr/local/bin/apc-ups-monitor <<EOF
#!/bin/bash
cd "$PACKAGE_DIR"
source venv/bin/activate
exec python -m src.main "\$@"
EOF

sudo chmod +x /usr/local/bin/apc-ups-monitor

# Start the service
echo "Starting UPS Monitor service..."
sudo systemctl enable apc-ups-monitor
sudo systemctl start apc-ups-monitor

echo ""
echo "UPS Monitor installed successfully!"
echo "Service status:"
sudo systemctl status apc-ups-monitor --no-pager
echo ""
echo "Access the web interface at: http://localhost:5000"
echo "Logs can be viewed with: sudo journalctl -u apc-ups-monitor -f"
echo ""
echo "To stop the service: sudo systemctl stop apc-ups-monitor"
echo "To start the service: sudo systemctl start apc-ups-monitor"
echo "To restart the service: sudo systemctl restart apc-ups-monitor"