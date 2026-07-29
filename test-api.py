#!/usr/bin/env python3
"""
Test script for UPS Monitor API
"""

import requests
import json
import time
import sys

def test_api(base_url="http://localhost:5001"):
    """Test the UPS Monitor API endpoints"""
    
    print(f"Testing UPS Monitor API at {base_url}")
    print("=" * 50)
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/api/health", timeout=5)
        if response.status_code == 200:
            print("✓ Health check: PASSED")
            data = response.json()
            print(f"  Service: {data.get('service')}")
            print(f"  Status: {data.get('status')}")
        else:
            print(f"✗ Health check: FAILED ({response.status_code})")
    except Exception as e:
        print(f"✗ Health check: ERROR - {e}")
        return False
    
    # Test current data endpoint
    try:
        response = requests.get(f"{base_url}/api/current", timeout=5)
        if response.status_code == 200:
            print("✓ Current data: PASSED")
            data = response.json()
            print(f"  Status: {data.get('status', 'Unknown')}")
            print(f"  Battery: {data.get('battery_charge', 0)}%")
            print(f"  Load: {data.get('load_pct', 0)}%")
            print(f"  Using mock data: {data.get('using_mock_data', False)}")
        else:
            print(f"✗ Current data: FAILED ({response.status_code})")
    except Exception as e:
        print(f"✗ Current data: ERROR - {e}")
    
    # Test history endpoint
    try:
        response = requests.get(f"{base_url}/api/history?hours=1&limit=10", timeout=5)
        if response.status_code == 200:
            print("✓ History data: PASSED")
            data = response.json()
            print(f"  Records: {len(data)}")
        else:
            print(f"✗ History data: FAILED ({response.status_code})")
    except Exception as e:
        print(f"✗ History data: ERROR - {e}")
    
    # Test events endpoint
    try:
        response = requests.get(f"{base_url}/api/events?limit=5", timeout=5)
        if response.status_code == 200:
            print("✓ Events data: PASSED")
            data = response.json()
            print(f"  Events: {len(data)}")
        else:
            print(f"✗ Events data: FAILED ({response.status_code})")
    except Exception as e:
        print(f"✗ Events data: ERROR - {e}")
    
    # Test battery events endpoint
    try:
        response = requests.get(f"{base_url}/api/battery-events?limit=5", timeout=5)
        if response.status_code == 200:
            print("✓ Battery events: PASSED")
            data = response.json()
            print(f"  Battery events: {len(data)}")
        else:
            print(f"✗ Battery events: FAILED ({response.status_code})")
    except Exception as e:
        print(f"✗ Battery events: ERROR - {e}")
    
    # Test battery stats endpoint
    try:
        response = requests.get(f"{base_url}/api/battery-stats", timeout=5)
        if response.status_code == 200:
            print("✓ Battery stats: PASSED")
            data = response.json()
            print(f"  Total events: {data.get('total_events', 0)}")
        else:
            print(f"✗ Battery stats: FAILED ({response.status_code})")
    except Exception as e:
        print(f"✗ Battery stats: ERROR - {e}")
    
    # Test web interface
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✓ Web interface: PASSED")
            print(f"  Content length: {len(response.content)} bytes")
        else:
            print(f"✗ Web interface: FAILED ({response.status_code})")
    except Exception as e:
        print(f"✗ Web interface: ERROR - {e}")
    
    print("\nAPI test completed!")
    return True

if __name__ == '__main__':
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5001"
    test_api(base_url)