"""
Unit tests for authentication flows (login, logout, password reset, invitation).
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from hub.apps.auth.models import RefreshToken
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AuthenticationFlowsTest(TestCase):
    """Test authentication flows"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_login_success(self):
        """Test successful login"""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)
        self.assertEqual(response.data["token_type"], "Bearer")
        
        # Verify refresh token was created
        refresh_token_str = response.data["refresh_token"]
        from hub.apps.auth.models import RefreshToken
        refresh_token_hash = RefreshToken.hash_token(refresh_token_str)
        self.assertTrue(
            RefreshToken.objects.filter(token_hash=refresh_token_hash).exists()
        )
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "wrongpassword"},
            format="json"
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
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_refresh_token_success(self):
        """Test successful token refresh"""
        # First login
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json"
        )
        refresh_token = login_response.data["refresh_token"]
        
        # Refresh token
        response = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh_token": refresh_token},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertEqual(response.data["token_type"], "Bearer")
    
    def test_refresh_token_invalid(self):
        """Test token refresh with invalid token"""
        response = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh_token": "invalid_token"},
            format="json"
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
            expires_at=timezone.now() - timedelta(days=1)  # Expired
        )
        
        response = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh_token": refresh_token_str},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_logout(self):
        """Test logout"""
        # First login
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": "testpass123"},
            format="json"
        )
        refresh_token = login_response.data["refresh_token"]
        access_token = login_response.data["access_token"]
        
        # Authenticate with access token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Logout
        response = self.client.post(
            "/api/v1/auth/logout/",
            {"refresh_token": refresh_token},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify refresh token was revoked
        refresh_token_hash = RefreshToken.hash_token(refresh_token)
        refresh_token_obj = RefreshToken.objects.get(token_hash=refresh_token_hash)
        self.assertIsNotNone(refresh_token_obj.revoked_at)
    
    def test_password_reset_request(self):
        """Test password reset request"""
        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": "user@example.com"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify password reset token was created
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token)
        self.assertIsNotNone(self.user.password_reset_token_expires_at)
    
    def test_password_reset_confirm(self):
        """Test password reset confirmation"""
        # Request password reset
        self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": "user@example.com"},
            format="json"
        )
        
        self.user.refresh_from_db()
        reset_token = self.user.password_reset_token
        
        # Confirm password reset
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": str(reset_token), "new_password": "newpass123"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass123"))
        self.assertIsNone(self.user.password_reset_token)
        self.assertIsNotNone(self.user.password_reset_token_used_at)
        
        # Verify token version was incremented
        self.assertGreater(self.user.token_version, 1)
    
    def test_accept_invitation(self):
        """Test invitation acceptance"""
        import uuid
        # Create invited user
        invited_user = User.objects.create_user(
            email="invited@example.com",
            tenant=self.tenant,
            status=UserStatus.INVITED
        )
        # Generate a UUID for invitation token
        invited_user.invitation_token = uuid.uuid4()
        invited_user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        invited_user.save()
        
        # Accept invitation
        response = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {"token": str(invited_user.invitation_token), "password": "newpass123"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)
        
        # Verify user was activated
        invited_user.refresh_from_db()
        self.assertEqual(invited_user.status, UserStatus.ACTIVE)
        self.assertTrue(invited_user.check_password("newpass123"))
        self.assertIsNone(invited_user.invitation_token)
        self.assertIsNotNone(invited_user.invitation_token_used_at)

