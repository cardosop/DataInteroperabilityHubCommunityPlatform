"""
Unit tests for authentication flows (login, logout, password reset, invitation).
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


class AuthenticationFlowsTest(TestCase):
    """Test authentication flows"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

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
        """Test successful login creates refresh token."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )

        refresh_token_str = response.data["refresh_token"]
        from hub.apps.auth.models import RefreshToken

        refresh_token_hash = RefreshToken.hash_token(refresh_token_str)
        self.assertTrue(RefreshToken.objects.filter(token_hash=refresh_token_hash).exists())

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "wrongpassword"},
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
            {"email": "user@example.com", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout(self):
        """Test logout"""
        # First login
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

        # Verify refresh token was revoked
        refresh_token_hash = RefreshToken.hash_token(refresh_token)
        refresh_token_obj = RefreshToken.objects.get(token_hash=refresh_token_hash)
        self.assertIsNotNone(refresh_token_obj.revoked_at)

    def test_password_reset_request_returns_200(self):
        """Test password reset request returns 200."""
        response = self.client.post(
            "/api/v1/auth/password-reset/", {"email": "user@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_request_creates_token(self):
        """Test password reset request creates token."""
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": "user@example.com"}, format="json"
        )

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token)

    def test_password_reset_request_sets_token_expiry(self):
        """Test password reset request sets token expiry."""
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": "user@example.com"}, format="json"
        )

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token_expires_at)

    def test_password_reset_confirm_returns_200(self):
        """Test password reset confirmation returns 200."""
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

    def test_password_reset_confirm_changes_password(self):
        """Test password reset confirmation changes password."""
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

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass123"))

    def test_password_reset_confirm_clears_token(self):
        """Test password reset confirmation clears token."""
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

        self.user.refresh_from_db()
        self.assertIsNone(self.user.password_reset_token)

    def test_password_reset_confirm_sets_token_used_at(self):
        """Test password reset confirmation sets token_used_at."""
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

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token_used_at)

    def test_password_reset_confirm_increments_token_version(self):
        """Test password reset confirmation increments token_version."""
        # Request password reset
        self.client.post(
            "/api/v1/auth/password-reset/", {"email": "user@example.com"}, format="json"
        )

        self.user.refresh_from_db()
        reset_token = self.user.password_reset_token
        original_version = self.user.token_version

        # Confirm password reset
        self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": str(reset_token), "new_password": "newpass123"},
            format="json",
        )

        self.user.refresh_from_db()
        self.assertGreater(self.user.token_version, original_version)

    def test_accept_invitation_returns_200(self):
        """Test invitation acceptance returns 200."""
        import uuid

        # Create invited user
        invited_user = User.objects.create_user(
            email="invited@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )
        # Generate a UUID for invitation token
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

    def test_accept_invitation_returns_access_token(self):
        """Test invitation acceptance returns access_token."""
        import uuid

        # Create invited user
        invited_user = User.objects.create_user(
            email="invited@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )
        # Generate a UUID for invitation token
        invited_user.invitation_token = uuid.uuid4()
        invited_user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        invited_user.save()

        # Accept invitation
        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": str(invited_user.invitation_token), "password": "newpass123"},
            format="json",
        )

        self.assertIn("access_token", response.data)

    def test_accept_invitation_returns_refresh_token(self):
        """Test invitation acceptance returns refresh_token."""
        import uuid

        # Create invited user
        invited_user = User.objects.create_user(
            email="invited@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )
        # Generate a UUID for invitation token
        invited_user.invitation_token = uuid.uuid4()
        invited_user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        invited_user.save()

        # Accept invitation
        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": str(invited_user.invitation_token), "password": "newpass123"},
            format="json",
        )

        self.assertIn("refresh_token", response.data)

    def test_accept_invitation_activates_user(self):
        """Test invitation acceptance activates user."""
        import uuid

        # Create invited user
        invited_user = User.objects.create_user(
            email="invited@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )
        # Generate a UUID for invitation token
        invited_user.invitation_token = uuid.uuid4()
        invited_user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        invited_user.save()

        # Accept invitation
        self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": str(invited_user.invitation_token), "password": "newpass123"},
            format="json",
        )

        invited_user.refresh_from_db()
        self.assertEqual(invited_user.status, UserStatus.ACTIVE)

    def test_accept_invitation_sets_password(self):
        """Test invitation acceptance sets password."""
        import uuid

        # Create invited user
        invited_user = User.objects.create_user(
            email="invited@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )
        # Generate a UUID for invitation token
        invited_user.invitation_token = uuid.uuid4()
        invited_user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        invited_user.save()

        # Accept invitation
        self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": str(invited_user.invitation_token), "password": "newpass123"},
            format="json",
        )

        invited_user.refresh_from_db()
        self.assertTrue(invited_user.check_password("newpass123"))

    def test_accept_invitation_clears_token(self):
        """Test invitation acceptance clears token."""
        import uuid

        # Create invited user
        invited_user = User.objects.create_user(
            email="invited@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )
        # Generate a UUID for invitation token
        invited_user.invitation_token = uuid.uuid4()
        invited_user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        invited_user.save()

        # Accept invitation
        self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": str(invited_user.invitation_token), "password": "newpass123"},
            format="json",
        )

        invited_user.refresh_from_db()
        self.assertIsNone(invited_user.invitation_token)

    def test_accept_invitation_sets_token_used_at(self):
        """Test invitation acceptance sets token_used_at."""
        import uuid

        # Create invited user
        invited_user = User.objects.create_user(
            email="invited@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )
        # Generate a UUID for invitation token
        invited_user.invitation_token = uuid.uuid4()
        invited_user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        invited_user.save()

        # Accept invitation
        self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": str(invited_user.invitation_token), "password": "newpass123"},
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
            "/api/v1/auth/login/", {"email": "user@example.com", "password": ""}, format="json"
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
            {"email": "user@example.com", "password": "testpass123"},
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
        import uuid

        # Create invited user with expired token
        invited_user = User.objects.create_user(
            email="invited2@example.com", tenant=self.tenant, status=UserStatus.INVITED
        )
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
