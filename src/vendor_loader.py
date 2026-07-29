#!/usr/bin/env python3
"""
Vendor loader to load bundled dependencies
"""
import os
import sys
import glob
import zipfile
import tempfile
import shutil
from .debug_utils import debug

def load_vendor_packages():
    """Load vendored packages from the vendor directory."""
    # Get the directory where this module is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Look for vendor directory in various locations
    vendor_paths = [
        # Development mode - relative to src directory
        os.path.join(current_dir, '..', 'vendor'),
        # Development mode - relative to project root
        os.path.join(os.path.dirname(current_dir), 'vendor'),
        # System installation paths
        '/usr/lib/python3/dist-packages/vendor',
        '/usr/apc_ups_monitor/vendor',
        # Alternative system paths
        '/usr/lib/python3/dist-packages/apc_ups_monitor/vendor',
        # User installation path
        os.path.join(os.path.expanduser('~'), '.local/lib/python3/site-packages/apc_ups_monitor/vendor')
    ]
    
    vendor_dir = None
    for path in vendor_paths:
        if os.path.exists(path):
            vendor_dir = path
            break
    
    if vendor_dir and os.path.exists(vendor_dir):
        # Get all wheel files
        wheel_files = glob.glob(os.path.join(vendor_dir, '*.whl'))
        debug.info(f"Found vendor directory: {vendor_dir}")
        debug.info(f"Found {len(wheel_files)} wheel files")
        
        # Create a persistent directory for extracted wheels (avoid temp cleanup issues)
        extract_base_dir = os.path.join(tempfile.gettempdir(), 'apc_ups_vendor_packages')
        os.makedirs(extract_base_dir, exist_ok=True)
        
        # Extract each wheel and add to sys.path
        for wheel_file in wheel_files:
            if os.path.exists(wheel_file):
                try:
                    # Extract wheel to a dedicated directory
                    wheel_name = os.path.basename(wheel_file).replace('.whl', '')
                    extract_path = os.path.join(extract_base_dir, wheel_name)
                    
                    # Only extract if not already extracted
                    if not os.path.exists(extract_path):
                        os.makedirs(extract_path, exist_ok=True)
                        with zipfile.ZipFile(wheel_file, 'r') as zip_ref:
                            zip_ref.extractall(extract_path)
                        debug.info(f"Extracted: {wheel_name}")
                    
                    # Add extracted path to sys.path with HIGH priority to override system packages
                    if extract_path not in sys.path:
                        # Insert at position 1 (after current directory) to ensure vendor packages take priority
                        sys.path.insert(1, extract_path)
                        
                except Exception as e:
                    debug.warn(f"Warning: Could not extract vendor package {wheel_file}: {e}")
                    # Fallback: try adding wheel file directly
                    if wheel_file not in sys.path:
                        sys.path.insert(0, wheel_file)
        
        # Test critical imports to verify vendor packages work
        try:
            import flask
            import flask_socketio
            import werkzeug
            debug.info(f"Successfully loaded {len(wheel_files)} vendor packages from extracted directories")
            try:
                from importlib.metadata import version
                flask_ver = version('flask')
                werkzeug_ver = version('werkzeug')
                debug.info(f"Test import successful: flask version {flask_ver}, werkzeug version {werkzeug_ver}")
            except:
                debug.info(f"Test import successful: packages loaded")
            return True
        except ImportError as e:
            debug.warn(f"Warning: Vendor packages loaded but some dependencies missing: {e}")
            debug.warn("This is normal - system packages will be used for missing dependencies")
            return True  # Return True anyway, let system packages fill gaps
    else:
        debug.info("No vendor directory found. Checked paths:")
        for path in vendor_paths:
            debug.info(f"  - {path} {'(exists)' if os.path.exists(path) else '(not found)'}")
        return False

# Load vendor packages when this module is imported (only in production)
# Development mode will call this explicitly
if __name__ != '__main__':
    # Only auto-load in production/package mode, not when called from dev-run
    try:
        import sys
        if 'dev-run.py' not in ' '.join(sys.argv):
            load_vendor_packages()
    except:
        pass
