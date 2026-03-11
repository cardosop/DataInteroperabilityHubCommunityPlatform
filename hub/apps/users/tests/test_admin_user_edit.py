"""
Unit tests for Admin User Edit (PUT/PATCH /users/{id}/).

Phase 28.1.1: Tests for roles, status, permissions.
Uses real DB and auth; no mocks/stubs.
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, User, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _unique_slug():
    """Unique slug to avoid deadlocks/collisions when tests run concurrently."""
    return f"tae-{uuid.uuid4().hex[:12]}"


class AdminUserEditTest(TestCase):
    """Tests for PUT/PATCH /api/v1/users/{id}/ — admin user edit."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        slug_a = _unique_slug()
        slug_b = _unique_slug()

        self.tenant_a = Tenant.objects.create(
            name=f"Tenant A {slug_a}",
            slug=slug_a,
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"Tenant B {slug_b}",
            slug=slug_b,
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Platform admin (no tenant)
        self.platform_admin = User.objects.create_user(
            email=f"platform_admin_edit_{slug_a}@example.com",
            password="testpass123",
            is_platform_admin=True,
        )

        # Tenant A admin
        self.tenant_a_admin = User.objects.create_user(
            email=f"tenant_a_admin_edit_{slug_a}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        admin_role_a, _ = Role.objects.get_or_create(
            tenant=self.tenant_a,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.create(user=self.tenant_a_admin, role=admin_role_a)

        # Tenant B admin
        self.tenant_b_admin = User.objects.create_user(
            email=f"tenant_b_admin_edit_{slug_b}@example.com",
            password="testpass123",
            tenant=self.tenant_b,
            status=UserStatus.ACTIVE,
        )
        admin_role_b, _ = Role.objects.get_or_create(
            tenant=self.tenant_b,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.create(user=self.tenant_b_admin, role=admin_role_b)

        # Regular user in Tenant A
        self.regular_user_a = User.objects.create_user(
            email=f"regular_a_edit_{slug_a}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
            display_name="Regular A",
        )
        self.provider_role_a, _ = Role.objects.get_or_create(
            tenant=self.tenant_a,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        UserRole.objects.create(user=self.regular_user_a, role=self.provider_role_a)

        # Consumer role for Tenant A
        self.consumer_role_a, _ = Role.objects.get_or_create(
            tenant=self.tenant_a,
            name="DATA_CONSUMER",
            defaults={"description": "Data Consumer"},
        )

        ensure_tenant_has_active_subscription(self.tenant_a)
        ensure_tenant_has_active_subscription(self.tenant_b)

    def test_put_user_updates_display_name(self):
        """PUT /users/{id}/ with display_name updates user."""
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.put(
            f"/api/v1/users/{self.regular_user_a.id}/",
            {"display_name": "Updated Display Name", "status": "ACTIVE", "role_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["display_name"], "Updated Display Name")
        self.regular_user_a.refresh_from_db()
        self.assertEqual(self.regular_user_a.display_name, "Updated Display Name")

    def test_put_user_updates_status(self):
        """PUT /users/{id}/ with status updates user status."""
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.put(
            f"/api/v1/users/{self.regular_user_a.id}/",
            {"display_name": "Regular A", "status": "SUSPENDED", "role_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "SUSPENDED")
        self.regular_user_a.refresh_from_db()
        self.assertEqual(self.regular_user_a.status, UserStatus.SUSPENDED)

    def test_put_user_updates_roles(self):
        """PUT /users/{id}/ with role_ids replaces user roles."""
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.put(
            f"/api/v1/users/{self.regular_user_a.id}/",
            {
                "display_name": "Regular A",
                "status": "ACTIVE",
                "role_ids": [str(self.consumer_role_a.id)],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("DATA_CONSUMER", response.data["roles"])
        self.assertNotIn("DATA_PROVIDER", response.data["roles"])

        role_names = [
            ur.role.name for ur in UserRole.objects.filter(user=self.regular_user_a)
        ]
        self.assertIn("DATA_CONSUMER", role_names)
        self.assertNotIn("DATA_PROVIDER", role_names)

    def test_put_user_clears_roles_when_empty_list(self):
        """PUT /users/{id}/ with role_ids=[] clears all roles."""
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.put(
            f"/api/v1/users/{self.regular_user_a.id}/",
            {"display_name": "Regular A", "status": "ACTIVE", "role_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["roles"], [])
        role_count = UserRole.objects.filter(user=self.regular_user_a).count()
        self.assertEqual(role_count, 0)

    def test_put_user_multiple_roles(self):
        """PUT /users/{id}/ with multiple role_ids assigns all roles."""
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.put(
            f"/api/v1/users/{self.regular_user_a.id}/",
            {
                "display_name": "Regular A",
                "status": "ACTIVE",
                "role_ids": [
                    str(self.provider_role_a.id),
                    str(self.consumer_role_a.id),
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("DATA_PROVIDER", response.data["roles"])
        self.assertIn("DATA_CONSUMER", response.data["roles"])

    def test_patch_user_partial_update(self):
        """PATCH /users/{id}/ allows partial update."""
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.patch(
            f"/api/v1/users/{self.regular_user_a.id}/",
            {"display_name": "Patched Name"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["display_name"], "Patched Name")
        self.regular_user_a.refresh_from_db()
        self.assertEqual(self.regular_user_a.display_name, "Patched Name")

    def test_patch_user_status_only(self):
        """PATCH /users/{id}/ with status only updates status."""
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.patch(
            f"/api/v1/users/{self.regular_user_a.id}/",
            {"status": "INVITED"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "INVITED")
        self.regular_user_a.refresh_from_db()
        self.assertEqual(self.regular_user_a.status, UserStatus.INVITED)

    def test_regular_user_cannot_edit_returns_403(self):
        """Regular user (no TENANT_ADMIN) cannot edit users — 403."""
        self.client.force_authenticate(user=self.regular_user_a)
        response = self.client.put(
            f"/api/v1/users/{self.tenant_a_admin.id}/",
            {"display_name": "Hacked", "status": "ACTIVE", "role_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", response.data)

    def test_platform_admin_can_edit_any_tenant_user(self):
        """Platform admin can edit user in any tenant."""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.put(
            f"/api/v1/users/{self.regular_user_a.id}/",
            {"display_name": "Edited by Platform Admin", "status": "ACTIVE", "role_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["display_name"], "Edited by Platform Admin")

    def test_put_creates_audit_event(self):
        """PUT /users/{id}/ creates USER_UPDATED audit event."""
        self.client.force_authenticate(user=self.tenant_a_admin)
        self.client.put(
            f"/api/v1/users/{self.regular_user_a.id}/",
            {"display_name": "Audited Update", "status": "ACTIVE", "role_ids": []},
            format="json",
        )
        events = AuditEvent.objects.filter(
            resource_type="USER",
            resource_id=str(self.regular_user_a.id),
            action="USER_UPDATED",
        ).order_by("-timestamp")
        self.assertGreaterEqual(events.count(), 1)

    def test_put_invalid_role_ids_returns_400(self):
        """PUT /users/{id}/ with role from other tenant returns 400."""
        other_role, _ = Role.objects.get_or_create(
            tenant=self.tenant_b,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.put(
            f"/api/v1/users/{self.regular_user_a.id}/",
            {
                "display_name": "Regular A",
                "status": "ACTIVE",
                "role_ids": [str(other_role.id)],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_put_invalid_status_transition_returns_400(self):
        """PUT /users/{id}/ with invalid status transition returns 400."""
        self.regular_user_a.status = UserStatus.DISABLED
        self.regular_user_a.save(update_fields=["status"])
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.put(
            f"/api/v1/users/{self.regular_user_a.id}/",
            {"display_name": "Regular A", "status": "SUSPENDED", "role_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
