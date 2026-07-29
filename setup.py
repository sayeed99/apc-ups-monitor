#!/usr/bin/env python3
"""
Setup script for UPS Monitor Package
"""
import os
import glob
from setuptools import setup, find_packages

# Get all wheel files from vendor directory
vendor_wheels = glob.glob("vendor/*.whl")

setup(
    name="apc-ups-monitor",
    version="1.17.5",
    description="APC UPS monitoring system with a real-time web interface",
    author="Sayeed Afridi",
    author_email="sayeed.afridi2009@gmail.comm",
    url="https://github.com/sayeed99/apc-ups-monitor",
    packages=["apc_ups_monitor"],
    package_dir={"apc_ups_monitor": "src"},
    include_package_data=True,
    install_requires=[],
    package_data={
        "apc_ups_monitor": ["../static/*", "../templates/*", "../systemd/*", "../vendor/*.whl"],
    },
    data_files=[
        ("apc_ups_monitor/vendor", vendor_wheels),
    ],
    entry_points={
        "console_scripts": [
            "apc-ups-monitor=apc_ups_monitor.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
)
