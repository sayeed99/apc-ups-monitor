#!/usr/bin/env python3
"""
UPS Monitoring Backend - Adapted for Package
"""

import os
import json
import subprocess
import sqlite3
import threading
import time
import math
import re
from datetime import datetime, timedelta, timezone
import pytz
from typing import Dict, Any, List
from flask import Blueprint, jsonify, request
from .apcupsd_config import ApcupsdConfigManager
from flask_socketio import SocketIO, emit, disconnect
from flask_cors import CORS
from contextlib import contextmanager
import functools
import logging
from threading import Lock
import queue
from concurrent.futures import ThreadPoolExecutor

# Global variables
socketio = None
logger = logging.getLogger(__name__)

# Database path from environment or default
DB_FILE = os.environ.get('UPS_MONITOR_DB_PATH', '/var/lib/apc-ups-monitor/ups_monitoring.db')

# Performance optimizations
DB_POOL_SIZE = 5
CACHE_TIMEOUT = 30  # seconds
MONITOR_INTERVAL = 5  # seconds
BATCH_SIZE = 100

# Global cache and locks
cache = {}
cache_lock = Lock()
db_lock = Lock()

# Database connection pool
db_pool = queue.Queue(maxsize=DB_POOL_SIZE)
db_pool_lock = Lock()

# Thread pool for async operations
thread_pool = ThreadPoolExecutor(max_workers=4)

# Timezone setup - Auto-detect or default to IST
def get_local_timezone():
    """Get local timezone, default to IST if detection fails."""
    try:
        # Try to get system timezone
        import time
        import os
        
        # Method 1: Check TZ environment variable
        tz_env = os.environ.get('TZ')
        if tz_env:
            try:
                return pytz.timezone(tz_env)
            except pytz.UnknownTimeZoneError:
                pass
        
        # Method 2: Use system timezone detection
        try:
            import zoneinfo
            local_tz = zoneinfo.ZoneInfo(time.tzname[0])
            return local_tz
        except:
            pass
        
        # Method 3: Default to IST
        return pytz.timezone('Asia/Kolkata')
    except:
        # Fallback to IST
        return pytz.timezone('Asia/Kolkata')

LOCAL_TZ = get_local_timezone()

# Database connection pool management
def init_db_pool(db_path):
    """Initialize database connection pool."""
    global db_pool
    with db_pool_lock:
        # Clear existing connections
        while not db_pool.empty():
            try:
                conn = db_pool.get_nowait()
                conn.close()
            except:
                pass
        
        # Create new connections
        for _ in range(DB_POOL_SIZE):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=10000')
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            db_pool.put(conn)

@contextmanager
def get_db_connection():
    """Context manager for database connections from pool."""
    conn = None
    try:
        conn = db_pool.get(timeout=5)
        yield conn
    except queue.Empty:
        # Fallback to new connection if pool is empty
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        if conn:
            try:
                db_pool.put(conn, block=False)
            except queue.Full:
                conn.close()

# Caching decorators
def cache_result(timeout=CACHE_TIMEOUT):
    """Decorator to cache function results."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            with cache_lock:
                if cache_key in cache:
                    result, timestamp = cache[cache_key]
                    if time.time() - timestamp < timeout:
                        return result
                    else:
                        del cache[cache_key]
            
            result = func(*args, **kwargs)
            
            with cache_lock:
                cache[cache_key] = (result, time.time())
            
            return result
        return wrapper
    return decorator

def clear_cache():
    """Clear expired cache entries."""
    with cache_lock:
        current_time = time.time()
        expired_keys = [key for key, (_, timestamp) in cache.items() 
                       if current_time - timestamp > CACHE_TIMEOUT]
        for key in expired_keys:
            del cache[key]

def get_local_now():
    """Get current datetime in local timezone."""
    return datetime.now(LOCAL_TZ)

def utc_to_local(utc_dt):
    """Convert UTC datetime to local timezone."""
    if isinstance(utc_dt, str):
        utc_dt = datetime.fromisoformat(utc_dt.replace('Z', '+00:00'))
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(LOCAL_TZ)

def init_database(db_path=None):
    """Initialize SQLite database with required tables and optimizations."""
    if db_path is None:
        db_path = DB_FILE
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')  # Enable WAL mode for better concurrency
    conn.execute('PRAGMA synchronous=NORMAL')  # Faster writes
    conn.execute('PRAGMA cache_size=10000')  # Increase cache size
    conn.execute('PRAGMA temp_store=MEMORY')  # Use memory for temp tables
    cursor = conn.cursor()
    
    # UPS data history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ups_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            status TEXT,
            battery_charge INTEGER,
            time_left REAL,
            load_pct INTEGER,
            line_voltage REAL,
            output_voltage REAL,
            battery_voltage REAL,
            temperature REAL,
            frequency REAL,
            hostname TEXT,
            driver TEXT,
            ups_mode TEXT,
            start_time TEXT,
            min_battery_charge_shutdown INTEGER,
            min_time_left_shutdown REAL,
            max_time_on_battery REAL,
            delay_before_wakeup REAL,
            delay_before_shutdown REAL,
            low_battery_timeout REAL,
            required_return_charge REAL,
            alarm_delay REAL,
            time_on_battery REAL,
            cumulative_on_battery REAL,
            transfer_off_battery_reason TEXT,
            self_test_interval INTEGER,
            status_flag TEXT,
            manufacture_date TEXT,
            nominal_output_voltage REAL,
            nominal_battery_voltage REAL,
            external_batteries INTEGER,
            raw_data TEXT
        )
    ''')
    
    # Events/alerts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ups_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            event_type TEXT,
            severity TEXT,
            message TEXT,
            resolved BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # System stats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            total_transfers INTEGER,
            uptime_hours REAL,
            last_test_date TEXT,
            battery_replace_date TEXT
        )
    ''')
    
    # Battery drain events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS battery_drain_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_timestamp DATETIME,
            end_timestamp DATETIME,
            start_battery_percent INTEGER,
            end_battery_percent INTEGER,
            duration_seconds INTEGER,
            drain_rate_percent_per_hour REAL,
            trigger_reason TEXT,
            event_type TEXT,
            resolved BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Create indexes for better query performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ups_history_timestamp ON ups_history(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ups_events_timestamp ON ups_events(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_battery_events_start_timestamp ON battery_drain_events(start_timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ups_history_status ON ups_history(status)')
    
    conn.commit()
    conn.close()
    
    # Initialize database connection pool
    init_db_pool(db_path)

class UPSMonitor:
    """UPS monitoring and data collection class with performance optimizations."""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_FILE
        self.current_data = {}
        self.is_monitoring = False
        self.monitor_thread = None
        self.previous_status = None
        self.use_mock_data = False
        self.battery_event_start = None
        self.last_battery_percent = None
        self.battery_event_active = False
        self.data_lock = Lock()
        self.last_apcaccess_call = 0
        self.apcaccess_cache = None
        self.pending_db_writes = queue.Queue()
        self.db_writer_thread = None
        self.start_db_writer()
    
    def parse_apcaccess_output(self) -> Dict[str, Any]:
        """Parse apcaccess status output with caching and improved error handling."""
        # Use cached result if recent
        current_time = time.time()
        if (self.apcaccess_cache and 
            current_time - self.last_apcaccess_call < 2):  # 2 second cache
            return self.apcaccess_cache
        
        try:
            # Try to run apcaccess command
            result = subprocess.run(['apcaccess', 'status'], 
                                  capture_output=True, text=True, timeout=5)  # Reduced timeout
            
            if result.returncode != 0:
                logger.warning(f"apcaccess failed with return code {result.returncode}")
                logger.warning(f"Error output: {result.stderr}")
                self.use_mock_data = True
                return self.get_mock_data()
            
            output = result.stdout
            
            # Parse the output
            data = self.parse_ups_output(output)
            
            if not data:
                logger.warning("No data parsed from apcaccess output, using mock data")
                self.use_mock_data = True
                return self.get_mock_data()
            
            normalized = self.normalize_data(data)
            
            # Cache the result
            self.apcaccess_cache = normalized
            self.last_apcaccess_call = current_time
            
            return normalized
            
        except FileNotFoundError:
            logger.error("apcaccess command not found. Install apcupsd package. Using mock data.")
            self.use_mock_data = True
            return self.get_mock_data()
        except subprocess.TimeoutExpired:
            logger.error("apcaccess command timed out. Using mock data.")
            self.use_mock_data = True
            return self.get_mock_data()
        except Exception as e:
            logger.error(f"Error running apcaccess: {e}. Using mock data.")
            self.use_mock_data = True
            return self.get_mock_data()
    
    def parse_ups_output(self, output: str) -> Dict[str, str]:
        """Parse the raw apcaccess output into key-value pairs."""
        data = {}
        
        for line in output.strip().split('\n'):
            line = line.strip()
            
            # Skip header, footer and empty lines
            if not line or line.startswith('APC') or line.startswith('END') or line.startswith('DATE'):
                continue
                
            # Look for lines with colons
            if ':' in line:
                try:
                    # Split on first colon only
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        
                        # Only add non-empty keys and values
                        if key and value and value != 'N/A':
                            data[key] = value
                        
                except Exception as e:
                    logger.debug(f"Failed to parse line: '{line}' - {e}")
                    continue
        
        return data
    
    def normalize_data(self, raw_data: Dict[str, str]) -> Dict[str, Any]:
        """Normalize and clean the UPS data with robust parsing."""
        
        def extract_number(value: str, default: float = 0.0) -> float:
            """Extract numeric value from string with units."""
            if not value or value.lower() in ['n/a', 'na', 'none', '']:
                return default
            
            try:
                # Use regex to extract the first number from the string
                match = re.search(r'[-+]?\d*\.?\d+', value.replace(',', ''))
                if match:
                    return float(match.group())
                else:
                    return default
            except (ValueError, TypeError):
                return default
        
        def extract_int(value: str, default: int = 0) -> int:
            """Extract integer value from string."""
            return int(extract_number(value, default))
        
        # Map the data with fallbacks for different key names
        normalized = {
            'status': raw_data.get('STATUS', 'UNKNOWN'),
            'battery_charge': extract_int(raw_data.get('BCHARGE', '0')),
            'time_left': extract_number(raw_data.get('TIMELEFT', '0')),
            'load_pct': extract_int(raw_data.get('LOADPCT', '0')),
            'line_voltage': extract_number(raw_data.get('LINEV', '0')),
            'output_voltage': extract_number(raw_data.get('OUTPUTV', '0')),
            'battery_voltage': extract_number(raw_data.get('BATTV', '0')),
            'temperature': extract_number(raw_data.get('ITEMP', '0')),
            'frequency': extract_number(raw_data.get('LINEFREQ', '0')),
            'last_transfer': raw_data.get('LASTXFER', 'None'),
            'num_transfers': extract_int(raw_data.get('NUMXFERS', '0')),
            'model': raw_data.get('MODEL', 'Unknown'),
            'serial_no': raw_data.get('SERIALNO', 'Unknown'),
            'firmware': raw_data.get('FIRMWARE', 'Unknown'),
            'battery_date': raw_data.get('BATTDATE', 'Unknown'),
            'max_line_v': extract_number(raw_data.get('MAXLINEV', raw_data.get('HITRANS', '0'))),
            'min_line_v': extract_number(raw_data.get('MINLINEV', raw_data.get('LOTRANS', '0'))),
            'self_test': raw_data.get('SELFTEST', 'NO'),
            'ups_name': raw_data.get('UPSNAME', 'UPS'),
            'hostname': raw_data.get('HOSTNAME', 'Unknown'),
            'driver': raw_data.get('DRIVER', 'Unknown'),
            'ups_mode': raw_data.get('UPSMODE', 'Unknown'),
            'start_time': raw_data.get('STARTTIME', 'Unknown'),
            'min_battery_charge_shutdown': extract_int(raw_data.get('MBATTCHG', '0')),
            'min_time_left_shutdown': extract_number(raw_data.get('MINTIMEL', '0')),
            'max_time_on_battery': extract_number(raw_data.get('MAXTIME', '0')),
            'delay_before_wakeup': extract_number(raw_data.get('DWAKE', '0')),
            'delay_before_shutdown': extract_number(raw_data.get('DSHUTD', '0')),
            'low_battery_timeout': extract_number(raw_data.get('DLOWBATT', '0')),
            'required_return_charge': extract_number(raw_data.get('RETPCT', '0')),
            'alarm_delay': extract_number(raw_data.get('ALARMDEL', '0')),
            'time_on_battery': extract_number(raw_data.get('TONBATT', '0')),
            'cumulative_on_battery': extract_number(raw_data.get('CUMONBATT', '0')),
            'transfer_off_battery_reason': raw_data.get('XOFFBATT', 'N/A'),
            'self_test_interval': extract_int(raw_data.get('STESTI', '0')),
            'status_flag': raw_data.get('STATFLAG', '0x00000000'),
            'manufacture_date': raw_data.get('MANDATE', 'Unknown'),
            'nominal_output_voltage': extract_number(raw_data.get('NOMOUTV', '0')),
            'nominal_battery_voltage': extract_number(raw_data.get('NOMBATTV', '0')),
            'external_batteries': extract_int(raw_data.get('EXTBATTS', '0')),
            'timestamp': get_local_now().isoformat(),
            'raw_data': json.dumps(raw_data),
            'using_mock_data': self.use_mock_data
        }
        
        # Validate critical values
        if normalized['battery_charge'] > 100:
            normalized['battery_charge'] = 100
        if normalized['battery_charge'] < 0:
            normalized['battery_charge'] = 0
            
        if normalized['load_pct'] > 100:
            normalized['load_pct'] = 100
        if normalized['load_pct'] < 0:
            normalized['load_pct'] = 0
        
        return normalized
    
    def get_mock_data(self) -> Dict[str, Any]:
        """Generate realistic mock data for testing."""
        import random
        
        # Simulate realistic variations over time
        base_time = time.time()
        battery_base = 85 + 10 * math.sin(base_time / 7200)  # 2-hour cycle
        load_base = 10 + 15 * math.sin(base_time / 1800)     # 30-minute cycle
        voltage_base = 230 + 5 * math.sin(base_time / 3600)  # 1-hour cycle
        
        # Add some randomness
        battery_charge = max(5, min(100, int(battery_base + random.uniform(-5, 5))))
        load_pct = max(0, min(100, int(load_base + random.uniform(-3, 3))))
        line_voltage = max(200, min(250, voltage_base + random.uniform(-2, 2)))
        
        # Determine status based on battery level (simulate realistic behavior)
        if battery_charge < 20:
            status = random.choice(['ONBATT', 'ONBATT', 'ONLINE'])  # More likely on battery when low
        else:
            status = random.choice(['ONLINE', 'ONLINE', 'ONLINE', 'ONLINE', 'ONBATT'])  # Mostly online
        
        raw_mock = {
            'STATUS': status,
            'BCHARGE': f"{battery_charge}.0 Percent",
            'TIMELEFT': f"{random.randint(120 if battery_charge < 50 else 180, 300)}.0 Minutes",
            'LOADPCT': f"{load_pct}.0 Percent",
            'LINEV': f"{line_voltage:.1f} Volts",
            'OUTPUTV': f"{random.uniform(220, 235):.1f} Volts",
            'BATTV': f"{random.uniform(79, 84):.1f} Volts",
            'ITEMP': f"{random.uniform(22, 28):.1f} C",
            'LINEFREQ': f"{random.uniform(49.8, 50.2):.1f} Hz",
            'LASTXFER': random.choice(['Low line voltage', 'High line voltage', 'No transfers', 'Automatic or explicit self test']),
            'NUMXFERS': str(random.randint(0, 15)),
            'MODEL': 'SRV3KL-IN',
            'SERIALNO': '9S2316A00464',
            'FIRMWARE': '441.08CT.I',
            'BATTDATE': '04/18/23',
            'HITRANS': f"{random.uniform(245, 250):.1f} Volts",
            'LOTRANS': f"{random.uniform(180, 190):.1f} Volts",
            'SELFTEST': random.choice(['OK', 'OK', 'OK', 'NO', 'BT']),  # Mostly OK
            'UPSNAME': 'SRVL3KIN'
        }
        
        logger.info("Generated mock UPS data for testing")
        return self.normalize_data(raw_mock)
    
    def start_db_writer(self):
        """Start the database writer thread for async operations."""
        self.db_writer_thread = threading.Thread(target=self._db_writer_loop, daemon=True)
        self.db_writer_thread.start()
    
    def _db_writer_loop(self):
        """Background database writer loop."""
        batch = []
        while True:
            try:
                # Collect batch of writes
                item = self.pending_db_writes.get(timeout=1)
                if item is None:  # Shutdown signal
                    break
                    
                batch.append(item)
                
                # Write batch when full or timeout
                if len(batch) >= BATCH_SIZE:
                    self._write_batch(batch)
                    batch = []
                    
            except queue.Empty:
                # Write remaining items on timeout
                if batch:
                    self._write_batch(batch)
                    batch = []
                    
            except Exception as e:
                logger.error(f"Error in database writer loop: {e}")
    
    def _write_batch(self, batch):
        """Write batch of database operations."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                for item in batch:
                    if item['type'] == 'ups_history':
                        self._write_ups_history(cursor, item['data'])
                    elif item['type'] == 'ups_events':
                        self._write_ups_events(cursor, item['data'])
                    elif item['type'] == 'battery_event':
                        self._write_battery_event(cursor, item['data'])
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error writing batch to database: {e}")
    
    def _write_ups_history(self, cursor, data):
        """Write UPS history data to database."""
        cursor.execute('''
            INSERT INTO ups_history (
                timestamp, status, battery_charge, time_left, load_pct, line_voltage,
                output_voltage, battery_voltage, temperature, frequency, hostname, driver,
                ups_mode, start_time, min_battery_charge_shutdown, min_time_left_shutdown,
                max_time_on_battery, delay_before_wakeup, delay_before_shutdown, low_battery_timeout,
                required_return_charge, alarm_delay, time_on_battery, cumulative_on_battery,
                transfer_off_battery_reason, self_test_interval, status_flag, manufacture_date,
                nominal_output_voltage, nominal_battery_voltage, external_batteries, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            get_local_now().isoformat(),
            data['status'], data['battery_charge'], data['time_left'],
            data['load_pct'], data['line_voltage'], data['output_voltage'],
            data['battery_voltage'], data['temperature'], data['frequency'],
            data['hostname'], data['driver'], data['ups_mode'], data['start_time'],
            data['min_battery_charge_shutdown'], data['min_time_left_shutdown'],
            data['max_time_on_battery'], data['delay_before_wakeup'], data['delay_before_shutdown'],
            data['low_battery_timeout'], data['required_return_charge'], data['alarm_delay'],
            data['time_on_battery'], data['cumulative_on_battery'], data['transfer_off_battery_reason'],
            data['self_test_interval'], data['status_flag'], data['manufacture_date'],
            data['nominal_output_voltage'], data['nominal_battery_voltage'], data['external_batteries'],
            data['raw_data']
        ))
    
    def _write_ups_events(self, cursor, events):
        """Write UPS events to database with duplicate prevention."""
        current_time = get_local_now().isoformat()
        
        for event in events:
            # Check for duplicates within a 5-second window
            cursor.execute('''
                SELECT COUNT(*) FROM ups_events 
                WHERE ABS(julianday(timestamp) - julianday(?)) < (5.0 / 86400)
                AND event_type = ? AND message = ?
            ''', (current_time, event['event_type'], event['message']))
            
            if cursor.fetchone()[0] > 0:
                logger.debug(f"Duplicate event detected within 5-second window, skipping: {event['event_type']} - {event['message']}")
                continue
                
            cursor.execute('''
                INSERT INTO ups_events (timestamp, event_type, severity, message)
                VALUES (?, ?, ?, ?)
            ''', (current_time, event['event_type'], event['severity'], event['message']))
    
    def _write_battery_event(self, cursor, event_data):
        """Write battery event to database with duplicate prevention."""
        # Check for duplicates within a 5-second window to handle slight timing differences
        start_time = datetime.fromisoformat(event_data[0])
        end_time = datetime.fromisoformat(event_data[1])
        
        cursor.execute('''
            SELECT COUNT(*) FROM battery_drain_events 
            WHERE ABS(julianday(start_timestamp) - julianday(?)) < (5.0 / 86400)
            AND ABS(julianday(end_timestamp) - julianday(?)) < (5.0 / 86400)
            AND start_battery_percent = ? AND end_battery_percent = ?
        ''', (start_time.isoformat(), end_time.isoformat(), event_data[2], event_data[3]))
        
        if cursor.fetchone()[0] > 0:
            logger.debug(f"Duplicate battery event detected within 5-second window, skipping: {event_data[2]}% -> {event_data[3]}%")
            return
        
        cursor.execute('''
            INSERT INTO battery_drain_events (
                start_timestamp, end_timestamp, start_battery_percent, end_battery_percent,
                duration_seconds, drain_rate_percent_per_hour, trigger_reason, event_type, resolved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', event_data)
    
    def log_data_to_db(self, data: Dict[str, Any]):
        """Queue UPS data for async database storage."""
        try:
            self.pending_db_writes.put({
                'type': 'ups_history',
                'data': data
            }, block=False)
        except queue.Full:
            logger.warning("Database write queue is full, dropping data")
    
    def check_alerts(self, data: Dict[str, Any]):
        """Check for alert conditions and log events only on state changes."""
        alerts = []
        current_status = data['status']
        
        # Only log status-based alerts on status changes
        if self.previous_status and self.previous_status != current_status:
            # Handle power-related status changes with appropriate severity
            current_time = get_local_now().isoformat()
            
            if self.previous_status == 'ONLINE' and current_status == 'ONBATT':
                # Power lost - CRITICAL only
                alerts.append({
                    'event_type': 'ON_BATTERY',
                    'severity': 'CRITICAL',
                    'message': "UPS is running on battery power - power outage detected",
                    'timestamp': current_time
                })
            elif self.previous_status == 'ONBATT' and current_status == 'ONLINE':
                # Power restored - INFO only
                alerts.append({
                    'event_type': 'STATUS_CHANGE',
                    'severity': 'INFO',
                    'message': "UPS power restored - now running on utility power",
                    'timestamp': current_time
                })
            elif current_status == 'OFFLINE':
                # UPS offline - CRITICAL
                alerts.append({
                    'event_type': 'UPS_OFFLINE',
                    'severity': 'CRITICAL',
                    'message': "UPS is offline",
                    'timestamp': current_time
                })
            else:
                # Other status changes - INFO
                alerts.append({
                    'event_type': 'STATUS_CHANGE',
                    'severity': 'INFO',
                    'message': f"UPS status changed from {self.previous_status} to {current_status}",
                    'timestamp': current_time
                })
            
            # Track battery drain events only on actual status transitions
            logger.info(f"Status transition detected: {self.previous_status} -> {current_status}")
            self.track_battery_events(data, self.previous_status)
        
        # Battery alerts - only on significant changes
        if self.last_battery_percent is None:
            self.last_battery_percent = data['battery_charge']
        
        battery_charge = data['battery_charge']
        if self.last_battery_percent is not None:
            # Only alert on crossing thresholds
            if self.last_battery_percent >= 30 and battery_charge < 30:
                alerts.append({
                    'event_type': 'BATTERY_LOW',
                    'severity': 'WARNING',
                    'message': f"Battery charge low: {battery_charge}%",
                    'timestamp': get_local_now().isoformat()
                })
            elif self.last_battery_percent >= 20 and battery_charge < 20:
                alerts.append({
                    'event_type': 'BATTERY_LOW',
                    'severity': 'CRITICAL',
                    'message': f"Battery charge critically low: {battery_charge}%",
                    'timestamp': get_local_now().isoformat()
                })
        
        # Load alerts - only on crossing thresholds
        if not hasattr(self, 'last_load_pct') or self.last_load_pct is None:
            self.last_load_pct = data['load_pct']
        
        load_pct = data['load_pct']
        if self.last_load_pct is not None:
            if self.last_load_pct < 80 and load_pct >= 80:
                alerts.append({
                    'event_type': 'HIGH_LOAD',
                    'severity': 'WARNING',
                    'message': f"UPS load high: {load_pct}%",
                    'timestamp': get_local_now().isoformat()
                })
            elif self.last_load_pct < 90 and load_pct >= 90:
                alerts.append({
                    'event_type': 'HIGH_LOAD',
                    'severity': 'CRITICAL',
                    'message': f"UPS load critically high: {load_pct}%",
                    'timestamp': get_local_now().isoformat()
                })
        
        # Temperature alerts - only on crossing thresholds
        if not hasattr(self, 'last_temperature') or self.last_temperature is None:
            self.last_temperature = data['temperature']
        
        temperature = data['temperature']
        if self.last_temperature is not None:
            if self.last_temperature <= 35 and temperature > 35:
                alerts.append({
                    'event_type': 'HIGH_TEMP',
                    'severity': 'WARNING',
                    'message': f"UPS temperature high: {temperature}°C",
                    'timestamp': get_local_now().isoformat()
                })
        
        # Queue alerts for async database storage and emit to WebSocket
        if alerts:
            try:
                self.pending_db_writes.put({
                    'type': 'ups_events',
                    'data': alerts
                }, block=False)
                
                # Emit new events to WebSocket clients immediately
                if socketio:
                    try:
                        socketio.emit('new_events', alerts)
                        logger.info(f"Emitted {len(alerts)} new events via WebSocket: {[alert['event_type'] for alert in alerts]}")
                    except Exception as e:
                        logger.error(f"Error emitting new events via WebSocket: {e}")
                
            except queue.Full:
                logger.warning("Database write queue is full, dropping alerts")
        
        # Update previous states
        self.previous_status = current_status
        self.last_battery_percent = battery_charge
        self.last_load_pct = load_pct
        self.last_temperature = temperature
        
        return alerts
    
    def monitor_loop(self):
        """Main monitoring loop with performance optimizations."""
        last_websocket_emit = 0
        websocket_emit_interval = 2  # Emit every 2 seconds instead of every 5
        last_keepalive = 0
        keepalive_interval = 30  # Send keepalive every 30 seconds
        
        while self.is_monitoring:
            try:
                # Get current UPS data
                self.current_data = self.parse_apcaccess_output()
                
                # Log to database asynchronously
                self.log_data_to_db(self.current_data)
                
                # Check for alerts
                alerts = self.check_alerts(self.current_data)
                
                # Emit real-time data via WebSocket less frequently
                current_time = time.time()
                if current_time - last_websocket_emit >= websocket_emit_interval:
                    if socketio:
                        try:
                            # Emit to all connected clients
                            socketio.emit('ups_data', {
                                'data': self.current_data,
                                'alerts': alerts
                            })
                            
                            # Count connected clients safely
                            try:
                                rooms = socketio.server.manager.rooms.get('/', {})
                                client_count = len(rooms)
                                logger.info(f"WebSocket data emitted to {client_count} connected clients")
                            except Exception as count_error:
                                logger.debug(f"Could not count clients: {count_error}")
                                
                        except Exception as e:
                            logger.error(f"Error emitting WebSocket data: {e}")
                    else:
                        logger.warning("SocketIO instance not available for data emission")
                    last_websocket_emit = current_time
                
                # Send WebSocket keepalive ping periodically
                if current_time - last_keepalive >= keepalive_interval:
                    if socketio:
                        try:
                            socketio.emit('keepalive', {'timestamp': current_time})
                            logger.debug("WebSocket keepalive sent")
                        except Exception as e:
                            logger.error(f"Error sending keepalive: {e}")
                    last_keepalive = current_time
                
                # Reduced logging frequency for performance
                if current_time % 30 < MONITOR_INTERVAL:  # Log every 30 seconds
                    logger.info(f"Monitor update: Status={self.current_data.get('status')}, Battery={self.current_data.get('battery_charge')}%, Load={self.current_data.get('load_pct')}%")
                
                # Clear expired cache entries periodically
                if current_time % 60 < MONITOR_INTERVAL:  # Every minute
                    clear_cache()
                
                # Wait before next reading
                time.sleep(MONITOR_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(10)
    
    def start_monitoring(self):
        """Start the monitoring thread."""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            logger.info("UPS monitoring started")
    
    def track_battery_events(self, current_data, previous_status):
        """Track battery drain events when UPS switches to/from battery power."""
        current_status = current_data['status']
        current_time = get_local_now()
        
        try:
            # UPS switched to battery power
            if previous_status == 'ONLINE' and current_status == 'ONBATT':
                # Only start tracking if we don't have an active event
                if not self.battery_event_active:
                    logger.info(f"Battery event started: {current_data['battery_charge']}% at {current_time}")
                    self.battery_event_start = {
                        'start_timestamp': current_time,
                        'start_battery_percent': current_data['battery_charge'],
                        'trigger_reason': current_data.get('last_transfer', 'Power outage')
                    }
                    self.battery_event_active = True
                else:
                    logger.debug(f"Battery event already active, skipping duplicate start event")
                
            # UPS switched back to online power
            elif previous_status == 'ONBATT' and current_status == 'ONLINE':
                if self.battery_event_start and self.battery_event_active:
                    end_time = current_time
                    duration_seconds = int((end_time - self.battery_event_start['start_timestamp']).total_seconds())
                    
                    start_percent = self.battery_event_start['start_battery_percent']
                    end_percent = current_data['battery_charge']
                    
                    # Only log if the duration is meaningful (> 10 seconds)
                    if duration_seconds > 10:
                        # Calculate drain rate (percent per hour)
                        percent_drained = start_percent - end_percent
                        drain_rate = 0
                        if duration_seconds > 0:
                            drain_rate = (percent_drained / duration_seconds) * 3600  # per hour
                        
                        logger.info(f"Battery event ended: {end_percent}% at {end_time}")
                        logger.info(f"Duration: {duration_seconds}s, Drained: {percent_drained}%, Rate: {drain_rate:.2f}%/hour")
                        
                        # Log battery drain event
                        self.log_battery_event(
                            self.battery_event_start['start_timestamp'],
                            end_time,
                            start_percent,
                            end_percent,
                            duration_seconds,
                            drain_rate,
                            self.battery_event_start['trigger_reason'],
                            'BATTERY_DRAIN'
                        )
                    else:
                        logger.debug(f"Battery event too short ({duration_seconds}s), not logging")
                    
                    # Reset tracking state
                    self.battery_event_active = False
                    self.battery_event_start = None
                else:
                    logger.debug(f"No active battery event to end, skipping")
                    
        except Exception as e:
            logger.error(f"Error tracking battery events: {e}")
    
    def log_battery_event(self, start_time, end_time, start_percent, end_percent, duration, drain_rate, trigger_reason, event_type):
        """Log battery drain event to database asynchronously."""
        try:
            event_data = (
                start_time.isoformat(),
                end_time.isoformat(),
                start_percent,
                end_percent,
                duration,
                drain_rate,
                trigger_reason,
                event_type,
                True
            )
            
            # Queue for async database write
            self.pending_db_writes.put({
                'type': 'battery_event',
                'data': event_data
            }, block=False)
            
            logger.info(f"Battery event queued: {start_percent}% -> {end_percent}% over {duration}s")
            
        except queue.Full:
            logger.warning("Database write queue is full, dropping battery event")
        except Exception as e:
            logger.error(f"Error logging battery event: {e}")
    
    def stop_monitoring(self):
        """Stop the monitoring thread."""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        logger.info("UPS monitoring stopped")
        # Signal database writer to stop
        self.pending_db_writes.put(None)

# Global monitor instance
apc_ups_monitor = None

def create_ups_blueprint():
    """Create the UPS monitoring blueprint."""
    global apc_ups_monitor
    
    # Initialize the global monitor instance if not already done
    if apc_ups_monitor is None:
        apc_ups_monitor = UPSMonitor()
    
    bp = Blueprint('apc_ups_monitor', __name__, url_prefix='/api')
    
    # Enable CORS for all routes
    CORS(bp, origins="*", 
         allow_headers=["Content-Type", "Authorization", "ngrok-skip-browser-warning"],
         expose_headers=["ngrok-skip-browser-warning"])
    
    @bp.after_request
    def after_request(response):
        response.headers.add('ngrok-skip-browser-warning', 'true')
        return response
    
    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint for connection testing."""
        return jsonify({
            'status': 'healthy',
            'timestamp': get_local_now().isoformat(),
            'service': 'ups-monitoring-backend',
            'version': '1.17.0'
        })
    
    @bp.route('/current', methods=['GET'])
    @cache_result(timeout=5)  # Cache for 5 seconds
    def get_current_data():
        """Get current UPS data."""
        return jsonify(apc_ups_monitor.current_data if apc_ups_monitor else {})
    
    @bp.route('/history', methods=['GET'])
    @cache_result(timeout=15)  # Cache for 15 seconds
    def get_history():
        """Get historical UPS data with minimum 15 minutes."""
        hours = request.args.get('hours', 24, type=float)
        limit = request.args.get('limit', 1000, type=int)
        
        # Ensure minimum 15 minutes (0.25 hours)
        if hours < 0.25:
            hours = 0.25
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get data from last N hours
                since = get_local_now() - timedelta(hours=hours)
                
                # First, get count of records in the time range
                cursor.execute('''
                    SELECT COUNT(*) FROM ups_history 
                    WHERE timestamp > ?
                ''', (since.isoformat(),))
                total_records = cursor.fetchone()[0]
                
                # Get records with proper SQL LIMIT and ORDER BY (latest first)
                cursor.execute('''
                    SELECT * FROM ups_history 
                    WHERE timestamp > ? 
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (since.isoformat(), limit))
                
                columns = [desc[0] for desc in cursor.description]
                history = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
                logger.info(f"Returning {len(history)} records for {hours} hours (requested {total_records} total)")
                return jsonify(history)
        except Exception as e:
            logger.error(f"Error fetching history: {e}")
            return jsonify([])
    
    @bp.route('/events', methods=['GET'])
    @cache_result(timeout=10)  # Cache for 10 seconds
    def get_events():
        """Get UPS events/alerts."""
        limit = request.args.get('limit', 100, type=int)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM ups_events 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
                
                columns = [desc[0] for desc in cursor.description]
                events = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
                return jsonify(events)
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return jsonify([])
    
    @bp.route('/stats', methods=['GET'])
    @cache_result(timeout=30)  # Cache for 30 seconds
    def get_stats():
        """Get UPS statistics."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get basic stats
                since_24h = get_local_now() - timedelta(hours=24)
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_readings,
                        AVG(battery_charge) as avg_battery,
                        AVG(load_pct) as avg_load,
                        AVG(temperature) as avg_temp,
                        MIN(battery_charge) as min_battery,
                        MAX(load_pct) as max_load
                    FROM ups_history 
                    WHERE timestamp > ?
                ''', (since_24h.isoformat(),))
                
                result = cursor.fetchone()
                if result:
                    stats = dict(zip([desc[0] for desc in cursor.description], result))
                else:
                    stats = {}
                
                # Get event counts
                cursor.execute('''
                    SELECT severity, COUNT(*) as count
                    FROM ups_events 
                    WHERE timestamp > ?
                    GROUP BY severity
                ''', (since_24h.isoformat(),))
                
                event_counts = {row[0]: row[1] for row in cursor.fetchall()}
                stats['event_counts'] = event_counts
                
                return jsonify(stats)
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            return jsonify({})
    
    @bp.route('/battery-events', methods=['GET'])
    @cache_result(timeout=20)  # Cache for 20 seconds
    def get_battery_events():
        """Get battery drain events."""
        limit = request.args.get('limit', 50, type=int)
        days = request.args.get('days', 30, type=int)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                since_date = get_local_now() - timedelta(days=days)
                cursor.execute('''
                    SELECT * FROM battery_drain_events 
                    WHERE start_timestamp > ?
                    ORDER BY start_timestamp DESC 
                    LIMIT ?
                ''', (since_date.isoformat(), limit))
                
                columns = [desc[0] for desc in cursor.description]
                events = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
                return jsonify(events)
        except Exception as e:
            logger.error(f"Error fetching battery events: {e}")
            return jsonify([])
    
    @bp.route('/battery-stats', methods=['GET'])
    @cache_result(timeout=30)  # Cache for 30 seconds
    def get_battery_stats():
        """Get battery performance statistics."""
        days = request.args.get('days', 30, type=int)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                since_date = get_local_now() - timedelta(days=days)
                
                # Get battery drain statistics
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_events,
                        AVG(duration_seconds) as avg_duration_seconds,
                        AVG(drain_rate_percent_per_hour) as avg_drain_rate,
                        AVG(start_battery_percent - end_battery_percent) as avg_percent_drained,
                        MAX(drain_rate_percent_per_hour) as max_drain_rate,
                        MIN(drain_rate_percent_per_hour) as min_drain_rate,
                        SUM(duration_seconds) as total_battery_time_seconds
                    FROM battery_drain_events 
                    WHERE start_timestamp > ?
                ''', (since_date.isoformat(),))
                
                result = cursor.fetchone()
                if result:
                    stats = dict(zip([desc[0] for desc in cursor.description], result))
                else:
                    stats = {}
                
                # Get trigger reason breakdown
                cursor.execute('''
                    SELECT trigger_reason, COUNT(*) as count
                    FROM battery_drain_events 
                    WHERE start_timestamp > ?
                    GROUP BY trigger_reason
                ''', (since_date.isoformat(),))
                
                trigger_stats = {row[0]: row[1] for row in cursor.fetchall()}
                stats['trigger_breakdown'] = trigger_stats
                
                return jsonify(stats)
        except Exception as e:
            logger.error(f"Error fetching battery stats: {e}")
            return jsonify({})
    
    @bp.route('/cleanup-duplicates', methods=['POST'])
    def cleanup_duplicate_events():
        """Clean up duplicate battery drain events."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Find and remove duplicate events (keep the one with lowest ID)
                cursor.execute('''
                    DELETE FROM battery_drain_events 
                    WHERE id NOT IN (
                        SELECT MIN(id) 
                        FROM battery_drain_events 
                        GROUP BY start_timestamp, end_timestamp, start_battery_percent, end_battery_percent
                    )
                ''')
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                # Clear cache after cleanup
                clear_cache()
                
                return jsonify({
                    'success': True,
                    'deleted_count': deleted_count,
                    'message': f'Cleaned up {deleted_count} duplicate battery events'
                })
            
        except Exception as e:
            logger.error(f"Error cleaning up duplicates: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @bp.route('/clear-cache', methods=['POST'])
    def clear_cache_endpoint():
        """Clear server cache."""
        try:
            clear_cache()
            return jsonify({
                'success': True,
                'message': 'Cache cleared successfully'
            })
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @bp.route('/export/csv', methods=['GET'])
    def export_historic_csv():
        """Export historic data as CSV."""
        try:
            from flask import Response
            import csv
            import io
            
            # Get parameters
            hours = request.args.get('hours', 24, type=float)
            limit = request.args.get('limit', 1000, type=int)
            
            # Parse date filters if provided
            from_date = request.args.get('from')
            to_date = request.args.get('to')
            
            if from_date and to_date:
                try:
                    from_datetime = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                    to_datetime = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
                    time_diff = to_datetime - from_datetime
                    hours = time_diff.total_seconds() / 3600
                except:
                    pass
            
            # Ensure minimum 15 minutes
            if hours < 0.25:
                hours = 0.25
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get data from last N hours
                since = get_local_now() - timedelta(hours=hours)
                
                cursor.execute('''
                    SELECT * FROM ups_history 
                    WHERE timestamp > ? 
                    ORDER BY timestamp ASC
                    LIMIT ?
                ''', (since.isoformat(), limit))
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                # Create CSV in memory
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Write header
                writer.writerow(columns)
                
                # Write data rows
                for row in rows:
                    writer.writerow(row)
                
                # Create response
                csv_output = output.getvalue()
                output.close()
                
                response = Response(
                    csv_output,
                    mimetype='text/csv',
                    headers={
                        'Content-Disposition': f'attachment; filename=ups-historic-data-{datetime.now().strftime("%Y%m%d-%H%M%S")}.csv'
                    }
                )
                
                logger.info(f"Exported {len(rows)} records to CSV for {hours} hours")
                return response
                
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # Configuration endpoints
    @bp.route('/config/status', methods=['GET'])
    def get_config_status():
        """Get apcupsd configuration status."""
        try:
            config_manager = ApcupsdConfigManager()
            status = config_manager.get_apcupsd_status()
            return jsonify(status)
        except Exception as e:
            logger.error(f"Error getting config status: {e}")
            return jsonify({
                'error': str(e),
                'installed': False,
                'configured': False,
                'active': False,
                'enabled': False
            }), 500
    
    @bp.route('/config/template', methods=['GET'])
    def get_config_template():
        """Get configuration template."""
        try:
            config_manager = ApcupsdConfigManager()
            template = config_manager.get_config_template()
            return jsonify(template)
        except Exception as e:
            logger.error(f"Error getting config template: {e}")
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/config/devices', methods=['GET'])
    def detect_ups_devices():
        """Detect UPS devices."""
        try:
            config_manager = ApcupsdConfigManager()
            devices = config_manager.detect_ups_devices()
            return jsonify(devices)
        except Exception as e:
            logger.error(f"Error detecting devices: {e}")
            return jsonify({'error': str(e)}), 500
    
    @bp.route('/config/validate', methods=['POST'])
    def validate_config():
        """Validate UPS configuration."""
        try:
            config_manager = ApcupsdConfigManager()
            config_data = request.get_json()
            
            if not config_data:
                return jsonify({
                    'success': False,
                    'error': 'No configuration data provided'
                }), 400
            
            is_valid, message = config_manager.validate_config(config_data)
            return jsonify({
                'success': is_valid,
                'message': message
            })
        except Exception as e:
            logger.error(f"Error validating config: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @bp.route('/config/save', methods=['POST'])
    def save_config():
        """Save UPS configuration."""
        try:
            config_manager = ApcupsdConfigManager()
            config_data = request.get_json()
            
            if not config_data:
                return jsonify({
                    'success': False,
                    'error': 'No configuration data provided'
                }), 400
            
            success, message = config_manager.configure_ups(config_data)
            return jsonify({
                'success': success,
                'message': message
            })
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @bp.route('/config/install', methods=['POST'])
    def install_apcupsd():
        """Install apcupsd packages."""
        try:
            config_manager = ApcupsdConfigManager()
            success, message = config_manager.install_apcupsd()
            return jsonify({
                'success': success,
                'message': message
            })
        except Exception as e:
            logger.error(f"Error installing apcupsd: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @bp.route('/config/restart', methods=['POST'])
    def restart_apcupsd():
        """Restart apcupsd service."""
        try:
            config_manager = ApcupsdConfigManager()
            success, message = config_manager.restart_apcupsd()
            return jsonify({
                'success': success,
                'message': message
            })
        except Exception as e:
            logger.error(f"Error restarting apcupsd: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return bp

def setup_socketio(app):
    """Setup SocketIO with the Flask app."""
    global socketio
    
    # Configure SocketIO with better timeout and keepalive settings
    socketio_config = {
        'cors_allowed_origins': "*",
        # The application does not use Socket.IO sessions. Disabling Flask-SocketIO's
        # private session copy avoids incompatibilities across distro Flask versions.
        'manage_session': False,
        'ping_timeout': 120,     # Increased timeout for service environment
        'ping_interval': 60,     # Less frequent pings to reduce overhead
        'max_http_buffer_size': 1000000,  # 1MB buffer
        'allow_upgrades': True,
        'compression': False,    # Disable compression to avoid issues
        'cookie': None,         # No cookies needed
        'upgrade_timeout': 30,   # Longer upgrade timeout for service
        'heartbeat_timeout': 120, # Match ping_timeout
        'heartbeat_interval': 60, # Match ping_interval
        'logger': True,         # Enable socket.io logging for debugging
        'engineio_logger': True # Enable engine.io logging for debugging
    }
    
    # Create SocketIO instance
    new_socketio = SocketIO(app, async_mode='threading', **socketio_config)
    logger.info("SocketIO using threading async mode for service compatibility")
    
    # Update global variable
    socketio = new_socketio
    
    logger.info(f"SocketIO configuration: ping_timeout={socketio_config['ping_timeout']}s, ping_interval={socketio_config['ping_interval']}s")
    
    # Register handlers after socketio is created
    register_socketio_handlers(new_socketio)
    
    return new_socketio

def register_socketio_handlers(socketio_instance):
    """Register SocketIO event handlers."""
    logger.info(f"Registering SocketIO handlers on instance: {socketio_instance}")
    
    @socketio_instance.on('connect')
    def handle_connect():
        """Handle client connection."""
        logger.info(f'✅ Client connected: {request.sid if request else "unknown"}')
        
        # Send current data immediately
        try:
            # Get the current monitor instance
            monitor = apc_ups_monitor
            if monitor and hasattr(monitor, 'current_data'):
                data = monitor.current_data
            else:
                data = {}
                logger.warning("apc_ups_monitor not available or has no current_data")
            
            emit('ups_data', {
                'data': data,
                'alerts': []
            })
            logger.info(f'Initial data sent to client {request.sid if request else "unknown"}')
        except Exception as e:
            logger.error(f'Error sending initial data to client: {e}')
    
    @socketio_instance.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        logger.info(f'❌ Client disconnected: {request.sid if request else "unknown"}')
        
    @socketio_instance.on('connect_error') 
    def handle_connect_error(error):
        """Handle connection errors."""
        logger.error(f'Client connection error: {error}')
    
    @socketio_instance.on('ping')
    def handle_ping(data):
        """Handle ping from client to keep connection alive."""
        import time
        emit('pong', {'timestamp': time.time()})
    
    @socketio_instance.on('request_refresh')
    def handle_refresh_request():
        """Handle manual refresh request."""
        logger.info('Manual refresh requested')
        if apc_ups_monitor:
            # Force immediate data collection
            current_data = apc_ups_monitor.parse_apcaccess_output()
            apc_ups_monitor.current_data = current_data
            alerts = apc_ups_monitor.check_alerts(current_data)
            
            emit('ups_data', {
                'data': current_data,
                'alerts': alerts
            })
    
    @socketio_instance.on_error_default
    def default_error_handler(e):
        """Handle SocketIO errors."""
        logger.error(f'SocketIO error: {e}')
