# UPS Monitor - Development Guide

## Development Setup

### 1. Quick Development Test

```bash
# Activate the test environment
source test_env/bin/activate

# Run in development mode
python dev-run.py
```

This will:
- Create a local `dev_data/` directory for the database
- Run the application on `http://localhost:5001`
- Enable debug mode with auto-reload
- Use mock data if no UPS is connected

### 2. Manual Development Run

```bash
# Activate environment
source test_env/bin/activate

# Run with custom options
python src/main.py \
    --debug \
    --port=5001 \
    --db-path=./dev_ups_monitoring.db \
    --log-level=DEBUG
```

## Testing

### 1. API Testing

```bash
# Test all API endpoints
python test-api.py

# Test specific URL
python test-api.py http://localhost:5001
```

### 2. Manual Testing

1. **Start the development server**:
   ```bash
   python dev-run.py
   ```

2. **Access the web interface**:
   - Open `http://localhost:5001` in your browser
   - Check all tabs: Overview, Charts, Battery, Events, System

3. **Test API endpoints**:
   - Health: `http://localhost:5001/api/health`
   - Current data: `http://localhost:5001/api/current`
   - History: `http://localhost:5001/api/history?hours=1`

### 3. WebSocket Testing

Open browser console at `http://localhost:5001` and run:

```javascript
// Connect to WebSocket
const socket = io();

// Listen for data
socket.on('ups_data', (data) => {
    console.log('UPS Data:', data);
});

// Request refresh
socket.emit('request_refresh');
```

## Development Commands

### Environment Setup
```bash
# Create virtual environment
python3 -m venv test_env
source test_env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install additional development tools
pip install requests  # For API testing
```

### Running Different Modes

```bash
# Development mode with debug
python dev-run.py

# Production-like mode
python src/main.py --port=5001 --db-path=./dev_data/ups_monitoring.db

# With mock data (if no UPS)
# Mock data is automatically enabled if apcaccess fails

# With custom log level
python src/main.py --log-level=DEBUG --port=5001 --db-path=./dev_data/ups_monitoring.db
```

## File Structure for Development

```
apc-ups-monitor/
├── dev-run.py              # Development runner
├── test-api.py             # API testing script
├── dev_data/               # Development database (created automatically)
│   └── ups_monitoring.db
├── test_env/               # Virtual environment
├── src/                    # Source code
│   ├── main.py            # Application entry point
│   └── apc_ups_monitor.py     # Core monitoring logic
├── templates/             # HTML templates
│   └── index.html
├── static/               # Static files
│   └── app.js
└── requirements.txt      # Dependencies
```

## Development Features

### Mock Data Mode
- Automatically enabled if `apcaccess` command fails
- Simulates realistic UPS behavior
- Generates varying battery, load, and voltage data
- Includes status changes and events

### Debug Mode Features
- Auto-reload on file changes
- Detailed error messages
- Extended logging
- Flask debug toolbar (if installed)

### Database Development
- SQLite database in `dev_data/` directory
- Automatic schema creation
- Sample data generation through mock mode
- Easy to reset: delete `dev_data/` directory

## Common Development Tasks

### 1. Testing Frontend Changes
1. Edit `templates/index.html` or `static/app.js`
2. Reload browser (auto-reload enabled in debug mode)
3. Check browser console for errors

### 2. Testing Backend Changes
1. Edit `src/main.py` or `src/apc_ups_monitor.py`
2. Server auto-restarts in debug mode
3. Check terminal for error messages

### 3. Database Testing
```bash
# View database content
sqlite3 dev_data/ups_monitoring.db

# Common queries
.tables
SELECT * FROM ups_history ORDER BY timestamp DESC LIMIT 10;
SELECT * FROM ups_events ORDER BY timestamp DESC LIMIT 5;
SELECT * FROM battery_drain_events ORDER BY start_timestamp DESC LIMIT 5;
```

### 4. API Development
```bash
# Test specific endpoints
curl http://localhost:5001/api/health
curl http://localhost:5001/api/current
curl http://localhost:5001/api/history?hours=1&limit=10
```

## Troubleshooting

### Common Issues

1. **Port already in use**:
   ```bash
   # Kill process on port 5001
   sudo lsof -ti:5001 | xargs sudo kill -9
   ```

2. **Database permission errors**:
   ```bash
   # Use local database path
   python src/main.py --db-path=./dev_data/ups_monitoring.db
   ```

3. **Module import errors**:
   ```bash
   # Ensure virtual environment is active
   source test_env/bin/activate
   
   # Check Python path
   python -c "import sys; print(sys.path)"
   ```

4. **No UPS data**:
   - Mock data is automatically used if `apcaccess` fails
   - Check logs for "Generated mock UPS data for testing"

### Development Logs
```bash
# View detailed logs
python dev-run.py 2>&1 | tee dev.log

# Filter specific log levels
python dev-run.py 2>&1 | grep -E "(ERROR|WARNING|INFO)"
```

## Building and Testing Package

### 1. Test Package Creation
```bash
# Build development package
python setup.py sdist bdist_wheel

# Install in development mode
pip install -e .
```

### 2. Test Debian Package
```bash
# Build package
./scripts/build-deb.sh

# Test installation (requires sudo)
sudo dpkg -i build/apc-ups-monitor_*.deb
```

### 3. Test Local Installation
```bash
# Full local installation test
./scripts/install-local.sh
```

## Performance Testing

### Load Testing
```bash
# Install testing tools
pip install locust

# Create basic load test
cat > locustfile.py << 'EOF'
from locust import HttpUser, task, between

class UPSMonitorUser(HttpUser):
    wait_time = between(1, 5)
    
    @task(3)
    def current_data(self):
        self.client.get("/api/current")
    
    @task(2)
    def history_data(self):
        self.client.get("/api/history?hours=1&limit=100")
    
    @task(1)
    def events_data(self):
        self.client.get("/api/events?limit=50")
EOF

# Run load test
locust -H http://localhost:5001
```

### Memory and CPU Monitoring
```bash
# Monitor during development
python dev-run.py &
PID=$!

# Monitor resources
while kill -0 $PID 2>/dev/null; do
    ps -p $PID -o pid,ppid,cmd,vsz,rss,pcpu,pmem
    sleep 5
done
```

## Code Quality

### Linting and Formatting
```bash
# Install tools
pip install black flake8 mypy

# Format code
black src/

# Check style
flake8 src/

# Type checking
mypy src/
```

This development guide provides everything you need to test and develop the UPS Monitor package!