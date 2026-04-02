"""Phase 98: JWT token security tests."""
import uuid
import pytest
import time
import jwt as pyjwt
from django.test import TestCase
from django.conf import settings
from rest_framework.test import APIClient
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus, UserTenantMembership
from hub.apps.auth.models import RefreshToken
from hub.apps.auth.jwt_utils import JWTTokenGenerator
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

pytestmark = pytest.mark.security


class JWTSecurityTest(TestCase):
    """Verify JWT security properties."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"JWT Test {uid}", slug=f"jwt-test-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"jwt-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(
            user=self.user, tenant=self.tenant,
        )
        self.client = APIClient()

    def test_expired_access_token_rejected(self):
        """Access token past expiry must return 401."""
        expired = pyjwt.encode(
            {
                "user_id": str(self.user.id),
                "exp": int(time.time()) - 3600,
                "iat": int(time.time()) - 7200,
            },
            settings.JWT_SECRET_KEY,
            algorithm="HS256",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {expired}")
        response = self.client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertIn(response.status_code, [401, 403])

    def test_revoked_refresh_token_rejected(self):
        """Revoked refresh token must not issue new access token."""
        # Create a refresh token
        token_str = RefreshToken.generate_token()
        token_hash = RefreshToken.hash_token(token_str)
        rt = RefreshToken.objects.create(
            user=self.user,
            token_hash=token_hash,
            expires_at=timezone.now() + timedelta(days=7),
        )
        # Revoke it
        rt.revoke()

        # Try to refresh
        response = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh_token": token_str},
            format="json",
        )
        self.assertIn(response.status_code, [400, 401])

    def test_refresh_token_max_lifetime_enforced(self):
        """RefreshToken.save() must cap expires_at to max lifetime."""
        far_future = timezone.now() + timedelta(days=365)
        rt = RefreshToken(
            user=self.user,
            token_hash=RefreshToken.hash_token("test-token"),
            expires_at=far_future,
        )
        rt.save()
        max_days = getattr(settings, "REFRESH_TOKEN_MAX_LIFETIME_DAYS", 30)
        max_allowed = timezone.now() + timedelta(days=max_days, seconds=60)
        self.assertLessEqual(rt.expires_at, max_allowed)
