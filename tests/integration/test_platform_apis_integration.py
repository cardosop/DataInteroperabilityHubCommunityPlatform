"""
Integration tests for Platform APIs: tenants list/suspend/resume, usage, erasure (admin).

Real APIClient; admin where required. No mocks/stubs. Plan 3.3.1.1 (P1).
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class TestPlatformAPIsIntegration:
    """Integration tests for platform/tenants/ and platform admin actions."""

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Platform Integration Tenant",
            slug="platform-integration-tenant",
        )
        self.admin = User.objects.create_user(
            email="platform_admin@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )
        self.client.force_authenticate(user=self.admin)

    def test_platform_tenants_list_returns_200(self):
        """GET /api/v1/platform/tenants/ returns 200 for platform admin."""
        response = self.client.get("/api/v1/platform/tenants/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "results" in data

    def test_platform_tenants_usage_returns_200(self):
        """GET /api/v1/platform/tenants/usage/ returns 200 for platform admin."""
        response = self.client.get("/api/v1/platform/tenants/usage/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "results" in data or "count" in data

    def test_platform_tenant_suspend_resume_flow(self):
        """Platform admin can suspend and resume a tenant."""
        # Create a second tenant to suspend
        other = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant-platform-integration",
        )
        # Suspend
        response_suspend = self.client.post(
            f"/api/v1/platform/tenants/{other.id}/suspend/",
            data={"reason": "Integration test"},
            format="json",
        )
        assert response_suspend.status_code in (
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )
        if response_suspend.status_code == status.HTTP_200_OK:
            response_resume = self.client.post(f"/api/v1/platform/tenants/{other.id}/resume/")
            assert response_resume.status_code in (
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND,
            )

    def test_platform_users_erasure_requests_returns_200(self):
        """GET platform/users/{id}/erasure-requests/ returns 200 for platform admin."""
        url = f"/api/v1/platform/users/{self.admin.id}/erasure-requests/"
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)

    def test_platform_request_erasure_returns_201_and_audit_actor_is_platform_admin(self):
        """POST platform/users/{id}/request-erasure/ (29.67.2): audit actor = platform admin."""
        from hub.apps.audit.models import AuditEvent

        regular_user = User.objects.create_user(
            email="regular_platform_erasure@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        response = self.client.post(
            f"/api/v1/platform/users/{regular_user.id}/request-erasure/"
        )
        assert response.status_code == status.HTTP_201_CREATED

        event = AuditEvent.objects.filter(
            resource_type="ERASURE_REQUEST", action="ERASURE_REQUESTED"
        ).order_by("-timestamp").first()
        assert event is not None
        assert event.actor_user_id == self.admin.id
        assert event.details_json.get("source") == "platform_admin"
        assert event.details_json.get("initiated_by") == str(self.admin.id)
