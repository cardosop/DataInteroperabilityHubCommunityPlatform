"""Phase 98: Privilege escalation prevention tests."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

User = get_user_model()

pytestmark = pytest.mark.security


class PrivilegeEscalationTest(TestCase):
    """Verify role-based access control prevents privilege escalation."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Priv Test {uid}",
            slug=f"priv-test-{uid}",
        )
        # Create roles
        self.viewer_role = Role.objects.create(
            tenant=self.tenant,
            name="DATA_VIEWER",
            description="Read-only",
        )
        self.provider_role = Role.objects.create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            description="Can publish",
        )
        # Create viewer user
        self.viewer = User.objects.create_user(
            email=f"viewer-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(
            user=self.viewer,
            tenant=self.tenant,
            role=self.viewer_role,
        )
        self.viewer_client = APIClient()
        self.viewer_client.force_authenticate(user=self.viewer)

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_viewer_cannot_create_asset(self):
        """DATA_VIEWER must not create assets when scopes enforced."""
        response = self.viewer_client.post(
            "/api/v1/assets/",
            {"key": "test-key", "name": "Test"},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertIn(response.status_code, [403, 400])

    def test_user_cannot_modify_own_tenant_id(self):
        """User cannot change their own tenant_id via profile update."""
        other_tenant = Tenant.objects.create(
            name=f"Other {uuid.uuid4().hex[:8]}",
            slug=f"other-{uuid.uuid4().hex[:8]}",
        )
        self.viewer_client.patch(
            "/api/v1/auth/me/",
            {"tenant_id": str(other_tenant.id)},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        # tenant_id must NOT change regardless of response status
        self.viewer.refresh_from_db()
        self.assertEqual(
            self.viewer.tenant_id,
            self.tenant.id,
            "User's tenant_id must be immutable via profile update",
        )
