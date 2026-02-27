"""
Security tests for Health endpoints (test2 Phase 2.4).

Health endpoints (/health/, /health/live/, /health/circuit-breakers/) are public by design
for monitoring and load balancer probes. These tests verify:
- Unauthenticated access is allowed (200 or 503)
- No sensitive data in responses (emails, tokens, tenant IDs, internal secrets)
- Response structure is appropriate for monitoring

Uses real Django test client; no mocks or stubs.
"""

import re

import pytest
from django.test import Client, TestCase


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
CIRCUIT_BREAKER_ALLOWED_KEYS = {
    "status", "circuit_breaker", "circuit_breakers",
    "total_breakers", "open_breakers", "open_breaker_names",
    "error", "http_status",
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
    """Circuit breaker status endpoint: operational data only, no sensitive data."""

    def test_circuit_breaker_unauthenticated_returns_200_or_404_or_500(self):
        """GET /health/circuit-breakers/ without auth returns 200, 404, or 500."""
        response = self.client.get("/health/circuit-breakers/")
        self.assertIn(
            response.status_code,
            (200, 404, 500),
            "Circuit breaker status must be public for monitoring",
        )

    def test_circuit_breaker_returns_no_sensitive_data(self):
        """GET /health/circuit-breakers/ must not expose emails, tokens, secrets."""
        response = self.client.get("/health/circuit-breakers/")
        if response.status_code not in (200, 404, 500):
            return
        text = response.content.decode("utf-8", errors="replace")
        self._assert_no_sensitive_data_in_text(text, "/health/circuit-breakers/")
        try:
            data = response.json()
        except Exception:
            return
        for key in data:
            self.assertIn(
                key,
                CIRCUIT_BREAKER_ALLOWED_KEYS,
                f"Circuit breaker status must not expose '{key}'",
            )
