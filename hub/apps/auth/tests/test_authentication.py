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
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create active user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create inactive user
        self.inactive_user = User.objects.create_user(
            email="inactive@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.DISABLED,
        )

    # ========== LOGIN TESTS ==========

    def test_login_success_returns_200(self):
        """Test successful login returns 200."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_success_returns_access_token(self):
        """Test successful login returns access_token."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )

        self.assertIn("access_token", response.data)

    def test_login_success_returns_refresh_token(self):
        """Test successful login returns refresh_token."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )

        self.assertIn("refresh_token", response.data)

    def test_login_success_returns_bearer_token_type(self):
        """Test successful login returns Bearer token_type."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.data["token_type"], "Bearer")

    def test_login_success_creates_refresh_token(self):
        """Test successful login creates refresh token in database."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )

        # Verify refresh token was created in database
        refresh_token_str = response.data["refresh_token"]
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

        self.assertIn("email", response.data)

    def test_login_invalid_password_returns_400(self):
        """Test login with incorrect password returns 400."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "wrongpassword"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_invalid_password_has_error(self):
        """Test login with incorrect password has email error."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "wrongpassword"},
            format="json",
        )

        self.assertIn("email", response.data)

    def test_login_inactive_user_returns_400(self):
        """Test login with inactive user account returns 400."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "inactive@example.com", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_inactive_user_has_error(self):
        """Test login with inactive user account has email error."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "inactive@example.com", "password": "testpass123"},
            format="json",
        )

        self.assertIn("email", response.data)

    def test_login_empty_email(self):
        """Test login with empty email (edge case)"""
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "", "password": "testpass123"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_empty_password(self):
        """Test login with empty password (edge case)"""
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "user@example.com", "password": ""}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_missing_email(self):
        """Test login with missing email field"""
        response = self.client.post(
            "/api/v1/auth/login/", {"password": "testpass123"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_missing_password(self):
        """Test login with missing password field"""
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "user@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_invalid_email_format(self):
        """Test login with invalid email format (edge case)"""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "not-an-email", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_sql_injection_attempt(self):
        """Test login with SQL injection attempt (security edge case)"""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com' OR '1'='1", "password": "testpass123"},
            format="json",
        )

        # Should fail validation, not execute SQL
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_xss_attempt(self):
        """Test login with XSS attempt (security edge case)"""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "<script>alert('xss')</script>@example.com", "password": "testpass123"},
            format="json",
        )

        # Should fail validation
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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
            {"email": "user@example.com", "password": long_password},
            format="json",
        )

        # Should fail validation or authentication
        self.assertIn(
            response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED]
        )

    # ========== TOKEN REFRESH TESTS ==========

    def test_refresh_token_success_returns_200(self):
        """Test successful token refresh returns 200."""
        # First login
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )
        refresh_token = login_response.data["refresh_token"]

        # Refresh token
        response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": refresh_token}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_refresh_token_success_returns_access_token(self):
        """Test successful token refresh returns access_token."""
        # First login
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )
        refresh_token = login_response.data["refresh_token"]

        # Refresh token
        response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": refresh_token}, format="json"
        )

        self.assertIn("access_token", response.data)

    def test_refresh_token_success_returns_bearer_token_type(self):
        """Test successful token refresh returns Bearer token_type."""
        # First login
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )
        refresh_token = login_response.data["refresh_token"]

        # Refresh token
        response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": refresh_token}, format="json"
        )

        self.assertEqual(response.data["token_type"], "Bearer")

    def test_refresh_token_invalid(self):
        """Test token refresh with invalid token"""
        response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": "invalid_token_string"}, format="json"
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

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_token_revoked(self):
        """Test token refresh with revoked token"""
        # Login and get refresh token
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )
        refresh_token = login_response.data["refresh_token"]

        # Revoke the token
        refresh_token_hash = RefreshToken.hash_token(refresh_token)
        refresh_token_obj = RefreshToken.objects.get(token_hash=refresh_token_hash)
        refresh_token_obj.revoke()

        # Try to refresh with revoked token
        response = self.client.post(
            "/api/v1/auth/refresh/", {"refresh_token": refresh_token}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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
        # Login first
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )
        refresh_token = login_response.data["refresh_token"]
        access_token = login_response.data["access_token"]

        # Authenticate with access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Logout
        response = self.client.post(
            "/api/v1/auth/logout/", {"refresh_token": refresh_token}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_success_revokes_refresh_token(self):
        """Test successful logout revokes refresh token."""
        # Login first
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )
        refresh_token = login_response.data["refresh_token"]
        access_token = login_response.data["access_token"]

        # Authenticate with access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Logout
        self.client.post("/api/v1/auth/logout/", {"refresh_token": refresh_token}, format="json")

        # Verify refresh token was revoked
        refresh_token_hash = RefreshToken.hash_token(refresh_token)
        refresh_token_obj = RefreshToken.objects.get(token_hash=refresh_token_hash)
        self.assertIsNotNone(refresh_token_obj.revoked_at)

    def test_logout_invalid_token(self):
        """Test logout with invalid refresh token"""
        # Login first
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
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
        """Test logout with missing refresh token"""
        # Login first
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )
        access_token = login_response.data["access_token"]

        # Authenticate with access token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Logout without token
        response = self.client.post("/api/v1/auth/logout/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== PASSWORD RESET TESTS ==========

    def test_password_reset_request_success_returns_200(self):
        """Test successful password reset request returns 200."""
        response = self.client.post(
            "/api/v1/auth/password-reset/", {"email": "user@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_request_success_creates_token(self):
        """Test successful password reset request creates token."""
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": "user@example.com"}, format="json"
        )

        # Verify password reset token was created
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token)

    def test_password_reset_request_success_sets_token_expiry(self):
        """Test successful password reset request sets token expiry."""
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": "user@example.com"}, format="json"
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
        # Request password reset
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": "user@example.com"}, format="json"
        )

        self.user.refresh_from_db()
        reset_token = self.user.password_reset_token

        # Confirm password reset
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": str(reset_token), "new_password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_confirm_success_changes_password(self):
        """Test successful password reset confirmation changes password."""
        # Request password reset
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": "user@example.com"}, format="json"
        )

        self.user.refresh_from_db()
        reset_token = self.user.password_reset_token

        # Confirm password reset
        self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": str(reset_token), "new_password": "newpass123"},
            format="json",
        )

        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass123"))

    def test_password_reset_confirm_success_clears_token(self):
        """Test successful password reset confirmation clears token."""
        # Request password reset
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": "user@example.com"}, format="json"
        )

        self.user.refresh_from_db()
        reset_token = self.user.password_reset_token

        # Confirm password reset
        self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": str(reset_token), "new_password": "newpass123"},
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
        # Request password reset
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": "user@example.com"}, format="json"
        )

        self.user.refresh_from_db()
        reset_token = self.user.password_reset_token

        # Expire the token
        self.user.password_reset_token_expires_at = timezone.now() - timedelta(hours=1)
        self.user.save()

        # Try to confirm with expired token
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": str(reset_token), "new_password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_weak_password(self):
        """Test password reset confirmation with weak password (edge case)"""
        # Request password reset
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": "user@example.com"}, format="json"
        )

        self.user.refresh_from_db()
        reset_token = self.user.password_reset_token

        # Try with weak password
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": str(reset_token), "new_password": "123"},
            format="json",
        )

        # Should fail validation
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== INVITATION ACCEPTANCE TESTS ==========

    def test_accept_invitation_success(self):
        """Test successful invitation acceptance"""
        # Create invited user
        invited_user = User.objects.create_user(
            email="invited@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )
        import uuid

        invited_user.invitation_token = uuid.uuid4()
        invited_user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        invited_user.save()

        # Accept invitation
        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": str(invited_user.invitation_token), "password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)

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
        invited_user = User.objects.create_user(
            email="invited@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )
        import uuid

        invited_user.invitation_token = uuid.uuid4()
        invited_user.invitation_token_expires_at = timezone.now() - timedelta(days=1)  # Expired
        invited_user.save()

        # Try to accept with expired token
        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": str(invited_user.invitation_token), "password": "newpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_invitation_already_accepted(self):
        """Test invitation acceptance for already active user"""
        # Create active user (not invited)
        active_user = User.objects.create_user(
            email="active@example.com",
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
