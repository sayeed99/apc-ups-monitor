#!/bin/bash
# Version Bump Script for APC UPS Monitor
# Usage: ./scripts/bump-version.sh [major|minor|patch] [new_version]
# Examples: 
#   ./scripts/bump-version.sh patch        # 1.0.0 -> 1.0.1
#   ./scripts/bump-version.sh minor        # 1.0.0 -> 1.1.0  
#   ./scripts/bump-version.sh major        # 1.0.0 -> 2.0.0
#   ./scripts/bump-version.sh 1.2.3        # Set to specific version

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Function to get current version from setup.py
get_current_version() {
    grep -E '^\s*version=' "$PROJECT_DIR/setup.py" | sed -E 's/.*version="([^"]+)".*/\1/'
}

# Function to increment version
increment_version() {
    local current_version="$1"
    local bump_type="$2"
    
    IFS='.' read -ra VERSION_PARTS <<< "$current_version"
    major="${VERSION_PARTS[0]}"
    minor="${VERSION_PARTS[1]}"
    patch="${VERSION_PARTS[2]}"
    
    case "$bump_type" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch)
            patch=$((patch + 1))
            ;;
        *)
            echo "Invalid bump type: $bump_type"
            exit 1
            ;;
    esac
    
    echo "${major}.${minor}.${patch}"
}

# Function to validate version format
validate_version() {
    local version="$1"
    if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Error: Invalid version format '$version'. Expected format: X.Y.Z"
        exit 1
    fi
}

# Function to update version in file with specific patterns
update_version_in_file() {
    local file="$1"
    local old_version="$2" 
    local new_version="$3"
    local pattern="$4"
    
    if [[ ! -f "$file" ]]; then
        echo "Warning: File $file not found, skipping"
        return
    fi
    
    # Use specific patterns for each file type to avoid false replacements
    case "$(basename "$file")" in
        "setup.py")
            sed -i "s/version=\"$old_version\"/version=\"$new_version\"/" "$file"
            ;;
        "__init__.py")
            sed -i "s/__version__ = \"$old_version\"/__version__ = \"$new_version\"/" "$file"
            ;;
        "apc_ups_monitor.py")
            sed -i "s/'version': '$old_version'/'version': '$new_version'/" "$file"
            ;;
        *)
            # For other files, use generic replacement
            sed -i "s/$old_version/$new_version/g" "$file"
            ;;
    esac
    
    echo "✓ Updated $file"
}

# Function to update debian changelog
update_debian_changelog() {
    local new_version="$1"
    local changelog_file="$PROJECT_DIR/debian/changelog"
    
    # Create new changelog entry
    local timestamp=$(date -R)
    local temp_file=$(mktemp)
    
    cat > "$temp_file" << EOF
apc-ups-monitor (${new_version}-1) unstable; urgency=low

  * Version bump to ${new_version}
  * Automated version update

 -- Sayeed Afridi <sayeed.afridi2009@gmail.comm>  $timestamp

EOF
    
    if [[ -f "$changelog_file" ]]; then
        cat "$changelog_file" >> "$temp_file"
    fi
    
    mv "$temp_file" "$changelog_file"
    echo "✓ Updated debian/changelog"
}

# Main script
main() {
    echo "APC UPS Monitor Version Bump Script"
    echo "===================================="
    
    # Get current version
    current_version=$(get_current_version)
    echo "Current version: $current_version"
    
    # Parse arguments
    if [[ $# -eq 0 ]]; then
        echo "Usage: $0 [major|minor|patch|VERSION]"
        echo "Examples:"
        echo "  $0 patch        # $current_version -> increment patch"
        echo "  $0 minor        # $current_version -> increment minor" 
        echo "  $0 major        # $current_version -> increment major"
        echo "  $0 1.2.3        # $current_version -> 1.2.3"
        exit 1
    fi
    
    # Determine new version
    if [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        new_version="$1"
        validate_version "$new_version"
    elif [[ "$1" =~ ^(major|minor|patch)$ ]]; then
        new_version=$(increment_version "$current_version" "$1")
    else
        echo "Error: Invalid argument '$1'"
        exit 1
    fi
    
    echo "New version: $new_version"
    echo
    
    # Confirm update
    read -p "Update version from $current_version to $new_version? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled"
        exit 0
    fi
    
    echo "Updating version in files..."
    
    # Update version in all relevant files
    update_version_in_file "$PROJECT_DIR/setup.py" "$current_version" "$new_version"
    update_version_in_file "$PROJECT_DIR/src/__init__.py" "$current_version" "$new_version" 
    update_version_in_file "$PROJECT_DIR/src/apc_ups_monitor.py" "$current_version" "$new_version"
    
    # Update debian changelog (this needs special handling)
    update_debian_changelog "$new_version"
    
    # Clean up build artifacts to force rebuild
    if [[ -d "$PROJECT_DIR/build" ]]; then
        rm -rf "$PROJECT_DIR/build"
        echo "✓ Cleaned build directory"
    fi
    
    if [[ -d "$PROJECT_DIR/dist" ]]; then
        rm -rf "$PROJECT_DIR/dist" 
        echo "✓ Cleaned dist directory"
    fi
    
    if [[ -d "$PROJECT_DIR"/*.egg-info ]]; then
        rm -rf "$PROJECT_DIR"/*.egg-info
        echo "✓ Cleaned egg-info directories"
    fi
    
    echo
    echo "✅ Version successfully updated to $new_version"
    echo "Next steps:"
    echo "  1. Review changes: git diff"
    echo "  2. Build package: dpkg-buildpackage -us -uc"
    echo "  3. Commit changes: git add . && git commit -m 'Bump version to $new_version'"
    echo "  4. Tag release: git tag v$new_version"
}

# Run main function
main "$@"