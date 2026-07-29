#!/bin/bash
# Show Current Version Script for APC UPS Monitor

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "APC UPS Monitor - Current Version Information"
echo "============================================="

# Check setup.py
if [[ -f "$PROJECT_DIR/setup.py" ]]; then
    setup_version=$(grep -E '^\s*version=' "$PROJECT_DIR/setup.py" | sed -E 's/.*version="([^"]+)".*/\1/')
    echo "setup.py:              $setup_version"
else
    echo "setup.py:              NOT FOUND"
fi

# Check src/__init__.py
if [[ -f "$PROJECT_DIR/src/__init__.py" ]]; then
    init_version=$(grep -E '^__version__' "$PROJECT_DIR/src/__init__.py" | sed -E 's/.*"([^"]+)".*/\1/')
    echo "src/__init__.py:       $init_version"
else
    echo "src/__init__.py:       NOT FOUND"
fi

# Check debian/changelog
if [[ -f "$PROJECT_DIR/debian/changelog" ]]; then
    debian_version=$(head -n1 "$PROJECT_DIR/debian/changelog" | sed -E 's/.*\(([^)]+)\).*/\1/')
    echo "debian/changelog:      $debian_version"
else
    echo "debian/changelog:      NOT FOUND"
fi

# Check if versions are consistent
echo
if [[ "$setup_version" == "${init_version}" && "$setup_version" == "${debian_version%-*}" ]]; then
    echo "✅ All versions are consistent: $setup_version"
else
    echo "⚠️  Version mismatch detected!"
    echo "   Run ./scripts/bump-version.sh to fix inconsistencies"
fi