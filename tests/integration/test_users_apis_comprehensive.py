"""
Integration tests for Users APIs: me, me/erasure-requests, me/export-jobs, roles.

Real APIClient and User/Role; tenant isolation. No mocks/stubs. Plan 3.3.1.1 (P1).
Phase 28.1.2: Admin user edit flow (PUT/PATCH /users/{id}/).
"""

import uuid

import pytest

pytestmark = pytest.mark.slow
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import Role, UserRole, UserStatus

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class TestUsersAPIsComprehensiveIntegration:
    """Integration tests for auth/me, users/roles, me/export-jobs, me/erasure-requests."""

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        self.client = APIClient()
        slug = f"users-int-{uuid.uuid4().hex[:10]}"
        self.tenant = Tenant.objects.create(
            name=f"Users Integration Tenant {slug}",
            slug=slug,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"users_integ-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)
        ensure_user_has_data_provider_role(self.user)

    def test_auth_me_returns_current_user(self):
        """GET /api/v1/auth/me/ returns 200 and current user info."""
        response = self.client.get("/api/v1/auth/me/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get("email") == self.user.email
        assert "id" in data

    def test_users_roles_list_returns_200(self):
        """GET /api/v1/users/roles/ returns 200 and list or paginated results."""
        response = self.client.get("/api/v1/users/roles/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "results" in data

    def test_users_me_erasure_requests_list_returns_200(self):
        """GET users/me/erasure-requests/ returns 200 (tenant-scoped)."""
        response = self.client.get("/api/v1/users/me/erasure-requests/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "results" in data

    def test_users_me_export_jobs_list_returns_200(self):
        """GET users/me/export-jobs/ returns 200 (tenant-scoped)."""
        response = self.client.get("/api/v1/users/me/export-jobs/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "results" in data


class TestAdminUserEditIntegration:
    """Integration tests for admin user edit flow (PUT/PATCH /users/{id}/). Phase 28.1.2."""

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        self.client = APIClient()
        slug = f"admin-edit-{uuid.uuid4().hex[:10]}"
        self.tenant = Tenant.objects.create(
            name=f"Admin Edit Integration Tenant {slug}",
            slug=slug,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        self.tenant_admin = User.objects.create_user(
            email=f"admin_edit_integ_{slug}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.tenant_admin, role=admin_role)

        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        self.target_user = User.objects.create_user(
            email=f"target_edit_integ_{slug}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Target User",
        )
        UserRole.objects.create(user=self.target_user, role=provider_role)

    def test_admin_user_edit_full_flow(self):
        """Tenant admin: list users, retrieve user, PUT update, verify changes."""
        self.client.force_authenticate(user=self.tenant_admin)

        # List users
        list_resp = self.client.get("/api/v1/users/")
        assert list_resp.status_code == status.HTTP_200_OK
        results = list_resp.json().get("results", list_resp.json())
        user_ids = [u["id"] for u in results]
        assert str(self.target_user.id) in user_ids

        # Retrieve user
        get_resp = self.client.get(f"/api/v1/users/{self.target_user.id}/")
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["display_name"] == "Target User"
        assert "DATA_PROVIDER" in get_resp.json().get("roles", [])

        # PUT update (display_name, status, roles)
        consumer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_CONSUMER",
            defaults={"description": "Data Consumer"},
        )
        put_resp = self.client.put(
            f"/api/v1/users/{self.target_user.id}/",
            {
                "display_name": "Updated via Integration",
                "status": "SUSPENDED",
                "role_ids": [str(consumer_role.id)],
            },
            format="json",
        )
        assert put_resp.status_code == status.HTTP_200_OK
        assert put_resp.json()["display_name"] == "Updated via Integration"
        assert put_resp.json()["status"] == "SUSPENDED"
        assert "DATA_CONSUMER" in put_resp.json().get("roles", [])

        # Verify persistence
        self.target_user.refresh_from_db()
        assert self.target_user.display_name == "Updated via Integration"
        assert self.target_user.status == UserStatus.SUSPENDED
        role_names = [ur.role.name for ur in UserRole.objects.filter(user=self.target_user)]
        assert "DATA_CONSUMER" in role_names

    def test_admin_user_edit_patch_partial(self):
        """Tenant admin: PATCH partial update (display_name only)."""
        self.client.force_authenticate(user=self.tenant_admin)
        patch_resp = self.client.patch(
            f"/api/v1/users/{self.target_user.id}/",
            {"display_name": "Patched Name"},
            format="json",
        )
        assert patch_resp.status_code == status.HTTP_200_OK
        assert patch_resp.json()["display_name"] == "Patched Name"
        self.target_user.refresh_from_db()
        assert self.target_user.display_name == "Patched Name"
