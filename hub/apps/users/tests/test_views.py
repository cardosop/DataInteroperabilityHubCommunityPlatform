"""
Unit tests for User API views.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
import uuid

from hub.apps.users.models import User, Role, UserRole, UserStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class UserViewSetTest(TestCase):
    """Test UserViewSet CRUD operations"""
    
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
        
        # Create platform admin user
        self.platform_admin = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            is_platform_admin=True
        )
        
        # Create tenant admin user
        self.tenant_admin = User.objects.create_user(
            email="tenant_admin@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create regular user
        self.regular_user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Active subscription required so TenantSuspensionMiddleware allows writes
        ensure_tenant_has_active_subscription(self.tenant)
    
    def test_create_user(self):
        """Test user creation"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        data = {
            "email": "newuser@example.com",
            "display_name": "New User",
            "password": "testpass123",
            "tenant": str(self.tenant.id),
            "status": "ACTIVE"
        }
        
        response = self.client.post("/api/v1/users/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "newuser@example.com")
        self.assertEqual(response.data["status"], "ACTIVE")
        
        # Verify user was created
        user = User.objects.get(email="newuser@example.com")
        self.assertEqual(user.tenant, self.tenant)
        self.assertEqual(user.status, UserStatus.ACTIVE)
    
    def test_list_users(self):
        """Test user listing (tenant-scoped)"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        response = self.client.get("/api/v1/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should only see users in the same tenant
        user_emails = [user["email"] for user in response.data["results"]]
        self.assertIn("tenant_admin@example.com", user_emails)
        self.assertIn("user@example.com", user_emails)
        self.assertNotIn("admin@example.com", user_emails)  # Platform admin not in tenant
    
    def test_retrieve_user(self):
        """Test user retrieval"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        response = self.client.get(f"/api/v1/users/{self.regular_user.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "user@example.com")
    
    def test_update_user(self):
        """Test user update"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        data = {
            "display_name": "Updated Name"
        }
        
        response = self.client.patch(
            f"/api/v1/users/{self.regular_user.id}/",
            data,
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["display_name"], "Updated Name")
        
        # Verify update
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.display_name, "Updated Name")
    
    def test_delete_user_no_resources(self):
        """Test user deletion when user has no resources (hard delete)"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        # Create a user with no resources
        test_user = User.objects.create_user(
            email="todelete@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        user_id = test_user.id
        
        response = self.client.delete(f"/api/v1/users/{user_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify user was deleted
        self.assertFalse(User.objects.filter(id=user_id).exists())
    
    def test_delete_user_with_resources(self):
        """Test user deletion when user has resources (soft delete)"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        # For now, _user_has_resources returns False, so this will hard delete
        # When resources are implemented, this should soft delete
        # TODO: Update this test when resource checking is implemented
        pass
    
    def test_invite_user(self):
        """Test user invitation"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        data = {
            "email": "invited@example.com",
            "display_name": "Invited User"
        }
        
        response = self.client.post("/api/v1/users/invite/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "invited@example.com")
        self.assertEqual(response.data["status"], "INVITED")
        
        # Verify invitation token was created
        user = User.objects.get(email="invited@example.com")
        self.assertIsNotNone(user.invitation_token)
        self.assertIsNotNone(user.invitation_token_expires_at)
        self.assertGreater(
            user.invitation_token_expires_at,
            timezone.now() + timedelta(days=6)
        )
    
    def test_tenant_scoping(self):
        """Test that users can only see users in their tenant"""
        self.client.force_authenticate(user=self.regular_user)
        
        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )
        
        # Regular user should not see users from other tenant
        response = self.client.get("/api/v1/users/")
        user_emails = [user["email"] for user in response.data["results"]]
        self.assertNotIn("other@example.com", user_emails)
        
        # Regular user should not be able to retrieve other tenant's user
        response = self.client.get(f"/api/v1/users/{other_user.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_platform_admin_sees_all_users(self):
        """Test that platform admins can see all users"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get("/api/v1/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        user_emails = [user["email"] for user in response.data["results"]]
        # Platform admin should see all users
        self.assertIn("admin@example.com", user_emails)
        self.assertIn("tenant_admin@example.com", user_emails)
        self.assertIn("user@example.com", user_emails)

