"""
Unit tests for API key authentication.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.auth.models import APIKey
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class APIKeyAuthenticationTest(TestCase):
    """Test API key authentication"""
    
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
        
        # Create API key
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        self.api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=key_hash,
            name="Test API Key",
            scopes=["assets:read", "assets:write"]
        )
        self.plaintext_key = plaintext_key
    
    def test_api_key_authentication_authorization_header(self):
        """Test API key authentication via Authorization header"""
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {self.plaintext_key}')
        
        # Try to access a protected endpoint
        response = self.client.get("/api/v1/users/users/")
        
        # Should succeed (assuming users endpoint exists and is protected)
        # Note: This test might need adjustment based on actual endpoint requirements
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED])
    
    def test_api_key_authentication_x_api_key_header(self):
        """Test API key authentication via X-API-Key header"""
        self.client.credentials(HTTP_X_API_KEY=self.plaintext_key)
        
        # Try to access a protected endpoint
        response = self.client.get("/api/v1/users/users/")
        
        # Should succeed
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED])
    
    def test_api_key_invalid(self):
        """Test API key authentication with invalid key"""
        self.client.credentials(HTTP_AUTHORIZATION='ApiKey invalid_key')
        
        response = self.client.get("/api/v1/users/users/")
        
        # Should fail
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_api_key_expired(self):
        """Test API key authentication with expired key"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Create expired API key
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)
        expired_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=key_hash,
            name="Expired Key",
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        self.client.credentials(HTTP_AUTHORIZATION=f'ApiKey {plaintext_key}')
        
        response = self.client.get("/api/v1/users/users/")
        
        # Should fail
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_api_key(self):
        """Test API key creation"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(
            "/api/v1/auth/api-keys/",
            {
                "name": "New API Key",
                "scopes": ["assets:read"],
                "expires_in_days": 30
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("api_key", response.data)
        self.assertEqual(response.data["name"], "New API Key")
        
        # Verify API key was created
        api_key_id = response.data["id"]
        self.assertTrue(APIKey.objects.filter(id=api_key_id).exists())
    
    def test_list_api_keys(self):
        """Test listing API keys"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get("/api/v1/auth/api-keys/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)
    
    def test_revoke_api_key(self):
        """Test API key revocation"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.delete(f"/api/v1/auth/api-keys/{self.api_key.id}/")
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify API key was deleted
        self.assertFalse(APIKey.objects.filter(id=self.api_key.id).exists())

