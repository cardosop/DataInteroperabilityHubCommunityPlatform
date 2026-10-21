"""
Integration tests for Health API endpoints.

Verifies GET /health/ and GET /health/circuit-breakers/ with real client and
real HealthService (no mocks/stubs). Covers the gap from Phase 3.2.1 for
dedicated health and circuit-breakers endpoint coverage.

Phase 221.3 update:
- /health/circuit-breakers/ now requires authentication (221.3.1).
- ?service_name= query param removed; response is aggregate-only (221.3.2).

Circuit-breakers status codes:
- 200: Healthy (all breakers closed)
- 500: Unhandled exception during status retrieval
- 401/403: Unauthenticated (rejected by IsAuthenticated permission)
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class HealthIntegrationTest(TestCase):
    """Integration tests for health and circuit-breakers endpoints."""

    def setUp(self):
        self.anon_client = APIClient()
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"T {uid}",
            slug=f"t-hi-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        user = User.objects.create_user(
            email=f"hi-{uid}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        self.auth_client = APIClient()
        self.auth_client.force_authenticate(user=user)

    def test_health_endpoint_returns_ok_or_unhealthy(self):
        """GET /health/ returns 200 (healthy) or 503 (unhealthy) with JSON."""
        response = self.anon_client.get("/health/")
        self.assertIn(
            response.status_code,
            [200, 503],
            msg="Health endpoint must return 200 or 503",
        )
        self.assertEqual(
            response.get("Content-Type", ""),
            "application/json",
        )
        data = response.json()
        self.assertIn("status", data)
        self.assertIn(data["status"], ("healthy", "unhealthy"))
        self.assertIn("database", data)
        self.assertIn("redis", data)

    def test_health_accepts_unauthenticated(self):
        """GET /health/ does not require authentication."""
        response = self.anon_client.get("/health/")
        self.assertIn(response.status_code, [200, 503])

    def test_circuit_breakers_rejects_unauthenticated(self):
        """GET /health/circuit-breakers/ without auth → 401/403 (221.3.1)."""
        response = self.anon_client.get("/health/circuit-breakers/")
        self.assertIn(
            response.status_code,
            [401, 403],
            msg="Circuit-breakers must reject unauthenticated",
        )

    def test_circuit_breakers_authenticated_returns_json(self):
        """GET /health/circuit-breakers/ with auth → 200 or 500."""
        response = self.auth_client.get("/health/circuit-breakers/")
        self.assertIn(
            response.status_code,
            [200, 500],
            msg="Circuit-breakers: 200 or 500 when authenticated",
        )
        data = response.json()
        if response.status_code == 200:
            self.assertIn("status", data)
            self.assertIn(data["status"], ("healthy", "degraded"))
            # 221.3.2: aggregate only, no service names
            self.assertNotIn("circuit_breakers", data)
            self.assertNotIn("open_breaker_names", data)
            self.assertIn("total_breakers", data)
            self.assertIn("open_breakers", data)
        elif response.status_code == 500:
            self.assertIn("status", data)
            self.assertEqual(data["status"], "error")
            self.assertIn("error", data)

    def test_circuit_breakers_service_name_param_ignored(self):
        """?service_name= has no effect (221.3.2)."""
        resp = self.auth_client.get(
            "/health/circuit-breakers/?service_name=dq-service",
        )
        self.assertIn(resp.status_code, [200, 500])
        if resp.status_code == 200:
            data = resp.json()
            # Must still be aggregate — no single-service detail
            self.assertNotIn("circuit_breaker", data)
            self.assertIn("total_breakers", data)
