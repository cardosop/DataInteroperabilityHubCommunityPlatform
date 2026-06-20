"""
Phase 221.3 — Circuit breaker endpoint hardening tests (TDD).

Covers:
  - 221.3.1  /health/circuit-breakers/ requires authentication
  - 221.3.2  service_name query param removed; response sanitized
             (no internal service names exposed)

Uses real Django test client + DRF APIClient; no mocks/stubs.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class CircuitBreakerAuthGateTest(TestCase):
    """221.3.1: /health/circuit-breakers/ must require authentication."""

    def setUp(self):
        self.anon_client = Client()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-cb-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"cbtest-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.auth_client = APIClient()
        self.auth_client.force_authenticate(user=self.user)

    # ---- Unauthenticated access must be rejected ----

    def test_unauthenticated_returns_401_or_403(self):
        """Unauthenticated GET must be rejected (401 or 403)."""
        response = self.anon_client.get("/health/circuit-breakers/")
        self.assertIn(
            response.status_code,
            (401, 403),
            f"Expected 401/403 for unauthenticated, got {response.status_code}",
        )

    # ---- Authenticated access should succeed ----

    def test_authenticated_returns_200_or_500(self):
        """Authenticated GET returns 200 (healthy) or 500 (breaker error)."""
        response = self.auth_client.get("/health/circuit-breakers/")
        self.assertIn(
            response.status_code,
            (200, 500),
            f"Expected 200/500 for authenticated, got {response.status_code}",
        )

    # ---- Public health probes remain unauthenticated ----

    def test_liveness_remains_public(self):
        """GET /health/live/ must stay public (K8s liveness probe)."""
        response = self.anon_client.get("/health/live/")
        self.assertEqual(response.status_code, 200)

    def test_health_check_remains_public(self):
        """GET /health/ must stay public (K8s readiness probe)."""
        response = self.anon_client.get("/health/")
        self.assertIn(response.status_code, (200, 503))


class CircuitBreakerResponseSanitizationTest(TestCase):
    """221.3.2: Response must not expose internal service architecture."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-cb2-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"cbtest2-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    # ---- service_name query param must be ignored ----

    def test_service_name_param_ignored(self):
        """?service_name= must have no effect (removed in 221.3.2)."""
        response_all = self.client.get("/health/circuit-breakers/")
        response_named = self.client.get("/health/circuit-breakers/?service_name=anything")
        # Both should return the same top-level keys
        if response_all.status_code == 200 and response_named.status_code == 200:
            data_all = response_all.data
            data_named = response_named.data
            self.assertEqual(
                set(data_all.keys()),
                set(data_named.keys()),
                "service_name param should have no effect on response shape",
            )

    # ---- Response must NOT contain service names ----

    def test_response_does_not_contain_circuit_breakers_dict(self):
        """The 'circuit_breakers' dict (keyed by service name) must be absent."""
        response = self.client.get("/health/circuit-breakers/")
        if response.status_code == 200:
            data = response.data
            self.assertNotIn(
                "circuit_breakers",
                data,
                "'circuit_breakers' dict exposes internal service names",
            )

    def test_response_does_not_contain_open_breaker_names(self):
        """The 'open_breaker_names' list must be absent."""
        response = self.client.get("/health/circuit-breakers/")
        if response.status_code == 200:
            data = response.data
            self.assertNotIn(
                "open_breaker_names",
                data,
                "'open_breaker_names' list exposes internal service names",
            )

    def test_response_does_not_contain_circuit_breaker_singular(self):
        """The 'circuit_breaker' key (single-service detail) must be absent."""
        response = self.client.get("/health/circuit-breakers/")
        if response.status_code == 200:
            data = response.data
            self.assertNotIn(
                "circuit_breaker",
                data,
                "'circuit_breaker' key should not be present (single-service lookup removed)",
            )

    # ---- Response structure: only aggregate data ----

    def test_response_contains_only_aggregate_fields(self):
        """Response must contain only status + aggregate counts."""
        response = self.client.get("/health/circuit-breakers/")
        if response.status_code == 200:
            data = response.data
            allowed_keys = {"status", "total_breakers", "open_breakers"}
            self.assertTrue(
                set(data.keys()).issubset(allowed_keys),
                f"Response keys {set(data.keys())} must be subset of {allowed_keys}",
            )
            self.assertIn("status", data)
            self.assertIn("total_breakers", data)
            self.assertIn("open_breakers", data)
            self.assertIsInstance(data["total_breakers"], int)
            self.assertIsInstance(data["open_breakers"], int)
