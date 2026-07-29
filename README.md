# APC UPS Monitor

An APC UPS monitoring system with a real-time web interface, historical data,
and alerting. It communicates with APC hardware through `apcupsd` and is not
intended as a generic multi-vendor UPS platform.

Maintained by [Sayeed Afridi](https://github.com/sayeed99).
Support: `sayeed.afridi2009@gmail.comm`

## Features

- **Real-time Monitoring**: Live UPS status updates via WebSocket
- **Historical Data**: Detailed charts and graphs of UPS performance over time
- **Battery Analytics**: Track battery performance, drain rates, and events
- **Event Logging**: Comprehensive logging of UPS events and alerts
- **Web Interface**: Modern, responsive web dashboard with native HTML/JS
- **REST API**: Full REST API for integration with other systems
- **Systemd Integration**: Proper Linux service with automatic startup
- **Debian Package**: Easy installation via DEB package

## Requirements

- Linux system (tested on Ubuntu/Debian)
- Python 3.8+
- `apcupsd` package for UPS communication
- systemd for service management

## Installation

### Install the latest GitHub release (recommended)

On Debian or Ubuntu:

```bash
curl -fL \
  https://github.com/sayeed99/apc-ups-monitor/releases/latest/download/apc-ups-monitor_latest_all.deb \
  -o /tmp/apc-ups-monitor.deb
sudo apt install /tmp/apc-ups-monitor.deb
```

The package enables and starts `apc-ups-monitor`. Open:

```text
http://localhost:8555
```

Verify the installation:

```bash
systemctl status apc-ups-monitor --no-pager
apcaccess status
```

The monitor requires `apcupsd` and an APC UPS supported by `apcupsd`. Use the
Configuration tab to select the detected APC USB or serial connection when
automatic detection does not match the active device.

### Build the Debian package from source

1. Build the package:
   ```bash
   cd apc-ups-monitor
   ./scripts/build-deb.sh
   ```

2. Install the package:
   ```bash
   sudo dpkg -i build/apc-ups-monitor_*.deb
   sudo apt-get install -f  # Fix any dependency issues
   ```

### Local development installation

1. Clone and install locally:
   ```bash
   cd apc-ups-monitor
   ./scripts/install-local.sh
   ```

### Configuration management permissions

Installing the `.deb` automatically configures secure, limited permissions for:
- Installing apcupsd packages
- Managing apcupsd configuration files
- Controlling apcupsd service

No separate permission setup or login/logout is required. Source installations can
use `sudo ./scripts/setup-sudo-permissions.sh` as a repair/setup tool.

### Complete removal

To completely remove all traces of APC UPS Monitor:

```bash
cd apc-ups-monitor
sudo ./scripts/cleanup.sh
```

This will remove:
- Package and service
- Configuration files  
- Log files
- User accounts and groups
- Sudo permissions
- Build artifacts
- Optionally: database files (with confirmation)

## Usage

### Starting the Service

The service starts automatically after installation. You can also control it manually:

```bash
# Start the service
sudo systemctl start apc-ups-monitor

# Stop the service
sudo systemctl stop apc-ups-monitor

# Restart the service
sudo systemctl restart apc-ups-monitor

# Check status
sudo systemctl status apc-ups-monitor

# View logs
sudo journalctl -u apc-ups-monitor -f
```

### Web Interface

Access the web interface at: `http://localhost:8555`

The interface provides:
- **Overview**: Current UPS status and key metrics
- **Charts**: Historical data visualization
- **Battery**: Battery performance and events
- **Events**: System events and alerts
- **System**: UPS information and configuration

### Command Line Options

```bash
apc-ups-monitor --help
apc-ups-monitor --host=0.0.0.0 --port=8555 --db-path=/var/lib/apc-ups-monitor/ups_monitoring.db
```

Options:
- `--host`: Host to bind to (default: 0.0.0.0)
- `--port`: Port to bind to (default: 8555)
- `--debug`: Enable debug mode
- `--db-path`: Database file path
- `--log-level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

## API Endpoints

### REST API

- `GET /api/health` - Health check
- `GET /api/current` - Current UPS data
- `GET /api/history?hours=24&limit=1000` - Historical data
- `GET /api/events?limit=100` - System events
- `GET /api/battery-events?limit=50&days=30` - Battery events
- `GET /api/battery-stats?days=30` - Battery statistics
- `POST /api/cleanup-duplicates` - Clean up duplicate events
- `POST /api/clear-cache` - Clear server cache

### WebSocket Events

- `ups_data` - Real-time UPS status updates
- `new_events` - New system events
- `request_refresh` - Request manual data refresh

## Configuration

Configuration file: `/etc/apc-ups-monitor/config.conf`

```ini
[DEFAULT]
host = 0.0.0.0
port = 8555
debug = false
log_level = INFO
db_path = /var/lib/apc-ups-monitor/ups_monitoring.db

[database]
pool_size = 5
cache_timeout = 30
monitor_interval = 5
batch_size = 100

[monitoring]
use_mock_data = false
apcaccess_timeout = 5
websocket_emit_interval = 2
```

## File Locations

- **Service**: `/etc/systemd/system/apc-ups-monitor.service`
- **Configuration**: `/etc/apc-ups-monitor/config.conf`
- **Database**: `/var/lib/apc-ups-monitor/ups_monitoring.db`
- **Logs**: `/var/log/apc-ups-monitor/` and `journalctl -u apc-ups-monitor`
- **Web files**: Embedded in the Python package
- **User**: `apc-ups-monitor` (created automatically)

## Database Schema

The system uses SQLite with the following tables:
- `ups_history` - Historical UPS data points
- `ups_events` - System events and alerts
- `battery_drain_events` - Battery performance events
- `system_stats` - System statistics

## Security

The service runs as a non-root user (`apc-ups-monitor`) with restricted permissions:
- No new privileges
- Private /tmp and /dev
- Protected system directories
- Restricted system calls
- Memory execution protection

## Monitoring and Alerting

The system monitors:
- UPS status changes (ONLINE/ONBATT/OFFLINE)
- Battery charge levels (warnings at 30%, critical at 20%)
- Load percentage (warnings at 80%, critical at 90%)
- Temperature (warnings at 35°C)
- Battery drain events and rates

## Testing

### Method 1: Quick Development Test (Recommended)

1. **Setup and run in development mode**:
   ```bash
   cd apc-ups-monitor
   
   # Activate virtual environment (already created)
   source test_env/bin/activate
   
   # Run in development mode
   python dev-run.py
   ```

2. **Access the web interface**:
   - Open browser to `http://localhost:8556`
   - The interface will automatically use mock data if no UPS is connected

3. **Test all features**:
   - **Overview Tab**: Check battery status, power info, and system details
   - **Charts Tab**: Verify all 4 charts load with historical data
   - **Battery Tab**: Review battery performance stats and events
   - **Events Tab**: Check system events and alerts
   - **System Tab**: Verify detailed UPS information and configuration

### Method 2: API Testing

1. **Test API endpoints**:
   ```bash
   source test_env/bin/activate
   python test-api.py
   ```

2. **Manual API testing**:
   ```bash
   # Test health endpoint
   curl http://localhost:8556/api/health
   
   # Test current data
   curl http://localhost:8556/api/current
   
   # Test historical data
   curl http://localhost:8556/api/history?hours=1&limit=10
   
   # Test events
   curl http://localhost:8556/api/events?limit=5
   
   # Test battery events
   curl http://localhost:8556/api/battery-events?limit=5
   
   # Test battery stats
   curl http://localhost:8556/api/battery-stats
   ```

### Method 3: WebSocket Testing

1. **Open browser console** at `http://localhost:8556`
2. **Test WebSocket connection**:
   ```javascript
   // Listen for real-time data
   const socket = io();
   
   socket.on('ups_data', (data) => {
       console.log('UPS Data:', data);
   });
   
   socket.on('new_events', (events) => {
       console.log('New Events:', events);
   });
   
   // Request manual refresh
   socket.emit('request_refresh');
   ```

### Method 4: Production Installation Test

1. **Build and install package**:
   ```bash
   # Build debian package
   ./scripts/build-deb.sh
   
   # Install package
   sudo dpkg -i build/apc-ups-monitor_*.deb
   sudo apt-get install -f
   ```

2. **Test service**:
   ```bash
   # Check service status
   sudo systemctl status apc-ups-monitor
   
   # View logs
   sudo journalctl -u apc-ups-monitor -f
   
   # Access web interface
   curl http://localhost:8555/api/health
   ```

### Method 5: Full System Test

1. **Test with real UPS** (if available):
   ```bash
   # Check apcupsd status
   sudo systemctl status apcupsd
   
   # Test apcaccess command
   apcaccess status
   
   # Run UPS monitor
   python dev-run.py
   ```

2. **Verify real UPS data**:
   - Check that `using_mock_data` is `false` in API responses
   - Verify actual UPS model and serial number appear
   - Test real-time updates when UPS status changes

### Expected Test Results

#### ✅ **Web Interface Tests**
- [ ] Dashboard loads without errors
- [ ] All tabs are functional (Overview, Charts, Battery, Events, System)
- [ ] Status bar shows connection status and key metrics
- [ ] Settings modal opens and saves configuration
- [ ] Charts display data with proper styling
- [ ] Battery analytics show statistics and events
- [ ] Events display with proper icons and formatting
- [ ] System tab shows detailed UPS information

#### ✅ **API Tests**
- [ ] `/api/health` returns service information
- [ ] `/api/current` returns UPS status data
- [ ] `/api/history` returns time-series data
- [ ] `/api/events` returns system events
- [ ] `/api/battery-events` returns battery events
- [ ] `/api/battery-stats` returns battery statistics

#### ✅ **WebSocket Tests**
- [ ] Connection establishes successfully
- [ ] Real-time data updates every 2 seconds
- [ ] Events are pushed to connected clients
- [ ] Manual refresh requests work

#### ✅ **Service Tests**
- [ ] Service starts without errors
- [ ] Service runs as `apc-ups-monitor` user
- [ ] Database is created and populated
- [ ] Logs are written to journal
- [ ] Service restarts automatically on failure

### Test Data Validation

**Mock Data Mode** (when no UPS connected):
- Status randomly cycles between ONLINE/ONBATT
- Battery charge varies between 5-100%
- Load percentage varies between 0-30%
- Temperature varies between 22-28°C
- Voltage values are realistic (220-240V)

**Real UPS Mode** (when UPS connected):
- Status reflects actual UPS state
- All values match `apcaccess status` output
- Historical data is logged to database
- Events are generated on status changes

## Troubleshooting

### Common Issues

1. **Service won't start**:
   ```bash
   sudo journalctl -u apc-ups-monitor -f
   sudo systemctl status apc-ups-monitor
   ```

2. **No UPS data**:
   - Check if `apcupsd` is running: `sudo systemctl status apcupsd`
   - Test apcaccess: `apcaccess status`
   - Check UPS connection

3. **Permission errors**:
   - Ensure directories exist and have correct ownership
   - Check service user permissions

4. **Database issues**:
   - Check database file permissions
   - Verify disk space in `/var/lib/apc-ups-monitor`

5. **Web interface not loading**:
   - Check if service is running on correct port
   - Verify firewall settings
   - Check browser console for JavaScript errors

6. **Charts not displaying**:
   - Reinstall the package if any local web assets are missing
   - Check browser console for errors
   - Verify historical data is available

### Mock Data Mode

For testing without a UPS, the system can use mock data:
- Automatic fallback if `apcaccess` fails
- Simulates realistic UPS behavior
- Useful for development and testing

## Development

The dashboard ships its complete browser runtime locally, including Tailwind,
Chart.js, the date adapter, Lucide icons, Socket.IO, and Geist fonts. It does
not require Internet access after installation. Third-party notices are kept
in `static/vendor/THIRD_PARTY_NOTICES.md`.

### Project Structure

```
apc-ups-monitor/
├── src/
│   ├── main.py              # Application entry point
│   ├── apc_ups_monitor.py       # Core monitoring logic
│   └── __init__.py
├── templates/
│   └── index.html           # Web interface
├── static/
│   └── app.js              # Frontend JavaScript
├── systemd/
│   └── apc-ups-monitor.service  # Systemd service file
├── debian/                  # Debian package files
├── scripts/                 # Build and install scripts
├── setup.py                 # Python package setup
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

### Building from Source

1. Install build dependencies:
   ```bash
   sudo apt-get install build-essential debhelper python3-setuptools python3-all dh-python
   ```

2. Build the package:
   ```bash
   dpkg-buildpackage -us -uc -b
   ```

## License

This is free and open-source software released under the
[MIT License](LICENSE). You may use, copy, modify, distribute, sublicense, and
sell copies of the software. The original copyright and license notice naming
Sayeed Afridi must remain in all copies or substantial portions.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues and questions:
- Check the logs: `sudo journalctl -u apc-ups-monitor -f`
- Review the troubleshooting section
- Open an issue on GitHub
