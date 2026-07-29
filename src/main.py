#!/usr/bin/env python3
"""
UPS Monitor Main Application
Self-contained UPS monitoring service with web interface
"""

# Load vendor packages first before any other imports
try:
    from .vendor_loader import load_vendor_packages
    load_vendor_packages()
except ImportError:
    pass

import os
import sys
import argparse
import logging
from flask import Flask, render_template, send_from_directory
from flask_cors import CORS

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from .apc_ups_monitor import UPSMonitor, init_database, setup_socketio
from .apcupsd_config import ApcupsdConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def register_apcupsd_routes(app):
    """Register apcupsd configuration routes."""
    from flask import request, jsonify
    
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

def get_package_path():
    """Get the base path of the package installation."""
    # Try to find the package installation directory
    possible_paths = [
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # Development
        '/usr/lib/python3/dist-packages/apc-ups-monitor',  # System installation
        '/usr/local/lib/python3/dist-packages/apc-ups-monitor',  # Local installation
        os.path.join(os.path.expanduser('~'), '.local/lib/python3/site-packages/apc-ups-monitor'),  # User installation
    ]
    
    for path in possible_paths:
        if os.path.exists(os.path.join(path, 'templates')):
            return path
    
    # Fallback to current directory
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def create_app():
    """Create and configure the Flask application."""
    package_path = get_package_path()
    
    app = Flask(__name__,
                template_folder=os.path.join(package_path, 'templates'),
                static_folder=os.path.join(package_path, 'static'))
    
    app.config['SECRET_KEY'] = 'apc-ups-monitor-secret-key-change-in-production'
    
    # Enable CORS for all routes
    CORS(app, origins="*")
    
    # Import and register the UPS monitoring blueprint
    from .apc_ups_monitor import create_ups_blueprint
    app.register_blueprint(create_ups_blueprint())
    
    # Register apcupsd configuration routes
    from .apcupsd_config import ApcupsdConfigManager
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

def main():
    """Main entry point for the UPS Monitor application."""
    parser = argparse.ArgumentParser(description='UPS Monitor Service')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8555, help='Port to bind to (default: 8555)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--db-path', default='/var/lib/apc-ups-monitor/ups_monitoring.db', 
                       help='Database path (default: /var/lib/apc-ups-monitor/ups_monitoring.db)')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Log level (default: INFO)')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Ensure database directory exists
    db_dir = os.path.dirname(args.db_path)
    os.makedirs(db_dir, exist_ok=True)
    
    # Set database path
    os.environ['UPS_MONITOR_DB_PATH'] = args.db_path
    
    # Initialize database
    init_database(args.db_path)
    
    # Create Flask app
    app = create_app()
    
    # Setup SocketIO
    logger.info("Setting up SocketIO...")
    socketio = setup_socketio(app)
    logger.info("SocketIO setup complete")
    
    # Initialize UPS monitor
    from . import apc_ups_monitor as ups_module
    if ups_module.apc_ups_monitor is None:
        ups_module.apc_ups_monitor = UPSMonitor(db_path=args.db_path)
    apc_ups_monitor = ups_module.apc_ups_monitor
    
    # Start monitoring
    apc_ups_monitor.start_monitoring()
    
    # Store monitor instance in app for cleanup
    app.apc_ups_monitor = apc_ups_monitor
    
    try:
        logger.info(f"Starting UPS Monitor on http://{args.host}:{args.port}")
        logger.info(f"Database: {args.db_path}")
        logger.info("Available endpoints:")
        logger.info("  - /                      - Main dashboard")
        logger.info("  - /api/health            - Health check")
        logger.info("  - /api/current           - Current UPS data")
        logger.info("  - /api/history           - Historical data")
        logger.info("  - /api/events            - System events")
        logger.info("  - /api/battery-events    - Battery events")
        logger.info("  - /api/battery-stats     - Battery statistics")
        
        # Run the application with websocket compatibility settings
        # SocketIO handles the server setup internally
        socketio.run(app, host=args.host, port=args.port, debug=args.debug, 
                    use_reloader=False, log_output=True,
                    # This service intentionally uses Werkzeug's threaded server.
                    # Flask-SocketIO 5.5+ requires explicit acknowledgement.
                    allow_unsafe_werkzeug=True)
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error running application: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if hasattr(app, 'apc_ups_monitor'):
            app.apc_ups_monitor.stop_monitoring()
        logger.info("UPS Monitor stopped")

if __name__ == '__main__':
    main()
