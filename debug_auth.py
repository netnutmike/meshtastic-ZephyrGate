#!/usr/bin/env python3
"""
Debug script to test authentication and diagnose 401 errors
"""
import requests
import json
import getpass
import sys

BASE_URL = "http://localhost:8080"

def test_login():
    """Test login and subsequent API calls"""
    print("=" * 60)
    print("Testing Authentication Flow")
    print("=" * 60)
    
    # Get credentials
    username = input("\nEnter username (default: test): ").strip() or "test"
    password = getpass.getpass("Enter password: ")
    
    if not password:
        print("❌ Password cannot be empty!")
        sys.exit(1)
    
    # Test login
    print("\n1. Testing login...")
    login_data = {
        "username": username,
        "password": password
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")
    
    if response.status_code != 200:
        print("\n❌ Login failed!")
        return
    
    data = response.json()
    token = data.get("access_token")
    print(f"\n✓ Login successful!")
    print(f"   Token: {token[:50]}...")
    
    # Decode token to see what's inside (without verification)
    import base64
    try:
        # JWT format: header.payload.signature
        parts = token.split('.')
        if len(parts) == 3:
            # Add padding if needed
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            print(f"   Token payload: {decoded.decode('utf-8')}")
    except Exception as e:
        print(f"   Could not decode token: {e}")
    
    # Test profile endpoint
    print("\n2. Testing /api/auth/profile...")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(f"{BASE_URL}/api/auth/profile", headers=headers)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")
    
    if response.status_code == 200:
        print("\n✓ Profile endpoint works!")
    else:
        print("\n❌ Profile endpoint failed!")
        print("\nPossible issues:")
        print("  - IP address mismatch (IPv4 vs IPv6)")
        print("  - Session not being created properly")
        print("  - Token validation issue")
    
    # Test system status endpoint
    print("\n3. Testing /api/system/status...")
    response = requests.get(f"{BASE_URL}/api/system/status", headers=headers)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}...")
    
    if response.status_code == 200:
        print("\n✓ System status endpoint works!")
    else:
        print("\n❌ System status endpoint failed!")

if __name__ == "__main__":
    try:
        test_login()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Is it running on http://localhost:8080?")
    except Exception as e:
        print(f"❌ Error: {e}")
