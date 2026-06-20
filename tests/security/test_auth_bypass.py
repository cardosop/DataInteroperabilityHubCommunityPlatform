"""Phase 98: Auth bypass prevention tests."""

import uuid

import jwt
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus, UserTenantMembership

User = get_user_model()

pytestmark = pytest.mark.security


class AuthBypassTest(TestCase):
    """Verify authentication cannot be bypassed."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Auth Test {uid}",
            slug=f"auth-test-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"auth-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(
            user=self.user,
            tenant=self.tenant,
        )
        self.client = APIClient()

    def test_no_token_returns_401(self):
        """Request without auth token must return 401."""
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertIn(response.status_code, [401, 403])

    def test_forged_jwt_wrong_secret_returns_401(self):
        """JWT signed with wrong secret must be rejected."""
        forged = jwt.encode(
            {"user_id": str(self.user.id), "email": self.user.email},
            "wrong-secret-key",
            algorithm="HS256",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {forged}")
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertIn(response.status_code, [401, 403])

    def test_expired_jwt_returns_401(self):
        """Expired JWT must be rejected."""
        import time

        expired = jwt.encode(
            {"user_id": str(self.user.id), "exp": int(time.time()) - 3600},
            settings.JWT_SECRET_KEY,
            algorithm="HS256",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {expired}")
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertIn(response.status_code, [401, 403])

    def test_jwt_missing_claims_returns_401(self):
        """JWT with missing required claims must be rejected."""
        incomplete = jwt.encode(
            {"foo": "bar"},
            settings.JWT_SECRET_KEY,
            algorithm="HS256",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {incomplete}")
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertIn(response.status_code, [401, 403])
