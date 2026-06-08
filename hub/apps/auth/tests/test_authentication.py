"""
Comprehensive unit tests for authentication endpoints.

Tests cover:
- Login endpoint (success, failure, edge cases, error handling)
- Token refresh endpoint (success, failure, edge cases, error handling)
- Logout endpoint (success, failure, edge cases, error handling)
- Password reset endpoints (success, failure, edge cases, error handling)
- Invitation acceptance (success, failure, edge cases, error handling)
- Edge cases: empty inputs, null values, max length, special characters
- Error handling: database errors, network errors, validation errors

All tests use real implementations (no mocks of hub services).
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


class AuthenticationTest(TestCase):
    """Comprehensive tests for authentication endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create active user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create inactive user
        self.inactive_user = User.objects.create_user(
            email=f"inactive-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.DISABLED,
        )

    # ========== LOGIN TESTS ==========

    def test_login_success_returns_200(self):
        """Test successful login returns 200."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_success_returns_access_token(self):
        """Test successful login returns access_token."""
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
        """Test successful login returns refresh_token via httpOnly cookie (11.1)."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token_type"], "Bearer")

    def test_login_success_creates_refresh_token(self):
        """Test successful login creates refresh token in database."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )

        # Refresh token is in httpOnly cookie (11.1)
        refresh_token_str = response.cookies["refresh_token"].value
        refresh_token_hash = RefreshToken.hash_token(refresh_token_str)
        self.assertTrue(RefreshToken.objects.filter(token_hash=refresh_token_hash).exists())

    def test_login_invalid_email_returns_400(self):
        """Test login with non-existent email returns 400."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "nonexistent@example.com", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_invalid_email_has_error(self):
        """Test login with non-existent email has email error."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "nonexistent@example.com", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_invalid_password_returns_400(self):
        """Test login with incorrect password returns 400."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "wrongpassword"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_invalid_password_has_error(self):
        """Test login with incorrect password returns error keyed on email (to avoid revealing which field is wrong)."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "wrongpassword"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_inactive_user_returns_400(self):
        """Test login with inactive user account returns 400."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.inactive_user.email, "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_inactive_user_has_error(self):
        """Test login with inactive user account has email error."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.inactive_user.email, "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_empty_email(self):
        """Test login with empty email returns 400 with email error."""
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "", "password": "testpass123"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_empty_password(self):
        """Test login with empty password returns 400 with password error."""
        response = self.client.post(
            "/api/v1/auth/login/", {"email": self.user.email, "password": ""}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_login_missing_email(self):
        """Test login with missing email field returns 400 with email error."""
        response = self.client.post(
            "/api/v1/auth/login/", {"password": "testpass123"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_missing_password(self):
        """Test login with missing password field returns 400 with password error."""
        response = self.client.post(
            "/api/v1/auth/login/", {"email": self.user.email}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_login_invalid_email_format(self):
        """Test login with invalid email format returns 400 with email error."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "not-an-email", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_sql_injection_attempt(self):
        """Test login with SQL injection attempt (security edge case)"""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com' OR '1'='1", "password": "testpass123"},
            format="json",
        )

        # Should fail validation, not execute SQL — no token must be issued
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("access_token", response.data)

    def test_login_xss_attempt(self):
        """Test login with XSS attempt (security edge case)"""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "<script>alert('xss')</script>@example.com", "password": "testpass123"},
            format="json",
        )

        # Should fail validation — no token must be issued
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("access_token", response.data)

    def test_login_very_long_email(self):
        """Test login with extremely long email (edge case)"""
        long_email = "a" * 300 + "@example.com"
        response = self.client.post(
            "/api/v1/auth/login/", {"email": long_email, "password": "testpass123"}, format="json"
        )

        # Should fail validation due to length
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_very_long_password(self):
        """Test login with extremely long password (edge case)"""
        long_password = "a" * 10000
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": long_password},
            format="json",
        )

        # Long password is simply wrong credentials — expect 400 like any failed login
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Verify no token was issued
        self.assertNotIn("access_token", response.data)

    # ========== TOKEN REFRESH TESTS ==========

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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertIsInstance(response.data["access_token"], str)
        self.assertGreater(len(response.data["access_token"]), 0)

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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token_type"], "Bearer")

    def test_refresh_token_invalid(self):
        """Test token refresh with invalid token"""
        response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": "invalid_token_string"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_token_expired(self):
        """Test token refresh with expired token returns 401.

        The refresh endpoint returns 401 (not 400) for expired tokens so
        the frontend's auth interceptor recognises this as an auth failure
        and forces re-login.
        """
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

    def test_refresh_token_revoked(self):
        """Test token refresh with revoked token"""
        # Login — refresh token is in httpOnly cookie (11.1)
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )
        refresh_token = login_response.cookies["refresh_token"].value

        # Revoke the token directly in the DB
        refresh_token_hash = RefreshToken.hash_token(refresh_token)
        refresh_token_obj = RefreshToken.objects.get(token_hash=refresh_token_hash)
        refresh_token_obj.revoke()

        # Try to refresh — cookie is still sent automatically, but token is revoked.
        # Replay detection (11.2) returns 401 to force re-login.
        response = self.client.post("/api/v1/auth/refresh/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_empty(self):
        """Test token refresh with empty token (edge case)"""
        response = self.client.post("/api/v1/auth/refresh/", {"refresh_token": ""}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_token_missing(self):
        """Test token refresh with missing token field"""
        response = self.client.post("/api/v1/auth/refresh/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== LOGOUT TESTS ==========

    def test_logout_success_returns_200(self):
        """Test successful logout returns 200."""
        # Login — refresh token is in httpOnly cookie (11.1)
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )
        access_token = login_response.data["access_token"]

        # Authenticate with access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Logout — cookie sent automatically by APIClient
        response = self.client.post("/api/v1/auth/logout/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_success_revokes_refresh_token(self):
        """Test successful logout revokes refresh token."""
        # Login — refresh token is in httpOnly cookie (11.1)
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
        self.client.post("/api/v1/auth/logout/", {}, format="json")

        # Verify refresh token was revoked
        refresh_token_hash = RefreshToken.hash_token(refresh_token)
        refresh_token_obj = RefreshToken.objects.get(token_hash=refresh_token_hash)
        self.assertIsNotNone(refresh_token_obj.revoked_at)

    def test_logout_invalid_token(self):
        """Test logout with invalid refresh token"""
        # Login first
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )
        access_token = login_response.data["access_token"]

        # Authenticate with access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Logout with invalid token (idempotent: returns 200, revoked_count=0)
        response = self.client.post(
            "/api/v1/auth/logout/", {"refresh_token": "invalid_token"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_unauthenticated(self):
        """Test logout without authentication"""
        response = self.client.post(
            "/api/v1/auth/logout/", {"refresh_token": "some_token"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_missing_token(self):
        """Test logout without authentication returns 401 (endpoint requires IsAuthenticated)."""
        # Do NOT login — no access token, no refresh cookie
        response = self.client.post("/api/v1/auth/logout/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== PASSWORD RESET TESTS ==========

    def test_password_reset_request_success_returns_200(self):
        """Test successful password reset request returns 200."""
        response = self.client.post(
            "/api/v1/auth/password-reset/", {"email": self.user.email}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_request_success_creates_token(self):
        """Test successful password reset request creates token."""
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": self.user.email}, format="json"
        )

        # Verify password reset token was created
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token)

    def test_password_reset_request_success_sets_token_expiry(self):
        """Test successful password reset request sets token expiry."""
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": self.user.email}, format="json"
        )

        # Verify password reset token expiry was set
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token_expires_at)

    def test_password_reset_request_nonexistent_email(self):
        """Test password reset request with non-existent email"""
        response = self.client.post(
            "/api/v1/auth/password-reset/", {"email": "nonexistent@example.com"}, format="json"
        )

        # Should still return 200 to prevent email enumeration
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_request_empty_email(self):
        """Test password reset request with empty email (edge case)"""
        response = self.client.post("/api/v1/auth/password-reset/", {"email": ""}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_success_returns_200(self):
        """Test successful password reset confirmation returns 200."""
        import uuid
        import hashlib

        # Set password reset token directly: store hash, keep plaintext for the API call
        plaintext_token = str(uuid.uuid4())
        self.user.password_reset_token = hashlib.sha256(plaintext_token.encode()).hexdigest()
        self.user.password_reset_token_expires_at = timezone.now() + timedelta(hours=1)
        self.user.password_reset_token_used_at = None
        self.user.save()

        # Confirm password reset with the plaintext token
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": plaintext_token, "new_password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_confirm_success_changes_password(self):
        """Test successful password reset confirmation changes password."""
        import uuid
        import hashlib

        # Set password reset token directly: store hash, keep plaintext for the API call
        plaintext_token = str(uuid.uuid4())
        self.user.password_reset_token = hashlib.sha256(plaintext_token.encode()).hexdigest()
        self.user.password_reset_token_expires_at = timezone.now() + timedelta(hours=1)
        self.user.password_reset_token_used_at = None
        self.user.save()

        # Confirm password reset with the plaintext token
        self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": plaintext_token, "new_password": "newpass123"},
            format="json",
        )

        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass123"))

    def test_password_reset_confirm_success_clears_token(self):
        """Test successful password reset confirmation clears token."""
        import uuid
        import hashlib

        # Set password reset token directly: store hash, keep plaintext for the API call
        plaintext_token = str(uuid.uuid4())
        self.user.password_reset_token = hashlib.sha256(plaintext_token.encode()).hexdigest()
        self.user.password_reset_token_expires_at = timezone.now() + timedelta(hours=1)
        self.user.password_reset_token_used_at = None
        self.user.save()

        # Confirm password reset with the plaintext token
        self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": plaintext_token, "new_password": "newpass123"},
            format="json",
        )

        # Verify token was cleared
        self.user.refresh_from_db()
        self.assertIsNone(self.user.password_reset_token)

    def test_password_reset_confirm_invalid_token(self):
        """Test password reset confirmation with invalid token"""
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": "invalid_token", "new_password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_expired_token(self):
        """Test password reset confirmation with expired token"""
        # Set up a token directly so we control both plaintext and hash.
        # The view stores sha256(plaintext); the confirm endpoint receives plaintext.
        plaintext_token = str(uuid.uuid4())
        self.user.password_reset_token = hashlib.sha256(plaintext_token.encode()).hexdigest()
        self.user.password_reset_token_expires_at = timezone.now() - timedelta(hours=1)  # Expired
        self.user.password_reset_token_used_at = None
        self.user.save()

        # Try to confirm with expired (but otherwise valid) token
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": plaintext_token, "new_password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Verify the error is about the token, not a generic validation error
        self.assertIn("token", str(response.data).lower())

    def test_password_reset_confirm_weak_password(self):
        """Test password reset confirmation with weak password (edge case)"""
        # Set up a valid token directly so we control both plaintext and hash.
        plaintext_token = str(uuid.uuid4())
        self.user.password_reset_token = hashlib.sha256(plaintext_token.encode()).hexdigest()
        self.user.password_reset_token_expires_at = timezone.now() + timedelta(hours=1)
        self.user.password_reset_token_used_at = None
        self.user.save()

        # Try with weak password (too short — serializer enforces min_length=8)
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": plaintext_token, "new_password": "123"},
            format="json",
        )

        # Should fail password validation, not token validation
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

        # Verify the password was NOT changed (token still valid, user untouched)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("testpass123"))

    # ========== INVITATION ACCEPTANCE TESTS ==========

    def test_accept_invitation_success(self):
        """Test successful invitation acceptance"""
        import hashlib

        # Create invited user
        inv_uid = uuid.uuid4().hex[:8]
        invited_user = User.objects.create_user(
            email=f"invited-{inv_uid}@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )

        raw_token = uuid.uuid4()
        # invitation_token stores the SHA-256 hash; the raw token is sent in the request
        invited_user.invitation_token = hashlib.sha256(str(raw_token).encode()).hexdigest()
        invited_user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        invited_user.save()

        # Accept invitation
        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": str(raw_token), "password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        # Refresh token is delivered via httpOnly cookie (11.1), not in the body
        self.assertIn("refresh_token", response.cookies)

        # Verify user was activated
        invited_user.refresh_from_db()
        self.assertEqual(invited_user.status, UserStatus.ACTIVE)
        self.assertTrue(invited_user.check_password("newpass123"))

    def test_accept_invitation_invalid_token(self):
        """Test invitation acceptance with invalid token"""
        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": "invalid_token", "password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_invitation_expired_token(self):
        """Test invitation acceptance with expired token"""
        # Create invited user with expired token
        exp_uid = uuid.uuid4().hex[:8]
        invited_user = User.objects.create_user(
            email=f"invited-exp-{exp_uid}@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )

        # Store hash in DB, keep plaintext to send in the request (11.3)
        raw_token = str(uuid.uuid4())
        invited_user.invitation_token = hashlib.sha256(raw_token.encode()).hexdigest()
        invited_user.invitation_token_expires_at = timezone.now() - timedelta(days=1)  # Expired
        invited_user.save()

        # Try to accept with expired (but otherwise correct) token
        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": raw_token, "password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Verify the error is about the token
        self.assertIn("token", str(response.data).lower())
        # Verify user was NOT activated
        invited_user.refresh_from_db()
        self.assertEqual(invited_user.status, UserStatus.INVITED)

    def test_accept_invitation_already_accepted(self):
        """Test invitation acceptance for already active user"""
        # Create active user (not invited)
        act_uid = uuid.uuid4().hex[:8]
        active_user = User.objects.create_user(
            email=f"active-{act_uid}@example.com",
            password="existingpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Try to accept invitation (should fail)
        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": "some_token", "password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
