"""
Unit tests for role management.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.users.models import User, Role, UserRole, UserStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class RoleManagementTest(TestCase):
    """Test role assignment and removal"""
    
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
        
        # Create roles
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )
        self.provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )
        
        # Create tenant admin user
        self.tenant_admin = User.objects.create_user(
            email="admin@example.com",
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
    
    def test_assign_role(self):
        """Test assigning a role to a user"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        initial_token_version = self.regular_user.token_version
        
        data = {
            "role_id": str(self.provider_role.id),
            "action": "assign"
        }
        
        response = self.client.post(
            f"/api/v1/users/{self.regular_user.id}/roles/",
            data,
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify role was assigned
        self.assertTrue(
            UserRole.objects.filter(
                user=self.regular_user,
                role=self.provider_role
            ).exists()
        )
        
        # Verify token version was incremented
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.token_version, initial_token_version + 1)
    
    def test_remove_role(self):
        """Test removing a role from a user"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        # First assign a role
        UserRole.objects.create(user=self.regular_user, role=self.provider_role)
        initial_token_version = self.regular_user.token_version
        
        data = {
            "role_id": str(self.provider_role.id),
            "action": "remove"
        }
        
        response = self.client.post(
            f"/api/v1/users/{self.regular_user.id}/roles/",
            data,
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify role was removed
        self.assertFalse(
            UserRole.objects.filter(
                user=self.regular_user,
                role=self.provider_role
            ).exists()
        )
        
        # Verify token version was incremented
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.token_version, initial_token_version + 1)
    
    def test_assign_role_cross_tenant(self):
        """Test that roles can only be assigned from the same tenant"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        # Create another tenant and role
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        other_role, _ = Role.objects.get_or_create(
            tenant=other_tenant,
            name="DATA_CONSUMER",
            defaults={"description": "Data Consumer"}
        )
        
        data = {
            "role_id": str(other_role.id),
            "action": "assign"
        }
        
        response = self.client.post(
            f"/api/v1/users/{self.regular_user.id}/roles/",
            data,
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_list_roles(self):
        """Test listing roles (tenant-scoped)"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        response = self.client.get("/api/v1/users/roles/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        role_names = [role["name"] for role in response.data["results"]]
        self.assertIn("TENANT_ADMIN", role_names)
        self.assertIn("DATA_PROVIDER", role_names)
    
    def test_user_roles_in_serializer(self):
        """Test that user serializer includes roles"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        # Assign a role
        UserRole.objects.create(user=self.regular_user, role=self.provider_role)
        
        response = self.client.get(f"/api/v1/users/{self.regular_user.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify roles are included in response (serializer returns role names as strings)
        self.assertIn("roles", response.data)
        role_names = list(response.data["roles"])
        self.assertIn("DATA_PROVIDER", role_names)

