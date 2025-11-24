"""
Unit tests for Auth models (APIKey).
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.auth.models import APIKey

User = get_user_model()


class APIKeyModelTest(TestCase):
    """Test APIKey model"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
    
    def test_create_api_key(self):
        """Test API key creation"""
        key = APIKey.generate_key()
        key_hash = APIKey.hash_key(key)
        
        api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            key_hash=key_hash,
        )
        
        self.assertEqual(api_key.tenant, self.tenant)
        self.assertEqual(api_key.user, self.user)
        self.assertEqual(api_key.name, "Test API Key")
        self.assertIsNotNone(api_key.key_hash)
    
    def test_api_key_generate_and_hash(self):
        """Test API key generation and hashing"""
        key = APIKey.generate_key()
        self.assertIsInstance(key, str)
        self.assertGreater(len(key), 0)
        
        key_hash = APIKey.hash_key(key)
        self.assertIsInstance(key_hash, str)
        self.assertEqual(len(key_hash), 64)  # SHA-256 hex digest length
    
    def test_api_key_is_expired(self):
        """Test API key expiration check"""
        from django.utils import timezone
        from datetime import timedelta
        
        key = APIKey.generate_key()
        key_hash = APIKey.hash_key(key)
        
        # Non-expiring key
        api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            key_hash=key_hash,
            expires_at=None
        )
        self.assertFalse(api_key.is_expired())
        
        # Expired key
        api_key.expires_at = timezone.now() - timedelta(days=1)
        api_key.save()
        self.assertTrue(api_key.is_expired())

