#!/usr/bin/env python3
"""
APC UPS Configuration Management Module
Handles automatic installation and configuration of apcupsd and apcupsd-cgi
"""

import os
import glob
import subprocess
import shutil
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class ApcupsdConfigManager:
    """Manages apcupsd installation and configuration"""
    
    APCUPSD_CONF_PATH = "/etc/apcupsd/apcupsd.conf"
    APCUPSD_DEFAULT_PATH = "/etc/default/apcupsd"
    APCUPSD_BACKUP_PATH = "/etc/apcupsd/apcupsd.conf.backup"
    STAGING_CONFIG_PATH = "/var/lib/apc-ups-monitor/staging/apcupsd.conf"
    STAGING_DEFAULT_PATH = "/var/lib/apc-ups-monitor/staging/apcupsd.default"
    SUDO = ["/usr/bin/sudo", "-n"]
    
    DEFAULT_CONFIG = {
        'UPSNAME': '',  # Will be commented out if empty
        'UPSCABLE': 'usb',
        'UPSTYPE': 'usb',
        'DEVICE': '',  # Will be commented out if empty for USB
        'LOCKFILE': '/var/lock',
        'SCRIPTDIR': '/etc/apcupsd',
        'PWRFAILDIR': '/etc/apcupsd',
        'NOLOGINDIR': '/etc',
        'ONBATTERYDELAY': '6',
        'BATTERYLEVEL': '5',
        'MINUTES': '3',
        'TIMEOUT': '0',
        'ANNOY': '300',
        'ANNOYDELAY': '60',
        'NOLOGON': 'disable',
        'KILLDELAY': '0',
        'NETSERVER': 'on',
        'NISIP': '127.0.0.1',
        'NISPORT': '3551',
        'EVENTSFILE': '/var/log/apcupsd.events',
        'EVENTSFILEMAX': '10',
        'UPSCLASS': 'standalone',
        'UPSMODE': 'disable',
        'STATTIME': '0',
        'STATFILE': '/var/log/apcupsd.status',
        'LOGSTATS': 'off',
        'DATATIME': '0'
    }
    
    def __init__(self):
        self.is_installed = self._check_apcupsd_installed()
        self.is_configured = self._check_apcupsd_configured()
    
    def _check_apcupsd_installed(self) -> bool:
        """Check if apcupsd is installed"""
        try:
            subprocess.run(['dpkg', '-s', 'apcupsd'], 
                         capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def _check_apcupsd_configured(self) -> bool:
        """Check if apcupsd is properly configured"""
        if not os.path.exists(self.APCUPSD_CONF_PATH):
            return False
        
        # Check if ENABLED or ISCONFIGURED is set to yes in /etc/default/apcupsd
        enabled_check = False
        try:
            with open(self.APCUPSD_DEFAULT_PATH, 'r') as f:
                content = f.read()
                enabled_check = 'ENABLED=yes' in content or 'ISCONFIGURED=yes' in content
        except FileNotFoundError:
            enabled_check = False
        
        # Also check if the main config file has valid UPS settings
        config_check = False
        try:
            with open(self.APCUPSD_CONF_PATH, 'r') as f:
                config_content = f.read()
                # Check for essential settings
                has_upstype = any(line.strip().startswith('UPSTYPE ') for line in config_content.split('\n'))
                has_upscable = any(line.strip().startswith('UPSCABLE ') for line in config_content.split('\n'))
                config_check = has_upstype and has_upscable
        except FileNotFoundError:
            config_check = False
        
        # Both checks must pass for proper configuration
        return enabled_check and config_check
    
    def install_apcupsd(self) -> Tuple[bool, str]:
        """Install apcupsd and apcupsd-cgi packages"""
        if self.is_installed:
            return True, "apcupsd is already installed"
        
        try:
            # Update package lists using sudo
            subprocess.run(self.SUDO + ['/usr/bin/apt-get', 'update'], check=True)
            
            # Install apcupsd and apcupsd-cgi using sudo
            subprocess.run(self.SUDO + ['/usr/bin/apt-get', 'install', '-y', 'apcupsd', 'apcupsd-cgi'],
                         check=True)
            
            self.is_installed = True
            logger.info("Successfully installed apcupsd and apcupsd-cgi")
            return True, "apcupsd and apcupsd-cgi installed successfully"
            
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:  # Permission denied
                error_msg = (
                    "Permission denied: Unable to install apcupsd packages. "
                    "Please run 'sudo ./scripts/setup-sudo-permissions.sh' to configure "
                    "the required permissions, or install apcupsd manually with 'sudo apt-get install apcupsd apcupsd-cgi'."
                )
            else:
                error_msg = f"Failed to install apcupsd: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def detect_ups_devices(self) -> List[Dict[str, str]]:
        """Detect connected UPS devices"""
        devices = []
        
        # Check USB devices
        try:
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if any(keyword in line.lower() for keyword in ['apc', 'ups', 'american power']):
                    devices.append({
                        'type': 'usb',
                        'device': '',  # USB devices should have blank DEVICE
                        'description': line.strip(),
                        'cable': 'usb',
                        'upstype': 'usb'
                    })
        except subprocess.CalledProcessError:
            pass
        
        # Check serial devices dynamically. The monitor service may have PrivateDevices
        # enabled, so also use sysfs, which still exposes the host's enumerated adapters.
        serial_devices = set(glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*'))
        for sysfs_device in glob.glob('/sys/class/tty/ttyUSB*') + glob.glob('/sys/class/tty/ttyACM*'):
            serial_devices.add(f"/dev/{os.path.basename(sysfs_device)}")

        for device in sorted(serial_devices):
            if os.path.exists(device) or os.path.exists(f"/sys/class/tty/{os.path.basename(device)}"):
                description = f'Serial adapter at {device}'
                properties = self._udev_properties(device)
                model = properties.get('ID_MODEL_FROM_DATABASE') or properties.get('ID_MODEL')
                vendor = properties.get('ID_VENDOR_FROM_DATABASE') or properties.get('ID_VENDOR')
                if vendor or model:
                    description = f"{vendor or 'USB serial'} {model or 'adapter'} at {device}"
                devices.append({
                    'type': 'serial',
                    'device': device,
                    'description': description,
                    'cable': 'smart',
                    'upstype': 'apcsmart'
                })
        
        return devices

    @staticmethod
    def _udev_properties(device: str) -> Dict[str, str]:
        """Return safe udev metadata for a serial device, if available."""
        try:
            result = subprocess.run(
                ['udevadm', 'info', '--query=property', f'--name={device}'],
                capture_output=True, text=True, timeout=3
            )
            return dict(
                line.split('=', 1) for line in result.stdout.splitlines() if '=' in line
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return {}
    
    def generate_config(self, ups_config: Dict[str, str]) -> str:
        """Generate apcupsd configuration content matching original format"""
        config = self.DEFAULT_CONFIG.copy()
        config.update(ups_config)
        
        config_lines = []
        config_lines.append("## apcupsd.conf v1.1 ##")
        config_lines.append("# ")
        config_lines.append("# \"apcupsd\" POSIX config file")
        config_lines.append("# Generated by UPS Monitor")
        config_lines.append("")
        config_lines.append("#")
        config_lines.append("# Note that the apcupsd daemon must be restarted in order for changes to")
        config_lines.append("# this configuration file to become active.")
        config_lines.append("#")
        config_lines.append("")
        
        # UPS Configuration
        config_lines.append("#")
        config_lines.append("# ========= General configuration parameters ============")
        config_lines.append("#")
        config_lines.append("")
        
        # UPSNAME with proper commenting
        if config.get('UPSNAME'):
            config_lines.append(f"UPSNAME {config['UPSNAME']}")
        else:
            config_lines.append("#UPSNAME")
        config_lines.append("")
        
        # UPSCABLE
        config_lines.append(f"UPSCABLE {config['UPSCABLE']}")
        config_lines.append("")
        
        # UPSTYPE and DEVICE
        config_lines.append(f"UPSTYPE {config['UPSTYPE']}")
        if config.get('DEVICE'):
            config_lines.append(f"DEVICE {config['DEVICE']}")
        else:
            config_lines.append("#DEVICE")
        config_lines.append("")
        
        # System directories
        config_lines.append(f"LOCKFILE {config['LOCKFILE']}")
        config_lines.append(f"SCRIPTDIR {config['SCRIPTDIR']}")
        config_lines.append(f"PWRFAILDIR {config['PWRFAILDIR']}")
        config_lines.append(f"NOLOGINDIR {config['NOLOGINDIR']}")
        config_lines.append("")
        
        # Power failure configuration
        config_lines.append("#")
        config_lines.append("# ======== Configuration parameters used during power failures ===========")
        config_lines.append("#")
        config_lines.append("")
        
        config_lines.append(f"ONBATTERYDELAY {config['ONBATTERYDELAY']}")
        config_lines.append(f"BATTERYLEVEL {config['BATTERYLEVEL']}")
        config_lines.append(f"MINUTES {config['MINUTES']}")
        config_lines.append(f"TIMEOUT {config['TIMEOUT']}")
        config_lines.append(f"ANNOY {config['ANNOY']}")
        config_lines.append(f"ANNOYDELAY {config['ANNOYDELAY']}")
        config_lines.append(f"NOLOGON {config['NOLOGON']}")
        config_lines.append(f"KILLDELAY {config['KILLDELAY']}")
        config_lines.append("")
        
        # Network Information Server
        config_lines.append("#")
        config_lines.append("# ==== Configuration statements for Network Information Server ====")
        config_lines.append("#")
        config_lines.append("")
        
        config_lines.append(f"NETSERVER {config['NETSERVER']}")
        config_lines.append(f"NISIP {config['NISIP']}")
        config_lines.append(f"NISPORT {config['NISPORT']}")
        config_lines.append(f"EVENTSFILE {config['EVENTSFILE']}")
        config_lines.append(f"EVENTSFILEMAX {config['EVENTSFILEMAX']}")
        config_lines.append("")
        
        # Sharing configuration
        config_lines.append("#")
        config_lines.append("# ========== Configuration statements used if sharing =============")
        config_lines.append("#            a UPS with more than one machine")
        config_lines.append("")
        
        config_lines.append(f"UPSCLASS {config['UPSCLASS']}")
        config_lines.append(f"UPSMODE {config['UPSMODE']}")
        config_lines.append("")
        
        # Logging configuration
        config_lines.append("#")
        config_lines.append("# ===== Configuration statements to control apcupsd system logging ========")
        config_lines.append("#")
        config_lines.append("")
        
        config_lines.append(f"STATTIME {config['STATTIME']}")
        config_lines.append(f"STATFILE {config['STATFILE']}")
        config_lines.append(f"LOGSTATS {config['LOGSTATS']}")
        config_lines.append(f"DATATIME {config['DATATIME']}")
        config_lines.append("")
        
        return '\n'.join(config_lines)
    
    def backup_config(self) -> bool:
        """Backup existing apcupsd configuration using sudo"""
        if os.path.exists(self.APCUPSD_CONF_PATH):
            try:
                # Use sudo to copy the config file
                subprocess.run(self.SUDO + ['/usr/bin/cp', self.APCUPSD_CONF_PATH, self.APCUPSD_BACKUP_PATH],
                             check=True)
                logger.info(f"Backed up existing config to {self.APCUPSD_BACKUP_PATH}")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to backup config: {e}")
                return False
            except Exception as e:
                logger.error(f"Failed to backup config: {e}")
                return False
        return True
    
    def write_config(self, config_content: str) -> Tuple[bool, str]:
        """Write apcupsd configuration file using sudo"""
        try:
            # Backup existing config
            if not self.backup_config():
                return False, "Failed to backup existing configuration"
            
            # The package creates this private, service-owned staging directory.
            with open(self.STAGING_CONFIG_PATH, 'w') as temp_file:
                temp_file.write(config_content)

            subprocess.run(
                self.SUDO + [
                    '/usr/bin/install', '-o', 'root', '-g', 'root', '-m', '0644',
                    self.STAGING_CONFIG_PATH, self.APCUPSD_CONF_PATH
                ],
                check=True
            )

            logger.info("Successfully wrote apcupsd configuration")
            return True, "Configuration written successfully"
            
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:  # Permission denied
                error_msg = (
                    "Permission denied: Unable to write apcupsd configuration. "
                    "Reinstall or upgrade the APC UPS Monitor package to restore "
                    "its service permissions."
                )
            else:
                error_msg = f"Failed to write configuration: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Failed to write configuration: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def enable_apcupsd(self) -> Tuple[bool, str]:
        """Enable apcupsd service using sudo"""
        try:
            # Enable in /etc/default/apcupsd - use the standard format
            default_content = """# Defaults for apcupsd initscript (unused with systemd as init).
# Set to "yes" to enable startup of apcupsd.
ISCONFIGURED=yes
"""
            with open(self.STAGING_DEFAULT_PATH, 'w') as temp_file:
                temp_file.write(default_content)

            subprocess.run(
                self.SUDO + [
                    '/usr/bin/install', '-o', 'root', '-g', 'root', '-m', '0644',
                    self.STAGING_DEFAULT_PATH, self.APCUPSD_DEFAULT_PATH
                ],
                check=True
            )
            
            # Reload systemd and enable service
            subprocess.run(self.SUDO + ['/usr/bin/systemctl', 'daemon-reload'], check=True)
            subprocess.run(self.SUDO + ['/usr/bin/systemctl', 'enable', 'apcupsd'], check=True)
            
            self.is_configured = True
            logger.info("Successfully enabled apcupsd service")
            return True, "apcupsd service enabled successfully"
            
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:  # Permission denied
                error_msg = (
                    "Permission denied: Unable to enable apcupsd service. "
                    "Reinstall or upgrade the APC UPS Monitor package to restore "
                    "its service permissions."
                )
            else:
                error_msg = f"Failed to enable apcupsd: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Failed to enable apcupsd: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def restart_apcupsd(self) -> Tuple[bool, str]:
        """Restart apcupsd service using sudo"""
        try:
            subprocess.run(self.SUDO + ['/usr/bin/systemctl', 'restart', 'apcupsd'], check=True)
            logger.info("Successfully restarted apcupsd service")
            return True, "apcupsd service restarted successfully"
            
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:  # Permission denied
                error_msg = (
                    "Permission denied: Unable to restart apcupsd service. "
                    "Reinstall or upgrade the APC UPS Monitor package to restore "
                    "its service permissions."
                )
            else:
                error_msg = f"Failed to restart apcupsd: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_apcupsd_status(self) -> Dict[str, any]:
        """Get apcupsd service status"""
        try:
            # Check service status
            result = subprocess.run(['systemctl', 'is-active', 'apcupsd'], 
                                  capture_output=True, text=True)
            is_active = result.stdout.strip() == 'active'
            
            # Check if enabled
            result = subprocess.run(['systemctl', 'is-enabled', 'apcupsd'], 
                                  capture_output=True, text=True)
            is_enabled = result.stdout.strip() == 'enabled'
            
            # Get detailed status
            result = subprocess.run(['systemctl', 'status', 'apcupsd'], 
                                  capture_output=True, text=True)
            status_output = result.stdout
            
            communication_ok, communication_status = self._get_communication_status()
            current_config = self.get_current_config()
            configured_device = current_config.get('DEVICE', '')
            device_present = (
                not configured_device
                or os.path.exists(configured_device)
                or os.path.exists(f"/sys/class/tty/{os.path.basename(configured_device)}")
            )

            return {
                'installed': self.is_installed,
                'configured': self.is_configured,
                'active': is_active,
                'enabled': is_enabled,
                'communication_ok': communication_ok,
                'communication_status': communication_status,
                'configured_device': configured_device,
                'device_present': device_present,
                'status_output': status_output
            }
            
        except Exception as e:
            logger.error(f"Failed to get apcupsd status: {e}")
            return {
                'installed': self.is_installed,
                'configured': self.is_configured,
                'active': False,
                'enabled': False,
                'communication_ok': False,
                'communication_status': f"Unable to check UPS communication: {e}",
                'configured_device': '',
                'device_present': False,
                'status_output': f"Error: {e}"
            }

    @staticmethod
    def _get_communication_status() -> Tuple[bool, str]:
        """Query apcupsd and distinguish daemon health from UPS communication."""
        try:
            result = subprocess.run(
                ['apcaccess', 'status'], capture_output=True, text=True, timeout=5
            )
        except FileNotFoundError:
            return False, "apcaccess is not installed"
        except subprocess.TimeoutExpired:
            return False, "apcaccess timed out"

        if result.returncode != 0:
            message = (result.stderr or result.stdout).strip()
            return False, message or f"apcaccess exited with status {result.returncode}"

        status = ''
        for line in result.stdout.splitlines():
            if line.strip().startswith('STATUS') and ':' in line:
                status = line.split(':', 1)[1].strip()
                break
        if 'COMMLOST' in status.upper():
            return False, f"UPS communication lost ({status})"
        return True, status or "UPS is responding"
    
    def validate_config(self, config: Dict[str, str]) -> Tuple[bool, str]:
        """Validate configuration values according to apcupsd requirements"""
        errors = []
        
        # Validate UPSNAME (max 8 characters)
        if config.get('UPSNAME') and len(config['UPSNAME']) > 8:
            errors.append("UPSNAME must be 8 characters or less")
        
        # Validate UPSCABLE
        valid_cables = ['usb', 'smart', 'simple', 'ether']
        if config.get('UPSCABLE') not in valid_cables:
            errors.append(f"UPSCABLE must be one of: {', '.join(valid_cables)}")
        
        # Validate UPSTYPE
        valid_types = ['usb', 'apcsmart', 'net', 'snmp', 'netsnmp', 'dumb', 'pcnet', 'modbus']
        if config.get('UPSTYPE') not in valid_types:
            errors.append(f"UPSTYPE must be one of: {', '.join(valid_types)}")
        
        # Validate DEVICE based on UPSTYPE
        upstype = config.get('UPSTYPE', 'usb')
        device = config.get('DEVICE', '')
        
        if upstype == 'usb' and device:
            # USB should typically have blank DEVICE for auto-detection
            pass  # Allow but warn
        elif upstype in ['apcsmart', 'dumb', 'modbus'] and not device:
            errors.append(f"DEVICE path required for UPSTYPE {upstype}")
        elif upstype == 'net' and device and ':' not in device:
            errors.append("DEVICE for net type must be hostname:port format")
        elif upstype == 'snmp' and device and device.count(':') != 3:
            errors.append("DEVICE for snmp type must be hostname:port:vendor:community format")
        
        # Validate numeric ranges
        numeric_validations = {
            'BATTERYLEVEL': (1, 100),
            'MINUTES': (1, 60),
            'ONBATTERYDELAY': (0, 300),
            'TIMEOUT': (0, 86400),
            'ANNOY': (0, 3600),
            'ANNOYDELAY': (0, 3600),
            'KILLDELAY': (0, 3600),
            'NISPORT': (1024, 65535),
            'EVENTSFILEMAX': (0, 1000),
            'STATTIME': (0, 3600),
            'DATATIME': (0, 3600)
        }
        
        for key, (min_val, max_val) in numeric_validations.items():
            if key in config:
                try:
                    value = int(config[key])
                    if not (min_val <= value <= max_val):
                        errors.append(f"{key} must be between {min_val} and {max_val}")
                except ValueError:
                    errors.append(f"{key} must be a valid number")
        
        # Validate select options
        select_validations = {
            'NOLOGON': ['disable', 'timeout', 'percent', 'minutes', 'always'],
            'NETSERVER': ['on', 'off'],
            'LOGSTATS': ['on', 'off'],
            'UPSCLASS': ['standalone', 'shareslave', 'sharemaster'],
            'UPSMODE': ['disable', 'share']
        }
        
        for key, valid_options in select_validations.items():
            if key in config and config[key] not in valid_options:
                errors.append(f"{key} must be one of: {', '.join(valid_options)}")
        
        # Validate IP address format (basic check)
        if 'NISIP' in config:
            ip = config['NISIP']
            if ip != '0.0.0.0' and ip != '127.0.0.1':
                # Basic IP validation
                parts = ip.split('.')
                if len(parts) != 4:
                    errors.append("NISIP must be a valid IP address")
                else:
                    try:
                        for part in parts:
                            num = int(part)
                            if not (0 <= num <= 255):
                                errors.append("NISIP must be a valid IP address")
                                break
                    except ValueError:
                        errors.append("NISIP must be a valid IP address")
        
        if errors:
            return False, "; ".join(errors)
        return True, "Configuration is valid"

    def configure_ups(self, ups_config: Dict[str, str]) -> Tuple[bool, str]:
        """Complete UPS configuration process"""
        # Validate configuration first
        is_valid, validation_message = self.validate_config(ups_config)
        if not is_valid:
            return False, f"Configuration validation failed: {validation_message}"
        
        # Install if not installed
        if not self.is_installed:
            success, message = self.install_apcupsd()
            if not success:
                return False, message
        
        # Generate and write config
        config_content = self.generate_config(ups_config)
        success, message = self.write_config(config_content)
        if not success:
            return False, message
        
        # Enable service
        success, message = self.enable_apcupsd()
        if not success:
            return False, message
        
        # Restart service
        success, message = self.restart_apcupsd()
        if not success:
            return False, message
        
        return True, "UPS configuration completed successfully"
    
    def get_config_template(self) -> Dict[str, Dict[str, any]]:
        """Get configuration template with descriptions based on original apcupsd.conf"""
        return {
            'basic': {
                'UPSNAME': {
                    'value': '',
                    'description': 'UPS name (8 characters or less, optional)',
                    'type': 'text',
                    'maxlength': 8,
                    'required': False
                },
                'UPSCABLE': {
                    'value': 'usb',
                    'description': 'Cable type connecting UPS to computer',
                    'type': 'select',
                    'options': ['usb', 'smart', 'simple', 'ether'],
                    'required': True
                },
                'UPSTYPE': {
                    'value': 'usb',
                    'description': 'UPS connection type',
                    'type': 'select',
                    'options': ['usb', 'apcsmart', 'net', 'snmp', 'netsnmp', 'dumb', 'pcnet', 'modbus'],
                    'required': True
                },
                'DEVICE': {
                    'value': '',
                    'description': 'Device path (leave blank for USB auto-detection)',
                    'type': 'text',
                    'required': False,
                    'placeholder': '/dev/ttyS0 for serial, blank for USB'
                }
            },
            'power': {
                'ONBATTERYDELAY': {
                    'value': '6',
                    'description': 'Delay (seconds) before reacting to power failure',
                    'type': 'number',
                    'min': 0,
                    'max': 300,
                    'required': True
                },
                'BATTERYLEVEL': {
                    'value': '5',
                    'description': 'Battery level (%) to initiate shutdown',
                    'type': 'number',
                    'min': 1,
                    'max': 100,
                    'required': True
                },
                'MINUTES': {
                    'value': '3',
                    'description': 'Runtime left (minutes) to initiate shutdown',
                    'type': 'number',
                    'min': 1,
                    'max': 60,
                    'required': True
                },
                'TIMEOUT': {
                    'value': '0',
                    'description': 'Shutdown timeout in seconds (0 = disabled)',
                    'type': 'number',
                    'min': 0,
                    'max': 86400,
                    'required': True
                },
                'ANNOY': {
                    'value': '300',
                    'description': 'Time between user warnings (0 = disabled)',
                    'type': 'number',
                    'min': 0,
                    'max': 3600,
                    'required': True
                },
                'ANNOYDELAY': {
                    'value': '60',
                    'description': 'Initial delay before warning users',
                    'type': 'number',
                    'min': 0,
                    'max': 3600,
                    'required': True
                },
                'NOLOGON': {
                    'value': 'disable',
                    'description': 'Prevent user logins during power failure',
                    'type': 'select',
                    'options': ['disable', 'timeout', 'percent', 'minutes', 'always'],
                    'required': True
                },
                'KILLDELAY': {
                    'value': '0',
                    'description': 'Delay before killing power (0 = disabled)',
                    'type': 'number',
                    'min': 0,
                    'max': 3600,
                    'required': True
                }
            },
            'network': {
                'NETSERVER': {
                    'value': 'on',
                    'description': 'Enable network information server',
                    'type': 'select',
                    'options': ['on', 'off'],
                    'required': True
                },
                'NISIP': {
                    'value': '127.0.0.1',
                    'description': 'IP address for network server (0.0.0.0 for all)',
                    'type': 'text',
                    'required': True,
                    'placeholder': '127.0.0.1 for localhost only'
                },
                'NISPORT': {
                    'value': '3551',
                    'description': 'Network information server port',
                    'type': 'number',
                    'min': 1024,
                    'max': 65535,
                    'required': True
                }
            },
            'logging': {
                'EVENTSFILE': {
                    'value': '/var/log/apcupsd.events',
                    'description': 'Events log file path',
                    'type': 'text',
                    'required': True
                },
                'EVENTSFILEMAX': {
                    'value': '10',
                    'description': 'Maximum events file size (KB)',
                    'type': 'number',
                    'min': 0,
                    'max': 1000,
                    'required': True
                },
                'STATTIME': {
                    'value': '0',
                    'description': 'Status file update interval (0 = disabled)',
                    'type': 'number',
                    'min': 0,
                    'max': 3600,
                    'required': True
                },
                'STATFILE': {
                    'value': '/var/log/apcupsd.status',
                    'description': 'Status file path',
                    'type': 'text',
                    'required': True
                },
                'LOGSTATS': {
                    'value': 'off',
                    'description': 'Enable detailed logging',
                    'type': 'select',
                    'options': ['on', 'off'],
                    'required': True
                },
                'DATATIME': {
                    'value': '0',
                    'description': 'Data logging interval (0 = disabled)',
                    'type': 'number',
                    'min': 0,
                    'max': 3600,
                    'required': True
                }
            },
            'advanced': {
                'UPSCLASS': {
                    'value': 'standalone',
                    'description': 'UPS class (for ShareUPS only)',
                    'type': 'select',
                    'options': ['standalone', 'shareslave', 'sharemaster'],
                    'required': True
                },
                'UPSMODE': {
                    'value': 'disable',
                    'description': 'UPS mode (for ShareUPS only)',
                    'type': 'select',
                    'options': ['disable', 'share'],
                    'required': True
                }
            }
        }
    
    def get_current_config(self) -> Dict[str, str]:
        """Read current configuration from apcupsd.conf file"""
        config = {}
        
        if not os.path.exists(self.APCUPSD_CONF_PATH):
            # Return defaults if file doesn't exist
            return self.DEFAULT_CONFIG.copy()
        
        try:
            with open(self.APCUPSD_CONF_PATH, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Handle lines with configuration values
                        if ' ' in line:
                            key, value = line.split(' ', 1)
                            config[key] = value
                        
            # Fill in defaults for any missing values
            for key, default_value in self.DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = default_value
                    
            return config
            
        except Exception as e:
            logger.error(f"Failed to read current configuration: {e}")
            # Return defaults on error
            return self.DEFAULT_CONFIG.copy()
