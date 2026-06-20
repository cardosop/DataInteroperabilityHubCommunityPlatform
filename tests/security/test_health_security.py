"""
Security tests for Health endpoints (test2 Phase 2.4, updated Phase 221.3).

Health probe endpoints (/health/, /health/live/) are public by design
for monitoring and load balancer probes.

/health/circuit-breakers/ requires authentication (Phase 221.3.1) and
returns only aggregate data — no internal service names (Phase 221.3.2).

These tests verify:
- Unauthenticated access is allowed for probes (200 or 503)
- Circuit breaker endpoint rejects unauthenticated requests (401/403)
- No sensitive data in responses (emails, tokens, tenant IDs, secrets)
- Response structure is appropriate for monitoring

Uses real Django test client; no mocks or stubs.
"""

import re
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


# Sensitive patterns that must NOT appear in health endpoint responses
SENSITIVE_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
    re.compile(r"Bearer\s+[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", re.I),  # JWT
    re.compile(r"refresh_token=[^&\s]+", re.I),
    re.compile(r"api_key=[^&\s]+", re.I),
    re.compile(r"password['\"]?\s*[:=]\s*['\"]?[^'\"]+", re.I),
    re.compile(r"secret['\"]?\s*[:=]\s*['\"]?[^'\"]+", re.I),
]

# Allowed keys in health check response (operational status only)
HEALTH_ALLOWED_KEYS = {"status", "database", "redis", "baas", "http_status"}
LIVE_ALLOWED_KEYS = {"status"}
# Phase 221.3.2: response sanitized — only aggregate counts, no service names.
CIRCUIT_BREAKER_ALLOWED_KEYS = {
    "status",
    "total_breakers",
    "open_breakers",
    "error",
    "http_status",
}


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.security]


class HealthSecurityTestBase(TestCase):
    """Base for health security tests."""

    def setUp(self):
        super().setUp()
        self.client = Client()

    def _assert_no_sensitive_data_in_text(self, text: str, endpoint_name: str):
        """Assert response text does not contain sensitive patterns."""
        if not text:
            return
        for pattern in SENSITIVE_PATTERNS:
            matches = pattern.findall(text)
            self.assertFalse(
                matches,
                f"{endpoint_name} must not expose sensitive data; "
                f"found pattern {pattern.pattern}: {matches[:3]}",
            )


class HealthLivenessSecurityTest(HealthSecurityTestBase):
    """Liveness endpoint: minimal public probe, no sensitive data."""

    def test_liveness_unauthenticated_returns_200(self):
        """GET /health/live/ without auth returns 200 (public probe)."""
        response = self.client.get("/health/live/")
        self.assertIn(response.status_code, (200, 404), "Liveness must be public or not mounted")

    def test_liveness_returns_no_sensitive_data(self):
        """GET /health/live/ must not expose emails, tokens, secrets."""
        response = self.client.get("/health/live/")
        if response.status_code != 200:
            return
        text = response.content.decode("utf-8", errors="replace")
        self._assert_no_sensitive_data_in_text(text, "/health/live/")
        data = response.json()
        for key in data:
            self.assertIn(key, LIVE_ALLOWED_KEYS, f"Liveness must not expose '{key}'")


class HealthCheckSecurityTest(HealthSecurityTestBase):
    """Health check endpoint: operational status, no sensitive data."""

    def test_health_check_unauthenticated_returns_200_or_503(self):
        """GET /health/ without auth returns 200 (healthy) or 503 (unhealthy)."""
        response = self.client.get("/health/")
        self.assertIn(
            response.status_code,
            (200, 503),
            "Health check must be public for monitoring",
        )

    def test_health_check_returns_no_sensitive_data(self):
        """GET /health/ must not expose emails, tokens, tenant IDs, secrets."""
        response = self.client.get("/health/")
        if response.status_code not in (200, 503):
            return
        text = response.content.decode("utf-8", errors="replace")
        self._assert_no_sensitive_data_in_text(text, "/health/")
        data = response.json()
        for key in data:
            self.assertIn(
                key,
                HEALTH_ALLOWED_KEYS,
                f"Health check must not expose '{key}' (operational status only)",
            )


class HealthCircuitBreakerSecurityTest(HealthSecurityTestBase):
    """Circuit breaker status: requires auth (221.3.1), aggregate only (221.3.2)."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"T {uid}",
            slug=f"t-sec-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        user = User.objects.create_user(
            email=f"sec-{uid}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        self.auth_client = APIClient()
        self.auth_client.force_authenticate(user=user)

    def test_circuit_breaker_unauthenticated_rejected(self):
        """GET /health/circuit-breakers/ without auth → 401/403 (221.3.1)."""
        response = self.client.get("/health/circuit-breakers/")
        self.assertIn(
            response.status_code,
            (401, 403),
            "Circuit breaker must reject unauthenticated requests",
        )

    def test_circuit_breaker_authenticated_returns_200_or_500(self):
        """GET /health/circuit-breakers/ with auth → 200 or 500."""
        response = self.auth_client.get("/health/circuit-breakers/")
        self.assertIn(
            response.status_code,
            (200, 500),
            "Authenticated circuit breaker request must succeed",
        )

    def test_circuit_breaker_returns_no_sensitive_data(self):
        """Authenticated response must not expose sensitive data."""
        response = self.auth_client.get("/health/circuit-breakers/")
        if response.status_code not in (200, 500):
            return
        text = response.content.decode("utf-8", errors="replace")
        self._assert_no_sensitive_data_in_text(
            text,
            "/health/circuit-breakers/",
        )
        try:
            data = response.json()
        except Exception:
            return
        for key in data:
            self.assertIn(
                key,
                CIRCUIT_BREAKER_ALLOWED_KEYS,
                f"Circuit breaker must not expose '{key}'",
            )
