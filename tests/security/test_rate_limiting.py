"""Phase 98: Rate limiting enforcement tests."""
import uuid
import pytest
from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from hub.apps.auth.views import _check_ip_rate_limit, _check_password_reset_rate_limit

pytestmark = pytest.mark.security


class RateLimitingTest(TestCase):
    """Verify rate limits are enforced."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_ip_login_rate_limit_enforced(self):
        """Exceeding per-IP login rate limit returns False."""
        ip = "192.0.2.99"
        # Default is 10 per minute
        for i in range(10):
            self.assertTrue(_check_ip_rate_limit(ip), f"Request {i+1} should pass")
        # 11th should be blocked
        self.assertFalse(_check_ip_rate_limit(ip))

    def test_password_reset_rate_limit_enforced(self):
        """Exceeding per-email reset limit returns False."""
        email = f"ratelimit-{uuid.uuid4().hex[:8]}@example.com"
        for i in range(5):
            self.assertTrue(
                _check_password_reset_rate_limit(email),
                f"Reset {i+1} should pass",
            )
        # 6th should be blocked
        self.assertFalse(_check_password_reset_rate_limit(email))

    def test_login_endpoint_returns_429(self):
        """Login endpoint returns 429 after exceeding rate limit."""
        client = APIClient()
        ip = "10.99.99.99"
        # Exhaust rate limit
        for _ in range(12):
            client.post(
                "/api/v1/auth/login/",
                {"email": "nonexistent@example.com", "password": "wrong"},
                format="json",
                REMOTE_ADDR=ip,
            )
        # Next attempt should be 429
        response = client.post(
            "/api/v1/auth/login/",
            {"email": "nonexistent@example.com", "password": "wrong"},
            format="json",
            REMOTE_ADDR=ip,
        )
        self.assertEqual(response.status_code, 429)
