#!/usr/bin/env python3
"""
Test script for apcupsd configuration API endpoints
"""
import requests
import json

BASE_URL = "http://localhost:5001"

def test_apcupsd_status():
    """Test the apcupsd status endpoint"""
    print("Testing apcupsd status endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/apcupsd/status")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

def test_detect_devices():
    """Test the device detection endpoint"""
    print("\nTesting device detection endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/apcupsd/detect-devices")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

def test_config_template():
    """Test the configuration template endpoint"""
    print("\nTesting configuration template endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/apcupsd/config-template")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

def test_configure_apcupsd():
    """Test the configuration endpoint with sample data"""
    print("\nTesting configuration endpoint...")
    try:
        config_data = {
            "UPSNAME": "TestUPS",
            "UPSCABLE": "usb",
            "UPSTYPE": "usb",
            "DEVICE": "",
            "BATTERYLEVEL": "10",
            "MINUTES": "5",
            "ONBATTERYDELAY": "6",
            "TIMEOUT": "0",
            "NETSERVER": "on",
            "NISIP": "127.0.0.1",
            "NISPORT": "3551"
        }
        
        response = requests.post(f"{BASE_URL}/api/apcupsd/configure", json=config_data)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Testing apcupsd configuration API endpoints...")
    print("=" * 50)
    
    test_apcupsd_status()
    test_detect_devices()
    test_config_template()
    # test_configure_apcupsd()  # Commented out to avoid actually configuring
    
    print("\nAll tests completed!")