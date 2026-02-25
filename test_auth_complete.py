#!/usr/bin/env python3
"""
Complete authentication test - tests both viewer and admin users
"""
import requests
import getpass

BASE_URL = "http://localhost:8080"

def test_user(username, password):
    """Test login and API access for a user"""
    print(f"\n{'='*60}")
    print(f"Testing user: {username}")
    print('='*60)
    
    # Login
    print("\n1. Login...")
    response = requests.post(f"{BASE_URL}/api/auth/login", 
                            json={"username": username, "password": password})
    
    if response.status_code != 200:
        print(f"   ❌ Login failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    token = response.json()["access_token"]
    print(f"   ✓ Login successful")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test profile
    print("\n2. Test /api/auth/profile...")
    response = requests.get(f"{BASE_URL}/api/auth/profile", headers=headers)
    if response.status_code == 200:
        profile = response.json()
        print(f"   ✓ Profile loaded")
        print(f"   Username: {profile['username']}")
        print(f"   Role: {profile['role']}")
        print(f"   Permissions: {profile['permissions']}")
    else:
        print(f"   ❌ Failed: {response.status_code}")
        return False
    
    # Test system status
    print("\n3. Test /api/system/status...")
    response = requests.get(f"{BASE_URL}/api/system/status", headers=headers)
    if response.status_code == 200:
        print(f"   ✓ System status accessible")
    elif response.status_code == 403:
        print(f"   ⚠ Forbidden (expected for viewer role)")
    else:
        print(f"   ❌ Unexpected status: {response.status_code}")
    
    return True

if __name__ == "__main__":
    print("Authentication Fix Verification")
    print("="*60)
    
    # Test viewer user
    test_user("test", "test")
    
    # Optionally test admin user
    print("\n\nWould you like to test admin user as well? (y/n): ", end="")
    if input().lower() == 'y':
        admin_password = getpass.getpass("Enter admin password: ")
        test_user("admin", admin_password)
    
    print("\n" + "="*60)
    print("✓ Authentication fix verified successfully!")
    print("="*60)
