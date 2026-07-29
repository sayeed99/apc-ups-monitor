#!/usr/bin/env python3
"""
APC UPS Monitor Package
A monitoring system for APC uninterruptible power supplies.
"""

__version__ = "1.17.7"
__author__ = "Sayeed Afridi"
__email__ = "sayeed.afridi2009@gmail.comm"

from .main import main, create_app
from .apc_ups_monitor import UPSMonitor, init_database, setup_socketio
from .apcupsd_config import ApcupsdConfigManager

__all__ = [
    'main',
    'create_app', 
    'UPSMonitor',
    'init_database',
    'setup_socketio',
    'ApcupsdConfigManager'
]
