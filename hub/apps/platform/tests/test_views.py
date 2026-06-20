"""
Minimal unit tests for Platform Admin views (Gap #2, task 1.5).

Tests permission enforcement (IsPlatformAdmin) and that platform endpoints
respond correctly. Uses real User, Tenant, APIClient; no mocks/stubs.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class TestPlatformTenantViewSetPermissions(TestCase):
    """Platform tenant endpoints require IsPlatformAdmin."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Platform Test Tenant",
            slug="platform-test-tenant",
        )
        self.platform_admin = User.objects.create_user(
            email=f"platform-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=True,
            status=UserStatus.ACTIVE,
        )
        self.regular_user = User.objects.create_user(
            email=f"regular-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            is_platform_admin=False,
            status=UserStatus.ACTIVE,
        )

    def test_platform_tenant_list_requires_platform_admin(self):
        """GET /api/v1/platform/tenants/ returns 403 for non-platform-admin."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get("/api/v1/platform/tenants/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_tenant_list_200_for_platform_admin(self):
        """GET /api/v1/platform/tenants/ returns 200 for platform admin."""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get("/api/v1/platform/tenants/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_platform_tenant_retrieve_requires_platform_admin(self):
        """GET /api/v1/platform/tenants/{id}/ returns 403 for non-platform-admin."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(f"/api/v1/platform/tenants/{self.tenant.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_tenant_retrieve_200_for_platform_admin(self):
        """GET /api/v1/platform/tenants/{id}/ returns 200 for platform admin."""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(f"/api/v1/platform/tenants/{self.tenant.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "platform-test-tenant")

    def test_platform_tenant_usage_requires_platform_admin(self):
        """GET /api/v1/platform/tenants/usage/ returns 403 for non-platform-admin."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get("/api/v1/platform/tenants/usage/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_tenant_usage_200_for_platform_admin(self):
        """GET /api/v1/platform/tenants/usage/ returns 200 for platform admin."""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get("/api/v1/platform/tenants/usage/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertIn("period_start", response.data)
        self.assertIn("period_end", response.data)

    def test_platform_tenant_suspend_returns_200_and_sets_suspended(self):
        """Phase 15: POST suspend sets tenant status to SUSPENDED."""
        from hub.apps.tenants.models import TenantStatus

        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.post(
            f"/api/v1/platform/tenants/{self.tenant.id}/suspend/",
            data={"reason": "Phase 15 test"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], TenantStatus.SUSPENDED)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, TenantStatus.SUSPENDED)

    def test_platform_tenant_suspend_creates_audit_event(self):
        """AUDIT_POLICY 1.10.1: Suspend emits TENANT_SUSPENDED with actor_user = platform admin."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.tenants.models import TenantStatus

        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.post(
            f"/api/v1/platform/tenants/{self.tenant.id}/suspend/",
            data={"reason": "Audit policy test"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = (
            AuditEvent.objects.filter(resource_type="TENANT", action="TENANT_SUSPENDED")
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.actor_user_id, self.platform_admin.id)
        self.assertEqual(str(event.resource_id), str(self.tenant.id))
        self.assertEqual(event.details_json.get("new_status"), TenantStatus.SUSPENDED)

    def test_platform_tenant_resume_returns_200_and_sets_active(self):
        """Phase 15: POST resume sets suspended tenant to ACTIVE."""
        from hub.apps.tenants.models import TenantStatus

        self.tenant.status = TenantStatus.SUSPENDED
        self.tenant.save(update_fields=["status"])
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.post(f"/api/v1/platform/tenants/{self.tenant.id}/resume/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], TenantStatus.ACTIVE)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, TenantStatus.ACTIVE)

    def test_platform_tenant_resume_creates_audit_event(self):
        """AUDIT_POLICY 1.10.1: Resume emits TENANT_REACTIVATED with actor_user = platform admin."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.tenants.models import TenantStatus

        self.tenant.status = TenantStatus.SUSPENDED
        self.tenant.save(update_fields=["status"])
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.post(f"/api/v1/platform/tenants/{self.tenant.id}/resume/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        event = (
            AuditEvent.objects.filter(resource_type="TENANT", action="TENANT_REACTIVATED")
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.actor_user_id, self.platform_admin.id)
        self.assertEqual(str(event.resource_id), str(self.tenant.id))
        self.assertEqual(event.details_json.get("new_status"), TenantStatus.ACTIVE)

    def test_platform_tenant_suspend_resume_flow(self):
        """Phase 15: Full suspend then resume flow."""
        from hub.apps.tenants.models import TenantStatus

        self.client.force_authenticate(user=self.platform_admin)
        # Suspend
        r1 = self.client.post(
            f"/api/v1/platform/tenants/{self.tenant.id}/suspend/",
            data={"reason": "Flow test"},
            format="json",
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, TenantStatus.SUSPENDED)
        # Resume
        r2 = self.client.post(f"/api/v1/platform/tenants/{self.tenant.id}/resume/")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, TenantStatus.ACTIVE)


class TestPlatformUserViewSetPermissions(TestCase):
    """Platform user endpoints require IsPlatformAdmin."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Platform User Test Tenant",
            slug="platform-user-test-tenant",
        )
        self.platform_admin = User.objects.create_user(
            email=f"platform-admin2-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=True,
            status=UserStatus.ACTIVE,
        )
        self.regular_user = User.objects.create_user(
            email=f"regular2-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            is_platform_admin=False,
            status=UserStatus.ACTIVE,
        )

    def test_platform_user_list_requires_platform_admin(self):
        """GET /api/v1/platform/users/ returns 403 for non-platform-admin."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get("/api/v1/platform/users/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_user_list_200_for_platform_admin(self):
        """GET /api/v1/platform/users/ returns 200 for platform admin."""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get("/api/v1/platform/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_platform_user_retrieve_requires_platform_admin(self):
        """GET /api/v1/platform/users/{id}/ returns 403 for non-platform-admin."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(f"/api/v1/platform/users/{self.regular_user.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_user_retrieve_200_for_platform_admin(self):
        """GET /api/v1/platform/users/{id}/ returns 200 for platform admin."""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(f"/api/v1/platform/users/{self.regular_user.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("id", response.data)

    def test_platform_request_erasure_audit_actor_is_platform_admin(self):
        """Task 29.67.2.3: Platform admin request_erasure → audit actor_user = platform admin."""
        from hub.apps.audit.models import AuditEvent

        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.post(
            f"/api/v1/platform/users/{self.regular_user.id}/request-erasure/"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        event = (
            AuditEvent.objects.filter(resource_type="ERASURE_REQUEST", action="ERASURE_REQUESTED")
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.actor_user_id, self.platform_admin.id)
        self.assertEqual(event.details_json.get("source"), "platform_admin")
        self.assertEqual(event.details_json.get("initiated_by"), str(self.platform_admin.id))

    def test_platform_request_erasure_creates_erasure_completed_audit_event(self):
        """AUDIT_POLICY 1.10.1: Platform request_erasure → execute_erasure emits ERASURE_COMPLETED."""
        from hub.apps.audit.models import AuditEvent

        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.post(
            f"/api/v1/platform/users/{self.regular_user.id}/request-erasure/"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        event = (
            AuditEvent.objects.filter(resource_type="ERASURE_REQUEST", action="ERASURE_COMPLETED")
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(event)
        assert event is not None
        self.assertIsNone(event.actor_user_id, "ERASURE_COMPLETED is system action")
