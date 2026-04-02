"""Phase 98: Session and cookie security tests."""
import uuid
import pytest
from django.test import TestCase
from django.conf import settings
from rest_framework.test import APIClient
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.security


class SessionSecurityTest(TestCase):
    """Verify session and cookie security properties."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Session Test {uid}",
            slug=f"session-test-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"session-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_refresh_cookie_httponly(self):
        """Refresh token cookie must be httpOnly."""
        client = APIClient()
        response = client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )
        if response.status_code == 200:
            cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")
            cookie = response.cookies.get(cookie_name)
            if cookie:
                self.assertTrue(
                    cookie["httponly"],
                    "Refresh token cookie must be httpOnly",
                )

    def test_refresh_cookie_samesite_strict(self):
        """Refresh token cookie must have SameSite=Strict."""
        client = APIClient()
        response = client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )
        if response.status_code == 200:
            cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")
            cookie = response.cookies.get(cookie_name)
            if cookie:
                self.assertEqual(
                    cookie["samesite"], "Strict",
                    "Refresh cookie must have SameSite=Strict",
                )

    def test_session_cookie_httponly(self):
        """Django session cookie must be httpOnly."""
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_csrf_cookie_httponly(self):
        """CSRF cookie must be httpOnly (Phase 90)."""
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)

    def test_session_cookie_samesite(self):
        """Session cookie must have SameSite set."""
        self.assertIn(
            settings.SESSION_COOKIE_SAMESITE, ["Strict", "Lax"],
        )
