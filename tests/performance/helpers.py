"""
Helper utilities for performance tests
"""

import os
import random
import time

import requests


class PerformanceTestHelper:
    """Helper class for performance test setup and utilities"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("API_BASE_URL", "http://localhost:8000")
        self.api_base = f"{self.base_url}/api/v1"
        self._users_cache: dict[str, dict] = {}
        self._test_password = "perf-test-password-123"

    def create_test_tenant_and_user(self, tenant_name: str = None, user_email: str = None) -> dict:
        """
        Create a test tenant and user for performance testing via API.

        Returns dict with tenant, user, and access_token.
        """
        # Generate unique names if not provided
        if not tenant_name:
            tenant_name = f"perf-tenant-{int(time.time())}-{random.randint(1000, 9999)}"
        if not user_email:
            user_email = f"perf-user-{int(time.time())}-{random.randint(1000, 9999)}@example.com"

        # Check cache first
        cache_key = f"{tenant_name}:{user_email}"
        if cache_key in self._users_cache:
            return self._users_cache[cache_key]

        # Use environment variables for test user credentials
        default_email = os.getenv("PERF_TEST_USER_EMAIL", "perf-test@example.com")
        default_password = os.getenv("PERF_TEST_USER_PASSWORD", "perf-test-password-123")

        # Try to login with provided or default credentials
        login_result = self.login(default_email, default_password)
        if login_result and login_result.get("access_token"):
            result = {
                "tenant_name": tenant_name,
                "user_email": default_email,
                "access_token": login_result["access_token"],
                "headers": login_result["headers"],
            }
            self._users_cache[cache_key] = result
            return result

        # If login fails, raise an error with helpful message
        error_msg = (
            f"Could not login test user '{default_email}'. "
            "Please ensure:\n"
            "1. Test user exists (run: python tests/performance/setup_test_users.py)\n"
            "2. API server is running\n"
            "3. Credentials are correct (set PERF_TEST_USER_EMAIL and PERF_TEST_USER_PASSWORD)"
        )
        raise Exception(error_msg)

    def get_auth_headers(self, access_token: str) -> dict[str, str]:
        """Get authentication headers for API requests"""
        return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    def login(self, email: str, password: str) -> dict | None:
        """Login and get access token"""
        url = f"{self.api_base}/auth/login/"
        try:
            response = requests.post(url, json={"email": email, "password": password}, timeout=10)

            if response.status_code == 200:
                data = response.json()
                access_token = data.get("access_token")
                if access_token:
                    return {
                        "access_token": access_token,
                        "headers": self.get_auth_headers(access_token),
                    }
        except Exception as e:
            # Log error for debugging
            print(f"Login error: {e}")
        return None

    def create_test_file_data(self, size_mb: int = 1) -> bytes:
        """Generate test file data of specified size"""
        # Generate deterministic test data
        chunk = b"0" * 1024  # 1KB chunk
        data = b""
        for _ in range(size_mb * 1024):
            data += chunk
        return data

    def calculate_percentiles(self, values: list, percentiles: list = [50, 95, 99]) -> dict:
        """Calculate percentile values from a list"""
        if not values:
            return {f"p{p}": 0 for p in percentiles}

        sorted_values = sorted(values)
        result = {}
        for p in percentiles:
            index = int(len(sorted_values) * p / 100)
            if index >= len(sorted_values):
                index = len(sorted_values) - 1
            result[f"p{p}"] = sorted_values[index]
        return result
