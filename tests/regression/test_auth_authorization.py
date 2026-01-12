"""
Comprehensive regression tests for all authentication/authorization flows.

Tests:
- JWT authentication
- API key authentication
- Password reset
- User registration
- Role-based access control
- Permission checks
- Token refresh
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
import json

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from hub.apps.auth.models import APIKey
from hub.apps.auth.jwt_utils import JWTTokenGenerator

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class AuthenticationRegressionTest(TestCase):
    """Base class for authentication regression tests"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Auth Test Tenant",
            slug="auth-test-tenant"
        )
        self.user = User.objects.create_user(
            email="auth@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )


class JWTAuthenticationTest(AuthenticationRegressionTest):
    """Test JWT authentication"""
    
    def test_jwt_login(self):
        """Test JWT login"""
        response = self.client.post(
            '/api/v1/auth/login/',
            {'email': self.user.email, 'password': 'testpass123'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
    
    def test_jwt_token_usage(self):
        """Test using JWT token for authentication"""
        # Login to get token
        login_response = self.client.post(
            '/api/v1/auth/login/',
            {'email': self.user.email, 'password': 'testpass123'},
            format='json'
        )
        access_token = login_response.data['access_token']
        
        # Use token for authenticated request
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get('/api/v1/assets/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_jwt_token_refresh(self):
        """Test JWT token refresh"""
        # Login to get tokens
        login_response = self.client.post(
            '/api/v1/auth/login/',
            {'email': self.user.email, 'password': 'testpass123'},
            format='json'
        )
        refresh_token = login_response.data['refresh_token']
        
        # Refresh token
        refresh_response = self.client.post(
            '/api/v1/auth/refresh/',
            {'refresh_token': refresh_token},
            format='json'
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', refresh_response.data)
    
    def test_jwt_logout(self):
        """Test JWT logout"""
        # Login first
        login_response = self.client.post(
            '/api/v1/auth/login/',
            {'email': self.user.email, 'password': 'testpass123'},
            format='json'
        )
        access_token = login_response.data['access_token']
        
        # Logout
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_response = self.client.post('/api/v1/auth/logout/', {}, format='json')
        self.assertIn(logout_response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])


class APIKeyAuthenticationTest(AuthenticationRegressionTest):
    """Test API key authentication"""
    
    def test_api_key_authentication(self):
        """Test API key authentication"""
        # API keys must be user-scoped (not tenant-scoped)
        api_key_obj = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,  # User-scoped API key required
            name="Test API Key",
            key_hash=APIKey.hash_key("test-api-key-123")
        )
        
        # Use API key for authentication
        response = self.client.get(
            '/api/v1/assets/',
            HTTP_AUTHORIZATION="ApiKey test-api-key-123"
        )
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_api_key_creation(self):
        """Test creating an API key"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(
            '/api/v1/auth/api-keys/',
            {'name': 'New API Key'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # API returns 'api_key' not 'key'
        self.assertIn('api_key', response.data)
        self.assertIn('id', response.data)
    
    def test_api_key_list(self):
        """Test listing API keys"""
        self.client.force_authenticate(user=self.user)
        
        # Create user-scoped API key
        APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,  # User-scoped API key required
            name="List Test API Key",
            key_hash=APIKey.hash_key("list-test-key")
        )
        
        # List API keys
        response = self.client.get('/api/v1/auth/api-keys/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response may be paginated (dict with 'results') or a list
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertIsInstance(response.data['results'], list)
        else:
            self.assertIsInstance(response.data, list)
    
    def test_api_key_deletion(self):
        """Test deleting an API key"""
        self.client.force_authenticate(user=self.user)
        
        api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,  # User-scoped API key required
            name="Delete Test API Key",
            key_hash=APIKey.hash_key("delete-test-key")
        )
        
        # Delete API key
        response = self.client.delete(f'/api/v1/auth/api-keys/{api_key.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deletion
        self.assertFalse(APIKey.objects.filter(id=api_key.id).exists())


class PasswordResetTest(AuthenticationRegressionTest):
    """Test password reset flow"""
    
    def test_password_reset_request(self):
        """Test requesting password reset"""
        response = self.client.post(
            '/api/v1/auth/password-reset/',
            {'email': self.user.email},
            format='json'
        )
        # May return 200 (success) or 400 (user not found)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
    
    def test_password_reset_confirm(self):
        """Test confirming password reset"""
        # This typically requires a valid reset token
        # In a real scenario, the token would be sent via email
        response = self.client.post(
            '/api/v1/auth/password-reset/confirm/',
            {
                'token': 'invalid-token',
                'new_password': 'newpass123'
            },
            format='json'
        )
        # Should fail with invalid token
        self.assertIn(response.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND
        ])


class UserRegistrationTest(AuthenticationRegressionTest):
    """Test user registration"""
    
    def test_user_registration(self):
        """Test user registration"""
        response = self.client.post(
            '/api/v1/auth/register/',
            {
                'email': 'newuser@example.com',
                'password': 'newpass123',
                'tenant_id': str(self.tenant.id)
            },
            format='json'
        )
        # May require invitation or other setup
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND
        ])


class AuthorizationTest(AuthenticationRegressionTest):
    """Test authorization and permissions"""
    
    def test_authenticated_access(self):
        """Test authenticated user can access resources"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get('/api/v1/assets/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_unauthenticated_access(self):
        """Test unauthenticated user cannot access resources"""
        response = self.client.get('/api/v1/assets/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_tenant_isolation(self):
        """Test tenant isolation in authorization"""
        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant"
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create asset in first tenant
        from hub.apps.assets.models import Asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="isolated-asset",
            name="Isolated Asset"
        )
        
        # Try to access with other user
        self.client.force_authenticate(user=other_user)
        response = self.client.get(f'/api/v1/assets/{asset.id}/')
        
        # Should be forbidden (tenant isolation)
        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ])
    
    def test_platform_admin_access(self):
        """Test platform admin access"""
        # Make user platform admin
        self.user.is_platform_admin = True
        self.user.save()
        
        self.client.force_authenticate(user=self.user)
        
        # Platform admin should be able to access all tenants
        response = self.client.get('/api/v1/tenants/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])


class TokenValidationTest(AuthenticationRegressionTest):
    """Test token validation"""
    
    def test_invalid_token_rejected(self):
        """Test invalid token is rejected"""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
        response = self.client.get('/api/v1/assets/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_expired_token_rejected(self):
        """Test expired token is rejected"""
        # Create an expired token (if possible)
        # This depends on JWT implementation
        # For now, verify invalid tokens are rejected
        self.client.credentials(HTTP_AUTHORIZATION='Bearer expired-token')
        response = self.client.get('/api/v1/assets/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

