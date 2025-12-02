"""
Unit tests for user deletion rules.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.users.models import User, UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class UserDeletionTest(TestCase):
    """Test user deletion rules and resource checking"""
    
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
        
        # Create tenant admin user
        self.tenant_admin = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_hard_delete_user_no_resources(self):
        """Test hard delete when user has no resources"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        # Create a user with no resources
        test_user = User.objects.create_user(
            email="todelete@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        user_id = test_user.id
        
        response = self.client.delete(f"/api/v1/users/users/{user_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify user was hard deleted
        self.assertFalse(User.objects.filter(id=user_id).exists())
    
    def test_soft_delete_user_with_resources(self):
        """Test soft delete when user has resources"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        # Create a user
        test_user = User.objects.create_user(
            email="todelete@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        user_id = test_user.id
        
        # TODO: When resources are implemented (assets, datasets, etc.),
        # create some resources for this user and verify soft delete behavior
        # For now, _user_has_resources returns False, so this will hard delete
        
        # When resources exist, deletion should:
        # 1. Set status to DISABLED
        # 2. Return 200 OK with message
        # 3. Not actually delete the user
        
        # This test will be updated when resource checking is implemented
        pass
    
    def test_cannot_delete_self(self):
        """Test that a user cannot delete themselves"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        response = self.client.delete(f"/api/v1/users/users/{self.tenant_admin.id}/")
        # Should return 400 Bad Request with error message
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('cannot delete themselves', response.data['error'].lower())
        
        # Verify user still exists
        self.assertTrue(User.objects.filter(id=self.tenant_admin.id).exists())
    
    def test_delete_invited_user(self):
        """Test deleting an invited user (should hard delete)"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        # Create an invited user
        invited_user = User.objects.create_user(
            email="invited@example.com",
            tenant=self.tenant,
            status=UserStatus.INVITED
        )
        user_id = invited_user.id
        
        response = self.client.delete(f"/api/v1/users/users/{user_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify user was hard deleted
        self.assertFalse(User.objects.filter(id=user_id).exists())
    
    def test_delete_disabled_user(self):
        """Test deleting a disabled user"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        # Create a disabled user
        disabled_user = User.objects.create_user(
            email="disabled@example.com",
            tenant=self.tenant,
            status=UserStatus.DISABLED
        )
        user_id = disabled_user.id
        
        response = self.client.delete(f"/api/v1/users/users/{user_id}/")
        # Disabled user should be hard deletable if no resources
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify user was hard deleted
        self.assertFalse(User.objects.filter(id=user_id).exists())

