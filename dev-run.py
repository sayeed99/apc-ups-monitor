#!/usr/bin/env python3
"""
Development runner for UPS Monitor
"""

import os
import sys
import tempfile
from pathlib import Path

# Load vendor packages first before any other imports
try:
    # Add src to path first so we can import vendor_loader
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    from vendor_loader import load_vendor_packages
    from debug_utils import debug
    load_vendor_packages()
    debug.info("Loaded vendor dependencies from wheel files")
except ImportError as e:
    # Import debug after path is set up
    try:
        from debug_utils import debug
        debug.warn(f"Warning: Could not load vendor packages: {e}")
        debug.warn("Falling back to system dependencies")
    except ImportError:
        print(f"Warning: Could not load vendor packages: {e}")
        print("Falling back to system dependencies")
except Exception as e:
    try:
        from debug_utils import debug
        debug.error(f"Error loading vendor packages: {e}")
        debug.error("Falling back to system dependencies")
    except ImportError:
        print(f"Error loading vendor packages: {e}")
        print("Falling back to system dependencies")

# Create a development-specific main function that avoids relative imports
def create_dev_app():
    """Create Flask app for development mode."""
    from flask import Flask, render_template, send_from_directory
    from flask_cors import CORS
    import os
    
    def get_package_path():
        """Get the base path of the package for development."""
        return os.path.dirname(os.path.abspath(__file__))
    
    package_path = get_package_path()
    
    app = Flask(__name__,
                template_folder=os.path.join(package_path, 'templates'),
                static_folder=os.path.join(package_path, 'static'))
    
    app.config['SECRET_KEY'] = 'apc-ups-monitor-secret-key-change-in-production'
    
    # Enable CORS for all routes
    CORS(app, origins="*")
    
    # Import and register the UPS monitoring blueprint
    from apc_ups_monitor import create_ups_blueprint
    app.register_blueprint(create_ups_blueprint())
    
    # Register apcupsd configuration routes
    from apcupsd_config import ApcupsdConfigManager
    register_apcupsd_routes(app)
    
    @app.route('/')
    def index():
        """Serve the main dashboard."""
        return render_template('index.html')
    
    @app.route('/favicon.ico')
    def favicon():
        """Serve favicon."""
        return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    
    return app

def register_apcupsd_routes(app):
    """Register apcupsd configuration routes."""
    from flask import request, jsonify
    from apcupsd_config import ApcupsdConfigManager
    
    config_manager = ApcupsdConfigManager()
    
    @app.route('/api/apcupsd/status')
    def apcupsd_status():
        """Get apcupsd installation and configuration status."""
        return jsonify(config_manager.get_apcupsd_status())
    
    @app.route('/api/apcupsd/detect-devices')
    def detect_ups_devices():
        """Detect connected UPS devices."""
        devices = config_manager.detect_ups_devices()
        return jsonify({'devices': devices})
    
    @app.route('/api/apcupsd/config-template')
    def get_config_template():
        """Get configuration template."""
        template = config_manager.get_config_template()
        return jsonify(template)
    
    @app.route('/api/apcupsd/current-config')
    def get_current_config():
        """Get current configuration values."""
        current_config = config_manager.get_current_config()
        return jsonify(current_config)
    
    @app.route('/api/apcupsd/install', methods=['POST'])
    def install_apcupsd():
        """Install apcupsd packages."""
        success, message = config_manager.install_apcupsd()
        return jsonify({'success': success, 'message': message})
    
    @app.route('/api/apcupsd/configure', methods=['POST'])
    def configure_apcupsd():
        """Configure apcupsd with provided settings."""
        try:
            config_data = request.get_json()
            if not config_data:
                return jsonify({'success': False, 'message': 'No configuration data provided'})
            
            success, message = config_manager.configure_ups(config_data)
            return jsonify({'success': success, 'message': message})
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'Configuration error: {str(e)}'})
    
    @app.route('/api/apcupsd/restart', methods=['POST'])
    def restart_apcupsd():
        """Restart apcupsd service."""
        success, message = config_manager.restart_apcupsd()
        return jsonify({'success': success, 'message': message})

# Import required modules
from apc_ups_monitor import UPSMonitor, init_database, setup_socketio

def main():
    # Use temporary directory for development
    dev_dir = Path('./dev_data')
    dev_dir.mkdir(exist_ok=True)
    
    db_path = dev_dir / 'ups_monitoring.db'
    
    debug.info(f"Starting UPS Monitor in development mode...")
    debug.info(f"Database: {db_path}")
    debug.info(f"Web interface: http://localhost:8556")
    debug.info(f"Press Ctrl+C to stop")
    
    # Set environment variable for database path
    os.environ['UPS_MONITOR_DB_PATH'] = str(db_path)
    
    # Initialize database
    init_database(str(db_path))
    
    # Create Flask app (development version)
    app = create_dev_app()
    
    # Setup SocketIO
    socketio = setup_socketio(app)
    
    # Initialize UPS monitor
    from apc_ups_monitor import apc_ups_monitor
    if apc_ups_monitor is None:
        apc_ups_monitor = UPSMonitor(db_path=str(db_path))
    
    # Start monitoring
    apc_ups_monitor.start_monitoring()
    
    # Store monitor instance in app for cleanup
    app.apc_ups_monitor = apc_ups_monitor
    
    try:
        # Run the application with unsafe werkzeug allowed for development
        socketio.run(app, host='0.0.0.0', port=8556, debug=True, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        debug.info("Shutting down...")
    finally:
        # Cleanup
        if hasattr(app, 'apc_ups_monitor'):
            app.apc_ups_monitor.stop_monitoring()
        debug.info("UPS Monitor stopped")

if __name__ == '__main__':
    main()