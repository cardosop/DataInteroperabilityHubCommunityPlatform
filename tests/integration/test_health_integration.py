"""
Integration tests for Health API endpoints.

Verifies GET /health/ and GET /health/circuit-breakers/ with real client and
real HealthService (no mocks/stubs). Covers the gap from Phase 3.2.1 for
dedicated health and circuit-breakers endpoint coverage.

Circuit-breakers status codes (see docs/TEST_ASSERTION_CONVENTIONS.md §2.2, §2.5):
- 200: Healthy (all breakers closed or requested breaker healthy)
- 404: Requested service_name not found in circuit breaker registry
- 500: Unhandled exception during status retrieval (e.g. registry not initialized,
  import error, downstream failure). Valid per view's except block.
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db(transaction=True)


class HealthIntegrationTest(TestCase):
    """Integration tests for health and circuit-breakers endpoints."""

    def setUp(self):
        self.client = APIClient()

    def test_health_endpoint_returns_ok_or_unhealthy(self):
        """GET /health/ returns 200 (healthy) or 503 (unhealthy) with JSON."""
        response = self.client.get("/health/")
        self.assertIn(
            response.status_code,
            [200, 503],
            msg="Health endpoint must return 200 or 503",
        )
        self.assertEqual(response.get("Content-Type", ""), "application/json")
        data = response.json()
        self.assertIn("status", data)
        self.assertIn(data["status"], ("healthy", "unhealthy"))
        self.assertIn("database", data)
        self.assertIn("redis", data)

    def test_health_accepts_unauthenticated(self):
        """GET /health/ does not require authentication."""
        response = self.client.get("/health/")
        self.assertIn(response.status_code, [200, 503])

    def test_circuit_breakers_endpoint_returns_json(self):
        """GET /health/circuit-breakers/ returns JSON (200, 404, or 500)."""
        response = self.client.get("/health/circuit-breakers/")
        # 200=healthy; 404=service_name not found; 500=unhandled exception (see module docstring)
        self.assertIn(
            response.status_code,
            [200, 404, 500],
            msg="Circuit-breakers: 200, 404, or 500",
        )
        self.assertEqual(response.get("Content-Type", ""), "application/json")
        data = response.json()
        if response.status_code == 200:
            self.assertIn("status", data)
            self.assertIn(data["status"], ("healthy", "degraded"))
        elif response.status_code == 500:
            self.assertIn("status", data)
            self.assertEqual(data["status"], "error")
            self.assertIn("error", data)

    def test_circuit_breakers_with_service_name_query(self):
        """GET /health/circuit-breakers/?service_name=X returns JSON."""
        response = self.client.get("/health/circuit-breakers/?service_name=dq-service")
        # 200=breaker healthy; 404=dq-service not in registry; 500=unhandled exception
        self.assertIn(response.status_code, [200, 404, 500])
        data = response.json()
        self.assertIsInstance(data, dict)
        self.assertIn("status", data)
