"""
Integration tests for Audit API: list and export audit-events.

Uses real APIClient and real DB (AuditEvent). Filter by tenant and time range.
Real services (no mocks/stubs). Plan: INTEGRATION_TEST_UPDATE_PLAN 3.3.1.1 (P1).
"""

from datetime import timedelta

import pytest

pytestmark = pytest.mark.slow
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant
import uuid

pytestmark = pytest.mark.django_db(transaction=True)


class AuditAPIsComprehensiveIntegrationTest:
    """Integration tests for audit-events API. Real client + real DB; no mocks."""

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name=f"Audit Integration Tenant {uuid.uuid4().hex[:8]}",
            slug=f"audit-integration-tenant-{uuid.uuid4().hex[:8]}",
        )
        from django.contrib.auth import get_user_model

        from hub.apps.users.models import UserStatus

        User = get_user_model()
        self.user = User.objects.create_user(
            email=f"audit_integ-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

    def test_audit_events_list_returns_200_and_list_or_paginated(self):
        """GET /api/v1/audit/audit-events/ returns 200 and list or paginated."""
        response = self.client.get("/api/v1/audit/audit-events/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "results" in data

    def test_audit_events_list_tenant_scoped(self):
        """Audit list is tenant-scoped for authenticated user."""
        AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="ASSET",
            action="CREATED",
            details_json={},
        )
        response = self.client.get("/api/v1/audit/audit-events/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data if isinstance(data, list) else data.get("results", [])
        for item in results:
            if isinstance(item, dict) and item.get("tenant"):
                assert str(item["tenant"]) == str(self.tenant.id)

    def test_audit_events_filter_by_time_range(self):
        """Filter audit-events by start_date/end_date (time range)."""
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="CONTRACT",
            action="CREATED",
            details_json={},
        )
        start = (event.timestamp - timedelta(hours=1)).isoformat()
        end = (event.timestamp + timedelta(hours=1)).isoformat()
        response = self.client.get(
            "/api/v1/audit/audit-events/",
            data={"start_date": start, "end_date": end},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data if isinstance(data, list) else data.get("results", [])
        ids = [r.get("id") for r in results if isinstance(r, dict)]
        assert str(event.id) in ids

    def test_audit_events_filter_by_resource_type(self):
        """Filter audit-events by resource_type."""
        AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="CONTRACT",
            action="CREATED",
            details_json={},
        )
        url = "/api/v1/audit/audit-events/?resource_type=CONTRACT"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data if isinstance(data, list) else data.get("results", [])
        for item in results:
            assert item.get("resource_type") == "CONTRACT"

    def test_audit_events_retrieve_by_id(self):
        """GET audit-events/{id}/ returns 200 for own-tenant event."""
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="CONTRACT",
            action="CREATED",
            details_json={},
        )
        response = self.client.get(f"/api/v1/audit/audit-events/{event.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert str(response.json().get("id")) == str(event.id)

    def test_audit_events_export_returns_200_or_403(self):
        """GET audit-events/export/ returns 200 (allowed) or 403 (forbidden)."""
        response = self.client.get("/api/v1/audit/audit-events/export/")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        )
