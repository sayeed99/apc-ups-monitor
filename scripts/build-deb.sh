#!/bin/bash

# Build script for UPS Monitor Debian package
# Usage: ./build-deb.sh [--no-version-bump] [--help]
# 
# Options:
#   --no-version-bump    Skip automatic minor version bump before building
#   --help              Show this help message

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PACKAGE_DIR/build"

# Function to show help
show_help() {
    echo "UPS Monitor Debian Package Build Script"
    echo "========================================"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --no-version-bump    Skip automatic minor version bump before building"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                   # Build with automatic minor version bump"
    echo "  $0 --no-version-bump # Build without changing version"
    echo ""
    echo "The script will automatically:"
    echo "  1. Bump minor version (unless --no-version-bump is used)"
    echo "  2. Install build dependencies"
    echo "  3. Build Debian package"
    echo "  4. Move package files to build/ directory"
    echo ""
}

# Parse command line arguments
SKIP_VERSION_BUMP=false
for arg in "$@"; do
    case $arg in
        --no-version-bump)
        SKIP_VERSION_BUMP=true
        shift
        ;;
        --help)
        show_help
        exit 0
        ;;
        *)
        echo "Unknown option: $arg"
        echo "Use --help for usage information"
        exit 1
        ;;
    esac
done

echo "Building UPS Monitor Debian package..."
echo "Package directory: $PACKAGE_DIR"
echo "Build directory: $BUILD_DIR"

cd "$PACKAGE_DIR"

# Auto-bump minor version before building (unless skipped)
if [[ "$SKIP_VERSION_BUMP" == "false" ]]; then
    echo "Auto-bumping minor version..."
    if [[ -x "$SCRIPT_DIR/bump-version.sh" ]]; then
        # Run version bump non-interactively
        OLD_VERSION=$(grep -E '^\s*version=' "$PACKAGE_DIR/setup.py" | sed -E 's/.*version="([^"]+)".*/\1/')
        echo "Current version: $OLD_VERSION"
        
        # Automatically bump minor version
        echo "y" | "$SCRIPT_DIR/bump-version.sh" minor
        
        NEW_VERSION=$(grep -E '^\s*version=' "$PACKAGE_DIR/setup.py" | sed -E 's/.*version="([^"]+)".*/\1/')
        echo "Version bumped: $OLD_VERSION -> $NEW_VERSION"
    else
        echo "Warning: bump-version.sh not found or not executable"
    fi
else
    echo "Skipping version bump (--no-version-bump flag provided)"
    CURRENT_VERSION=$(grep -E '^\s*version=' "$PACKAGE_DIR/setup.py" | sed -E 's/.*version="([^"]+)".*/\1/')
    echo "Using current version: $CURRENT_VERSION"
fi

# Clean previous build
if [ -d "$BUILD_DIR" ]; then
    rm -rf "$BUILD_DIR"
fi

# Install build dependencies
echo "Installing build dependencies..."
sudo apt-get update
sudo apt-get install -y build-essential debhelper python3-setuptools python3-all dh-python

# Build the package
echo "Building package..."
dpkg-buildpackage -us -uc -b

# Move packages to build directory
mkdir -p "$BUILD_DIR"
mv ../*.deb "$BUILD_DIR/" 2>/dev/null || true
mv ../*.changes "$BUILD_DIR/" 2>/dev/null || true
mv ../*.buildinfo "$BUILD_DIR/" 2>/dev/null || true

# Get final version for success message
FINAL_VERSION=$(grep -E '^\s*version=' "$PACKAGE_DIR/setup.py" | sed -E 's/.*version="([^"]+)".*/\1/')

echo "Package built successfully!"
echo "Version: $FINAL_VERSION"
echo "Package files:"
ls -la "$BUILD_DIR"

echo ""
echo "To install the package, run:"
echo "sudo dpkg -i $BUILD_DIR/apc-ups-monitor_*.deb"
echo "sudo apt-get install -f  # Fix any dependency issues"

echo ""
echo "Build completed for version: $FINAL_VERSION"