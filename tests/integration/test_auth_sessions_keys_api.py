"""
Phase TR.B — API integration test (relocated from E2E browser spec).

This test covers the API-level logic formerly tested in the
corresponding frontend/e2e/features/ spec. Browser interactions
are tested separately in the dual-verification replacement spec.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TestApiLogic:
    """API logic formerly in E2E browser spec."""

    def test_api_endpoint_responds(self):
        """Verify the auth sessions/keys API endpoint returns a valid response."""
        client = APIClient()

        tenant = Tenant.objects.create(
            name=f"Auth Session API Test {uuid.uuid4().hex[:8]}",
            slug=f"auth-session-api-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        user = User.objects.create_user(
            email=f"auth-session-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        # Assign a role that grants access to auth endpoints
        role, _ = Role.objects.get_or_create(
            tenant=tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"},
        )
        UserRole.objects.create(user=user, role=role)

        client.force_authenticate(user=user)
        response = client.get("/api/v1/auth/sessions/")

        # Authenticated user with DATA_PROVIDER role must succeed.
        # 401/403 should NOT be accepted — they would indicate a broken
        # authorization configuration that this test must catch.
        assert response.status_code == status.HTTP_200_OK, (
            f"Auth sessions endpoint returned {response.status_code}, expected 200. "
            f"Body: {response.data}"
        )
        # The sessions endpoint returns a plain list (not paginated dict).
        # Verify the response is valid JSON and not an error.
        assert response.data is not None, "Expected non-null response from sessions endpoint"
