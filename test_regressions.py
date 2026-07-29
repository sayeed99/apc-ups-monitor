#!/usr/bin/env python3
"""Regression tests for offline assets and apcupsd device/status handling."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.apcupsd_config import ApcupsdConfigManager


PACKAGE_ROOT = Path(__file__).resolve().parent


class PackageAssetTests(unittest.TestCase):
    def test_socketio_client_is_local_and_packaged(self):
        template = (PACKAGE_ROOT / "templates/index.html").read_text()
        manifest = (PACKAGE_ROOT / "MANIFEST.in").read_text()

        self.assertIn("filename='socket.io.min.js'", template)
        self.assertNotIn("cdn.socket.io", template)
        self.assertIn("recursive-include static *", manifest)
        self.assertGreater((PACKAGE_ROOT / "static/socket.io.min.js").stat().st_size, 40_000)

    def test_device_api_response_is_unwrapped_by_frontend(self):
        frontend = (PACKAGE_ROOT / "static/app.js").read_text()
        self.assertIn("(result.devices || [])", frontend)

    def test_socketio_does_not_replace_flask_request_session(self):
        backend = (PACKAGE_ROOT / "src/apc_ups_monitor.py").read_text()
        self.assertIn("'manage_session': False", backend)

    def test_vendor_loader_uses_package_relative_imports(self):
        main = (PACKAGE_ROOT / "src/main.py").read_text()
        loader = (PACKAGE_ROOT / "src/vendor_loader.py").read_text()
        backend = (PACKAGE_ROOT / "src/apc_ups_monitor.py").read_text()
        self.assertIn("from .vendor_loader import load_vendor_packages", main)
        self.assertIn("from .debug_utils import debug", loader)
        self.assertIn("from .apcupsd_config import ApcupsdConfigManager", backend)

    def test_service_explicitly_allows_werkzeug_runner(self):
        main = (PACKAGE_ROOT / "src/main.py").read_text()
        self.assertIn("allow_unsafe_werkzeug=True", main)

    def test_package_configures_privileges_for_service_account(self):
        postinst = (PACKAGE_ROOT / "debian/postinst").read_text()
        service = (PACKAGE_ROOT / "systemd/apc-ups-monitor.service").read_text()

        self.assertIn(
            "apc-ups-monitor ALL=(root) NOPASSWD: /usr/bin/systemctl restart apcupsd",
            postinst,
        )
        self.assertNotIn("$INSTALL_USER ALL=", postinst)
        self.assertIn("NoNewPrivileges=false", service)
        self.assertIn("/etc/apcupsd /etc/default", service)
        self.assertNotIn("\nLockPersonality=", service)
        self.assertNotIn("\nRestrictAddressFamilies=", service)

    def test_config_writes_use_fixed_private_staging_files(self):
        backend = (PACKAGE_ROOT / "src/apcupsd_config.py").read_text()
        postinst = (PACKAGE_ROOT / "debian/postinst").read_text()

        self.assertIn("/var/lib/apc-ups-monitor/staging/apcupsd.conf", backend)
        self.assertIn("/var/lib/apc-ups-monitor/staging/apcupsd.default", backend)
        self.assertNotIn("NamedTemporaryFile", backend)
        self.assertNotIn("/tmp/*.conf", postinst)


class ApcupsdDeviceTests(unittest.TestCase):
    def make_manager(self):
        with patch.object(ApcupsdConfigManager, "_check_apcupsd_installed", return_value=True), \
             patch.object(ApcupsdConfigManager, "_check_apcupsd_configured", return_value=True):
            return ApcupsdConfigManager()

    def test_detects_serial_adapter_exposed_through_sysfs(self):
        manager = self.make_manager()
        real_glob = __import__("glob").glob

        def fake_glob(pattern):
            if pattern == "/sys/class/tty/ttyUSB*":
                return ["/sys/class/tty/ttyUSB1"]
            if pattern.startswith("/dev/") or pattern.endswith("ttyACM*"):
                return []
            return real_glob(pattern)

        with patch("src.apcupsd_config.glob.glob", side_effect=fake_glob), \
             patch("src.apcupsd_config.os.path.exists", return_value=True), \
             patch.object(manager, "_udev_properties", return_value={
                 "ID_VENDOR_FROM_DATABASE": "Exar Corp.",
                 "ID_MODEL_FROM_DATABASE": "XR21V1410 USB-UART IC",
             }):
            devices = manager.detect_ups_devices()

        serial = next(device for device in devices if device["device"] == "/dev/ttyUSB1")
        self.assertEqual(serial["cable"], "smart")
        self.assertEqual(serial["upstype"], "apcsmart")

    def test_commlost_is_reported_as_failed_communication(self):
        result = subprocess.CompletedProcess(
            ["apcaccess", "status"], 0, "STATUS   : COMMLOST\n", ""
        )
        with patch("src.apcupsd_config.subprocess.run", return_value=result):
            ok, message = ApcupsdConfigManager._get_communication_status()

        self.assertFalse(ok)
        self.assertIn("COMMLOST", message)


if __name__ == "__main__":
    unittest.main()
