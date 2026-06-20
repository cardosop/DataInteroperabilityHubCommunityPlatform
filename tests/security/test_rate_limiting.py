"""Phase 98: Rate limiting enforcement tests."""

import uuid
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from hub.apps.auth.views import _check_ip_rate_limit, _check_password_reset_rate_limit
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

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
            self.assertTrue(_check_ip_rate_limit(ip), f"Request {i + 1} should pass")
        # 11th should be blocked
        self.assertFalse(_check_ip_rate_limit(ip))

    def test_password_reset_rate_limit_enforced(self):
        """Exceeding per-email reset limit returns False."""
        email = f"ratelimit-{uuid.uuid4().hex[:8]}@example.com"
        for i in range(5):
            self.assertTrue(
                _check_password_reset_rate_limit(email),
                f"Reset {i + 1} should pass",
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


# ── Phase 277.4.6 — Retry-After header verification ──────────────


@override_settings(SEARCH_RATE_LIMIT_PER_MIN="3/min")
class TestRetryAfterHeader(TestCase):
    """Phase 277.4.6 — throttled requests return Retry-After header."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"RA-{uid}",
            slug=f"ra-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"ra-{uid}@meshant.test",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("hub.apps.search.views.UnifiedSearchView._fts_query")
    def test_retry_after_header_present(self, mock_fts):
        """When throttled, Retry-After header is present and positive."""
        mock_fts.return_value = []
        for _ in range(3):
            self.client.get("/api/search/?q=test")
        resp = self.client.get("/api/search/?q=test")
        assert resp.status_code == 429
        assert "Retry-After" in resp, "Retry-After header must be present on 429"
        retry_after = int(resp.get("Retry-After", "0"))
        assert retry_after > 0, f"Retry-After must be positive, got {retry_after}"
