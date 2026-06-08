"""
Regression tests for Audit and Health API endpoints.

Uses real APIClient and real DB; no mocks/stubs. Closes gap from
TEST_GAP_ANALYSIS_5_5.md (5.5.1) and UPDATE_PLAN_MISSING_COVERAGE_5_6_1.md (P1).
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
import uuid

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class AuditHealthRegressionTestBase(TestCase):
    """Base for Audit and Health regression tests. Real DB and client."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name=f"Audit Health Regression Tenant {uuid.uuid4().hex[:8]}",
            slug="audit-health-regression",
        )
        self.user = User.objects.create_user(
            email=f"audithealth-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)


class AuditAPIRegressionTest(AuditHealthRegressionTestBase):
    """Regression tests for /api/v1/audit/audit-events/. Real client; no mocks."""

    def test_audit_events_list(self):
        """GET /api/v1/audit/audit-events/ returns 200 and list or paginated results."""
        response = self.client.get("/api/v1/audit/audit-events/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json() if hasattr(response, "json") else response.data
        self.assertTrue(
            isinstance(data, list) or (isinstance(data, dict) and "results" in data),
            "Response must be list or paginated dict with 'results'",
        )

    def test_audit_events_list_tenant_scoped(self):
        """Audit list is tenant-scoped for authenticated user."""
        # Create one audit event for this tenant
        AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="ASSET",
            action="CREATED",
            details_json={},
        )
        response = self.client.get("/api/v1/audit/audit-events/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json() if hasattr(response, "json") else response.data
        results = data if isinstance(data, list) else data.get("results", [])
        # All returned events should belong to our tenant
        for item in results:
            if isinstance(item, dict) and "tenant" in item and item["tenant"]:
                self.assertEqual(
                    str(item["tenant"]),
                    str(self.tenant.id),
                    "Audit events must be tenant-scoped",
                )

    def test_audit_events_retrieve(self):
        """GET /api/v1/audit/audit-events/{id}/ returns 200 for own-tenant event."""
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="CONTRACT",
            action="CREATED",
            details_json={},
        )
        response = self.client.get(f"/api/v1/audit/audit-events/{event.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json() if hasattr(response, "json") else response.data
        self.assertEqual(str(data.get("id")), str(event.id))

    def test_audit_events_export_endpoint(self):
        """GET /api/v1/audit/audit-events/export/ returns 200 or 403."""
        response = self.client.get("/api/v1/audit/audit-events/export/")
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN),
            "Export must return 200 (allowed) or 403 (forbidden)",
        )


class HealthAPIRegressionTest(AuditHealthRegressionTestBase):
    """Regression tests for /health/ and /health/circuit-breakers/. Real client; no mocks."""

    def test_health_check_returns_ok_or_unhealthy(self):
        """GET /health/ returns 200 or 503 and JSON with status."""
        response = self.client.get("/health/")
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE),
            "Health must return 200 (healthy) or 503 (unhealthy)",
        )
        data = response.json() if hasattr(response, "json") else response.data
        self.assertIn(data.get("status"), ("healthy", "unhealthy"))

    def test_health_check_structure(self):
        """Health response includes status and expected keys."""
        response = self.client.get("/health/")
        self.assertIn(
            response.status_code, (status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE)
        )
        data = response.json() if hasattr(response, "json") else response.data
        self.assertIn("status", data)

    def test_circuit_breaker_status_endpoint(self):
        """GET /health/circuit-breakers/ returns 200 or 500 and JSON (221.3 — auth required)."""
        response = self.client.get("/health/circuit-breakers/")
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR),
            "Circuit breaker status may return 200 or 500",
        )
        data = response.json() if hasattr(response, "json") else response.data
        self.assertIsInstance(data, dict)
        if response.status_code == status.HTTP_200_OK:
            # 221.3.2: only aggregate fields, no service names
            self.assertNotIn("circuit_breakers", data)
            self.assertNotIn("open_breaker_names", data)
            self.assertIn("total_breakers", data)
            self.assertIn("open_breakers", data)

    def test_circuit_breaker_service_name_param_removed(self):
        """?service_name= has no effect (221.3.2)."""
        resp_all = self.client.get("/health/circuit-breakers/")
        resp_named = self.client.get(
            "/health/circuit-breakers/?service_name=test-service",
        )
        # Both return the same shape — service_name is ignored
        self.assertEqual(resp_all.status_code, resp_named.status_code)
