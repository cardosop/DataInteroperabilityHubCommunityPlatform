"""
Unit tests for JWT utilities.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.conf import settings
from hub.apps.tenants.models import Tenant
from hub.apps.auth.jwt_utils import JWTTokenGenerator


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class JWTUtilsTest(TestCase):
    """Test JWT utilities"""
    
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
    
    def test_generate_access_token(self):
        """Test generate_access_token"""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user,
            tenant_id=str(self.tenant.id)
        )
        
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 0)
    
    def test_decode_access_token(self):
        """Test decode_access_token"""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user,
            tenant_id=str(self.tenant.id)
        )
        
        payload = JWTTokenGenerator.decode_access_token(token)
        
        self.assertIsNotNone(payload)
        self.assertEqual(payload['sub'], str(self.user.id))
        self.assertEqual(payload['tenant_id'], str(self.tenant.id))
        self.assertEqual(payload['email'], self.user.email)
    
    def test_decode_invalid_token(self):
        """Test decode_access_token with invalid token"""
        payload = JWTTokenGenerator.decode_access_token("invalid.token.here")
        self.assertIsNone(payload)
    
    def test_validate_token_version(self):
        """Test validate_token_version"""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user,
            tenant_id=str(self.tenant.id)
        )
        
        payload = JWTTokenGenerator.decode_access_token(token)
        is_valid = JWTTokenGenerator.validate_token_version(payload, self.user)
        
        self.assertTrue(is_valid)
        
        # Invalidate token version
        self.user.token_version += 1
        self.user.save()
        is_valid = JWTTokenGenerator.validate_token_version(payload, self.user)
        self.assertFalse(is_valid)
    
    def test_get_user_from_token(self):
        """Test get_user_from_token"""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user,
            tenant_id=str(self.tenant.id)
        )
        
        payload = JWTTokenGenerator.decode_access_token(token)
        user = JWTTokenGenerator.get_user_from_token(payload)
        
        self.assertEqual(user, self.user)

