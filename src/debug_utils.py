#!/usr/bin/env python3
"""
Debug utilities for UPS Monitor
Provides conditional logging and debug functionality
"""

import os
import logging
import sys

logger = logging.getLogger(__name__)

class DebugLogger:
    """Conditional debug logger that respects environment variables and log levels."""
    
    def __init__(self):
        self.debug_enabled = self._is_debug_enabled()
    
    def _is_debug_enabled(self):
        """Check if debug logging is enabled via environment or log level."""
        # Check environment variables
        debug_env = os.environ.get('UPS_MONITOR_DEBUG', '').lower()
        if debug_env in ('1', 'true', 'yes', 'on'):
            return True
        
        # Check if root logger is set to DEBUG level
        return logging.getLogger().isEnabledFor(logging.DEBUG)
    
    def log(self, *args, **kwargs):
        """Log debug message only if debug is enabled."""
        if self.debug_enabled:
            message = ' '.join(str(arg) for arg in args)
            logger.debug(message)
    
    def info(self, *args, **kwargs):
        """Log info message only if debug is enabled."""
        if self.debug_enabled:
            message = ' '.join(str(arg) for arg in args)
            logger.info(message)
    
    def error(self, *args, **kwargs):
        """Log error message only if debug is enabled."""
        if self.debug_enabled:
            message = ' '.join(str(arg) for arg in args)
            logger.error(message)
    
    def warn(self, *args, **kwargs):
        """Log warning message only if debug is enabled."""
        if self.debug_enabled:
            message = ' '.join(str(arg) for arg in args)
            logger.warning(message)

# Global debug instance
debug = DebugLogger()