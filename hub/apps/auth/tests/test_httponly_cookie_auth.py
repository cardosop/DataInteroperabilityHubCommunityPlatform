"""
Tests for httpOnly cookie-based authentication (Task 220.4).

Covers:
- Login with USE_HTTPONLY_AUTH_COOKIES=True: tokens in cookies, NOT in body
- Refresh with USE_HTTPONLY_AUTH_COOKIES=True: access_token in cookie, NOT in body
- API call with access_token cookie (no Authorization header): authenticates successfully
- Logout clears both cookies
- Legacy mode (flag off): tokens still in response body
"""

import uuid

import pytest
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class HttpOnlyCookieAuthTest(TestCase):
    """Test httpOnly cookie-based authentication flow."""

    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Cookie Auth Test {uid}",
            slug=f"cookie-auth-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"cookie-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.login_payload = {
            "email": self.user.email,
            "password": "testpass123",
        }

    # ---- Login (220.4.1) ----

    @override_settings(USE_HTTPONLY_AUTH_COOKIES=True)
    def test_login_sets_access_token_cookie(self):
        """Login must set access_token as httpOnly cookie."""
        resp = self.client.post(
            "/api/v1/auth/login/",
            self.login_payload,
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", resp.cookies)
        cookie = resp.cookies["access_token"]
        self.assertTrue(cookie["httponly"])

    @override_settings(USE_HTTPONLY_AUTH_COOKIES=True)
    def test_login_sets_refresh_token_cookie(self):
        """Login must set refresh_token as httpOnly cookie."""
        resp = self.client.post(
            "/api/v1/auth/login/",
            self.login_payload,
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("refresh_token", resp.cookies)
        cookie = resp.cookies["refresh_token"]
        self.assertTrue(cookie["httponly"])

    @override_settings(USE_HTTPONLY_AUTH_COOKIES=True)
    def test_login_omits_tokens_from_body(self):
        """Login body must NOT contain access_token or refresh_token."""
        resp = self.client.post(
            "/api/v1/auth/login/",
            self.login_payload,
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertNotIn("access_token", body)
        self.assertNotIn("refresh_token", body)
        # token_type and expires_in should still be present
        self.assertIn("token_type", body)
        self.assertIn("expires_in", body)

    # ---- Refresh (220.4.1) ----

    @override_settings(USE_HTTPONLY_AUTH_COOKIES=True)
    def test_refresh_sets_access_token_cookie(self):
        """Refresh must set access_token as httpOnly cookie."""
        # Login first to get cookies
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            self.login_payload,
            format="json",
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)

        # Refresh — cookies are auto-sent by APIClient
        refresh_resp = self.client.post(
            "/api/v1/auth/refresh/",
            {},
            format="json",
        )
        self.assertEqual(refresh_resp.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", refresh_resp.cookies)
        self.assertTrue(refresh_resp.cookies["access_token"]["httponly"])

    @override_settings(USE_HTTPONLY_AUTH_COOKIES=True)
    def test_refresh_omits_access_token_from_body(self):
        """Refresh body must NOT contain access_token."""
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            self.login_payload,
            format="json",
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)

        refresh_resp = self.client.post(
            "/api/v1/auth/refresh/",
            {},
            format="json",
        )
        self.assertEqual(refresh_resp.status_code, status.HTTP_200_OK)
        body = refresh_resp.json()
        self.assertNotIn("access_token", body)

    # ---- API calls via cookie (220.4.2) ----

    @override_settings(USE_HTTPONLY_AUTH_COOKIES=True)
    def test_api_call_authenticates_via_cookie(self):
        """API call with access_token cookie (no Bearer header) should succeed."""
        # Login to get access_token cookie
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            self.login_payload,
            format="json",
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)

        # Make API call — cookies are auto-sent, no Authorization header
        # The /auth/me/ endpoint requires authentication
        me_resp = self.client.get(
            "/api/v1/auth/me/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(
            me_resp.status_code,
            status.HTTP_200_OK,
            f"Expected 200 from /auth/me/ with cookie auth, got {me_resp.status_code}: {me_resp.content}",
        )
        self.assertEqual(me_resp.json()["email"], self.user.email)

    # ---- Logout (220.4) ----

    @override_settings(USE_HTTPONLY_AUTH_COOKIES=True)
    def test_logout_clears_access_token_cookie(self):
        """Logout must delete the access_token cookie."""
        # Login to get cookies
        login_resp = self.client.post(
            "/api/v1/auth/login/",
            self.login_payload,
            format="json",
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)

        # Logout
        logout_resp = self.client.post("/api/v1/auth/logout/")
        self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)

        # access_token cookie should be expired (max-age=0)
        self.assertIn("access_token", logout_resp.cookies)
        # Django's delete_cookie sets max-age=0 and expires in the past
        cookie = logout_resp.cookies["access_token"]
        self.assertEqual(cookie["max-age"], 0)

    # ---- Legacy mode (flag off) ----

    @override_settings(USE_HTTPONLY_AUTH_COOKIES=False)
    def test_legacy_login_returns_tokens_in_body(self):
        """Legacy mode: tokens should be in response body."""
        resp = self.client.post(
            "/api/v1/auth/login/",
            self.login_payload,
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)
