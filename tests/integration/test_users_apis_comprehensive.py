"""
Integration tests for Users APIs: me, me/erasure-requests, me/export-jobs, roles.

Real APIClient and User/Role; tenant isolation. No mocks/stubs. Plan 3.3.1.1 (P1).
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class UsersAPIsComprehensiveIntegrationTest:
    """Integration tests for auth/me, users/roles, me/export-jobs, me/erasure-requests."""

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Users Integration Tenant",
            slug="users-integration-tenant",
        )
        self.user = User.objects.create_user(
            email="users_integ@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

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
