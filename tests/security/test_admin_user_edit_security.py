"""
Security tests for Admin User Edit (PUT/PATCH /users/{id}/).

Phase 28.1.3: Tenant isolation, role escalation prevention.
Uses real DB and auth; no mocks/stubs.
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, User, UserRole, UserStatus

pytestmark = [pytest.mark.django_db(transaction=True)]


class TestAdminUserEditTenantIsolation:
    """Tenant isolation: tenant admin cannot edit users in other tenants."""

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        """Set up two tenants with admins and users."""
        self.client = APIClient()
        self.slug_a = f"sec-a-{uuid.uuid4().hex[:10]}"
        self.slug_b = f"sec-b-{uuid.uuid4().hex[:10]}"

        self.tenant_a = Tenant.objects.create(
            name=f"Security Tenant A {self.slug_a}",
            slug=self.slug_a,
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"Security Tenant B {self.slug_b}",
            slug=self.slug_b,
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant_a)
        ensure_tenant_has_active_subscription(self.tenant_b)

        admin_role_a, _ = Role.objects.get_or_create(
            tenant=self.tenant_a,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        self.tenant_a_admin = User.objects.create_user(
            email=f"sec_admin_a_edit_{self.slug_a}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.tenant_a_admin, role=admin_role_a)

        self.tenant_b_user = User.objects.create_user(
            email=f"sec_user_b_edit_{self.slug_b}@example.com",
            password="testpass123",
            tenant=self.tenant_b,
            status=UserStatus.ACTIVE,
            display_name="User B",
        )

    def test_tenant_admin_cannot_edit_user_in_other_tenant(self):
        """Tenant A admin cannot PUT/PATCH user in Tenant B — 404."""
        self.client.force_authenticate(user=self.tenant_a_admin)

        put_resp = self.client.put(
            f"/api/v1/users/{self.tenant_b_user.id}/",
            {"display_name": "Hacked", "status": "ACTIVE", "role_ids": []},
            format="json",
        )
        assert put_resp.status_code == status.HTTP_404_NOT_FOUND

        patch_resp = self.client.patch(
            f"/api/v1/users/{self.tenant_b_user.id}/",
            {"display_name": "Hacked"},
            format="json",
        )
        assert patch_resp.status_code == status.HTTP_404_NOT_FOUND

        # Verify user unchanged
        self.tenant_b_user.refresh_from_db()
        assert self.tenant_b_user.display_name == "User B"

    def test_tenant_admin_cannot_assign_cross_tenant_role(self):
        """Tenant B admin cannot edit user in Tenant A — 404 (user not in queryset)."""
        admin_role_b, _ = Role.objects.get_or_create(
            tenant=self.tenant_b,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        tenant_b_admin = User.objects.create_user(
            email=f"sec_admin_b_edit_{self.slug_b}@example.com",
            password="testpass123",
            tenant=self.tenant_b,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=tenant_b_admin, role=admin_role_b)

        user_in_a = User.objects.create_user(
            email=f"sec_user_a_edit_{self.slug_a}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        role_a, _ = Role.objects.get_or_create(
            tenant=self.tenant_a,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.create(user=user_in_a, role=role_a)

        # Tenant B admin tries to assign Tenant B role to Tenant A user — 404 (user not in queryset)
        self.client.force_authenticate(user=tenant_b_admin)
        resp = self.client.put(
            f"/api/v1/users/{user_in_a.id}/",
            {
                "display_name": "User A",
                "status": "ACTIVE",
                "role_ids": [str(admin_role_b.id)],
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestAdminUserEditRoleEscalation:
    """Role escalation prevention: regular user cannot self-assign TENANT_ADMIN."""

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        """Set up tenant with admin and regular user."""
        self.client = APIClient()
        slug = f"escalate-{uuid.uuid4().hex[:10]}"
        self.tenant = Tenant.objects.create(
            name=f"Escalation Tenant {slug}",
            slug=slug,
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)

        admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )

        self.regular_user = User.objects.create_user(
            email=f"escalate_edit_{slug}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.regular_user, role=provider_role)
        self.admin_role_id = str(admin_role.id)

    def test_regular_user_cannot_edit_any_user_returns_403(self):
        """Regular user (no TENANT_ADMIN) cannot edit self or others — 403."""
        self.client.force_authenticate(user=self.regular_user)

        # Cannot edit self
        resp_self = self.client.put(
            f"/api/v1/users/{self.regular_user.id}/",
            {"display_name": "Self Escalation", "status": "ACTIVE", "role_ids": [self.admin_role_id]},
            format="json",
        )
        assert resp_self.status_code == status.HTTP_403_FORBIDDEN
        assert "error" in resp_self.json()

        # Verify no role change
        self.regular_user.refresh_from_db()
        role_names = [ur.role.name for ur in UserRole.objects.filter(user=self.regular_user)]
        assert "TENANT_ADMIN" not in role_names
