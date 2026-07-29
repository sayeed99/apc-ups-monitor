#!/bin/bash
set -e

# APC UPS Monitor Cleanup Script
# This script completely removes all traces of the APC UPS Monitor installation

echo "🧹 APC UPS Monitor Cleanup Script"
echo "================================="
echo ""
echo "This will remove:"
echo "- APC UPS Monitor package and service"
echo "- Configuration files"
echo "- Log files"
echo "- Database files (optional)"
echo "- User accounts and groups"
echo "- Sudo permissions"
echo "- Build artifacts"
echo ""

# Function to ask for confirmation
ask_confirmation() {
    local prompt="$1"
    local default="${2:-n}"
    
    while true; do
        if [ "$default" = "y" ]; then
            read -p "$prompt [Y/n]: " yn
            yn=${yn:-y}
        else
            read -p "$prompt [y/N]: " yn
            yn=${yn:-n}
        fi
        
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

# Function to safely remove directory
safe_remove_dir() {
    local dir="$1"
    if [ -d "$dir" ]; then
        echo "  Removing directory: $dir"
        rm -rf "$dir"
    else
        echo "  Directory not found: $dir (skipping)"
    fi
}

# Function to safely remove file
safe_remove_file() {
    local file="$1"
    if [ -f "$file" ]; then
        echo "  Removing file: $file"
        rm -f "$file"
    else
        echo "  File not found: $file (skipping)"
    fi
}

echo "⚠️  WARNING: This will permanently delete all APC UPS Monitor data!"
echo ""

if ! ask_confirmation "Do you want to proceed with cleanup?"; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "🔧 Starting cleanup process..."
echo ""

# 1. Stop and disable service
echo "1️⃣  Stopping and disabling service..."
if systemctl is-active --quiet apc-ups-monitor.service 2>/dev/null; then
    echo "  Stopping apc-ups-monitor service..."
    systemctl stop apc-ups-monitor.service
fi

if systemctl is-enabled --quiet apc-ups-monitor.service 2>/dev/null; then
    echo "  Disabling apc-ups-monitor service..."
    systemctl disable apc-ups-monitor.service
fi

# Reload systemd
systemctl daemon-reload 2>/dev/null || true

echo ""

# 2. Remove package
echo "2️⃣  Removing package..."
if dpkg -l | grep -q "apc-ups-monitor"; then
    echo "  Removing apc-ups-monitor package..."
    dpkg --purge apc-ups-monitor 2>/dev/null || true
    apt-get remove --purge -y apc-ups-monitor 2>/dev/null || true
else
    echo "  Package not found (may already be removed)"
fi

echo ""

# 3. Remove systemd service files
echo "3️⃣  Removing systemd files..."
safe_remove_file "/etc/systemd/system/apc-ups-monitor.service"
safe_remove_file "/lib/systemd/system/apc-ups-monitor.service"
systemctl daemon-reload 2>/dev/null || true

echo ""

# 4. Remove user and group
echo "4️⃣  Removing user and group..."
if getent passwd apc-ups-monitor >/dev/null 2>&1; then
    echo "  Removing user: apc-ups-monitor"
    userdel apc-ups-monitor 2>/dev/null || true
else
    echo "  User not found: apc-ups-monitor (skipping)"
fi

if getent group apc-ups-monitor >/dev/null 2>&1; then
    echo "  Removing group: apc-ups-monitor"
    groupdel apc-ups-monitor 2>/dev/null || true
else
    echo "  Group not found: apc-ups-monitor (skipping)"
fi

echo ""

# 5. Remove configuration files
echo "5️⃣  Removing configuration files..."
safe_remove_dir "/etc/apc-ups-monitor"

echo ""

# 6. Remove log files
echo "6️⃣  Removing log files..."
safe_remove_dir "/var/log/apc-ups-monitor"

# Remove journal logs
echo "  Cleaning systemd journal logs..."
journalctl --vacuum-time=1s --identifier=apc-ups-monitor 2>/dev/null || true

echo ""

# 7. Ask about database files
echo "7️⃣  Database files..."
if [ -d "/var/lib/apc-ups-monitor" ]; then
    echo "  Found database directory: /var/lib/apc-ups-monitor"
    if ask_confirmation "Remove database files? (This will delete all historical data)"; then
        safe_remove_dir "/var/lib/apc-ups-monitor"
    else
        echo "  Keeping database files in /var/lib/apc-ups-monitor"
        echo "  💡 To remove later: sudo rm -rf /var/lib/apc-ups-monitor"
    fi
else
    echo "  Database directory not found (skipping)"
fi

echo ""

# 8. Remove sudo permissions
echo "8️⃣  Removing sudo permissions..."
safe_remove_file "/etc/sudoers.d/apc-ups-monitor"

echo ""

# 9. Remove Python package (if installed via pip)
echo "9️⃣  Checking for pip-installed package..."
if pip3 show apc-ups-monitor >/dev/null 2>&1; then
    echo "  Removing pip package: apc-ups-monitor"
    pip3 uninstall -y apc-ups-monitor 2>/dev/null || true
else
    echo "  No pip package found (skipping)"
fi

echo ""

# 10. Clean up build artifacts
echo "🔟  Cleaning build artifacts..."
BUILD_DIR="$(dirname "$0")/../build"
if [ -d "$BUILD_DIR" ]; then
    echo "  Removing build directory..."
    rm -rf "$BUILD_DIR"
else
    echo "  Build directory not found (skipping)"
fi

# Clean up Python cache files
SCRIPT_DIR="$(dirname "$0")/.."
if [ -d "$SCRIPT_DIR" ]; then
    echo "  Cleaning Python cache files..."
    find "$SCRIPT_DIR" -name "*.pyc" -delete 2>/dev/null || true
    find "$SCRIPT_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$SCRIPT_DIR" -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
fi

echo ""

# 11. Optional: Remove development files
if [ -f "$(dirname "$0")/../dev-run.py" ]; then
    echo "🗂️   Development files..."
    if ask_confirmation "Remove development virtual environment and test databases?"; then
        safe_remove_dir "$(dirname "$0")/../test_env"
        safe_remove_file "$(dirname "$0")/../dev_ups_monitoring.db"
        safe_remove_file "$(dirname "$0")/../dev_ups_monitoring.db-shm"
        safe_remove_file "$(dirname "$0")/../dev_ups_monitoring.db-wal"
        safe_remove_dir "$(dirname "$0")/../dev_data"
        echo "  Development files removed"
    else
        echo "  Keeping development files"
    fi
fi

echo ""

# 12. Verification
echo "✅ Cleanup verification..."
echo ""

# Check for remaining files
REMAINING_FILES=()

if [ -d "/var/lib/apc-ups-monitor" ]; then
    REMAINING_FILES+=("/var/lib/apc-ups-monitor (database - kept by user choice)")
fi

if [ -f "/etc/systemd/system/apc-ups-monitor.service" ]; then
    REMAINING_FILES+=("/etc/systemd/system/apc-ups-monitor.service")
fi

if getent passwd apc-ups-monitor >/dev/null 2>&1; then
    REMAINING_FILES+=("apc-ups-monitor user account")
fi

if dpkg -l | grep -q "apc-ups-monitor"; then
    REMAINING_FILES+=("apc-ups-monitor package")
fi

if [ ${#REMAINING_FILES[@]} -eq 0 ]; then
    echo "🎉 Cleanup completed successfully!"
    echo "   All APC UPS Monitor components have been removed."
else
    echo "⚠️  Cleanup completed with some remaining items:"
    for item in "${REMAINING_FILES[@]}"; do
        echo "   - $item"
    done
fi

echo ""
echo "📋 Summary:"
echo "   - Service: Stopped and disabled"
echo "   - Package: Removed"
echo "   - User/Group: Removed"
echo "   - Config files: Removed"
echo "   - Log files: Removed"
echo "   - Sudo permissions: Removed"
echo "   - Build artifacts: Cleaned"
echo ""

# Final notes
echo "📝 Notes:"
echo "   - apcupsd package was NOT removed (it may be used by other applications)"
echo "   - Python dependencies were NOT removed (they may be used by other applications)"
echo "   - To reinstall: Run the installation process again"
if [ -d "/var/lib/apc-ups-monitor" ]; then
    echo "   - Database preserved in /var/lib/apc-ups-monitor"
fi
echo ""
echo "✨ Cleanup complete!"