#!/usr/bin/env python3
"""
Script to set up tenant and API key for SDK tests.

This script:
1. Creates or gets a tenant for SDK tests
2. Assigns the test user to the tenant
3. Creates an API key for the user
4. Prints the API key for use in tests
"""

import os
import sys

import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
TEST_USER_EMAIL = os.getenv("TEST_USER_EMAIL", "sdk-test@example.com")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "TestPass123!")


def main():
    print("Setting up SDK test API key...")

    # Step 1: Login as test user
    print(f"1. Logging in as {TEST_USER_EMAIL}...")
    login_response = requests.post(
        f"{API_BASE_URL}/auth/login/",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
        timeout=10,
    )

    if login_response.status_code != 200:
        print(f"   ✗ Login failed: {login_response.status_code}")
        print(f"   Response: {login_response.text[:200]}")
        sys.exit(1)

    token = login_response.json().get("access_token")
    if not token:
        print("   ✗ No access token in response")
        sys.exit(1)

    print("   ✓ Login successful")
    headers = {"Authorization": f"Bearer {token}"}

    # Step 2: Check if user has a tenant
    print("2. Checking user tenant...")
    user_info_response = requests.get(f"{API_BASE_URL}/auth/me/", headers=headers, timeout=10)

    if user_info_response.status_code == 200:
        user_data = user_info_response.json()
        tenant_id = user_data.get("tenant_id")
        if tenant_id:
            print(f"   ✓ User has tenant: {tenant_id}")
        else:
            print("   ✗ User does not have a tenant")
            print("   Note: User needs a tenant to create API keys.")
            print("   You may need to:")
            print("   - Create a tenant via Django admin or management command")
            print("   - Or assign the user to an existing tenant")
            sys.exit(1)
    else:
        print(f"   ✗ Could not get user info: {user_info_response.status_code}")
        sys.exit(1)

    # Step 3: Try to create API key
    print("3. Creating API key...")
    api_key_response = requests.post(
        f"{API_BASE_URL}/auth/api-keys/",
        json={"name": "SDK Test API Key"},
        headers=headers,
        timeout=10,
    )

    if api_key_response.status_code == 201:
        api_key_data = api_key_response.json()
        api_key = api_key_data.get("api_key")
        if api_key:
            print("   ✓ API key created successfully")
            print(f"\n{'=' * 60}")
            print("TEST_API_KEY for use in tests:")
            print(f"{'=' * 60}")
            print(api_key)
            print(f"{'=' * 60}")
            print("\nTo use this in tests, run:")
            print(f"export TEST_API_KEY='{api_key}'")
            return api_key
        else:
            print("   ✗ API key not in response")
            print(f"   Response: {api_key_response.text[:200]}")
            sys.exit(1)
    else:
        print(f"   ✗ API key creation failed: {api_key_response.status_code}")
        print(f"   Response: {api_key_response.text[:200]}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        api_key = main()
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
