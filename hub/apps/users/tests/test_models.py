"""
Unit tests for User model.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class UserModelTest(TestCase):
    """Test User model"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
    
    def test_create_user(self):
        """Test user creation"""
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
            status=UserStatus.ACTIVE
        )
        
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.tenant, self.tenant)
        self.assertEqual(user.status, UserStatus.ACTIVE)
        self.assertTrue(user.check_password("testpass123"))
    
    def test_user_status_choices(self):
        """Test user status enum"""
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        
        user.status = UserStatus.SUSPENDED
        user.save()
        self.assertEqual(user.status, UserStatus.SUSPENDED)

