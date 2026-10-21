"""Phase 98: CSRF protection tests."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()

pytestmark = pytest.mark.security


class CSRFProtectionTest(TestCase):
    """Verify CSRF enforcement on state-changing endpoints."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"CSRF Test {uid}",
            slug=f"csrf-test-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"csrf-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_csrf_cookie_httponly_flag(self):
        """CSRF cookie must have httpOnly=True (Phase 90)."""
        from django.conf import settings

        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)

    def test_api_uses_jwt_not_session_auth(self):
        """API uses JWT auth, so CSRF is not required for API endpoints."""
        from django.conf import settings

        auth_classes = settings.REST_FRAMEWORK.get("DEFAULT_AUTHENTICATION_CLASSES", [])
        session_auth = [c for c in auth_classes if "Session" in c]
        self.assertEqual(
            len(session_auth), 0, "SessionAuthentication should not be in DRF defaults"
        )
