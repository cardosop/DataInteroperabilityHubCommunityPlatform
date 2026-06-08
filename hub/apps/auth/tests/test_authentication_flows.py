"""
Unit tests for authentication flows (login, logout, password reset, invitation).
"""

import hashlib
import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.auth.models import RefreshToken
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AuthenticationFlowsTest(TestCase):
    """Test authentication flows"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_login_success_returns_200(self):
        """Test successful login returns 200."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_success_returns_access_token(self):
        """Test successful login returns a non-empty access_token string."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertIsInstance(response.data["access_token"], str)
        self.assertGreater(len(response.data["access_token"]), 0)

    def test_login_success_returns_refresh_token(self):
        """Test successful login returns refresh_token via httpOnly cookie."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        # Refresh token is in httpOnly cookie (11.1), not in the body
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("refresh_token", response.cookies)
        self.assertGreater(len(response.cookies["refresh_token"].value), 0)

    def test_login_success_returns_bearer_token_type(self):
        """Test successful login returns Bearer token_type."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.data["token_type"], "Bearer")

    def test_login_success_creates_refresh_token(self):
        """Test successful login creates refresh token."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        # Refresh token is in httpOnly cookie (11.1)
        refresh_token_str = response.cookies["refresh_token"].value
        refresh_token_hash = RefreshToken.hash_token(refresh_token_str)
        self.assertTrue(RefreshToken.objects.filter(token_hash=refresh_token_hash).exists())

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "wrongpassword"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_inactive_user(self):
        """Test login with inactive user"""
        self.user.status = UserStatus.DISABLED
        self.user.save()

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_token_success_returns_200(self):
        """Test successful token refresh returns 200."""
        # First login — sets refresh_token as httpOnly cookie (11.1)
        self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        # Refresh token — cookie sent automatically by APIClient
        response = self.client.post("/api/v1/auth/refresh/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_refresh_token_success_returns_access_token(self):
        """Test successful token refresh returns access_token."""
        # First login — sets refresh_token as httpOnly cookie (11.1)
        self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        # Refresh token — cookie sent automatically by APIClient
        response = self.client.post("/api/v1/auth/refresh/", {}, format="json")

        self.assertIn("access_token", response.data)

    def test_refresh_token_success_returns_bearer_token_type(self):
        """Test successful token refresh returns Bearer token_type."""
        # First login — sets refresh_token as httpOnly cookie (11.1)
        self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        # Refresh token — cookie sent automatically by APIClient
        response = self.client.post("/api/v1/auth/refresh/", {}, format="json")

        self.assertEqual(response.data["token_type"], "Bearer")

    def test_refresh_token_invalid(self):
        """Test token refresh with invalid token"""
        response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": "invalid_token"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_token_expired(self):
        """Test token refresh with expired token"""
        # Create an expired refresh token
        refresh_token_str = RefreshToken.generate_token()
        refresh_token_hash = RefreshToken.hash_token(refresh_token_str)

        RefreshToken.objects.create(
            user=self.user,
            token_hash=refresh_token_hash,
            expires_at=timezone.now() - timedelta(days=1),  # Expired
        )

        response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": refresh_token_str}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout(self):
        """Test logout"""
        # First login — refresh token in httpOnly cookie (11.1)
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )
        refresh_token = login_response.cookies["refresh_token"].value
        access_token = login_response.data["access_token"]

        # Authenticate with access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Logout — cookie sent automatically by APIClient
        response = self.client.post("/api/v1/auth/logout/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify refresh token was revoked
        refresh_token_hash = RefreshToken.hash_token(refresh_token)
        refresh_token_obj = RefreshToken.objects.get(token_hash=refresh_token_hash)
        self.assertIsNotNone(refresh_token_obj.revoked_at)

    def test_password_reset_request_returns_200(self):
        """Test password reset request returns 200."""
        response = self.client.post(
            "/api/v1/auth/password-reset/", {"email": self.user.email}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_request_creates_token(self):
        """Test password reset request creates token."""
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": self.user.email}, format="json"
        )

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token)

    def test_password_reset_request_sets_token_expiry(self):
        """Test password reset request sets token expiry."""
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": self.user.email}, format="json"
        )

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token_expires_at)

    def _set_password_reset_token(self):
        """Helper: set a valid password_reset_token directly (avoids email flow).
        Returns the plaintext token to pass to the confirm endpoint."""
        plaintext_token = str(uuid.uuid4())
        self.user.password_reset_token = hashlib.sha256(plaintext_token.encode()).hexdigest()
        self.user.password_reset_token_expires_at = timezone.now() + timedelta(hours=1)
        self.user.password_reset_token_used_at = None
        self.user.save()
        return plaintext_token

    def test_password_reset_confirm_returns_200(self):
        """Test password reset confirmation returns 200."""
        plaintext_token = self._set_password_reset_token()

        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": plaintext_token, "new_password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_confirm_changes_password(self):
        """Test password reset confirmation changes password."""
        plaintext_token = self._set_password_reset_token()

        self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": plaintext_token, "new_password": "newpass123"},
            format="json",
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass123"))

    def test_password_reset_confirm_clears_token(self):
        """Test password reset confirmation clears token."""
        plaintext_token = self._set_password_reset_token()

        self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": plaintext_token, "new_password": "newpass123"},
            format="json",
        )

        self.user.refresh_from_db()
        self.assertIsNone(self.user.password_reset_token)

    def test_password_reset_confirm_sets_token_used_at(self):
        """Test password reset confirmation sets token_used_at."""
        plaintext_token = self._set_password_reset_token()

        self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": plaintext_token, "new_password": "newpass123"},
            format="json",
        )

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token_used_at)

    def test_password_reset_confirm_increments_token_version(self):
        """Test password reset confirmation increments token_version."""
        plaintext_token = self._set_password_reset_token()
        self.user.refresh_from_db()
        original_version = self.user.token_version

        self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": plaintext_token, "new_password": "newpass123"},
            format="json",
        )

        self.user.refresh_from_db()
        self.assertGreater(self.user.token_version, original_version)

    def _make_invited_user(self, email=f"invited-{uuid.uuid4().hex[:8]}@example.com"):
        """Helper: create an invited user with a valid invitation token.
        Returns (user, plaintext_token) — store plaintext_token in API call."""
        invited_user = User.objects.create_user(
            email=email, tenant=self.tenant, status=UserStatus.INVITED
        )
        raw_token = str(uuid.uuid4())
        invited_user.invitation_token = hashlib.sha256(raw_token.encode()).hexdigest()
        invited_user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        invited_user.save()
        return invited_user, raw_token

    def test_accept_invitation_returns_200(self):
        """Test invitation acceptance returns 200."""
        invited_user, raw_token = self._make_invited_user()

        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": raw_token, "password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_accept_invitation_returns_access_token(self):
        """Test invitation acceptance returns access_token."""
        invited_user, raw_token = self._make_invited_user()

        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": raw_token, "password": "newpass123"},
            format="json",
        )

        self.assertIn("access_token", response.data)

    def test_accept_invitation_returns_refresh_token(self):
        """Test invitation acceptance returns refresh_token (httpOnly cookie, 11.1)."""
        invited_user, raw_token = self._make_invited_user()

        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": raw_token, "password": "newpass123"},
            format="json",
        )

        # Refresh token is in httpOnly cookie (11.1), not in the body
        self.assertIn("refresh_token", response.cookies)

    def test_accept_invitation_activates_user(self):
        """Test invitation acceptance activates user."""
        invited_user, raw_token = self._make_invited_user()

        self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": raw_token, "password": "newpass123"},
            format="json",
        )

        invited_user.refresh_from_db()
        self.assertEqual(invited_user.status, UserStatus.ACTIVE)

    def test_accept_invitation_sets_password(self):
        """Test invitation acceptance sets password."""
        invited_user, raw_token = self._make_invited_user()

        self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": raw_token, "password": "newpass123"},
            format="json",
        )

        invited_user.refresh_from_db()
        self.assertTrue(invited_user.check_password("newpass123"))

    def test_accept_invitation_clears_token(self):
        """Test invitation acceptance clears token."""
        invited_user, raw_token = self._make_invited_user()

        self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": raw_token, "password": "newpass123"},
            format="json",
        )

        invited_user.refresh_from_db()
        self.assertIsNone(invited_user.invitation_token)

    def test_accept_invitation_sets_token_used_at(self):
        """Test invitation acceptance sets token_used_at."""
        invited_user, raw_token = self._make_invited_user()

        self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": raw_token, "password": "newpass123"},
            format="json",
        )

        invited_user.refresh_from_db()
        self.assertIsNotNone(invited_user.invitation_token_used_at)

    # ========== EDGE CASES ==========

    def test_login_empty_email(self):
        """Test login with empty email (edge case)"""
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "", "password": "testpass123"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_empty_password(self):
        """Test login with empty password (edge case)"""
        response = self.client.post(
            "/api/v1/auth/login/", {"email": self.user.email, "password": ""}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_missing_fields(self):
        """Test login with missing required fields (edge case)"""
        response = self.client.post("/api/v1/auth/login/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_token_empty(self):
        """Test token refresh with empty token (edge case)"""
        response = self.client.post("/api/v1/auth/refresh/", {"refresh_token": ""}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_token_missing(self):
        """Test token refresh with missing token field (edge case)"""
        response = self.client.post("/api/v1/auth/refresh/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_unauthenticated(self):
        """Test logout without authentication (error handling)"""
        response = self.client.post(
            "/api/v1/auth/logout/", {"refresh_token": "some_token"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_invalid_token(self):
        """Test logout with invalid refresh token (error handling)"""
        # Login first
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )
        access_token = login_response.data["access_token"]

        # Authenticate with access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Logout with invalid token
        response = self.client.post(
            "/api/v1/auth/logout/", {"refresh_token": "invalid_token"}, format="json"
        )

        # Should still return 200 (logout is idempotent)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_request_nonexistent_email(self):
        """Test password reset request with non-existent email (edge case)"""
        response = self.client.post(
            "/api/v1/auth/password-reset/", {"email": "nonexistent@example.com"}, format="json"
        )

        # Should still return 200 to prevent email enumeration
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_confirm_invalid_token(self):
        """Test password reset confirmation with invalid token (error handling)"""
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": "invalid_token", "new_password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_expired_token(self):
        """Test password reset confirmation with expired token (error handling)"""
        plaintext_token = str(uuid.uuid4())
        self.user.password_reset_token = hashlib.sha256(plaintext_token.encode()).hexdigest()
        self.user.password_reset_token_expires_at = timezone.now() - timedelta(hours=1)
        self.user.password_reset_token_used_at = None
        self.user.save()

        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": plaintext_token, "new_password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_invitation_invalid_token(self):
        """Test invitation acceptance with invalid token (error handling)"""
        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": "invalid_token", "password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_invitation_expired_token(self):
        """Test invitation acceptance with expired token (error handling)"""
        invited_user = User.objects.create_user(
            email=f"invited2-{uuid.uuid4().hex[:8]}@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )
        raw_token = str(uuid.uuid4())
        invited_user.invitation_token = hashlib.sha256(raw_token.encode()).hexdigest()
        invited_user.invitation_token_expires_at = timezone.now() - timedelta(days=1)
        invited_user.save()

        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": raw_token, "password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
